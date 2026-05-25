# Adversarial Review dos Documentos de Planejamento

Este review trata os arquivos `planning/*.md` como instruções executáveis e procura brechas que permitam cumprir a letra do plano enquanto se viola seu espírito. Escopo lido: `planning/PLAN.md`, `planning/PROJECT_BUILDING.md` e `planning/CODEX-REVIEW.md` vazio.

## Brechas Críticas

### 1. Hierarquia documental ainda não existe

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** há uma tarefa pendente para explicar que `PLAN.md` governa escopo, `CLAUDE.md` governa estilo e `BEHAVIORAL_GUIDELINES.md` governa processo, mas isso ainda não está definido.
- **Caminho de exploração:** quando `PLAN.md` disser para modularizar e outro documento sugerir cautela/simplicidade, escolher seletivamente a regra mais conveniente e alegar conformidade com algum documento.
- **Correção:** criar uma seção normativa de hierarquia com precedência explícita e comportamento em caso de conflito.

### 2. `CODEX-REVIEW.md` vazio vira aprovação tácita

- **Arquivo:** `planning/CODEX-REVIEW.md`
- **Brecha:** o arquivo existe, mas não contém critérios, achados ou status.
- **Caminho de exploração:** declarar que “não há problemas registrados no review” e avançar fases sem tratar riscos conhecidos.
- **Correção:** preencher o arquivo ou marcá-lo explicitamente como “não executado; não usar como aprovação”.

### 3. Referência a arquivo inexistente desloca responsabilidade

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** o plano aponta o catálogo completo de bugs para `docs/CODE-AND-PLAN-REVIEW.md`, que não está no diretório de planejamento e pode não existir.
- **Caminho de exploração:** corrigir apenas a lista curta do plano e ignorar outros bugs alegando que o catálogo externo não estava disponível.
- **Correção:** mover o catálogo para `planning/` ou incorporar a lista completa no próprio plano.

### 4. “Preservar metodologia” conflita com “corrigir bugs óbvios”

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** “não discutir nem redesenhar metodologia” e “corrigir bugs técnicos óbvios” não definem fronteira.
- **Caminho de exploração:** classificar uma mudança comportamental como bug técnico, ou recusar correção real dizendo que alteraria a tese analítica.
- **Correção:** definir exemplos positivos e negativos: o que pode mudar resultado numérico, o que só corrige execução e quem aprova mudanças ambíguas.

### 5. “Quando impedirem a intenção do código” é subjetivo

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** bugs técnicos só devem ser corrigidos quando impedirem a intenção, mas a intenção não é formalizada por testes, baseline ou invariantes.
- **Caminho de exploração:** deixar bugs que degradam silenciosamente resultados porque o programa ainda roda.
- **Correção:** transformar intenção em invariantes: universo vem do Excel, cache mensal segue regra, rankings não aceitam NaN silencioso, saída JSON sempre serializa.

### 6. Baseline humano permite validação fraca

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** a fase 1 pede “comparação humana” de amostra.
- **Caminho de exploração:** gerar amostra incompleta, comparar visualmente só colunas fáceis e marcar fase como validada.
- **Correção:** exigir fixture versionada, snapshot mínimo e critérios objetivos de comparação por coluna.

### 7. Checkbox `[x]` não exige evidência

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** fases podem ser marcadas como concluídas e validadas, mas não há campo obrigatório para comando, saída, data ou artefato.
- **Caminho de exploração:** marcar `[x]` após implementação parcial sem rodar o teste rápido.
- **Correção:** cada fase deve registrar “comando executado”, “resultado”, “arquivos alterados” e “limitações”.

### 8. “Teste rápido” é insuficientemente definido

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** testes rápidos são exigidos, mas não há framework obrigatório, local, padrão de nome ou condição de reprovação global.
- **Caminho de exploração:** executar testes manuais no REPL ou scripts descartáveis e considerar validado.
- **Correção:** exigir `pytest`, pasta `tests/`, nomes `test_*.py` e comando único de verificação.

### 9. `main.py` antigo como referência temporária não tem prazo

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** manter o arquivo antigo como referência temporária sem definir quando será removido ou congelado.
- **Caminho de exploração:** deixar lógica duplicada indefinidamente, criando divergência entre implementação modular e script legado.
- **Correção:** definir fim da referência: após fase 8, `main.py` deve ser somente CLI e o legado deve ir para arquivo arquivado ou tag Git.

