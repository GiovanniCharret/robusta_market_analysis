# ROBUSTA

Screener da B3 que combina análise técnica e fundamentalista para gerar sinais
de long/short. Pipeline em Python; dashboard estático servido via GitHub Pages
e atualizado 3×/dia pelo GitHub Actions.

🌐 **Live**: https://giovannicharret.github.io/robusta_market_analysis/
⚙️ **Pipeline**: [![status](https://github.com/GiovanniCharret/robusta_market_analysis/actions/workflows/run-pipeline.yml/badge.svg)](https://github.com/GiovanniCharret/robusta_market_analysis/actions/workflows/run-pipeline.yml)

## O que faz

1. **Análise técnica** — baixa OHLCV do Yahoo Finance para os tickers líquidos da B3,
   calcula MMAs (9, 10, 26, 50, 150, 200), volatilidade anualizada, persistência de
   volume e níveis de suporte/resistência por concentração de preço.
2. **Análise fundamentalista** — raspa o Fundamentus (cache mensal), recalcula
   indicadores dependentes de preço (P/L, P/VP, Dív.Líquida/VM), rankeia em decis
   por setor e produz um score 4–40 com sinal `compra` / `venda` / `neutro`.
3. **Distortion ranking** — combina o score fundamentalista invertido com a
   distância às MMAs 10/50 e produz um ranking cross-sectional. Os 5 maiores
   viram **shorts** (pressão vendedora); os 5 menores viram **longs** (pressão
   compradora).

A saída final é um `latest.json` único que o frontend consome via `fetch`.
O dashboard (`index.html`) mostra os top/bottom signals; cada ticker tem uma
página de drill-down (`ticker.html?ticker=XXXX`) com avaliação fundamentalista,
régua de suporte/preço/resistência e cruzamento com a carteira pessoal.

## Como rodar localmente

Pré-requisito: Python 3.13.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Executar o pipeline

```bash
# universo completo (79 tickers — 5 a 10 min, faz chamadas de rede)
python -m robusta run --emit-latest site/data

# subset pra dev/debug (mais rápido, menos risco de rate-limit)
python -m robusta run --tickers PRIO3 ASAI3 LREN3 --emit-latest site/data

# forçar raspagem do Fundamentus fora do 1º dia útil
python -m robusta run --refresh-fundamentos --emit-latest site/data
```

### Servir o site

```bash
python -m http.server 8000 --directory site
# abrir http://localhost:8000/
```

### Rodar os testes

```bash
pytest                            # bateria completa (122 testes, sem rede)
pytest tests/test_persistence.py  # módulo específico
```

## Deploy automatizado

Tudo via GitHub Actions + Pages — sem servidor próprio.

- **Workflow**: [`.github/workflows/run-pipeline.yml`](.github/workflows/run-pipeline.yml)
- **Cron**: seg–sex em `12:30`, `16:00` e `21:30` UTC (= `09:30`, `13:00` e `18:30` BRT).
- O bot `github-actions[bot]` commita `site/data/latest.json` e `site/data/latest.xlsx`
  na `main` após cada execução.
- GitHub Pages republica o `site/` em ~1 min após o commit.
- Triggers manuais via **Actions → "ROBUSTA pipeline (3x/dia)" → "Run workflow"**.

## Estrutura do repositório

```
robusta/              # pacote Python — código do pipeline
  config.py           # versão, janelas, caminhos, calendário
  data.py             # IO: Excel, Yahoo, Fundamentus
  technical.py        # análise técnica (T1–T7)
  fundamental.py      # análise fundamentalista (F1–F10)
  pipeline.py         # orquestrador + RunResult
  persistence.py      # serialização latest.json/.xlsx
  cli.py              # entrypoint `python -m robusta run`

site/                 # frontend estático (HTML + CSS + JS vanilla)
  index.html          # dashboard com longs/shorts
  ticker.html         # drill-down por ticker
  assets/             # app.js, app.css
  data/               # latest.json, latest.xlsx, carteira.json

tests/                # pytest (sem rede; usa fixtures sintéticos)
planning/             # PLAN, ADVERSARIAL_REVIEW, mockups
scripts_antigos/      # snapshot histórico do monolito legado (read-only)
```

## Carteira pessoal

Edite `site/data/carteira.json` à mão para listar seus papéis:

```json
{ "tickers": ["LREN3", "ASAI3", "GOAU4", "PRIO3", "KBLN11", "POMO4"] }
```

O frontend cruza com `latest.json` em runtime para popular a tabela "Carteira"
do drill-down e marca o ticker buscado com um pin "● na carteira" quando aplicável.

## Convenções

- **Ticker base** (`PRIO3`, sem `.SA`) é o formato interno do projeto. O sufixo
  `.SA` só aparece dentro de `data.baixa_cotacoes_yahoo`, isolado da lógica de
  negócio.
- **Universo** vem exclusivamente de `lista_tickers_liquidos.xlsx` — não há
  override embutido no código.
- **Fundamentus** é raspado apenas no 1º dia útil do mês (cache em
  `all_ticker_financial_indicators.xlsx`) ou quando `--refresh-fundamentos` é
  passado.
- **Testes não tocam a rede**: usam OHLCV CSV fixtures + HTML do Fundamentus
  em `tests/fixtures/`.

## Limitações conhecidas

- **Rate limit do Yahoo Finance**: rodando do IP do GitHub Actions (datacenter),
  Yahoo pode rate-limitar mais que de IPs residenciais. Há retry com backoff
  exponencial, mas runs podem falhar parcialmente em horários ruins.
- **Sem histórico de runs**: cada execução sobrescreve `latest.json`. O histórico
  vive apenas no `git log` dos commits do bot.
- **Sem testes de UI automatizados**: o frontend tem só checagens de sintaxe JS
  e presença de placeholders. Mudanças visuais exigem validação humana no
  navegador.
- **Sem autenticação**: o site é público (uso pessoal), sem login. A carteira
  fica visível no JSON do repo.

## Documentação adicional

- [`CLAUDE.md`](CLAUDE.md) — contexto técnico do projeto (arquitetura, convenções,
  bugs do legado já corrigidos).
- [`planning/PLAN.md`](planning/PLAN.md) — plano de rebuild fase a fase.
- [`planning/ADVERSARIAL_REVIEW.md`](planning/ADVERSARIAL_REVIEW.md) — análise
  adversarial do plano.

## Disclaimer

Ferramenta de análise quantitativa **pessoal**. Não é recomendação de investimento.
Os sinais são resultado de fórmulas mecânicas sobre dados públicos do Yahoo Finance
e Fundamentus; não levam em conta notícias, eventos corporativos, contexto macro
ou perfil de risco do investidor. Use por sua conta e risco.
