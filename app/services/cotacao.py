import logging
from datetime import datetime, timedelta

import requests
import yfinance as yf


logger = logging.getLogger(__name__)


def status_mercado(pais):
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    if pais == 'CRIPTO':
        return 'ABERTO (24/7)'
    dia_semana = agora_brt.weekday()
    if dia_semana >= 5:
        return 'FECHADO'
    hora_atual = agora_brt.strftime('%H:%M')
    if pais == 'BR':
        if '10:00' <= hora_atual <= '17:00':
            return 'ABERTO'
    elif pais == 'US':
        if '10:30' <= hora_atual <= '17:00':
            return 'ABERTO'
    return 'FECHADO'


def mercado_aberto(pais):
    return status_mercado(pais) == 'ABERTO'


def _awesomeapi_preco(ticker_busca):
    if not ticker_busca.endswith('-BRL'):
        return None
    try:
        r = requests.get(
            f'https://economia.awesomeapi.com.br/last/{ticker_busca}',
            timeout=3,
        )
        if r.status_code == 200:
            data = r.json()
            key = ticker_busca.replace('-', '')
            if key in data:
                return float(data[key]['bid'])
    except Exception as e:
        logger.debug('AwesomeAPI falhou para %s: %s', ticker_busca, e)
    return None


def _binance_preco(ticker_busca):
    try:
        symbol = ticker_busca.replace('-', '')
        if symbol.endswith('USD') and not symbol.endswith('USDT'):
            symbol += 'T'
        r = requests.get(
            f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}',
            timeout=3,
        )
        if r.status_code == 200:
            return float(r.json()['price'])
    except Exception as e:
        logger.debug('Binance falhou para %s: %s', ticker_busca, e)
    return None


def _yfinance_preco(ticker_busca):
    try:
        hist = yf.Ticker(ticker_busca).history(period='1d')
        if not hist.empty:
            preco = float(hist['Close'].iloc[-1])
            if preco > 0:
                return preco
    except Exception as e:
        logger.debug('Yahoo falhou para %s: %s', ticker_busca, e)
    return None


def _fallback_brl(ticker_busca):
    """Fallback matemático: preço em USD * dólar atual para pares -BRL."""
    if not ticker_busca.endswith('-BRL'):
        return None
    try:
        base_coin = ticker_busca.split('-')[0]
        hist_coin = yf.Ticker(f'{base_coin}-USD').history(period='1d')
        if hist_coin.empty:
            return None
        preco_usd = float(hist_coin['Close'].iloc[-1])
        r_usd = requests.get(
            'https://economia.awesomeapi.com.br/last/USD-BRL',
            timeout=3,
        )
        dolar_brl = float(r_usd.json()['USDBRL']['bid'])
        preco_final = preco_usd * dolar_brl
        return preco_final if preco_final > 0 else None
    except Exception as e:
        logger.debug('Fallback BRL falhou para %s: %s', ticker_busca, e)
    return None


def buscar_preco(ticker_busca):
    ticker_busca = ticker_busca.upper().strip()

    preco = _awesomeapi_preco(ticker_busca)
    if preco is not None:
        return preco

    preco = _binance_preco(ticker_busca)
    if preco is not None:
        return preco

    preco = _yfinance_preco(ticker_busca)
    if preco is not None:
        return preco

    preco = _fallback_brl(ticker_busca)
    if preco is not None:
        return preco

    return None


def buscar_historico_br(ticker, periodo):
    ticker_busca = ticker.upper().strip()
    if not ticker_busca.endswith('.SA'):
        ticker_busca += '.SA'

    stock = yf.Ticker(ticker_busca)
    hist = stock.history(period=periodo)

    if hist.empty:
        return None

    return {
        'dates': hist.index.strftime('%d-%m-%Y').tolist(),
        'prices': [round(float(p), 2) for p in hist['Close'].tolist()],
        'highs': [round(float(h), 2) for h in hist['High'].tolist()],
        'lows': [round(float(l), 2) for l in hist['Low'].tolist()],
    }


def buscar_historico_cripto(ticker_busca, periodo):
    ticker_busca = ticker_busca.upper().strip()
    if '-' not in ticker_busca:
        ticker_busca += '-BRL'

    days_map = {'1mo': 30, '2mo': 60, '3mo': 90, '4mo': 120, '5mo': 150, '6mo': 180}
    limit = days_map.get(periodo, 180)

    dates = []
    prices = []
    highs = []
    lows = []

    # Motor 1: AwesomeAPI
    if ticker_busca.endswith('-BRL'):
        try:
            r_aws = requests.get(
                f'https://economia.awesomeapi.com.br/json/daily/{ticker_busca}/{limit}',
                timeout=5,
            )
            if r_aws.status_code == 200:
                data_aws = r_aws.json()
                data_aws.reverse()
                for candle in data_aws:
                    dt = datetime.fromtimestamp(int(candle['timestamp'])).strftime('%d-%m-%Y')
                    dates.append(dt)
                    prices.append(round(float(candle['bid']), 2))
                    highs.append(float(candle['high']))
                    lows.append(float(candle['low']))
        except Exception as e:
            logger.debug('AwesomeAPI hist falhou: %s', e)

    # Motor 2: Binance
    if not dates:
        try:
            symbol = ticker_busca.replace('-', '')
            if symbol.endswith('USD') and not symbol.endswith('USDT'):
                symbol += 'T'
            headers = {'User-Agent': 'Mozilla/5.0'}
            r_bin = requests.get(
                f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}',
                headers=headers, timeout=5,
            )
            if r_bin.status_code == 200:
                data_bin = r_bin.json()
                for candle in data_bin:
                    dt = datetime.fromtimestamp(candle[0] / 1000).strftime('%d-%m-%Y')
                    dates.append(dt)
                    prices.append(round(float(candle[4]), 2))
                    highs.append(float(candle[2]))
                    lows.append(float(candle[1]))
        except Exception as e:
            logger.debug('Binance hist falhou: %s', e)

    if not dates:
        return None

    return {
        'dates': dates,
        'prices': prices,
        'highs': highs,
        'lows': lows,
    }
