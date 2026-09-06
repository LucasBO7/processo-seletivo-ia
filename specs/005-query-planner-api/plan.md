# Plano 005: API do Query Planner

## Estratégia

Uma nova rota FastAPI traduzirá o JSON HTTP para `AppState`, resolverá o
`QueryPlannerAgent` com o `ModelRegistry` existente e traduzirá sua atualização
parcial para um response model. A camada HTTP não interpretará a consulta nem
alterará o plano. As rotas de saúde serão removidas do roteador e do OpenAPI.

## Contrato

```text
POST /api/v1/query-plans
request:  { query: string }
response: { query_plan, warnings, errors, metrics }
```

Mapeamento de falhas:

| Código do agente | HTTP |
| --- | --- |
| `query_empty`, `query_too_long` | 422 |
| `query_plan_invalid_output` | 502 |
| `query_planner_unavailable` | 503 |
| plano `invalid` | 200 |

## Verificação

1. Testar os contratos e códigos HTTP sem rede.
2. Verificar CORS, correlação, OpenAPI e remoção das rotas antigas.
3. Executar o comando agregado e cobertura do backend.
4. Executar lint, testes e build do frontend.

## Sugestão de commit

`feat(api): expose query planner endpoint for frontend clients`
