# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**ROBUSTA** is a Brazilian stock market screener and decision system. It combines technical and fundamental analysis of B3-listed stocks to generate trading signals. Version is the single source `robusta/config.py:VERSION`.

The repo is currently in a **modular rebuild** of an older monolithic script. The runnable code lives in the `robusta/` package; the legacy `main.py` has already been removed from the repo root, and a frozen snapshot is kept at `scripts_antigos/main.py` purely as historical reference (do **not** edit it, and don't treat its symbols as live).

The rebuild is tracked phase by phase in `planning/PLAN.md`. **Phases 1–6 are complete** — `config`, `data`, full technical analysis (T1–T7), full fundamental analysis (F1–F10), the consolidated pipeline + `RunResult`, and the JSON/XLSX persistence layer. **Phase 7 (static frontend) is in progress.** Phase 8 (cron + VPS deployment) follows. When changing analytical behavior, work in `robusta/`.

Adjacent files worth knowing about:
- `scripts_antigos/main.py` — historical snapshot of the old monolith. Read-only reference. Do not edit, do not include in greps for live symbols.
- `planning/` — all project documentation: `PLAN.md` (modular rebuild plan with per-phase checkboxes), `PROJECT_BUILDING.md` (meta-plan/setup checklist), `ADVERSARIAL_REVIEW.md` (adversarial gap analysis of the plan), `architecture-static-first.html` + `dashboard-v1-mockup.html` (approved frontend mockups), `implementation-plan.html` (rendered plan), and `html-effectiveness/` (HTML design references).
- `site/` — static frontend (HTML + CSS + vanilla JS) being built in Phase 7; served by nginx in production.
- `tests/` — pytest suite covering the rebuild only. `tests/baseline/COLUMN_SCHEMA.md` is the static column-by-column baseline of the legacy flow that the rebuild must reproduce; `tests/fixtures/` holds deterministic synthetic OHLCV CSVs (PRIO3/ASAI3/LREN3, 260 sessions each), a minimal Fundamentus HTML, and `latest_mock.json` for frontend iteration — so tests never touch the network.
- `docs/` — reserved for technical documentation; currently empty.

All planning documents live under `planning/`. `BEHAVIORAL_GUIDELINES.md` is a critical document for how to make changes (surgical, simple, surface uncertainty).

### Document hierarchy

Four instruction documents coexist; when guidance overlaps, they apply at different scopes:
- `CLAUDE.md` — repo facts, architecture, current state (this file).
- `BEHAVIORAL_GUIDELINES.md` — process: how to make changes (surgical, simple, surface uncertainty).
- `planning/PLAN.md` — scope: the approved modular-rebuild work and its phase checkboxes; **always read it before starting a rebuild phase**.
- `AGENTS.md` — repo-guidelines variant (structure, build commands, style, commit/PR conventions); overlaps with this file but adds commit/PR and testing conventions.

## Running the project

Environment setup (PowerShell — this is a Windows dev box; the production target is a Linux VPS):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` pins the rebuild's dependency surface (yfinance, requests, beautifulsoup4, lxml, numpy, pandas, openpyxl, tqdm, fastapi, uvicorn, pytest). FastAPI/uvicorn are vestigial — the architecture pivoted to static files served by nginx; they're not used today and may be pruned later. `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, `runs/` and `runs_test/` are gitignored.

Run the pipeline via the CLI:

```bash
python -m robusta run                              # roda a lista inteira do Excel
python -m robusta run --tickers PRIO3 ASAI3        # subconjunto dev/debug
python -m robusta run --export-xlsx saida.xlsx     # export ad-hoc do merged
python -m robusta run --refresh-fundamentos        # força raspagem do Fundamentus
python -m robusta run --emit-latest                # grava latest.json + latest.xlsx em ~/robusta/var/
python -m robusta run --emit-latest PASTA          # grava em PASTA
```

`run` executes `pipeline.executa_pipeline` end-to-end. The default universe is the full `lista_tickers_liquidos.xlsx`; `--tickers` is a dev/debug override (the legacy had this hardcoded as a bug — see "Known issues"). Fundamentus is scraped only on the 1st business day of the month unless `--refresh-fundamentos` is passed. This makes **real** network calls (Yahoo Finance + Fundamentus) and can hit rate limits.

`--emit-latest` is what the production cron will invoke: it writes `latest.json` + `latest.xlsx` atomically via `robusta.persistence.grava_latest`.

Run the test suite:

```bash
pytest                                              # all tests
pytest tests/test_data.py::test_eh_primeiro_dia_util_do_mes   # one test
```

Tests cover `robusta/` only — there are no tests against `scripts_antigos/main.py`.

## Architecture

### Package layout

`robusta/` contains:

- `robusta/config.py` — single source of `VERSION`, MMA windows (`MMA_WINDOWS = (9,10,26,50,150,200)`), `VOL_WINDOW = 30`, `HISTORICO_ANOS = 5`, Excel paths, `PASTA_RUNS`, Fundamentus base URL, and the `eh_primeiro_dia_util_do_mes` calendar helper.
- `robusta/data.py` — sole IO boundary: `ler_lista_tickers`, `ler_fundamentos_cache`, `baixa_cotacoes_yahoo` (with exponential-backoff retry on `YFRateLimitError`), `baixa_html_fundamentus`, and `carrega_fundamentos` (scrapes only on the first business day of the month, otherwise reads the Excel cache; takes the scraper as an injected `raspar_fn` so it stays testable).
- `robusta/technical.py` — análise técnica completa (T1–T7): `crie_variacao`, `crie_medias_moveis`, `calcule_volatilidade_anualizada_std`, `alto_volume_persistente`, `add_price_concentration_levels_by_me` (cria as 8 colunas `*_by_mslf` — B1 corrigido), `extrai_cotacoes` (delega o download a `data.baixa_cotacoes_yahoo` e remove os artefatos GOAU3/prints), e `screener`. O `screener` devolve `(carteira_automatica, precos_por_ticker)`, onde `precos_por_ticker: Dict[str, float]` (ticker base → último `Close`) é o handoff que substitui o antigo global `data_cache_backtest` e alimenta a fase fundamentalista.
- `robusta/fundamental.py` — análise fundamentalista completa (F1–F10): `puxar_dados` (HTTP + parse), `formatar_tabela` (limpeza + transposição + `Papel → Ticker` maiúsculo — B2 resolvido), `gera_indicadores_extras` (recalcula P/L, P/VP, Dív.Líquida/VM consumindo `precos_por_ticker`), `rankeia_outros_indicadores_maior_melhor` / `_menor_melhor` (decil via helper `_classe_decil` com `qcut` protegido contra empates e `.fillna(0)` agora atribuído), `avaliacao_fundamentalista` (score por setor financeiro/geral), `rankeando_empresas` (melhor/pior por setor), `avaliacao_fundamentalista_analisys` (sinal `Fundamental_?value` por faixas: ≥32→1, ≤14→-1, senão 0), `adicione_indicadores_e_ranking` (orquestrador F3→F8), `varre_lista` (scraper iterativo com `pd.concat` único em vez de em loop).
- `robusta/pipeline.py` — pipeline consolidado: `distorions_analysys` (ranking cross-sectional, preserva `{média, std_vol}`), `distorted_price_analysis` (sinais top5/bottom5 — duas correções: continuação de linha e copy-paste MMA50→MMA10), a dataclass `RunResult` (`schema_version`, `run_id`, `generated_at`, `robusta_version`, `input_universe`, `summary`, `portfolio_signals`, `merged_results`, `warnings`, `failed_tickers`), e o orquestrador `executa_pipeline` que conecta técnica + fundamental + merge + ranking.
- `robusta/persistence.py` — serialização do `RunResult` em `latest.json` + `latest.xlsx`. Mapa coluna→chave JSON em `COLUNA_PARA_JSON`, encoder customizado para `numpy.int64/float64/bool_` + `pandas.Timestamp` + `NaN → null`. Escrita atômica (`<arquivo>.tmp` + `Path.replace`) garante que o nginx nunca sirva arquivo pela metade. **Guarda contra execução degenerada**: se `tickers_ok == 0` ou taxa de falha > 50%, não sobrescreve `latest.json` — grava em `last_failed_run.json` e levanta `RuntimeError`.
- `robusta/cli.py` + `robusta/__main__.py` — entrypoint `python -m robusta run`. Quatro flags: `--tickers` (dev/debug), `--export-xlsx` (ad-hoc), `--refresh-fundamentos` (bypass do gate mensal), `--emit-latest` (cron de produção).

### Pipeline flow (`pipeline.executa_pipeline`)

1. **Technical analysis** — `screener()` itera sobre os tickers líquidos, chama `extrai_cotacoes()` para cada um (baixa OHLCV do Yahoo Finance com `.SA` para B3), e pipa o DataFrame por `crie_variacao` → `crie_medias_moveis` → `calcule_volatilidade_anualizada_std` → `alto_volume_persistente` → `add_price_concentration_levels_by_me`. Devolve `(carteira_automatica, precos_por_ticker)`.
2. **Fundamental analysis** — `varre_lista()` raspa fundamentus.com.br para cada ticker (ou lê o cache mensal). `formatar_tabela()` limpa o HTML. `adicione_indicadores_e_ranking()` recalcula ratios price-dependent usando `precos_por_ticker`, classifica cada indicador em decis (1–10) com `pandas.qcut` (protegido contra empates), e produz `avaliacao_fundamentalista` + sinal `Fundamental_?value`.
3. **Merge & rank** — merge técnico+fundamental por `Ticker`. `distorions_analysys` adiciona o ranking cross-sectional e preserva `{média, std_vol}` (que o legado descartava) no `summary`. `distorted_price_analysis` produz `portfolio_signals` (top/bottom do `distortion_ranking`).
4. **Persistence (opcional, via `--emit-latest`)** — `persistence.grava_latest(run_result, pasta)` serializa o `RunResult` em `<pasta>/latest.json` (todo o universo, indexado por ticker) e `<pasta>/latest.xlsx` (`merged_results` exportado).

### Target deployment architecture

Production target (Phase 8): VPS Linux (Hostinger), domínio próprio + HTTPS via Let's Encrypt, audiência pessoal sem autenticação.

- **System cron** dispara `python -m robusta run --emit-latest --refresh-fundamentos?` 3×/dia (seg–sex, 12:30 / 16:00 / 21:30 UTC = 09:30 / 13:00 / 18:30 BRT). Sem scheduler Python permanente.
- **nginx** serve `site/` como root estático e expõe `~/robusta/var/latest.json` + `latest.xlsx` em `/data/`.
- **Frontend** (`site/`): HTML + CSS + JS vanilla, sem framework, sem build step. `index.html` mostra dashboard de top/bottom signals; `ticker.html?ticker=XXXX` é drill-down individual; `site/data/carteira.json` (editado manualmente) lista a carteira pessoal e é cruzado com `latest.json` em runtime.

Não há histórico de runs (sem `runs/<timestamp>.json`), sem symlinks, sem API Python permanente.

### JSON Contract (resumido)

`latest.json` schema (definição completa em `planning/PLAN.md > JSON Contract`):

- `schema_version` (int, atualmente `1`), `run_id` (ISO 8601 sem `:`), `generated_at`, `robusta_version`.
- `input_universe` (lista de tickers base, sem `.SA`).
- `summary` — `tickers_ok`, `tickers_failed`, `vol_media`, `vol_std`.
- `portfolio_signals` — `{longs: [...], shorts: [...]}`.
- `tickers` — dict `{TICKER: {...}}` com todos os campos (técnica + fundamental + ranking), chaves em snake_case ASCII (mapeamento em `persistence.COLUNA_PARA_JSON`).
- `warnings`, `failed_tickers`.

Convenções: `NaN`/`None` → `null` JSON (campo presente, valor `null` — nunca key omitida); `pandas.Timestamp` → ISO 8601; `numpy.int64/float64` → nativos via encoder; sentinelas `"Abismo"`/`"Foguete"` dos níveis `*_by_mslf` mantêm tipo string.

### Input files

| File | Purpose |
|---|---|
| `lista_tickers_liquidos.xlsx` | Ticker list used in daily runs (única fonte de universo) |
| `all_ticker_financial_indicators.xlsx` | Cached fundamental data refreshed on the first business day of the month |
| `site/data/carteira.json` (futuro / Fase 7d) | Carteira pessoal `{tickers: [...]}` editada manualmente |

### Ticker conventions

- Internal ticker format: `PRIO3`, `LREN3` (sem `.SA`).
- Yahoo Finance format: `PRIO3.SA` (anexado em `extrai_cotacoes` antes do download).
- Fundamentus scraping usa o ticker base direto.
- Handoff técnica → fundamentalista: `Dict[str, float]` com ticker base → último `Close` (sem `.SA`).

## Phase status (mirror `planning/PLAN.md` — keep both in sync)

- Phase 1 — baseline (column schema + fixtures + conftest) ✅ done
- Phase 2 — `robusta/config.py` + `robusta/data.py` ✅ done
- Phase 3 — análise técnica T1–T7 ✅ done
- Phase 4 — fundamentalista F1–F10 ✅ done
- Phase 5 — pipeline consolidado + `RunResult` ✅ done
- Phase 6 — persistência `latest.json` + `latest.xlsx` ✅ done
- Phase 7 — frontend estático (sub-fases 7a–7e) 🚧 em progresso
- Phase 8 — VPS + nginx + cron — não iniciada

## Legacy bugs and fixes already in the rebuild

These bugs lived in the (now-removed) `main.py` monolith. They are documented here because (a) `scripts_antigos/main.py` still has them and may be consulted for reference, and (b) `tests/baseline/COLUMN_SCHEMA.md` codifies the legacy column layout that the rebuild had to faithfully reproduce.

All items below are **fixed in `robusta/`**:

- **Hardcoded ticker override** (legacy lines 1336–1337): `gere_df_principal` overwrote the Excel list with `{'ticker':['PRIO3','ASAI3','LREN3']}`. → `robusta.data.ler_lista_tickers` is the single source of universe.
- **Inverted cache logic** (legacy 1345–1357): scraped Fundamentus on every non-first-of-month run, loaded cache only on day 1. → `robusta.data.carrega_fundamentos` scrapes only on the 1st business day and caches; reads cache otherwise. `--refresh-fundamentos` bypasses the gate on demand.
- **`YFRateLimitError` not imported** (legacy line 261): `except` raised `NameError` on first rate-limit. → `robusta.data` imports it and applies exponential backoff.
- **`send_whatsapp_messages` + Twilio credentials**: hardcoded plaintext, `client` commented out, called at end of every run → crash. → Removed entirely from the rebuild.
- **Debug `yfinance.download('GOAU3')` in `extrai_cotacoes`**: downloaded irrelevant data on every ticker. → Dropped in T6, along with the redundant second download and the prints.
- **B1 — silent assignment in `add_price_concentration_levels_by_me`**: 8 `*_by_mslf` columns were assigned with `:` (annotation) instead of `=`, so the function silently returned a DataFrame missing them. → T5 uses `=` and asserts the 8 columns.
- **B2 — merge key mismatch**: `formatar_tabela` renamed `Papel` → `ticker` (lowercase) but `gere_df_principal` merged on `Ticker`. → F2 renames to `Ticker` (capital), standardizing across the pipeline.
- **`hora_atual` and `eh_dia_util` overrides**: hardcoded `"19:00"` and `True` made the scheduler fire on every run. → Legacy `main.py` removed; cron handles scheduling in the new architecture.
- **`.fillna(0)` without assignment** (legacy ~1085, ~1112): result discarded, NaNs leaked into `avaliacao_fundamentalista`. → F4/F5 assign the `.fillna(0)` result; F5 also covers the `neg_bloqueado` path.
- **`pandas.qcut` without dup protection**: empates rebentavam em universos pequenos. → `_classe_decil` em F4/F5 protege com `duplicates='drop'` + fallback.
- **`pd.concat` in loop in `varre_lista`**: O(n²) concat. → F10 acumula em lista e faz `concat` único.
- **Filename with leading space** `' carteira_automatica.xlsx'`: n/a — export Excel só via flag explícita.

The full list and the **invariants** that separate "bug to fix" from "methodology to preserve" live in `planning/PLAN.md > Fronteira bug vs metodologia`.

## Porting rules (active for Phases 7–8)

- **One function per phase**; keep existing return types until a later phase explicitly changes them.
- Each phase ships with a fast test using a small fixture or network mock before moving on. The only acceptable verification command is `pytest` from the repo root — REPL/scratch scripts do not count as evidence for marking a phase `[x]`.
- **Tests must not touch the network**: use the OHLCV CSV fixtures, the Fundamentus HTML fixture, and `latest_mock.json` in `tests/fixtures/`, or inject scrapers/downloaders as arguments (see `carrega_fundamentos(raspar_fn=...)` for the pattern).
- **Global state is forbidden**: the technical→fundamentalist handoff is `Dict[str, float]` mapping base ticker (no `.SA`) to last close — passed as an explicit argument (`precos_por_ticker`).
- **Fronteira bug vs metodologia**: only fix things the legacy clearly meant to do (see bug list above + invariants in `PLAN.md`). Indicator names, weights, thresholds, window sizes — never change without explicit ask.
- **Visual frontend changes (Phase 7)**: the assistant cannot see the rendered site. Automated tests cover JS syntax + file presence; **visual review is the user's responsibility** at each sub-phase 7b/7c/7d. Saying "está pronto" without a user visual pass is a meia-verdade.
