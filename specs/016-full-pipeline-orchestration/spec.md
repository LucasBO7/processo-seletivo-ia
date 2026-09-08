# Especificação 016: orquestração completa do pipeline

## Status

Implementada e validada tecnicamente em 8 de setembro de 2026.

## Contexto

A especificação 007 criou o único `StateGraph` da aplicação e as especificações
009 a 015 o estenderam incrementalmente. A sequência nominal já existe, mas a
entrega completa precisa consolidar as pré-condições, interrupções e garantias de
preservação do estado em um contrato único, além de provar a execução integrada
dos oito agentes reais.

## Objetivos

- Evoluir o grafo existente, sem criar outro workflow paralelo.
- Fixar a ordem TAPI: Query Planner, Retriever, Extractor, Startup Classifier,
  Evidence Validator, NVIDIA RAG, Recommendation e Briefing.
- Encerrar cedo quando a próxima etapa não possuir entrada válida.
- Permitir continuidade parcial somente quando ainda existir saída válida para a
  próxima etapa.
- Reutilizar agentes, modelos, pools, índices e clientes criados no lifespan.
- Comprovar topologia, roteamento, interrupção, isolamento e fluxo completo.

## Histórias e critérios de aceite

### US-01 — Executar um único pipeline completo

- `create_graph_builder` e `compile_analysis_workflow` existentes continuam sendo
  os únicos construtores do workflow.
- A topologia é exatamente `START → query_planner → retriever → extractor →
  startup_classifier → evidence_validator → nvidia_rag → recommendation →
  briefing → END`, com decisões condicionais entre os agentes.
- Todos os nós recebem instâncias reais no composition root da aplicação.
- Não existe segundo grafo, chamada manual sequencial na API ou atalho entre nós.

### US-02 — Interromper entradas sem pré-condição

- Consulta `needs_clarification`, `invalid`, ausente ou com erro bloqueante do
  Planner termina antes do Retriever.
- Ausência de startups termina após o Retriever.
- Candidatos sem documentos apropriados terminam antes do Extractor.
- Ausência de `StructuredStartupProfile` válido termina antes do Classifier.
- O Validator executa quando existe perfil estruturado, mesmo sem classificação,
  pois a spec 011 trata essa ausência como lacuna.
- Ausência de perfil validado utilizável termina antes do NVIDIA RAG.
- Contexto NVIDIA ausente, `insufficient`, sem chunks citáveis ou sem startup
  correspondente termina antes do Recommendation Agent.
- Ausência de `StartupRecommendation` válida termina antes do Briefing Agent.
- O Briefing sempre termina em `END`.

### US-03 — Tratar falhas recuperáveis e resultados parciais

- Erros recuperáveis são preservados e nunca lançados pelo roteamento.
- Uma falha sem saída válida interrompe antes da próxima etapa.
- Quando um agente preserva uma saída válida de outra startup, o fluxo continua
  para processar essa saída parcial.
- Funções de roteamento são puras e não realizam I/O.
- Valores malformados não satisfazem pré-condições somente por serem truthy.

### US-04 — Preservar o estado rastreável

- `run_id`, `correlation_id`, consulta e todos os campos produzidos permanecem no
  `AppState` final.
- IDs de startup, documento e chunk, URLs, citações e locators não são reescritos
  pelo orquestrador.
- Avisos e erros permanecem deduplicados conforme os contratos dos agentes.
- Métricas de todos os oito nós coexistem no resultado final.
- O estado não armazena modelos, clientes, pools, prompts ou respostas brutas.

### US-05 — Reutilizar recursos do lifespan

- O composition root cria modelos, repositories, pool PostgreSQL, Qdrant,
  embedding, reranker, agentes e workflow uma vez por lifespan.
- `/api/v1/search` cria apenas um `empty_state` e chama `workflow.ainvoke`.
- Requisições consecutivas reutilizam o mesmo workflow e recebem estados mutáveis
  independentes.
- Nenhum roteador ou nó recompila o grafo ou cria infraestrutura por requisição.

### US-06 — Testar o pipeline sem provedores reais

- Testes unitários cobrem nós, arestas, todas as decisões de continuar/parar e
  falhas recuperáveis.
- Testes de execução comprovam interrupção e isolamento entre invocações.
- Um teste de integração executa os oito agentes reais com `SequenceChatModel`,
  repositories, embedding, busca vetorial, busca lexical e reranker falsos.
- O teste integrado preserva identidade, URLs e citações e contém métricas de
  todos os nós.
- Nenhum teste usa LLM real, rede ou serviço pago.

## Política de continuidade parcial

O roteamento é orientado pela presença de contratos válidos, não apenas pela
existência de um erro. Isso permite que uma falha em uma startup não descarte
resultados já concluídos para outra. Se não houver saída válida correspondente, o
fluxo termina. O Planner é a exceção: seus códigos bloqueantes impedem qualquer
consulta ao Retriever.

## Requisitos funcionais

- **RF-01:** declarar a ordem canônica dos oito nós.
- **RF-02:** manter um único builder e um único workflow compilado.
- **RF-03:** validar pré-condições por contratos e associações de `startup_id`.
- **RF-04:** encerrar os sete pontos condicionais de forma determinística.
- **RF-05:** preservar o `AppState` e seus dados rastreáveis.
- **RF-06:** reutilizar os recursos do lifespan.
- **RF-07:** permitir continuidade parcial com ao menos uma saída válida.
- **RF-08:** testar o fluxo completo com agentes reais e adaptadores falsos.

## Requisitos não funcionais

- Funções de roteamento são síncronas, puras e tipadas.
- O workflow permanece assíncrono, sem checkpointer ou estado global mutável.
- A suíte padrão não acessa rede, banco real, Qdrant real ou LLM real.
- Ruff, mypy, import-linter, cobertura mínima de 80% e frontend permanecem verdes.

## Fora do escopo

- Memória conversacional, checkpoint, retomada ou intervenção humana.
- Autenticação, autorização, scraping ou ingestão adicional.
- Persistência do `AppState` ou histórico de execuções.
- Novo endpoint, novo grafo, streaming ou alteração visual do frontend.
- Alteração das decisões internas dos agentes implementados nas specs 004–015.

## Critério de conclusão

A feature estará concluída quando o único `StateGraph` tiver topologia e
pré-condições verificadas, o teste integrado percorrer os oito agentes reais, o
estado final preservar rastreabilidade e métricas, e todas as verificações de
qualidade passarem.

## Sugestão de commit

`feat(graph): validate and test full pipeline orchestration`
