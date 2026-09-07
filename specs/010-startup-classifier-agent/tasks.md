# Tarefas 010: Startup Classifier Agent

A execução depende de aprovação explícita desta especificação e do plano.

## Contratos e critérios

- [x] **T-01 [US-01 a US-04, RF-01 a RF-03, RNF-01]** Criar contratos estritos de status, confiança, sinais, saída e classificação.
- [x] **T-02 [US-01, US-03, RF-02, RF-03]** Codificar invariantes das três categorias e do resultado incerto.
- [x] **T-03 [US-02, US-04, RF-05, RF-06]** Validar referências, associação, ordem e coerência entre categoria e sinais.
- [x] **T-04 [US-06, RF-04, RF-07]** Criar `StartupClassifierConfig`, defaults, ambiente e limites.

## Agente e prompt

- [x] **T-05 [US-01 a US-03, RF-02 a RF-04]** Criar prompt versionado com taxonomia e restrição às evidências recebidas.
- [x] **T-06 [US-02, US-06, RF-04]** Montar contexto isolado e limitado com perfil e excerpts da startup.
- [x] **T-07 [US-01 a US-03, RF-02, RF-03]** Implementar classificação e incerteza determinística para perfil sem fatos.
- [x] **T-08 [US-04, RF-06, RF-07]** Implementar parsing, validação e tentativa limitada de reparo.
- [x] **T-09 [US-04, US-08, RF-08, RF-09]** Preservar resultados parciais e emitir erros sanitizados sem alterar perfis.
- [x] **T-10 [US-06, RF-09, RNF-06]** Adicionar avisos, métricas e logs permitidos.
- [x] **T-11 [US-06, RF-12]** Criar factory e resolver `llm_heavy` pela política central.

## Grafo, composição e API

- [x] **T-12 [US-05, RF-10]** Implementar e testar `route_after_extractor`.
- [x] **T-13 [US-05, RF-10]** Registrar Classifier e arestas Extractor → Classifier/END → END.
- [x] **T-14 [US-06, RF-12, RNF-04]** Compor e reutilizar uma instância do Classifier no lifespan.
- [x] **T-15 [US-07, RF-11]** Expor classificações e códigos 502/503 em `/api/v1/search`.
- [x] **T-16 [US-07, US-08]** Atualizar OpenAPI, `.env.example`, README e evolução das specs anteriores.

## Testes e verificação

- [x] **T-17 [US-01 a US-04, RNF-05]** Testar contratos, categorias, incerteza, sinais e referências.
- [x] **T-18 [US-02 a US-06]** Testar agente com fakes, isolamento, reparo, limites, falhas, métricas e logs.
- [x] **T-19 [US-05]** Testar topologia, roteamento, ausência de perfis e estado final.
- [x] **T-20 [US-07]** Testar API, OpenAPI, sucesso, incerteza e erros HTTP.
- [x] **T-21 [US-01 a US-08, RNF-08]** Executar integração PostgreSQL real com Retriever, Extractor e Classifier falsos.
- [x] **T-22 [US-01 a US-08, RNF-08]** Executar qualidade, cobertura e regressão do frontend.
- [ ] **T-23 [US-01 a US-08]** Revisar critérios e concluir após aprovação explícita da entrega.

## Sugestão de commit

`feat(classifier): classify structured startup profiles from evidence`
