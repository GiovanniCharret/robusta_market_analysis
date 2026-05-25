"""Testes da Fase 5 do rebuild - pipeline consolidado (`robusta.pipeline`).

Comando: pytest
"""

import pandas as pd
import pytest

from robusta import data, fundamental, pipeline


# --- 5a: distorions_analysys -----------------------------------------------

def _df_montagens(vols, mma50, mma10):
    return pd.DataFrame({
        "vol_anualized_30days": vols,
        "%_to_MMA50": mma50,
        "%_to_MMA10": mma10,
    })


def test_distorions_analysys_cria_colunas_e_preserva_media_std():
    df = _df_montagens(
        vols=[0.1, 0.2, 0.3, 0.4, 0.5],
        mma50=[-5.0, -1.0, 0.0, 2.0, 8.0],
        mma10=[1.0, 2.0, 3.0, 4.0, 5.0],
    )
    resultado, stats = pipeline.distorions_analysys(df)

    # Colunas criadas (nomes do baseline).
    assert "%_to_MMA50_Categoria" in resultado.columns
    assert "%_to_MMA10_Categoria" in resultado.columns
    assert "Vol Mês^Anual_?value" in resultado.columns

    # Categorias sao inteiros em 1..10 (rank percentil).
    assert resultado["%_to_MMA50_Categoria"].between(1, 10).all()
    assert resultado["%_to_MMA50_Categoria"].iloc[-1] == 10   # maior distancia
    assert str(resultado["%_to_MMA50_Categoria"].dtype).startswith("int")

    # media/std_vol preservados (nao descartados como no legado).
    assert stats["média"] is not None
    assert stats["std_vol"] is not None
    assert stats["média"] == pytest.approx(0.3)


def test_distorions_analysys_vol_value_sinais():
    """Vol abaixo de media-std -> 1; acima de media+std -> -1; meio -> 0."""
    df = _df_montagens(
        vols=[0.1, 0.2, 0.3, 0.4, 0.5],
        mma50=[1.0, 2.0, 3.0, 4.0, 5.0],
        mma10=[1.0, 2.0, 3.0, 4.0, 5.0],
    )
    resultado, stats = pipeline.distorions_analysys(df)

    media, std = stats["média"], stats["std_vol"]
    valores = resultado["Vol Mês^Anual_?value"]
    # Conferencia direta da regra contra media/std calculados.
    for vol, val in zip(df["vol_anualized_30days"], valores):
        esperado = 1 if vol < media - std else (-1 if vol > media + std else 0)
        assert val == esperado


# --- 5b: distorted_price_analysis ------------------------------------------

def _df_distortion(n=6):
    return pd.DataFrame({
        "Ticker": [f"TIC{i}" for i in range(n)],
        "Subsetor": ["Sub"] * n,
        "avaliacao_fundamentalista": [10, 20, 25, 30, 35, 40][:n],
        "%_to_MMA50_Categoria": [1, 3, 5, 6, 8, 10][:n],
        "%_to_MMA10_Categoria": [2, 4, 5, 7, 9, 10][:n],
        "%_to_MMA10": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6][:n],
    })


def test_distorted_price_analysis_formula_e_colunas():
    df = _df_distortion()
    resultado = pipeline.distorted_price_analysis(df, mma50_wgh=4, mma10_wgh=1)

    # Colunas finais e o rename.
    assert list(resultado.columns) == ["Ticker", "Subsetor", "Major->Long", "%_to_MMA10"]

    # Formula (Opcao 1) para TIC0: (10-40)*-1 + 1*4 + 2*1 = 30 + 4 + 2 = 36.
    linha_tic0 = resultado[resultado["Ticker"] == "TIC0"]
    assert linha_tic0["Major->Long"].iloc[0] == 36


