# Plano 006: Retriever Agent

## Estratégia

O agente dependerá de portas de repositório, nunca de SQLAlchemy. Um contrato
`StartupSearchCriteria` traduzirá o plano em filtros normalizados e intervalos
de equipe. O adaptador PostgreSQL aplicará filtros e score em uma query
parametrizada, limitará os candidatos e carregará todos os documentos em uma
segunda query com `IN`, evitando N+1.

## Fluxo

```text
AppState.query_plan
  -> valida status
  -> traduz critérios
  -> busca e ordena startups no PostgreSQL
  -> carrega documentos em lote
  -> candidate_startups + selected_sources
```

## Persistência e desempenho

- filtros estruturados usam comparação normalizada;
- índices funcionais suportam os filtros sem diferença de caixa;
- a FK `startup_documents.startup_id` já possui índice para o carregamento em lote;
- o limite é aplicado antes da consulta de documentos;
- score, nome e UUID formam ordenação total e reproduzível;
- busca textual simples é suficiente para a base MVP de 30–80 startups; full-text
  e ranking híbrido permanecem para specs próprias.

## Verificação

1. Testar tradução de critérios e agente com fakes.
2. Testar SQL e carregamento em lote com PostgreSQL real.
3. Executar Ruff, mypy, contratos arquiteturais, cobertura e suíte completa.
4. Executar lint, testes e build do frontend.

## Sugestão de commit

`feat(retriever): query PostgreSQL from structured query plans`
