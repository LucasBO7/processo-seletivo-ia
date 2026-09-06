# Especificação 007: orquestração Query Planner → Retriever

## Status

Proposta.

Esta especificação precisa de aprovação explícita antes da implementação.

## Contexto

As especificações 004 e 006 implementaram, respectivamente, o Query Planner e
o Retriever como nós isolados e compatíveis com `GraphNode`. O estado
compartilhado já transporta `query_plan`, `candidate_startups`,
`selected_sources`, avisos, erros e métricas. Entretanto, o `StateGraph` atual
continua vazio e a API chama somente o Query Planner diretamente.

O fluxo parcial executável deve transformar a consulta em plano, interromper
casos inválidos ou ambíguos e consultar PostgreSQL somente quando o plano estiver
pronto. Como o Extractor ainda não existe, o fluxo termina após o Retriever.

## Objetivos

- Montar e compilar um `StateGraph` com Query Planner e Retriever.
- Encaminhar ao Retriever somente planos com status `ready`.
- Encerrar previsivelmente planos `needs_clarification`, `invalid` e falhas.
- Expor uma rota HTTP própria para executar o fluxo parcial completo.
- Reutilizar modelos, pool PostgreSQL e grafo compilado durante o lifespan.
- Manter os agentes testáveis isoladamente e sem dependência da camada HTTP.

## Histórias do usuário

### US-01 — Executar o fluxo parcial no LangGraph

Como pessoa mantenedora, quero conectar os agentes pelo LangGraph para que o
estado produzido por um nó seja consumido pelo próximo sem chamadas manuais na
API.

Critérios de aceite:

- O grafo registra os nós `query_planner` e `retriever` usando os agentes reais.
- `START` encaminha para `query_planner`.
- Uma função de roteamento pura lê `query_plan.status` após o Planner.
- Status `ready` encaminha para `retriever`.
- Status `needs_clarification`, `invalid`, plano ausente ou erro do Planner
  encaminha para `END` sem consultar PostgreSQL.
- Após o Retriever, o fluxo encaminha para `END`, inclusive quando a busca não
  encontra resultados ou produz erro recuperável.
- O grafo é compilado e pode ser chamado assincronamente com `AppState`.

### US-02 — Preservar o estado entre os nós

Como próximo agente da pipeline, quero receber uma única saída coerente para
consumir o plano, as startups e suas evidências.

Critérios de aceite:

- A entrada mínima contém a consulta e os metadados de correlação da execução.
- A saída de sucesso contém `query_plan`, `candidate_startups` e
  `selected_sources` no mesmo `AppState`.
- UUIDs e URLs produzidos pelo Retriever permanecem inalterados após a execução
  do grafo.
- Avisos, erros e métricas produzidos pelos dois nós são preservados.
- O estado não contém clientes, sessões, prompts, respostas brutas ou segredos.
- Cada invocação usa estado independente; requisições concorrentes não
  compartilham resultados mutáveis.

### US-03 — Executar a busca pelo frontend

Como frontend, quero uma rota de busca que execute o fluxo disponível para não
orquestrar agentes individualmente no navegador.

Critérios de aceite:

- `POST /api/v1/search` aceita `{ "query": string }`.
- Uma execução `ready` retorna HTTP 200 com plano, candidatos, fontes, avisos,
  erros e métricas.
- `needs_clarification` e `invalid` retornam HTTP 200 com o plano e sem executar
  o Retriever.
- Entrada vazia ou longa retorna HTTP 422; saída inválida do Planner retorna
  502; indisponibilidade da Groq ou PostgreSQL retorna 503.
- A rota existente `POST /api/v1/query-plans` continua disponível para testar o
  Planner isoladamente.
- OpenAPI, CORS e documentação apresentam os dois contratos sem expor uma rota
  para o Retriever isolado.

### US-04 — Compor e operar o workflow com segurança

Como pessoa operadora, quero que o workflow reutilize recursos e produza falhas
sanitizadas para operar a API de forma previsível.

Critérios de aceite:

- O composition root instancia repositórios, agentes e grafo uma vez por ciclo
  de vida da aplicação.
- O grafo compilado reutiliza o pool assíncrono existente; não cria engine ou
  cliente por requisição.
- A execução não usa checkpointer, memória conversacional ou estado global
  persistente nesta feature.
- Logs usam correlação, nós executados, duração, status e contagens, sem consulta
  integral, SQL, prompt, resposta bruta ou credenciais.
