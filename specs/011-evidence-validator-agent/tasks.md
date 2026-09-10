# Tarefas 011: Evidence Validator Agent

A execução depende de aprovação explícita desta especificação e do plano.

## Contratos e enumeração

- [x] **T-01 [US-01 a US-03, RF-01 a RF-05, RNF-01]** Criar contratos estritos de status, veredito, avaliações e perfis validados.
- [x] **T-02 [US-01, RF-01]** Enumerar fatos com chaves determinísticas e ordem estável.
- [x] **T-03 [US-03, US-07, RF-04, RF-05]** Validar allowlist, associação, URLs, cobertura exata e coerência de status.
- [x] **T-04 [US-08, RF-09, RNF-02]** Criar `EvidenceValidatorConfig`, defaults, ambiente e limites.

## Agente e prompt

- [x] **T-05 [US-01 a US-03, RF-02 a RF-04]** Criar prompt versionado com regras de suporte documental.
- [x] **T-06 [US-03, US-08, RF-04]** Construir contexto isolado e limitado com itens, classificação e excerpts.
- [x] **T-07 [US-01, US-02, RF-02, RF-03]** Implementar avaliação de fatos e classificação.
- [x] **T-08 [US-04 a US-06, RF-06 a RF-08]** Compor perfis validados e coleções separadas sem mutar originais.
- [x] **T-09 [US-07, RF-05, RF-09]** Implementar parsing e tentativa limitada de reparo.
- [x] **T-10 [US-07, RF-10]** Preservar resultados parciais e emitir erros sanitizados.
- [x] **T-11 [US-08, RF-10, RNF-06]** Adicionar avisos, métricas e logs permitidos.
- [x] **T-12 [US-08, RF-13]** Criar factory e resolver `llm_fast` pela política central.

## Grafo, composição e API

- [x] **T-13 [US-08, RF-11]** Implementar e testar `route_after_classifier`.
- [x] **T-14 [US-06, US-08, RF-11]** Registrar Validator e arestas Classifier → Validator/END → END.
- [x] **T-15 [US-08, RF-13, RNF-04]** Compor e reutilizar uma instância do Validator no lifespan.
- [x] **T-16 [US-09, RF-12]** Expor resultados e códigos 502/503 em `/api/v1/search`.
- [x] **T-17 [US-09, US-10]** Atualizar OpenAPI, `.env.example`, README e evolução das specs anteriores.

## Testes e verificação

- [x] **T-18 [US-01 a US-07, RNF-05]** Testar contratos, enumeração, status, fontes e composição filtrada.
- [x] **T-19 [US-03, US-06 a US-08]** Testar agente com fakes, lacunas, reparo, falhas, limites, métricas e logs.
- [x] **T-20 [US-06, US-08]** Testar topologia, roteamento, ausência de entrada e estado final.
- [x] **T-21 [US-09]** Testar API, OpenAPI, sucesso, ausência de aprovados e erros HTTP.
- [x] **T-22 [US-01 a US-10, RNF-08]** Executar integração PostgreSQL real com todos os agentes falsos.
- [x] **T-23 [US-01 a US-10, RNF-08]** Executar qualidade, cobertura e regressão do frontend.
- [x] **T-23A [US-03, US-07, RNF-02]** Avaliar itens em lotes limitados, preservando cobertura exata e resultados parciais quando um lote persistir inválido após reparo.
- [x] **T-23B [US-03, US-07, RF-10A]** Preservar fatos com suporte literal nas fontes citadas quando o provedor estiver indisponível, mantendo os demais itens insuficientes e o erro sanitizado.
- [ ] **T-24 [US-01 a US-10]** Revisar critérios e concluir após aprovação explícita da entrega.

## Sugestão de commit

`feat(validator): validate documentary support for startup claims`
