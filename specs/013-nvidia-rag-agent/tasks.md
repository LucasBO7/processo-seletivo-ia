# Tarefas 013: NVIDIA RAG Agent

A execução depende de aprovação explícita desta especificação e do plano.

## Contratos e configuração

- [x] **T-01 [US-01, US-05, RF-01, RF-02, RF-07]** Criar contratos estritos de consulta, scores, chunk, suficiência, lacuna e contexto por startup.
- [x] **T-02 [US-02, US-04, RF-03, RF-06, RNF-06]** Definir portas de leitura canônica, busca vetorial e lexical e adaptar `EmbeddingModel` e `Reranker` existentes.
- [x] **T-03 [US-03, US-06, RNF-03]** Adicionar e validar configurações de top-k, weighted RRF, reranking, limiares, tentativas, expansão e limites de consulta.
- [x] **T-04 [US-07, RF-10, RNF-05]** Definir falhas internas, avisos e mensagens sanitizadas.

## Consulta e recuperação

- [x] **T-05 [US-01, RF-01]** Implementar seleção de perfis utilizáveis sem fatos rejeitados, conflitantes ou insuficientes.
- [x] **T-06 [US-01, RF-02]** Implementar query builder determinístico com precedência, deduplicação, limites e proveniência.
- [x] **T-07 [US-02, RF-03]** Implementar busca vetorial por embedding e Qdrant, preservando UUID, score bruto e rank.
- [x] **T-08 [US-02, RF-03]** Implementar construção/carga e busca BM25 sobre chunks ativos, preservando UUID, score bruto e rank.
- [x] **T-09 [US-02, US-05, RF-04, RF-07]** Carregar candidatos canônicos do PostgreSQL e validar documento, chunk, metadados e `knowledge_documents.source_url`.

## Fusão, reranking e suficiência

- [x] **T-10 [US-03, RF-05]** Implementar ordenação de canal, componente normalizado e weighted RRF com pesos efetivos auditáveis.
- [x] **T-11 [US-03, US-06, RF-05]** Implementar deduplicação, limites, desempates e união de ocorrências entre tentativas.
- [x] **T-12 [US-04, RF-06]** Integrar reranker, validar saída, preservar scores e ordenar resultados finais.
- [x] **T-13 [US-04, US-07, RF-06, RF-10]** Implementar fallback híbrido quando o reranker falhar ou responder de forma inválida.
- [x] **T-14 [US-06, RF-08]** Implementar avaliação determinística de suficiência com razões objetivas e limiar por modo.
- [x] **T-15 [US-06, RF-09]** Implementar expansão de top-k, reformulações determinísticas, limite de tentativas e lacuna final explícita.

## Agente, grafo e API

- [x] **T-16 [US-07, RF-10]** Orquestrar os canais com degradação independente, base vazia, irrelevância e indisponibilidade total.
- [x] **T-17 [US-07, US-08, RF-11]** Implementar o `NvidiaRagAgent` com processamento por startup, sucesso parcial, métricas e patch parcial do estado.
- [x] **T-18 [US-08, RF-11]** Registrar adaptadores no composition root e adicionar o nó ao workflow.
- [x] **T-19 [US-08, RF-11]** Rotear Evidence Validator para NVIDIA RAG somente com perfil validado utilizável e encerrar em `END` depois do nó.
- [x] **T-20 [US-08, RF-11, RNF-09]** Estender `AppState`, `empty_state`, `/api/v1/search` e mapeamento HTTP de forma aditiva.
- [x] **T-21 [US-10, RF-12]** Garantir por arquitetura que o nó não escreve no corpus, não altera evidências e não produz recomendações.

## Testes offline

- [x] **T-22 [US-01, RNF-01, RNF-07]** Testar perfil utilizável, query builder, precedência, limites, deduplicação e proveniência com fixtures mínimas.
- [x] **T-23 [US-02, US-03, RNF-01, RNF-07]** Testar canais, fórmula weighted RRF, pesos degradados, empates, IDs inválidos e limites.
- [x] **T-24 [US-04, RNF-07]** Testar reranking, scores, IDs estranhos, duplicatas, valores inválidos e fallback com fake.
- [x] **T-25 [US-05, RNF-04, RNF-07]** Testar conteúdo, localizadores e URL canônicos vindos do PostgreSQL.
- [x] **T-26 [US-06, RNF-03, RNF-07]** Testar suficiência, irrelevância, expansão, reformulações, parada antecipada e esgotamento.
- [x] **T-27 [US-07, RNF-05, RNF-07]** Testar matriz de falhas, base vazia, resultados parciais, sanitização e HTTP 200/503.
- [x] **T-28 [US-08, RNF-07]** Testar estado parcial, rotas LangGraph, ausência de I/O sem perfil e contrato da API.
- [x] **T-29 [US-09, RNF-07]** Reforçar guardas para impedir rede, LLM, embedding e reranker reais na suíte padrão.

## Integração, documentação e qualidade

- [x] **T-30 [US-09, RNF-08]** Criar integração PostgreSQL/Qdrant opt-in com embedding e reranker fakes.
- [x] **T-31 [US-09, RNF-07]** Isolar qualquer teste real de embedding/reranker sob marca `external` e habilitação explícita adicional.
- [x] **T-32 [US-07, US-08]** Atualizar README e `.env.example` com configuração, limites e modos degradados.
- [x] **T-33 [US-01 a US-10, RNF-08]** Executar Ruff, mypy, import-linter, suíte offline e cobertura mínima de 80%.
- [x] **T-34 [US-08, US-09, RNF-08]** Executar regressão de lint, testes e build do frontend.
- [ ] **T-35 [US-01 a US-10]** Revisar critérios e concluir após aprovação explícita da entrega.

## Sugestão de commit

`feat(rag): add hybrid NVIDIA knowledge retrieval agent`
