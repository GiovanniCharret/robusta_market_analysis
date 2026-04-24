# Plano De Rebuild Modular Do ROBUSTA

## Summary

Rebuild gradual do `main.py`, preservando a lógica empírica principal de análise técnica e fundamentalista, mas separando código por responsabilidade e trocando prints/exports Excel por uma saída JSON estável para consumo em HTML.

Decisões travadas:

- Persistência principal: arquivos JSON, funcionando como banco local simples.
- API: FastAPI local, servindo os JSONs para o futuro HTML.
- Rebuild: modular gradual, podendo dividir o `main.py` em mais de um `.py` quando isso simplificar o código.
- Entradas: manter `lista_tickers_liquidos.xlsx` e `all_ticker_financial_indicators.xlsx` nesta fase.
- WhatsApp/Twilio: removidos do rebuild.
- Análise: não discutir nem redesenhar metodologia; apenas portar e organizar.
- Bugs técnicos óbvios: corrigir quando impedirem a intenção do código, sem alterar a tese analítica.

## Key Changes

- Organizar o código por responsabilidades, seja em um pacote interno `robusta/` ou em poucos arquivos `.py` simples se isso for suficiente:
  - configuração e constantes: versão, janelas, tolerâncias, caminhos e calendário.
  - fontes de dados: leitura dos Excel atuais, Yahoo Finance e Fundamentus.
  - análise técnica: variação, médias móveis, volatilidade, volume persistente e concentração de preço.
  - análise fundamentalista: limpeza do Fundamentus, indicadores extras, classes e ranking.
  - pipeline: orquestração do fluxo completo técnico + fundamentalista + merge + ranking final.
  - persistência JSON: gravação de execuções, `latest.json` e metadados.
  - API FastAPI: endpoints JSON para o HTML.

- Transformar `main.py` em CLI simples:
  - `python main.py run`: executa uma análise e grava JSON.
  - `python main.py api`: sobe a API local.
  - `python main.py schedule`: opcional, roda nos horários configurados sem overrides de debug.

- Remover do fluxo normal:
  - credenciais Twilio.
  - função `send_whatsapp_messages`.
  - prints de progresso como saída de produto.
  - exports automáticos para Excel como saída principal.

- Corrigir bugs técnicos conhecidos durante o porte (catálogo completo em `docs/CODE-AND-PLAN-REVIEW.md`):
  - remover download incondicional de `GOAU3` em `extrai_cotacoes`.
  - trocar atribuições com `:` por `=` em `add_price_concentration_levels_by_me` e dar `return df` explícito (hoje a função retorna `None` e o caller reatribui).
  - remover override fixo de `hora_atual = "19:00"` e `eh_dia_util = True`.
  - remover override silencioso de `ticker_list = {'ticker':['PRIO3','ASAI3','LREN3']}` em `gere_df_principal` — a lista lida do Excel deve ser a única fonte de universo.
  - inverter a lógica de cache de fundamentos em `gere_df_principal`: raspar Fundamentus no 1º dia útil do mês e salvar; nos demais dias, carregar do Excel cacheado. Hoje está trocado.
  - importar a exceção correta no retry do Yahoo: `from yfinance.exceptions import YFRateLimitError` (ou capturar `Exception` genérico). Hoje o `except YFRateLimitError` lança `NameError` no primeiro rate-limit.
  - atribuir o retorno de `.fillna(0)` nas funções de ranking fundamentalista (linhas ~1085 e ~1112); hoje o resultado é descartado e NaNs contaminam `avaliacao_fundamentalista`.
  - proteger `pandas.qcut(..., 10)` com `duplicates='drop'` ou fallback, para universos pequenos e indicadores com muitos empates (ex: ROIC = 0).
  - corrigir filename `' carteira_automatica.xlsx'` (espaço inicial) em `gere_df_principal`.
  - avaliar remoção de `concatene_analises_tecnicas` (referencia `last_line` indefinido e não é chamada) — confirmar antes de excluir.
  - substituir `pandas.concat` em loop dentro de `varre_lista` por acumulação em lista + `concat` único.
  - tratar variáveis globais como estado explícito do pipeline, não como dependência invisível.

## JSON And API Contract

