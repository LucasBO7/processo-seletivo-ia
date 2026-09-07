# Especificação 012: NVIDIA Knowledge Base

## Status

Implementada e verificada em 7 de setembro de 2026; aguardando aprovação
explícita da entrega para conclusão formal.

## Contexto

O fluxo atual termina no Evidence Validator com perfis e classificações apoiados
pelos documentos das startups. O futuro NVIDIA RAG Agent precisará consultar um
corpus próprio, reproduzível e citável sobre tecnologias NVIDIA, mas esse corpus
ainda não é ingerido nem indexado.

A fundação do backend já definiu PostgreSQL como fonte de verdade dos textos,
Qdrant como índice vetorial derivado e BM25 como índice lexical reconstruível a
partir dos chunks persistidos. Esta feature concretiza essas decisões sem criar o
agente de RAG, fusão de rankings, reranking ou recomendações.

O catálogo inicial será declarado em um manifesto versionado e partirá das
fontes oficiais indicadas no TAPI. Novas fontes somente poderão ser adicionadas
quando forem oficiais e estiverem registradas no manifesto.

## Objetivos

- Manter um catálogo versionado de fontes oficiais por tecnologia NVIDIA.
- Coletar, limpar e normalizar documentos de modo determinístico e reproduzível.
- Produzir chunks citáveis com identidade, origem e posição preservadas.
- Gerar embeddings por uma porta substituível e armazená-los no Qdrant.
- Persistir documentos e chunks canônicos no PostgreSQL.
- Preparar um corpus BM25 reconstruível e verificável a partir do PostgreSQL.
- Permitir reingestão e atualização sem duplicar documentos, chunks ou vetores.
- Disponibilizar comandos documentados de ingestão, verificação e modo seco.
- Manter os testes padrão totalmente offline, determinísticos e sem serviços pagos.

## Catálogo mínimo de fontes

O manifesto inicial deve conter, no mínimo, as seguintes tecnologias e URLs
indicadas no TAPI:

| Tecnologia | Fontes oficiais iniciais |
| --- | --- |
| NVIDIA Inception | `https://www.nvidia.com/en-us/startups/` |
| NVIDIA NIM | `https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/`, `https://build.nvidia.com/` |
| NVIDIA NeMo | `https://www.nvidia.com/en-us/ai-data-science/products/nemo/` |
| NeMo Guardrails | `https://github.com/NVIDIA/NeMo-Guardrails` |
| Triton Inference Server | `https://developer.nvidia.com/triton-inference-server`, `https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/` |
| TensorRT-LLM | `https://github.com/NVIDIA/TensorRT-LLM` |
| RAPIDS | `https://rapids.ai/` |
| cuDF | `https://docs.rapids.ai/api/cudf/stable/` |
| cuML | `https://docs.rapids.ai/api/cuml/stable/` |
| CUDA | `https://developer.nvidia.com/cuda-toolkit` |
| NVIDIA Riva | `https://developer.nvidia.com/riva` |
| NVIDIA Omniverse | `https://www.nvidia.com/en-us/omniverse/` |
| NVIDIA Isaac | `https://developer.nvidia.com/isaac` |
| NVIDIA Clara | `https://www.nvidia.com/en-us/clara/` |
| NVIDIA Morpheus | `https://developer.nvidia.com/morpheus-cybersecurity` |
| NVIDIA AI Enterprise | `https://www.nvidia.com/en-us/data-center/products/ai-enterprise/` |

O manifesto também poderá registrar os materiais introdutórios NVIDIA presentes
no TAPI, como `https://blogs.nvidia.com/blog/ai-5-layer-cake/` e materiais do
canal oficial no YouTube. Eles não substituem a cobertura obrigatória das páginas
de produto e documentação. Uma fonte opcional indisponível deve ser reportada,
sem mascarar a ausência de uma tecnologia obrigatória.

## Histórias do usuário

### US-01 — Manter fontes oficiais auditáveis

Como pessoa mantenedora, quero declarar as fontes em um manifesto versionado para
saber exatamente o que compõe a base e reproduzir uma ingestão.

Critérios de aceite:

- Cada entrada possui `source_key` estável, tecnologia canônica, URL canônica,
  tipo de conteúdo, obrigatoriedade e adaptador de extração.
