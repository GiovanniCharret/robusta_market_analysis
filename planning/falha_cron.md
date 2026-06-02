# Falha do cron — diagnóstico confirmado (2026-06-02)

## Sintoma observado

- Site público (`giovannicharret.github.io/robusta_market_analysis/`) congelado em **2026-05-29T22:53Z** (último run com sucesso, `robusta_version: 13`, 79/79 tickers ok).
- Cron de segunda 2026-06-01 disparou 3 vezes, todas com **failure**:

  | run_id       | created_at (UTC)     | conclusion | duração |
  |--------------|----------------------|------------|---------|
  | 26773546360  | 2026-06-01T18:20:57  | failure    | ~41 s   |
  | 26779745369  | 2026-06-01T20:22:04  | failure    | ~41 s   |
  | 26787781640  | 2026-06-01T23:14:00  | failure    | ~41 s   |

- Os 3 runs ficaram **atrasados em 4–6 h** vs. os crons agendados (12:37/16:13/21:43) — fila do GitHub Actions em hora cheia.
- O `deploy-pages.yml` corretamente entrou em `skipped` (gate `workflow_run.conclusion == 'success'`).

## Causa raiz (confirmada via traceback)

Stack do run `26773546360`:

```
File "robusta/pipeline.py", line 164, in executa_pipeline
    fundamentos = fundamental.adicione_indicadores_e_ranking(
        fundamentos, precos_por_ticker
    )
File "robusta/fundamental.py", line 358, in adicione_indicadores_e_ranking
    df = rankeia_outros_indicadores_maior_melhor(df, "Cres. Rec (5a)", "ROIC")
File "robusta/fundamental.py", line 214, in rankeia_outros_indicadores_maior_melhor
    dados_financeiro_all_tickers[indicador], errors="coerce"
KeyError: 'Cres. Rec (5a)'
```

**Encadeamento:**

1. `varre_lista` (scrape do Fundamentus) entrou no `try/except` por ticker e **todos os 79 falharam** — cada `puxar_dados` levantou exception, cada um pulou.
2. `varre_lista` retornou `pd.DataFrame()` (vazio).
3. `data.carrega_fundamentos` (modo "1º dia útil do mês") salvou esse DF vazio no cache mensal `all_ticker_financial_indicators.xlsx` e o devolveu.
4. `gera_indicadores_extras` iterou zero linhas e devolveu o DF inalterado (vazio).
5. `rankeia_outros_indicadores_maior_melhor(df, "Cres. Rec (5a)", ...)` fez `df["Cres. Rec (5a)"]` num DF sem colunas → `KeyError`.

**Por que a duração foi 41 s e não os ~5–10 min normais:** com `timeout=20s` por request, 79 chamadas só caberiam em 41 s se cada uma falhar **quase instantaneamente** — TCP RST ou 403/429 imediato. Comportamento típico de anti-bot.

**Por que local funciona e CI não** (testado agora em 2026-06-02):

| Ambiente            | Resultado                              |
|---------------------|----------------------------------------|
| Local (IP residencial BR) | 79/79 tickers, 38 colunas cada, run limpo |
| GitHub Actions (datacenter US/EU) | 3 runs consecutivas crasharam |

O mesmo código contra o mesmo site produz resultados opostos. **Única variável que mudou: o IP de origem.**

## Diagnóstico

**fundamentus.com.br está bloqueando IPs do GitHub Actions** (range de datacenter / ASN cloud). É padrão de anti-bot — sites brasileiros, principalmente de finanças, costumam filtrar ranges de AWS/Azure/GCP/GitHub/Hetzner. O bloqueio pode ter sido:
- Atualização da blocklist do anti-bot entre 29/05 e 01/06.
- O IP do runner sorteado em 01/06 caiu numa faixa já banida (os runners são reciclados de pools).

Hipóteses anteriores **refutadas** pelo traceback + reprodução local:

- ~~H1 (HTML do Fundamentus mudou)~~ — local com 79 tickers produz 38 colunas em todos.
- ~~H2 (yfinance rate-limit)~~ — o stack mostra que `screener` rodou; só Fundamentus quebrou.
- ~~H3 (dependência atualizada)~~ — `KeyError` em coluna conhecida não é mudança de API.
- ~~H4 (ticker delistado)~~ — falha em 100% dos tickers não é caso pontual.

## Mitigações aplicadas hoje

### 1. Flag de debug em `fundamental.varre_lista` + propagação
- Param `debug=False` na função: quando True, imprime por ticker via `tqdm.write` a URL, número de tabelas parseadas, número de colunas, e traceback completo em caso de falha.
- `executa_pipeline` aceita `debug_fundamentos=False` (implica `forcar_raspagem_fundamentos=True`).
- CLI: `--debug-fundamentos`.
- Uso: `python -m robusta run --debug-fundamentos` (lista inteira) ou com `--tickers` pra subconjunto.

### 2. Fail-fast em `adicione_indicadores_e_ranking`
- Guarda no topo: se `all_ticker_financial_indicators.empty`, levanta `RuntimeError` com mensagem clara apontando scrape do Fundamentus.
- Evita `KeyError` cripta 100 frames depois (como no run de 01/06).

### 3. User-Agent realista em `data._HEADERS_FUNDAMENTUS`
- Trocado de Chrome 58 (2017) para Chrome 124.
- Adicionados headers `Accept`, `Accept-Language` (pt-BR), `Accept-Encoding`, `Connection` — equivalentes ao que um navegador real envia.
- Reduz, mas **não garante**, sucesso contra anti-bot baseado em IP.

## Mitigações em aberto (não aplicadas)

### A. Fallback pra cache antigo quando scrape mensal falha
Hoje, no 1º dia útil, `carrega_fundamentos` chama `raspar_fn()`; se ele devolver DF vazio, salva o vazio. Proposta: detectar DF vazio, manter o cache antigo, e logar warning. O run continua com fundamentos do mês anterior em vez de crashar. **Custo: 30 min.**

### B. Pinar versões em `requirements.txt`
Hoje só lista nomes. `pip freeze > requirements.txt` na venv local elimina variabilidade. **Custo: 5 min.** Não resolve o problema atual, mas elimina H3 para sempre.

### C. Notificação de falha
Step `if: failure()` no `run-pipeline.yml` que dispara email/Telegram via webhook. Descobre falha na hora, não pelo site congelado. **Custo: 15 min.**

### D. Plano-B caso anti-bot persistir
Se com o User-Agent novo o cron continuar falhando, opções em ordem de complexidade:
1. Adicionar `time.sleep()` entre requests (reduz pegada de bot).
2. Proxy residencial (custo $) ou Tor.
3. Migrar o scrape pra rodar localmente (laptop do user) ou em VPS com IP residencial, e fazer upload do cache pra repo.
4. Trocar fonte de fundamentos (StatusInvest, brapi.dev) — mudança de escopo, exige re-validação dos rankings contra `tests/baseline/COLUMN_SCHEMA.md`.

## Próxima ação recomendada

1. Commitar as 3 mitigações de hoje (debug flag, fail-fast, User-Agent).
2. Disparar manualmente o workflow via **Actions → ROBUSTA pipeline → Run workflow** (workflow_dispatch).
3. Se passar → User-Agent resolveu, monitorar 1 semana.
4. Se falhar → o log do step "Roda pipeline" vai mostrar exatamente onde quebra agora (RuntimeError com mensagem clara, em vez de KeyError). Daí parte-se pras opções da seção D.
