import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import Transacao, TransacaoExterior, TransacaoCripto

logger = logging.getLogger(__name__)
editar_bp = Blueprint('editar', __name__)

MODEL_MAP = {
    'br': (Transacao, 'brasil.dashboard', 'excluir_br'),
    'us': (TransacaoExterior, 'brasil.dashboard', 'excluir_us'),
    'cripto': (TransacaoCripto, 'brasil.dashboard', 'excluir_cripto'),
}

MERCADO_NOME = {
    'br': 'Brasil (B3)',
    'us': 'Exterior (EUA)',
    'cripto': 'Criptomoedas',
}


def _get_transacao(model, id):
    t = model.query.get(id)
    if not t or t.user_id != current_user.id:
        return None
    return t


@editar_bp.route('/editar_<pais>/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(pais, id):
    if pais not in MODEL_MAP:
        flash('Tipo inválido.', 'error')
        return redirect(url_for('brasil.dashboard'))

    model, redirect_route, _ = MODEL_MAP[pais]
    t = _get_transacao(model, id)
    if not t:
        flash('Transação não encontrada.', 'error')
        return redirect(url_for('brasil.dashboard'))

    if request.method == 'POST':
        t.data = request.form.get('data', t.data)
        t.codigo = request.form.get('codigo', t.codigo).upper().strip()
        t.tipo_ativo = request.form.get('tipo', t.tipo_ativo)
        t.tipo_transacao = request.form.get('tipo_transacao', t.tipo_transacao)
        t.banco = request.form.get('banco', t.banco)

        try:
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

        if t.tipo_transacao == 'Venda':
            t.lucro_perda = 0.0
            t.imposto = 0.0
            t.darf = 'Recalcular'

        db.session.commit()
        flash('Transação atualizada com sucesso!', 'success')
        return redirect(url_for(redirect_route))

    return render_template(
        'editar.html',
        t=t,
        mercado=MERCADO_NOME.get(pais, pais.upper()),
        action=url_for('editar.editar', pais=pais, id=id),
    )
