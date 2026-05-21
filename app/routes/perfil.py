"""Rotas para gerenciamento de perfil do usuário, incluindo avatar."""

import os
import uuid
from werkzeug.utils import secure_filename
from io import BytesIO
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, make_response
from fpdf import FPDF
from flask_login import login_required, current_user
from app import db

perfil_bp = Blueprint('perfil', __name__)

# Extensões de imagem permitidas para upload
EXTENSOES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
PASTA_AVATAR = 'avatars'


def extensao_ok(nome):
    """Verifica se a extensão do arquivo está na lista de formatos permitidos."""
    return '.' in nome and nome.rsplit('.', 1)[1].lower() in EXTENSOES


def magic_bytes_ok(arquivo):
    """Valida os bytes de cabeçalho para garantir que é uma imagem real.

    Lê os primeiros bytes do arquivo e compara com os signatures (magic numbers)
    de formatos conhecidos. Isso impede que um arquivo com extensão falsa seja aceito.
    """
    inicio = arquivo.read(12)
    # Volta o ponteiro ao início para que a leitura posterior funcione
    arquivo.seek(0)
    # JPEG: FF D8 FF
    if inicio[:3] == b'\xff\xd8\xff':
        return True
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if inicio[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    # GIF: GIF87a ou GIF89a
    if inicio[:6] in (b'GIF87a', b'GIF89a'):
        return True
    # WebP: RIFF .... WEBP
    if inicio[:4] == b'RIFF' and inicio[8:12] == b'WEBP':
        return True
    return False


# --- Upload de avatar com múltiplas camadas de validação ---
@perfil_bp.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Faz upload e valida uma nova foto de perfil (avatar) para o usuário logado.

    Realiza validações consecutivas: presença do arquivo, extensão e
    magic bytes. Em caso de sucesso, salva com nome único e vincula ao usuário.
    """
    # Verifica se o campo 'avatar' existe no formulário
    if 'avatar' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('brasil.dashboard'))

    arquivo = request.files['avatar']

    # Verifica se o usuário selecionou um arquivo
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Valida a extensão do arquivo (camada rápida de verificação)
    if not extensao_ok(arquivo.filename):
        flash('Formato inválido. Use: PNG, JPG, GIF ou WebP.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Valida o conteúdo real através dos primeiros bytes (camada profunda)
    # Impede ataques de extensão falsa (ex.: um script .exe renomeado para .png)
    if not magic_bytes_ok(arquivo):
        flash('Arquivo corrompido ou não é uma imagem válida.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Gera nome único para evitar colisão e sobrescrita
    # Usa ID do usuário + hash aleatório para garantir unicidade
    nome_seguro = secure_filename(arquivo.filename)
    ext = nome_seguro.rsplit('.', 1)[1].lower()
    nome_arquivo = f'avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}'
    caminho = os.path.join(current_app.static_folder, PASTA_AVATAR, nome_arquivo)

    # Garante que a pasta de destino existe e salva o arquivo
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    arquivo.save(caminho)

    # Atualiza o avatar do usuário no banco
    current_user.avatar = nome_arquivo
    db.session.commit()

    flash('Foto de perfil atualizada!', 'success')
    return redirect(url_for('brasil.dashboard'))


# --- Remoção de avatar ---
@perfil_bp.route('/remover_avatar', methods=['POST'])
@login_required
def remover_avatar():
    """Remove a foto de perfil do usuário logado, apagando o arquivo do disco."""
    if current_user.avatar:
        # Monta o caminho completo do arquivo no diretório estático
        caminho = os.path.join(current_app.static_folder, PASTA_AVATAR, current_user.avatar)
        if os.path.exists(caminho):
            os.remove(caminho)
        # Remove a referência no banco de dados
        current_user.avatar = None
        db.session.commit()
        flash('Foto de perfil removida.', 'success')
    return redirect(url_for('brasil.dashboard'))


# --- Geração de relatório PDF da carteira ---
@perfil_bp.route('/relatorio-pdf')
@login_required
def relatorio_pdf():
    """Gera e retorna um relatório PDF com o resumo da carteira e DARFs."""
    # Importações tardias para evitar dependências circulares e carregamento desnecessário
    from app.models import Transacao, TransacaoExterior, TransacaoCripto, Configuracao
    from app.services.carteira import (
        processar_carteira, popular_precos_br, popular_precos_us,
        popular_precos_cripto, gerar_resumo_darfs,
    )
    from calendar import monthrange

    conf = Configuracao.query.filter_by(user_id=current_user.id).first()

    # --- Processa dados (mesma lógica do dashboard) ---
    # Processa a carteira brasileira: transações, vendas e DARFs
    transacoes = Transacao.query.filter_by(user_id=current_user.id).order_by(Transacao.id).all()
    carteira, _, vendas, _ = processar_carteira(transacoes, buscar_cotacao=False)
    popular_precos_br(carteira)
    total_investido = sum(v['custo_total'] for v in carteira.values())
    saldo_br = sum(v['valor_atual'] for v in carteira.values())
    total_lucro = sum(v.lucro_perda for v in vendas if v.lucro_perda > 0)
    total_perda = sum(v.lucro_perda for v in vendas if v.lucro_perda < 0)
    darfs = gerar_resumo_darfs(vendas)

    # Processa carteira do exterior (USD)
    transacoes_us = TransacaoExterior.query.filter_by(user_id=current_user.id).order_by(TransacaoExterior.id).all()
    carteira_us, _, vendas_us, _ = processar_carteira(transacoes_us, buscar_cotacao=False)
    popular_precos_us(carteira_us)
    total_investido_us = sum(v['custo_total'] for v in carteira_us.values())
    saldo_us = sum(v['valor_atual'] for v in carteira_us.values())

    # Processa carteira de criptomoedas
    transacoes_c = TransacaoCripto.query.filter_by(user_id=current_user.id).order_by(TransacaoCripto.id).all()
    carteira_c, _, vendas_c, _ = processar_carteira(transacoes_c, buscar_cotacao=False)
    popular_precos_cripto(carteira_c)
    total_investido_c = sum(v['custo_total'] for v in carteira_c.values())
    saldo_c = sum(v['valor_atual'] for v in carteira_c.values())

    # --- Gera PDF ---
    # Inicializa o documento com título, data e usuário
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 14, 'Nexus Trader - Relatorio de Investimentos', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 7, f'Gerado em: {date.today().strftime("%d/%m/%Y")}  |  Usuario: {current_user.username}', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(10)

    # Totais gerais consolidando os três mercados
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Resumo Geral', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    total_geral = saldo_br + saldo_us + saldo_c
    total_inv_geral = total_investido + total_investido_us + total_investido_c
    lucro_total = total_lucro + total_perda
    pdf.cell(0, 7, f'Total Investido: R$ {total_inv_geral:,.2f}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 7, f'Valor de Mercado: R$ {total_geral:,.2f}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 7, f'Lucro/Prejuizo Realizado: R$ {lucro_total:,.2f}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    # Seção Brasil — tabela com ticker, quantidade, preço médio, cotação, total e rentabilidade
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 9, 'Brasil (B3)', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 7, f'Investido: R$ {total_investido:,.2f}  |  Mercado: R$ {saldo_br:,.2f}  |  Lucro: R$ {total_lucro:,.2f}  |  Prejuizo: R$ {total_perda:,.2f}', new_x='LMARGIN', new_y='NEXT')
    if carteira:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 7, 'Ativo', border=1)
        pdf.cell(20, 7, 'Qtd', border=1, align='C')
        pdf.cell(30, 7, 'P.Medio', border=1, align='R')
        pdf.cell(30, 7, 'Cotacao', border=1, align='R')
        pdf.cell(30, 7, 'Total', border=1, align='R')
        pdf.cell(40, 7, 'Rent.', border=1, align='R')
        pdf.ln()
        pdf.set_font('Helvetica', '', 9)
        for codigo, ativo in carteira.items():
            pdf.cell(40, 6, codigo[:18], border=1)
            pdf.cell(20, 6, str(ativo['quantidade']), border=1, align='C')
            pdf.cell(30, 6, f"R$ {ativo['preco_medio']:.2f}", border=1, align='R')
            pdf.cell(30, 6, f"R$ {ativo['preco_atual']:.2f}", border=1, align='R')
            pdf.cell(30, 6, f"R$ {ativo['valor_atual']:.2f}", border=1, align='R')
            pdf.cell(40, 6, f"{ativo['rentabilidade_pct']:.2f}%", border=1, align='R')
            pdf.ln()
    else:
        pdf.cell(0, 7, 'Nenhum ativo na carteira.', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    # Seção Exterior — mesma estrutura mas em dólar (US$)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 9, 'Exterior (EUA)', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 7, f'Investido: US$ {total_investido_us:,.2f}  |  Mercado: US$ {saldo_us:,.2f}', new_x='LMARGIN', new_y='NEXT')
    if carteira_us:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 7, 'Ticker', border=1)
        pdf.cell(20, 7, 'Qtd', border=1, align='C')
        pdf.cell(30, 7, 'P.Medio', border=1, align='R')
        pdf.cell(30, 7, 'Cotacao', border=1, align='R')
        pdf.cell(30, 7, 'Total', border=1, align='R')
        pdf.cell(40, 7, 'Rent.', border=1, align='R')
        pdf.ln()
        pdf.set_font('Helvetica', '', 9)
        for codigo, ativo in carteira_us.items():
            pdf.cell(40, 6, codigo[:18], border=1)
            pdf.cell(20, 6, str(ativo['quantidade']), border=1, align='C')
            pdf.cell(30, 6, f"US$ {ativo['preco_medio']:.2f}", border=1, align='R')
            pdf.cell(30, 6, f"US$ {ativo['preco_atual']:.2f}", border=1, align='R')
            pdf.cell(30, 6, f"US$ {ativo['valor_atual']:.2f}", border=1, align='R')
            pdf.cell(40, 6, f"{ativo['rentabilidade_pct']:.2f}%", border=1, align='R')
            pdf.ln()
    else:
        pdf.cell(0, 7, 'Nenhum ativo na carteira.', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    # Seção Cripto — similar ao Brasil por ser em Real, com formatação especial para quantidades fracionárias
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 9, 'Criptomoedas', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 7, f'Investido: R$ {total_investido_c:,.2f}  |  Mercado: R$ {saldo_c:,.2f}', new_x='LMARGIN', new_y='NEXT')
    if carteira_c:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(40, 7, 'Ativo', border=1)
        pdf.cell(25, 7, 'Qtd', border=1, align='C')
        pdf.cell(30, 7, 'P.Medio', border=1, align='R')
        pdf.cell(30, 7, 'Cotacao', border=1, align='R')
        pdf.cell(30, 7, 'Total', border=1, align='R')
        pdf.cell(35, 7, 'Rent.', border=1, align='R')
        pdf.ln()
        pdf.set_font('Helvetica', '', 9)
        for codigo, ativo in carteira_c.items():
            pdf.cell(40, 6, codigo[:18], border=1)
            # Remove zeros à direita de quantidades fracionárias de cripto para legibilidade
            qtd_str = f"{ativo['quantidade']:.6f}".rstrip('0').rstrip('.') if isinstance(ativo['quantidade'], float) else str(ativo['quantidade'])
            pdf.cell(25, 6, qtd_str[:10], border=1, align='C')
            pdf.cell(30, 6, f"R$ {ativo['preco_medio']:.2f}", border=1, align='R')
            pdf.cell(30, 6, f"R$ {ativo['preco_atual']:.2f}", border=1, align='R')
            pdf.cell(30, 6, f"R$ {ativo['valor_atual']:.2f}", border=1, align='R')
            pdf.cell(35, 6, f"{ativo['rentabilidade_pct']:.2f}%", border=1, align='R')
            pdf.ln()
    else:
        pdf.cell(0, 7, 'Nenhum ativo na carteira.', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    # Seção DARF — pendências fiscais do mercado brasileiro (mês, lucro, imposto, vencimento)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 9, 'DARFs Pendentes (Brasil)', new_x='LMARGIN', new_y='NEXT')
    if darfs:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(30, 7, 'Mes/Ano', border=1)
        pdf.cell(30, 7, 'Lucro', border=1, align='R')
        pdf.cell(30, 7, 'Imposto', border=1, align='R')
        pdf.cell(40, 7, 'Vencimento', border=1)
        pdf.ln()
        pdf.set_font('Helvetica', '', 9)
        for d in darfs:
            pdf.cell(30, 6, d['ano_mes_ordem'][:7], border=1)
            pdf.cell(30, 6, f"R$ {d['lucro']:.2f}", border=1, align='R')
            pdf.cell(30, 6, f"R$ {d['imposto']:.2f}", border=1, align='R')
            pdf.cell(40, 6, d.get('vencimento', '-'), border=1)
            pdf.ln()
    else:
        pdf.cell(0, 7, 'Nenhum DARF pendente.', new_x='LMARGIN', new_y='NEXT')

    # Disclaimer — o relatório é informativo e não substitui orientação contábil
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 5, 'Este relatorio e uma amostra dos dados cadastrados no Nexus Trader. Consulte seu contador para declaracao oficial.', new_x='LMARGIN', new_y='NEXT', align='C')

    # Converte o PDF para bytes e retorna como attachment para download
    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    response = make_response(buf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=relatorio_nexus_{date.today().isoformat()}.pdf'
    return response
