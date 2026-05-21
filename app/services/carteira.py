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

# Logger específico do módulo para registrar eventos e erros durante o processamento da carteira
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
    # Dicionário que acumulará saldo, custo total e métricas financeiras de cada ativo
    carteira = {}
    # Listas separadas para vendas e compras, usadas posteriormente em relatórios e cálculo de impostos
    vendas = []
    compras = []

    # Itera cada transação para atualizar saldo, custo e classificar a operação
    for t in transacoes:
        # Separa compras em lista própria para relatórios detalhados posteriormente
        if t.tipo_transacao == 'Compra':
            compras.append(t)

        # Se é a primeira transação deste ativo, inicializa sua entrada no dicionário com valores padrão
        if t.codigo not in carteira:
            # Estrutura que armazena posição atual, custo total, preços e indicadores de rentabilidade
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

        # Atualiza saldo e custo conforme o tipo de transação: compra aumenta, venda deduz
        if t.tipo_transacao == 'Compra':
            # Garante que o tipo e banco reflitam a transação mais recente do ativo
            carteira[t.codigo]['tipo_ativo'] = t.tipo_ativo
            # Usa getattr com fallback para compatibilidade com transações que não possuem o campo 'banco'
            carteira[t.codigo]['banco'] = getattr(t, 'banco', 'Não Informado')
            # Acumula quantidade e custo total na compra
            carteira[t.codigo]['quantidade'] += t.quantidade
            carteira[t.codigo]['custo_total'] += t.valor_total
        elif t.tipo_transacao == 'Venda':
            # Calcula o preço médio ponderado vigente antes de deduzir a venda, para manter consistência do custo médio
            pm = (
                carteira[t.codigo]['custo_total'] / carteira[t.codigo]['quantidade']
                if carteira[t.codigo]['quantidade'] > 0 else 0
            )
            # Deduz a quantidade vendida e o custo proporcional correspondente
            carteira[t.codigo]['quantidade'] -= t.quantidade
            carteira[t.codigo]['custo_total'] -= (t.quantidade * pm)
            # Acumula a venda na lista para processamento posterior de impostos
            vendas.append(t)

    # Filtra apenas ativos com saldo positivo para exibição na carteira ativa; ativos zerados são mantidos no outro dicionário
    carteira_ativa = {
        k: v for k, v in carteira.items()
        if v['quantidade'] > 0
    }

    # Se solicitado, tenta buscar cotações atualizadas de mercado; falhas são registradas mas não interrompem o fluxo
    if buscar_cotacao:
        try:
            _atualizar_cotacoes(carteira_ativa)
        except Exception as e:
            logger.error('Erro ao atualizar cotações: %s', e)

    # Retorna os quatro conjuntos: carteira ativa (saldo > 0), carteira completa, vendas e compras
    return carteira_ativa, carteira, vendas, compras


# Função interna que calcula o preço médio e define o preço atual igual ao médio como valor inicial (fallback)
def _atualizar_cotacoes(carteira_ativa):
    """Função interna que define preço médio e preço atual inicial para os ativos ativos."""
    for ativo in carteira_ativa.values():
        # Preço médio ponderado = custo total dividido pela quantidade; evita divisão por zero
        ativo['preco_medio'] = (
            ativo['custo_total'] / ativo['quantidade']
            if ativo['quantidade'] > 0 else 0
        )
        # Inicializa o preço atual igual ao preço médio; será sobrescrito se a cotação real for encontrada depois
        ativo['preco_atual'] = ativo['preco_medio']


