"""
Rotas da API de dados financeiros.

Fornece endpoints para cotação em tempo real, análise técnica
com indicadores (suporte, resistência, médias móveis) e
histórico de compras do usuário sobreposto ao gráfico.
"""

import logging
from datetime import datetime

import pandas as pd
import yfinance as yf
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from requests import get

from app.models import Transacao, TransacaoExterior, TransacaoCripto
from app.services.cotacao import (
    buscar_preco, buscar_historico_br, buscar_historico_cripto,
)
from app.services.carteira import (
    processar_carteira, popular_precos_br, popular_precos_us,
    popular_precos_cripto, gerar_resumo_darfs,
)

logger = logging.getLogger(__name__)

# Blueprint com prefixo /api (algumas rotas usam prefixo próprio)
api_bp = Blueprint('api', __name__)


@api_bp.route('/api/cotacao/<ticker>')
@login_required
def api_cotacao(ticker):
    """Retorna a cotação atual de um ativo em formato JSON."""
    preco = buscar_preco(ticker)
    if preco is not None:
        return jsonify({'preco': preco})
    return jsonify({'preco': 0.0, 'error': 'Ativo não encontrado'})


@api_bp.route('/api/analise/<pais>/<ticker>/<periodo>')
@login_required
def api_analise(pais, ticker, periodo):
    """
    Retorna dados de análise técnica de um ativo.

    Inclui preços históricos, suporte, resistência, cruzamento
    de médias móveis (SMA9/SMA21) e compras do usuário no período.
    """
    ticker_busca = ticker.upper().strip()
    ticker_db = ticker_busca

    try:
        # Obtém histórico conforme o mercado (Brasil, EUA ou Cripto)
        if pais == 'CRIPTO':
            resultado = buscar_historico_cripto(ticker_busca, periodo)
            if resultado is None:
                return jsonify({'error': 'A corretora global bloqueou o acesso ou o ativo não existe.'})
        else:
            resultado = buscar_historico_br(ticker_busca, periodo)
            if resultado is None:
                return jsonify({'error': 'Ativo não encontrado na base de dados global.'})

        dates = resultado['dates']
        prices = resultado['prices']
        highs = resultado.get('highs', prices)
        lows = resultado.get('lows', prices)

        # Calcula suporte (mínimo) e resistência (máximo) do período
        resistance = round(max(highs), 2)
        support = round(min(lows), 2)

        # Cálculo de médias móveis e sinais
        df = pd.DataFrame({'Close': prices})
        sma9 = df['Close'].rolling(window=9).mean()
        sma21 = df['Close'].rolling(window=21).mean()

        buy_signals = []
        sell_signals = []

        # Gera sinais de compra/venda no cruzamento das médias SMA9 e SMA21
        if len(prices) > 21:
            for i in range(21, len(prices)):
                if sma9.iloc[i] > sma21.iloc[i] and sma9.iloc[i - 1] <= sma21.iloc[i - 1]:
                    buy_signals.append({'x': dates[i], 'y': prices[i]})
                elif sma9.iloc[i] < sma21.iloc[i] and sma9.iloc[i - 1] >= sma21.iloc[i - 1]:
                    sell_signals.append({'x': dates[i], 'y': prices[i]})

        # Compras do usuário no período — consulta modelo adequado por país
        user_purchases = []
        if pais == 'BR':
            compras_bd = Transacao.query.filter_by(
                user_id=current_user.id, codigo=ticker_db, tipo_transacao='Compra',
            ).all()
        elif pais == 'US':
            compras_bd = TransacaoExterior.query.filter_by(
                user_id=current_user.id, codigo=ticker_db, tipo_transacao='Compra',
            ).all()
        elif pais == 'CRIPTO':
            compras_bd = TransacaoCripto.query.filter_by(
                user_id=current_user.id, codigo=ticker_db, tipo_transacao='Compra',
            ).all()
        else:
            compras_bd = []

        # Converte datas e preços das compras para o formato do gráfico
        for c in compras_bd:
            y, m, d = c.data.split('-')
            data_formatada = f'{d}-{m}-{y}'
            preco_pago = round(c.valor_total / c.quantidade, 2) if c.quantidade > 0 else 0
            if data_formatada in dates:
                user_purchases.append({'x': data_formatada, 'y': preco_pago})

        return jsonify({
            'dates': dates,
            'prices': prices,
            'support': support,
            'resistance': resistance,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'user_purchases': user_purchases,
            'ticker': ticker_db,
        })

    except Exception as e:
        logger.exception('Erro na análise técnica para %s/%s', pais, ticker)
        return jsonify({'error': 'Erro interno do servidor. Tente novamente mais tarde.'})