- Cada execução gera um arquivo JSON em formato orientado a registros:
  - `run_id` — string determinística por timestamp (ex: `2026-04-24T19-00-00Z`).
  - `generated_at` — ISO 8601 UTC.
  - `robusta_version` — string vinda de `config.VERSION`, fonte única (hoje há divergência entre `versao = "12.3.1"` e docstring `"ROBUSTA - 13"`).
  - `input_universe` — lista de tickers base (sem `.SA`) efetivamente analisados.
  - `summary` — objeto com contagens (`tickers_ok`, `tickers_failed`), média e desvio padrão de volatilidade (hoje descartados por `distorions_analysys`), e demais metadados agregados.
  - `technical_results` — lista de registros, um por ticker, com as colunas do DataFrame técnico final (tipos primitivos JSON).
  - `fundamental_results` — lista de registros, um por ticker, com as colunas do DataFrame fundamentalista após ranking.
  - `merged_results` — lista de registros, um por ticker, equivalente ao `carteira_automatica` pós-merge e ranking cross-sectional.
  - `portfolio_signals` — resultado de `distorted_price_analysis` (top 5 longs e top 5 shorts), herdeiro do que antes ia para o WhatsApp.
  - `warnings` — lista de strings com avisos não fatais (ex: `qcut` caiu em fallback, ticker sem fundamentos).
  - `failed_tickers` — lista de objetos `{ticker, reason}`.

- Convenções de serialização:
  - `NaN`/`None` → `null` JSON (campo presente, valor `null`), não campo omitido.
  - `pandas.Timestamp` → ISO 8601 string.
  - `numpy.int64`/`numpy.float64` → `int`/`float` nativos; encoder customizado obrigatório (`json.dumps` padrão lança `TypeError`).
  - Chaves de dicionário sempre string.

- `latest.json` replica a execução mais recente (cópia, não symlink) para consumo direto pelo HTML.

- Handoff interno técnica → fundamentalista:
  - Contrato: `Dict[str, float]` mapeando ticker base (`PRIO3`) → último preço de fechamento.
  - A fase técnica produz e normaliza a chave (remove `.SA`); a fase fundamentalista consome sem saber da Yahoo.
  - Tipo definido em `config.py` ou módulo de tipos; passado como argumento explícito, não como global.

- Endpoints FastAPI mínimos:
  - `GET /api/health`: status da API e versão.
  - `GET /api/runs/latest`: resultado consolidado mais recente.
  - `GET /api/runs`: lista execuções disponíveis.
  - `GET /api/runs/{run_id}`: execução específica.
  - `GET /api/tickers/{ticker}`: dados consolidados de um ticker na execução mais recente.
  - `GET /api/signals`: atalho para `portfolio_signals` da execução mais recente.

- O HTML futuro não dependerá de pandas, Excel ou prints; ele consumirá somente JSON.

## Implementation Plan

Legenda de status por fase:

- `[ ]` — não iniciada
- `[~]` — em andamento
- `[x]` — concluída e validada com teste rápido

Estado atual: todas as fases em `[ ]`. Executor deve atualizar o checkbox da fase imediatamente após o terminar o build.

1. `[ ]` Criar baseline de segurança:
   - manter `main.py` antigo como referência temporária.
   - registrar quais colunas finais existem hoje em `carteira_automatica` e no merge final.
   - criar fixtures pequenas com 2 ou 3 tickers para comparar o rebuild sem rodar toda a B3.
   - teste rápido: rodar uma execução reduzida com 2 ou 3 tickers e salvar uma amostra de colunas/valores finais para comparação humana.

2. `[ ]` Extrair configuração e IO:
   - centralizar caminhos dos Excel, pasta de JSON, versão, janelas e listas de médias.
   - encapsular leitura de tickers e fundamentos cacheados. O `DataLoader` de fundamentos deve raspar Fundamentus **somente** no 1º dia útil do mês e salvar cache; nos demais dias, carregar do cache (inverso do bug atual).
   - encapsular chamadas Yahoo/Fundamentus com retries e erros explícitos. Importar `YFRateLimitError` corretamente (ou capturar `Exception`).
   - remover override de universo: a lista lida do Excel passa direto ao pipeline; qualquer filtro (ex: subset manual para debug) fica atrás de flag explícita de CLI.
   - entrada: caminhos atuais dos Excel e parâmetros que hoje estão como globais.
   - saída: mesmos objetos usados pelo fluxo atual, como DataFrame de tickers, DataFrame de fundamentos cacheados e constantes acessíveis por importação.
   - teste rápido: carregar `lista_tickers_liquidos.xlsx` e confirmar coluna `ticker`; carregar `all_ticker_financial_indicators.xlsx` e confirmar coluna `Ticker`; mock de data dentro/fora do 1º dia útil confirmando que só raspa no 1º dia útil.

