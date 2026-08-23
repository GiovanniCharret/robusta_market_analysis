# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**ROBUSTA** is a personal Brazilian stock market screener. It combines technical and fundamental analysis of B3-listed stocks into a single cross-sectional `distortion_ranking` that produces long/short signals. Version is the single source `robusta/config.py:VERSION` (currently `"13"`).

The whole system is: a Python package (`robusta/`) that emits one `latest.json`, a static frontend (`site/`) that fetches it, and two GitHub Actions workflows that run the pipeline 3×/day and republish the site. **There is no server, no API, no database, and no run history** — each run overwrites `latest.json`; the history lives only in the bot's commits on `main`.

Live site: https://giovannicharret.github.io/robusta_market_analysis/

The modular rebuild described in `planning/PLAN.md` is **complete** (phases 1–7 all `[x]`, deployment shipped). The legacy monolith `main.py` and the `scripts_antigos/` snapshot have both been **deleted from the repo** — if you see references to them in `README.md`, `AGENTS.md`, or `planning/`, those documents are stale; `robusta/` is the only live code.

## Commands

Dev box is Windows/PowerShell; CI is `ubuntu-latest` on Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Pipeline

```bash
python -m robusta run                                   # universo completo, sem gravar nada
python -m robusta run --emit-latest site/data           # o que o CI roda: grava latest.json + latest.xlsx
python -m robusta run --tickers PRIO3 ASAI3 --emit-latest site/data   # subset dev/debug
python -m robusta run --export-xlsx saida.xlsx          # export ad-hoc do merged
python -m robusta run --refresh-fundamentos             # ignora o gate mensal do Fundamentus
python -m robusta run --debug-fundamentos               # traceback/URL/colunas por ticker (implica --refresh)
```

`--emit-latest` sem argumento grava em `~/robusta/var/`; com argumento usa o caminho. Todo `run` faz chamadas de rede reais (Yahoo Finance + Fundamentus) e pode sofrer rate-limit; o universo completo (~79 tickers) leva 5–10 min.

### Testes

```bash
pytest                                                  # 122 testes, nenhum toca a rede
pytest tests/test_persistence.py                        # um módulo
pytest tests/test_data.py::test_eh_primeiro_dia_util_do_mes   # um teste
```

`pytest` da raiz é a **única** evidência de verificação aceita — REPL e scripts descartáveis não contam. `tests/test_frontend.py` chama `node --check site/assets/app.js`, então precisa de Node no PATH.

### Site local

```bash
python -m http.server 8000 --directory site   # abrir http://localhost:8000/
```

## Architecture

### Fluxo de dados (uma passada, sem estado global)

```
lista_tickers_liquidos.xlsx
        │
        ▼
technical.screener ──► (carteira_automatica, precos_por_ticker: Dict[str, float])
        │                                    │
        │                                    ▼ (handoff explícito, ticker base sem .SA)
        │              data.carrega_fundamentos ──► fundamental.varre_lista (scrape)
        │                        │                  ou all_ticker_financial_indicators.xlsx (cache)
        │                        ▼
        │              fundamental.adicione_indicadores_e_ranking (F3→F8)
        │                        │
        ▼                        ▼
        merge on "Ticker" (how="left")
                    │
                    ▼
        pipeline.distorions_analysys  ──► + ranking cross-sectional, {média, std_vol}
                    │
                    ▼
        pipeline.distorted_price_analysis ──► nlargest(5) ++ nsmallest(5)
                    │
                    ▼
                RunResult ──► persistence.grava_latest ──► latest.json + latest.xlsx
                                                                  │
                                                                  ▼
                                                   site/assets/app.js (fetch ./data/latest.json)
```

### Módulos

| Módulo | Responsabilidade |
|---|---|
| `robusta/config.py` | `VERSION`, `MMA_WINDOWS = (9,10,26,50,150,200)`, `VOL_WINDOW = 30`, `HISTORICO_ANOS = 2`, caminhos Excel, URL do Fundamentus, `eh_primeiro_dia_util_do_mes` |
| `robusta/data.py` | **Única fronteira de IO**: Excel, Yahoo (com backoff em `YFRateLimitError`), HTTP do Fundamentus, e o gate de cache mensal |
| `robusta/technical.py` | T1–T7: variação, MMAs, volatilidade anualizada, volume persistente, níveis `*_by_mslf`, `extrai_cotacoes`, `screener` |
| `robusta/fundamental.py` | F1–F10: scrape/parse, indicadores recalculados por preço, rankings decil (`_classe_decil`), `avaliacao_fundamentalista`, sinal `Fundamental_?value`, `varre_lista` |
| `robusta/pipeline.py` | `distorions_analysys`, `distorted_price_analysis`, dataclass `RunResult`, orquestrador `executa_pipeline` |
| `robusta/persistence.py` | `COLUNA_PARA_JSON`, encoder numpy/pandas → JSON nativo, escrita atômica, guarda de execução degenerada |
| `robusta/cli.py` + `__main__.py` | `python -m robusta run` com as 5 flags acima |

