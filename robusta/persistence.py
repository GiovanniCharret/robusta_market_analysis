"""Persistencia do ROBUSTA (Fase 6 do PLAN).

Serializa o `RunResult` da Fase 5 em dois arquivos atomicos:

- `latest.json` — payload completo consumido pelo frontend.
- `latest.xlsx` — `merged_results` exportado para Excel (download via botao
  do site).

Convenções (ver `planning/PLAN.md > JSON Contract`):

- Chaves do JSON em snake_case ASCII (`Dív. Líquida/Valor de mercado` →
  `div_liq_vm`); o mapping vive em `COLUNA_PARA_JSON`.
- Sentinelas `"Abismo"`/`"Foguete"` dos níveis `*_by_mslf` preservadas como
  string (o frontend trata).
- Escrita atômica: grava em `<arquivo>.tmp` e usa `Path.replace()`
  (`rename` atômico no Linux), garantindo que o nginx nunca sirva um arquivo
  pela metade.
- Guarda contra execução degenerada: se `tickers_ok == 0` ou taxa de falha
  > 50%, **não** sobrescreve `latest.json`; grava o payload em
  `last_failed_run.json` para diagnóstico e levanta `RuntimeError`.
"""

import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Mapping coluna do `merged_results` → chave JSON snake_case ASCII.
# Ordem preservada para que o JSON saia em ordem semântica (identidade →
# sinais → técnica → fundamental → ranking).
COLUNA_PARA_JSON = {
    # identidade
    "Ticker": "ticker",
    "Setor": "setor",         # ausente no merged_results atual (bug do legado em F7); fica None
    "Subsetor": "subsetor",
    # sinais
    "Fundamental_?value": "fundamental_signal",
    "Vol Mês^Anual_?value": "vol_signal",
    "Posicao setorial": "posicao_setorial",
    # técnica - preço
    "Close": "preco",
    # técnica - volatilidade/volume
    "vol_anualized_30days": "vol_anualizada_30d",
    "Alto_volume_persistente": "alto_vol_persistente",
    # técnica - MMAs
    "MMA9": "mma9",
    "MMA10": "mma10",
    "MMA26": "mma26",
    "MMA50": "mma50",
    "MMA150": "mma150",
    "MMA200": "mma200",
    "%_to_MMA10": "pct_to_mma10",
    "%_to_MMA50": "pct_to_mma50",
    # técnica - níveis (nomes preservados)
    "sup_min_by_mslf": "sup_min_by_mslf",
    "sup_med_by_mslf": "sup_med_by_mslf",
    "sup_max_by_mslf": "sup_max_by_mslf",
    "res_min_by_mslf": "res_min_by_mslf",
    "res_med_by_mslf": "res_med_by_mslf",
    "res_max_by_mslf": "res_max_by_mslf",
    "std_raking_value_by_mslf": "std_raking_value_by_mslf",
    "momentum_break_by_mslf": "momentum_break_by_mslf",
    # fundamental
    "P/L": "pl",
    "P/VP": "pvp",
    "EV / EBIT": "ev_ebit",
    "ROIC": "roic",
    "Cres. Rec (5a)": "cres_rec_5a",
    "Dív. Líquida/Valor de mercado": "div_liq_vm",
    "avaliacao_fundamentalista": "avaliacao_fundamentalista",
    # ranking
    "distortion_ranking": "distortion_ranking",
}


