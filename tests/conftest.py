"""Configuracao e fixtures compartilhadas dos testes do rebuild ROBUSTA.

O pytest carrega este arquivo automaticamente. Ele faz duas coisas:
  1. Poe a raiz do repositorio no sys.path, para que as fases seguintes
     consigam fazer `import robusta...` ao rodar `pytest` da raiz.
  2. Expoe fixtures que carregam os dados sinteticos de `tests/fixtures/`.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Garante que `import robusta` funcione independente de onde o pytest roda.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Tickers cobertos pelas fixtures sinteticas de OHLCV.
TICKERS_FIXTURE = ("PRIO3", "ASAI3", "LREN3")


def _carrega_ohlcv(ticker):
    """Le um CSV de fixture e devolve um DataFrame OHLCV indexado por Date,
    no mesmo formato que `yfinance.download(..., auto_adjust=False)` produz."""
    caminho = FIXTURES_DIR / f"ohlcv_{ticker}.csv"
    return pd.read_csv(caminho, parse_dates=["Date"], index_col="Date")


@pytest.fixture
def ohlcv_fixtures():
    """Dict {ticker: DataFrame OHLCV} para os tres tickers sinteticos."""
    return {ticker: _carrega_ohlcv(ticker) for ticker in TICKERS_FIXTURE}


@pytest.fixture
def fundamentus_html():
    """HTML de uma pagina Fundamentus sintetica (ticker PRIO3)."""
    return (FIXTURES_DIR / "fundamentus_PRIO3.html").read_text(encoding="utf-8")
