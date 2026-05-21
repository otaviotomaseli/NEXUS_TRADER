"""Blueprint de operações Brasil — dashboard, compra, venda, configurações e exclusão de ativos B3."""
import logging
from calendar import monthrange

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import Transacao, TransacaoExterior, TransacaoCripto, Configuracao
from app.services.cotacao import status_mercado, mercado_aberto
from app.services.carteira import (
    processar_carteira, popular_precos_br, popular_precos_us,
    popular_precos_cripto, gerar_resumo_darfs,
)
from app.services.imposto import calcular_imposto_venda_br

logger = logging.getLogger(__name__)
brasil_bp = Blueprint('brasil', __name__)


@brasil_bp.route('/dashboard')
@login_required
def dashboard():
    """Exibe a página principal com resumo das carteiras Brasil, exterior e cripto.

    Carrega do banco as transações de cada categoria, calcula carteira ativa,
    popular preços atualizados, soma totais de lucro/perda e prepara os dados
    dos DARFs (Brasil e cripto) e do imposto de renda (exterior).
    """
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    # Verifica se cada mercado está aberto no momento
    mercado_br = status_mercado('BR')
    mercado_us = status_mercado('US')
    mercado_cripto = status_mercado('CRIPTO')

    # ---------- ATIVOS BRASIL (B3) ----------
    transacoes = Transacao.query.filter_by(
        user_id=current_user.id,
    ).order_by(Transacao.id).all()
    # Processa as transações para obter carteira, vendas e compras
    carteira_ativa, _, vendas, compras = processar_carteira(transacoes, buscar_cotacao=False)
    popular_precos_br(carteira_ativa)
    saldo_atual_b3 = sum(v['valor_atual'] for v in carteira_ativa.values())
    total_investido = sum(v['custo_total'] for v in carteira_ativa.values())
    total_lucro_realizado = sum(v.lucro_perda for v in vendas if v.lucro_perda > 0)
    total_perda_realizada = sum(v.lucro_perda for v in vendas if v.lucro_perda < 0)
    anos_br = sorted(list(set(t.data.split('-')[0] for t in transacoes)), reverse=True)
    lista_darfs_br = gerar_resumo_darfs(vendas)

    # Calcula a data de vencimento de cada DARF (último dia do mês seguinte)
    for v in vendas:
        if v.imposto > 0:
            y, m, d = map(int, v.data.split('-'))
            y_v, m_v = (y + 1, 1) if m == 12 else (y, m + 1)
            _, last = monthrange(y_v, m_v)
            v.vencimento_darf = f'{last:02d}/{m_v:02d}/{y_v}'
        else:
            v.vencimento_darf = '-'

    # ---------- ATIVOS EXTERIOR (US) ----------
    transacoes_us = TransacaoExterior.query.filter_by(
        user_id=current_user.id,
    ).order_by(TransacaoExterior.id).all()
    carteira_us, _, vendas_us, compras_us = processar_carteira(transacoes_us, buscar_cotacao=False)
    popular_precos_us(carteira_us)
    saldo_atual_us = sum(v['valor_atual'] for v in carteira_us.values())
    total_investido_us = sum(v['custo_total'] for v in carteira_us.values())
    total_lucro_realizado_us = sum(v.lucro_perda for v in vendas_us if v.lucro_perda > 0)
    total_perda_realizada_us = sum(v.lucro_perda for v in vendas_us if v.lucro_perda < 0)
    anos_us = sorted(list(set(t.data.split('-')[0] for t in transacoes_us)), reverse=True)

    # Agrupa impostos do exterior por ano (declarados no IRPF do ano seguinte)
    resumo_impostos_us = {}
    for v in vendas_us:
        ano = v.data[:4]
        if ano not in resumo_impostos_us:
            resumo_impostos_us[ano] = {
                'ano': ano, 'lucro_total': 0.0, 'imposto_total': 0.0,
                'vencimento': f"Na Declaração IRPF {int(ano) + 1}",
            }
        resumo_impostos_us[ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0:
            resumo_impostos_us[ano]['imposto_total'] += v.imposto
    lista_impostos_us = sorted(
        [d for d in resumo_impostos_us.values() if d['imposto_total'] > 0],
        key=lambda x: x['ano'], reverse=True,
    )

    # ---------- CRIPTOMOEDAS ----------
    transacoes_cripto = TransacaoCripto.query.filter_by(
        user_id=current_user.id,
    ).order_by(TransacaoCripto.id).all()
    carteira_cripto, _, vendas_cripto, compras_cripto = processar_carteira(
        transacoes_cripto, buscar_cotacao=False,
    )
    popular_precos_cripto(carteira_cripto)
    saldo_atual_cripto = sum(v['valor_atual'] for v in carteira_cripto.values())
    total_investido_cripto = sum(v['custo_total'] for v in carteira_cripto.values())
    total_lucro_realizado_cripto = sum(v.lucro_perda for v in vendas_cripto if v.lucro_perda > 0)
    total_perda_realizada_cripto = sum(v.lucro_perda for v in vendas_cripto if v.lucro_perda < 0)
    anos_cripto = sorted(list(set(t.data.split('-')[0] for t in transacoes_cripto)), reverse=True)
    lista_darfs_cripto = gerar_resumo_darfs(vendas_cripto)

    return render_template(
        'dashboard.html', nome=current_user.username, conf=conf,
        mercado_br=mercado_br, mercado_us=mercado_us, mercado_cripto=mercado_cripto,
        carteira=carteira_ativa, transacoes=transacoes, transacoes_us=transacoes_us,
        transacoes_cripto=transacoes_cripto, compras=compras, anos_br=anos_br,
        lista_darfs_br=lista_darfs_br,
        total_investido=total_investido, saldo_atual_b3=saldo_atual_b3,
        lucro_aberto_total_br=saldo_atual_b3 - total_investido,
        total_lucro_realizado=total_lucro_realizado,
        total_perda_realizada=total_perda_realizada,
        carteira_us=carteira_us, compras_us=compras_us, anos_us=anos_us,
        lista_impostos_us=lista_impostos_us,
        total_investido_us=total_investido_us, saldo_atual_us=saldo_atual_us,
        lucro_aberto_total_us=saldo_atual_us - total_investido_us,
        total_lucro_realizado_us=total_lucro_realizado_us,
        total_perda_realizada_us=total_perda_realizada_us,
        carteira_cripto=carteira_cripto, compras_cripto=compras_cripto,
        anos_cripto=anos_cripto, lista_darfs_cripto=lista_darfs_cripto,
        total_investido_cripto=total_investido_cripto,
        saldo_atual_cripto=saldo_atual_cripto,
        lucro_aberto_total_cripto=saldo_atual_cripto - total_investido_cripto,
        total_lucro_realizado_cripto=total_lucro_realizado_cripto,
        total_perda_realizada_cripto=total_perda_realizada_cripto,
    )


@brasil_bp.route('/comprar', methods=['POST'])
@login_required
def comprar():
    """Registra uma nova compra de ativo B3."""
    # Impede a compra se o mercado B3 estiver fechado
    if not mercado_aberto('BR'):
        flash('MERCADO FECHADO: Não é possível comprar na B3 agora.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Valida os campos numéricos do formulário
    try:
        qtd = int(request.form.get('quantidade', 0))
        valor = float(request.form.get('valor_compra', 0))
        if qtd <= 0 or valor <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Dados inválidos. Verifique quantidade e valor.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Cria e persiste o registro da compra
    nova_compra = Transacao(
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
    flash('Compra registrada!', 'success')
    return redirect(url_for('brasil.dashboard'))


@brasil_bp.route('/vender', methods=['POST'])
@login_required
def vender():
    """Registra uma nova venda de ativo B3, calcula lucro e imposto devido."""
    if not mercado_aberto('BR'):
        flash('MERCADO FECHADO: Não é possível vender na B3 agora.', 'error')
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

    operacao = request.form.get('operacao', 'swing_trade')
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()

    # Recalcula o saldo atual do ativo (soma compras, subtrai vendas anteriores)
    transacoes = Transacao.query.filter_by(
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

    # Calcula preço médio, lucro/prejuízo e o imposto devido
    pm_venda = custo_atual / qtd_atual if qtd_atual > 0 else 0
    lucro = valor_venda - (qtd_vendida * pm_venda)
    imposto, darf = calcular_imposto_venda_br(lucro, valor_venda, tipo_ativo, operacao, conf)

    # Cria e persiste o registro da venda
    nova_venda = Transacao(
        user_id=current_user.id, tipo_ativo=tipo_ativo, codigo=codigo,
        tipo_transacao='Venda', quantidade=qtd_vendida, valor_total=valor_venda,
        data=request.form.get('data_venda'), lucro_perda=lucro,
        imposto=imposto, darf=darf,
    )
    db.session.add(nova_venda)
    db.session.commit()
    flash('Venda realizada!', 'success')
    return redirect(url_for('brasil.dashboard'))


@brasil_bp.route('/salvar_config', methods=['POST'])
@login_required
def salvar_config():
    """Salva as alíquotas e faixas de isenção nas configurações do usuário."""
    # Lê e converte os campos do formulário, garantindo valores positivos
    try:
        isencao = abs(float(request.form.get('isencao', 20000)))
        swing = abs(float(request.form.get('swing', 15))) / 100
        day = abs(float(request.form.get('day', 20))) / 100
        fii = abs(float(request.form.get('fii', 20))) / 100
        exterior = abs(float(request.form.get('exterior', 15))) / 100
        isencao_cripto = abs(float(request.form.get('isencao_cripto', 35000)))
        taxa_cripto = abs(float(request.form.get('taxa_cripto', 15))) / 100
    except (ValueError, TypeError):
        flash('Valores inválidos nas configurações.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Atualiza o registro de configuração do usuário no banco
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    conf.isencao_br = isencao
    conf.taxa_swing_br = swing
    conf.taxa_day_br = day
    conf.taxa_fii_br = fii
    conf.taxa_exterior = exterior
    conf.isencao_cripto = isencao_cripto
    conf.taxa_cripto = taxa_cripto
    db.session.commit()
    flash('Configurações atualizadas com sucesso!', 'success')
    return redirect(url_for('brasil.dashboard'))


@brasil_bp.route('/excluir_br/<int:id>')
@login_required
def excluir_br(id):
    """Exclui uma transação B3 pelo ID, desde que pertença ao usuário logado."""
    t = Transacao.query.get(id)
    if t and t.user_id == current_user.id:
        db.session.delete(t)
        db.session.commit()
        flash('Lançamento excluído.', 'success')
    return redirect(request.referrer or url_for('brasil.dashboard'))
