# Plano 012: NVIDIA Knowledge Base

## Estratégia

Implementar a ingestão como caso de uso independente do LangGraph. Um manifesto
de fontes alimenta uma pipeline composta por portas pequenas para coleta,
embeddings, persistência e índice vetorial. A limpeza, normalização, hashing e o
chunking permanecem funções determinísticas e testáveis sem I/O.

O PostgreSQL será o registro canônico de documentos, revisões e chunks. Qdrant é
uma projeção vetorial reconciliável. O BM25 será construído a partir dos chunks
ativos no PostgreSQL em ordem estável; sua busca e combinação com o ranking
vetorial pertencem a uma spec futura.

## Estrutura prevista

```text
backend/
├── migrations/versions/
│   └── *_nvidia_knowledge_ingestion.py
├── scripts/
│   ├── README.md
│   └── nvidia_sources.json
├── src/app/
│   ├── application/
│   │   ├── contracts/knowledge_ingestion.py
│   │   ├── ports/knowledge_sources.py
│   │   └── services/knowledge_ingestion.py
│   ├── domain/
│   │   └── knowledge.py
│   ├── infrastructure/
│   │   ├── ingestion/
│   │   │   ├── http_source.py
│   │   │   ├── normalization.py
│   │   │   ├── chunking.py
│   │   │   └── manifest.py
│   │   ├── persistence/
│   │   ├── retrieval/bm25.py
│   │   ├── providers/embeddings.py
│   │   └── vector/qdrant.py
│   └── cli/knowledge.py
└── tests/
    ├── fixtures/knowledge/
    ├── unit/
    └── integration/
```

Os nomes podem ser ajustados durante a implementação se os limites de camada e
os contratos desta spec forem preservados. O manifesto deve continuar como
artefato humano, legível e versionado.

## Fases de implementação

### 1. Contratos, catálogo e configuração

- Criar enum canônico para as tecnologias obrigatórias.
- Definir contratos imutáveis para fonte, documento normalizado, chunk preparado,
  revisão, relatório e falha.
- Criar porta assíncrona de obtenção de conteúdo e estender portas dos
  repositórios para upsert, listagem ativa e reconciliação.
- Definir configuração validada para manifesto, HTTP, limites de conteúdo,
  chunking, lotes, pipeline version e concorrência limitada.
- Criar e validar o manifesto inicial com todas as URLs do TAPI.

### 2. Persistência versionada

- Criar migração reversível para identidade por `source_key`, tecnologia,
  revisão, versão da pipeline e `ingested_at`.
- Preservar `knowledge_documents.source_url` como coluna obrigatória e fonte
  canônica da URL oficial, propagando seu valor aos chunks e payloads vetoriais.
- Remover a suposição de que conteúdos iguais representam necessariamente a
  mesma fonte, mantendo hash para detecção de mudanças.
- Evoluir entidades, mapeamentos e repositórios sem expor SQL à aplicação.
- Definir consultas em ordem estável para chunks ativos e detecção de órfãos.

### 3. Coleta e preparação determinística

- Implementar cliente HTTP com allowlist, HTTPS, timeout, limite de bytes,
  redirecionamento validado e tentativas somente para falhas transitórias.
- Implementar adaptador de fixtures com a mesma porta para testes e dry-run.
- Normalizar HTML, Markdown e texto sem resumir ou traduzir.
- Implementar chunking por heading/parágrafo, com fallback por tamanho,
  sobreposição limitada e localizadores de origem.
- Gerar SHA-256 e UUIDs determinísticos usando namespaces e versões explícitos.

### 4. Embeddings, PostgreSQL e Qdrant

- Resolver o `EmbeddingModel` configurado no composition root da CLI.
- Processar chunks em lotes e validar contagem, finitude e dimensão.
- Preparar a revisão completa antes das escritas.
- Persistir documento e chunks em transação, preservando a revisão anterior até
  que a nova preparação seja válida.
- Fazer upsert Qdrant com UUID do chunk e payload mínimo.
- Copiar para o payload do chunk a mesma `source_url` persistida no documento,
  sem permitir divergência entre PostgreSQL e Qdrant.
- Remover pontos obsoletos após o upsert e tornar a operação reconciliável.
- Registrar fingerprint de embedding e rejeitar coleção incompatível.

### 5. Corpus BM25 e verificação

- Estender o construtor BM25 para carregar chunks ativos do repositório em ordem
  determinística e preservar seus UUIDs.
- Calcular fingerprint do corpus a partir de IDs e hashes ordenados.
- Implementar verificador somente leitura para cobertura, duplicações,
  metadados, hashes, vetores ausentes/órfãos, dimensão e corpus BM25.
- Não implementar consulta híbrida, normalização ou fusão de scores.

### 6. CLI e documentação

