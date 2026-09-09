# Plano 017: API de análise

## Estratégia

Evoluir `POST /api/v1/search` de modo aditivo. O contrato existente ganhará o
discriminador `outcome`; os demais campos permanecerão estáveis. Uma função pura
classificará o estado final e o status HTTP, e outra limitará as métricas públicas
aos namespaces dos oito agentes.

Exceções inesperadas durante `workflow.ainvoke` serão convertidas na própria rota
em uma resposta de análise 500, com código e mensagem estáveis. Assim o frontend
recebe o mesmo formato estrutural sem ter acesso ao conteúdo da exceção.

## Decisão de endpoint

- Evoluir: `POST /api/v1/search`.
- Preservar: `POST /api/v1/query-plans`, pois executa somente o Planner.
- Não criar: `/api/v1/analysis`, evitando duas rotas equivalentes.

## Etapas

1. Definir `AnalysisOutcome` e adicioná-lo ao contrato de resposta.
2. Mapear consulta inválida para HTTP 422 e classificar os seis desfechos.
3. Construir a resposta em função dedicada e filtrar métricas públicas.
4. Sanitizar exceções inesperadas com resposta 500 correlacionável.
5. Adicionar exemplos completos ao OpenAPI para 200, 422, 502, 503 e 500.
6. Cobrir helpers, contratos HTTP, ausência da rota duplicada e sanitização.
7. Integrar a API com o grafo compilado usando nós controlados.
8. Atualizar o README e executar a matriz de qualidade.

## Verificação

- Ruff check e format check dos arquivos alterados.
- mypy e import-linter.
- testes unitários com cobertura mínima de 80%.
- testes de integração controlados.
- regressão de testes, lint e build do frontend.

## Resultado da implementação

- `/api/v1/search` foi mantida como única rota do pipeline completo e recebeu o
  discriminador tipado `outcome` sem remover campos anteriores.
- Os seis desfechos possuem status e exemplos documentados no OpenAPI.
- Métricas não pertencentes aos oito agentes e valores não finitos são omitidos.
- Exceções inesperadas retornam um contrato 500 estável e correlacionável, sem o
  texto original da exceção.
- O teste integrado confirmou API, middleware, estado inicial, grafo compilado e
  interrupção antes de nós sem pré-condição.
- 350 testes offline e 6 integrações passaram.
- Ruff format/lint, mypy em 126 arquivos e os dois contratos do import-linter passaram.
- Teste, lint e build do frontend passaram.

## Correção validada em execução real

Um teste manual posterior revelou que `openai/gpt-oss-20b` produzia JSON completo,
mas marcava uma consulta executável como `needs_clarification` sem declarar uma
ambiguidade ou pergunta. O Parser agora normaliza esse caso de forma determinística:
sem filtro não resolvido, o plano se torna `ready`; com um par válido de filtro e
sugestões, a ambiguidade e a pergunta são derivadas do próprio valor não resolvido.
A normalização emite `query_status_normalized`. Estruturas incompletas ou pares
inconsistentes continuam inválidos e percorrem o reparo normal.

Uma segunda validação real encontrou incompatibilidade entre o escopo nacional
`Brazil` produzido pelo Planner e startups cuja coluna `location` contém a cidade.
Como o corpus é brasileiro e não possui coluna de país, `Brasil`/`Brazil` agora
representam ausência de restrição por cidade. Localizações específicas continuam
filtradas normalmente. O comportamento foi confirmado contra PostgreSQL com uma
startup de acessibilidade armazenada em `Maceió`.

Na execução completa, o Extractor revelou `finish_reason=length`: o limite implícito
de 2.048 tokens incluía 1.441 tokens de raciocínio e truncava o JSON. Os dois perfis
LLM agora configuram 8.192 tokens e modo `json_object`. O Extractor normaliza apenas
variações estruturais sem conteúdo factual (objeto em lista unitária, listas `null`
e `unknown_fields`, que é derivado dos fatos); fatos e citações permanecem sujeitos
à validação estrita.

A validação operacional também revelou que o CLI de conhecimento usava no
Windows uma política de event loop incompatível e que páginas oficiais podem
repetir blocos com o mesmo hash. O CLI agora seleciona a política compatível, o
chunker deduplica conteúdo dentro do documento e os testes de integração removem
seus próprios registros. A base local foi reconstruída e verificada com 19
documentos oficiais, 4.297 chunks/vetores, todas as 16 tecnologias e nenhuma
inconsistência.

Para reduzir perda de sinais antes da recomendação, o trecho padrão passou a
1.000 caracteres e o prompt do Extractor exige varredura de todos os campos e de
necessidades técnicas explícitas. O Validator processa no máximo 10 itens por
chamada e preserva os lotes já válidos caso uma chamada posterior fique
indisponível. O fluxo completo com todos os agentes reais e provedores falsos
continua coberto pela integração controlada; uma validação externa posterior foi
interrompida por indisponibilidade do Groq após os retries configurados, retornando
o erro sanitizado esperado.

## Sugestão de commit

`feat(api): expose typed full-pipeline analysis results`
