"""
Serviço de processamento e gerenciamento da carteira de investimentos.

Responsável por:
- Processar transações (compras/vendas) e calcular saldos, preço médio, etc.
- Atualizar cotações de ativos BR, US e Cripto.
- Gerar resumos de DARF (imposto BR) e impostos para exterior (US).
"""

import logging
from collections import defaultdict

from app.services.cotacao import buscar_preco

logger = logging.getLogger(__name__)


def processar_carteira(transacoes, buscar_cotacao=True):
    """
    Processa uma lista de transações e retorna os dados consolidados da carteira.

    Args:
        transacoes: Lista de objetos de transação com atributos:
                    tipo_transacao, codigo, tipo_ativo, quantidade, valor_total, banco, etc.
        buscar_cotacao: Se True, tenta atualizar os preços atuais dos ativos após o cálculo.

    Returns:
        Tupla com:
        - carteira_ativa: dict com ativos que possuem saldo > 0
        - carteira_completa: dict com todos os ativos (inclusive saldo zerado)
        - vendas: lista de transações do tipo 'Venda'
        - compras: lista de transações do tipo 'Compra'
    """
    carteira = {}
    vendas = []
    compras = []

    for t in transacoes:
        # Acumula transações de compra para retorno separado
        if t.tipo_transacao == 'Compra':
            compras.append(t)

        # Inicializa a entrada do ativo no dicionário se ainda não existir
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

        # Atualiza saldo e custo conforme o tipo de transação
        if t.tipo_transacao == 'Compra':
            carteira[t.codigo]['tipo_ativo'] = t.tipo_ativo
            carteira[t.codigo]['banco'] = getattr(t, 'banco', 'Não Informado')
            carteira[t.codigo]['quantidade'] += t.quantidade
            carteira[t.codigo]['custo_total'] += t.valor_total
        elif t.tipo_transacao == 'Venda':
            # Calcula o preço médio atual antes de deduzir a venda
            pm = (
                carteira[t.codigo]['custo_total'] / carteira[t.codigo]['quantidade']
                if carteira[t.codigo]['quantidade'] > 0 else 0
            )
            carteira[t.codigo]['quantidade'] -= t.quantidade
            carteira[t.codigo]['custo_total'] -= (t.quantidade * pm)
            vendas.append(t)

    # Filtra apenas ativos com saldo positivo
    carteira_ativa = {
        k: v for k, v in carteira.items()
        if v['quantidade'] > 0
    }

    # Tenta buscar cotações atualizadas se solicitado
    if buscar_cotacao:
        try:
            _atualizar_cotacoes(carteira_ativa)
        except Exception as e:
            logger.error('Erro ao atualizar cotações: %s', e)

    return carteira_ativa, carteira, vendas, compras


def _atualizar_cotacoes(carteira_ativa):
    """Função interna que define preço médio e preço atual inicial para os ativos ativos."""
    for ativo in carteira_ativa.values():
        ativo['preco_medio'] = (
            ativo['custo_total'] / ativo['quantidade']
            if ativo['quantidade'] > 0 else 0
        )
        # Define o preço atual como o preço médio como fallback inicial
        ativo['preco_atual'] = ativo['preco_medio']


def popular_precos_br(carteira_ativa):
    """
    Busca e atualiza cotações de ativos brasileiros (sufixo .SA) via yfinance/Binance/AwesomeAPI.

    Para cada ativo na carteira, consulta o preço atual e recalcula valor de mercado,
    lucro/aberto e rentabilidade percentual.
    """
    for codigo, ativo in carteira_ativa.items():
        # Consulta cotação com sufixo .SA exigido pelo yfinance para ações brasileiras
        try:
            preco = buscar_preco(f'{codigo}.SA')
            if preco is not None:
                ativo['preco_atual'] = preco
        except Exception as e:
            logger.warning('Cotação BR falhou para %s: %s', codigo, e)

        # Recalcula métricas financeiras do ativo
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
    """
    Busca e atualiza cotações de ativos americanos (sem sufixo adicional).

    Para cada ativo na carteira, consulta o preço atual via yfinance/Binance/AwesomeAPI
    e recalcula as métricas financeiras.
    """
    for codigo, ativo in carteira_ativa.items():
        try:
            preco = buscar_preco(codigo)
            if preco is not None:
                ativo['preco_atual'] = preco
        except Exception as e:
            logger.warning('Cotação US falhou para %s: %s', codigo, e)

        # Recalcula métricas financeiras do ativo
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
    """
    Busca e atualiza cotações de criptomoedas via Binance/AwesomeAPI.

    Para cada ativo na carteira, consulta o preço atual e recalcula as métricas financeiras.
    """
    for codigo, ativo in carteira_ativa.items():
        preco = buscar_preco(codigo)
        if preco is not None:
            ativo['preco_atual'] = preco

        # Recalcula métricas financeiras do ativo
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
    """
    Calcula o preço médio de um ativo específico iterando sobre suas transações.

    Percorre todas as transações aplicando o método de custo médio ponderado:
    compras aumentam quantidade e custo total; vendas deduzem usando o preço médio vigente.

    Args:
        transacoes: Lista de transações (podem ser de vários ativos).
        codigo: Código do ativo a ser calculado.

    Returns:
        Preço médio ponderado do ativo, ou 0 se não houver saldo.
    """
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
    """
    Gera um resumo mensal de DARFs (imposto de renda BR) a partir de vendas com imposto.

    Agrupa vendas por mês (baseado no campo data), calcula o total de lucro e imposto,
    e determina a data de vencimento (último dia do mês seguinte).

    Args:
        vendas: Lista de transações de venda com atributos data, lucro_perda, imposto.

    Returns:
        Lista de dicionários ordenada (do mais recente para o mais antigo)
        contendo apenas meses com imposto_total > 0.
    """
    from calendar import monthrange

    resumo = {}
    for v in vendas:
        mes_ano = v.data[:7]  # Extrai 'YYYY-MM' da data
        if mes_ano not in resumo:
            y, m = map(int, mes_ano.split('-'))
            # Calcula mês seguinte para o vencimento
            y_v, m_v = (y + 1, 1) if m == 12 else (y, m + 1)
            _, last = monthrange(y_v, m_v)  # Último dia do mês de vencimento
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

    # Retorna apenas meses com imposto a pagar, ordenados do mais recente ao mais antigo
    return sorted(
        [d for d in resumo.values() if d['imposto_total'] > 0],
        key=lambda x: x['ano_mes_ordem'],
        reverse=True,
    )


def gerar_resumo_impostos_us(vendas):
    """
    Gera um resumo anual de impostos para ativos do exterior (US).

    Agrupa vendas por ano e calcula lucro total e imposto total.
    O vencimento é informado como "Na Declaração IRPF ano_seguinte".

    Args:
        vendas: Lista de transações de venda com atributos data, lucro_perda, imposto.

    Returns:
        Lista de dicionários ordenada (do mais recente para o mais antigo)
        contendo apenas anos com imposto_total > 0.
    """
    resumo = {}
    for v in vendas:
        ano = v.data[:4]  # Extrai o ano 'YYYY' da data
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

    # Retorna apenas anos com imposto a pagar, ordenados do mais recente ao mais antigo
    return sorted(
        [d for d in resumo.values() if d['imposto_total'] > 0],
        key=lambda x: x['ano'],
        reverse=True,
    )
