# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**ROBUSTA** is a Brazilian stock market screener and decision system (current version `13`, single source `robusta/config.py:VERSION`; the legacy `main.py:3` / `main.py:44` still says `13 - Reborn Stronger` but diverges internally — see "Active rebuild plan"). It combines technical and fundamental analysis of B3-listed stocks to generate trading signals. The legacy script writes Excel and (optionally) WhatsApp via Twilio; the in-progress rebuild replaces both with JSON files served by a local FastAPI.

The repo currently holds **two parallel codebases**: the legacy monolith `main.py` (still the runnable artifact today) and the new `robusta/` package being built phase by phase per `planning/PLAN.md`. Phases 1–3 are complete: baseline fixtures + `robusta.config` + `robusta.data` (Fases 1–2) and the full technical analysis `robusta.technical` (Fase 3, T1–T7). Phase 4 (fundamental, F1–F10) is complete: `robusta.fundamental` cobre toda a fundamentalista (scraping → limpeza → indicadores → rankings → score → sinal → orquestração via `adicione_indicadores_e_ranking`, mais o scraper de lista `varre_lista`). Phase 5 (pipeline consolidado) is complete: `robusta.pipeline` faz o merge técnico+fundamental, o ranking cross-sectional e empacota tudo num `RunResult` via `executa_pipeline`. Next is Phase 6 (persistência JSON). When changing analytical behavior, work in `robusta/`, not `main.py`.

Adjacent files worth knowing about:
- `scripts_antigos/main.py` — historical snapshot of `main.py`. Do **not** edit; do not treat as live code when grepping for symbols.
- `planning/` — all project documentation: `PLAN.md` (modular rebuild plan with per-phase checkboxes), `PROJECT_BUILDING.md` (meta-plan / setup checklist), `ADVERSARIAL_REVIEW.md` (adversarial gap analysis of the plan), `REVIEW.md` (short executive/marketing pitch — not technical context), `CODEX-REVIEW.md` (empty placeholder), `implementation-plan.html` (rendered plan), and `html-effectiveness/` (HTML design references, a clone of github.com/ThariqS/html-effectiveness).
- `tests/` — pytest suite covering the rebuild only. `tests/baseline/COLUMN_SCHEMA.md` is the static column-by-column baseline of the legacy flow that future rebuild phases must reproduce; `tests/fixtures/` holds deterministic synthetic OHLCV CSVs (PRIO3/ASAI3/LREN3, 260 sessions each) and a minimal Fundamentus HTML — used so tests never touch the network.
- `docs/` — reserved for technical documentation; currently empty.

Toda documentação estará dentro de planning/ e @BEHAVIORAL_GUIDELINES.md é um documento crítico para a elaboração do projeto
A pasta scripts_antigos/ só tem referências a projetos antigos. Pode ser ignorada.

### Document hierarchy

Four instruction documents coexist; when guidance overlaps, they apply at different scopes:
- `CLAUDE.md` — repo facts, architecture, and known issues (this file).
- `BEHAVIORAL_GUIDELINES.md` — process: how to make changes (surgical, simple, surface uncertainty).
- `planning/PLAN.md` — scope: the approved modular-rebuild work and its phase checkboxes.
- `AGENTS.md` — repo-guidelines variant (structure, build commands, style, commit/PR conventions); overlaps with this file but adds commit/PR and testing conventions.

## Running the Project

Environment setup (PowerShell — this is a Windows repo):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` pins the rebuild's dependency surface (yfinance, requests, beautifulsoup4, lxml, numpy, pandas, openpyxl, tqdm, fastapi, uvicorn, pytest). `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, and `runs/` are gitignored.

Run the rebuilt pipeline via the minimal CLI (a Phase 8 slice pulled forward; the legacy `main.py` is left intact as reference):

```bash
python -m robusta run --tickers PRIO3 ASAI3 --export-xlsx saida.xlsx
python -m robusta run            # usa a lista de tickers do Excel
```

`run` executes `pipeline.executa_pipeline` end-to-end and (with `--export-xlsx`) writes `merged_results` to xlsx — Excel export is opt-in only, per the plan. This makes **real** network calls (Yahoo Finance + Fundamentus) and can hit rate limits.

The legacy screener:

```bash
python main.py
```