class _Encoder(json.JSONEncoder):
    """Fallback do json.dumps para tipos numpy/pandas que ele nao conhece."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            v = float(obj)
            return None if math.isnan(v) else v
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


def _converte_celula(valor):
    """Converte um valor de célula do DataFrame para tipo JSON nativo.

    Trata explicitamente NaN aqui porque `json.dumps` por padrão serializa
    NaN como literal `NaN` (JSON inválido). E numpy ints/floats não passariam
    sem o encoder; convertendo aqui o JSON resultante já fica limpo,
    aliviando o encoder.
    """
    if valor is None:
        return None
    # numpy antes de float/int/bool porque np.float64 herda de `float` (e
    # np.bool_ herda de int em algumas versoes) — checar a base nativa
    # primeiro deixaria escapar.
    if isinstance(valor, np.floating):
        v = float(valor)
        return None if math.isnan(v) else v
    if isinstance(valor, np.integer):
        return int(valor)
    if isinstance(valor, np.bool_):
        return bool(valor)
    if isinstance(valor, float):
        return None if math.isnan(valor) else valor
    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()
    return valor


def _ticker_dict(row, mapping):
    """Constrói `{chave_json: valor}` para uma linha do `merged_results`.

    Campos ausentes na linha viram `None` (campo presente com valor `null`,
    nunca key omitida — invariante do JSON Contract).
    """
    saida = {}
    for col_origem, chave_json in mapping.items():
        if col_origem in row.index:
            saida[chave_json] = _converte_celula(row[col_origem])
        else:
            saida[chave_json] = None
    return saida


def _portfolio_dict(portfolio_signals):
    """Quebra o `portfolio_signals` (top ++ bottom concatenados) em
    `{longs: [...], shorts: [...]}`.

    Semantica do `distortion_ranking`: valor ALTO = preco esticado acima das
    medias + fundamentalista fraca -> pressao vendedora -> shorts. Valor
    BAIXO = preco descontado + fundamentalista forte -> pressao compradora
    -> longs. Por isso a primeira metade (nlargest) vira `shorts` e a
    segunda (nsmallest) vira `longs`.

    `distorted_price_analysis` devolve `nlargest(5)` ++ `nsmallest(5)`; em
    universos pequenos isso duplica linhas (preservado do legado). Aqui só
    partimos ao meio.
    """
    if portfolio_signals.empty:
        return {"longs": [], "shorts": []}

    metade = len(portfolio_signals) // 2
    shorts_df = portfolio_signals.iloc[:metade]
    longs_df = portfolio_signals.iloc[metade:]

    def serializa(df):
        return [
            {
                "ticker": _converte_celula(row["Ticker"]),
                "subsetor": _converte_celula(row["Subsetor"]),
                "distortion_ranking": _converte_celula(row["Major->Long"]),
                "pct_to_mma10": _converte_celula(row["%_to_MMA10"]),
            }
            for _, row in df.iterrows()
        ]

    return {"longs": serializa(longs_df), "shorts": serializa(shorts_df)}


def constroi_payload(run_result):
    """Monta o dict que vira o `latest.json` a partir do `RunResult`."""
    merged = run_result.merged_results

    tickers = {
        row["Ticker"]: _ticker_dict(row, COLUNA_PARA_JSON)
        for _, row in merged.iterrows()
    }

    summary = {k: _converte_celula(v) for k, v in run_result.summary.items()}

    return {
        "schema_version": run_result.schema_version,
        "run_id": run_result.run_id,
        "generated_at": run_result.generated_at,
        "robusta_version": run_result.robusta_version,
        "input_universe": list(run_result.input_universe),
        "summary": summary,
        "portfolio_signals": _portfolio_dict(run_result.portfolio_signals),
        "tickers": tickers,
        "warnings": list(run_result.warnings),
        "failed_tickers": list(run_result.failed_tickers),
    }


def _escreve_atomico(caminho, escritor):
    """Escreve via tmp + replace (rename atômico no Linux).

    `escritor` é uma função que recebe o path do tmp e escreve nele.
    """
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    escritor(tmp)
    tmp.replace(caminho)


def _execucao_degenerada(run_result):
    """True quando a execução não tem dados suficientes pra ser publicada.

    Critérios (do JSON Contract): `tickers_ok == 0` ou taxa de falha > 50%.
    """
    ok = run_result.summary.get("tickers_ok", 0) or 0
    fail = run_result.summary.get("tickers_failed", 0) or 0
    total = ok + fail
    if total == 0 or ok == 0:
        return True
    return (fail / total) > 0.5


def _grava_json(caminho, payload):
    _escreve_atomico(
        caminho,
        lambda p: p.write_text(
            json.dumps(payload, cls=_Encoder, ensure_ascii=False, indent=2),
            encoding="utf-8",
        ),
    )


def grava_latest(run_result, pasta_var):
    """Escreve `latest.json` + `latest.xlsx` atomicamente em `pasta_var`.

    Em execução degenerada (`tickers_ok == 0` ou taxa de falha > 50%):
    `latest.json` **não** é sobrescrito (preserva a run anterior boa); o
    payload da run ruim vai para `last_failed_run.json` para diagnóstico e a
    função levanta `RuntimeError` (o cron registra o exit code != 0).
    """
    pasta_var = Path(pasta_var)
    pasta_var.mkdir(parents=True, exist_ok=True)

    payload = constroi_payload(run_result)

    if _execucao_degenerada(run_result):
        caminho_falho = pasta_var / "last_failed_run.json"
        _grava_json(caminho_falho, payload)
        raise RuntimeError(
            f"Execucao degenerada: tickers_ok={run_result.summary.get('tickers_ok')}, "
            f"tickers_failed={run_result.summary.get('tickers_failed')}. "
            f"latest.json NAO sobrescrito; payload em {caminho_falho}"
        )

    caminho_json = pasta_var / "latest.json"
    caminho_xlsx = pasta_var / "latest.xlsx"

    _grava_json(caminho_json, payload)
    _escreve_atomico(
        caminho_xlsx,
        lambda p: run_result.merged_results.to_excel(p, index=False),
    )
    logger.info("latest.json e latest.xlsx atualizados em %s", pasta_var)
