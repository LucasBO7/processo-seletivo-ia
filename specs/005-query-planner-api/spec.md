# Especificação 005: API do Query Planner

## Status

Implementada e verificada em 6 de setembro de 2026; aguardando aprovação
explícita da entrega para conclusão.

A implementação foi autorizada por confirmação explícita do responsável pelo
projeto. As tarefas T-01 a T-08 foram concluídas; a T-09 permanece aberta até a
validação da entrega.

## Contexto

A especificação 004 implementou o Query Planner somente como nó interno. O
frontend e clientes como Postman precisam de um contrato HTTP real para enviar
consultas. Os endpoints de liveness e readiness da fundação foram criados para
validar a API inicialmente e serão removidos por decisão explícita desta entrega.

## Objetivos

- Expor o Query Planner sob o prefixo versionado `/api/v1`.
- Fornecer contratos de entrada e saída documentados no OpenAPI.
- Preservar status, avisos, erros recuperáveis e métricas do agente.
- Remover `GET /health/live` e `GET /health/ready` e seus testes específicos.
- Manter CORS e correlação compatíveis com o consumo pelo frontend.

## Histórias e critérios de aceite

### US-01 — Planejar uma consulta por HTTP

Como frontend, quero enviar uma consulta ao Query Planner para receber um plano
estruturado sem conhecer os contratos internos do grafo.

Critérios de aceite:

- `POST /api/v1/query-plans` aceita JSON com o campo textual `query`.
- Uma consulta executável retorna HTTP 200 e um `QueryPlan` com status `ready`.
- Planos `needs_clarification` e `invalid` retornam HTTP 200, preservando seus
  status, filtros inequívocos, avisos e erros recuperáveis.
- A resposta contém `query_plan`, `warnings`, `errors` e `metrics`.
- O endpoint utiliza o Query Planner e o modelo rápido já compostos, sem duplicar
  regras de planejamento na camada HTTP.

### US-02 — Tratar falhas de forma previsível

Como frontend, quero distinguir entrada inválida de indisponibilidade para
apresentar uma resposta adequada à pessoa usuária.

Critérios de aceite:

- Consulta vazia ou longa retorna HTTP 422 e o código estável produzido pelo nó.
- Saída inválida do modelo retorna HTTP 502.
- Indisponibilidade do modelo retorna HTTP 503.
- Erros não incluem prompt, resposta bruta, credencial ou stack trace.
- JSON com tipo inválido ou campo ausente usa o envelope global de validação.

### US-03 — Consumir a API pelo navegador e pelo Postman

Como pessoa desenvolvedora, quero descobrir e chamar a rota atual para integrar
o frontend e validar manualmente o backend.

Critérios de aceite:

- O OpenAPI lista `POST /api/v1/query-plans` e não lista rotas `/health`.
- CORS aceita `POST` e `OPTIONS` para as origens configuradas.
- `X-Correlation-ID` continua sendo aceito e devolvido.
- README documenta uma requisição para Postman e uma chamada `fetch` para o
  frontend.
- `GET /health/live` e `GET /health/ready` retornam 404.

## Requisitos funcionais

- **RF-01:** expor `POST /api/v1/query-plans` com request e response models.
- **RF-02:** resolver o Query Planner a partir dos recursos e configurações da aplicação.
- **RF-03:** mapear erros do agente para HTTP 422, 502 ou 503.
- **RF-04:** remover as rotas públicas de liveness e readiness.
- **RF-05:** publicar o contrato atual no OpenAPI e na documentação do repositório.

## Requisitos não funcionais

- **RNF-01:** manter execução assíncrona, tipagem estrita e cobertura mínima de 80%.
- **RNF-02:** não realizar chamadas reais à Groq nos testes.
- **RNF-03:** manter CORS por allowlist e correlação sem expor dados sensíveis.
- **RNF-04:** manter lint, mypy, testes arquiteturais, testes de backend e frontend aprovados.

## Fora do escopo

- Integrar componentes visuais do frontend nesta entrega.
- Implementar os sete agentes restantes ou executar o grafo completo.
- Consultar PostgreSQL ou Qdrant a partir do Query Planner.
- Adicionar autenticação, persistência de planos ou streaming.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-02, RNF-01 | Testes de sucesso e dos status do plano |
| US-02 | RF-03, RNF-02, RNF-03 | Testes de erros e sanitização |
| US-03 | RF-04, RF-05, RNF-03, RNF-04 | OpenAPI, CORS, correlação, documentação e suíte completa |

## Critério de conclusão

A entrega estará concluída quando a rota funcional estiver documentada e
testada, as rotas de saúde não estiverem mais publicadas, os critérios de aceite
passarem e a entrega receber aprovação explícita.

## Sugestão de commit

`feat(api): expose query planner endpoint for frontend clients`