Note: legacy `main.py` does **not** run cleanly today — `YFRateLimitError` isn't imported and `send_whatsapp_messages` references a commented-out Twilio client, so a full run crashes. See "Known issues". It's kept as the reference implementation until the port finishes (Phase 8).

Run the test suite (covers `robusta/` only — the legacy `main.py` has no tests):

```bash
pytest
```

Run a single test:

```bash
pytest tests/test_data.py::test_eh_primeiro_dia_util_do_mes
```

## Architecture

### Two coexisting codebases

- **Legacy** — `main.py` is a single file structured like a converted Jupyter notebook with markdown docstrings as section headers. Execution flows top to bottom when run directly. Still the only end-to-end runnable artifact.
- **Rebuild** — `robusta/` is the modular package being grown one phase at a time. Today it contains:
  - `robusta/config.py` — single source of `VERSION`, MMA windows (`MMA_WINDOWS = (9,10,26,50,150,200)`), `VOL_WINDOW = 30`, `HISTORICO_ANOS = 5`, Excel paths, `PASTA_RUNS`, Fundamentus base URL, and the `eh_primeiro_dia_util_do_mes` calendar helper.
  - `robusta/data.py` — sole IO boundary: `ler_lista_tickers`, `ler_fundamentos_cache`, `baixa_cotacoes_yahoo` (with exponential-backoff retry on `YFRateLimitError`), `baixa_html_fundamentus`, and `carrega_fundamentos` (which fixes the legacy's inverted cache logic: scrapes only on the first business day of the month, otherwise reads the Excel cache; takes the scraper as an injected `raspar_fn` so it stays testable before Phase F10 lands).
  - `robusta/technical.py` — análise técnica completa (Fase 3 do PLAN, T1–T7): `crie_variacao` (T1), `crie_medias_moveis` (T2), `calcule_volatilidade_anualizada_std` (T3, renomeada do legado para sinalizar que a vol é via desvio-padrão simples), `alto_volume_persistente` (T4), `add_price_concentration_levels_by_me` (T5, que corrige o bug B1: as 8 colunas `*_by_mslf` agora são criadas com `=` em vez de `:`), `extrai_cotacoes` (T6, que delega o download a `data.baixa_cotacoes_yahoo` e remove os artefatos de debug GOAU3/prints) e `screener` (T7). O `screener` devolve `(carteira_automatica, precos_por_ticker)`, onde `precos_por_ticker` é o handoff `Dict[str, float]` (ticker base → último `Close`) que substitui o global `data_cache_backtest` e alimenta a fase fundamentalista.
  - `robusta/fundamental.py` — análise fundamentalista em construção (Fase 4 do PLAN, F1–F10). Hoje contém `puxar_dados` (F1, que delega o GET a `data.baixa_html_fundamentus` e parseia via `read_html`) , `formatar_tabela` (F2, que limpa/transpõe as tabelas do Fundamentus, converte números BR via `_converte_para_numero` e — resolvendo o bug B2 — padroniza a chave do papel como `Ticker` maiúsculo) , `gera_indicadores_extras` (F3, que recalcula `P/L`, `P/VP` e `Dív. Líquida/Valor de mercado` consumindo o handoff `precos_por_ticker` por ticker base, sem o global `data_cache_backtest` nem concatenação de `.SA`), `rankeia_outros_indicadores_maior_melhor` (F4, ranking em decil "maior melhor" via o helper `_classe_decil`, que protege o `qcut` contra empates; corrige também o `.fillna(0)` descartado pelo legado), `rankeia_outros_indicadores_menor_melhor` (F5, "menor melhor", unifica as duas funções do legado via o parâmetro `bloquear_negativos` que penaliza valores `<= 0` com `+1e9`), `avaliacao_fundamentalista` (F6, soma as colunas `classe ...` num score, com conjunto distinto para setores financeiros vs gerais), `rankeando_empresas` (F7, rotula `Posicao setorial` melhor/pior por `Setor`), `avaliacao_fundamentalista_analisys` (F8, gera o sinal `Fundamental_?value` por faixas do score: ≥32→1, ≤14→-1, senão 0), `adicione_indicadores_e_ranking` (F9, orquestrador que encadeia F3→F8 e remove colunas `Unnamed`) e `varre_lista` (F10, scraper que itera a lista de tickers, chama F1+F2 por ticker e consolida com `pd.concat` único). Fase 4 completa.
  - `robusta/pipeline.py` — pipeline consolidado (Fase 5 do PLAN): `distorions_analysys` (ranking cross-sectional, preserva `{média, std_vol}`), `distorted_price_analysis` (sinais top5/bottom5; a fórmula `distortion_ranking` teve dois bugs corrigidos a pedido do usuário — continuação de linha + copy-paste MMA50→MMA10), a dataclass `RunResult` e o orquestrador `executa_pipeline`. Esse é o ponto onde o fluxo completo roda de ponta a ponta (técnica + fundamental + merge + ranking).
  - `robusta/cli.py` + `robusta/__main__.py` — CLI mínima (`python -m robusta run`), fatia da Fase 8 antecipada para testes manuais. Roda `executa_pipeline` e exporta xlsx opt-in via `--export-xlsx`. A CLI completa (`run`/`api`/`schedule`) e a migração do `main.py` são da Fase 8.

The legacy file is the source of truth for *what the analysis does today*; the rebuild is the source of truth for *what the methodology will look like going forward*. Treat them as separate worlds when grepping.

### Legacy main flow (`gere_df_principal` in `main.py`)

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

These are bugs in the **legacy `main.py`**. The full intended fix list lives in `planning/PLAN.md` (sections "Key Changes" and "Fronteira bug vs metodologia"); the list below is the operational short version. Bugs marked **[fixed in rebuild]** are already addressed in `robusta/` and only remain in the legacy file.

- **Hardcoded ticker override (silent)**: Lines 1336–1337 of `gere_df_principal` overwrite the Excel-loaded list with `{'ticker':['PRIO3','ASAI3','LREN3']}`. Only three tickers are actually analyzed today. **[fixed in rebuild]** — `robusta.data.ler_lista_tickers` is the single source of universe, no embedded override.
- **Inverted cache logic**: Lines 1345–1357 scrape Fundamentus on every non-first-of-month run and load the cached Excel only on the first business day — the opposite of the documented intent. `all_ticker_financial_indicators.xlsx` is never refreshed. **[fixed in rebuild]** — `robusta.data.carrega_fundamentos` scrapes only on the 1st business day and caches; reads cache otherwise.
- **`YFRateLimitError` not imported** (line 261): the `except` clause raises `NameError` the first time Yahoo rate-limits, not a retry. **[fixed in rebuild]** — `robusta.data` imports `YFRateLimitError` and applies exponential backoff.
- **`send_whatsapp_messages()` crashes on call** (line 1394): the Twilio `client` on line 230 is commented out, so this function raises `NameError` whenever the scheduler completes a run. In practice every run hits this path because `hora_atual` and `eh_dia_util` are both overridden (see below) — so the script always crashes at the end. Removed entirely from the rebuild.
- **Hardcoded credentials**: `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are stored as plaintext strings (lines 226–227). Twilio integration is commented out but the credentials remain.
- **Debug artifact in `extrai_cotacoes`**: There is an unconditional `yfinance.download('GOAU3')` call before the retry loop (line 246) that downloads irrelevant data on every ticker. **[fixed in rebuild]** — `robusta.technical.extrai_cotacoes` (T6) drops the GOAU3 download, the redundant second download, and the prints; it delegates the download (with retry) to `data.baixa_cotacoes_yahoo`.
- **Silent assignment bug in `add_price_concentration_levels_by_me`** (B1 in `tests/baseline/COLUMN_SCHEMA.md`): Lines 718–725 use `:` instead of `=` (e.g., `df["sup_min_by_mslf"]: below_vals[0]`), so those eight `by_mslf` columns are never set on the DataFrame. The function does `return df`, so callers that reassign still get a DataFrame — just one silently missing the `by_mslf` columns. **[fixed in rebuild]** — `robusta.technical.add_price_concentration_levels_by_me` (T5) uses `=` and the 8 columns are created/asserted.
- **Merge key mismatch** (B2 in `tests/baseline/COLUMN_SCHEMA.md`): `formatar_tabela` renames `Papel` → `ticker` (lowercase), but `gere_df_principal` merges `on='Ticker'`. **[fixed in rebuild]** — `robusta.fundamental.formatar_tabela` (F2) renames `Papel` → `Ticker` (capital), standardizing the key across the whole pipeline; F3+ will read `row['Ticker']`.
- **`hora_atual` override**: Line 1419 overrides the real clock with `"19:00"`, so the scheduler fires immediately on every run regardless of actual time.
- **`.fillna(0)` without assignment** (lines ~1085, ~1112) — result discarded; NaNs leak into `avaliacao_fundamentalista`. **[fixed in rebuild]** — F4 (`rankeia_outros_indicadores_maior_melhor`) and F5 (`rankeia_outros_indicadores_menor_melhor`) both assign the `.fillna(0)` result; F5 also adds it to the `neg_bloqueado` path that lacked it.
- **Filename with leading space** (line 1375): `to_excel(' carteira_automatica.xlsx')`.

## Ticker conventions

- Internal ticker format: `PRIO3`, `LREN3` (without `.SA`)
- Yahoo Finance format: `PRIO3.SA` (appended in `screener()` before calling `extrai_cotacoes`)
- Fundamental scraping uses the base ticker directly with the fundamentus URL

## Active rebuild plan (`planning/PLAN.md`)

There is an approved, in-progress plan to rebuild `main.py` into a modular package. `planning/PLAN.md` is the plan itself and tracks per-phase checkboxes; **always read it before starting a rebuild phase** — each completed phase records the commands run, files touched, and known limitations as evidence in the checkbox. `planning/PROJECT_BUILDING.md` tracks the meta-plan (how the project scaffolding itself is being set up); `planning/ADVERSARIAL_REVIEW.md` holds an adversarial gap analysis; `planning/CODEX-REVIEW.md` is an empty placeholder.

**Phase status (mirror what's in `PLAN.md` — keep both in sync):**
- Phase 1 — baseline (column schema + fixtures + conftest) ✅ done
- Phase 2 — `robusta/config.py` + `robusta/data.py` ✅ done
- Phase 3 — análise técnica ✅ completa: T1 (`crie_variacao`), T2 (`crie_medias_moveis`), T3 (`calcule_volatilidade_anualizada_std`), T4 (`alto_volume_persistente`), T5 (`add_price_concentration_levels_by_me`, B1 corrigido), T6 (`extrai_cotacoes`), T7 (`screener`, cria o handoff `precos_por_ticker`)
- Phase 4 — fundamentalista ✅ completa: F1 (`puxar_dados`), F2 (`formatar_tabela`, B2 resolvido), F3 (`gera_indicadores_extras`, consome `precos_por_ticker`), F4 (`rankeia_outros_indicadores_maior_melhor`, fillna+qcut corrigidos), F5 (`rankeia_outros_indicadores_menor_melhor`, unifica neg_permitido/bloqueado), F6 (`avaliacao_fundamentalista`), F7 (`rankeando_empresas`), F8 (`avaliacao_fundamentalista_analisys`), F9 (`adicione_indicadores_e_ranking`), F10 (`varre_lista`)
- Phase 5 — pipeline consolidado ✅ completa: `distorions_analysys` (5a), `distorted_price_analysis` (5b, fórmula corrigida), `RunResult` + `executa_pipeline` (5c)
- Phases 6 (JSON persistence), 7 (FastAPI), 8 (CLI cleanup) — not started

Key locked decisions:

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
- Each phase ships with a fast test using a small fixture or network mock before moving on. The only acceptable verification command is `pytest` from the repo root — REPL/scratch scripts do not count as evidence for marking a phase `[x]`.
- Tests must not touch the network: use the OHLCV CSV fixtures and the Fundamentus HTML fixture in `tests/fixtures/`, or inject scrapers/downloaders as arguments (see `carrega_fundamentos(raspar_fn=...)` for the pattern).
- Global state (`data_cache_backtest`, `probleminhas`, `carteira_automatica`) must become explicit pipeline arguments, not module-level side effects. The technical→fundamentalist handoff is `Dict[str, float]` mapping base ticker (no `.SA`) to last close — see `planning/PLAN.md` "Handoff interno".
- "Fronteira bug vs metodologia": when porting, only fix things the legacy clearly meant to do (the bugs listed above). Indicator names, weights, thresholds, window sizes — never change without explicit ask. See the invariants list in `planning/PLAN.md`.
- The experimental LAB section has already been removed from the current script; the rebuild does not need to port it.
