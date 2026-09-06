# Plano 007: orquestração Query Planner → Retriever

## Estratégia

O `graph/builder.py` deixará de retornar um builder vazio e receberá os dois nós
já construídos. Ele registrará a topologia, uma função pura de roteamento e
compilará o workflow. A composition root construirá repositórios, agentes e
workflow uma vez, armazenando o grafo compilado nos recursos da aplicação.

A rota `/api/v1/search` criará apenas o estado inicial por requisição e chamará
`workflow.ainvoke`. Ela traduzirá o estado final para response models, sem
reimplementar regras dos agentes. `/api/v1/query-plans` permanecerá como rota de
diagnóstico funcional do Planner isolado.

## Arquitetura dentro do escopo

```text
api/routes/search.py
  └── ApplicationResources.workflow.ainvoke(initial_state)

core/resources.py
  ├── model_registry
  ├── repositories compartilhados
  └── workflow compilado

graph/builder.py
  ├── query_planner node
  ├── route_after_query_planner
  ├── retriever node
  └── compile()
```

## Estado e roteamento

O estado inicial será produzido por `empty_state`, com UUID de execução,
correlation ID e consulta. O Planner adiciona `query_plan`; o roteador lê apenas
status e erros bloqueantes. O Retriever adiciona candidatos e fontes. Como a
execução é sequencial e os agentes já preservam diagnósticos anteriores, não
serão introduzidos reducers ou canais paralelos nesta feature.

## Composição

1. Criar engine, session factory e demais recursos existentes.
2. Criar `SqlAlchemyStartupRepository` e
   `SqlAlchemyStartupDocumentRepository` sobre a session factory compartilhada.
3. Resolver `llm_fast` no Query Planner.
4. Injetar repositórios no Retriever.
5. Construir e compilar o `StateGraph`.
6. Armazenar o workflow compilado em `ApplicationResources`.
7. Reutilizar o workflow em todas as requisições sem checkpointer.

## Contrato HTTP

`POST /api/v1/search` usa request model com `query`. O response model converte
os objetos internos para JSON, preservando UUIDs como strings e URLs sem
alteração. O mapeamento de status reutilizará uma função comum para evitar
divergência entre as rotas de planejamento e busca.

## Testes

- topologia contém os dois nós e arestas esperadas;
- `ready` chama Retriever uma vez;
- ambiguidade, invalidade e falha do Planner não chamam repositórios;
- execução final preserva plano, candidatos, IDs, URLs, avisos e métricas;
- invocações consecutivas não compartilham estado;
- rota cobre sucesso e códigos 422, 502 e 503;
- integração usa PostgreSQL real e `FakeChatModel`;
- nenhuma chamada unitária usa rede ou credenciais.

## Verificação

1. Executar testes específicos do builder, workflow e rota.
2. Executar Ruff format/check, mypy e import-linter.
3. Executar suíte unitária com cobertura mínima de 80%.
4. Executar integração real com PostgreSQL e modelo falso.
5. Executar lint, testes e build do frontend.
6. Revisar OpenAPI, logs, respostas e matriz de rastreabilidade.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Retriever executar após ambiguidade | Roteamento puro e testes negativos de chamadas |
| API duplicar orquestração | Única chamada a `workflow.ainvoke` |
| Estado vazar entre requisições | Grafo sem checkpointer e novo estado por invocação |
| Recursos serem recriados por request | Composição e compilação no lifespan |
| Próximo agente inexistente ser simulado | Encerrar explicitamente após Retriever |
| Status HTTP divergir entre rotas | Extrair mapeamento compartilhado e testá-lo |

## Decisões adiadas

- Aresta Retriever → Extractor.
- Checkpoint e retomada para esclarecimento humano.
- Streaming de eventos do LangGraph para o frontend.
- Persistência de execuções e estados intermediários.
- Endpoint único para a pipeline completa.

## Sugestão de commit

`feat(graph): orchestrate query planner and retriever workflow`