def test_distorted_price_analysis_usa_mma10_e_nao_mma50_duas_vezes():
    """Duas linhas iguais exceto MMA10_Categoria devem ter ranking diferente
    (prova que a 3a parcela usa MMA10, nao MMA50 de novo)."""
    df = pd.DataFrame({
        "Ticker": ["A", "B"],
        "Subsetor": ["S", "S"],
        "avaliacao_fundamentalista": [20, 20],
        "%_to_MMA50_Categoria": [5, 5],
        "%_to_MMA10_Categoria": [1, 9],     # so o MMA10 difere
        "%_to_MMA10": [0.1, 0.2],
    })
    resultado = pipeline.distorted_price_analysis(df, mma50_wgh=4, mma10_wgh=1)
    # nlargest(5)+nsmallest(5) duplicam linhas em universos pequenos; filtro por mascara.
    val_a = resultado.loc[resultado["Ticker"] == "A", "Major->Long"].iloc[0]
    val_b = resultado.loc[resultado["Ticker"] == "B", "Major->Long"].iloc[0]
    # A: (20-40)*-1 + 5*4 + 1*1 = 20+20+1 = 41 ; B: ...+9*1 = 49.
    assert val_a == 41
    assert val_b == 49


# --- 5c: executa_pipeline (integracao com mocks de rede) -------------------

def _fundamentos_crus():
    """DataFrame fundamentalista cru (como sairia de varre_lista/cache)."""
    return pd.DataFrame({
        "Ticker": ["PRIO3", "ASAI3"],
        "Setor": ["Petróleo", "Varejo"],
        "Subsetor": ["Exploração", "Alimentar"],
        "LPA": [5.0, 2.0],
        "VPA": [10.0, 4.0],
        "Nro. Ações": [1000.0, 2000.0],
        "Dív. Líquida": [2000.0, 1000.0],
        "Cres. Rec (5a)": [10.0, 5.0],
        "ROIC": [15.0, 8.0],
        "EV / EBIT": [6.0, 9.0],
    })


def test_executa_pipeline_integracao(monkeypatch, ohlcv_fixtures):
    # Tecnica roda de verdade sobre as fixtures (PRIO3 != ASAI3 -> vols distintas).
    monkeypatch.setattr(
        data, "baixa_cotacoes_yahoo",
        lambda ticker_yf, **kw: ohlcv_fixtures[ticker_yf[:-3]].copy(),
    )
    # Fundamentos: pula scraping/cache, devolve direto os crus.
    monkeypatch.setattr(
        data, "carrega_fundamentos",
        lambda momento, raspar_fn=None, **kw: _fundamentos_crus(),
    )

    resultado = pipeline.executa_pipeline(["PRIO3", "ASAI3"])

    # Metadados.
    assert resultado.schema_version == pipeline.SCHEMA_VERSION
    assert resultado.run_id
    assert resultado.generated_at
    assert resultado.input_universe == ["PRIO3", "ASAI3"]

    # DataFrames preenchidos.
    assert len(resultado.technical_results) == 2
    assert len(resultado.merged_results) == 2

    # Colunas essenciais no merge (tecnica + fundamental + cross-sectional).
    for col in ("Ticker", "vol_anualized_30days", "avaliacao_fundamentalista",
                "%_to_MMA50_Categoria", "Fundamental_?value"):
        assert col in resultado.merged_results.columns

    # summary.std_vol nao e None (requisito do PLAN) e nao ha falhas.
    assert resultado.summary["vol_std"] is not None
    assert resultado.summary["tickers_ok"] == 2
    assert resultado.summary["tickers_failed"] == 0


def test_executa_pipeline_registra_ticker_sem_dados_tecnicos(monkeypatch, ohlcv_fixtures):
    def fake_baixa(ticker_yf, **kw):
        base = ticker_yf[:-3]
        if base == "XPTO3":
            return pd.DataFrame()   # download vazio -> screener pula
        return ohlcv_fixtures[base].copy()

    monkeypatch.setattr(data, "baixa_cotacoes_yahoo", fake_baixa)
    monkeypatch.setattr(
        data, "carrega_fundamentos",
        lambda momento, raspar_fn=None, **kw: _fundamentos_crus(),
    )

    resultado = pipeline.executa_pipeline(["PRIO3", "XPTO3"])

    assert resultado.summary["tickers_ok"] == 1
    assert resultado.summary["tickers_failed"] == 1
    assert resultado.failed_tickers[0]["ticker"] == "XPTO3"
