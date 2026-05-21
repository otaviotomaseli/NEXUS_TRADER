"""Rotas para edição de transações financeiras (Brasil, Exterior e Criptomoedas)."""

import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import Transacao, TransacaoExterior, TransacaoCripto

logger = logging.getLogger(__name__)
editar_bp = Blueprint('editar', __name__)

# Mapeamento dos tipos de mercado para seus respectivos modelos e rotas
# Cada tipo (br, us, cripto) aponta para: (modelo SQLAlchemy, rota de redirecionamento, rota de exclusão)
MODEL_MAP = {
    'br': (Transacao, 'brasil.dashboard', 'excluir_br'),
    'us': (TransacaoExterior, 'brasil.dashboard', 'excluir_us'),
    'cripto': (TransacaoCripto, 'brasil.dashboard', 'excluir_cripto'),
}

# Nomes legíveis para exibição no formulário
MERCADO_NOME = {
    'br': 'Brasil (B3)',
    'us': 'Exterior (EUA)',
    'cripto': 'Criptomoedas',
}


def _get_transacao(model, id):
    """Busca uma transação pelo ID e verifica se pertence ao usuário logado."""
    t = model.query.get(id)
    # Proteção contra acesso a registros de outros usuários
    if not t or t.user_id != current_user.id:
        return None
    return t


# --- Rota de edição (GET = exibe formulário, POST = processa atualização) ---
@editar_bp.route('/editar_<pais>/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(pais, id):
    """Exibe e processa o formulário de edição de uma transação existente.

    O parâmetro 'pais' determina o tipo (br/us/cripto) e o 'id' identifica
    o registro. No POST, atualiza os campos permitidos diretamente no modelo.
    """
    # Valida o tipo de mercado informado na URL
    if pais not in MODEL_MAP:
        flash('Tipo inválido.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Obtém o modelo e a transação específica, verificando propriedade
    model, redirect_route, _ = MODEL_MAP[pais]
    t = _get_transacao(model, id)
    if not t:
        flash('Transação não encontrada.', 'error')
        return redirect(url_for('brasil.dashboard'))

    if request.method == 'POST':
        # Atualiza campos de texto com os valores enviados no formulário
        t.data = request.form.get('data', t.data)
        t.codigo = request.form.get('codigo', t.codigo).upper().strip()
        t.tipo_ativo = request.form.get('tipo', t.tipo_ativo)
        t.tipo_transacao = request.form.get('tipo_transacao', t.tipo_transacao)
        t.banco = request.form.get('banco', t.banco)

        try:
            # Converte quantidade suportando tanto ponto quanto vírgula decimal
            # Se não tiver separador decimal, converte para int (ações têm quantidade inteira)
            raw_qtd = request.form.get('quantidade', str(t.quantidade))
            t.quantidade = float(raw_qtd) if '.' in raw_qtd or ',' in raw_qtd else int(float(raw_qtd))
            if t.quantidade <= 0:
                raise ValueError
            t.valor_total = float(request.form.get('valor_total', t.valor_total))
            if t.valor_total <= 0:
                raise ValueError
        except (ValueError, TypeError):
            flash('Quantidade ou valor inválidos.', 'error')
            return redirect(url_for('editar.editar', pais=pais, id=id))

        # Ao editar uma venda, zera impostos para obrigar o recálculo
        # Isso evita que o lucro/imposto anterior fique incorreto após alterar valores
        if t.tipo_transacao == 'Venda':
            t.lucro_perda = 0.0
            t.imposto = 0.0
            t.darf = 'Recalcular'

        db.session.commit()
        flash('Transação atualizada com sucesso!', 'success')
        return redirect(url_for(redirect_route))

    # GET: exibe o formulário preenchido com os dados atuais da transação
    return render_template(
        'editar.html',
        t=t,
        mercado=MERCADO_NOME.get(pais, pais.upper()),
        action=url_for('editar.editar', pais=pais, id=id),
    )
