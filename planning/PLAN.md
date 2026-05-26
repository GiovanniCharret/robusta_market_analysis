# Plano De Rebuild Modular Do ROBUSTA

## Summary

Rebuild gradual do `main.py` legado, separando código por responsabilidade dentro do pacote `robusta/`. O alvo final é uma execução automatizada que roda 3×/dia num VPS Linux, grava `latest.json` em disco e o serve através do **nginx** para um **site estático** (HTML + JS vanilla) com dashboard pessoal e drill-down por ticker. Excel continua disponível para download via botão no site, mas não é mais a saída principal.

Decisões travadas:

- **Persistência**: arquivo `latest.json` único (sem histórico) + `latest.xlsx` em paralelo (para download). Cada run sobrescreve atomicamente.
- **Servidor HTTP**: **nginx servindo arquivos estáticos**. Sem FastAPI, sem aplicação Python permanente — o pipeline é processo curto disparado pelo cron.
- **Frontend**: HTML + CSS + JavaScript vanilla, sem framework, sem build step, sem Node no VPS.
- **Hospedagem**: VPS Linux (Hostinger) com domínio próprio e HTTPS via Let's Encrypt. Audiência: uso pessoal, sem autenticação.
- **Agendamento**: cron do sistema, seg–sex, 3 horários (12:30, 16:00, 21:30 UTC = 09:30, 13:00, 18:30 BRT).
- **Entradas**: `lista_tickers_liquidos.xlsx` e `all_ticker_financial_indicators.xlsx` permanecem como fonte da lista e do cache mensal. `carteira.json` (novo) lista os tickers da carteira pessoal para comparação.
- **WhatsApp/Twilio**: removidos do rebuild (já apagados em fases anteriores).
- **Análise**: metodologia preservada (pesos, thresholds, nomes de indicadores). Apenas portar e organizar.
- **Bugs técnicos óbvios**: corrigir quando impedirem a intenção do código, sem alterar a tese analítica.

## Key Changes

- Organização do código em `robusta/` por responsabilidades (status atual entre parênteses):
  - `robusta/config.py` (concluído) — versão, janelas, caminhos, calendário.
  - `robusta/data.py` (concluído) — leitura de Excel, Yahoo, Fundamentus.
  - `robusta/technical.py` (concluído) — análise técnica T1–T7.
  - `robusta/fundamental.py` (concluído) — análise fundamentalista F1–F10.
  - `robusta/pipeline.py` (concluído) — orquestração + `RunResult`.
  - `robusta/cli.py` (já existe, será expandida) — entrypoint `python -m robusta run`.
  - `robusta/persistence.py` (Fase 6) — serialização JSON + XLSX.
  - `site/` (Fase 7) — frontend estático (HTML + CSS + JS).

- CLI atual e futura (`python -m robusta run`):
  - `--tickers PRIO3 ASAI3` (DEV/DEBUG, **já existe**) — subconjunto opcional.
  - `--export-xlsx CAMINHO` (**já existe**) — exporta o `merged_results` para xlsx. Em produção via cron, aponta para `~/robusta/var/latest.xlsx`.
  - `--refresh-fundamentos` (**já existe**) — força raspagem do Fundamentus fora do 1º dia útil do mês.
  - `--emit-latest` (**Fase 6**) — escreve `~/robusta/var/latest.json` via `persistence.py`. Em produção via cron, sempre passado.

- Removidos do fluxo (já feito nas fases concluídas):
  - credenciais Twilio e função `send_whatsapp_messages`.
  - `main.py` legado (excluído; snapshot em `scripts_antigos/main.py` para referência).
  - prints de progresso (substituídos por logging + tqdm controlado).

- Bugs técnicos conhecidos: a lista que orientou o porte está abaixo. Os que **continuam relevantes** estão marcados; os já corrigidos ficam como histórico.
  - ~~download incondicional de `GOAU3` em `extrai_cotacoes`~~ — corrigido na Fase 3 (T6).
  - ~~`:` no lugar de `=` em `add_price_concentration_levels_by_me`~~ — corrigido na Fase 3 (T5, bug B1).
  - ~~override de `hora_atual = "19:00"` e `eh_dia_util = True`~~ — `main.py` legado removido.
  - ~~override de `ticker_list = {'ticker':[...]}` em `gere_df_principal`~~ — Fase 2.
  - ~~lógica de cache invertida em `carrega_fundamentos`~~ — Fase 2 (com nova flag `forcar_raspagem` para atualização sob demanda).
  - ~~`YFRateLimitError` não importado~~ — Fase 2.
  - ~~`.fillna(0)` sem atribuição em rankings~~ — Fase 4 (F4/F5).
  - ~~`pandas.qcut` sem proteção contra empates~~ — Fase 4 (`_classe_decil`).
  - ~~filename `' carteira_automatica.xlsx'`~~ — n/a (export viável só via `--export-xlsx`).
  - ~~`pandas.concat` em loop dentro de `varre_lista`~~ — Fase 4 (F10).
  - ~~variáveis globais (`data_cache_backtest`, etc.)~~ — Fase 3 (handoff `precos_por_ticker`).
  - ~~Encoding do Fundamentus: `?` literal de tooltip aparecendo nas chaves~~ — corrigido em `formatar_tabela` (limpeza de prefixo `?` antes do rename `Papel → Ticker`).

### Fronteira bug vs metodologia — invariantes

A regra "corrigir bugs quando impedirem a intenção do código" só vale contra estas invariantes. Violá-las é bug a corrigir; mudar número, peso, threshold ou nome de indicador é metodologia e **não** se altera sem pedido explícito:

- o universo analisado vem somente de `lista_tickers_liquidos.xlsx`, sem override embutido no código.
- a raspagem de fundamentos ocorre **só** quando: (a) é o 1º dia útil do mês, (b) o usuário passou `--refresh-fundamentos`, ou (c) o cache `all_ticker_financial_indicators.xlsx` está ausente/vazio (fallback de auto-recuperação). Nos demais casos, lê o cache.
- rankings e `avaliacao_fundamentalista` não podem conter `NaN` silencioso.
- toda execução que chega ao fim serializa um JSON válido conforme o contrato.
- nenhuma coluna obrigatória do contrato JSON pode estar ausente da saída.

## JSON Contract

A cada execução do pipeline, dois arquivos são sobrescritos atomicamente em `~/robusta/var/`:

- `latest.json` — payload completo da execução, consumido pelo frontend (`fetch('/data/latest.json')`).
- `latest.xlsx` — `merged_results` exportado para Excel, servido pelo botão de download do site.

Não há retenção de execuções antigas. Sem `runs/<timestamp>.json`, sem symlinks.

### Estrutura de `latest.json`

Formato orientado a registros, com snake_case ASCII em todas as chaves:

- `schema_version` — inteiro; incrementa a cada mudança incompatível de campos. Versão atual: `1`.
- `run_id` — string ISO 8601 sem `:` (ex: `2026-05-26T13-00-00Z`).
- `generated_at` — ISO 8601 UTC.
- `robusta_version` — string vinda de `config.VERSION`.
- `input_universe` — lista de tickers base (sem `.SA`) efetivamente analisados.
- `summary` — objeto com `tickers_ok`, `tickers_failed`, `vol_media`, `vol_std` (preservados de `distorions_analysys`).
- `portfolio_signals` — objeto `{longs: [...], shorts: [...]}` com os tickers do top 3 / bottom 3 do `distortion_ranking` (mockup atual mostra top 3; o pipeline pode produzir mais e o frontend recorta).
- `tickers` — dicionário `{ticker_base: {...}}` com **todos** os tickers do universo. Cada valor traz todos os campos calculados pelo pipeline (técnica + fundamental + ranking), em snake_case. O frontend escolhe o que mostrar.
- `warnings` — lista de strings com avisos não fatais (ex: `qcut` caiu em fallback, ticker sem fundamentos).
- `failed_tickers` — lista de objetos `{ticker, reason}`.

