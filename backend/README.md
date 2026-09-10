# Backend — NVIDIA Startup AI Radar

Guia técnico para desenvolvimento, operação local e manutenção da API. A
visão do produto está no [README da raiz](../README.md).

## Stack

- Python 3.12+ e `uv`;
- FastAPI + Uvicorn;
- LangGraph para orquestração assíncrona;
- PostgreSQL 16 + SQLAlchemy + Alembic;
- Qdrant para busca vetorial;
- BM25 para busca lexical e Cohere Rerank opcional;
- Groq via `langchain-groq`;
- Pytest, Ruff, mypy e import-linter.

## Pré-requisitos

- Python 3.12 ou superior;
- [`uv`](https://docs.astral.sh/uv/);
- Docker Desktop, recomendado para PostgreSQL e Qdrant;
- credenciais dos provedores quando o fluxo real exigir Groq, embeddings ou
  Cohere.

## Configuração local

Na raiz do repositório:

```powershell
Copy-Item backend/.env.example backend/.env
```

Preencha no `backend/.env` as variáveis obrigatórias, principalmente
`POSTGRES__URL`, `QDRANT__URL` e `GROQ__API_KEY`. O arquivo `.env` é ignorado
pelo Git e nunca deve conter dados versionados.

Os perfis de modelo são configuráveis por `LLM_FAST__*` e `LLM_HEAVY__*`. O
limitador `GROQ__MIN_REQUEST_INTERVAL_SECONDS` controla o intervalo global entre
chamadas; o padrão operacional para o plano gratuito é 7 segundos.

## Instalação e execução

Instale as dependências e aplique as migrações:

```powershell
uv sync --project backend --locked --all-groups
uv run --project backend alembic -c backend/alembic.ini upgrade head
```

Suba as dependências locais:

```powershell
docker compose up -d
docker compose ps
```

Inicie a API:

```powershell
uv run --project backend startup-radar
```

A API fica em `http://127.0.0.1:8000`. Para encerrar apenas os containers do
projeto:

```powershell
docker compose down
```

Se aparecer `WinError 10048`, já existe outro `startup-radar` usando a porta
8000. Encerre a instância anterior ou libere a porta antes de iniciar outra.

## Endpoints principais

| Endpoint | Uso |
| --- | --- |
| `POST /api/v1/search` | Executa o pipeline completo de análise |
| `POST /api/v1/query-plans` | Executa apenas o Query Planner |
| `GET /api/v1/docs` | Swagger UI |
| `GET /api/v1/openapi.json` | Contrato OpenAPI |

Exemplo mínimo:

```json
{
  "query": "Analise a Neurotech"
}
```

## Arquitetura de pastas

```text
backend/
├── pyproject.toml          # dependências, scripts e ferramentas
├── uv.lock                 # resolução reproduzível
├── alembic.ini             # configuração de migrações
├── migrations/             # schema PostgreSQL versionado
├── scripts/                # manifesto e operações da base NVIDIA
├── evaluation/             # datasets e relatórios de qualidade
├── src/app/
│   ├── api/                # FastAPI, rotas, erros e middleware
│   ├── application/
│   │   ├── contracts/      # contratos Pydantic entre etapas
│   │   ├── ports/          # interfaces de persistência e provedores
│   │   └── services/       # casos de uso de aplicação
│   ├── domain/             # modelos independentes de frameworks
│   ├── graph/
│   │   ├── agents/         # oito agentes do pipeline
│   │   ├── prompts/        # prompts e formatos estruturados
│   │   ├── builder.py      # topologia e roteamento do grafo
│   │   ├── state.py        # AppState compartilhado
│   │   └── model_policy.py # alocação fast/heavy/none
│   ├── infrastructure/
│   │   ├── persistence/    # PostgreSQL e repositórios SQLAlchemy
│   │   ├── providers/      # Groq, embeddings e Cohere
│   │   ├── retrieval/      # índice BM25
│   │   ├── vector/         # cliente e store Qdrant
│   │   └── ingestion/      # coleta e chunking NVIDIA
│   ├── core/               # settings, logging e recursos do lifespan
│   └── main.py             # entrypoint Windows/Linux
└── tests/
    ├── unit/               # testes rápidos, offline e com fakes
    ├── integration/        # PostgreSQL/Qdrant reais, opt-in
    └── external/           # fontes externas, opt-in
```

## Fluxo de execução

```text
API request
  → query_planner
  → retriever (PostgreSQL)
  → extractor
  → startup_classifier
  → evidence_validator
  → nvidia_rag (Qdrant + BM25 + reranker opcional)
  → recommendation
  → briefing
```

O `AppState` carrega somente contratos tipados, IDs, fontes, avisos, erros e
métricas. O composition root em `src/app/api/app.py` cria clientes, repositórios,
agentes e o workflow uma vez por lifespan. O Retriever não usa LLM.

## Ingestão da base NVIDIA

O manifesto de fontes está em `scripts/nvidia_sources.json`. Os comandos
disponíveis são:

```powershell
uv run --project backend startup-radar-knowledge --help
uv run --project backend startup-radar-knowledge ingest
uv run --project backend startup-radar-knowledge verify
```

PostgreSQL é a fonte de verdade; Qdrant e BM25 são índices derivados. A
ingestão real exige as credenciais configuradas para embeddings e reranking.

## Testes e qualidade

Testes padrão não chamam LLMs reais:

```powershell
uv run --project backend pytest -c backend/pyproject.toml backend/tests/unit -q
uv run --project backend ruff check backend/src backend/tests
uv run --project backend ruff format --check backend/src backend/tests backend/migrations
uv run --project backend mypy backend/src
```

Integrações exigem PostgreSQL/Qdrant ativos e são opt-in:

```powershell
$env:RUN_INTEGRATION_TESTS = "1"
uv run --project backend pytest -c backend/pyproject.toml backend/tests/integration -q
```

Use fakes (`FakeChatModel`, `SequenceChatModel` e adaptadores falsos) em novos
testes unitários. Nunca coloque chaves, prompts completos ou respostas brutas
em logs, fixtures versionadas ou mensagens de erro.

## Convenções de desenvolvimento

- Agentes dependem de portas internas, nunca de SDKs concretos.
- Toda saída de modelo deve ser validada por contrato Pydantic e por regras
  semânticas determinísticas.
- Mudanças de comportamento devem atualizar a spec correspondente e suas tasks.
- Para novas integrações, configure timeout finito, erro sanitizado e teste com
  cliente falso.