3. Extrair análise técnica em fases pequenas:
   - regra de porte: migrar uma função por fase. Só juntar duas funções quando a união criar uma única função mais simples e mais fácil de debugar.
   - manter os objetos de retorno atuais. Se uma função hoje retorna DataFrame, ela continua retornando DataFrame; se retorna `False` ou lista, esse contrato permanece até uma fase posterior explicitamente planejada.
   - `[ ]` fase T1, `crie_variacao(stock_data, info)`: entrada DataFrame OHLCV e `info`; saída mesmo DataFrame com `Return` ou `Oscillation`. Teste rápido: DataFrame de 3 fechamentos conhecidos e comparação direta do `pct_change`.
   - `[ ]` fase T2, `crie_medias_moveis(stock_data, lista_args)`: entrada DataFrame com `Close` e lista de janelas; saída mesmo DataFrame com `MMA{n}`, `Position_MMA{n}` e `%_to_MMA{n}`. Teste rápido: janela curta `[2]` com valores conhecidos e checagem da média, posição e distância.
   - `[ ]` fase T3, `calcule_volatilidade_anualizada(dados, vol_window)`: entrada DataFrame com `Return`; saída mesmo DataFrame com `vol_anualized_{vol_window}days`. Teste rápido: série curta de retornos e comparação com `rolling.std() * sqrt(252)`.
   - `[ ]` fase T4, `alto_volume_persistente(df)`: entrada DataFrame com `Volume` e `Close`; saída mesmo DataFrame com `Alto_volume_persistente`. Teste rápido: fixture com dois dias consecutivos de volume alto e preço subindo/caindo para validar `1` e `-1`.
   - `[ ]` fase T5, `add_price_concentration_levels_by_me(df)`: entrada DataFrame OHLCV com `Adj Close`, `High` e `Low`; saída **DataFrame modificado com `return df` explícito** (hoje retorna `None`), acrescido das colunas `sup_*_by_mslf`, `res_*_by_mslf`, `std_raking_value_by_mslf` e `momentum_break_by_mslf`. Corrigir o bug de `:` usado no lugar de `=`. Teste rápido: fixture com edges conhecidos, confirmação de que as colunas são criadas e de que o retorno não é `None`.
   - `[ ]` fase T6, `extrai_cotacoes(ticker)`: entrada ticker Yahoo no formato `PRIO3.SA`; saída preservada como `False` em falha ou `[ticker, stock_data]` em sucesso. Remover o `yfinance.download('GOAU3')` incondicional e importar `YFRateLimitError`. Teste rápido: mock de download retornando DataFrame válido, mock vazio, e mock que lança `YFRateLimitError` para validar os três caminhos sem acessar rede.
   - `[ ]` fase T7, `screener(lista, carteira_automatica)`: entrada lista de tickers base e DataFrame acumulador; saída DataFrame consolidado `carteira_automatica` **e** `Dict[str, float]` de últimos preços por ticker base (handoff explícito para F3). Teste rápido: mock de `extrai_cotacoes` com dois tickers e confirmação de duas linhas finais + dicionário de preços com chaves sem `.SA`.

