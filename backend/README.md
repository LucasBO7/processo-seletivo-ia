# Backend do NVIDIA Startup AI Radar

Fundação assíncrona e modular descrita na especificação `002-backend-foundation`.
Os comandos operacionais estão documentados no README da raiz do repositório.

## Modelos Groq

A aplicação disponibiliza dois perfis de chat reutilizáveis por meio do contrato
interno `ChatModel`:

- `llm_fast`: `openai/gpt-oss-20b`, temperatura `0`;
- `llm_heavy`: `openai/gpt-oss-120b`, temperatura `0.1`.

Defina `GROQ__API_KEY` no arquivo `.env` local antes de iniciar a composição
completa da aplicação. O valor não deve ser versionado nem registrado em logs.
Modelos, temperaturas, timeouts e retentativas podem ser substituídos pelos
grupos `LLM_FAST__` e `LLM_HEAVY__`.
Como os IDs publicados pela Groq possuem ciclo de vida próprio e podem depender
das permissões da conta, qualquer substituição deve ser validada no ambiente
antes de ser promovida.

O Query Planner, Extractor, Evidence Validator e NVIDIA RAG usam o perfil rápido.
Startup Classifier, Recommendation e Briefing usam o perfil pesado. O Retriever
executa somente código de recuperação e não recebe LLM.

## Base NVIDIA

A spec 012 adiciona uma ingestão independente do LangGraph. O manifesto
`scripts/nvidia_sources.json` cobre NVIDIA Inception, NIM, NeMo, NeMo Guardrails,
Triton, TensorRT-LLM, RAPIDS, cuDF, cuML, CUDA, Riva, Omniverse, Isaac, Clara,
Morpheus e NVIDIA AI Enterprise.

Use `startup-radar-knowledge ingest`, `dry-run` ou `verify`. O texto e a URL
oficial em `knowledge_documents.source_url` permanecem canônicos no PostgreSQL;
Qdrant e BM25 são índices derivados. Testes comuns usam fixtures e embeddings
falsos e não acessam a rede.

## Query Planner

O Query Planner é um nó assíncrono que depende somente do contrato interno
`ChatModel`. Ele transforma `AppState.query` em um `QueryPlan` estrito com status
`ready`, `needs_clarification` ou `invalid`, filtros separados e estratégia de
análise. Entradas inválidas são rejeitadas antes do modelo e respostas malformadas
possuem no máximo uma tentativa configurável de reparo.

Setor, estágio e porte usam Enums canônicos. Aliases conhecidos são
normalizados; um filtro explícito desconhecido produz `needs_clarification`,
`unresolved_filters` e três `filter_suggestions` válidas. Consultas que não
solicitam filtros permanecem exploratórias e executáveis.

Os limites não sensíveis ficam no grupo `QUERY_PLANNER__`: tamanho da consulta,
itens por lista, perguntas de esclarecimento, justificativa e tentativas de
reparo. O agente não acessa PostgreSQL, Qdrant ou SDKs concretos e é exposto por
`POST /api/v1/query-plans`. A rota aceita `{"query": "..."}` e devolve o plano,
avisos, erros recuperáveis e métricas. Ela ainda não conecta o restante do
pipeline por si só. As rotas iniciais `/health/live` e `/health/ready` foram removidas pela
especificação 005.

## Retriever

O Retriever Agent recebe um `QueryPlan` com status `ready`, consulta startups no
PostgreSQL e carrega seus documentos em lote. Setor, estágio e localização são
filtros sem diferença de caixa; portes conhecidos e intervalos numéricos são
traduzidos para `team_size`; palavras-chave e sinais de IA contribuem para o
score textual. A ordenação usa score, nome e UUID para permanecer determinística.

Os Enums de setor e estágio são expandidos para rótulos persistidos. Por
exemplo, `financial_services` consulta `Fintech / Crédito` e
`SaaS de Gestão Financeira` com OR, sem reescrever os dados importados.

As saídas usam `candidate_startups` e `selected_sources`, preservando UUIDs e
URLs. Os limites `RETRIEVER__MAX_RESULTS` e `RETRIEVER__EXCERPT_LENGTH` controlam
quantidade de candidatos e tamanho dos trechos. O agente ainda não possui rota
HTTP isolada.

## Orquestração disponível

O workflow compilado conecta `START → query_planner → retriever → END`. O
Retriever é chamado somente para planos `ready`; ambiguidade, consulta inválida
ou falha do Planner encerram o fluxo antes do PostgreSQL. O grafo é criado uma
vez no lifespan, não utiliza checkpointer e recebe um estado novo por requisição.

`POST /api/v1/search` aceita `{"query": "..."}` e devolve `query_plan`,
`candidate_startups`, `selected_sources`, avisos, erros e métricas. UUIDs e URLs
das fontes são preservados. A rota `/api/v1/query-plans` permanece disponível
para executar somente o Planner.
