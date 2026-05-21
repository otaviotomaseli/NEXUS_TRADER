"""
Rotas para transações no mercado exterior (EUA).

Gerencia compra, venda e exclusão de ativos internacionais,
incluindo cálculo de imposto sobre lucro em vendas.
"""

import logging

from flask import Blueprint, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import TransacaoExterior, Configuracao
from app.services.cotacao import mercado_aberto
from app.services.imposto import calcular_imposto_venda_us

logger = logging.getLogger(__name__)

# Blueprint para agrupar as rotas de exterior
exterior_bp = Blueprint('exterior', __name__)


@exterior_bp.route('/comprar_us', methods=['POST'])
@login_required
def comprar_us():
    """Registra uma compra de ativo no mercado americano."""
    # Verifica se o mercado dos EUA está aberto
    if not mercado_aberto('US'):
        flash('MERCADO FECHADO: Não é possível comprar nos EUA agora.', 'error')
        return redirect(url_for('brasil.dashboard'))

    try:
        qtd = int(request.form.get('quantidade', 0))
        valor = float(request.form.get('valor_compra', 0))
        if qtd <= 0 or valor <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Dados inválidos. Verifique quantidade e valor.', 'error')
        return redirect(url_for('brasil.dashboard'))

    nova_compra = TransacaoExterior(
        user_id=current_user.id,
        tipo_ativo=request.form.get('tipo', '').strip(),
        codigo=request.form.get('codigo', '').upper().strip(),
        tipo_transacao='Compra',
        quantidade=qtd,
        valor_total=valor,
        data=request.form.get('data_compra', '').strip(),
        banco=request.form.get('banco', '').strip(),
    )
    db.session.add(nova_compra)
    db.session.commit()
    flash('Compra EUA registrada!', 'success')
    return redirect(url_for('brasil.dashboard'))


@exterior_bp.route('/vender_us', methods=['POST'])
@login_required
def vender_us():
    """Registra uma venda de ativo no mercado americano com cálculo de imposto."""
    # Verifica se o mercado dos EUA está aberto
    if not mercado_aberto('US'):
        flash('MERCADO FECHADO: Não é possível vender nos EUA agora.', 'error')
        return redirect(url_for('brasil.dashboard'))

    codigo = request.form.get('codigo', '').strip()
    tipo_ativo = request.form.get('tipo_ativo', '').strip()
    try:
        qtd_vendida = int(request.form.get('quantidade', 0))
        valor_venda = float(request.form.get('valor_venda', 0))
        if qtd_vendida <= 0 or valor_venda <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Dados inválidos. Verifique quantidade e valor.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Carrega configurações fiscais do usuário
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()

    # Calcula preço médio ponderado (PM) das compras e vendas anteriores
    transacoes = TransacaoExterior.query.filter_by(
        user_id=current_user.id, codigo=codigo,
    ).all()
    qtd_atual = 0
    custo_atual = 0.0
    for t in transacoes:
        if t.tipo_transacao == 'Compra':
            qtd_atual += t.quantidade
            custo_atual += t.valor_total
        else:
            pm = custo_atual / qtd_atual if qtd_atual > 0 else 0
            qtd_atual -= t.quantidade
            custo_atual -= (t.quantidade * pm)

    pm_venda = custo_atual / qtd_atual if qtd_atual > 0 else 0
    lucro = valor_venda - (qtd_vendida * pm_venda)
    imposto, darf = calcular_imposto_venda_us(lucro, conf)

    nova_venda = TransacaoExterior(
        user_id=current_user.id, tipo_ativo=tipo_ativo, codigo=codigo,
        tipo_transacao='Venda', quantidade=qtd_vendida, valor_total=valor_venda,
        data=request.form.get('data_venda'), lucro_perda=lucro,
        imposto=imposto, darf=darf,
    )
    db.session.add(nova_venda)
    db.session.commit()
    flash('Venda EUA realizada!', 'success')
    return redirect(url_for('brasil.dashboard'))


@exterior_bp.route('/excluir_us/<int:id>')
@login_required
def excluir_us(id):
    """Exclui uma transação exterior desde que pertença ao usuário atual."""
    t = TransacaoExterior.query.get(id)
    if t and t.user_id == current_user.id:
        db.session.delete(t)
        db.session.commit()
        flash('Lançamento excluído.', 'success')
    return redirect(request.referrer or url_for('brasil.dashboard'))
