# Scripts operacionais

## Base de conhecimento NVIDIA

`nvidia_sources.json` é o manifesto versionado das fontes oficiais indicadas no
TAPI. Ele define uma identidade estável (`source_key`), tecnologia, URL canônica,
tipo e obrigatoriedade. A ingestão não descobre nem segue novas páginas.

Antes de ingerir, aplique as migrações e configure PostgreSQL, Qdrant e um
endpoint de embeddings compatível com a API OpenAI:

```powershell
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend startup-radar-knowledge ingest
uv run --project backend startup-radar-knowledge verify
```

É possível limitar a operação:

```powershell
uv run --project backend startup-radar-knowledge ingest --technology cuda
uv run --project backend startup-radar-knowledge ingest --source-key nvidia-nim
```

O dry-run prepara e valida os dados sem escrever. Para um teste totalmente
offline, informe fixtures e embeddings determinísticos:

```powershell
uv run --project backend startup-radar-knowledge dry-run --source-key nvidia-nim --fixture-dir backend/tests/fixtures/knowledge --offline-embeddings
```

A URL oficial de cada documento é persistida em
`knowledge_documents.source_url`. Chunks e Qdrant recebem uma cópia para
rastreabilidade; o PostgreSQL permanece canônico. Uma execução interrompida pode
ser repetida: IDs e upserts são determinísticos, e `verify` aponta vetores
ausentes ou órfãos.

Os relatórios apresentam apenas identificadores, status e contagens. Conteúdo,
vetores e credenciais não são impressos.

Testes que acessam fontes reais exigem simultaneamente
`RUN_INTEGRATION_TESTS=1` e `RUN_EXTERNAL_TESTS=1`; eles não fazem parte da suíte
padrão. Nenhum teste chama LLM.