@api_bp.route('/api/rentabilidade')
@login_required
def api_rentabilidade():
    """
    Retorna dados de rentabilidade acumulada ao longo do tempo.

    Consolida todas as transações (BR, US, Cripto) do usuário,
    calcula o valor acumulado investido e o resultado (investido + lucro)
    em cada mês, além do valor de mercado atual da carteira.
    """
    uid = current_user.id

    transacoes_br = Transacao.query.filter_by(user_id=uid).order_by(Transacao.data, Transacao.id).all()
    transacoes_us = TransacaoExterior.query.filter_by(user_id=uid).order_by(TransacaoExterior.data, TransacaoExterior.id).all()
    transacoes_c = TransacaoCripto.query.filter_by(user_id=uid).order_by(TransacaoCripto.data, TransacaoCripto.id).all()

    todas = []
    for t in transacoes_br:
        todas.append({'data': t.data, 'tipo': t.tipo_transacao, 'valor': t.valor_total, 'lucro': t.lucro_perda or 0})
    for t in transacoes_us:
        todas.append({'data': t.data, 'tipo': t.tipo_transacao, 'valor': t.valor_total, 'lucro': t.lucro_perda or 0})
    for t in transacoes_c:
        todas.append({'data': t.data, 'tipo': t.tipo_transacao, 'valor': t.valor_total, 'lucro': t.lucro_perda or 0})
    todas.sort(key=lambda x: x['data'])

    mensal = {}
    for t in todas:
        mes = t['data'][:7]
        if mes not in mensal:
            mensal[mes] = {'investido': 0.0, 'resultado': 0.0}
        if t['tipo'] == 'Compra':
            mensal[mes]['investido'] += t['valor']
        else:
            mensal[mes]['investido'] -= t['valor']
            mensal[mes]['resultado'] += t['lucro']

    meses = sorted(mensal.keys())
    cum_investido = 0.0
    cum_resultado = 0.0
    labels = []
    investido_data = []
    resultado_data = []
    total_data = []

    for m in meses:
        cum_investido += mensal[m]['investido']
        cum_resultado += mensal[m]['resultado']
        labels.append(m)
        investido_data.append(round(cum_investido, 2))
        resultado_data.append(round(cum_resultado, 2))
        total_data.append(round(cum_investido + cum_resultado, 2))

    # Valor de mercado atual da carteira
    def _valor_carteira(modelo, popular_fn):
        qs = modelo.query.filter_by(user_id=uid).order_by(modelo.id).all()
        c, _, _, _ = processar_carteira(qs, buscar_cotacao=False)
        popular_fn(c)
        return sum(v['valor_atual'] for v in c.values())

    try:
        valor_br = _valor_carteira(Transacao, popular_precos_br)
        valor_us = _valor_carteira(TransacaoExterior, popular_precos_us)
        valor_c = _valor_carteira(TransacaoCripto, popular_precos_cripto)
    except Exception:
        valor_br = valor_us = valor_c = 0

    return jsonify({
        'labels': labels,
        'investido': investido_data,
        'resultado': resultado_data,
        'total': total_data,
        'valor_portfolio_atual': round(valor_br + valor_us + valor_c, 2),
    })