- `source_key` e URL canônica são únicas.
- URLs de rede usam HTTPS e pertencem a domínios oficiais permitidos no manifesto.
- O catálogo cobre individualmente todas as 16 tecnologias mínimas desta spec.
- O verificador falha quando uma tecnologia obrigatória não possui documento e
  ao menos um chunk válidos.
- Alterações no catálogo são visíveis no controle de versão e não dependem de
  configuração oculta ou descoberta automática da web.

### US-02 — Representar e normalizar documentos

Como pessoa desenvolvedora, quero uma representação independente do formato de
origem para executar a mesma pipeline sobre páginas, documentação e fixtures.

Critérios de aceite:

- O documento normalizado contém `source_key`, título, tecnologia, URL oficial,
  tipo de conteúdo, conteúdo textual, data de publicação quando disponível,
  data de ingestão UTC e hash SHA-256.
- Ao persistir o documento, sua URL oficial é gravada obrigatoriamente na coluna
  `knowledge_documents.source_url`, sem substituição por URL do manifesto,
  redirecionamento intermediário ou identificador interno na saída persistida.
- A coleta aceita conteúdo por uma porta interna; HTTP e leitura de fixtures são
  adaptadores substituíveis.
- HTML remove navegação, scripts, estilos, banners e conteúdo repetitivo sem
  remover títulos, listas, tabelas textuais ou blocos de código relevantes.
- Markdown e texto preservam hierarquia de títulos e conteúdo técnico.
- Espaços, quebras de linha e Unicode são normalizados deterministicamente, sem
  traduzir, resumir ou reescrever o conteúdo.
- Documento vazio, tipo não permitido, resposta excessiva ou fonte fora da
  allowlist é rejeitado com erro sanitizado.
- Timeout, tentativas transitórias, tamanho máximo e identificação do cliente são
  configuráveis; redirecionamento para domínio não permitido é bloqueado.

### US-03 — Produzir chunks citáveis e determinísticos

Como futura consumidora do corpus, quero recuperar trechos que preservem sua
posição e origem para produzir citações verificáveis.

Critérios de aceite:

- O chunking prioriza limites de seção e parágrafo e usa tamanho e sobreposição
  configuráveis e versionados.
- A mesma entrada, configuração e versão do algoritmo produzem a mesma ordem,
  conteúdo, hashes e identificadores.
- Cada chunk preserva título, tecnologia, URL oficial, UUID do documento, índice,
  seção ou heading de origem, posição inicial/final quando disponível, data de
  ingestão, hash do conteúdo e versão do pipeline.
- Chunks vazios ou compostos apenas por ruído não são persistidos.
- A sobreposição não altera a posição canônica do trecho e não impede a
  deduplicação dentro do documento.
- Pelo menos um localizador auditável, formado por seção e/ou posição, existe em
  todo chunk.

### US-04 — Gerar embeddings de forma desacoplada

Como pessoa operadora, quero gerar vetores por uma interface interna para trocar
o provedor e testar sem rede ou custo.

Critérios de aceite:

- A pipeline usa somente o contrato `EmbeddingModel`, sem tipos de SDK na
  aplicação ou no domínio.
- Textos são enviados em lotes com limites configuráveis e ordem preservada.
- A quantidade e dimensão dos vetores são validadas antes de qualquer escrita.
- Vetores não finitos, quantidade divergente ou dimensão incorreta abortam a
  publicação da revisão.
- O fingerprint do embedding registra provedor, modelo e dimensão sem segredo.
- Trocar modelo ou dimensão exige coleção Qdrant versionada e reindexação
  explícita; não mistura vetores incompatíveis na mesma coleção.

### US-05 — Persistir e preparar recuperação lexical

Como futura implementação do NVIDIA RAG Agent, quero encontrar no PostgreSQL o
texto canônico correspondente a cada ponto vetorial e reconstruir o BM25.

Critérios de aceite:

- Documentos e chunks são persistidos no PostgreSQL antes de serem considerados
  publicados no índice derivado.
- `knowledge_documents.source_url` é a fonte canônica da URL de cada documento;
  seu valor deve corresponder à URL oficial validada usada na ingestão.
- O UUID de cada ponto Qdrant é o UUID do chunk correspondente.
- O payload vetorial contém somente metadados necessários a filtro e
  rastreabilidade, incluindo uma cópia de `source_url`; o PostgreSQL continua
  sendo a fonte canônica do texto e da URL.