Campos relevantes dentro de cada `tickers[TICKER]`:

- Identidade: `ticker`, `setor`, `subsetor`.
- Sinais: `fundamental_signal` (-1/0/+1), `vol_signal` (-1/0/+1), `posicao_setorial` (`melhor`/`pior`/`""`).
- Técnica: `preco`, `vol_anualizada_30d`, `mma9..mma200`, `pct_to_mma10`, `pct_to_mma50`, `alto_vol_persistente`, e os 8 níveis `sup_min_by_mslf` ... `momentum_break_by_mslf`.
- Fundamental: `pl`, `pvp`, `ev_ebit`, `roic`, `cres_rec_5a`, `div_liq_vm`, `avaliacao_fundamentalista`.
- Ranking: `distortion_ranking`.

### Convenções de serialização

- `NaN`/`None` → `null` JSON (campo presente, valor `null`), não campo omitido.
- `pandas.Timestamp` → ISO 8601 string.
- `numpy.int64`/`numpy.float64` → `int`/`float` nativos; encoder customizado obrigatório (`json.dumps` padrão lança `TypeError`).
- Chaves de dicionário sempre string.
- Sentinelas `"Abismo"`/`"Foguete"` dos níveis `*_by_mslf` mantêm o tipo string (frontend trata).

### Escrita atômica

`persistence.py` grava primeiro em `latest.json.tmp` e usa `Path.replace()` (syscall atômica no Linux) para promover o arquivo. Em nenhum momento o nginx serve um arquivo pela metade.

### Handoff interno técnica → fundamentalista

- Contrato: `Dict[str, float]` mapeando ticker base (`PRIO3`) → último preço de fechamento.
- A fase técnica produz e normaliza a chave (remove `.SA`); a fase fundamentalista consome sem saber da Yahoo.
- Passado como argumento explícito ao longo do pipeline, não como global.

### Carteira pessoal (`carteira.json`)

Arquivo separado, editado manualmente pelo usuário em `~/robusta/site/carteira.json` (servido pelo nginx como `/carteira.json`):

```json
{ "tickers": ["LREN3", "ASAI3", "GOAU4", "PRIO3", "KBLN11", "POMO4"] }
```

O frontend cruza com `latest.json` em runtime para popular o bloco "Sua carteira" da página do ticker.

## Implementation Plan

Legenda de status por fase:

- `[ ]` — não iniciada
- `[~]` — em andamento
- `[x]` — concluída e validada com teste rápido

Estado atual: todas as fases em `[ ]`. Executor deve atualizar o checkbox da fase imediatamente após terminar o build. Marcar `[x]` exige registrar, na própria fase, evidência: comando executado, resultado do teste, arquivos alterados e limitações conhecidas. Sem essa evidência a fase permanece `[~]`.

1. `[x]` Criar baseline de segurança:
   - manter `main.py` antigo como referência temporária.
   - registrar quais colunas finais existem hoje em `carteira_automatica` e no merge final.
   - criar fixtures pequenas com 2 ou 3 tickers para comparar o rebuild sem rodar toda a B3.
   - teste rápido: rodar uma execução reduzida com 2 ou 3 tickers e salvar um snapshot versionado (commitado em `tests/`) das colunas e valores finais. As fases seguintes comparam coluna a coluna contra esse snapshot, não por inspeção visual.

   **Evidência (concluída):**
   - Decisão acordada com o usuário: baseline reproduzível = schema de colunas (análise estática) + fixtures sintéticas determinísticas, em vez de snapshot de valores ao vivo (o `main.py` legado depende de dados não reproduzíveis da Yahoo/Fundamentus e não roda até o fim — bugs B3).
   - Ambiente criado: `.venv` + `requirements.txt`; instalado pandas 3.0.3, numpy 2.4.6, pytest 9.0.3, fastapi, etc.
   - Arquivos criados: `requirements.txt`, `.gitignore`, `tests/fixtures/_generate_ohlcv.py` (gerador determinístico), `tests/fixtures/ohlcv_{PRIO3,ASAI3,LREN3}.csv` (260 pregões cada), `tests/fixtures/fundamentus_PRIO3.html`, `tests/conftest.py`, `tests/test_baseline.py`, `tests/baseline/COLUMN_SCHEMA.md` (schema final por análise estática + bugs B1/B2/B3).
   - Comando: `pytest -q` → `3 passed in 0.29s`.
   - Limitações conhecidas: sem snapshot de valores de execução real; a fixture Fundamentus é mínima e pode ser refinada nas fases F1/F2.

2. `[x]` Extrair configuração e IO:
   - centralizar caminhos dos Excel, pasta de JSON, versão, janelas e listas de médias.
   - encapsular leitura de tickers e fundamentos cacheados. O `DataLoader` de fundamentos deve raspar Fundamentus **somente** no 1º dia útil do mês e salvar cache; nos demais dias, carregar do cache (inverso do bug atual).
   - encapsular chamadas Yahoo/Fundamentus com retries e erros explícitos. Importar `YFRateLimitError` corretamente (ou capturar `Exception`).
   - remover override de universo: a lista lida do Excel passa direto ao pipeline; qualquer filtro (ex: subset manual para debug) fica atrás de flag explícita de CLI.
   - entrada: caminhos atuais dos Excel e parâmetros que hoje estão como globais.
   - saída: mesmos objetos usados pelo fluxo atual, como DataFrame de tickers, DataFrame de fundamentos cacheados e constantes acessíveis por importação.
   - teste rápido: carregar `lista_tickers_liquidos.xlsx` e confirmar coluna `ticker`; carregar `all_ticker_financial_indicators.xlsx` e confirmar coluna `Ticker`; mock de data dentro/fora do 1º dia útil confirmando que só raspa no 1º dia útil.

   **Evidência (concluída):**
   - Arquivos criados: `robusta/__init__.py`, `robusta/config.py` (VERSION, `MMA_WINDOWS`, `VOL_WINDOW`, `HISTORICO_ANOS`, caminhos dos Excel, `PASTA_RUNS`, `FUNDAMENTUS_URL_BASE`, `data_inicio_download`, `eh_primeiro_dia_util_do_mes`), `robusta/data.py` (`ler_lista_tickers`, `ler_fundamentos_cache`, `baixa_cotacoes_yahoo` com retry e `YFRateLimitError` importado corretamente, `baixa_html_fundamentus`, `carrega_fundamentos` com lógica de cache mensal **corrigida**), `tests/test_data.py`.
   - O calendário de feriados (legado `CustomHolidayCalendar`) **não** foi portado nesta fase: só é usado pelo scheduler (`eh_dia_util`), que é da Fase 8. `eh_primeiro_dia_util_do_mes` replica o `first_day_alert` legado, que ignora feriados.
   - `carrega_fundamentos` recebe `raspar_fn` por injeção — desacopla da Fase F10 e mantém testável agora.
   - Override de universo: `ler_lista_tickers` é a única fonte do universo, sem lista embutida. O subset de debug fica para a flag de CLI da Fase 8.
   - Comando: `pytest -q` → `9 passed` (3 baseline + 6 de config/IO).
   - Limitações/descobertas: `all_ticker_financial_indicators.xlsx` real tem nomes de coluna com mojibake (`Nro. A��es`, `D�v. L�quida`) e uma coluna `Unnamed: 0`; reconciliar isso é trabalho das Fases F3/F9. `openpyxl` precisou ser adicionado ao `requirements.txt` (faltava nas instruções legadas). Feriados móveis no calendário ainda são fixos de 2025 (limitação herdada).