### 10. Estrutura modular é opcional demais

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** “pacote interno `robusta/` ou poucos arquivos `.py` simples” permite quase qualquer decomposição.
- **Caminho de exploração:** criar módulos genéricos ou manter um monólito dividido artificialmente, alegando simplicidade.
- **Correção:** definir estrutura mínima obrigatória ou critérios objetivos para escolher pacote versus arquivos planos.

### 11. Contrato JSON não define schema formal

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** lista campos, mas não define obrigatoriedade, tipos aninhados exatos, ordenação, versionamento de schema ou erro para campo extra.
- **Caminho de exploração:** emitir JSON “parecido”, com campos opcionais ausentes, tipos mistos ou nomes divergentes, e alegar conformidade geral.
- **Correção:** criar `schema_version`, JSON Schema ou modelos Pydantic para `RunResult`.

### 12. `portfolio_signals` depende de nome inconsistente

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** o plano menciona `distorted_price_analysis`, enquanto o contexto existente também usa `distorions_analysys`.
- **Caminho de exploração:** implementar wrapper novo com comportamento diferente ou pular sinais por ambiguidade de função.
- **Correção:** fixar nome canônico, entrada, saída e mapeamento exato da função legada.

### 13. Saída Excel “não principal” ainda permite export oculto

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** Excel deixa de ser saída principal, mas não é proibido como efeito colateral.
- **Caminho de exploração:** continuar gerando Excel automaticamente além do JSON, preservando acoplamento antigo.
- **Correção:** declarar que export Excel automático é proibido no fluxo normal, salvo flag explícita.

### 14. “Warnings não fatais” pode mascarar falhas estruturais

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** `warnings` e `failed_tickers` são aceitos sem limite.
- **Caminho de exploração:** transformar falhas amplas de scraping, ranking ou serialização em warnings e ainda produzir `latest.json`.
- **Correção:** definir thresholds de falha: por exemplo, erro se `tickers_ok == 0`, se colunas obrigatórias faltarem ou se taxa de falha exceder limite.

### 15. API local sem autenticação não define superfície segura

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** “local” e “CORS localhost” não impedem bind em `0.0.0.0`, endpoints mutáveis ou vazamento de arquivos.
- **Caminho de exploração:** subir API acessível na rede local e dizer que CORS está restrito.
- **Correção:** exigir bind padrão em `127.0.0.1`, leitura apenas da pasta de runs e nenhum path arbitrário.

### 16. `POST /api/runs` opcional cria rota de escopo indefinido

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** endpoint opcional pode acionar análise pela API sem critérios de segurança, concorrência ou rate limit.
- **Caminho de exploração:** adicionar endpoint mutável prematuramente e abrir execução remota de chamadas externas caras.
- **Correção:** proibir na primeira fase ou exigir aprovação explícita, fila single-flight e proteção contra execução concorrente.

### 17. Scheduler “opcional” não define decisão

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** `schedule` é opcional, mas também aparece como comando do CLI e fase de limpeza.
- **Caminho de exploração:** implementar scheduler incompleto para satisfazer CLI, ou deixar comando quebrado por ser opcional.
- **Correção:** decidir se `schedule` entra no MVP. Se entrar, especificar comportamento e teste; se não, remover do contrato inicial.

### 18. Entradas Excel permanecem, mas validação é estreita

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** só confirma colunas `ticker` e `Ticker`.
- **Caminho de exploração:** aceitar arquivos com colunas mínimas mas valores vazios, duplicados, tickers inválidos ou tipos errados.
- **Correção:** validar schema completo, unicidade, normalização de ticker e erro claro para dados inválidos.

### 19. Normalização de ticker não cobre todos os casos

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** define base sem `.SA`, mas não fala de caixa, espaços, duplicatas, tickers fracionários ou sufixos já presentes.
- **Caminho de exploração:** deixar `PRIO3.SA.SA`, ` prio3 ` ou duplicatas passarem para o pipeline.
- **Correção:** criar função única `normalize_ticker()` com testes e uso obrigatório em IO, técnica, fundamentos e API.