### Semântica do sinal (fácil de inverter por engano)

`distortion_ranking = (avaliacao_fundamentalista - 40) * -1 + %_to_MMA50_Categoria * 4 + %_to_MMA10_Categoria * 1`

Valor **alto** = preço esticado + fundamento fraco → **shorts**. Valor **baixo** = preço descontado + fundamento forte → **longs**. Por isso `persistence._portfolio_dict` mapeia a primeira metade (`nlargest`) para `shorts` e a segunda (`nsmallest`) para `longs`, enquanto a coluna renomeada continua se chamando `Major->Long` (nome herdado do legado — não é indicação de direção). Em universos pequenos as duas metades se sobrepõem; comportamento preservado do legado.

### Persistência e guardas

- Escrita atômica: `<arquivo>.tmp` + `Path.replace`, para o Pages nunca servir arquivo pela metade.
- **Execução degenerada** (`tickers_ok == 0` ou taxa de falha > 50%): `latest.json` **não** é sobrescrito; o payload ruim vai para `last_failed_run.json` (gitignored) e `grava_latest` levanta `RuntimeError`, fazendo o job do Actions falhar.
- **Fail-fast em `adicione_indicadores_e_ranking`**: DataFrame de fundamentos vazio levanta `RuntimeError` com mensagem clara, em vez do `KeyError` críptico 100 frames adiante.
- `carrega_fundamentos` raspa quando: `forcar_raspagem=True`, **ou** é o 1º dia útil do mês, **ou** o cache não existe/está vazio (auto-recuperação).

### JSON Contract (`latest.json`, `schema_version: 1`)

Chaves de topo: `schema_version`, `run_id` (ISO com `:` trocado por `-`), `generated_at`, `robusta_version`, `input_universe`, `summary` (`tickers_ok`, `tickers_failed`, `vol_media`, `vol_std`), `portfolio_signals` (`{longs, shorts}`), `tickers` (dict indexado por ticker, todos os campos técnicos+fundamentais em snake_case ASCII via `persistence.COLUNA_PARA_JSON`), `warnings`, `failed_tickers`.

Convenções: `NaN`/`None` → `null` (a chave sempre existe, nunca é omitida); `pandas.Timestamp` → ISO 8601; `numpy.int64/float64/bool_` → nativos. As sentinelas `"Abismo"`/`"Foguete"` dos níveis `*_by_mslf` permanecem strings e o frontend tem tratamento específico para elas. Definição completa em `planning/PLAN.md > JSON Contract`.

**Limitação conhecida**: `Setor` sai `null` no `merged_results` — `rankeando_empresas` (F7) faz `groupby('Setor').apply().reset_index(drop=True)` e o pandas descarta a coluna do groupby. `Subsetor` está OK e é o que o dashboard usa. Não é bug a corrigir sem pedido.

### Frontend (`site/`)

HTML + CSS + JS vanilla, sem framework, sem build step, sem npm. `assets/app.js` faz `fetch("./data/latest.json")` e `fetch("./data/carteira.json")` (caminhos **relativos** — o site vive num subpath do GitHub Pages) e expõe tudo em `window.ROBUSTA`. `index.html` é o dashboard long/short; `ticker.html?ticker=XXXX` é o drill-down (navegação full-page por URL, sem SPA). `site/data/carteira.json` (`{"tickers": [...]}`) é editado à mão e cruzado com `latest.json` em runtime.

**O assistant não consegue ver o site renderizado.** Os testes cobrem sintaxe JS e presença de placeholders; validação visual é responsabilidade do usuário. Dizer "está pronto" sem passe visual do usuário é meia-verdade.

### Deploy (GitHub Actions + Pages — não há VPS)

- `.github/workflows/run-pipeline.yml`: cron seg–sex `12:37`, `16:13`, `21:43` UTC (= 09:37 / 13:13 / 18:43 BRT; minutos primos evitam a fila do Actions em horário redondo) + `workflow_dispatch`. Roda `python -m robusta run --emit-latest site/data` e o `github-actions[bot]` commita `site/data/latest.json` + `latest.xlsx` na `main`.
- `.github/workflows/deploy-pages.yml`: publica `site/` no Pages. Dispara em `push` para `site/**` **e** via `workflow_run` após o pipeline — esse segundo trigger é necessário porque commits feitos com o `GITHUB_TOKEN` não disparam workflows por design do GitHub.
- `site/data/latest.json` e `latest.xlsx` são **versionados de propósito** (o `.gitignore` documenta isso). Rodar `--emit-latest site/data` localmente os sobrescreve e suja o working tree.

### Gotcha operacional: Fundamentus bloqueia IPs de datacenter

