"""Fase 1 do rebuild - baseline de seguranca.

Estes testes NAO exercem logica de analise. Eles so garantem que o "snapshot"
sintetico versionado em `tests/fixtures/` esta integro, para que as fases
seguintes do porte possam compara-lo com confianca.

Comando: pytest
"""

from io import StringIO

import pandas as pd

# Colunas OHLCV na ordem que `yfinance.download(..., auto_adjust=False)` produz.
OHLCV_COLUNAS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def test_fixtures_ohlcv_carregam(ohlcv_fixtures):
    """As tres fixtures de cotacao carregam com formato e tamanho esperados."""
    assert set(ohlcv_fixtures) == {"PRIO3", "ASAI3", "LREN3"}
    for ticker, df in ohlcv_fixtures.items():
        assert list(df.columns) == OHLCV_COLUNAS, ticker
        assert len(df) == 260, ticker
        assert isinstance(df.index, pd.DatetimeIndex), ticker


def test_ohlcv_respeita_relacao_de_candle(ohlcv_fixtures):
    """Em todo pregao: High >= max(Open, Close) e Low <= min(Open, Close)."""
    for ticker, df in ohlcv_fixtures.items():
        assert (df["High"] >= df[["Open", "Close"]].max(axis=1)).all(), ticker
        assert (df["Low"] <= df[["Open", "Close"]].min(axis=1)).all(), ticker


def test_fundamentus_fixture_e_parseavel(fundamentus_html):
    """A pagina Fundamentus sintetica e lida por pandas.read_html como o
    site real: varias tabelas, colunas inteiras (sem cabecalho)."""
    tabelas = pd.read_html(StringIO(fundamentus_html))
    assert len(tabelas) >= 2
    # A primeira celula da primeira tabela e o rotulo "Papel".
    assert tabelas[0].iloc[0, 0] == "Papel"
