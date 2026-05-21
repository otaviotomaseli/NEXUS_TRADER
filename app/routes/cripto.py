"""
Rotas para transações com criptomoedas.

Gerencia compra, venda e exclusão de ativos digitais,
incluindo cálculo de imposto sobre lucro em vendas.
"""

# Logger para registrar eventos específicos do módulo de criptomoedas
import logging

# Flask: Blueprint, redirecionamento, flash messages e request
from flask import Blueprint, redirect, url_for, flash, request
# Flask-Login: protege rotas com @login_required e fornece o usuário atual
from flask_login import login_required, current_user

from app import db
# Modelos: transações de criptomoedas e configurações fiscais do usuário
from app.models import TransacaoCripto, Configuracao
# Serviço fiscal: calcula imposto sobre venda de criptomoedas (15% sobre lucro, isenção até R$ 35k/mês)
from app.services.imposto import calcular_imposto_venda_cripto

logger = logging.getLogger(__name__)

# Blueprint para agrupar as rotas de criptomoedas sob o prefixo /cripto (implícito)
cripto_bp = Blueprint('cripto', __name__)


@cripto_bp.route('/comprar_cripto', methods=['POST'])
@login_required
def comprar_cripto():
    """Registra uma compra de criptomoeda."""
    try:
        # Criptomoedas aceitam quantidade fracionada (float), diferente de ações que são inteiras
        qtd = float(request.form.get('quantidade', 0))
        valor = float(request.form.get('valor_compra', 0))
        if qtd <= 0 or valor <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Dados inválidos. Verifique quantidade e valor.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Cria registro de compra no modelo TransacaoCripto e persiste no banco
    nova_compra = TransacaoCripto(
        user_id=current_user.id,
        tipo_ativo=request.form.get('tipo', 'cripto').strip(),
        codigo=request.form.get('codigo', '').upper().strip(),
        tipo_transacao='Compra',
        quantidade=qtd,
        valor_total=valor,
        data=request.form.get('data_compra', '').strip(),
        banco=request.form.get('banco', '').strip(),
    )
    db.session.add(nova_compra)
    db.session.commit()
    flash('Compra de Criptomoeda registrada!', 'success')
    return redirect(url_for('brasil.dashboard'))


@cripto_bp.route('/vender_cripto', methods=['POST'])
@login_required
def vender_cripto():
    """Registra uma venda de criptomoeda com cálculo de imposto."""
    # Extrai e sanitiza os campos de código e tipo do ativo do formulário
    codigo = request.form.get('codigo', '').strip()
    tipo_ativo = request.form.get('tipo_ativo', '').strip()
    try:
        qtd_vendida = float(request.form.get('quantidade', 0))
        valor_venda = float(request.form.get('valor_venda', 0))
        if qtd_vendida <= 0 or valor_venda <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Dados inválidos. Verifique quantidade e valor.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Carrega configurações fiscais do usuário (isenção mensal de R$ 35k e alíquota de 15%)
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()

    # Calcula preço médio ponderado (PM) percorrendo todas as transações do ativo
    transacoes = TransacaoCripto.query.filter_by(
        user_id=current_user.id, codigo=codigo,
    ).all()
    qtd_atual = 0.0
    custo_atual = 0.0
    for t in transacoes:
        if t.tipo_transacao == 'Compra':
            qtd_atual += t.quantidade
            custo_atual += t.valor_total
        else:
            # Para vendas, deduz do estoque usando o preço médio calculado até o momento
            pm = custo_atual / qtd_atual if qtd_atual > 0 else 0
            qtd_atual -= t.quantidade
            custo_atual -= (t.quantidade * pm)

    # Calcula o lucro/prejuízo da venda e o imposto devido
    pm_venda = custo_atual / qtd_atual if qtd_atual > 0 else 0
    lucro = valor_venda - (qtd_vendida * pm_venda)
    imposto, darf = calcular_imposto_venda_cripto(lucro, valor_venda, conf)

    # Cria registro de venda no modelo TransacaoCripto e persiste
    nova_venda = TransacaoCripto(
        user_id=current_user.id, tipo_ativo=tipo_ativo, codigo=codigo,
        tipo_transacao='Venda', quantidade=qtd_vendida, valor_total=valor_venda,
        data=request.form.get('data_venda'), lucro_perda=lucro,
        imposto=imposto, darf=darf,
    )
    db.session.add(nova_venda)
    db.session.commit()
    flash('Venda de Criptomoeda realizada!', 'success')
    return redirect(url_for('brasil.dashboard'))


@cripto_bp.route('/excluir_cripto/<int:id>')
@login_required
def excluir_cripto(id):
    """Exclui uma transação de criptomoeda desde que pertença ao usuário atual."""
    # Busca a transação pelo ID; só a exclui se existir e pertencer ao usuário logado
    t = TransacaoCripto.query.get(id)
    if t and t.user_id == current_user.id:
        db.session.delete(t)
        db.session.commit()
        flash('Lançamento Cripto excluído.', 'success')
    # Retorna à página de origem ou ao dashboard como fallback
    return redirect(request.referrer or url_for('brasil.dashboard'))