Diagnóstico confirmado em `planning/falha_cron.md`: o mesmo código raspa 79/79 tickers de um IP residencial brasileiro e falha 79/79 do runner do GitHub Actions (anti-bot por ASN). Mitigações já aplicadas: User-Agent realista em `data._HEADERS_FUNDAMENTUS`, fail-fast com DF vazio, flag `--debug-fundamentos`. Se um run do CI falhar no scrape, esse documento tem as opções de plano-B — não re-diagnostique do zero.

## Input files

| Arquivo | Papel |
|---|---|
| `lista_tickers_liquidos.xlsx` | **Única** fonte do universo (~79 tickers). Não há lista embutida no código |
| `all_ticker_financial_indicators.xlsx` | Cache mensal do Fundamentus; sobrescrito quando o gate de raspagem abre |
| `site/data/carteira.json` | Carteira pessoal, editada à mão |

Os nomes de coluna do cache real trazem mojibake herdado (`Nro. A��es`, `D�v. L�quida`) — é esperado, não "conserte" sem pedido.

## Convenções

- **Ticker base** (`PRIO3`, sem `.SA`) é o formato interno. O sufixo `.SA` só aparece dentro de `technical.extrai_cotacoes` / `data.baixa_cotacoes_yahoo`.
- **Nomes de domínio em português** (`crie_medias_moveis`, `avaliacao_fundamentalista`, `varre_lista`) e docstrings em português. Mantenha ao estender. `snake_case` para funções/variáveis, `UPPER_CASE` só para constantes.
- **Sem estado global**: o handoff técnica→fundamental é o argumento explícito `precos_por_ticker`.
- **Testes não tocam a rede**: use as fixtures em `tests/fixtures/` (OHLCV CSVs de PRIO3/ASAI3/LREN3 com 260 sessões, HTML do Fundamentus, `latest_mock.json`) ou injete o downloader/scraper (padrão de `carrega_fundamentos(raspar_fn=...)`).
- **Fronteira bug vs metodologia**: nomes de indicadores, pesos, thresholds e janelas **nunca** mudam sem pedido explícito. Só corrija o que o legado claramente pretendia fazer. Invariantes em `planning/PLAN.md > Fronteira bug vs metodologia`.
- Commits: sumários curtos e imperativos, uma língua por PR. Não confunda seus commits com os do bot (`bot: update latest (...)`), que dominam o `git log`.

## Bugs do legado já corrigidos (não reintroduzir)

Todos corrigidos em `robusta/`; `tests/baseline/COLUMN_SCHEMA.md` codifica o layout de colunas que o rebuild teve de reproduzir fielmente.

- Override hardcoded do universo (`{'ticker':['PRIO3','ASAI3','LREN3']}`) → `data.ler_lista_tickers` é a única fonte.
- Lógica de cache **invertida** (raspava todo dia menos o 1º) → `carrega_fundamentos` raspa só no 1º dia útil (+ flags/fallback).
- `YFRateLimitError` não importado → importado, com backoff exponencial.
- `send_whatsapp_messages` + credenciais Twilio em texto plano → removidos por completo.
- `yfinance.download('GOAU3')` de debug em todo ticker → removido.
- **B1**: as 8 colunas `*_by_mslf` atribuídas com `:` (anotação) em vez de `=` — a função devolvia DataFrame sem elas.
- **B2**: `formatar_tabela` renomeava `Papel` → `ticker` minúsculo, mas o merge usava `Ticker`.
- `.fillna(0)` sem atribuição nos rankings (resultado descartado, NaN vazava para o score).
- `pandas.qcut` sem `duplicates='drop'` → estourava em universos com empates; hoje via `_classe_decil`.
- `pandas.concat` dentro do loop de `varre_lista` → acumula em lista e concatena uma vez.
- Fórmula do `distortion_ranking`: continuação de linha quebrada (as parcelas de MMA eram statements soltos e descartados) + copy-paste de `%_to_MMA50_Categoria` na parcela que deveria usar `%_to_MMA10_Categoria`. Ambos corrigidos por decisão explícita do usuário.

## Hierarquia de documentos

- `CLAUDE.md` — fatos do repo, arquitetura, estado atual (este arquivo).
- `BEHAVIORAL_GUIDELINES.md` — processo: mudanças cirúrgicas, simplicidade, surfacing de incerteza. Leia antes de mudanças não triviais.
- `planning/PLAN.md` — plano de rebuild fase a fase, JSON Contract completo, invariantes de metodologia.
- `planning/falha_cron.md` — pós-mortem do bloqueio do Fundamentus no CI.
- `planning/ADVERSARIAL_REVIEW.md` — análise adversarial do plano.
- `README.md` — visão pública do projeto (menciona `scripts_antigos/`, que já não existe).
- `AGENTS.md` — **desatualizado**: descreve o projeto como script único `main.py`. Vale só pelas seções de estilo e convenções de commit/PR.
- `planning/REVIEW.md` — pitch executivo antigo (fala de FastAPI e scheduler que não existem mais).
