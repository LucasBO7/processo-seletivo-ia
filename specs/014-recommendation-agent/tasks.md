# Tarefas 014: Recommendation Agent

A execução depende de aprovação explícita desta especificação e do plano.

## Contratos e configuração

- [x] **T-01 [US-02 a US-05, RF-04 a RF-08]** Criar enums e contratos estritos para necessidades, candidatos, fatores, evidências e recomendações finais.
- [x] **T-02 [US-07, RF-10, RNF-01]** Separar o contrato cru do modelo dos campos derivados pelo agente.
- [x] **T-03 [US-09, RNF-02]** Adicionar configurações validadas de recomendações, necessidades, fontes, chunks, caracteres, textos e reparo.
- [x] **T-04 [US-06, US-07, RF-10, RNF-06]** Definir avisos, erros recuperáveis e mensagens sanitizadas.

## Elegibilidade e contexto

- [x] **T-05 [US-01, RF-01]** Associar perfis, classificações, validações, gaps e contextos exclusivamente por `startup_id`.
- [x] **T-06 [US-01, RF-02]** Enumerar `technical_needs` aprovadas com chaves estáveis e fontes preservadas.
- [x] **T-07 [US-01, RF-02]** Resolver `technical_gaps` somente por evidências aprovadas de uma única startup.
- [x] **T-08 [US-01, US-03, RF-03, RF-06]** Construir allowlists separadas de necessidades, evidências da startup e chunks NVIDIA.
- [x] **T-09 [US-01, US-02, RF-01, RF-03]** Detectar ausência de necessidade, contexto NVIDIA e evidência de negócio antes de chamar o modelo.
- [x] **T-10 [US-09, RF-03, RNF-02]** Aplicar limites e truncamento determinístico preservando a ordem de relevância.

## Prompt e geração

- [x] **T-11 [US-07, US-09, RF-03, RF-04]** Criar prompt compacto, delimitado e versionado para uma startup por chamada.
- [x] **T-12 [US-07, US-09, RF-04]** Resolver `NodeName.RECOMMENDATION` pelo `ModelRegistry` e usar `llm_heavy`.
- [x] **T-13 [US-02, US-06, RF-04, RF-05]** Permitir lote de candidatos ou lista vazia válida sem forçar recomendação.

## Validação e derivação

- [x] **T-14 [US-02, US-03, RF-05, RF-06]** Validar necessidade, tecnologia, startup e IDs contra as allowlists do estado.
- [x] **T-15 [US-03, RF-06]** Resolver referências completas da startup e NVIDIA sem aceitar UUIDs, URLs ou scores criados pelo modelo.
- [x] **T-16 [US-02, US-03, RF-05, RF-06]** Exigir vínculo técnico, evidência de negócio e chunk da mesma tecnologia recomendada.
- [x] **T-17 [US-04, RF-07, RNF-04]** Implementar fatores, força de evidência, score e nível determinístico de prioridade.
- [x] **T-18 [US-05, RF-08, RNF-04]** Implementar fatores, score e nível determinístico de complexidade.
- [x] **T-19 [US-06, RF-09]** Rejeitar restrições incompatíveis e duplicatas por startup/tecnologia.
- [x] **T-20 [US-04 a US-06, RF-07 a RF-09]** Validar divergência entre fatores propostos e valores recalculados.
- [x] **T-21 [US-04, US-05, RNF-04]** Implementar ordenação final e desempates estáveis.

## Reparo, agente, grafo e API

- [x] **T-22 [US-06, US-07, RF-10]** Implementar parse, validação semântica e no máximo uma tentativa configurável de reparo.
- [x] **T-23 [US-06, US-07, RF-10, RF-11]** Preservar lotes anteriores e tratar vazio válido, invalidade persistente e indisponibilidade.
- [x] **T-24 [US-09, RF-11, RNF-06]** Implementar métricas e logs estruturados sem conteúdo sensível.
- [x] **T-25 [US-08, RF-11, RF-12]** Implementar `RecommendationAgent`, composição e patch parcial do `AppState`.
- [x] **T-26 [US-08, RF-12]** Adicionar `route_after_nvidia_rag`, nó e arestas `nvidia_rag → recommendation → END`.
- [x] **T-27 [US-08, RF-12, RNF-10]** Expor recomendações e erros em `/api/v1/search` e OpenAPI de forma aditiva.
- [x] **T-28 [US-11, RF-13]** Garantir por arquitetura que não haja briefing, persistência ou nova recuperação.

## Testes offline

- [x] **T-29 [US-04, RF-07, RNF-04]** Testar todas as combinações e fronteiras da tabela de prioridade.
- [x] **T-30 [US-05, RF-08, RNF-04]** Testar todas as combinações e fronteiras da tabela de complexidade.
- [x] **T-31 [US-01, RF-01 a RF-03, RNF-05]** Testar elegibilidade, associação, gaps sem fonte, classificação ausente e isolamento entre startups.
- [x] **T-32 [US-02, US-03, RF-05, RF-06]** Testar necessidade, evidência dupla, URLs, UUIDs e correspondência da tecnologia.
- [x] **T-33 [US-06, RF-09 a RF-11]** Testar duplicatas, incompatibilidades, lote vazio, reparo, falha e sucesso parcial.
- [x] **T-34 [US-09, RNF-02, RNF-06]** Testar limites, truncamento, métricas e sanitização.
- [x] **T-35 [US-08, RF-12]** Testar roteamento LangGraph, estado parcial, API, HTTP e OpenAPI.
- [x] **T-36 [US-10, RNF-07]** Cobrir cenários TAPI com fakes e JSON mínimo, sem rede ou tokens.
- [x] **T-37 [US-10, RNF-07]** Reforçar guardas contra clientes reais e isolar qualquer teste externo por marca e opt-in.

## Documentação e qualidade

- [x] **T-38 [US-08, US-09]** Atualizar README e `.env.example` com contrato, configuração e comportamentos vazios/de erro.
- [x] **T-39 [US-01 a US-11, RNF-09]** Executar Ruff, mypy, import-linter, suíte offline e cobertura mínima de 80%.
- [x] **T-40 [US-08, US-10, RNF-09]** Executar regressão de lint, testes e build do frontend.
- [ ] **T-41 [US-01 a US-11]** Revisar critérios e concluir após aprovação explícita da entrega.

## Sugestão de commit

`feat(recommendation): generate grounded NVIDIA recommendations`
