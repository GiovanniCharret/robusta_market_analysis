"""Testes da Fase 3 do rebuild - analise tecnica (`robusta.technical`).

Comando: pytest
"""

import math

import pandas as pd
import pytest

from robusta import data, technical


# --- T1: crie_variacao -----------------------------------------------------

def test_crie_variacao_info_1_calcula_pct_change_de_close():
    df = pd.DataFrame({"Close": [10.0, 12.0, 9.0]})
    resultado = technical.crie_variacao(df, 1)

    # Primeiro valor de pct_change e NaN; os seguintes sao (12/10 - 1) e (9/12 - 1).
    assert "Return" in resultado.columns
    assert math.isnan(resultado["Return"].iloc[0])
    assert resultado["Return"].iloc[1] == pytest.approx(0.2)
    assert resultado["Return"].iloc[2] == pytest.approx(-0.25)


def test_crie_variacao_info_2_calcula_pct_change_de_momentum():
    df = pd.DataFrame({"Momentum": [100.0, 110.0, 99.0]})
    resultado = technical.crie_variacao(df, 2)

    assert "Oscillation" in resultado.columns
    assert math.isnan(resultado["Oscillation"].iloc[0])
    assert resultado["Oscillation"].iloc[1] == pytest.approx(0.1)
    assert resultado["Oscillation"].iloc[2] == pytest.approx(-0.1)


def test_crie_variacao_devolve_o_mesmo_dataframe():
    """O legado retorna o proprio DataFrame mutado; preservar esse contrato."""
    df = pd.DataFrame({"Close": [1.0, 2.0]})
    resultado = technical.crie_variacao(df, 1)
    assert resultado is df


def test_crie_variacao_info_invalido_levanta():
    df = pd.DataFrame({"Close": [1.0, 2.0]})
    with pytest.raises(ValueError):
        technical.crie_variacao(df, 3)


# --- T2: crie_medias_moveis ------------------------------------------------

def test_crie_medias_moveis_janela_2_com_valores_conhecidos():
    """Para Close=[10, 20, 15] e janela 2: MMA=[NaN, 15, 17.5].

    Confere as tres colunas geradas: MMA, Position_MMA e %_to_MMA.
    """
    df = pd.DataFrame({"Close": [10.0, 20.0, 15.0]})
    resultado = technical.crie_medias_moveis(df, [2])

    # MMA: NaN no primeiro dia (janela incompleta), depois medias simples.
    assert math.isnan(resultado["MMA2"].iloc[0])
    assert resultado["MMA2"].iloc[1] == pytest.approx(15.0)
    assert resultado["MMA2"].iloc[2] == pytest.approx(17.5)

    # Position_MMA: 0 onde MMA e NaN, 1 quando Close > MMA, -1 caso contrario.
    assert resultado["Position_MMA2"].iloc[0] == 0
    assert resultado["Position_MMA2"].iloc[1] == 1    # 20 > 15
    assert resultado["Position_MMA2"].iloc[2] == -1   # 15 < 17.5

    # %_to_MMA: NaN onde MMA e NaN; (Close - MMA) / MMA * 100 nos demais.
    assert math.isnan(resultado["%_to_MMA2"].iloc[0])
    assert resultado["%_to_MMA2"].iloc[1] == pytest.approx((20 - 15) / 15 * 100)
    assert resultado["%_to_MMA2"].iloc[2] == pytest.approx((15 - 17.5) / 17.5 * 100)


def test_crie_medias_moveis_close_igual_a_mma_cai_em_menos_um():
    """Contrato do legado: `Close > MMA` e estrito, entao Close == MMA -> -1."""
    # Close constante: MMA bate exatamente com Close a partir do 2o dia.
    df = pd.DataFrame({"Close": [10.0, 10.0]})
    resultado = technical.crie_medias_moveis(df, [2])
    assert resultado["MMA2"].iloc[1] == pytest.approx(10.0)
    assert resultado["Position_MMA2"].iloc[1] == -1


