# Repository Guidelines

## Project Structure & Module Organization

ROBUSTA is currently a single-file Python application. The active runtime code is in `main.py`; treat it as the source of truth for the current screener, scheduler, Excel inputs, and Excel output. Planning material lives in `planning/`, while `docs/` is reserved for technical documentation. `scripts_antigos/` contains historical snapshots only and should not be edited or used as live code. Root Excel files such as `lista_tickers_liquidos.xlsx` and `all_ticker_financial_indicators.xlsx` are runtime data inputs.

## Build, Test, and Development Commands

Create and activate a virtual environment before installing dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install yfinance requests beautifulsoup4 numpy pandas tqdm
python main.py
```

`python main.py` runs the full screener flow, including network calls to Yahoo Finance and Fundamentus and writing the generated portfolio Excel file. There is no checked-in build system, package metadata, or lockfile yet.

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation. Prefer small, named functions over expanding the current top-level flow. Keep existing Portuguese domain names when extending current logic, for example `ler_todos_tickers`, `gere_df_principal`, and `avaliacao_fundamentalista`. Use lowercase snake_case for functions and variables, uppercase only for constants. Avoid broad refactors unless they are part of the planned modular rebuild.

## Testing Guidelines

No automated test suite is currently present. When adding tests, use `pytest` and place them under `tests/` with names like `test_technical.py` or `test_pipeline.py`. Mock network calls to `yfinance` and Fundamentus; tests should use tiny fixtures instead of live market data. For changes to ranking or indicator logic, include at least one deterministic DataFrame fixture that verifies expected columns and scores.

## Commit & Pull Request Guidelines

Recent history uses short Portuguese commit messages, for example `commit inicial` and `atualizacoes do plano`. Continue with concise, imperative summaries in Portuguese or English, but keep one language per PR. Pull requests should describe the user-visible behavior changed, list commands run, mention any live-data assumptions, and link the relevant planning item when working from `planning/PLAN.md`.

## Security & Configuration Tips

Do not commit credentials or tokens. Move Twilio and future API secrets to environment variables before re-enabling integrations. Be careful with generated Excel/JSON outputs: confirm whether they are reproducible artifacts or project data before committing them.

## Agent-Specific Instructions

Follow `BEHAVIORAL_GUIDELINES.md`: make surgical changes, prefer simple fixes, and surface uncertainty early. Preserve analytical methodology unless the task explicitly asks to change it.
