"""
Serviço de consulta de cotações e histórico de preços.

Oferece funções para:
- Verificar se o mercado está aberto (BR, US, Cripto).
- Buscar preço atual de ativos através de múltiplas fontes (AwesomeAPI, Binance, yfinance).
- Buscar histórico de preços para ativos brasileiros (.SA) e criptomoedas.
"""

import logging
import threading
from datetime import datetime, timedelta

import requests
import yfinance as yf


logger = logging.getLogger(__name__)

# Cache de cotações em memória com TTL de 60 segundos
_cache = {}
_cache_lock = threading.Lock()
_cache_ttl = 60


def _get_cache(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (datetime.now().timestamp() - entry['time']) < _cache_ttl:
            return entry['value']
        return None


def _set_cache(key, value):
    with _cache_lock:
        _cache[key] = {'value': value, 'time': datetime.now().timestamp()}


def _limpar_cache():
    with _cache_lock:
        _cache.clear()


def status_mercado(pais):
    """
    Retorna o status atual do mercado ('ABERTO' ou 'FECHADO') para o país informado.

    Para CRIPTO, retorna 'ABERTO (24/7)' independente do horário.
    Para BR e US, considera horário comercial em dias úteis no fuso BRT (UTC-3):
      - BR: 10:00 às 17:00
      - US: 10:30 às 17:00
    Finais de semana (dia_semana >= 5) são considerados fechados.

    Args:
        pais: String indicando 'BR', 'US' ou 'CRIPTO'.

    Returns:
        String com o status do mercado.
    """
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
    """Retorna True se o mercado do país informado estiver aberto no momento."""
    return status_mercado(pais) == 'ABERTO'


def _awesomeapi_preco(ticker_busca):
    """
    Tenta obter o preço de um ativo via AwesomeAPI (API gratuita de câmbio e cripto).

    Suporta apenas tickers com sufixo -BRL (ex: BTC-BRL, USD-BRL).
    A resposta da API contém uma chave com o ticker sem o hífen.

    Args:
        ticker_busca: String do ticker a consultar (ex: 'BTC-BRL').

    Returns:
        Float com o preço ou None se falhar.
    """
    # AwesomeAPI só funciona para pares em Real
    if not ticker_busca.endswith('-BRL'):
        return None
    try:
        r = requests.get(
            f'https://economia.awesomeapi.com.br/last/{ticker_busca}',
            timeout=3,
        )
        if r.status_code == 200:
            data = r.json()
            key = ticker_busca.replace('-', '')  # Ex: 'BTC-BRL' vira 'BTCBRL'
            if key in data:
                return float(data[key]['bid'])
    except Exception as e:
        logger.debug('AwesomeAPI falhou para %s: %s', ticker_busca, e)
    return None


def _binance_preco(ticker_busca):
    """
    Tenta obter o preço de um ativo via API pública da Binance.

    Converte o ticker para o formato de símbolo da Binance (remove hífens).
    Se o ticker termina com 'USD' mas não 'USDT', adiciona 'T' automaticamente.

    Args:
        ticker_busca: String do ticker a consultar (ex: 'BTCUSDT' ou 'ETH-BRL').

    Returns:
        Float com o preço ou None se falhar.
    """
    try:
        symbol = ticker_busca.replace('-', '')
        # Binance usa USDT como stablecoin padrão; converte USD -> USDT
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
    """
    Tenta obter o preço de um ativo via Yahoo Finance (yfinance).

    Busca o candle diário mais recente e retorna o preço de fechamento.
    Útil para ações, ETFs e moedas que não estão disponíveis nas outras APIs.

    Args:
        ticker_busca: String do ticker no formato yfinance (ex: 'AAPL', 'PETR4.SA').

    Returns:
        Float com o preço de fechamento ou None se falhar.
    """
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
    """
    Fallback matemático para obter preço em Reais (BRL) quando outras APIs falham.

    Estratégia: obtém o preço do ativo em dólar (via yfinance) e multiplica
    pela cotação atual do dólar (USD-BRL via AwesomeAPI).

    Args:
        ticker_busca: Ticker com sufixo -BRL (ex: 'ETH-BRL').

    Returns:
        Float com o preço estimado em BRL ou None se falhar.
    """
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
    """
    Função principal de busca de preço, com fallback entre múltiplas fontes
    e cache em memória (TTL = 60s).

    A ordem de consulta é:
      1. Cache em memória
      2. AwesomeAPI (pares -BRL)
      3. Binance (cripto e pares)
      4. Yahoo Finance (ações, ETFs, moedas)
      5. Fallback BRL (cálculo USD * cotação dólar)

    Retorna o primeiro resultado não-nulo encontrado.

    Args:
        ticker_busca: String do ticker a consultar (ex: 'BTC-BRL', 'AAPL', 'PETR4.SA').

    Returns:
        Float com o preço encontrado ou None se todas as fontes falharem.
    """
    ticker_busca = ticker_busca.upper().strip()

    # 0: Verifica cache em memória
    cache_key = f'preco:{ticker_busca}'
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    # 1ª tentativa: AwesomeAPI (ideal para pares BRL)
    preco = _awesomeapi_preco(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # 2ª tentativa: Binance (ideal para criptomoedas)
    preco = _binance_preco(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # 3ª tentativa: Yahoo Finance (ações e ETFs)
    preco = _yfinance_preco(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # 4ª tentativa: Fallback matemático BRL
    preco = _fallback_brl(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # Nenhuma fonte retornou preço válido
    return None


def buscar_historico_br(ticker, periodo):
    """
    Busca o histórico de preços de um ativo brasileiro (.SA) via Yahoo Finance.

    Retorna listas de datas, preços de fechamento, máximas e mínimas.

    Args:
        ticker: Código do ativo (ex: 'PETR4'). O sufixo .SA é adicionado automaticamente.
        periodo: Período no formato yfinance (ex: '1mo', '3mo', '6mo', '1y', 'max').

    Returns:
        Dicionário com chaves 'dates', 'prices', 'highs', 'lows' ou None se vazio.
    """
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
    """
    Busca o histórico de preços de uma criptomoeda usando AwesomeAPI e Binance.

    Estratégia de fallback:
      1. AwesomeAPI (apenas pares -BRL): retorna dados diários completos.
      2. Binance: busca candles diários (klines) para qualquer par.

    Args:
        ticker_busca: Código da criptomoeda (ex: 'BTC', 'ETH-BRL').
        periodo: Período abreviado ('1mo', '2mo', ..., '6mo').

    Returns:
        Dicionário com chaves 'dates', 'prices', 'highs', 'lows' ou None se vazio.
    """
    ticker_busca = ticker_busca.upper().strip()
    if '-' not in ticker_busca:
        ticker_busca += '-BRL'  # Assume par em Real se não especificado

    # Mapeia período abreviado para número de dias / candles
    days_map = {'1mo': 30, '2mo': 60, '3mo': 90, '4mo': 120, '5mo': 150, '6mo': 180}
    limit = days_map.get(periodo, 180)

    dates = []
    prices = []
    highs = []
    lows = []

    # Motor 1: AwesomeAPI (apenas para pares -BRL)
    if ticker_busca.endswith('-BRL'):
        try:
            r_aws = requests.get(
                f'https://economia.awesomeapi.com.br/json/daily/{ticker_busca}/{limit}',
                timeout=5,
            )
            if r_aws.status_code == 200:
                data_aws = r_aws.json()
                data_aws.reverse()  # API retorna do mais recente ao mais antigo
                for candle in data_aws:
                    dt = datetime.fromtimestamp(int(candle['timestamp'])).strftime('%d-%m-%Y')
                    dates.append(dt)
                    prices.append(round(float(candle['bid']), 2))
                    highs.append(float(candle['high']))
                    lows.append(float(candle['low']))
        except Exception as e:
            logger.debug('AwesomeAPI hist falhou: %s', e)

    # Motor 2: Binance (fallback caso AwesomeAPI não tenha retornado dados)
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
                    # candle[0]: timestamp, [4]: close, [2]: high, [1]: low
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