### 20. “Manter assinaturas sempre que possível” permite exceções silenciosas

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** a expressão “sempre que possível” não exige justificativa.
- **Caminho de exploração:** alterar assinaturas de funções migradas e quebrar compatibilidade com baseline sem registrar motivo.
- **Correção:** toda alteração de assinatura deve aparecer em changelog da fase com motivo e impacto.

### 21. Remoção de Twilio não define limpeza completa

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** diz remover Twilio/WhatsApp do fluxo normal, mas não especifica remoção de imports, dependências, credenciais, docs e testes.
- **Caminho de exploração:** deixar credenciais ou função morta fora do fluxo e alegar remoção operacional.
- **Correção:** checklist explícito: sem credenciais hardcoded, sem import Twilio, sem chamada, sem dependência e sem documentação ativa.

### 22. Logs substituem prints sem padrão

- **Arquivo:** `planning/PLAN.md`
- **Brecha:** não define logger, níveis, formato nem política de dados sensíveis.
- **Caminho de exploração:** trocar `print` por `logging.warning` desordenado, ruidoso ou com dados indevidos.
- **Correção:** configurar logger por módulo, níveis esperados e mensagens sem segredos.

## Brechas no Processo de Planejamento

### 23. `PROJECT_BUILDING.md` mistura checklist, estratégia e pendências

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** o arquivo contém tarefas concluídas, futuras, anuladas e instruções normativas sem separação.
- **Caminho de exploração:** tratar itens pendentes como sugestões, ou itens concluídos como garantias sem verificar o estado real.
- **Correção:** separar roadmap, normas vigentes e histórico.

### 24. Legenda de status não tem semântica operacional

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** `a`, `f`, `x`, `n`, `r` são definidos, mas não dizem quem muda status, quando ou com qual evidência.
- **Caminho de exploração:** mover itens para `[f]` ou `[n]` para evitar implementação sem registrar decisão.
- **Correção:** exigir justificativa ao mudar status e registrar data/autor.

### 25. Duplicação de tarefas reduz clareza

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** tarefas como sinalizar arquivos da raiz e avaliar sandbox aparecem duplicadas.
- **Caminho de exploração:** marcar uma ocorrência como feita e deixar outra pendente, criando falsa impressão de progresso.
- **Correção:** deduplicar e dar ID estável para cada tarefa.

### 26. “Toda documentação em planning” conflita com arquivos na raiz e `docs/`

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** a regra diz que toda documentação estará em `planning/`, mas há `CLAUDE.md`, `BEHAVIORAL_GUIDELINES.md`, `REVIEW.md`, `AGENTS.md` e `docs/`.
- **Caminho de exploração:** ignorar documentos fora de `planning/` por estarem “fora do local oficial”, ou ignorar `planning/` usando os documentos raiz.
- **Correção:** definir quais documentos são normativos, quais são auxiliares e quais são legados.

### 27. “Preparar gitignore” pendente permite poluição de artefatos

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** `.gitignore` não está preparado, mas o plano gera JSON, Excel e possivelmente caches.
- **Caminho de exploração:** commitar outputs de execução, ambientes virtuais ou caches e alegar ausência de regra.
- **Correção:** criar `.gitignore` antes de fases que gerem artefatos.

### 28. Dependências não instaladas bloqueiam validação real

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** “Criar e instalar dependências” está pendente.
- **Caminho de exploração:** não rodar testes ou app por ambiente ausente, marcando validação como não executável.
- **Correção:** adicionar `requirements.txt` ou `pyproject.toml` como pré-requisito da fase 1.

### 29. Governança de Definition of Done está pendente

- **Arquivo:** `planning/PROJECT_BUILDING.md`
- **Brecha:** critérios de sucesso por fase ainda não existem em documento separado.
- **Caminho de exploração:** aceitar implementações que passam testes mínimos mas falham requisitos de manutenção, segurança ou documentação.
- **Correção:** criar `planning/DEFINITION_OF_DONE.md` antes de marcar fases do rebuild como concluídas.

## Correções Prioritárias

1. Criar hierarquia documental explícita e mover referências normativas para `planning/`.
2. Substituir critérios subjetivos por invariantes testáveis e schema formal.
3. Exigir evidência por checkbox concluído: comando, resultado, artefato e limitações.
4. Resolver referências quebradas (`docs/CODE-AND-PLAN-REVIEW.md`, `CODEX-REVIEW.md` vazio).
5. Definir escopo fechado para API, scheduler, Excel residual e Twilio.