- A coleção é criada ou validada com nome, dimensão e distância configurados.
- O corpus BM25 é montado deterministicamente a partir dos chunks ativos do
  PostgreSQL, em ordem estável, preservando UUID e texto.
- Um comando de verificação constrói o BM25 e comprova que todos os seus IDs
  existem no PostgreSQL; esta feature não executa busca híbrida nem funde scores.
- Contagens e hashes permitem detectar divergência entre PostgreSQL, Qdrant e o
  corpus preparado para BM25.

### US-06 — Reingerir e atualizar sem duplicações

Como pessoa operadora, quero executar a ingestão repetidamente para atualizar a
base com segurança.

Critérios de aceite:

- A identidade lógica do documento deriva do `source_key`, não do conteúdo atual.
- Uma fonte inalterada é marcada como `unchanged`, sem regenerar embeddings nem
  criar registros ou pontos.
- Conteúdo alterado cria uma nova revisão rastreável do documento e sincroniza o
  conjunto de chunks ativos.
- IDs de chunks são determinísticos para a revisão e o localizador; reexecuções
  idênticas mantêm os mesmos IDs.
- O upsert no Qdrant não cria duplicatas e chunks obsoletos são removidos somente
  depois da publicação bem-sucedida dos novos pontos.
- Falha parcial não apaga a última revisão utilizável; uma nova execução consegue
  reconciliar PostgreSQL e Qdrant.
- A execução produz resumo com `created`, `updated`, `unchanged`, `skipped`,
  `failed`, documentos, chunks e vetores, sem registrar o conteúdo integral.

### US-07 — Executar e verificar operacionalmente

Como pessoa desenvolvedora, quero comandos claros para inspecionar o plano,
ingerir e validar a base.

Critérios de aceite:

- Existe comando de `dry-run` que coleta, normaliza, divide e valida sem escrever
  em PostgreSQL ou Qdrant e sem chamar embeddings reais quando um fake é indicado.
- Existe comando de ingestão com seleção opcional por tecnologia ou `source_key`.
- Existe comando de verificação somente leitura para cobertura, metadados,
  duplicações, hashes, dimensão, IDs órfãos e corpus BM25.
- Os comandos retornam código diferente de zero quando houver falha obrigatória.
- README, `.env.example` e `backend/scripts/README.md` documentam pré-requisitos,
  parâmetros, exemplos, efeitos e como recuperar uma execução interrompida.
- Logs estruturados contêm apenas identificadores, versão, duração, status e
  contagens; conteúdo integral, vetores, tokens e segredos não são registrados.

### US-08 — Testar sem dependências externas por padrão

Como pessoa mantenedora, quero uma suíte rápida e determinística que não consuma
rede nem serviços pagos.

Critérios de aceite:

- Testes unitários usam fixtures locais pequenas, relógio controlado, cliente de
  conteúdo falso, embedding fake de dimensão mínima e repositórios falsos.
- Os testes cobrem limpeza, normalização, chunking, hashing, IDs, atualização,
  reconciliação, payloads, BM25 e erros.
- A suíte padrão falha imediatamente se tentar acessar HTTP ou criar cliente real
  de embeddings.
- Testes do adaptador HTTP usam transporte fake e não acessam a internet.
- Testes reais de PostgreSQL e Qdrant usam a marca `integration` e exigem
  `RUN_INTEGRATION_TESTS=1`.
- Chamadas a fontes oficiais ou embeddings reais usam marca `external`, exigem
  habilitação e credenciais explícitas e nunca executam no comando padrão ou CI.
- Nenhum teste usa LLM; nenhuma chamada real ocorre apenas por haver credenciais
  no ambiente da máquina.

### US-09 — Preservar o limite da feature

Como pessoa mantenedora, quero preparar a base sem antecipar decisões do agente
de recomendação.

Critérios de aceite:

- Nenhum nó, estado ou aresta do LangGraph é alterado nesta feature.
- Não há consulta de usuário, RAG, busca híbrida, fusão de ranking ou reranking.
- Não há classificação de startup nem recomendação de produto NVIDIA.
- A ingestão não chama chat model e não produz conteúdo sintético.
- Nenhum endpoint público novo é necessário; a operação ocorre por comandos.