4. Extrair análise fundamentalista em fases pequenas:
   - regra de porte: migrar uma função por fase, mantendo assinatura e retorno sempre que possível para facilitar comparação humana.
   - `[ ]` fase F1, `puxar_dados(url)`: entrada URL do Fundamentus; saída lista de tabelas conforme `pandas.read_html`. Teste rápido: mock de HTML com uma tabela mínima e confirmação de lista não vazia.
   - `[ ]` fase F2, `formatar_tabela(tables)`: entrada lista de tabelas do Fundamentus; saída DataFrame transposto e limpo, com coluna `ticker`/`Ticker` conforme padronização definida no porte. Teste rápido: fixture com tabela pequena contendo `Papel`, `Setor`, `LPA` e valores brasileiros para validar limpeza e conversão numérica.
   - `[ ]` fase F3, `gera_indicadores_extras(dados_financeiro_all_tickers, precos_por_ticker)`: entrada DataFrame fundamentalista e **`Dict[str, float]` de ticker base → último preço** (contrato definido em Fase 2, produzido em T7); saída mesmo DataFrame com `P/L`, `Dív. Líquida/Valor de mercado` e `P/VP`. Teste rápido: uma linha com `LPA`, `VPA`, `Nro. Ações`, `Dív. Líquida` e preço mockado para conferir as três contas; teste adicional confirmando que a função não lê `data_cache_backtest` global e não concatena `.SA` internamente.
   - `[ ]` fase F4, `rankeia_outros_indicadores_maior_melhor(...)`: entrada DataFrame e nomes de indicadores; saída mesmo DataFrame com colunas `classe {indicador}`. Usar `pandas.qcut(..., duplicates='drop')` e atribuir o resultado de `.fillna(0)`. Teste rápido: 10 valores crescentes e confirmação de classes 1 a 10; fixture com muitos empates (ex: 8 zeros e 2 positivos) confirmando que não levanta `ValueError`.
   - `[ ]` fase F5, unificar rankings `menor_melhor`: entrada DataFrame, indicadores e política de negativo (`neg_permitido` ou `neg_bloqueado`); saída mesmo DataFrame com classes invertidas e, quando aplicável, negativos penalizados. Mesma proteção de `qcut` e atribuição de `fillna`. Teste rápido: um caso com 10 valores crescentes para confirmar que o menor recebe classe 10 e outro caso com valor negativo, baixo positivo e alto positivo para garantir que negativo não vira melhor classe quando bloqueado.
   - `[ ]` fase F6, `avaliacao_fundamentalista(dados_financeiro_all_tickers)`: entrada DataFrame com classes e setor; saída mesmo DataFrame com `avaliacao_fundamentalista`. Teste rápido: uma empresa de setor especial e uma geral para validar soma das colunas corretas.
   - `[ ]` fase F7, `rankeando_empresas(dados_financeiro_all_tickers)`: entrada DataFrame com `Setor` e `avaliacao_fundamentalista`; saída mesmo DataFrame com `Posicao setorial`. Teste rápido: dois setores com melhor/pior conhecidos.
   - `[ ]` fase F8, `avaliacao_fundamentalista_analisys(dados_financeiro_all_tickers)`: entrada DataFrame com `avaliacao_fundamentalista`; saída mesmo DataFrame com `Fundamental_?value`. Teste rápido: valores 14, 15, 31 e 32 para validar fronteiras.
   - `[ ]` fase F9, `adicione_indicadores_e_ranking(all_ticker_financial_indicators, precos_por_ticker)`: entrada DataFrame fundamentalista bruto/cacheado + dicionário de preços; saída DataFrame enriquecido e sem colunas `Unnamed`. Teste rápido: fixture pequena passando por todas as funções F3-F8 com preços mockados.
   - `[ ]` fase F10, `varre_lista(lista)`: entrada lista de tickers base; saída DataFrame consolidado de fundamentos. Substituir `pandas.concat` em loop por acumulação em lista + `concat` único no final. Teste rápido: mock de `puxar_dados` para dois tickers e confirmação de duas linhas consolidadas.

5. `[ ]` Criar pipeline consolidado:
   - receber universo de tickers (sem override interno — a lista chega pronta do CLI / `DataLoader`).
   - executar técnica e receber de volta `carteira_automatica` + `precos_por_ticker`.
   - carregar ou atualizar fundamentos conforme regra mensal **corrigida** (raspar só no 1º dia útil; cachear no Excel; demais dias leem cache).
   - passar `precos_por_ticker` explicitamente para `adicione_indicadores_e_ranking`.
   - fazer merge e ranking final; preservar o segundo valor retornado por `distorions_analysys` (`{'média', 'std_vol'}`) em vez de descartá-lo — vai para `summary` no JSON.
   - devolver um objeto/estrutura única (ex: `RunResult` dataclass) pronto para persistência, contendo: `merged_results`, `technical_results`, `fundamental_results`, `summary`, `portfolio_signals`, `warnings`, `failed_tickers`.
   - entrada: lista de tickers e configuração de execução.
   - saída: `RunResult` com os campos acima; compatível campo a campo com o schema da seção JSON And API Contract.
   - teste rápido: pipeline com mocks para dois tickers, comparação de colunas essenciais contra o baseline, e confirmação de que `summary.std_vol` não é `None`.

