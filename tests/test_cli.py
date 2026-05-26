"""Testes da CLI minima (`robusta.cli`) - fatia antecipada da Fase 8.

Comando: pytest
"""

import pandas as pd

from robusta import cli, data


def _fundamentos_crus():
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


def _mock_rede(monkeypatch, ohlcv_fixtures):
    monkeypatch.setattr(
        data, "baixa_cotacoes_yahoo",
        lambda ticker_yf, **kw: ohlcv_fixtures[ticker_yf[:-3]].copy(),
    )
    monkeypatch.setattr(
        data, "carrega_fundamentos",
        lambda momento, raspar_fn=None, **kw: _fundamentos_crus(),
    )


def test_cli_run_com_tickers_e_export_xlsx(monkeypatch, ohlcv_fixtures, tmp_path, capsys):
    _mock_rede(monkeypatch, ohlcv_fixtures)
    saida = tmp_path / "merged.xlsx"

    cli.main(["run", "--tickers", "PRIO3", "ASAI3", "--export-xlsx", str(saida)])

    # xlsx foi criado e tem as duas linhas analisadas.
    assert saida.exists()
    exportado = pd.read_excel(saida)
    assert len(exportado) == 2
    assert "Ticker" in exportado.columns

    # resumo impresso.
    out = capsys.readouterr().out
    assert "tickers_ok=2" in out
    assert "merged exportado" in out


def test_cli_run_sem_tickers_usa_lista_do_excel(monkeypatch, ohlcv_fixtures, capsys):
    _mock_rede(monkeypatch, ohlcv_fixtures)
    # Sem --tickers a CLI chama ler_lista_tickers; mockado para um universo curto.
    monkeypatch.setattr(data, "ler_lista_tickers", lambda *a, **k: ["PRIO3", "ASAI3"])

    cli.main(["run"])

    out = capsys.readouterr().out
    assert "tickers_ok=2" in out


def test_cli_run_emit_latest_grava_json_e_xlsx(monkeypatch, ohlcv_fixtures, tmp_path, capsys):
    """`--emit-latest PASTA` grava latest.json + latest.xlsx via persistence."""
    _mock_rede(monkeypatch, ohlcv_fixtures)
    pasta = tmp_path / "var"

    cli.main(["run", "--tickers", "PRIO3", "ASAI3", "--emit-latest", str(pasta)])

    assert (pasta / "latest.json").exists()
    assert (pasta / "latest.xlsx").exists()

    out = capsys.readouterr().out
    assert "latest.json + latest.xlsx gravados" in out
