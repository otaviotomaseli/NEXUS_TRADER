"""
Blueprint de importação de notas de corretagem via CSV.

Permite ao usuário fazer upload de arquivos CSV com transações
para cadastro em lote nos mercados Brasil, Exterior e Cripto.
"""
import csv
import io
import logging
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user

from app import db
from app.models import Transacao, TransacaoExterior, TransacaoCripto

logger = logging.getLogger(__name__)

importar_bp = Blueprint('importar', __name__, url_prefix='/importar')

# Colunas que devem estar presentes em todo CSV de importação
COLUNAS_OBRIGATORIAS = {'data', 'tipo_ativo', 'codigo', 'tipo_transacao', 'quantidade', 'valor_total'}
COLUNAS_OPCIONAIS = {'banco'}
COLUNAS_ESPERADAS = COLUNAS_OBRIGATORIAS | COLUNAS_OPCIONAIS


# --- Página inicial de importação ---
@importar_bp.route('/', methods=['GET'])
@login_required
def pagina_importar():
    """Exibe a página de upload de CSV."""
    return render_template('importar.html')


# --- Upload e processamento do CSV ---
@importar_bp.route('/upload', methods=['POST'])
@login_required
def importar_csv():
    """Processa o upload do CSV e insere as transações no banco."""
    # Valida o mercado selecionado no formulário
    mercado = request.form.get('mercado', '').strip().upper()
    if mercado not in ('BR', 'US', 'CRIPTO'):
        flash('Selecione um mercado válido (Brasil, Exterior ou Cripto).', 'error')
        return redirect(url_for('importar.pagina_importar'))

    # Verifica se um arquivo foi enviado
    arquivo = request.files.get('csv_file')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('importar.pagina_importar'))

    # Tenta decodificar como UTF-8 com BOM (padrão Excel), fallback para Latin-1
    try:
        conteudo = arquivo.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            conteudo = arquivo.read().decode('latin-1')
        except UnicodeDecodeError:
            flash('Erro ao ler o arquivo. Use codificação UTF-8 ou Latin-1.', 'error')
            return redirect(url_for('importar.pagina_importar'))

    # Verifica se o arquivo não está vazio
    linhas = conteudo.strip().splitlines()
    if not linhas:
        flash('Arquivo vazio.', 'error')
        return redirect(url_for('importar.pagina_importar'))

    # Valida que todas as colunas obrigatórias estão presentes no CSV
    reader = csv.DictReader(linhas)
    colunas = set(reader.fieldnames or [])
    if not COLUNAS_OBRIGATORIAS.issubset(colunas):
        faltando = COLUNAS_OBRIGATORIAS - colunas
        flash(
            f'Colunas obrigatórias faltando: {", ".join(sorted(faltando))}. '
            f'Esperado: data, tipo_ativo, codigo, tipo_transacao, quantidade, valor_total.',
            'error',
        )
        return redirect(url_for('importar.pagina_importar'))

    importados = 0
    erros = []

    # Seleciona o modelo SQLAlchemy correspondente ao mercado
    Modelo = {
        'BR': Transacao,
        'US': TransacaoExterior,
        'CRIPTO': TransacaoCripto,
    }[mercado]

    # Processa cada linha do CSV (start=2 porque linha 1 é o cabeçalho)
    for i, row in enumerate(reader, start=2):
        try:
            # Extrai e limpa os campos de cada linha
            data = row.get('data', '').strip()
            tipo_ativo = row.get('tipo_ativo', '').strip().lower()
            codigo = row.get('codigo', '').strip().upper()
            tipo_transacao = row.get('tipo_transacao', '').strip().capitalize()
            quantidade_str = row.get('quantidade', '').strip()
            valor_str = row.get('valor_total', '').strip()
            banco = row.get('banco', '').strip() or 'Não Informado'

            # Verifica se nenhum campo obrigatório está vazio
            if not all([data, tipo_ativo, codigo, tipo_transacao, quantidade_str, valor_str]):
                erros.append(f'Linha {i}: campos obrigatórios vazios.')
                continue

            # Valida o tipo de transação (apenas Compra ou Venda são aceitos)
            if tipo_transacao not in ('Compra', 'Venda'):
                erros.append(f'Linha {i}: tipo_transacao deve ser "Compra" ou "Venda".')
                continue

            # Converte quantidade: inteira para BR/US, fracionária para Cripto
            try:
                quantidade = float(quantidade_str)
                if mercado != 'CRIPTO':
                    quantidade = int(quantidade)
            except ValueError:
                erros.append(f'Linha {i}: quantidade inválida "{quantidade_str}".')
                continue

            # Converte valor total
            try:
                valor_total = float(valor_str)
            except ValueError:
                erros.append(f'Linha {i}: valor_total inválido "{valor_str}".')
                continue

            # Rejeita valores negativos ou zero na quantidade
            if quantidade <= 0 or valor_total < 0:
                erros.append(f'Linha {i}: quantidade ou valor negativos.')
                continue

            # Valida formato da data (YYYY-MM-DD)
            try:
                datetime.strptime(data, '%Y-%m-%d')
            except ValueError:
                erros.append(f'Linha {i}: data inválida "{data}". Use AAAA-MM-DD.')
                continue

            # Cria o objeto da transação e adiciona à sessão do banco
            obj = Modelo(
                user_id=current_user.id,
                tipo_ativo=tipo_ativo,
                codigo=codigo,
                tipo_transacao=tipo_transacao,
                quantidade=quantidade,
                valor_total=valor_total,
                data=data,
                banco=banco,
            )
            db.session.add(obj)
            importados += 1

        # Captura qualquer erro inesperado em uma linha sem interromper as demais
        except Exception as e:
            erros.append(f'Linha {i}: erro inesperado - {str(e)}')

    # Persiste todas as transações válidas no banco
    db.session.commit()

    # Exibe feedback: sucesso para transações importadas
    if importados:
        flash(f'{importados} transação(ões) importada(s) com sucesso!', 'success')

    # Exibe erros (limitado aos 5 primeiros para não poluir a tela)
    if erros:
        for e in erros[:5]:
            flash(e, 'error')
        if len(erros) > 5:
            flash(f'E mais {len(erros) - 5} erro(s). Corrija e tente novamente.', 'error')

    return redirect(url_for('importar.pagina_importar'))


# --- Download de arquivo CSV modelo ---
@importar_bp.route('/modelo')
@login_required
def baixar_modelo():
    """Download de um arquivo CSV modelo para preenchimento."""
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    # Cabeçalho com todas as colunas aceitas (obrigatórias + opcionais)
    writer.writerow(['data', 'tipo_ativo', 'codigo', 'tipo_transacao', 'quantidade', 'valor_total', 'banco'])
    # Linhas de exemplo para o usuário seguir o formato
    writer.writerow(['2024-01-15', 'acao', 'PETR4', 'Compra', '100', '4500.00', 'NuInvest'])
    writer.writerow(['2024-02-20', 'fii', 'MXRF11', 'Compra', '50', '5000.00', 'Rico'])
    writer.writerow(['2024-03-10', 'acao', 'VALE3', 'Venda', '50', '3500.00', 'NuInvest'])
    output.seek(0)
    # Envia o CSV como download com codificação UTF-8 com BOM (compatível com Excel)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='modelo_importacao.csv',
    )
