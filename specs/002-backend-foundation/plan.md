# Plano 002: fundação do backend

## Estratégia

A fundação será um monólito modular assíncrono em Python. FastAPI expõe a borda HTTP; aplicação e domínio concentram contratos internos; LangGraph recebe apenas o estado e os identificadores dos nós nesta entrega; adaptadores de infraestrutura encapsulam PostgreSQL e provedores de IA.

PostgreSQL 16 será a fonte de verdade dos dados estruturados e textos citáveis. Qdrant armazenará os vetores, e um índice BM25 será construído a partir dos chunks persistidos. A fusão dos rankings e o uso do Cohere Rerank serão implementados em uma feature própria, sobre contratos definidos agora.

## Arquitetura dentro do escopo

```text
backend/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── migrations/                   # Evolução versionada do PostgreSQL
├── scripts/                      # Operações locais; ingestão real será uma feature futura
├── src/app/
│   ├── api/                     # FastAPI, health, middleware e erros HTTP
│   ├── application/
│   │   ├── ports/               # Contratos de repositórios, modelos e recuperação
│   │   └── services/            # Casos de uso; sem regras dos agentes nesta feature
│   ├── domain/                  # Entidades, evidências, citações e recomendações
│   ├── graph/
│   │   ├── state.py             # StartupRadarState tipado
│   │   ├── nodes.py             # Identificadores dos oito agentes
│   │   ├── contracts.py         # Contrato uniforme de nó
│   │   └── builder.py           # Construção futura do StateGraph
│   ├── infrastructure/
│   │   ├── persistence/         # PostgreSQL e implementações dos repositórios
│   │   ├── vector/              # Qdrant e coleção versionada
│   │   ├── retrieval/           # Fronteira para BM25 e recuperação híbrida
│   │   └── providers/           # Adaptadores de chat, embeddings e Cohere
│   ├── core/                    # Configuração, logging e ciclo de vida
│   └── main.py                  # Composition root da aplicação
└── tests/
    ├── unit/
    ├── integration/
    └── architecture/
```

Essa estrutura preserva a ideia funcional apresentada no README sem colocar a
lógica dos agentes na camada HTTP ou nos adaptadores. Os nomes `state.py`,
`nodes.py` e `builder.py` correspondem, respectivamente, ao estado compartilhado,
ao catálogo de agentes e à montagem do grafo. As responsabilidades antes
descritas genericamente como `tools` tornam-se portas em `application/ports` e
adaptadores em `infrastructure`, para que PostgreSQL, Qdrant, BM25 e provedores de
IA possam ser substituídos e testados isoladamente.

### Evolução prevista dos agentes

Quando specs funcionais posteriores aprovarem a lógica do pipeline,
`graph/agents/` receberá os oito nós abaixo:

```text
graph/agents/
├── query_planner.py
├── retriever.py
├── extractor.py
├── classifier.py
├── validator.py
├── nvidia_rag.py
├── recommender.py
└── briefing.py
```

Nesta fundação, somente seus identificadores e o contrato uniforme de execução
são criados. Os arquivos de agentes, as arestas do fluxo de negócio, as
ferramentas executáveis, o seed de startups e a ingestão NVIDIA continuam fora do
escopo, conforme a especificação 002.

Fluxo permitido de dependências:

```text
API ───────> Aplicação ───────> Domínio
  │              ▲                 ▲
  │              │                 │
  └────> Composição <──── Infraestrutura

Grafo ─────> Aplicação + Domínio
```

- `domain` não conhece frameworks ou I/O.
- `application` define protocolos assíncronos consumidos pelos casos de uso.
- `infrastructure` implementa os protocolos e não é importada pelo domínio.
- `api` traduz HTTP para contratos de aplicação.
- `graph` mantém estado e topologia separados das funções dos agentes.
- `main.py` e o ciclo de vida do FastAPI formam a composition root.

## Modelo de dados inicial

| Tabela | Responsabilidade | Campos essenciais |
| --- | --- | --- |
| `startups` | Cadastro estruturado da empresa | `id`, `name`, `website`, `sector`, `stage`, `location`, `short_description`, `founded_year`, `team_size`, timestamps |
| `startup_documents` | Evidências textuais da startup | `id`, `startup_id`, `document_type`, `title`, `content_text`, `source_url`, `published_at`, timestamps |
| `analysis_runs` | Identidade e ciclo de uma futura análise | `id`, `query`, `status`, `started_at`, `finished_at`, `error_code`, timestamps |
| `knowledge_documents` | Fonte da base de conhecimento | `id`, `title`, `source_url`, `content_type`, `published_at`, `content_hash`, timestamps |
| `knowledge_chunks` | Unidade recuperável e citável | `id`, `document_id`, `content`, `chunk_index`, `metadata`, `content_hash`, timestamps |

Decisões do schema:

