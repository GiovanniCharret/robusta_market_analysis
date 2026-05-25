# Baseline de colunas — ROBUSTA (Fase 1)

Este documento registra, **por analise estatica do `main.py` legado**, quais
colunas o fluxo atual produz. As fases seguintes do rebuild comparam suas
saidas contra esta lista, coluna a coluna.

Nao foi feito um snapshot de *valores* de uma execucao real: o `main.py` legado
depende de dados ao vivo da Yahoo/Fundamentus (nao reproduziveis) e nem roda
ate o fim (ver "Bugs conhecidos"). O baseline reproduzivel e: este schema +
as fixtures sinteticas de `tests/fixtures/`.

`main.py` legado e mantido como referencia ate o fim do porte — **nao apagar**.

---

## 1. DataFrame tecnico (`carteira_automatica` apos `screener`)

Cada ticker contribui com `tail(1)` do DataFrame montado por `extrai_cotacoes`.
Sequencia de funcoes e colunas que cada uma acrescenta:

| Origem | Colunas |
|---|---|
| `yfinance.download(auto_adjust=False)` + `reset_index` | `Date`, `Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume` |
| `insert(1, 'Ticker', ...)` | `Ticker` |
| `crie_variacao(df, 1)` | `Return` |
| `crie_medias_moveis(df, (9,10,26,50,150,200))` | para cada `n`: `MMA{n}`, `Position_MMA{n}`, `%_to_MMA{n}` |
| `calcule_volatilidade_anualizada(df, 30)` | `vol_anualized_30days` |
| `alto_volume_persistente(df)` | `Alto_volume_persistente` |
| `add_price_concentration_levels_by_me(df)` | **(deveria criar 8 colunas `*_by_mslf` — nao cria, ver bug B1)** |

**Total atual: 29 colunas.** Ordem completa:

```
Date, Ticker, Open, High, Low, Close, Adj Close, Volume, Return,
MMA9, Position_MMA9, %_to_MMA9,
MMA10, Position_MMA10, %_to_MMA10,
MMA26, Position_MMA26, %_to_MMA26,
MMA50, Position_MMA50, %_to_MMA50,
MMA150, Position_MMA150, %_to_MMA150,
MMA200, Position_MMA200, %_to_MMA200,
vol_anualized_30days, Alto_volume_persistente
```

Apos corrigir o bug B1, somam-se 8 colunas (total 37):

```
sup_min_by_mslf, sup_med_by_mslf, sup_max_by_mslf,
res_min_by_mslf, res_med_by_mslf, res_max_by_mslf,
std_raking_value_by_mslf, momentum_break_by_mslf
```

> O rebuild **deve** produzir essas 8 colunas (Fase T5 corrige o bug).

---

## 2. DataFrame fundamentalista (apos `adicione_indicadores_e_ranking`)

Parte do DataFrame transposto de `formatar_tabela` (colunas vindas do
Fundamentus — variam conforme a pagina; pass-through) e recebe:

| Origem | Colunas |
|---|---|
| `formatar_tabela` | `ticker` (renomeado de `Papel`), `Setor`, `Subsetor`, `LPA`, `VPA`, `Nro. Ações`, `Dív. Líquida`, `ROIC`, `EV / EBIT`, `Cres. Rec (5a)`, demais indicadores da pagina |
| `gera_indicadores_extras` | `P/L`, `Dív. Líquida/Valor de mercado`, `P/VP` |
| `rankeia_outros_indicadores_maior_melhor` | `classe Cres. Rec (5a)`, `classe ROIC` |
| `rankeia_..._menor_melhor_neg_permitido` | `classe Dív. Líquida/Valor de mercado` |
| `rankeia_..._menor_melhor_neg_bloqueado` | `classe P/L`, `classe P/VP`, `classe EV / EBIT` |
| `avaliacao_fundamentalista` | `avaliacao_fundamentalista` |
| `rankeando_empresas` | `Posicao setorial` |
| `avaliacao_fundamentalista_analisys` | `Fundamental_?value` |
| (final) | colunas `Unnamed*` sao removidas |

---

## 3. Merge final (`gere_df_principal`)

`carteira_automatica.merge(all_ticker_financial_indicators, on='Ticker', how='left')`
seguido de `distorions_analysys`, que acrescenta:

```
%_to_MMA50_Categoria, %_to_MMA10_Categoria, Vol Mês^Anual_?value
```

Resultado final = todas as colunas tecnicas + todas as fundamentalistas +
essas 3. `distorions_analysys` tambem devolve `{'média', 'std_vol'}`, hoje
descartado (Fase 5 preserva para o `summary` do JSON).

---

## Bugs conhecidos que afetam o baseline

- **B1 — `add_price_concentration_levels_by_me`**: linhas 718-725 usam `:` no
  lugar de `=`, entao as 8 colunas `*_by_mslf` **nao** sao criadas. A funcao
  da `return df`. Fase T5 corrige.
- **B2 — merge `Ticker` vs `ticker`**: `formatar_tabela` renomeia `Papel` ->
  `ticker` (minusculo), mas `gere_df_principal` faz merge `on='Ticker'`. Os
  nomes nao batem; a padronizacao da chave deve ser resolvida nas Fases F2/5.
- **B3 — fluxo nao chega ao fim**: `except YFRateLimitError` (nome nao
  importado) e `send_whatsapp_messages` (client Twilio comentado) impedem uma
  execucao completa do `main.py` legado. Por isso o baseline e estatico.

A lista completa de bugs a corrigir no porte esta em `planning/PLAN.md`.
