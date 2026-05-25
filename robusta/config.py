"""Configuracao central do ROBUSTA: versao, janelas e caminhos.

Tudo que e parametro de metodologia (janelas de media movel, janela de
volatilidade) vive aqui como constante e **nao deve ser alterado** sem pedido
explicito - ver a secao "Fronteira bug vs metodologia" em `planning/PLAN.md`.
"""

from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay, MonthBegin

# --- Versao -----------------------------------------------------------------
# Fonte unica da versao (o `main.py` legado divergia entre "12.3.1" e "13").
VERSION = "13"

# --- Parametros de analise (metodologia - nao alterar) ----------------------
# Janelas das medias moveis aritmeticas, em dias.
MMA_WINDOWS = (9, 10, 26, 50, 150, 200)
# Janela da volatilidade anualizada, em dias.
VOL_WINDOW = 30
# Anos de historico de cotacoes baixados da Yahoo Finance.
HISTORICO_ANOS = 5

# --- Caminhos ---------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
# Entradas Excel mantidas nesta fase do rebuild.
CAMINHO_LISTA_TICKERS = RAIZ / "lista_tickers_liquidos.xlsx"
CAMINHO_FUNDAMENTOS_CACHE = RAIZ / "all_ticker_financial_indicators.xlsx"
# Pasta onde a persistencia JSON gravara as execucoes (Fase 6).
PASTA_RUNS = RAIZ / "runs"

# URL base do Fundamentus; concatena-se o ticker base (ex: "PRIO3").
FUNDAMENTUS_URL_BASE = "https://www.fundamentus.com.br/detalhes.php?papel="


def data_inicio_download(referencia=None):
    """Devolve a data de inicio do download de cotacoes: `referencia` menos
    `HISTORICO_ANOS` anos. Sem argumento, usa o instante atual."""
    referencia = pd.Timestamp(referencia) if referencia is not None else pd.Timestamp.now()
    return referencia - pd.DateOffset(years=HISTORICO_ANOS)


def eh_primeiro_dia_util_do_mes(data):
    """True se `data` for o primeiro dia util do seu mes.

    Replica a intencao do `first_day_alert` legado (que usa `BDay`, ou seja,
    considera apenas sabado/domingo, sem feriados). Corrige o bug do legado de
    comparar um timestamp com hora contra uma data: aqui a hora e descartada.
    """
    data = pd.Timestamp(data).normalize()
    primeiro_do_mes = MonthBegin().rollback(data)
    primeiro_dia_util = primeiro_do_mes + BDay(0)
    return bool(data == primeiro_dia_util)
