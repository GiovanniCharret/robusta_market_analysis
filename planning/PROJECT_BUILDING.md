# OBJECTIVE

Estruturar o desenvolvimento via arquitetura de projetos com IA para tornar eficazes os outputs.

## Glossário

a - anulado
f - Revisão Futura
x - concluído
n - Não se aplica
r - Rollback - falhou

## Fases

[x] - Construir pasta planning E criar arquivo PLAN.md
[x] - Escrever no CLAUDE.md que toda a documentação estará em `planning` directory e o key document is PLAN.md
[x] - Criar o hook de revisão por outra IA (Kimi, Codex) e escrever em REVIEW.md
[x] - Criar uma pesquisa do plano equivalente ao texto abaixo:
    - "Realize uma pesquisa abrangente(...) e escreva documentos no diretório de planejamento em XXX_API.md"
    - "Pesquise API. Escreva a documentação com exemplos de código"
    - "Use isso para projetar a API em Python que deve ser usada para XXXX. Documente isso em XXX.md"
    - Por fim, documente a estrutura de código para [OBJETIVO]
[f] - Criar novo arquivo com a estrutura do backend em detalhes, com code snippets mais exemplo, de todas funcionalidades, escreva tudo em XXX_BACKEND.md
[x] - Subplanos dentro do plano para cada grande marco de implementação com certificação de bons testes em cada subplano
[x] - Prepara o Github
[ ] - Preparar o gitignore
[x] - Crie a pasta bug_fix
[x] - Usar Skill SDD para planejas as fases e subfases. GSD, feature-dev e superpowers são bons exemplos
[n] - Definir se o projeto usará single ou mult agents
[x] - Adicionar BEHVIORAL_GUIDELINES à pasta do projeto e no claude.
[x] - Após o /init - Leia todo o conteúdo de planning/. Depois, escreva o planning/ADVERSARIAL_REVIEW.md, que testa as falhas e ambiguidades do script: "Aja como um adversário maximamente competente. Sua tarefa é encontrar todas as ambiguidades, lacunas semânticas e formulações suaves neste documento que permiritiram a você seguir tecnicamente a refra enquanto viala seu espírito. Liste cada brecha com o caminho de exploração específico".
[ ] - Solicitar que desenvolvimento do site seja feito em pequenas partes para facilitar o teste humano.
[ ] - Mapa de testes (o que teste e como testar) escrito em um arquivo TESTES.md. Explica o teste de cada fase caso queira repetir. 
[a] - Avaliar o plugin caveman no projeto
[a] - Comparar arquitetura atual e clean Architecture
[a] - sinalizar arquivos da raiz que NÃO SÃO entradas
[a] - Avaliar usar sandbox e WSL2/VSCODE Ubuntu para execução
[a] - Criar e instalar dependências
[x] - Governança de desenvolvimento - Explica critérios de sucesso de cada fase em `definition of done.md` para humanos poderem acompanhar.
[x] - sinalizar arquivos da raiz que NÃO SÃO entradas 
[x] - Criar a pasta script_antigos e informar ao claude para ignorar a pasta
[x] - Clonar o repositório do thariq https://github.com/ThariqS/html-effectiveness. Crie um html de [tarefa] inspirados nos modelos disponíveis em html-effectveness/ para aumentar minha compreensão das suas atividades e a eficiência das minhas decisões.
