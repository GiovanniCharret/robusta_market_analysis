"""Camada de IO do ROBUSTA: leitura dos Excel e chamadas de rede.

Concentra todo acesso externo (disco e internet) num so lugar. As fases de
analise (tecnica e fundamentalista) recebem dados ja carregados e nao falam
diretamente com a Yahoo Finance, com o Fundamentus ou com arquivos Excel.
"""

import logging
import time

import pandas as pd
import requests
import yfinance
from yfinance.exceptions import YFRateLimitError

from robusta import config

logger = logging.getLogger(__name__)

# Header de navegador; o Fundamentus recusa requisicoes sem User-Agent.
_HEADERS_FUNDAMENTUS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    )
}


def ler_lista_tickers(caminho=None):
    """Le o Excel da lista de tickers liquidos e devolve a lista de tickers
    base (sem sufixo `.SA`), ex: `["ABEV3", "ALOS3", ...]`.

    Esta e a unica fonte do universo analisado - nao ha override embutido."""
    caminho = caminho or config.CAMINHO_LISTA_TICKERS
    df = pd.read_excel(caminho, usecols=["ticker"])
    tickers = df["ticker"].dropna().astype(str).tolist()
    _valida_lista_tickers_sem_duplicatas(tickers)
    return tickers


def _valida_lista_tickers_sem_duplicatas(tickers):
    """Falha se a lista de tickers contem valores repetidos.

    Tickers duplicados na entrada propagam para baixo (raspagem dupla do
    Fundamentus, linhas duplicadas no merge) e silenciosamente distorcem
    rankings. Esta validacao para a execucao na fonte.
    """
    serie = pd.Series(tickers)
    repetidos = serie[serie.duplicated(keep=False)].unique().tolist()
    if repetidos:
        raise ValueError(
            "lista_tickers_liquidos.xlsx tem valores repetidos. Corrija. "
            f"Tickers duplicados: {repetidos}"
        )


def ler_fundamentos_cache(caminho=None):
    """Le o Excel de fundamentos cacheados e devolve o DataFrame."""
    caminho = caminho or config.CAMINHO_FUNDAMENTOS_CACHE
    return pd.read_excel(caminho)


def baixa_cotacoes_yahoo(ticker_yf, data_inicio=None, tentativas=5):
    """Baixa o OHLCV diario de um ticker na Yahoo Finance.

    `ticker_yf` ja deve vir no formato Yahoo (ex: `"PRIO3.SA"`).
    Em caso de rate-limit, tenta de novo com espera exponencial (2^n s).
    Devolve o DataFrame baixado; se esgotar as tentativas, devolve vazio.
    """
    if data_inicio is None:
        data_inicio = config.data_inicio_download()

    for tentativa in range(tentativas):
        try:
            return yfinance.download(
                ticker_yf,
                progress=False,
                start=data_inicio,
                auto_adjust=False,
                multi_level_index=False,
            )
        except YFRateLimitError:
            if tentativa == tentativas - 1:
                break  # ultima tentativa: nao adianta esperar de novo
            espera = 2 ** tentativa
            logger.warning("Rate limit da Yahoo em %s; aguardando %ss",
                           ticker_yf, espera)
            time.sleep(espera)

    logger.error("Tentativas esgotadas ao baixar %s", ticker_yf)
    return pd.DataFrame()


def baixa_html_fundamentus(url):
    """Baixa o HTML cru de uma pagina de detalhes do Fundamentus."""
    resposta = requests.get(url, headers=_HEADERS_FUNDAMENTUS, timeout=20)
    resposta.raise_for_status()
    return resposta.text


def carrega_fundamentos(data_execucao, raspar_fn, caminho_cache=None,
                        forcar_raspagem=False):
    """Decide entre raspar o Fundamentus ou ler o cache em disco.

    Raspa (chamando `raspar_fn()` e salvando o resultado no Excel de cache)
    quando qualquer das condicoes for verdadeira:
      - `forcar_raspagem=True` (flag de CLI `--refresh-fundamentos`), para
        atualizacoes pontuais (mudanca de ticker, resultados no meio do mes).
      - `data_execucao` for o 1o dia util do mes (rotina mensal do legado).
      - O cache nao existir ou estiver vazio (fallback de auto-recuperacao):
        evita travar o pipeline quando o cache foi sobrescrito por engano.

    Nos demais dias, le e devolve o cache do Excel.

    `raspar_fn` e injetado de proposito: assim esta funcao nao depende do
    scraper (Fase F10) e pode ser testada isoladamente.
    """
    caminho_cache = caminho_cache or config.CAMINHO_FUNDAMENTOS_CACHE

    cache_invalido = (not caminho_cache.exists()) or _cache_vazio(caminho_cache)
    primeiro_dia_util = config.eh_primeiro_dia_util_do_mes(data_execucao)

    if forcar_raspagem or primeiro_dia_util or cache_invalido:
        motivo = (
            "forcado via flag" if forcar_raspagem
            else "1o dia util do mes" if primeiro_dia_util
            else "cache ausente ou vazio"
        )
        logger.info("Raspando fundamentos e atualizando cache (%s)", motivo)
        df = raspar_fn()
        df.to_excel(caminho_cache, index=False)
        return df

    logger.info("Carregando fundamentos do cache: %s", caminho_cache)
    return ler_fundamentos_cache(caminho_cache)


def _cache_vazio(caminho_cache):
    """True se o Excel de cache existir mas estiver sem dados (shape (0, 0))."""
    try:
        return pd.read_excel(caminho_cache).empty
    except Exception:
        return True