def test_crie_medias_moveis_multiplas_janelas_geram_todas_as_colunas():
    df = pd.DataFrame({"Close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    resultado = technical.crie_medias_moveis(df, [2, 3])

    for n in (2, 3):
        assert f"MMA{n}" in resultado.columns
        assert f"Position_MMA{n}" in resultado.columns
        assert f"%_to_MMA{n}" in resultado.columns


def test_crie_medias_moveis_devolve_o_mesmo_dataframe():
    df = pd.DataFrame({"Close": [1.0, 2.0, 3.0]})
    assert technical.crie_medias_moveis(df, [2]) is df


# --- T3: calcule_volatilidade_anualizada_std -------------------------------

def test_calcule_volatilidade_anualizada_std_comparada_a_pandas_direto():
    """Comparacao direta contra `rolling(...).std() * sqrt(252)`."""
    retornos = [0.01, -0.02, 0.015, 0.005, -0.01, 0.0, 0.02]
    df = pd.DataFrame({"Return": retornos})
    janela = 3

    resultado = technical.calcule_volatilidade_anualizada_std(df, janela)
    esperado = pd.Series(retornos).rolling(window=janela).std() * (252 ** 0.5)

    coluna = f"vol_anualized_{janela}days"
    assert coluna in resultado.columns
    # As primeiras janela-1 entradas sao NaN (janela incompleta).
    assert resultado[coluna].iloc[: janela - 1].isna().all()
    # As demais batem com o calculo direto via pandas.
    pd.testing.assert_series_equal(
        resultado[coluna].iloc[janela - 1 :].reset_index(drop=True),
        esperado.iloc[janela - 1 :].reset_index(drop=True),
        check_names=False,
    )


def test_calcule_volatilidade_anualizada_std_nome_da_coluna_usa_vol_window():
    """O sufixo da coluna acompanha `vol_window` (contrato do baseline)."""
    df = pd.DataFrame({"Return": [0.01, 0.02, -0.01, 0.0, 0.005]})
    technical.calcule_volatilidade_anualizada_std(df, 30)
    technical.calcule_volatilidade_anualizada_std(df, 5)
    assert "vol_anualized_30days" in df.columns
    assert "vol_anualized_5days" in df.columns


def test_calcule_volatilidade_anualizada_std_devolve_o_mesmo_dataframe():
    df = pd.DataFrame({"Return": [0.0, 0.01, -0.01]})
    assert technical.calcule_volatilidade_anualizada_std(df, 2) is df


# --- T4: alto_volume_persistente -------------------------------------------

def _df_volume(volumes, closes):
    """Helper: DataFrame com colunas Volume e Close de mesmo comprimento."""
    return pd.DataFrame({"Volume": volumes, "Close": closes})


def test_alto_volume_persistente_streak_com_preco_subindo_marca_1():
    """Dois dias com volume >= 2x a media + Close subindo nos ultimos 2 dias -> 1.

    Janela do legado: volume_window=20, multiplier=2, k=2. Por isso a fixture
    tem 22 dias: 20 dias normais formam a media base, depois 2 dias seguidos
    de volume alto com preco subindo.
    """
    base_volume = [100] * 20
    base_close = [10.0 + 0.01 * i for i in range(20)]  # sobe devagar
    df = _df_volume(
        base_volume + [250, 250],
        base_close + [11.0, 12.0],  # ultimos dois dias o Close cresce forte
    )
    resultado = technical.alto_volume_persistente(df)
    assert resultado["Alto_volume_persistente"].iloc[-1] == 1


def test_alto_volume_persistente_streak_com_preco_caindo_marca_menos_1():
    base_volume = [100] * 20
    base_close = [10.0] * 20
    df = _df_volume(
        base_volume + [250, 250],
        base_close + [9.0, 8.0],  # ultimos dois dias o Close cai
    )
    resultado = technical.alto_volume_persistente(df)
    assert resultado["Alto_volume_persistente"].iloc[-1] == -1


def test_alto_volume_persistente_streak_quebrado_marca_zero():
    """Volume alto so num dia (sem dois dias consecutivos) -> 0."""
    base_volume = [100] * 20
    base_close = [10.0] * 20
    df = _df_volume(
        base_volume + [100, 250],   # so o ultimo dia tem volume alto
        base_close + [11.0, 12.0],
    )
    resultado = technical.alto_volume_persistente(df)
    assert resultado["Alto_volume_persistente"].iloc[-1] == 0


def test_alto_volume_persistente_preco_estavel_marca_zero():
    """Mesmo com streak de volume alto, pct_change(2) == 0 cai no default 0
    (o legado usa `>` e `<` estritos)."""
    base_volume = [100] * 20
    base_close = [10.0] * 20
    df = _df_volume(
        base_volume + [250, 250],
        base_close + [10.0, 10.0],  # preco estavel
    )
    resultado = technical.alto_volume_persistente(df)
    assert resultado["Alto_volume_persistente"].iloc[-1] == 0


def test_alto_volume_persistente_devolve_o_mesmo_dataframe():
    base_volume = [100] * 20
    df = _df_volume(base_volume + [250, 250], [10.0] * 22)
    assert technical.alto_volume_persistente(df) is df


# --- T5: add_price_concentration_levels_by_me ------------------------------

COLUNAS_BY_MSLF = [
    "sup_min_by_mslf", "sup_med_by_mslf", "sup_max_by_mslf",
    "res_min_by_mslf", "res_med_by_mslf", "res_max_by_mslf",
    "std_raking_value_by_mslf", "momentum_break_by_mslf",
]


def test_concentration_cria_as_8_colunas_by_mslf(ohlcv_fixtures):
    """O cerne do fix B1: as 8 colunas `*_by_mslf` passam a existir e ser
    populadas (no legado nunca eram criadas, por causa do `:` em vez de `=`)."""
    for ticker, df in ohlcv_fixtures.items():
        resultado = technical.add_price_concentration_levels_by_me(df)
        assert resultado is not None, ticker
        for coluna in COLUNAS_BY_MSLF:
            assert coluna in resultado.columns, f"{ticker} sem {coluna}"
            # Escalar broadcast: a coluna inteira tem um unico valor.
            assert resultado[coluna].nunique(dropna=False) == 1, f"{ticker}/{coluna}"


def test_concentration_devolve_o_mesmo_dataframe(ohlcv_fixtures):
    df = ohlcv_fixtures["PRIO3"]
    assert technical.add_price_concentration_levels_by_me(df) is df


def _df_concentracao(highs, lows, adj_closes):
    return pd.DataFrame({
        "High": highs,
        "Low": lows,
        "Adj Close": adj_closes,
    })


def test_concentration_sem_resistencia_marca_foguete_e_momentum_1():
    """Ultimo Adj Close acima de todos os edges -> nao ha resistencia:
    res_*_by_mslf viram 'Foguete' e momentum_break = 1."""
    highs = [12.0, 13.0, 14.0, 13.0, 15.0, 14.0, 16.0, 20.0]
    lows = [10.0, 11.0, 12.0, 11.0, 13.0, 12.0, 14.0, 19.0]
    adj = [11.0, 12.0, 13.0, 12.0, 14.0, 13.0, 15.0, 100.0]  # price_today = 100
    df = _df_concentracao(highs, lows, adj)

    resultado = technical.add_price_concentration_levels_by_me(df)
    assert resultado["res_min_by_mslf"].iloc[0] == "Foguete"
    assert resultado["res_med_by_mslf"].iloc[0] == "Foguete"
    assert resultado["res_max_by_mslf"].iloc[0] == "Foguete"
    assert resultado["momentum_break_by_mslf"].iloc[0] == 1


def test_concentration_sem_suporte_marca_abismo_e_momentum_menos_1():
    """Ultimo Adj Close abaixo de todos os edges -> nao ha suporte:
    sup_*_by_mslf viram 'Abismo' e momentum_break = -1."""
    highs = [12.0, 13.0, 14.0, 13.0, 15.0, 14.0, 16.0, 17.0]
    lows = [10.0, 11.0, 12.0, 11.0, 13.0, 12.0, 14.0, 15.0]
    adj = [11.0, 12.0, 13.0, 12.0, 14.0, 13.0, 15.0, 1.0]  # price_today = 1
    df = _df_concentracao(highs, lows, adj)

    resultado = technical.add_price_concentration_levels_by_me(df)
    assert resultado["sup_min_by_mslf"].iloc[0] == "Abismo"
    assert resultado["sup_med_by_mslf"].iloc[0] == "Abismo"
    assert resultado["sup_max_by_mslf"].iloc[0] == "Abismo"
    assert resultado["momentum_break_by_mslf"].iloc[0] == -1


# --- T6: extrai_cotacoes ---------------------------------------------------

def test_extrai_cotacoes_sucesso_enriquece_e_devolve_par(monkeypatch, ohlcv_fixtures):
    """Download valido -> [ticker, DataFrame enriquecido por T1-T5]."""
    monkeypatch.setattr(data, "baixa_cotacoes_yahoo",
                        lambda ticker, **kw: ohlcv_fixtures["PRIO3"].copy())

    resultado = technical.extrai_cotacoes("PRIO3.SA")

    assert isinstance(resultado, list)
    assert resultado[0] == "PRIO3.SA"
    df = resultado[1]
    # 'Ticker' base, sem o sufixo '.SA'.
    assert (df["Ticker"] == "PRIO3").all()
    # Colunas que cada subfase T1-T5 acrescenta estao presentes.
    assert "Date" in df.columns
    assert "Return" in df.columns
    assert "MMA200" in df.columns
    assert "vol_anualized_30days" in df.columns
    assert "Alto_volume_persistente" in df.columns
    assert "momentum_break_by_mslf" in df.columns


def test_extrai_cotacoes_download_vazio_devolve_false(monkeypatch):
    """Download vazio (inclui rate-limit esgotado em baixa_cotacoes_yahoo)."""
    monkeypatch.setattr(data, "baixa_cotacoes_yahoo",
                        lambda ticker, **kw: pd.DataFrame())
    assert technical.extrai_cotacoes("XPTO3.SA") is False


def test_extrai_cotacoes_volume_baixo_devolve_false(monkeypatch):
    """Volume medio dos ultimos 30 pregoes < 10.000 -> False."""
    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    df_baixo = pd.DataFrame(
        {
            "Open": [10.0] * 5, "High": [11.0] * 5, "Low": [9.0] * 5,
            "Close": [10.0] * 5, "Adj Close": [10.0] * 5, "Volume": [100] * 5,
        },
        index=idx,
    )
    monkeypatch.setattr(data, "baixa_cotacoes_yahoo", lambda ticker, **kw: df_baixo)
    assert technical.extrai_cotacoes("ILIQ3.SA") is False


# --- T7: screener ----------------------------------------------------------

def _fake_extrai_factory(closes_por_base=None, falham=(), levantam=()):
    """Cria um fake de extrai_cotacoes: devolve [yf_ticker, df] com a coluna
    Close, ou False para `falham`, ou levanta para `levantam`."""
    closes_por_base = closes_por_base or {}

    def fake(yf_ticker):
        base = yf_ticker[:-3]
        if base in levantam:
            raise ValueError(f"boom {base}")
        if base in falham:
            return False
        closes = closes_por_base.get(base, [10.0, 11.0])
        df = pd.DataFrame({"Ticker": [base] * len(closes), "Close": closes})
        return [yf_ticker, df]

    return fake


def test_screener_dois_tickers_duas_linhas_e_precos_sem_sufixo(monkeypatch):
    """Contrato T7: duas linhas finais + dict de precos com chaves base."""
    monkeypatch.setattr(
        technical, "extrai_cotacoes",
        _fake_extrai_factory({"PRIO3": [10.0, 11.0], "ASAI3": [20.0, 22.0]}),
    )

    carteira, precos = technical.screener(["PRIO3", "ASAI3"], pd.DataFrame())

    assert len(carteira) == 2
    assert set(precos) == {"PRIO3", "ASAI3"}   # chaves sem '.SA'
    assert precos["PRIO3"] == 11.0             # ultimo Close
    assert precos["ASAI3"] == 22.0
    assert isinstance(precos["PRIO3"], float)


def test_screener_pula_ticker_que_retorna_false(monkeypatch):
    monkeypatch.setattr(
        technical, "extrai_cotacoes",
        _fake_extrai_factory(falham={"FAIL3"}),
    )
    carteira, precos = technical.screener(["GOOD3", "FAIL3"], pd.DataFrame())
    assert len(carteira) == 1
    assert "GOOD3" in precos
    assert "FAIL3" not in precos


def test_screener_pula_ticker_em_probleminhas(monkeypatch):
    monkeypatch.setattr(technical, "extrai_cotacoes", _fake_extrai_factory())
    carteira, precos = technical.screener(
        ["PRIO3", "SKIP3"], pd.DataFrame(), probleminhas={"SKIP3"}
    )
    assert len(carteira) == 1
    assert "SKIP3" not in precos


def test_screener_continua_quando_um_ticker_levanta(monkeypatch):
    """Resiliencia: um ticker que levanta nao interrompe a varredura."""
    monkeypatch.setattr(
        technical, "extrai_cotacoes",
        _fake_extrai_factory(levantam={"BOOM3"}),
    )
    carteira, precos = technical.screener(["OK3", "BOOM3"], pd.DataFrame())
    assert len(carteira) == 1
    assert "OK3" in precos
    assert "BOOM3" not in precos


def test_screener_sem_resultados_devolve_carteira_intacta(monkeypatch):
    monkeypatch.setattr(
        technical, "extrai_cotacoes",
        _fake_extrai_factory(falham={"A3", "B3"}),
    )
    carteira_inicial = pd.DataFrame()
    carteira, precos = technical.screener(["A3", "B3"], carteira_inicial)
    assert carteira is carteira_inicial   # nada concatenado
    assert precos == {}
