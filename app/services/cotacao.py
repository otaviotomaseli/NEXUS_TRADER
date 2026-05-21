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

# Cache de cotações em memória com TTL de 60 segundos para evitar chamadas repetidas às APIs externas
_cache = {}
# Lock de thread para garantir acesso seguro ao cache em ambiente concorrente (ex: múltiplas requisições simultâneas)
_cache_lock = threading.Lock()
# Tempo de vida do cache em segundos: 60s equilibra atualização versus performance
_cache_ttl = 60


# Recupera valor do cache se ainda estiver dentro do TTL; retorna None se expirado ou ausente
def _get_cache(key):
    # Usa lock para evitar leitura concorrente durante escrita
    with _cache_lock:
        entry = _cache.get(key)
        # Verifica se a entrada existe e não expirou comparando o timestamp atual com o armazenado
        if entry and (datetime.now().timestamp() - entry['time']) < _cache_ttl:
            return entry['value']
        return None


# Armazena valor no cache com timestamp atual para controle de expiração
def _set_cache(key, value):
    with _cache_lock:
        _cache[key] = {'value': value, 'time': datetime.now().timestamp()}


# Limpa todo o cache; útil para forçar atualização ou em testes
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
    # Obtém o horário atual no fuso BRT (UTC-3) subtraindo 3 horas do UTC
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    # Criptomoedas negociam 24 horas por dia, 7 dias por semana; retorna imediatamente
    if pais == 'CRIPTO':
        return 'ABERTO (24/7)'

    # Verifica se é final de semana (5=sexta, 6=sábado); mercados BR e US fecham em dias úteis
    dia_semana = agora_brt.weekday()
    if dia_semana >= 5:
        return 'FECHADO'

    # Comparação string de horário para determinar se está dentro do pregão
    hora_atual = agora_brt.strftime('%H:%M')
    if pais == 'BR':
        # B3: horário de negociação das 10:00 às 17:00 (BRT)
        if '10:00' <= hora_atual <= '17:00':
            return 'ABERTO'
    elif pais == 'US':
        # NYSE/NASDAQ: abre 10:30 BRT (09:30 ET) e fecha às 17:00 BRT (16:00 ET)
        if '10:30' <= hora_atual <= '17:00':
            return 'ABERTO'
    # Fora do horário comercial ou país não reconhecido: mercado fechado
    return 'FECHADO'