## Contratos conceituais

```text
KnowledgeSource
├── source_key: string
├── technology: NvidiaTechnology
├── canonical_url: URL
├── content_type: html | markdown | text
├── extractor: string
├── required: boolean
└── enabled: boolean

NormalizedKnowledgeDocument
├── document_id: UUID
├── source_key: string
├── title: string
├── technology: NvidiaTechnology
├── source_url: URL
├── content_type: string
├── content: string
├── published_at: datetime | null
├── ingested_at: datetime UTC
├── content_hash: SHA-256
└── pipeline_version: string

PreparedKnowledgeChunk
├── chunk_id: UUID
├── document_id: UUID
├── chunk_index: integer
├── content: string
├── content_hash: SHA-256
└── metadata
    ├── title
    ├── technology
    ├── source_url
    ├── source_key
    ├── source_section
    ├── start_offset | null
    ├── end_offset | null
    ├── ingested_at
    ├── pipeline_version
    └── embedding_fingerprint
```

`NvidiaTechnology` deve ser um catálogo fechado com as 16 tecnologias mínimas.
Aliases de exibição podem existir, mas os valores persistidos são estáveis.

## Processo de ingestão

```text
manifesto versionado
  → validação de fonte e allowlist
  → coleta com limites
  → limpeza e normalização
  → hash e detecção de mudança
  → chunking determinístico
  → embeddings em lote
  → validação local dos vetores
  → transação PostgreSQL
  → upsert Qdrant
  → remoção reconciliável de pontos obsoletos
  → construção/verificação do corpus BM25
  → relatório da execução
```

A preparação anterior à escrita deve ser concluída para toda a revisão. O
PostgreSQL registra a revisão canônica; Qdrant e BM25 são derivados e podem ser
reconstruídos. Como não há transação distribuída, o processo deve ser convergente:
uma interrupção deixa a última revisão utilizável e a próxima execução reconcilia
o índice vetorial a partir do estado canônico.

## Códigos operacionais mínimos

| Código | Situação |
| --- | --- |
| `knowledge_source_invalid` | Manifesto, URL, domínio ou tipo inválido |
| `knowledge_fetch_failed` | Fonte não pôde ser coletada após política permitida |
| `knowledge_document_empty` | Limpeza não produziu conteúdo utilizável |
| `knowledge_embedding_invalid` | Quantidade, dimensão ou valor do vetor é inválido |
| `knowledge_persistence_failed` | Revisão não pôde ser persistida |
| `knowledge_vector_sync_failed` | Qdrant não pôde ser sincronizado |
| `knowledge_index_inconsistent` | Verificação encontrou ausência, órfão ou divergência |
| `knowledge_required_coverage_missing` | Tecnologia obrigatória sem cobertura válida |

Mensagens externas são sanitizadas. O relatório pode associar o erro ao
`source_key`, mas não deve incluir segredo, vetor ou conteúdo integral.

## Requisitos funcionais

- **RF-01:** fornecer manifesto versionado de fontes NVIDIA oficiais.
- **RF-02:** validar catálogo, cobertura, URLs, domínios e tipos de conteúdo.
- **RF-03:** coletar documentos por porta assíncrona e adaptadores substituíveis.
- **RF-04:** limpar e normalizar HTML, Markdown e texto deterministicamente.
- **RF-05:** gerar documentos e chunks com metadados completos e rastreáveis.
- **RF-06:** gerar e validar embeddings em lotes pela porta existente.
- **RF-07:** persistir documentos e chunks canônicos no PostgreSQL, gravar
  obrigatoriamente a URL oficial em `knowledge_documents.source_url` e propagá-la
  sem alteração aos metadados dos chunks.
- **RF-08:** sincronizar pontos vetoriais no Qdrant usando UUIDs dos chunks.
- **RF-09:** preparar e verificar corpus BM25 reconstruível do PostgreSQL.
- **RF-10:** detectar conteúdo inalterado e atualizar revisões idempotentemente.
- **RF-11:** reconciliar falhas parciais sem remover a última revisão utilizável.
- **RF-12:** fornecer comandos de dry-run, ingestão e verificação.
- **RF-13:** produzir relatório e erros sanitizados da execução.

## Requisitos não funcionais

