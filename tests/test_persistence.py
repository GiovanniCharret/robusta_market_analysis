"""Testes da Fase 6 do rebuild - persistencia JSON + XLSX (`robusta.persistence`).

Cobertura:
- encoder/conversor de tipos numpy/pandas/NaN para tipos JSON nativos
- construcao do payload (estrutura `tickers` por dict, mapping snake_case ASCII,
  portfolio_signals em {longs, shorts})
- escrita atomica (write tmp + replace)
- guarda contra execucao degenerada (tickers_ok==0, taxa de falha > 50%)

Comando: pytest
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from robusta import persistence
from robusta.pipeline import RunResult, SCHEMA_VERSION


# --- helpers ---------------------------------------------------------------


def _merged_minimo():
    """DataFrame parecido com o merged_results real (1 linha por ticker)."""
    return pd.DataFrame([
        {
            "Date": pd.Timestamp("2026-05-08"),
            "Ticker": "PRIO3",
            "Close": 47.77,
            "Open": 48.07, "High": 48.43, "Low": 47.69, "Adj Close": 47.77, "Volume": 24_000_000,
            "Return": -0.006,
            "MMA9": 48.50, "MMA10": 48.72, "MMA26": 51.86, "MMA50": 56.27, "MMA150": 56.79, "MMA200": 56.02,
            "Position_MMA9": -1, "Position_MMA10": -1, "Position_MMA26": -1,
            "Position_MMA50": -1, "Position_MMA150": -1, "Position_MMA200": -1,
            "%_to_MMA9": -1.5, "%_to_MMA10": -1.96, "%_to_MMA26": -7.89,
            "%_to_MMA50": -15.12, "%_to_MMA150": -15.88, "%_to_MMA200": -14.73,
            "vol_anualized_30days": 0.287,
            "Alto_volume_persistente": 1,
            "sup_min_by_mslf": "Abismo",
            "sup_med_by_mslf": 39.9,
            "sup_max_by_mslf": 46.6,
            "res_min_by_mslf": 48.3,
            "res_med_by_mslf": 52.7,
            "res_max_by_mslf": 53.2,
            "std_raking_value_by_mslf": 1,
            "momentum_break_by_mslf": 0,
            "Subsetor": "Exploração, Refino e Distribuição",
            "LPA": 5.0, "VPA": 10.0, "Nro. Ações": 1000.0, "Dív. Líquida": 2000.0,
            "Cres. Rec (5a)": 10.0, "ROIC": 15.0, "EV / EBIT": 6.0,
            "P/L": 9.55, "P/VP": 4.78,
            "Dív. Líquida/Valor de mercado": 0.04,
            "classe Cres. Rec (5a)": 10, "classe ROIC": 10,
            "classe Dív. Líquida/Valor de mercado": float("nan"),
            "classe P/L": 1, "classe P/VP": 1, "classe EV / EBIT": 10,
            "avaliacao_fundamentalista": 31,
            "Posicao setorial": "pior",
            "Fundamental_?value": 0,
            "%_to_MMA50_Categoria": 5, "%_to_MMA10_Categoria": 5,
            "Vol Mês^Anual_?value": 0,
            "distortion_ranking": 34,
        },
        {
            "Date": pd.Timestamp("2026-05-08"),
            "Ticker": "ASAI3",
            "Close": 9.84,
            "Open": 9.80, "High": 9.95, "Low": 9.70, "Adj Close": 9.84, "Volume": 12_000_000,
            "Return": 0.005,
            "MMA9": 9.40, "MMA10": 9.42, "MMA26": 9.20, "MMA50": 9.10, "MMA150": 9.05, "MMA200": 9.00,
            "Position_MMA9": 1, "Position_MMA10": 1, "Position_MMA26": 1,
            "Position_MMA50": 1, "Position_MMA150": 1, "Position_MMA200": 1,
            "%_to_MMA9": 4.5, "%_to_MMA10": 4.5, "%_to_MMA26": 6.9,
            "%_to_MMA50": 8.1, "%_to_MMA150": 8.7, "%_to_MMA200": 9.3,
            "vol_anualized_30days": 0.305,
            "Alto_volume_persistente": 0,
            "sup_min_by_mslf": 8.2, "sup_med_by_mslf": 8.6, "sup_max_by_mslf": 9.2,
            "res_min_by_mslf": 10.1, "res_med_by_mslf": 10.6, "res_max_by_mslf": "Foguete",
            "std_raking_value_by_mslf": 2, "momentum_break_by_mslf": 0,
            "Subsetor": "Alimentar",
            "LPA": 2.0, "VPA": 4.0, "Nro. Ações": 2000.0, "Dív. Líquida": 1000.0,
            "Cres. Rec (5a)": 5.0, "ROIC": 8.0, "EV / EBIT": 9.0,
            "P/L": 4.92, "P/VP": 2.46,
            "Dív. Líquida/Valor de mercado": 0.05,
            "classe Cres. Rec (5a)": 1, "classe ROIC": 1,
            "classe Dív. Líquida/Valor de mercado": float("nan"),
            "classe P/L": 10, "classe P/VP": 10, "classe EV / EBIT": 1,
            "avaliacao_fundamentalista": 22,
            "Posicao setorial": "melhor",
            "Fundamental_?value": 0,
            "%_to_MMA50_Categoria": 8, "%_to_MMA10_Categoria": 8,
            "Vol Mês^Anual_?value": 0,
            "distortion_ranking": 77,
        },
    ])


def _portfolio_signals_minimo():
    """Mesmo shape que distorted_price_analysis devolve: top + bottom concatenados."""
    return pd.DataFrame([
        {"Ticker": "ASAI3", "Subsetor": "Alimentar", "Major->Long": 77, "%_to_MMA10": 4.5},
        {"Ticker": "PRIO3", "Subsetor": "Exploração", "Major->Long": 34, "%_to_MMA10": -1.96},
        {"Ticker": "PRIO3", "Subsetor": "Exploração", "Major->Long": 34, "%_to_MMA10": -1.96},
        {"Ticker": "ASAI3", "Subsetor": "Alimentar", "Major->Long": 77, "%_to_MMA10": 4.5},
    ])


def _run_result_minimo():
    return RunResult(
        schema_version=SCHEMA_VERSION,
        run_id="2026-05-26T13-00-00Z",
        generated_at="2026-05-26T13:00:00+00:00",
        robusta_version="13",
        input_universe=["PRIO3", "ASAI3"],
        summary={
            "tickers_ok": 2,
            "tickers_failed": 0,
            "vol_media": np.float64(0.296),
            "vol_std": np.float64(0.012),
        },
        technical_results=_merged_minimo(),  # mesma fixture suficiente para teste
        fundamental_results=_merged_minimo(),
        merged_results=_merged_minimo(),
        portfolio_signals=_portfolio_signals_minimo(),
        warnings=[],
        failed_tickers=[],
    )


# --- conversor de celula ---------------------------------------------------


def test_converte_celula_nan_vira_none():
    assert persistence._converte_celula(float("nan")) is None


def test_converte_celula_numpy_float_nan_vira_none():
    assert persistence._converte_celula(np.float64("nan")) is None


def test_converte_celula_numpy_int_vira_int_nativo():
    val = persistence._converte_celula(np.int64(42))
    assert val == 42
    assert isinstance(val, int) and not isinstance(val, np.integer)


def test_converte_celula_numpy_float_vira_float_nativo():
    val = persistence._converte_celula(np.float64(3.14))
    assert val == pytest.approx(3.14)
    assert isinstance(val, float) and not isinstance(val, np.floating)


def test_converte_celula_pandas_timestamp_vira_iso():
    val = persistence._converte_celula(pd.Timestamp("2026-05-26T13:00:00"))
    assert val.startswith("2026-05-26T13:00:00")


def test_converte_celula_string_sentinela_preservada():
    assert persistence._converte_celula("Abismo") == "Abismo"
    assert persistence._converte_celula("Foguete") == "Foguete"


def test_converte_celula_string_normal_preservada():
    assert persistence._converte_celula("PRIO3") == "PRIO3"


# --- payload ---------------------------------------------------------------


def test_constroi_payload_estrutura_top_level():
    payload = persistence.constroi_payload(_run_result_minimo())

    chaves_esperadas = {
        "schema_version", "run_id", "generated_at", "robusta_version",
        "input_universe", "summary", "portfolio_signals", "tickers",
        "warnings", "failed_tickers",
    }
    assert chaves_esperadas == set(payload.keys())


def test_constroi_payload_tickers_e_dict_indexado_por_ticker():
    payload = persistence.constroi_payload(_run_result_minimo())
    assert "PRIO3" in payload["tickers"]
    assert "ASAI3" in payload["tickers"]
    assert payload["tickers"]["PRIO3"]["ticker"] == "PRIO3"


def test_constroi_payload_mapeia_colunas_snake_case_ascii():
    payload = persistence.constroi_payload(_run_result_minimo())
    prio = payload["tickers"]["PRIO3"]

    # Identidade
    assert prio["ticker"] == "PRIO3"
    assert prio["subsetor"] == "Exploração, Refino e Distribuição"

    # Sinais com nomes ASCII (sem acentos, sem ?)
    assert prio["fundamental_signal"] == 0
    assert prio["vol_signal"] == 0
    assert prio["posicao_setorial"] == "pior"

    # Técnica
    assert prio["preco"] == pytest.approx(47.77)
    assert prio["vol_anualizada_30d"] == pytest.approx(0.287)
    assert prio["alto_vol_persistente"] == 1
    assert prio["mma10"] == pytest.approx(48.72)
    assert prio["mma200"] == pytest.approx(56.02)
    assert prio["pct_to_mma10"] == pytest.approx(-1.96)
    assert prio["pct_to_mma50"] == pytest.approx(-15.12)

    # Niveis MSLF (preservam nome original)
    assert prio["sup_min_by_mslf"] == "Abismo"
    assert prio["sup_med_by_mslf"] == pytest.approx(39.9)
    assert prio["res_max_by_mslf"] == pytest.approx(53.2)
    assert prio["std_raking_value_by_mslf"] == 1
    assert prio["momentum_break_by_mslf"] == 0

    # Fundamental
    assert prio["pl"] == pytest.approx(9.55)
    assert prio["pvp"] == pytest.approx(4.78)
    assert prio["ev_ebit"] == pytest.approx(6.0)
    assert prio["roic"] == pytest.approx(15.0)
    assert prio["cres_rec_5a"] == pytest.approx(10.0)
    assert prio["div_liq_vm"] == pytest.approx(0.04)
    assert prio["avaliacao_fundamentalista"] == 31

    # Ranking
    assert prio["distortion_ranking"] == 34


def test_constroi_payload_portfolio_signals_separa_longs_shorts():
    payload = persistence.constroi_payload(_run_result_minimo())
    sig = payload["portfolio_signals"]

    assert "longs" in sig and "shorts" in sig
    # Apos inversao semantica (distortion alto = pressao vendedora):
    # 2 primeiras linhas (nlargest) viram SHORTS; 2 ultimas (nsmallest) viram LONGS.
    assert len(sig["longs"]) == 2
    assert len(sig["shorts"]) == 2
    # Validacao da semantica: shorts contem o maior distortion_ranking
    assert sig["shorts"][0]["distortion_ranking"] == 77
    assert sig["longs"][0]["distortion_ranking"] == 34
    # Schema por entrada
    assert set(sig["longs"][0].keys()) == {"ticker", "subsetor", "distortion_ranking", "pct_to_mma10"}


def test_constroi_payload_summary_converte_numpy_floats():
    payload = persistence.constroi_payload(_run_result_minimo())
    assert isinstance(payload["summary"]["vol_media"], float)
    assert not isinstance(payload["summary"]["vol_media"], np.floating)


def test_constroi_payload_inclui_metadados():
    payload = persistence.constroi_payload(_run_result_minimo())
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["run_id"] == "2026-05-26T13-00-00Z"
    assert payload["robusta_version"] == "13"
    assert payload["input_universe"] == ["PRIO3", "ASAI3"]


# --- serialização JSON (round-trip) ----------------------------------------


def test_serializacao_json_roundtrip_sem_typeerror():
    """json.dumps com o encoder customizado nao deve levantar TypeError."""
    payload = persistence.constroi_payload(_run_result_minimo())
    texto = json.dumps(payload, cls=persistence._Encoder, ensure_ascii=False)
    # roundtrip: parsing reconstrói o mesmo schema basico
    parsed = json.loads(texto)
    assert parsed["tickers"]["PRIO3"]["ticker"] == "PRIO3"
    assert parsed["schema_version"] == SCHEMA_VERSION


def test_serializacao_nan_vira_null():
    """NaN em coluna 'classe Dív. Líquida/Valor de mercado' deve aparecer como
    null no JSON (campo nao mapeado nao polui, mas se um campo mapeado vier NaN,
    precisa virar null)."""
    rr = _run_result_minimo()
    # Forca NaN em um campo MAPEADO
    rr.merged_results.loc[0, "Dív. Líquida/Valor de mercado"] = float("nan")
    payload = persistence.constroi_payload(rr)
    assert payload["tickers"]["PRIO3"]["div_liq_vm"] is None

    # Confirma que vira "null" no JSON serializado, nao "NaN"
    texto = json.dumps(payload, cls=persistence._Encoder, ensure_ascii=False)
    assert '"div_liq_vm": null' in texto
    assert "NaN" not in texto


# --- escrita atomica ------------------------------------------------------


def test_grava_latest_cria_json_e_xlsx(tmp_path):
    persistence.grava_latest(_run_result_minimo(), tmp_path)
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.xlsx").exists()


def test_grava_latest_json_parseavel(tmp_path):
    persistence.grava_latest(_run_result_minimo(), tmp_path)
    payload = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert payload["tickers"]["PRIO3"]["ticker"] == "PRIO3"
    assert payload["tickers"]["ASAI3"]["distortion_ranking"] == 77


def test_grava_latest_remove_tmp_apos_replace(tmp_path):
    persistence.grava_latest(_run_result_minimo(), tmp_path)
    assert not (tmp_path / "latest.json.tmp").exists()
    assert not (tmp_path / "latest.xlsx.tmp").exists()


def test_grava_latest_sobrescreve_versao_anterior(tmp_path):
    """Segunda chamada substitui a primeira."""
    persistence.grava_latest(_run_result_minimo(), tmp_path)
    primeira = (tmp_path / "latest.json").read_text(encoding="utf-8")

    rr2 = _run_result_minimo()
    rr2.run_id = "2026-05-26T16-00-00Z"
    persistence.grava_latest(rr2, tmp_path)
    segunda = (tmp_path / "latest.json").read_text(encoding="utf-8")

    assert "2026-05-26T16-00-00Z" in segunda
    assert primeira != segunda


# --- guarda contra execucao degenerada ------------------------------------


def test_grava_latest_falha_se_tickers_ok_zero(tmp_path):
    rr = _run_result_minimo()
    rr.summary = {"tickers_ok": 0, "tickers_failed": 5, "vol_media": None, "vol_std": None}

    with pytest.raises(RuntimeError, match="degenerada"):
        persistence.grava_latest(rr, tmp_path)

    # latest.json NAO foi criado
    assert not (tmp_path / "latest.json").exists()
    # last_failed_run.json foi criado com o payload pra diagnostico
    assert (tmp_path / "last_failed_run.json").exists()


def test_grava_latest_falha_se_taxa_falha_acima_de_50(tmp_path):
    rr = _run_result_minimo()
    rr.summary = {"tickers_ok": 2, "tickers_failed": 3, "vol_media": 0.3, "vol_std": 0.01}

    with pytest.raises(RuntimeError, match="degenerada"):
        persistence.grava_latest(rr, tmp_path)
    assert not (tmp_path / "latest.json").exists()


def test_grava_latest_preserva_latest_anterior_em_falha(tmp_path):
    """Execucao boa, depois execucao degenerada: latest.json NAO e tocado."""
    persistence.grava_latest(_run_result_minimo(), tmp_path)
    boa = (tmp_path / "latest.json").read_text(encoding="utf-8")

    rr_ruim = _run_result_minimo()
    rr_ruim.summary = {"tickers_ok": 0, "tickers_failed": 5, "vol_media": None, "vol_std": None}
    with pytest.raises(RuntimeError):
        persistence.grava_latest(rr_ruim, tmp_path)

    # latest.json continua sendo o da execucao boa
    assert (tmp_path / "latest.json").read_text(encoding="utf-8") == boa
