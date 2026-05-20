import logging
from collections import defaultdict

from app.services.cotacao import buscar_preco

logger = logging.getLogger(__name__)


def processar_carteira(transacoes, buscar_cotacao=True):
    """
    Processa lista de transações e retorna:
    - carteira_ativa: dict com ativos com saldo > 0
    - carteira_completa: dict com todos os ativos
    - vendas: lista de transações de venda
    - compras: lista de transações de compra
    """
    carteira = {}
    vendas = []
    compras = []

    for t in transacoes:
        if t.tipo_transacao == 'Compra':
            compras.append(t)

        if t.codigo not in carteira:
            carteira[t.codigo] = {
                'tipo_ativo': t.tipo_ativo,
                'quantidade': 0,
                'custo_total': 0.0,
                'banco': 'Vários',
                'preco_medio': 0.0,
                'preco_atual': 0.0,
                'valor_atual': 0.0,
                'lucro_aberto': 0.0,
                'rentabilidade_pct': 0.0,
            }

        if t.tipo_transacao == 'Compra':
            carteira[t.codigo]['tipo_ativo'] = t.tipo_ativo
            carteira[t.codigo]['banco'] = getattr(t, 'banco', 'Não Informado')
            carteira[t.codigo]['quantidade'] += t.quantidade
            carteira[t.codigo]['custo_total'] += t.valor_total
        elif t.tipo_transacao == 'Venda':
            pm = (
                carteira[t.codigo]['custo_total'] / carteira[t.codigo]['quantidade']
                if carteira[t.codigo]['quantidade'] > 0 else 0
            )
            carteira[t.codigo]['quantidade'] -= t.quantidade
            carteira[t.codigo]['custo_total'] -= (t.quantidade * pm)
            vendas.append(t)

    carteira_ativa = {
        k: v for k, v in carteira.items()
        if v['quantidade'] > 0
    }

    if buscar_cotacao:
        try:
            _atualizar_cotacoes(carteira_ativa)
        except Exception as e:
            logger.error('Erro ao atualizar cotações: %s', e)

    return carteira_ativa, carteira, vendas, compras


def _atualizar_cotacoes(carteira_ativa):
    for ativo in carteira_ativa.values():
        ativo['preco_medio'] = (
            ativo['custo_total'] / ativo['quantidade']
            if ativo['quantidade'] > 0 else 0
        )
        # O preço atual será preenchido separadamente
        ativo['preco_atual'] = ativo['preco_medio']


def popular_precos_br(carteira_ativa):
    for codigo, ativo in carteira_ativa.items():
        try:
            preco = buscar_preco(f'{codigo}.SA')
            if preco is not None:
                ativo['preco_atual'] = preco
        except Exception as e:
            logger.warning('Cotação BR falhou para %s: %s', codigo, e)

        ativo['preco_medio'] = (
            ativo['custo_total'] / ativo['quantidade']
            if ativo['quantidade'] > 0 else 0
        )
        ativo['valor_atual'] = ativo['quantidade'] * ativo['preco_atual']
        ativo['lucro_aberto'] = ativo['valor_atual'] - ativo['custo_total']
        ativo['rentabilidade_pct'] = (
            (ativo['lucro_aberto'] / ativo['custo_total'] * 100)
            if ativo['custo_total'] > 0 else 0
        )


def popular_precos_us(carteira_ativa):
    for codigo, ativo in carteira_ativa.items():
        try:
            preco = buscar_preco(codigo)
            if preco is not None:
                ativo['preco_atual'] = preco
        except Exception as e:
            logger.warning('Cotação US falhou para %s: %s', codigo, e)

        ativo['preco_medio'] = (
            ativo['custo_total'] / ativo['quantidade']
            if ativo['quantidade'] > 0 else 0
        )
        ativo['valor_atual'] = ativo['quantidade'] * ativo['preco_atual']
        ativo['lucro_aberto'] = ativo['valor_atual'] - ativo['custo_total']
        ativo['rentabilidade_pct'] = (
            (ativo['lucro_aberto'] / ativo['custo_total'] * 100)
            if ativo['custo_total'] > 0 else 0
        )


def popular_precos_cripto(carteira_ativa):
    for codigo, ativo in carteira_ativa.items():
        preco = buscar_preco(codigo)
        if preco is not None:
            ativo['preco_atual'] = preco

        ativo['preco_medio'] = (
            ativo['custo_total'] / ativo['quantidade']
            if ativo['quantidade'] > 0 else 0
        )
        ativo['valor_atual'] = ativo['quantidade'] * ativo['preco_atual']
        ativo['lucro_aberto'] = ativo['valor_atual'] - ativo['custo_total']
        ativo['rentabilidade_pct'] = (
            (ativo['lucro_aberto'] / ativo['custo_total'] * 100)
            if ativo['custo_total'] > 0 else 0
        )


def calcular_preco_medio(transacoes, codigo):
    """Calcula o preço médio de um ativo específico."""
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
    return custo_atual / qtd_atual if qtd_atual > 0 else 0


def gerar_resumo_darfs(vendas):
    """Gera resumo de DARFs a partir de vendas com imposto."""
    from calendar import monthrange

    resumo = {}
    for v in vendas:
        mes_ano = v.data[:7]
        if mes_ano not in resumo:
            y, m = map(int, mes_ano.split('-'))
            y_v, m_v = (y + 1, 1) if m == 12 else (y, m + 1)
            _, last = monthrange(y_v, m_v)
            resumo[mes_ano] = {
                'mes': f'{m:02d}/{y}',
                'ano_mes_ordem': mes_ano,
                'lucro_total': 0.0,
                'imposto_total': 0.0,
                'vencimento': f'{last:02d}/{m_v:02d}/{y_v}',
            }
        resumo[mes_ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0:
            resumo[mes_ano]['imposto_total'] += v.imposto
    return sorted(
        [d for d in resumo.values() if d['imposto_total'] > 0],
        key=lambda x: x['ano_mes_ordem'],
        reverse=True,
    )


def gerar_resumo_impostos_us(vendas):
    """Gera resumo anual de impostos para exterior."""
    resumo = {}
    for v in vendas:
        ano = v.data[:4]
        if ano not in resumo:
            resumo[ano] = {
                'ano': ano,
                'lucro_total': 0.0,
                'imposto_total': 0.0,
                'vencimento': f"Na Declaração IRPF {int(ano) + 1}",
            }
        resumo[ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0:
            resumo[ano]['imposto_total'] += v.imposto
    return sorted(
        [d for d in resumo.values() if d['imposto_total'] > 0],
        key=lambda x: x['ano'],
        reverse=True,
    )
