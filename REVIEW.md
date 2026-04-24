# ROBUSTA — Review Executivo

**Pitch em uma linha:** screener quant brasileiro que une análise técnica multi-janela e ranking fundamentalista decil-a-decil em um único sinal acionável, rodando diariamente sobre a B3.

## Por que importa

- **Decisão em segundos, não em planilhas** — combina 6 médias móveis, volatilidade anualizada, volume persistente e suportes/resistências proprietários (`by_mslf`) em um só veredito técnico por ticker.
- **Fundamentalismo com disciplina estatística** — cada indicador vira classe decil via `pandas.qcut`, e a soma dessas classes produz o `avaliacao_fundamentalista`: um score objetivo, comparável entre setores.
- **Híbrido técnico + fundamentalista** — o merge final cruza os dois mundos e ainda adiciona ranking cross-sectional de distorções, o diferencial que nenhum screener aberto brasileiro entrega pronto.
- **Arquitetura pronta para evoluir** — o `docs/PLAN.md` já tem rebuild modular aprovado: saída JSON, API FastAPI local, CLI limpo. O produto está na iminência de virar dashboard.

## Destaques

| Capacidade | Entrega |
|---|---|
| Universo | Tickers líquidos da B3 via `lista_tickers_liquidos.xlsx` |
| Frequência | Scheduler diário 14:56 / 19:00 (Brasília) |
| Saída atual | Excel consolidado; **em breve** JSON + API |
| Extensibilidade | Algoritmo proprietário de concentração de preço já embarcado |

## Roadmap visível

Rebuild modular em 8 fases com checkboxes rastreáveis (T1–T7 técnica, F1–F10 fundamentalista) — transparência total sobre o que está pronto e o que vem a seguir.

---

*ROBUSTA 12.3.1 — Reborn Stronger. A decisão quantitativa acessível ao investidor brasileiro.*
