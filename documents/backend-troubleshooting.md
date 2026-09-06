# Diagnóstico do backend

Este guia cobre falhas da fundação definida na especificação 002. Ele não inclui lógica de agentes ou provedores de IA.

## Configuração inválida na inicialização

Sintomas:

- erro de validação antes de o servidor iniciar;
- indicação de que `postgres` ou `qdrant` está ausente;
- porta, timeout, distância ou dimensão rejeitados.

Verificações:

1. Confirme que `backend/.env` existe e foi criado a partir de `backend/.env.example`.
2. Use nomes aninhados com dois sublinhados, como `POSTGRES__URL`.
3. Mantenha listas JSON válidas em `HTTP__CORS_ORIGINS`.
4. Não coloque aspas extras em URLs.
5. Nunca publique o conteúdo do `.env` em issues ou logs.

## Liveness falha

`GET /health/live` não consulta dependências. Se falhar, verifique se o processo está ativo, se a porta configurada está livre e se a aplicação terminou sua inicialização.

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health/live
```

## Readiness retorna HTTP 503

`GET /health/ready` consulta PostgreSQL e Qdrant. O corpo identifica qual dependência não respondeu.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Confira primeiro as URLs e a disponibilidade dos serviços configurados. Se
você optou pelo Compose, também pode usar:

```powershell
docker compose ps
docker compose logs postgres
docker compose logs qdrant
```

Se o PostgreSQL falhar, confira a URL, a porta e as credenciais locais. Se o Qdrant falhar, confira a URL e se a coleção configurada possui a mesma dimensão e distância do `.env`.

No Windows, uma mensagem indicando que o Psycopg não aceita
`ProactorEventLoop` significa que o servidor foi iniciado por outro entrypoint.
Use `uv run --project backend startup-radar`; esse comando configura o loop
seletor compatível também durante o reload local.

## Migração falha

Confirme primeiro a readiness dos serviços e a configuração do ambiente. Depois consulte o estado do Alembic:

```powershell
uv run --project backend alembic -c backend/alembic.ini current
uv run --project backend alembic -c backend/alembic.ini history
uv run --project backend alembic -c backend/alembic.ini upgrade head
```

Não use `Base.metadata.create_all()` para contornar migrações. Se o schema divergir, investigue a revisão aplicada e crie uma nova migração por uma spec aprovada.

## Coleção Qdrant incompatível

A aplicação rejeita uma coleção existente cuja dimensão ou distância divirja da configuração. Não altere esses valores em produção sem uma estratégia de reindexação. Se estiver usando a alternativa com Compose em um ambiente descartável, remova o volume somente se os dados locais puderem ser perdidos e após confirmar o alvo da operação.

## Encerramento

Ao interromper o servidor, o lifespan fecha o cliente Qdrant e descarta o pool SQLAlchemy. Mensagens sobre conexões pendentes indicam que algum recurso foi criado fora da composition root ou não passou pelo lifespan.