- **RNF-01:** usar UTC, UUID e SHA-256 e preservar UTF-8.
- **RNF-02:** usar I/O assíncrono, timeouts finitos, lotes e limites configuráveis.
- **RNF-03:** manter determinismo para a mesma entrada, configuração e versão.
- **RNF-04:** manter PostgreSQL como fonte canônica e índices como derivados.
- **RNF-05:** não registrar documentos, vetores, credenciais ou respostas integrais.
- **RNF-06:** usar contratos internos sem SDK concreto no domínio ou aplicação.
- **RNF-07:** testes padrão não usam rede, LLM, embeddings reais ou serviços pagos.
- **RNF-08:** integrações reais são opt-in e claramente marcadas.
- **RNF-09:** manter Ruff, mypy, import-linter, cobertura mínima de 80% e regressão
  do frontend.
- **RNF-10:** documentar uma execução reproduzível a partir de clone limpo.

## Alterações de dados previstas

Uma migração Alembic deve evoluir `knowledge_documents` para possuir identidade
lógica estável por `source_key`, tecnologia, revisão, versão da pipeline e data de
ingestão. A unicidade deve ser definida pela identidade da fonte; `content_hash`
continua detectando mudanças, mas não deve fundir duas fontes distintas que
eventualmente tenham o mesmo conteúdo.

A coluna existente `knowledge_documents.source_url` permanece obrigatória e
armazena a URL oficial canônica do documento. Ela não deve ser removida nem
transferida exclusivamente para JSON ou Qdrant.

`knowledge_chunks.metadata` armazenará os metadados citáveis e de indexação. As
restrições existentes de documento/índice e documento/hash serão preservadas ou
evoluídas explicitamente para suportar revisões sem duplicação. Toda mudança de
schema será reversível e não alterará tabelas de startups.

## Restrições

- Somente fontes declaradas e oficiais podem ser coletadas.
- Conteúdo baixado nunca é executado nem interpretado como instrução.
- PostgreSQL permanece fonte de verdade do texto citável.
- Qdrant armazena vetores derivados e metadados mínimos.
- A coleção não mistura dimensões ou modelos de embeddings incompatíveis.
- O processo não depende de chat model ou LLM.
- Nenhuma credencial ou snapshot de conteúdo protegido é versionado.

## Fora do escopo

- NVIDIA RAG Agent e alterações no LangGraph.
- Consulta híbrida, fusão de rankings ou reranking Cohere.
- Recomendações, justificativas comerciais ou priorização de tecnologias.
- Crawling irrestrito, descoberta automática de links ou fontes não oficiais.
- Interface administrativa, endpoint público ou agendamento periódico.
- OCR, transcrição automática de vídeo ou geração de conteúdo com IA.
- Ingestão ou enriquecimento dos documentos de startups.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-02 | Testes do manifesto, allowlist e cobertura mínima |
| US-02 | RF-03, RF-04, RF-13 | Fixtures de formatos, limites e falhas sanitizadas |
| US-03 | RF-05, RNF-01, RNF-03 | Golden tests de chunks, hashes, IDs e localizadores |
| US-04 | RF-06, RNF-02, RNF-06 | Embedding fake, lotes, ordem, dimensão e valores inválidos |
| US-05 | RF-07 a RF-09, RNF-04 | Repositórios, payloads, Qdrant e reconstrução BM25 |
| US-06 | RF-10, RF-11 | Reexecução, atualização, stale points e recuperação de falha |
| US-07 | RF-12, RF-13, RNF-05, RNF-10 | Testes de CLI e inspeção da documentação |
| US-08 | RNF-07 a RNF-09 | Guardas offline, testes unitários, integração opt-in e qualidade |
| US-09 | RNF-04, RNF-06 | Testes arquiteturais e inspeção do escopo |

## Critério de conclusão

A feature estará concluída quando o manifesto cobrir todas as tecnologias
obrigatórias, uma ingestão reproduzível produzir documentos, chunks, vetores e
corpus BM25 consistentes, reexecuções forem idempotentes, atualizações forem
reconciliáveis, comandos operacionais estiverem documentados, a suíte offline e
as integrações habilitadas passarem e a entrega receber aprovação explícita.

## Sugestão de commit

`feat(knowledge): build reproducible NVIDIA knowledge ingestion`
