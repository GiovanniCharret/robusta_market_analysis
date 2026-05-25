"""Testes da Fase 2 - configuracao e IO (`robusta.config`, `robusta.data`).

Comando: pytest
"""

import pandas as pd
import yfinance
from yfinance.exceptions import YFRateLimitError

from robusta import config, data


def test_eh_primeiro_dia_util_do_mes():
    # 2026-05-01 e sexta-feira -> e o primeiro dia util de maio.
    assert config.eh_primeiro_dia_util_do_mes("2026-05-01") is True
    assert config.eh_primeiro_dia_util_do_mes("2026-05-15") is False
    # 2026-02-01 cai num domingo -> o 1o dia util e 02/02 (segunda).
    assert config.eh_primeiro_dia_util_do_mes("2026-02-01") is False
    assert config.eh_primeiro_dia_util_do_mes("2026-02-02") is True
    # Mesmo com hora no timestamp, a comparacao deve funcionar (bug do legado).
    assert config.eh_primeiro_dia_util_do_mes("2026-05-01 14:30:00") is True


def test_data_inicio_download_recua_o_historico():
    inicio = config.data_inicio_download("2026-05-19")
    assert inicio == pd.Timestamp("2021-05-19")


def test_ler_lista_tickers():
    tickers = data.ler_lista_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) > 0
    assert all(isinstance(t, str) for t in tickers)
    assert "ABEV3" in tickers  # primeiro ticker da planilha real


def test_valida_lista_tickers_sem_duplicatas_levanta_e_lista_repetidos():
    import pytest

    with pytest.raises(ValueError) as exc:
        data._valida_lista_tickers_sem_duplicatas(
            ["ABEV3", "PRIO3", "ABEV3", "LREN3", "PRIO3"]
        )

    msg = str(exc.value)
    assert "lista_tickers_liquidos.xlsx tem valores repetidos. Corrija" in msg
    assert "ABEV3" in msg and "PRIO3" in msg
    assert "LREN3" not in msg  # nao-duplicado nao aparece


def test_valida_lista_tickers_sem_duplicatas_passa_em_lista_limpa():
    data._valida_lista_tickers_sem_duplicatas(["ABEV3", "PRIO3", "LREN3"])


def test_ler_fundamentos_cache():
    df = data.ler_fundamentos_cache()
    assert "Ticker" in df.columns
    assert len(df) > 0


def test_carrega_fundamentos_raspa_no_primeiro_dia_util(tmp_path):
    chamadas = []

    def raspar_fake():
        chamadas.append(True)
        return pd.DataFrame({"Ticker": ["PRIO3"], "ROIC": [18.5]})

    cache = tmp_path / "cache.xlsx"
    df = data.carrega_fundamentos("2026-05-01", raspar_fake, caminho_cache=cache)

    assert chamadas == [True]            # raspou uma vez
    assert cache.exists()                # gravou o cache em disco
    assert list(df["Ticker"]) == ["PRIO3"]


def test_carrega_fundamentos_usa_cache_fora_do_primeiro_dia(tmp_path):
    cache = tmp_path / "cache.xlsx"
    pd.DataFrame({"Ticker": ["ASAI3"], "ROIC": [9.0]}).to_excel(cache, index=False)

    def raspar_proibido():
        raise AssertionError("nao deveria raspar fora do 1o dia util")

    df = data.carrega_fundamentos("2026-05-15", raspar_proibido,
                                  caminho_cache=cache)

    assert list(df["Ticker"]) == ["ASAI3"]  # devolveu o cache, sem raspar


def test_carrega_fundamentos_forcar_raspagem_ignora_calendario(tmp_path):
    """`forcar_raspagem=True` raspa mesmo fora do 1o dia util e com cache valido."""
    cache = tmp_path / "cache.xlsx"
    pd.DataFrame({"Ticker": ["ASAI3"], "ROIC": [9.0]}).to_excel(cache, index=False)

    chamadas = []

    def raspar_fake():
        chamadas.append(True)
        return pd.DataFrame({"Ticker": ["PRIO3"], "ROIC": [18.5]})

    df = data.carrega_fundamentos("2026-05-15", raspar_fake,
                                  caminho_cache=cache, forcar_raspagem=True)

    assert chamadas == [True]                # raspou apesar do dia comum
    assert list(df["Ticker"]) == ["PRIO3"]   # devolveu o novo, nao o cache


def test_carrega_fundamentos_cache_ausente_dispara_raspagem(tmp_path):
    """Cache que nao existe em disco aciona raspagem automatica."""
    cache = tmp_path / "nao_existe.xlsx"
    chamadas = []

    def raspar_fake():
        chamadas.append(True)
        return pd.DataFrame({"Ticker": ["PRIO3"], "ROIC": [18.5]})

    df = data.carrega_fundamentos("2026-05-15", raspar_fake, caminho_cache=cache)

    assert chamadas == [True]
    assert cache.exists()
    assert list(df["Ticker"]) == ["PRIO3"]


def test_carrega_fundamentos_cache_vazio_dispara_raspagem(tmp_path):
    """Cache existente mas com shape (0,0) aciona raspagem automatica."""
    cache = tmp_path / "cache.xlsx"
    pd.DataFrame().to_excel(cache, index=False)   # cache vazio em disco

    chamadas = []

    def raspar_fake():
        chamadas.append(True)
        return pd.DataFrame({"Ticker": ["PRIO3"], "ROIC": [18.5]})

    df = data.carrega_fundamentos("2026-05-15", raspar_fake, caminho_cache=cache)

    assert chamadas == [True]
    assert list(df["Ticker"]) == ["PRIO3"]


def test_baixa_cotacoes_yahoo_sucesso(monkeypatch):
    esperado = pd.DataFrame({"Close": [1.0, 2.0]})
    monkeypatch.setattr(yfinance, "download", lambda *a, **k: esperado)
    resultado = data.baixa_cotacoes_yahoo("PRIO3.SA")
    pd.testing.assert_frame_equal(resultado, esperado)


def test_baixa_cotacoes_yahoo_rate_limit_esgota_e_devolve_vazio(monkeypatch):
    """Rate-limit em todas as tentativas: tenta `tentativas` vezes, espera
    entre elas (sem dormir de verdade no teste) e devolve DataFrame vazio."""
    chamadas = {"download": 0, "sleep": 0}

    def download_que_sempre_falha(*a, **k):
        chamadas["download"] += 1
        raise YFRateLimitError()

    monkeypatch.setattr(yfinance, "download", download_que_sempre_falha)
    monkeypatch.setattr(data.time, "sleep", lambda s: chamadas.__setitem__("sleep", chamadas["sleep"] + 1))

    resultado = data.baixa_cotacoes_yahoo("PRIO3.SA", tentativas=3)

    assert resultado.empty
    assert chamadas["download"] == 3        # tentou 3 vezes
    assert chamadas["sleep"] == 2           # esperou entre as tentativas, nao apos a ultima
