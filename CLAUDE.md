# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**ROBUSTA** is a Brazilian stock market screener and decision system (current version `13 - Reborn Stronger`, declared at `main.py:3` and `main.py:44`). It combines technical and fundamental analysis of B3-listed stocks to generate trading signals, outputting results to Excel files and (optionally) WhatsApp via Twilio.

Adjacent files worth knowing about:
- `REVIEW.md` (repo root) — short executive/marketing pitch of the project. Not technical context.
- `Scripts Antigos/main.py` — historical snapshot of `main.py`. Do **not** edit; do not treat as live code when grepping for symbols.

Toda documentação estará dentro de planning/ e @BEHAVIORAL_GUIDELINES.md é um documento crítico para a elaboração do projeto

## Running the Project


```bash
python main.py
```

There are no tests, no build steps, and no virtual environment configuration checked in. Install dependencies manually:

```bash
pip install yfinance requests beautifulsoup4 numpy pandas tqdm
```

## Architecture

The entire project lives in a single file (`main.py`), structured like a converted Jupyter notebook with markdown docstrings as section headers. Execution flows from top to bottom when run directly.

### Main flow (`gere_df_principal`)

1. **Technical analysis** — `screener()` iterates over the liquid tickers list, calling `extrai_cotacoes()` for each. That function downloads OHLCV data from Yahoo Finance (`.SA` suffix for B3 tickers), then pipes the DataFrame through:
   - `crie_variacao` → daily returns
   - `crie_medias_moveis` → MMAs (9, 10, 26, 50, 150, 200 days) and distance-to-MMA columns
   - `calcule_volatilidade_anualizada` → 30-day rolling annualized vol
   - `alto_volume_persistente` → persistent high-volume signals
   - `add_price_concentration_levels_by_me` → custom support/resistance levels

