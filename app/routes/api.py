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

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


@api_bp.route('/api/cotacao/<ticker>')
@login_required
def api_cotacao(ticker):
    preco = buscar_preco(ticker)
    if preco is not None:
        return jsonify({'preco': preco})
    return jsonify({'preco': 0.0, 'error': 'Ativo não encontrado'})


@api_bp.route('/api/analise/<pais>/<ticker>/<periodo>')
@login_required
def api_analise(pais, ticker, periodo):
    ticker_busca = ticker.upper().strip()
    ticker_db = ticker_busca

    try:
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

        resistance = round(max(highs), 2)
        support = round(min(lows), 2)

        # Cálculo de médias móveis e sinais
        df = pd.DataFrame({'Close': prices})
        sma9 = df['Close'].rolling(window=9).mean()
        sma21 = df['Close'].rolling(window=21).mean()

        buy_signals = []
        sell_signals = []

        if len(prices) > 21:
            for i in range(21, len(prices)):
                if sma9.iloc[i] > sma21.iloc[i] and sma9.iloc[i - 1] <= sma21.iloc[i - 1]:
                    buy_signals.append({'x': dates[i], 'y': prices[i]})
                elif sma9.iloc[i] < sma21.iloc[i] and sma9.iloc[i - 1] >= sma21.iloc[i - 1]:
                    sell_signals.append({'x': dates[i], 'y': prices[i]})

        # Compras do usuário no período
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
