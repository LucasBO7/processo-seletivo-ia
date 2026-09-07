# Tarefas 012: NVIDIA Knowledge Base

A execução depende de aprovação explícita desta especificação e do plano.

## Contratos, configuração e manifesto

- [x] **T-01 [US-01, RF-01, RF-02]** Criar catálogo canônico das 16 tecnologias e manifesto versionado com as fontes do TAPI.
- [x] **T-02 [US-01, US-02, RF-02, RF-03]** Criar contratos estritos de fonte, conteúdo coletado, documento normalizado, revisão e falha.
- [x] **T-03 [US-02, US-04, US-07, RNF-02]** Adicionar configurações validadas de coleta, conteúdo, chunking, lotes, concorrência e versão.
- [x] **T-04 [US-02, RF-03, RNF-06]** Definir porta assíncrona de conteúdo e preservar a porta `EmbeddingModel` independente de SDK.

## Schema e persistência

- [x] **T-05 [US-05, US-06, RF-07, RF-10]** Criar migração reversível para `source_key`, tecnologia, revisão, pipeline version e data de ingestão, preservando `knowledge_documents.source_url` como coluna obrigatória.
- [x] **T-06 [US-05, US-06, RF-07, RF-11]** Evoluir entidades, mapeamentos e repositórios para upsert, chunks ativos e reconciliação.
- [x] **T-07 [US-06, RF-10]** Implementar identidade lógica, SHA-256, UUIDs determinísticos e detecção `unchanged`.

## Coleta, normalização e chunking

- [x] **T-08 [US-01, US-02, RF-02, RF-03]** Implementar carregamento do manifesto, HTTPS, allowlist e validação de redirecionamentos.
- [x] **T-09 [US-02, RF-03, RNF-02]** Implementar cliente HTTP com timeout, limite de bytes, user-agent e retries transitórios.
- [x] **T-10 [US-02, RF-04]** Implementar limpeza e normalização determinística de HTML, Markdown e texto.
- [x] **T-11 [US-03, RF-05, RNF-01, RNF-03]** Implementar chunking determinístico por seção/parágrafo com posição e sobreposição limitada.
- [x] **T-12 [US-02, US-03, RF-04, RF-05, RF-07]** Rejeitar conteúdo vazio/ruidoso e preservar nos chunks a mesma `source_url` oficial do documento.

## Embeddings e índices

- [x] **T-13 [US-04, RF-06]** Implementar lotes de embeddings com validação de quantidade, finitude, dimensão e fingerprint.
- [x] **T-14 [US-05, US-06, RF-07, RF-10, RF-11]** Implementar preparação da revisão e publicação transacional no PostgreSQL.
- [x] **T-15 [US-05, US-06, RF-08, RF-11]** Implementar upsert, remoção segura de stale points e reconciliação do Qdrant.
- [x] **T-16 [US-05, RF-09]** Construir corpus BM25 determinístico a partir dos chunks ativos e calcular seu fingerprint.
- [x] **T-17 [US-05, US-07, RF-07, RF-09, RF-12]** Implementar verificador de cobertura, hashes, URLs, metadados, dimensões, órfãos e consistência BM25/Qdrant/PostgreSQL.

## Serviço, CLI e operação

- [x] **T-18 [US-06, RF-10, RF-11, RF-13]** Orquestrar ingestão idempotente, atualização, recuperação parcial e relatório sanitizado.
- [x] **T-19 [US-07, RF-12]** Criar comandos de dry-run, ingestão seletiva e verificação somente leitura.
- [x] **T-20 [US-07, RNF-05, RNF-10]** Atualizar README, `.env.example` e documentação dos scripts e recuperação.
- [x] **T-21 [US-09, RNF-04, RNF-06]** Garantir por arquitetura que grafo, API pública, RAG, reranking e recomendações não sejam adicionados.

## Testes offline

- [x] **T-22 [US-01 a US-03, RNF-03, RNF-07]** Testar manifesto, allowlist, normalização, hashes, chunks, localizadores e IDs com fixtures mínimas.
- [x] **T-23 [US-04, RNF-07]** Testar embeddings com fake mínimo, lotes, ordem e vetores inválidos sem rede ou tokens.
- [x] **T-24 [US-05, US-06, RNF-07]** Testar persistência e Qdrant com fakes, unchanged, update, falha parcial, stale points e reconciliação.
- [x] **T-25 [US-05, US-07, RNF-07]** Testar corpus BM25, verificador, CLI, códigos de saída e relatórios.
- [x] **T-26 [US-08, RNF-07, RNF-08]** Criar guardas automáticas contra HTTP e embeddings reais na suíte padrão.

## Integração e qualidade

- [x] **T-27 [US-08, RNF-08]** Testar migração, ingestão e reingestão em PostgreSQL e Qdrant reais somente com `RUN_INTEGRATION_TESTS=1`.
- [x] **T-28 [US-08, RNF-08]** Isolar testes de fontes e embeddings reais sob marca `external` e habilitação explícita adicional.
- [x] **T-29 [US-01 a US-09, RNF-09]** Executar Ruff, mypy, import-linter, suíte offline e cobertura mínima de 80%.
- [x] **T-30 [US-01 a US-09, RNF-09]** Executar regressão de lint, testes e build do frontend.
- [ ] **T-31 [US-01 a US-09]** Revisar critérios e concluir após aprovação explícita da entrega.

## Sugestão de commit

`feat(knowledge): build reproducible NVIDIA knowledge ingestion`