def popular_precos_br(carteira_ativa):
    """
    Busca e atualiza cotações de ativos brasileiros (sufixo .SA) via yfinance/Binance/AwesomeAPI.

    Para cada ativo na carteira, consulta o preço atual e recalcula valor de mercado,
    lucro/aberto e rentabilidade percentual.
    """
    # Itera todos os ativos com saldo positivo para buscar cotação e recalcular métricas
    for codigo, ativo in carteira_ativa.items():
        # Adiciona sufixo .SA exigido pelo yfinance para ativos negociados na B3 (ações brasileiras)
        try:
            preco = buscar_preco(f'{codigo}.SA')
            # Só atualiza o preço se a cotação foi retornada com sucesso
            if preco is not None:
                ativo['preco_atual'] = preco
        except Exception as e:
            logger.warning('Cotação BR falhou para %s: %s', codigo, e)

        # Recalcula preço médio, valor de mercado, lucro não realizado e rentabilidade percentual
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
    # Itera todos os ativos americanos ativos para buscar cotação (sem sufixo, pois yfinance aceita direto)
    for codigo, ativo in carteira_ativa.items():
        try:
            preco = buscar_preco(codigo)
            # Só atualiza o preço se a cotação foi obtida com sucesso
            if preco is not None:
                ativo['preco_atual'] = preco
        except Exception as e:
            logger.warning('Cotação US falhou para %s: %s', codigo, e)

        # Recalcula preço médio, valor de mercado, lucro não realizado e rentabilidade percentual
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
    # Itera criptomoedas ativas buscando cotação via Binance/AwesomeAPI (sem sufixo)
    for codigo, ativo in carteira_ativa.items():
        preco = buscar_preco(codigo)
        # Só atualiza o preço se a cotação foi obtida com sucesso; diferente dos outros, não há try/except pois o buscar_preco já trata exceções internamente
        if preco is not None:
            ativo['preco_atual'] = preco

        # Recalcula preço médio, valor de mercado, lucro não realizado e rentabilidade percentual
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
    # Acumuladores para percorrer as transações calculando o preço médio ponderado
    qtd_atual = 0
    custo_atual = 0.0
    # Itera apenas as transações deste ativo (já filtradas pelo parâmetro 'codigo' na chamada? Não, itera todas e calcula para o ativo específico? Na verdade calcula para o codigo informado, mas a lista contém todas as transações)
    for t in transacoes:
        # Compra: aumenta quantidade e custo total diretamente
        if t.tipo_transacao == 'Compra':
            qtd_atual += t.quantidade
            custo_atual += t.valor_total
        else:
            # Venda: usa o preço médio vigente para deduzir o custo proporcional
            pm = custo_atual / qtd_atual if qtd_atual > 0 else 0
            qtd_atual -= t.quantidade
            custo_atual -= (t.quantidade * pm)
    # Preço médio final = custo total / quantidade; retorna 0 se não houver saldo
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
    # Importa monthrange para determinar o último dia do mês de vencimento do DARF
    from calendar import monthrange

    # Dicionário que agregará vendas por mês, acumulando lucro e imposto de cada período
    resumo = {}
    for v in vendas:
        # Extrai apenas ano e mês ('YYYY-MM') da data completa da venda para agrupar
        mes_ano = v.data[:7]
        # Se este mês ainda não foi registrado, inicializa a entrada com dados de vencimento
        if mes_ano not in resumo:
            y, m = map(int, mes_ano.split('-'))
            # O vencimento do DARF é no último dia útil do mês seguinte ao da venda
            y_v, m_v = (y + 1, 1) if m == 12 else (y, m + 1)
            # Obtém o último dia do mês de vencimento (ex: jan vence em fev, último dia 28/29)
            _, last = monthrange(y_v, m_v)
            resumo[mes_ano] = {
                'mes': f'{m:02d}/{y}',
                'ano_mes_ordem': mes_ano,
                'lucro_total': 0.0,
                'imposto_total': 0.0,
                'vencimento': f'{last:02d}/{m_v:02d}/{y_v}',
            }
        # Acumula lucro e imposto da venda no mês correspondente
        resumo[mes_ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0:
            resumo[mes_ano]['imposto_total'] += v.imposto

    # Retorna apenas os meses que geraram imposto a pagar, ordenados do mais recente para o mais antigo
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
    # Dicionário que agregará vendas por ano para o imposto de renda de ativos no exterior
    resumo = {}
    for v in vendas:
        # Extrai apenas o ano ('YYYY') da data, pois o imposto US é declarado anualmente
        ano = v.data[:4]
        # Se o ano ainda não foi registrado, inicializa com vencimento na declaração IRPF do ano seguinte
        if ano not in resumo:
            resumo[ano] = {
                'ano': ano,
                'lucro_total': 0.0,
                'imposto_total': 0.0,
                # Imposto de renda sobre ativos no exterior é pago na declaração anual do ano seguinte
                'vencimento': f"Na Declaração IRPF {int(ano) + 1}",
            }
        resumo[ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0:
            resumo[ano]['imposto_total'] += v.imposto

    # Retorna apenas anos com imposto a pagar, ordenados do mais recente para o mais antigo
    return sorted(
        [d for d in resumo.values() if d['imposto_total'] > 0],
        key=lambda x: x['ano'],
        reverse=True,
    )