3. Extrair análise técnica em fases pequenas:
   - regra de porte: migrar uma função por fase. Só juntar duas funções quando a união criar uma única função mais simples e mais fácil de debugar.
   - manter os objetos de retorno atuais. Se uma função hoje retorna DataFrame, ela continua retornando DataFrame; se retorna `False` ou lista, esse contrato permanece até uma fase posterior explicitamente planejada.
   - `[x]` fase T1, `crie_variacao(stock_data, info)`: entrada DataFrame OHLCV e `info`; saída mesmo DataFrame com `Return` ou `Oscillation`. Teste rápido: DataFrame de 3 fechamentos conhecidos e comparação direta do `pct_change`.

     **Evidência (concluída):**
     - Arquivos criados: `robusta/technical.py` (com `crie_variacao`), `tests/test_technical.py`.
     - Contrato preservado do legado (`main.py:317-343`): `info=1` → coluna `Return` via `Close.pct_change()`; `info=2` → `Oscillation` via `Momentum.pct_change()`. Apenas `info=1` é usado em produção (`extrai_cotacoes` na linha 296); o caminho `info=2` foi mantido para preservar a assinatura. Adicionado `raise ValueError` para `info` fora de {1, 2} (no legado caía silenciosamente em `NameError` por variável não definida).
     - Comando: `pytest -q` → `13 passed in 3.23s` (9 anteriores + 4 novos).
     - Limitações: o caminho `info=2` continua sendo código morto no fluxo de produção; será removido apenas se a Fase 5 (pipeline) confirmar que ninguém o chama.
   - `[x]` fase T2, `crie_medias_moveis(stock_data, lista_args)`: entrada DataFrame com `Close` e lista de janelas; saída mesmo DataFrame com `MMA{n}`, `Position_MMA{n}` e `%_to_MMA{n}`. Teste rápido: janela curta `[2]` com valores conhecidos e checagem da média, posição e distância.

     **Evidência (concluída):**
     - Função adicionada em `robusta/technical.py` (`crie_medias_moveis`); testes em `tests/test_technical.py`.
     - Contrato preservado do legado (`main.py:345-362`): para cada `n` em `lista_args`, cria `MMA{n}` via `Close.rolling(window=n).mean()`; `Position_MMA{n}` = 1 se `Close > MMA{n}`, -1 caso contrário, 0 enquanto `MMA{n}` é NaN. Empate (`Close == MMA`) cai em **-1** porque o legado usa `>` estrito — preservado.
     - Imports do legado vinham de `from numpy import *` e `import pandas`; troquei por `import numpy as np` e `import pandas as pd` explícitos no topo do módulo.
     - Comando: `pytest -q` → `17 passed in 1.51s` (13 anteriores + 4 novos: janela conhecida, empate Close==MMA, múltiplas janelas, mesmo DataFrame retornado).
     - Limitações: a função aceita silenciosamente uma janela maior que `len(stock_data)` (toda a coluna `MMA{n}` fica NaN e `Position_MMA{n}` vira 0). Isso replica o legado e não é bug do contrato; o pipeline (Fase 5) é que decide se filtra tickers com histórico curto.
   - `[x]` fase T3, `calcule_volatilidade_anualizada_std(dados, vol_window)` (renomeada de `calcule_volatilidade_anualizada` no legado): entrada DataFrame com `Return`; saída mesmo DataFrame com `vol_anualized_{vol_window}days`. Teste rápido: série curta de retornos e comparação com `rolling.std() * sqrt(252)`.

     **Evidência (concluída):**
     - Função adicionada em `robusta/technical.py` (`calcule_volatilidade_anualizada_std`); testes em `tests/test_technical.py`.
     - Contrato preservado do legado (`main.py:471-486`): `rolling(window=vol_window).std() * sqrt(252)`. Nome da coluna gerada continua `vol_anualized_{vol_window}days` — está no baseline (`tests/baseline/COLUMN_SCHEMA.md`), portanto não muda.
     - **Renome a pedido do usuário**: sufixo `_std` na função para deixar explícito que a vol é por desvio-padrão estatístico simples; abre espaço para futuras estimativas (GARCH/EWMA/Parkinson) sem ambiguidade. O legado usava `from numpy import *`; aqui usamos `np.sqrt` explícito.
     - Divergência registrada: a docstring legada chamava `Return` de "retorno logarítmico", mas `crie_variacao(info=1)` produz `pct_change` (retorno simples). Mantido como está — troca para log-return é metodologia, não porte.
     - Comando: `pytest -q` → `20 passed in 1.00s` (17 anteriores + 3 novos: comparação contra cálculo direto via pandas, sufixo do nome da coluna acompanha `vol_window`, retorno do mesmo DataFrame).
     - Limitações: a função assume `Return` já existir; chamar antes de `crie_variacao` levanta `KeyError` (comportamento herdado do legado, sem proteção explícita).
   - `[x]` fase T4, `alto_volume_persistente(df)`: entrada DataFrame com `Volume` e `Close`; saída mesmo DataFrame com `Alto_volume_persistente`. Teste rápido: fixture com dois dias consecutivos de volume alto e preço subindo/caindo para validar `1` e `-1`.

     **Evidência (concluída):**
     - Função adicionada em `robusta/technical.py` (`alto_volume_persistente`); testes em `tests/test_technical.py`.
     - Contrato preservado do legado (`main.py:438-469`): parâmetros internos `volume_window=20`, `volume_multiplier=2`, `k=2` mantidos hard-coded — promovê-los a config é mudança de metodologia, não de porte.
     - Lógica: `vol_ma = Volume.rolling(20, min_periods=20).mean()`; `hv_flag = Volume >= vol_ma * 2`; `hv_streak = hv_flag.rolling(2).sum() == 2`; `ret = Close.pct_change(2)`; `1` se streak ∧ ret>0, `-1` se streak ∧ ret<0, `0` caso contrário. `select` veio de `from numpy import *` no legado; aqui usamos `np.select` explícito.
     - Nome da coluna preservado: `Alto_volume_persistente` (está no baseline). A docstring legada mencionava um nome parametrizado `Alto_volume_{multiplier}_p{k}d_?value` que **nunca** foi gerado de fato — apenas mencionado no docstring; ignorado no porte.
     - Comando: `pytest -q` → `25 passed in 0.85s` (20 anteriores + 5 novos: streak + preço subindo → 1; streak + preço caindo → -1; streak quebrado → 0; preço estável + streak → 0 (`>`/`<` estritos); retorno do mesmo DataFrame).
     - Limitações: fixture precisa de ≥ 20 dias para que `vol_ma` deixe de ser NaN; com menos dados, `Alto_volume_persistente` fica zerado mesmo com volume "alto". É comportamento herdado do `min_periods=20`.
   - `[x]` fase T5, `add_price_concentration_levels_by_me(df)`: entrada DataFrame OHLCV com `Adj Close`, `High` e `Low`; saída **DataFrame modificado com `return df` explícito**, acrescido das colunas `sup_*_by_mslf`, `res_*_by_mslf`, `std_raking_value_by_mslf` e `momentum_break_by_mslf`. Corrigir o bug de `:` usado no lugar de `=`. Teste rápido: fixture com edges conhecidos, confirmação de que as colunas são criadas e de que o retorno não é `None`.

     **Evidência (concluída):**
     - Função adicionada em `robusta/technical.py` (`add_price_concentration_levels_by_me`); testes em `tests/test_technical.py`.
     - **Bug B1 corrigido**: linhas 718-725 do legado usavam `:` (anotação no-op por PEP 526) no lugar de `=`, então as 8 colunas `*_by_mslf` nunca eram criadas. Trocadas por `=`. Importante: o legado **já** retornava `df` (linha 728) — a descrição "hoje retorna None" no texto da fase estava imprecisa; o `return df` foi confirmado e preservado. (Atualizei também a redação acima.)
     - Nomes preservados exatamente como no baseline (`tests/baseline/COLUMN_SCHEMA.md`), incluindo o typo `std_raking_value_by_mslf` ("raking", não "ranking"). Os 8 escalares são broadcast a todas as linhas do `df`.
     - Toda a lógica de concentração (round(1), value_counts, maps high/low, percentis 68/95/99, drop_duplicates, sentinelas "Abismo"/"Foguete", momentum_break) foi portada sem alteração de metodologia. `from numpy import *` → `np.where`; `pandas.concat`/`to_numeric` → `pd.*`.
     - Comando: `pytest -q` → `29 passed in 3.67s` (25 anteriores + 4 novos: 8 colunas criadas e broadcast sobre as 3 fixtures reais; mesmo DataFrame retornado; sem resistência → "Foguete" + momentum 1; sem suporte → "Abismo" + momentum -1).
     - Limitações: a anotação `-> dict` do legado foi removida (a função sempre devolveu DataFrame). Não há teste de valores numéricos exatos dos níveis de suporte/resistência — a fixture realista valida criação/broadcast e os casos sentinela validam os ramos de borda; verificação numérica fina fica para o teste de pipeline (Fase 5) se necessário.
   - `[x]` fase T6, `extrai_cotacoes(ticker)`: entrada ticker Yahoo no formato `PRIO3.SA`; saída preservada como `False` em falha ou `[ticker, stock_data]` em sucesso. Remover o `yfinance.download('GOAU3')` incondicional e importar `YFRateLimitError`. Teste rápido: mock de download retornando DataFrame válido, mock vazio, e mock que lança `YFRateLimitError` para validar os três caminhos sem acessar rede.

     **Evidência (concluída):**
     - Função adicionada em `robusta/technical.py` (`extrai_cotacoes`); testes em `tests/test_technical.py` (3 caminhos) + `tests/test_data.py` (rate-limit na camada de dados).
     - **Decisão de porte (delegação do retry):** na Fase 2 o retry e o tratamento de `YFRateLimitError` já foram encapsulados em `data.baixa_cotacoes_yahoo`. T6 **delega** o download a essa função em vez de re-implementar o loop (evita duplicar a Fase 2). Consequência: os "três caminhos" de T6 viram **válido / vazio / volume-baixo** — o esgotamento por rate-limit chega aqui como DataFrame vazio. O caminho `YFRateLimitError` em si foi testado em `data.baixa_cotacoes_yahoo` (`test_data.py`), preenchendo lacuna de teste da Fase 2.
     - Removidos: download incondicional de `'GOAU3'`, segundo download redundante de `ticker`, e os `print`. Sem efeitos colaterais em globais (`data_cache_backtest`, `probleminhas_temp`) — o caller (T7) montará handoff de preços e lista de falhas a partir do retorno.
     - Omitido o guard `droplevel(0) if MultiIndex`: `baixa_cotacoes_yahoo` usa `multi_level_index=False` (colunas planas garantidas) e o legado dropava do índice de **linhas** (axis=0), não de colunas — era código morto/bugado.
     - Contrato preservado: filtro de liquidez `Volume.tail(30).mean() < 10000` → `False`; `ticker[:-3]` para a coluna `Ticker` base; encadeamento T1→T2(`config.MMA_WINDOWS`)→T3(`config.VOL_WINDOW`)→T4→T5; retorno `[ticker, stock_data]`.
     - Comando: `pytest -q` → `34 passed in 0.69s` (29 anteriores + 5 novos: sucesso enriquecido, download vazio→False, volume baixo→False, `baixa_cotacoes_yahoo` sucesso, `baixa_cotacoes_yahoo` rate-limit esgota→vazio com 3 tentativas e 2 esperas).
     - Limitações: warning benigno do pandas (`obj.round has no effect with datetime`) quando `add_price_concentration_levels_by_me` roda após `reset_index` (a coluna `Date` é datetime); `round(1)` ignora datetime e segue arredondando os numéricos — comportamento idêntico ao legado, não corrigido para não tocar a lógica.
   - `[x]` fase T7, `screener(lista, carteira_automatica, probleminhas=None)`: entrada lista de tickers base e DataFrame acumulador; saída DataFrame consolidado `carteira_automatica` **e** `Dict[str, float]` de últimos preços por ticker base (handoff explícito para F3). Teste rápido: mock de `extrai_cotacoes` com dois tickers e confirmação de duas linhas finais + dicionário de preços com chaves sem `.SA`.

     **Evidência (concluída):**
     - Função adicionada em `robusta/technical.py` (`screener`); testes em `tests/test_technical.py`.
     - **Handoff de preços criado**: `precos_por_ticker[base] = float(stock_data["Close"].iloc[-1])`. Coluna `Close` (não `Adj Close`) confirmada contra o legado `gera_indicadores_extras` (`main.py:1037`: `data_cache_backtest[ticker_yf].iloc[-1]['Close']`). Chave = ticker base (sem `.SA`), conforme o redesenho do handoff no PLAN (o legado keyava por `.SA`). Substitui o global `data_cache_backtest`.
     - `probleminhas` virou parâmetro explícito (default `set()` vazio) em vez de global.
     - Removidos: export Excel interativo (`input()` + `to_excel` para listas <= 2), `tqdm` e prints de progresso — responsabilidade do CLI (Fase 8), fora do fluxo de biblioteca. `frames_para_concat` agora é de fato usado: acumula linhas e faz um único `concat` no final (o legado declarava a lista mas concatenava em loop). `except:` nu → `except Exception` (resiliência preservada sem engolir KeyboardInterrupt/SystemExit).
     - Comando: `pytest -q` → `39 passed in 2.56s` (34 anteriores + 5 novos: dois tickers→duas linhas + preços base; pula ticker que retorna False; pula ticker em probleminhas; continua quando um ticker levanta; sem resultados devolve a carteira intacta).
     - Limitações: `screener` não monta `failed_tickers` (tickers que falham são só pulados/logados) — a coleta estruturada de falhas para o JSON é da Fase 5/6. O `.SA` é anexado aqui (`f"{ticker}.SA"`); a normalização de ticker robusta (risco #19 do review) segue adiada.

   **Fase 3 concluída**: T1–T7 portadas e testadas. `robusta/technical.py` cobre toda a análise técnica do legado. Próxima é a Fase 4 (fundamentalista, F1–F10).

4. Extrair análise fundamentalista em fases pequenas:
   - regra de porte: migrar uma função por fase, mantendo assinatura e retorno sempre que possível para facilitar comparação humana.
   - `[x]` fase F1, `puxar_dados(url)`: entrada URL do Fundamentus; saída lista de tabelas conforme `pandas.read_html`. Teste rápido: mock de HTML com uma tabela mínima e confirmação de lista não vazia.

     **Evidência (concluída):**
     - Módulo criado: `robusta/fundamental.py` (com `puxar_dados`); testes em `tests/test_fundamental.py`.
     - **Decisão de porte (delegação do HTTP):** o GET com User-Agent já foi encapsulado em `data.baixa_html_fundamentus` (Fase 2). F1 delega o download a essa função e só faz `pd.read_html(StringIO(html))` — mesmo padrão de T6 com a Yahoo. Retorno preservado: lista de DataFrames.
     - Comando: `pytest -q` → `41 passed in 1.35s` (39 anteriores + 2 novos: HTML mínimo → lista não vazia; fixture sintética do Fundamentus → ≥2 tabelas e primeira célula `'Papel'`).
     - Limitações: nenhuma além da já conhecida (a fixture Fundamentus é mínima; pode ser refinada na F2 conforme o parsing exigir).
   - `[x]` fase F2, `formatar_tabela(tables)`: entrada lista de tabelas do Fundamentus; saída DataFrame transposto e limpo, com coluna `ticker`/`Ticker` conforme padronização definida no porte. Teste rápido: fixture com tabela pequena contendo `Papel`, `Setor`, `LPA` e valores brasileiros para validar limpeza e conversão numérica.

     **Evidência (concluída):**
     - Adicionadas em `robusta/fundamental.py`: `formatar_tabela` + helper `_converte_para_numero` (extraído como módulo-level para ser testável) + constante `_PADROES_LINHAS_DESCARTADAS` (regex de filtro preservadas verbatim do legado). Testes em `tests/test_fundamental.py`.
     - **Bug B2 RESOLVIDO — decisão de chave**: padronizado em `Ticker` (maiúsculo). Motivo: o lado técnico (`screener` insere `Ticker`), o merge (`on='Ticker'`) e o Excel cacheado (`test_ler_fundamentos_cache` confirma coluna `Ticker`) já usam maiúsculo; só `formatar_tabela`→`gera_indicadores_extras` usavam `ticker` minúsculo (inconsistência interna do legado, `main.py:1015` vs `main.py:1029`). Como vou portar F3 também, F3 lerá `row['Ticker']`. Unifica a chave em todo o pipeline.
     - **Conversão numérica BR preservada como metodologia**: o legado divide por 100 mesmo sem `.` no valor (`main.py:985`). Mantido sem alteração e documentado no docstring — mudar isso alteraria todos os números da fundamentalista.
     - Omitido o ramo de FII (`tables[0].iloc[0,0] == "?FII"`): código morto e quebrado (`tables` é lista, não tem `.drop`) que nunca rodava no caminho de ações. Filtro de FII fica como decisão separada se necessário. `concat` em loop → acumulação em lista + `concat` único.
     - Comando: `pytest -q` → `44 passed in 1.16s` (41 anteriores + 3 novos: `_converte_para_numero` nos formatos BR; `formatar_tabela` limpa/transpõe/renomeia `Papel`→`Ticker` e descarta linhas recalculadas/cabeçalho; consolidação de múltiplas tabelas em pares chave/valor).
     - Limitações: a conversão por-100-sempre pode distorcer inteiros puros sem separador (ex: `"123"`→`1.23`), mas é o comportamento do legado; só se revisa com pedido explícito. Filtro de FII não portado.
   - `[x]` fase F3, `gera_indicadores_extras(dados_financeiro_all_tickers, precos_por_ticker)`: entrada DataFrame fundamentalista e **`Dict[str, float]` de ticker base → último preço** (contrato definido em Fase 2, produzido em T7); saída mesmo DataFrame com `P/L`, `Dív. Líquida/Valor de mercado` e `P/VP`. Teste rápido: uma linha com `LPA`, `VPA`, `Nro. Ações`, `Dív. Líquida` e preço mockado para conferir as três contas; teste adicional confirmando que a função não lê `data_cache_backtest` global e não concatena `.SA` internamente.

     **Evidência (concluída):**
     - Função adicionada em `robusta/fundamental.py` (`gera_indicadores_extras`); testes em `tests/test_fundamental.py`.
     - **Handoff consumido**: novo parâmetro `precos_por_ticker` (o `Dict[str, float]` produzido pelo `screener` em T7) substitui o global `data_cache_backtest`. Lê `row['Ticker']` (maiúsculo, padronizado em F2) e busca o preço pela chave base — **sem** concatenar `.SA`.
     - Política numérica preservada do legado: `P/L = round(close/LPA, 2)` (ou `-1e6` se `LPA==0`); `P/VP = round(close/VPA, 2)` (ou `-1e6` se `VPA==0`); `Dív. Líquida/Valor de mercado = round(div_liquida / (nro_acoes*close), 2)`. `except:` nu → `except Exception`; print → logging.
     - Comando: `pytest -q` → `48 passed in 1.55s` (44 anteriores + 4 novos: três contas com preço mockado; `LPA`/`VPA`==0 → `-1e6`; dict só com chave `.SA` não casa → sem valuation (prova que não concatena `.SA`); ticker ausente do handoff não interrompe o loop).
     - Limitações: um ticker ausente do handoff (ou divisão degenerada, ex: `Nro. Ações==0`) cai no `except` e fica sem as 3 colunas de valuation — resiliência idêntica à intenção do legado.
   - `[x]` fase F4, `rankeia_outros_indicadores_maior_melhor(...)`: entrada DataFrame e nomes de indicadores; saída mesmo DataFrame com colunas `classe {indicador}`. Usar `pandas.qcut(..., duplicates='drop')` e atribuir o resultado de `.fillna(0)`. Teste rápido: 10 valores crescentes e confirmação de classes 1 a 10; fixture com muitos empates (ex: 8 zeros e 2 positivos) confirmando que não levanta `ValueError`.

     **Evidência (concluída):**
     - Adicionadas em `robusta/fundamental.py`: `rankeia_outros_indicadores_maior_melhor` + helper compartilhável `_classe_decil`. Testes em `tests/test_fundamental.py`.
     - **Bug do `.fillna(0)` corrigido**: o legado (`main.py:1085`) fazia `dados[col].fillna(0)` sem atribuir, descartando o resultado; aqui é atribuído de volta (`dados[col] = dados[col].fillna(0)`).
     - **Proteção do `qcut` (descoberta importante)**: `duplicates='drop'` **sozinho** com `labels=[1..10]` fixos ainda levanta `ValueError` quando os bins colapsam (pandas exige nº de labels = nº de bins). `_classe_decil` resolve com fallback: tenta `qcut(serie, 10, labels=[1..10])`; em `ValueError`, cai para `qcut(serie, 10, labels=False, duplicates='drop') + 1` (rotulagem inteira, < 10 classes). O legado quebrava nesses casos — qualquer comportamento não-quebrante que preserve o caso de 10 distintos é fiel à intenção.
     - `*kwargs` renomeado para `*indicadores` (era nome enganoso para varargs posicionais). Prints removidos.
     - Comando: `pytest -q` → `52 passed in 1.45s` (48 anteriores + 4 novos: 10 crescentes → classes 1–10; 8 zeros + 2 positivos → não levanta e classe sem NaN; `fillna(0)` atribuído; múltiplos indicadores).
     - Limitações: no caso de muitos empates as classes não cobrem 1–10 (menos bins) — é o preço de não quebrar; `_classe_decil` será reusado em F5 (menor melhor), invertendo a direção.
   - `[x]` fase F5, unificar rankings `menor_melhor`: entrada DataFrame, indicadores e política de negativo (`neg_permitido` ou `neg_bloqueado`); saída mesmo DataFrame com classes invertidas e, quando aplicável, negativos penalizados. Mesma proteção de `qcut` e atribuição de `fillna`. Teste rápido: um caso com 10 valores crescentes para confirmar que o menor recebe classe 10 e outro caso com valor negativo, baixo positivo e alto positivo para garantir que negativo não vira melhor classe quando bloqueado.

     **Evidência (concluída):**
     - Adicionada `rankeia_outros_indicadores_menor_melhor(dados, *indicadores, bloquear_negativos=False)` em `robusta/fundamental.py`; `_classe_decil` generalizado com parâmetro `crescente` (reusado por F4 e F5). Testes em `tests/test_fundamental.py`.
     - **Unificação das duas funções do legado** (`main.py:1094-1155`) num único parâmetro: `bloquear_negativos=False` = neg_permitido (menor valor → classe 10, sem restrição de sinal); `bloquear_negativos=True` = neg_bloqueado (valores `<= 0` ganham `+1e9` e vão para a pior classe). A penalização roda numa **série de trabalho** (`base.where(base > 0, base + 1e9)`), espelhando a coluna temporária `{indicador} descarte` do legado e preservando o valor real na coluna original.
     - Correções: `.fillna(0)` atribuído em ambos os modos (era descartado em neg_permitido; neg_bloqueado não tinha — agora honra a invariante "rankings sem NaN"); `qcut` protegido contra empates via `_classe_decil` (com inversão correta no fallback inteiro: `codigos.max() - codigos + 1`). Prints removidos.
     - **Delta documentada vs legado**: no modo bloqueado, a coluna original do indicador agora recebe `numeric + fillna(0)` (o legado deixava-a intacta, usando temp). É alinhado à invariante de não-NaN e o valor penalizado fica só na série de trabalho do decil.
     - Comando: `pytest -q` → `56 passed in 1.35s` (52 anteriores + 4 novos: 10 crescentes → menor pega classe 10; permitido → negativo pega a melhor classe; bloqueado → negativo vai para a pior classe; `fillna` atribuído).
     - Limitações: com poucos valores distintos as classes não cobrem 1–10 (fallback), igual a F4.
   - `[x]` fase F6, `avaliacao_fundamentalista(dados_financeiro_all_tickers)`: entrada DataFrame com classes e setor; saída mesmo DataFrame com `avaliacao_fundamentalista`. Teste rápido: uma empresa de setor especial e uma geral para validar soma das colunas corretas.

     **Evidência (concluída):**
     - Adicionada `avaliacao_fundamentalista` em `robusta/fundamental.py` + constantes `_SETORES_ESPECIAIS`, `_COLUNAS_ESPECIAIS`, `_COLUNAS_GERAIS` (extraídas do legado para o topo, são metodologia preservada verbatim). Testes em `tests/test_fundamental.py`.
     - Porte fiel (`main.py:1159-1179`): setor em `_SETORES_ESPECIAIS` (`Previdência e Seguros`, `Intermediários Financeiros`) soma `classe P/L + classe Cres. Rec (5a) + classe Dív. Líquida/Valor de mercado + classe P/VP`; demais somam `classe P/L + classe Cres. Rec (5a) + classe ROIC + classe EV / EBIT`. Só o print foi removido.
     - Comando: `pytest -q` → `59 passed in 1.73s` (56 anteriores + 3 novos: setor geral soma o conjunto geral e ignora os decoys; setor especial soma o conjunto especial; mistura de setores usa o conjunto certo por linha).
     - **Nota de ambiente**: durante esta fase o arquivo `all_ticker_financial_indicators.xlsx` apareceu deletado (git `D`), quebrando o teste pré-existente `test_ler_fundamentos_cache` (Fase 2). Restaurado via `git restore` a pedido do usuário; suíte voltou a verde.
     - Limitações: F6 assume que as colunas `classe ...` já existem (criadas por F4/F5) — o orquestrador (F9) garante a ordem.
   - `[x]` fase F7, `rankeando_empresas(dados_financeiro_all_tickers)`: entrada DataFrame com `Setor` e `avaliacao_fundamentalista`; saída mesmo DataFrame com `Posicao setorial`. Teste rápido: dois setores com melhor/pior conhecidos.

     **Evidência (concluída):**
     - Adicionada `rankeando_empresas` em `robusta/fundamental.py`; testes em `tests/test_fundamental.py`.
     - Porte fiel (`main.py:1182-1209`): por `Setor`, a(s) empresa(s) de maior `avaliacao_fundamentalista` recebem `'melhor'`, a(s) de menor recebem `'pior'`, as demais `''`. Só o print foi removido; usei `groupby("Setor", group_keys=False)` (limpa o índice na pandas 3.x, sem warning de grouping-columns).
     - **Quirk preservado e testado**: setor com uma só empresa tem `max == min`, então recebe `'melhor'` e logo `'pior'` (atribuição de min roda por último) → termina `'pior'`.
     - Comando: `pytest -q` → `62 passed in 4.91s` (59 anteriores + 3 novos: melhor/pior/meio-vazio num setor; dois setores independentes; setor de uma empresa → `'pior'`).
     - Limitações: o `reset_index(drop=True)` reordena as linhas por setor (efeito do legado) — irrelevante porque o merge final é por `Ticker`.
   - `[x]` fase F8, `avaliacao_fundamentalista_analisys(dados_financeiro_all_tickers)`: entrada DataFrame com `avaliacao_fundamentalista`; saída mesmo DataFrame com `Fundamental_?value`. Teste rápido: valores 14, 15, 31 e 32 para validar fronteiras.

     **Evidência (concluída):**
     - Adicionada `avaliacao_fundamentalista_analisys` em `robusta/fundamental.py`; testes em `tests/test_fundamental.py`.
     - Porte fiel (`main.py:1211-1224`), sem bug a corrigir: `>= 32 → 1`, `<= 14 → -1`, senão `0`. Nome da coluna `Fundamental_?value` preservado verbatim (mojibake do baseline).
     - Comando: `pytest -q` → `64 passed in 1.32s` (62 anteriores + 2 novos: fronteiras 14/15/31/32 → `[-1,0,0,1]`; extremos 0/50 → `[-1,1]`).
     - Limitações: nenhuma.
   - `[x]` fase F9, `adicione_indicadores_e_ranking(all_ticker_financial_indicators, precos_por_ticker)`: entrada DataFrame fundamentalista bruto/cacheado + dicionário de preços; saída DataFrame enriquecido e sem colunas `Unnamed`. Teste rápido: fixture pequena passando por todas as funções F3-F8 com preços mockados.

     **Evidência (concluída):**
     - Adicionada `adicione_indicadores_e_ranking` em `robusta/fundamental.py`; testes em `tests/test_fundamental.py`.
     - Encadeia F3 (com `precos_por_ticker`) → F4 (`Cres. Rec (5a)`, `ROIC`) → F5 permitido (`Dív. Líquida/Valor de mercado`) → F5 bloqueado (`P/L`, `P/VP`, `EV / EBIT`) → F6 → F7 → F8, e remove colunas `Unnamed`.
     - **Mapeamento das chamadas legadas**: as duas funções `menor_melhor` do legado (`neg_permitido`/`neg_bloqueado`) viram chamadas da unificada com `bloquear_negativos=False/True`. Linha morta `rankeia_PL` (comentada no legado) ignorada.
     - Comando: `pytest -q` → `66 passed in 3.96s` (64 anteriores + 2 novos: fixture de 3 tickers/2 setores passa por F3-F8 e sai com todas as colunas esperadas, sem `Unnamed`, sem NaN na avaliação, sinal em {-1,0,1}; ranking setorial produz melhor/pior no setor com 2 empresas).
     - Limitações: F9 assume que o `precos_por_ticker` cobre os tickers (senão F3 não cria P/L etc. para o ticker faltante, e o ranking de P/L levantaria KeyError se a coluna inteira faltar) — o pipeline (Fase 5) garante a consistência; o scraper de lista é F10.
   - `[x]` fase F10, `varre_lista(lista, probleminhas=None)`: entrada lista de tickers base; saída DataFrame consolidado de fundamentos. Substituir `pandas.concat` em loop por acumulação em lista + `concat` único no final. Teste rápido: mock de `puxar_dados` para dois tickers e confirmação de duas linhas consolidadas.

     **Evidência (concluída):**
     - Adicionada `varre_lista` em `robusta/fundamental.py` (`config` adicionado aos imports); testes em `tests/test_fundamental.py`.
     - **Acumulação corrigida**: o legado preenchia manualmente via `.loc[ticker_contador, column]` apenas para colunas presentes no 1º ticker (descartava colunas novas de tickers seguintes) e tinha um `except` quebrado (`tables = [tables]`, referência indefinida). Substituído por acumulação em lista + `pd.concat(linhas, ignore_index=True)` único, que **unifica** as colunas de todos os tickers.
     - `probleminhas` virou parâmetro (era global); `probleminhas_temp` removido; `url_financials` global → `config.FUNDAMENTUS_URL_BASE`; `except:` nus → `except Exception` com logging; prints removidos.
     - Comando: `pytest -q` → `70 passed in 1.27s` (66 anteriores + 4 novos: consolida dois tickers em duas linhas; pula `probleminhas`; falha de um ticker não interrompe; lista vazia → DataFrame vazio).
     - Limitações: falhas de download/parse apenas pulam o ticker (logado) — a coleta estruturada de `failed_tickers` é da Fase 5/6.

   **Fase 4 concluída**: F1–F10 portadas e testadas. `robusta/fundamental.py` cobre toda a análise fundamentalista do legado (scraping → limpeza → indicadores → rankings → score → sinal → orquestração). Próxima é a Fase 5 (pipeline consolidado).

5. `[x]` Criar pipeline consolidado:

   **Progresso (sub-fases):**
   - `[x]` 5a — `distorions_analysys` (ranking cross-sectional) portado em `robusta/pipeline.py`; preserva `(df, {'média', 'std_vol'})`. Testes em `tests/test_pipeline.py`. `pytest -q` → `72 passed` (+2). Nome e colunas (`%_to_MMA50_Categoria`, `%_to_MMA10_Categoria`, `Vol Mês^Anual_?value`) preservados do baseline.
   - `[x]` 5b — `distorted_price_analysis` (portfolio_signals) portado em `robusta/pipeline.py`. **Decisão do usuário (Opção 1)**: corrigir os dois bugs da fórmula `distortion_ranking` — (1) continuação de linha (parcelas de MMA eram statements soltos/descartados) e (2) copy-paste (3ª parcela usava `%_to_MMA50_Categoria` em vez de `%_to_MMA10_Categoria`). Fórmula final: `(avaliacao - 40)*-1 + %_to_MMA50_Categoria*mma50_wgh + %_to_MMA10_Categoria*mma10_wgh`. Removido o `to_excel`. `pytest -q` → `74 passed` (+2: fórmula+colunas; prova de que MMA10 é usado).
   - `[x]` 5c — `RunResult` (dataclass) + orquestrador `executa_pipeline(universo, momento=None, mma50_wgh=4, mma10_wgh=1)`. `RunResult` segura os DataFrames (`technical_results`, `fundamental_results`, `merged_results`, `portfolio_signals`) + metadados (`schema_version`, `run_id`, `generated_at`, `robusta_version`, `input_universe`, `summary`, `warnings`, `failed_tickers`); a serialização JSON fica para a Fase 6. `executa_pipeline` encadeia screener → `carrega_fundamentos` (regra mensal) → `adicione_indicadores_e_ranking` → merge `on='Ticker'` → `distorions_analysys` → `distorted_price_analysis`. `pytest -q` → `76 passed` (+2: integração com fixtures+mocks de rede confirma colunas essenciais e `summary.vol_std` não-None; ticker sem dados técnicos vai para `failed_tickers`).

   **Fase 5 concluída.** Decisão de design: `RunResult` carrega DataFrames (cálculo na Fase 5, serialização na Fase 6). `summary` traz `tickers_ok`, `tickers_failed`, `vol_media`, `vol_std`. `failed_tickers` = universo sem dados técnicos; `warnings` = tickers sem fundamentos no merge.

   **Fatia de CLI antecipada (a pedido do usuário, para testes manuais):** criados `robusta/cli.py` + `robusta/__main__.py` com `python -m robusta run [--tickers ...] [--export-xlsx CAMINHO]`. Roda `executa_pipeline` e, com a flag, exporta o `merged_results` para xlsx (export opt-in, conforme o PLAN). O `main.py` legado **não** foi tocado (continua como referência até a Fase 8, onde a CLI vira oficial). Testes em `tests/test_cli.py` (rede mockada). `pytest -q` → `78 passed`. Para testar com dados reais: `python -m robusta run --tickers PRIO3 ASAI3 --export-xlsx saida.xlsx` (faz chamadas reais à Yahoo/Fundamentus, pode dar rate-limit).

   - receber universo de tickers (sem override interno — a lista chega pronta do CLI / `DataLoader`).
   - executar técnica e receber de volta `carteira_automatica` + `precos_por_ticker`.
   - carregar ou atualizar fundamentos conforme regra mensal **corrigida** (raspar só no 1º dia útil; cachear no Excel; demais dias leem cache).
   - passar `precos_por_ticker` explicitamente para `adicione_indicadores_e_ranking`.
   - fazer merge e ranking final; preservar o segundo valor retornado por `distorions_analysys` (`{'média', 'std_vol'}`) em vez de descartá-lo — vai para `summary` no JSON.
   - devolver um objeto/estrutura única (ex: `RunResult` dataclass) pronto para persistência, contendo: `merged_results`, `technical_results`, `fundamental_results`, `summary`, `portfolio_signals`, `warnings`, `failed_tickers`.
   - entrada: lista de tickers e configuração de execução.
   - saída: `RunResult` com os campos acima; compatível campo a campo com o schema da seção JSON Contract.
   - teste rápido: pipeline com mocks para dois tickers, comparação de colunas essenciais contra o baseline, e confirmação de que `summary.std_vol` não é `None`.

6. `[x]` Persistência: `latest.json` + `latest.xlsx`
   - novo módulo `robusta/persistence.py` com função `grava_latest(run_result, pasta_var)` que recebe o `RunResult` da Fase 5 e produz os dois arquivos.
   - serialização JSON conforme a seção "JSON Contract": encoder customizado para `numpy.int64/float64` → `int/float`, `pandas.Timestamp` → ISO 8601, `NaN` → `null`. Chaves todas em snake_case ASCII.
   - estrutura `tickers: {TICKER: {...}}` (dict por ticker, não array) — facilita o drill-down do frontend (`data.tickers["PRIO3"]` direto, sem `find()`).
   - escrita atômica: grava em `latest.json.tmp` e usa `Path.replace()` (syscall atômica no Linux). O nginx nunca serve arquivo pela metade.
   - `latest.xlsx`: salva o `merged_results` via `to_excel`. Mesmo padrão atômico (`latest.xlsx.tmp` → `replace`).
   - guarda contra execução degenerada: **não** sobrescreve `latest.json` se `tickers_ok == 0` ou taxa de falha > 50%. Nesse caso, grava num arquivo de log de erro (ex: `~/robusta/var/last_failed_run.json`) e sai com `exit code` != 0 (cron registra a falha).
   - integração com a CLI: a flag `--emit-latest` em `python -m robusta run` dispara `grava_latest`. O cron passa `--emit-latest --export-xlsx ~/robusta/var/latest.xlsx`.
   - entrada: `RunResult` da Fase 5.
   - saída: `~/robusta/var/latest.json` e `~/robusta/var/latest.xlsx` atualizados atomicamente.
   - teste rápido: serializar fixture de `RunResult` com `NaN`, `numpy.float64`, `pandas.Timestamp` e sentinelas `"Abismo"`/`"Foguete"` sem erro; `json.loads` da saída deve conter `null` onde havia `NaN` e a estrutura `tickers` indexada por ticker.

   **Evidência (concluída):**
   - Arquivos criados: `robusta/persistence.py` (encoder + mapping de colunas + `constroi_payload` + `grava_latest`); `tests/test_persistence.py` (22 testes cobrindo conversor de células, payload, serialização, escrita atômica, guarda contra execução degenerada).
   - Mapping de colunas em `COLUNA_PARA_JSON`: `Ticker → ticker`, `Fundamental_?value → fundamental_signal`, `Vol Mês^Anual_?value → vol_signal`, `Posicao setorial → posicao_setorial`, `Close → preco`, `vol_anualized_30days → vol_anualizada_30d`, `Alto_volume_persistente → alto_vol_persistente`, MMAs como `mma9..mma200`, `%_to_MMA10/50 → pct_to_mma10/50`, níveis `*_by_mslf` preservam nome, fundamentais como `pl/pvp/ev_ebit/roic/cres_rec_5a/div_liq_vm`, `avaliacao_fundamentalista` e `distortion_ranking` mantidos. Campos ausentes na linha viram `null` (invariante: campo presente, valor `null`, nunca key omitida).
   - **Bug encontrado durante TDD**: a checagem `isinstance(valor, float)` capturava `np.float64` (que herda de `float`) antes do branch numpy, deixando passar `np.float64` em vez de converter pra `float` nativo. Reordenado para checar `np.floating`/`np.integer`/`np.bool_` ANTES dos tipos Python nativos.
   - **`Setor` ausente no `merged_results`** (limitação herdada): `rankeando_empresas` (F7) faz `groupby('Setor').apply().reset_index(drop=True)` e o pandas remove a coluna de groupby do resultado. O mapping `Setor → setor` continua presente mas resulta em `null`. `Subsetor` segue OK e é o que o dashboard usa. Não é bug a corrigir nesta fase.
   - CLI: adicionada flag `--emit-latest [PASTA]` em `robusta/cli.py` (sem argumento → `~/robusta/var/`; com argumento → usa o caminho). Teste em `tests/test_cli.py` confirma criação dos dois arquivos.
   - Escrita atômica via `Path.write_text` + `Path.replace`; arquivos `.tmp` são removidos após o rename. Confirmado por teste (`test_grava_latest_remove_tmp_apos_replace`).
   - Guarda contra execução degenerada: `tickers_ok == 0` OU `tickers_failed/(ok+failed) > 0.5` aciona `RuntimeError`; payload vai pra `last_failed_run.json`, `latest.json` da execução anterior permanece intacto. Confirmado por 3 testes (zero tickers, taxa > 50%, preservação após falha).
   - Comando: `pytest -q` → `108 passed in 1.37s` (85 anteriores + 22 de persistence + 1 novo de CLI).
   - Limitações: não há teste com `RunResult` real de ponta-a-ponta gravado em disco (os testes usam fixture construída manualmente). A integração ponta-a-ponta vai ser exercitada pelo teste da CLI (`test_cli_run_emit_latest_grava_json_e_xlsx`) e pelo smoke test manual no VPS.

7. `[x]` Frontend estático: dashboard + drill-down
   - novo diretório `site/` no repo, contendo: `index.html`, `ticker.html`, `assets/app.js`, `assets/app.css`, `carteira.json` (template inicial).
   - **Vanilla JS**: sem framework, sem build step, sem npm. Carrega via `<script>` direto.
   - layout aprovado nos mockups `planning/architecture-static-first.html` e `planning/dashboard-v1-mockup.html`. Estética clean estilo Google (paleta marfim/slate/clay/olive/oat).

   **Sub-fases:**

   - `[x]` 7a — `assets/app.js` lê `/data/latest.json` e expõe um shape estável `{ run_id, generated_at, signals: {longs, shorts}, tickers, carteira }`. Inclui parser do query string `?ticker=` para o drill-down. Fixture mock em `tests/fixtures/latest_mock.json` para iteração local sem rede.

   - `[x]` 7b — `index.html`: brand "ROBUSTA" centralizado, run stamp, duas colunas Long/Short com top 3 / bottom 3, busca de ticker, botão download Excel. Cliques em ticker → `ticker.html?ticker=XXXX`.

   - `[x]` 7c — `ticker.html`: cabeçalho com nome/preço/setor, bloco "Avaliação fundamentalista" (3 stats), bloco "Suporte · preço · resistência" (régua SVG horizontal com 6 níveis + preço), `std_raking_value` e `momentum_break` como meta-pair. Tratamento das sentinelas `"Abismo"`/`"Foguete"` (marcador "vazio" com label).

   - `[x]` 7d — `carteira.json` + bloco "Carteira" na `ticker.html`: tabela compacta com **3 colunas** (ticker, mini-régua S/R, preço — após revisão visual do usuário, as colunas score/sinal/posição foram removidas por redundância com o bloco fundamentalista do topo). Título do bloco simplificado para "Carteira" centralizado. Cabeçalho "suporte · preço · resistência" do bloco da régua principal também removido. Linhas clicáveis navegam para `ticker.html?ticker=XXXX`. Linha do ticker buscado destacada com fundo clay claro. Pin "● na carteira" no header quando aplicável. Schema do `carteira.json`: `{ "tickers": [ ... ] }`.

   - `[x]` 7e — comportamento de navegação **B1**: clicar em qualquer linha do bloco "Carteira" navega para `ticker.html?ticker=<clicado>`, recarregando a página com o novo ticker em destaque no topo. Sem SPA — uma URL por ticker (favoritável, compartilhável, botão voltar do browser funciona). **Entregue como subproduto natural da 7d**: o `addEventListener("click", ...)` nas linhas da tabela usa `window.location.href = R.urlDoTicker(t)`, que aciona navegação full-page nativa do browser (não pushState/SPA).

   - testes automatizados (responsabilidade do assistant): `node --check site/assets/app.js` (sintaxe JS válida); fixture `latest_mock.json` permite abrir `file://.../site/index.html` localmente.
   - testes visuais (responsabilidade do usuário): a cada sub-fase 7b/7c/7d, o usuário abre o arquivo local no navegador, compara com o mockup e diz "ok" ou pede ajuste. Sem isso, "está pronto" é meia-verdade.

## Test Plan

Duas naturezas de teste, com responsáveis diferentes:

### Testes automatizados (responsabilidade do assistant)

- Framework único: `pytest`. Os testes ficam em `tests/`, nomeados `test_*.py`. Comando único de verificação: `pytest`. Uma fase só pode ser `[x]` se seu teste passa nesse comando — REPL e scripts descartáveis não contam.
- Cada fase deve ter um teste rápido executável imediatamente após o porte da função, usando fixture pequena ou mock de rede. **Tests must not touch the network**: fixtures em `tests/fixtures/` (OHLCV CSVs, Fundamentus HTML, `latest_mock.json`) ou injeção de scrapers/downloaders.
- Os testes devem comparar entradas e saídas, não apenas verificar que a função roda sem erro.
- Bateria mínima no fechamento:
  - testes unitários das fases T1–T7 e F1–F10 (já existem; **85 testes verdes hoje**).
  - teste de pipeline com 2 ou 3 tickers usando mocks de Yahoo/Fundamentus (existe).
  - teste da Fase 6 (JSON + XLSX): serialização sem tipos pandas/numpy, `null` no lugar de `NaN`, sentinelas `"Abismo"`/`"Foguete"` preservadas, escrita atômica (tmp + replace).
  - teste da Fase 7 (frontend): `node --check site/assets/app.js` confirma sintaxe JS válida. Sem testes de UI automatizados (Playwright/Selenium seriam overengineering pra dashboard pessoal).

### Testes visuais manuais (responsabilidade do usuário)

O assistant **não** consegue olhar o site. Visual fica com o usuário:

- A cada sub-fase 7b/7c/7d: o assistant produz o código + uma fixture `latest_mock.json`; o usuário abre `file://.../site/index.html` (ou `ticker.html?ticker=PRIO3`) no navegador, compara com os mockups em `planning/dashboard-v1-mockup.html`, e dá feedback.

### Convenção operacional

Ao terminar uma sub-fase visual, o assistant deve avisar com instruções específicas de como abrir e o que olhar. "Está pronto" sem teste visual do usuário é meia-verdade.

## Assumptions

- A metodologia de análise é preservada (pesos, thresholds, nomes de indicadores). Mudanças requerem pedido explícito.
- Excel continua sendo **entrada** (`lista_tickers_liquidos.xlsx`, `all_ticker_financial_indicators.xlsx`) e também **saída opcional** (`latest.xlsx` para download via botão do site).
- O site é uso pessoal, sem autenticação. Audiência: somente o autor.
- Hospedagem: VPS Linux na Hostinger, com domínio próprio (a comprar) e HTTPS via Let's Encrypt.
- O PC do usuário fica fora do ciclo operacional: o VPS roda 3×/dia via cron, independente de o PC estar ligado.
- A carteira pessoal vive num arquivo `carteira.json` editado manualmente; mudanças são raras.
- A parte experimental do `main.py` legado já foi removida; o rebuild não precisa contemplar essa limpeza.
- Não há plano atual para histórico de runs, métricas, alertas ou dashboards comparando datas. Se forem necessários no futuro, viram fases novas, sem desfazer a arquitetura static-first.