2. **Fundamental analysis** — `varre_lista()` scrapes [fundamentus.com.br](https://www.fundamentus.com.br) for each ticker. `formatar_tabela()` cleans the raw HTML tables into a tidy DataFrame. `adicione_indicadores_e_ranking()` then:
   - Recalculates price-dependent ratios (P/L, P/VP, Dív.Líquida/VM) using live prices from `data_cache_backtest`
   - Ranks each indicator into decile classes (1–10) using `pandas.qcut`
   - Produces `avaliacao_fundamentalista` (sum of class scores) and `Fundamental_?value` signal column

3. **Merge & output** — Technical and fundamental DataFrames are merged on `Ticker`. `distorions_analysys()` adds cross-sectional ranking. Results are saved to `carteira_automatica.xlsx`.

### Scheduler

The main loop polls every 30 seconds and fires analysis at `14:56` and `19:00` Brasília time (UTC-3). **Note:** `hora_atual` is currently hardcoded to `"19:00"` (debug override on line 1419) and `eh_dia_util` is hardcoded to `True` (line 1425).

### Input files

| File | Purpose |
|---|---|
| `lista_tickers_liquidos.xlsx` | Ticker list used in daily runs |
| `all_ticker_financial_indicators.xlsx` | Cached fundamental data refreshed on the first business day of the month |

### Key global state

- `data_cache_backtest` — dict mapping ticker → recent OHLCV DataFrame; populated by `extrai_cotacoes`, consumed by `gera_indicadores_extras`
- `probleminhas` — set of tickers to skip permanently
- `carteira_automatica` — accumulator DataFrame built by `screener()`

## Known issues to be aware of

A catalog of issues — including ones flagged in earlier reviews — was intended to live in `docs/CODE-AND-PLAN-REVIEW.md`, but that file does not currently exist. The only review file present today is `docs/CODEX-REVIEW.md` (currently empty). The list below is therefore the canonical short list of known issues until that catalog is restored:

- **Hardcoded ticker override (silent)**: Lines 1336–1337 of `gere_df_principal` overwrite the Excel-loaded list with `{'ticker':['PRIO3','ASAI3','LREN3']}`. Only three tickers are actually analyzed today.
- **Inverted cache logic**: Lines 1345–1357 scrape Fundamentus on every non-first-of-month run and load the cached Excel only on the first business day — the opposite of the documented intent. `all_ticker_financial_indicators.xlsx` is never refreshed.
- **`YFRateLimitError` not imported** (line 261): the `except` clause raises `NameError` the first time Yahoo rate-limits, not a retry.
- **`send_whatsapp_messages()` crashes on call** (line 1394): the Twilio `client` on line 230 is commented out, so this function raises `NameError` whenever the scheduler completes a run. In practice every run hits this path because `hora_atual` and `eh_dia_util` are both overridden (see below) — so the script always crashes at the end.
- **Hardcoded credentials**: `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are stored as plaintext strings (lines 226–227). Twilio integration is commented out but the credentials remain.
- **Debug artifact in `extrai_cotacoes`**: There is an unconditional `yfinance.download('GOAU3')` call before the retry loop (line 246) that downloads irrelevant data on every ticker.
- **Silent assignment bug in `add_price_concentration_levels_by_me`**: Lines 718–723 use `:` instead of `=` (e.g., `df["sup_min_by_mslf"]: below_vals[0]`), so those columns are never set on the DataFrame. The function also has no `return`, so callers that reassign (`df = add_price_concentration_levels_by_me(df)`) turn `df` into `None`.
- **`hora_atual` override**: Line 1419 overrides the real clock with `"19:00"`, so the scheduler fires immediately on every run regardless of actual time.
- **`.fillna(0)` without assignment** (lines ~1085, ~1112) — result discarded; NaNs leak into `avaliacao_fundamentalista`.
- **Filename with leading space** (line 1375): `to_excel(' carteira_automatica.xlsx')`.

## Ticker conventions

- Internal ticker format: `PRIO3`, `LREN3` (without `.SA`)
- Yahoo Finance format: `PRIO3.SA` (appended in `screener()` before calling `extrai_cotacoes`)
- Fundamental scraping uses the base ticker directly with the fundamentus URL

## Active rebuild plan (`docs/PLAN.md`)

There is an approved, in-progress plan to rebuild `main.py` into a modular package. `docs/PLAN.md` is the plan itself and tracks per-phase checkboxes (all currently `[ ]`). A companion critical review was planned at `docs/CODE-AND-PLAN-REVIEW.md` but is not present — the placeholder file `docs/CODEX-REVIEW.md` is empty. Key locked decisions:

- **Output**: replace Excel exports with JSON files; serve them via a local FastAPI.
- **Persistence**: each run writes a timestamped JSON and updates `latest.json`.
- **CLI**: `main.py` becomes a thin CLI (`run` / `api` / `schedule` subcommands).
- **Twilio/WhatsApp**: removed from the new flow.
- **Methodology**: analytical logic, weights, thresholds, and indicator names are preserved as-is; only bugs that block the intent of the code get fixed during porting.

### Target module structure

```
robusta/           (or a few flat .py files if simpler)
  config.py        — version, MMA windows, paths, calendar
  data.py          — Excel readers, Yahoo Finance, Fundamentus HTTP
  technical.py     — crie_variacao … screener()
  fundamental.py   — formatar_tabela … adicione_indicadores_e_ranking()
  pipeline.py      — merge, cross-sectional ranking, gere_df_principal logic
  persistence.py   — JSON serialization, run_id, latest.json
  api.py           — FastAPI endpoints (read-only by default)
main.py            — CLI entry point only
```

### Minimum FastAPI endpoints

`GET /api/health` · `GET /api/runs/latest` · `GET /api/runs` · `GET /api/runs/{run_id}` · `GET /api/tickers/{ticker}`

### Porting rules

- One function per phase; keep existing return types until a later phase explicitly changes them.
- Each phase ships with a fast test using a small fixture or network mock before moving on.
- Global state (`data_cache_backtest`, `probleminhas`, `carteira_automatica`) must become explicit pipeline arguments, not module-level side effects.
- The experimental LAB section has already been removed from the current script; the rebuild does not need to port it.