- Adicionar entry points para `ingest`, `dry-run` e `verify`.
- Permitir selecionar todas as fontes, tecnologia ou `source_key`.
- Produzir saída resumida, sanitizada e código de saída estável.
- Documentar configuração, serviços necessários, exemplos, integração opt-in,
  reexecução e recuperação de falhas.
- Atualizar README, `.env.example` e `backend/scripts/README.md`.

### 7. Testes e qualidade

- Criar fixtures mínimas locais de HTML, Markdown e texto.
- Bloquear HTTP e cliente real de embeddings na suíte padrão.
- Testar funções puras com relógio e UUID namespace controlados.
- Testar serviço com fakes para unchanged, update e falhas em cada fronteira.
- Testar adaptadores por transporte fake.
- Testar PostgreSQL e Qdrant reais somente com `RUN_INTEGRATION_TESTS=1`.
- Manter fontes/embeddings reais em testes `external` separados e desabilitados.
- Executar Ruff, mypy, import-linter, pytest/cobertura e regressão do frontend.

## Decisões

### D-01 — Manifesto explícito, sem crawler aberto

O escopo de coleta é auditável e limitado. A ingestão não segue links nem aceita
URL arbitrária, reduzindo variação, risco de SSRF e entrada de fontes não oficiais.

### D-02 — Identidade lógica separada do hash de conteúdo

`source_key` identifica a fonte ao longo do tempo. `content_hash` identifica a
revisão observada. Assim, atualização não cria outro documento lógico e duas
fontes legítimas com texto igual não são fundidas.

### D-03 — IDs determinísticos e índices derivados

UUIDs determinísticos tornam upserts repetíveis. PostgreSQL retém o texto
canônico; Qdrant e BM25 podem ser reconstruídos e reconciliados.

### D-04 — Publicação convergente sem transação distribuída

A revisão é preparada antes da escrita. Upserts são idempotentes, pontos antigos
só são removidos após os novos e o verificador detecta divergências para que uma
reexecução convirja ao estado canônico.

### D-05 — BM25 preparado, não consultado pelo produto

Esta feature garante corpus, tokenização existente, identidade e reconstrução.
Consulta híbrida, fusão de ranking e reranking serão definidos com o NVIDIA RAG
Agent.

### D-06 — Testes offline por padrão

Fixtures e fakes cobrem todo o comportamento. Banco/Qdrant e qualquer chamada
externa exigem marcadores e flags explícitas; nenhuma credencial ambiente ativa
integrações implicitamente.

## Verificação prevista

1. Validar o manifesto e a cobertura das 16 tecnologias.
2. Executar testes unitários offline de contratos, transformação, serviço e CLI.
3. Executar Ruff format/check, mypy e import-linter.
4. Executar cobertura mínima de 80%.
5. Habilitar integração PostgreSQL/Qdrant e testar ingestão e reingestão.
6. Executar dry-run e verify com fixtures.
7. Executar lint, testes e build do frontend.
8. Revisar critérios, comandos, logs, migração e documentação.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Página oficial mudar de estrutura | Adaptadores pequenos, fixtures e erro por fonte |
| Fonte redirecionar para domínio externo | Validar cada destino contra allowlist |
| Conteúdo repetitivo degradar chunks | Normalização determinística e golden tests |
| Atualização deixar vetor órfão | IDs estáveis, upsert, verificador e reconciliação |
| Modelo de embedding mudar | Fingerprint e coleção versionada |
| Falha entre PostgreSQL e Qdrant | Última revisão utilizável e convergência na reexecução |
| Teste consumir rede ou tokens | Guardas automáticas, fakes mínimos e opt-in duplo |
| BM25 divergir do texto canônico | Construção exclusiva a partir dos chunks ativos |

## Evoluções posteriores

- NVIDIA RAG Agent e consulta híbrida vetorial + BM25;
- fusão de rankings e Cohere Rerank;
- recomendações e citações combinando startup e base NVIDIA;
- agendamento, histórico operacional e painel administrativo;
- novos formatos, OCR ou transcrição, mediante nova especificação.

## Resultado da implementação

- Manifesto versionado cobre as 16 tecnologias obrigatórias e fontes oficiais do TAPI.
- Pipeline assíncrona coleta, normaliza, divide, gera embeddings e publica revisões.
- PostgreSQL preserva texto e `source_url`; Qdrant replica a URL e usa o UUID do chunk.
- BM25 é reconstruível e verificável a partir dos chunks canônicos.
- Dry-run funciona offline com fixtures e embeddings determinísticos.
- Reingestão inalterada não recria vetores; falhas parciais são reconciliadas.
- Migração passou em upgrade, downgrade e novo upgrade.
- Suíte offline, integração PostgreSQL/Qdrant, cobertura e frontend foram aprovados.

## Sugestão de commit

`feat(knowledge): build reproducible NVIDIA knowledge ingestion`