- Testes unitários usam fakes e não acessam rede, banco ou Groq.
- Um teste de integração usa PostgreSQL real e modelo falso para comprovar a
  passagem Planner → Retriever.

## Contrato do fluxo

```text
START
  │
  ▼
query_planner
  │
  ▼
route_after_query_planner
  ├── ready ──────────────> retriever ──> END
  └── stop/error/invalid ───────────────> END
```

Saída conceitual da rota:

```text
SearchResponse
├── query_plan: QueryPlan | null
├── candidate_startups: list[CandidateStartup]
├── selected_sources: list[SourceReference]
├── warnings: list[string]
├── errors: list[RecoverableError]
└── metrics: map[string, number]
```

## Requisitos funcionais

- **RF-01:** registrar Query Planner e Retriever no `StateGraph`.
- **RF-02:** definir aresta inicial, roteamento condicional e término do fluxo.
- **RF-03:** compilar o grafo uma vez no composition root.
- **RF-04:** executar o workflow por `ainvoke` com estado independente.
- **RF-05:** expor `POST /api/v1/search` com contratos tipados.
- **RF-06:** mapear erros recuperáveis do estado para HTTP 422, 502 ou 503.
- **RF-07:** manter `POST /api/v1/query-plans` como endpoint isolado.
- **RF-08:** preservar correlação, dados rastreáveis e diagnósticos entre nós.

## Requisitos não funcionais

- **RNF-01:** usar a versão instalada do LangGraph e suas APIs públicas
  `START`, `END`, `StateGraph`, `add_node`, `add_edge`,
  `add_conditional_edges` e `compile`.
- **RNF-02:** manter execução assíncrona e tipagem estrita.
- **RNF-03:** não criar recursos de I/O por requisição.
- **RNF-04:** não usar rede, banco ou credenciais nos testes unitários.
- **RNF-05:** preservar logs e erros sanitizados.
- **RNF-06:** manter cobertura mínima de 80%, lint, mypy, testes arquiteturais e
  regressão do frontend aprovados.

## Regras de roteamento e HTTP

| Estado após Query Planner | Próximo nó | HTTP final esperado |
| --- | --- | --- |
| `ready`, sem erro bloqueante | Retriever | 200 ou 503 se PostgreSQL falhar |
| `needs_clarification` | END | 200 |
| `invalid` | END | 200 |
| `query_empty`, `query_too_long` | END | 422 |
| `query_plan_invalid_output` | END | 502 |
| `query_planner_unavailable` | END | 503 |

O aviso `retriever_no_results` continua sendo um resultado HTTP 200 com listas
vazias. `retriever_unavailable` é traduzido para HTTP 503.

## Restrições

- LangGraph permanece responsável pelo encadeamento dos agentes.
- A camada HTTP não pode chamar os dois agentes em sequência manualmente.
- O roteador não pode importar adaptadores PostgreSQL concretos.
- Query Planner e Retriever mantêm seus contratos e testes isolados.
- A rota de planejamento isolado não muda de semântica.

## Fora do escopo

- Implementar ou simular Extractor e os cinco agentes posteriores.
- Conectar o Retriever a um nó fictício após sua execução.
- Checkpoint, retomada, memória conversacional, streaming ou intervenção humana.
- Busca vetorial, BM25, reranking e recomendação NVIDIA.
- Autenticação, autorização, persistência do estado ou histórico de conversas.
- Alterações no schema PostgreSQL ou nos critérios de relevância do Retriever.
- Integração visual do frontend além da documentação do contrato HTTP.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01 a RF-04, RNF-01, RNF-02 | Testes de topologia, rotas condicionais e invocação |
| US-02 | RF-04, RF-08, RNF-02, RNF-05 | Testes de estado, rastreabilidade e isolamento |
| US-03 | RF-05 a RF-07, RNF-02 | Testes HTTP, OpenAPI, CORS e documentação |
| US-04 | RF-03, RF-08, RNF-03 a RNF-06 | Testes de composição, integração e suíte completa |

## Critério de conclusão

A feature estará concluída quando o grafo parcial estiver compilado e executável,
o roteamento impedir consultas indevidas ao PostgreSQL, a rota de busca refletir
o estado final, os testes unitários e de integração passarem e a entrega receber
aprovação explícita.

## Sugestão de commit

`feat(graph): orchestrate query planner and retriever workflow`