# Função de conveniência: retorna booleano indicando se o mercado está em horário de negociação
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
    # AwesomeAPI é uma API gratuita brasileira que só oferece pares com Real (BRL)
    if not ticker_busca.endswith('-BRL'):
        return None
    try:
        # Faz requisição GET para o endpoint de cotação da AwesomeAPI com timeout curto de 3s
        r = requests.get(
            f'https://economia.awesomeapi.com.br/last/{ticker_busca}',
            timeout=3,
        )
        if r.status_code == 200:
            data = r.json()
            # A chave no JSON não contém hífen; ex: 'BTC-BRL' vira 'BTCBRL' no response
            key = ticker_busca.replace('-', '')
            if key in data:
                # 'bid' é o preço de compra (cotação atual) retornado pela API
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
        # Remove hífens do ticker pois a Binance usa símbolos sem separador (ex: BTCBRL, ETHUSDT)
        symbol = ticker_busca.replace('-', '')
        # A Binance usa USDT como stablecoin padrão; converte sufixo USD para USDT automaticamente
        if symbol.endswith('USD') and not symbol.endswith('USDT'):
            symbol += 'T'
        # Endpoint público que retorna o preço atual de qualquer par negociado na Binance
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
        # Cria objeto Ticker do yfinance e baixa o histórico diário mais recente (último pregão)
        hist = yf.Ticker(ticker_busca).history(period='1d')
        # Verifica se o DataFrame não está vazio antes de extrair o preço de fechamento
        if not hist.empty:
            preco = float(hist['Close'].iloc[-1])
            # Ignora preços zerados (podem indicar ativo sem negociação no período)
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
    # Fallback só se aplica a pares BRL (ex: ETH-BRL) onde precisamos calcular o preço manualmente
    if not ticker_busca.endswith('-BRL'):
        return None
    try:
        # Extrai o ativo base (ex: 'ETH' de 'ETH-BRL')
        base_coin = ticker_busca.split('-')[0]
        # Busca o preço do ativo em dólar via Yahoo Finance
        hist_coin = yf.Ticker(f'{base_coin}-USD').history(period='1d')
        if hist_coin.empty:
            return None
        preco_usd = float(hist_coin['Close'].iloc[-1])
        # Busca a cotação atual do dólar (USD-BRL) via AwesomeAPI
        r_usd = requests.get(
            'https://economia.awesomeapi.com.br/last/USD-BRL',
            timeout=3,
        )
        dolar_brl = float(r_usd.json()['USDBRL']['bid'])
        # Calcula o preço em Reais multiplicando o preço em dólar pela cotação do dólar
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
    # Normaliza o ticker: maiúsculas e sem espaços nas bordas para consistência no cache e nas consultas
    ticker_busca = ticker_busca.upper().strip()

    # Etapa 0: verifica cache em memória para evitar chamadas desnecessárias às APIs
    cache_key = f'preco:{ticker_busca}'
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    # Etapa 1: tenta AwesomeAPI (API brasileira gratuita, ideal para pares BRL como BTC-BRL)
    preco = _awesomeapi_preco(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # Etapa 2: tenta Binance (API pública de criptomoedas, cobre a maioria dos pares digitais)
    preco = _binance_preco(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # Etapa 3: tenta Yahoo Finance via yfinance (cobre ações, ETFs, moedas fiduciárias)
    preco = _yfinance_preco(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # Etapa 4: fallback matemático para pares BRL - calcula preço em dólar * cotação do dólar
    preco = _fallback_brl(ticker_busca)
    if preco is not None:
        _set_cache(cache_key, preco)
        return preco

    # Nenhuma das fontes retornou preço válido para este ticker
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
    # Normaliza o ticker e garante o sufixo .SA exigido pelo Yahoo Finance para ativos brasileiros
    ticker_busca = ticker.upper().strip()
    if not ticker_busca.endswith('.SA'):
        ticker_busca += '.SA'

    # Cria objeto Ticker e baixa o histórico no período solicitado
    stock = yf.Ticker(ticker_busca)
    hist = stock.history(period=periodo)

    # Se o DataFrame estiver vazio (ativo sem dados ou ticker inválido), retorna None
    if hist.empty:
        return None

    # Retorna dicionário com listas de datas formatadas (DD-MM-YYYY), fechamentos, máximas e mínimas
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
    # Normaliza o ticker e assume par em Real se o usuário não especificou (ex: 'BTC' vira 'BTC-BRL')
    ticker_busca = ticker_busca.upper().strip()
    if '-' not in ticker_busca:
        ticker_busca += '-BRL'

    # Converte períodos abreviados ('1mo', '3mo') para número de candles diários; padrão 180 dias (~6 meses)
    days_map = {'1mo': 30, '2mo': 60, '3mo': 90, '4mo': 120, '5mo': 150, '6mo': 180}
    limit = days_map.get(periodo, 180)

    # Listas que acumularão os dados históricos processados
    dates = []
    prices = []
    highs = []
    lows = []

    # Motor 1: tenta AwesomeAPI primeiro (funciona apenas para pares com sufixo -BRL)
    if ticker_busca.endswith('-BRL'):
        try:
            # Endpoint de daily da AwesomeAPI retorna candles diários completos
            r_aws = requests.get(
                f'https://economia.awesomeapi.com.br/json/daily/{ticker_busca}/{limit}',
                timeout=5,
            )
            if r_aws.status_code == 200:
                data_aws = r_aws.json()
                # A API retorna ordenada do mais recente para o mais antigo; invertemos para ordem cronológica
                data_aws.reverse()
                for candle in data_aws:
                    # Converte timestamp Unix para data formatada DD-MM-YYYY
                    dt = datetime.fromtimestamp(int(candle['timestamp'])).strftime('%d-%m-%Y')
                    dates.append(dt)
                    # 'bid' é o preço de fechamento/compra no período; high e low são máximas e mínimas
                    prices.append(round(float(candle['bid']), 2))
                    highs.append(float(candle['high']))
                    lows.append(float(candle['low']))
        except Exception as e:
            logger.debug('AwesomeAPI hist falhou: %s', e)

    # Motor 2: se AwesomeAPI não retornou dados, tenta Binance como fallback (suporta qualquer par)
    if not dates:
        try:
            # Remove hífen e converte USD para USDT se necessário (padrão Binance)
            symbol = ticker_busca.replace('-', '')
            if symbol.endswith('USD') and not symbol.endswith('USDT'):
                symbol += 'T'
            # User-Agent é necessário pois a API da Binance pode rejeitar requisições sem cabeçalho
            headers = {'User-Agent': 'Mozilla/5.0'}
            # Endpoint klines retorna candles diários no formato: [timestamp, open, high, low, close, volume, ...]
            r_bin = requests.get(
                f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}',
                headers=headers, timeout=5,
            )
            if r_bin.status_code == 200:
                data_bin = r_bin.json()
                for candle in data_bin:
                    # candle[0]: timestamp em ms, [4]: close, [2]: high, [1]: low
                    dt = datetime.fromtimestamp(candle[0] / 1000).strftime('%d-%m-%Y')
                    dates.append(dt)
                    prices.append(round(float(candle[4]), 2))
                    highs.append(float(candle[2]))
                    lows.append(float(candle[1]))
        except Exception as e:
            logger.debug('Binance hist falhou: %s', e)

    # Se nenhuma fonte retornou dados, retorna None para indicar falha
    if not dates:
        return None

    # Retorna dicionário com as listas de datas, preços, máximas e mínimas históricas
    return {
        'dates': dates,
        'prices': prices,
        'highs': highs,
        'lows': lows,
    }
