# Tarefas 007: orquestração Query Planner → Retriever

Todas as tarefas permanecem pendentes enquanto a especificação estiver como
`Proposta`.

## Grafo e composição

- [ ] **T-01 [US-01, RF-01, RF-02]** Implementar a topologia START → Query Planner → roteamento → Retriever/END.
- [ ] **T-02 [US-01, RF-02]** Criar e testar a função pura de roteamento após o Planner.
- [ ] **T-03 [US-01, RF-03, RF-04]** Compilar o grafo e definir um contrato tipado para invocação assíncrona.
- [ ] **T-04 [US-04, RF-03, RNF-03]** Compor repositórios, agentes e workflow uma vez no lifespan.
- [ ] **T-05 [US-02, RF-08]** Garantir preservação de estado, diagnósticos, UUIDs e URLs entre os nós.

## API

- [ ] **T-06 [US-03, RF-05]** Criar request e response models de `POST /api/v1/search`.
- [ ] **T-07 [US-03, RF-06]** Mapear estados e erros finais para HTTP 200, 422, 502 e 503.
- [ ] **T-08 [US-03, RF-07]** Manter e testar `POST /api/v1/query-plans` como rota isolada.
- [ ] **T-09 [US-03, RNF-03]** Atualizar CORS, OpenAPI e documentação para o frontend e Postman.

## Testes e verificação

- [ ] **T-10 [US-01, US-02, RNF-04]** Criar testes unitários de topologia, roteamento, execução e isolamento com fakes.
- [ ] **T-11 [US-03, RNF-04]** Criar testes HTTP de sucesso, interrupções e falhas sanitizadas.
- [ ] **T-12 [US-04, RNF-03, RNF-05]** Testar composição única, ausência de estado global e logs permitidos.
- [ ] **T-13 [US-04, RNF-06]** Executar integração com PostgreSQL real e modelo falso.
- [ ] **T-14 [US-01 a US-04, RNF-06]** Executar qualidade, cobertura e regressão do frontend.
- [ ] **T-15 [US-01 a US-04]** Revisar critérios e concluir somente após aprovação explícita da entrega.

## Sugestão de commit

`feat(graph): orchestrate query planner and retriever workflow`