6. `[ ]` Criar persistência JSON:
   - converter DataFrames para records JSON com `orient='records'` e datas serializadas em ISO.
   - encoder customizado obrigatório para `numpy.int64/float64`, `pandas.Timestamp` e `NaN → null` (contrato definido na seção JSON And API Contract).
   - gravar execução com `run_id` determinístico por timestamp.
   - gravar/atualizar `latest.json` como cópia (não symlink).
   - incluir avisos e tickers com falha sem quebrar a execução inteira.
   - incluir `portfolio_signals` (top 5 long / top 5 short) vindos de `distorted_price_analysis`.
   - entrada: `RunResult` da Fase 5.
   - saída: arquivo JSON de execução e `latest.json`.
   - teste rápido: serializar fixture com datas, floats, `NaN`, `numpy.float64` e `pandas.Timestamp` sem erro; e `json.loads` da saída deve conter `null` onde havia `NaN`.

7. `[ ]` Criar API FastAPI:
   - servir os arquivos JSON já gravados.
   - não recalcular análise em requests de leitura.
   - CORS restrito a `localhost` desde o início.
   - incluir `GET /api/signals` apontando para `portfolio_signals` da execução mais recente.
   - expor endpoint opcional `POST /api/runs` apenas se for desejado acionar uma nova análise pela API; por padrão, execução fica no CLI.
   - entrada: arquivos JSON persistidos.
   - saída: respostas HTTP JSON.
   - teste rápido: `GET /api/health`, `GET /api/runs/latest`, `GET /api/signals` e `GET /api/tickers/{ticker}` retornando 200 em fixture local.

8. `[ ]` Limpar execução:
   - `main.py` vira apenas CLI.
   - scheduler fica explícito e desativável; remover overrides de `hora_atual = "19:00"` e `eh_dia_util = True`.
   - remover `send_whatsapp_messages` e credenciais Twilio hardcoded.
   - logs substituem prints.
   - Twilio e WhatsApp ficam fora.
   - entrada: argumentos de linha de comando (`run`, `api`, `schedule`).
   - saída: execução do pipeline, servidor local ou scheduler.
   - teste rápido: `python main.py --help` e `python main.py run --tickers PRIO3 ASAI3 --dry-run` sem efeitos colaterais fora dos arquivos esperados.

## Test Plan

- Cada fase deve ter um teste rápido executável imediatamente após o porte da função, usando fixture pequena ou mock de rede.
- Os testes devem comparar entradas e saídas, não apenas verificar que a função roda sem erro.
- Enquanto o porte estiver em andamento, usar testes focados por função antes de criar testes integrados maiores.
- No fechamento do rebuild, manter uma bateria mínima:
  - testes unitários das fases T1-T7 e F1-F10.
  - teste de pipeline com 2 ou 3 tickers usando mocks de Yahoo/Fundamentus.
  - teste de JSON garantindo serialização sem tipos pandas/numpy.
  - teste de API garantindo HTTP 200 nos endpoints principais.
  - teste de CLI garantindo que `main.py` dispara o caminho correto sem depender de scheduler.

## Assumptions

- A metodologia de análise atual será preservada, inclusive pesos, thresholds e nomes de indicadores, salvo correções técnicas óbvias.
- Excel continuará sendo entrada nesta fase, mas não será saída principal.
- O HTML será construído depois em cima da API JSON; este plano prepara o contrato e a infraestrutura de dados.
- Não haverá autenticação na API local nesta primeira fase.
- A parte experimental que ficava no final do arquivo já foi removida do script atual; o rebuild não precisa mais contemplar essa limpeza.