- UUIDs são gerados pela aplicação ou pelo banco de forma consistente.
- Datas persistidas usam timezone e UTC.
- `source_url` é obrigatória para documentos que sustentam evidências ou citações.
- `content_hash` permite detectar reingestão, sem implementar a ingestão nesta feature.
- O PostgreSQL preserva o texto canônico; o índice BM25 pode ser reconstruído sem perda a partir dele.
- Cada ponto no Qdrant usa o UUID do chunk como identificador e replica apenas metadados necessários para filtro; o conteúdo citável continua no PostgreSQL.
- A coleção Qdrant fixa distância e dimensão vetorial a partir de configuração validada. Trocar o modelo ou a dimensão exige uma nova coleção versionada e reindexação.
- Schema relacional, coleção vetorial e contratos de recuperação serão validados nesta fundação; qualidade de ranking pertence à feature de RAG.

## Estado compartilhado do grafo

O estado será uma estrutura tipada com campos opcionais ou coleções vazias, atualizada parcialmente pelos nós. Ele contempla:

- contexto da execução: `run_id`, `correlation_id`, consulta e filtros;
- recuperação: startups candidatas e documentos selecionados;
- entendimento: perfis estruturados e classificações;
- factualidade: afirmações validadas, rejeitadas e referências de fonte;
- diagnóstico: gaps técnicos;
- RAG: consulta de recuperação, chunks candidatos e chunks reranqueados;
- saída: recomendações e briefing;
- controle: avisos, erros recuperáveis e métricas de execução.

Modelos de domínio reutilizáveis representam evidência, citação e erro. O estado não transporta clientes de banco, SDKs, sessões HTTP nem segredos.

## Configuração

`pydantic-settings` carregará uma configuração imutável e validada, dividida logicamente em:

- aplicação e ambiente;
- servidor HTTP e CORS;
- PostgreSQL e pool de conexões;
- Qdrant e coleção vetorial;
- chat model;
- embeddings;
- reranker;
- timeouts, tentativas e logging.

`.env.example` documentará as variáveis sem conter valores secretos. Em teste, configurações serão construídas explicitamente para evitar dependência acidental do ambiente da máquina.

## Ferramentas e bibliotecas

| Grupo | Escolha | Finalidade |
| --- | --- | --- |
| Gestão de projeto | `uv`, `pyproject.toml`, `uv.lock` | Ambiente, dependências, scripts reproduzíveis |
| API | FastAPI, Uvicorn | HTTP assíncrono e OpenAPI |
| Contratos | Pydantic, pydantic-settings | Validação de entrada, saída e configuração |
| Orquestração | LangGraph, langchain-core | Estado e contratos da futura pipeline |
| Persistência | SQLAlchemy async, psycopg, Alembic | Acesso ao PostgreSQL, pool e migrações |
| Recuperação | qdrant-client, rank-bm25 | Similaridade vetorial e índice lexical |
| Integrações | Cohere SDK, HTTPX | Reranking e cliente HTTP assíncrono com timeout explícito |
| Qualidade | Ruff, mypy, pytest, pytest-asyncio, pytest-cov | Formatação, lint, tipos, testes e cobertura |
| Arquitetura | import-linter | Regras automatizadas entre camadas |
| Automação | pre-commit, GitHub Actions | Verificação local e integração contínua |

O cliente Cohere será encapsulado por um adaptador mínimo de reranking. SDKs concretos de chat e embeddings só devem ser adicionados quando o provedor for escolhido. Os contratos internos não expõem tipos desses SDKs.

## API e operação

- `GET /health/live` confirma apenas que o processo atende requisições.
- `GET /health/ready` verifica PostgreSQL e Qdrant sem chamar provedores pagos.
- Rotas funcionais futuras ficam sob `/api/v1`; não será criado endpoint fictício de análise.
- Middleware aceita ou gera `X-Correlation-ID` e devolve o valor na resposta.
- Erros usam um envelope estável com `code`, `message` e `correlation_id`.
- Logging usa a biblioteca padrão configurada para JSON, evitando uma dependência adicional nesta etapa.
- O lifespan cria e encerra o pool e os clientes compartilhados da aplicação.

## Ambiente local

Um `compose.yaml` fornecerá PostgreSQL 16 e Qdrant, ambos com volumes nomeados e healthchecks. O backend poderá rodar no host para preservar reload rápido. Um Dockerfile da API não é necessário para o escopo desta fundação e só deverá ser criado quando houver uma estratégia de implantação.

A inclusão do Compose substitui, após aprovação desta spec, a decisão temporária da especificação 001 de não configurar contêineres. O README e o registro de decisões removidas deverão ser atualizados durante a implementação para deixar essa evolução explícita.

## Decisões

### D-01 — Monólito modular antes de serviços distribuídos

Todos os módulos compartilham o mesmo processo e repositório. Filas, workers e microsserviços adicionariam custo operacional sem um requisito atual, enquanto os limites internos preservam a possibilidade de extração futura.

### D-02 — Recuperação híbrida com Qdrant e BM25

Qdrant atende a busca vetorial recomendada pelo TAPI, enquanto BM25 atende a busca lexical sobre o corpus persistido. O UUID do chunk correlaciona os resultados com o texto e a fonte canônicos no PostgreSQL. A duplicação é controlada e não transfere ao banco vetorial a responsabilidade por citações.

