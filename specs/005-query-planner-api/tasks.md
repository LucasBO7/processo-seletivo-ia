# Tarefas 005: API do Query Planner

- [x] **T-01 [US-01, RF-01]** Criar request e response models da rota.
- [x] **T-02 [US-01, RF-02]** Implementar `POST /api/v1/query-plans` usando o agente existente.
- [x] **T-03 [US-02, RF-03]** Mapear erros recuperáveis para códigos HTTP estáveis.
- [x] **T-04 [US-03, RF-04]** Remover as rotas e testes de liveness e readiness.
- [x] **T-05 [US-03, RNF-03]** Habilitar POST no CORS e preservar correlação.
- [x] **T-06 [US-01 a US-03, RNF-01 a RNF-03]** Criar testes automatizados do contrato HTTP.
- [x] **T-07 [US-03, RF-05]** Atualizar OpenAPI e documentação para Postman e frontend.
- [x] **T-08 [US-01 a US-03, RNF-04]** Executar qualidade, cobertura e regressão do frontend.
- [ ] **T-09 [US-01 a US-03]** Concluir a spec somente após aprovação explícita da entrega.

## Sugestão de commit

`feat(api): expose query planner endpoint for frontend clients`