### D-03 — Portas internas para provedores de IA

Chat, embeddings e reranking serão protocolos da aplicação. Essa fronteira permite trocar modelos e testar sem rede. Cohere é o primeiro adaptador de reranking; a seleção de modelos de chat e embeddings pertence às features que consumirem cada capacidade.

### D-04 — SQLAlchemy assíncrono com psycopg

SQLAlchemy fornece mapeamento e transações explícitas; psycopg fornece o driver e pool assíncronos. Consultas específicas de recuperação poderão usar SQL explícito dentro dos adaptadores sem vazar para a aplicação.

### D-05 — Migrações desde o primeiro schema

Alembic será a única forma de evoluir o schema. Criação automática de tabelas na inicialização é proibida, pois mascara diferenças entre ambientes e dificulta rollback.

### D-06 — Sem endpoint funcional incompleto

A fundação expõe apenas saúde e OpenAPI. A rota de análise será especificada quando houver comportamento ponta a ponta, evitando contratos prematuros e respostas simuladas.

### D-07 — Configuração fail-fast

Configurações obrigatórias são verificadas antes de servir tráfego. Readiness cobre indisponibilidade posterior do banco; liveness não depende de rede.

### D-08 — Testes reais apenas na fronteira de persistência

Unidades usam fakes definidos pelos protocolos. Testes de repositório, migração e armazenamento vetorial usam PostgreSQL e Qdrant; provedores pagos permanecem substituídos por fakes determinísticos.

### D-09 — Event loop explícito no entrypoint para compatibilidade com Windows

O Uvicorn seleciona `ProactorEventLoop` por padrão ao executar um único processo
no Windows, enquanto o Psycopg assíncrono requer um selector loop. O entrypoint
`startup-radar` fornece uma factory de event loop compatível ao Uvicorn. A
decisão fica na composition root, não altera o código de persistência e também
funciona no subprocesso de reload.

## Registro da implementação

- Implementação técnica verificada em 5 de setembro de 2026.
- PostgreSQL foi fixado em `16.10-alpine` e Qdrant em `v1.19.0`; a segunda versão
  foi alinhada ao cliente Python resolvido no lockfile para evitar divergência
  de protocolo durante os testes reais.
- A migration inicial foi validada nos ciclos `upgrade`, `downgrade base` e novo
  `upgrade`, incluindo os timestamps dos chunks usados pelos modelos ORM.
- O escopo permaneceu restrito à fundação: nenhum prompt, chamada paga, lógica
  de agente ou endpoint de análise foi introduzido.

## Verificação

1. Criar o ambiente a partir do lockfile em um clone limpo.
2. Subir PostgreSQL e Qdrant pelo Compose e aguardar os healthchecks.
3. Aplicar todas as migrações em banco vazio, inspecionar tabelas e índices, reverter a revisão e aplicá-la novamente.
4. Iniciar a API e verificar liveness, readiness, OpenAPI, correlação, CORS e envelope de erro.
5. Executar formatação em modo check, lint, mypy e testes unitários.
6. Executar testes de arquitetura e integração com PostgreSQL e Qdrant, incluindo criação idempotente da coleção, com cobertura.
7. Interromper a API e confirmar encerramento do pool e dos clientes sem recursos pendentes.
8. Executar lint, testes e build do frontend para detectar regressões.
9. Inspecionar o repositório para confirmar ausência de credenciais e de lógica de agentes.
10. Conferir cada critério de aceite e atualizar a matriz caso a implementação aprovada mude.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| A fundação antecipar regras dos agentes | Limitar o estado a contratos de transporte e manter prompts, arestas e decisões em specs próprias |
| Dimensão do embedding divergir do modelo escolhido | Tornar a dimensão explícita, versionar a coleção e exigir reindexação para mudanças |
| Camadas existirem apenas como pastas | Aplicar regras de importação e testes arquiteturais |
| Serviços locais divergirem dos ambientes alvo | Fixar versões de PostgreSQL e Qdrant e validar ambos em CI |
| Logs vazarem conteúdo sensível | Allowlist de campos, sanitização de erros e testes de redaction |
| Retentativas duplicarem operações | Restringir retry a operações idempotentes e falhas transitórias |
| Contratos de provedores ficarem genéricos demais | Definir somente as operações exigidas pelo pipeline descrito no TAPI |
| Ferramentas de qualidade tornarem o fluxo confuso | Expor comandos curtos, separados e um comando agregado documentado |

## Decisões adiadas

- Provedor e modelo de chat definitivos.
- Modelo e dimensão de embeddings definitivos antes da primeira ingestão real.
- Modelo Cohere de reranking e política de fallback.
- Algoritmo de fusão dos rankings lexical e vetorial.
- Checkpoint persistente do LangGraph e política de retomada.
- Contrato HTTP de submissão, acompanhamento e cancelamento de análises.
- Autenticação, autorização, rate limiting e implantação.
