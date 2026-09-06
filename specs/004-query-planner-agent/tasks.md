# Tarefas 004: Query Planner Agent

Todas as tarefas permanecem pendentes enquanto a especificação estiver como
`Proposta`.

## Preparação e contratos

- [ ] **T-01 [US-01, US-02, RF-03, RF-05]** Criar os enums e modelos tipados de `QueryPlan`, filtros e estratégia, incluindo invariantes entre status, ambiguidades e perguntas.
- [ ] **T-02 [US-01, RF-04, RNF-01]** Implementar normalização estável, remoção de vazios, deduplicação e limites das listas estruturadas.
- [ ] **T-03 [US-04, RF-02, RNF-04]** Adicionar `QueryPlannerConfig`, seus limites validados e as variáveis não sensíveis ao `.env.example`.
- [ ] **T-04 [US-01, RF-09]** Adicionar `query_plan` tipado ao `AppState` sem duplicar o plano no campo legado `filters`.

## Prompt e agente

- [ ] **T-05 [US-05, RNF-03, RNF-05]** Criar o prompt versionado com schema, regras de não inferência, distinção de ambiguidade e delimitação segura da consulta.
- [ ] **T-06 [US-04, RF-02, RF-08]** Implementar a pré-validação determinística para consultas vazias, sem conteúdo semântico e acima do limite, sem chamar o modelo.
- [ ] **T-07 [US-01, US-02, RF-01, RF-03, RF-05, RF-10, RNF-02]** Implementar `QueryPlannerAgent` assíncrono com o `llm_fast` resolvido pela integração da especificação 003 e injetado como `ChatModel`, parsing estrito e atualização parcial do estado.
- [ ] **T-08 [US-03, RF-07, RF-12]** Implementar os resultados `ready`, `needs_clarification` e `invalid`, preservando filtros inequívocos e sinalizando bloqueio para o futuro Retriever.
- [ ] **T-09 [US-04, RF-06, RF-08, RF-11]** Implementar reparo limitado de saída malformada e conversão de falhas em `RecoverableError` sanitizado.
- [ ] **T-10 [US-04, US-05, RNF-03]** Adicionar logging por allowlist com status, duração e versão do prompt, sem consulta integral, prompt ou resposta bruta.

## Testes

- [ ] **T-11 [US-01, US-02, RNF-08]** Testar todos os campos mínimos, parâmetros ausentes, normalização, deduplicação, UTF-8 e os três modos de estratégia.
- [ ] **T-12 [US-03]** Testar consulta ampla válida, ambiguidades bloqueantes, perguntas de esclarecimento e preservação de filtros inequívocos.
- [ ] **T-13 [US-04, RNF-06]** Testar entradas inválidas sem chamada ao modelo, consulta alheia, JSON inválido, campos extras, enums inválidos, reparo e indisponibilidade do modelo.
- [ ] **T-14 [US-05, RNF-03, RNF-05, RNF-07]** Testar atualização parcial, compatibilidade com `GraphNode`, prompt injection, sanitização e ausência de rede, clientes ou segredos no estado e nos logs.
- [ ] **T-15 [US-05, RNF-09]** Atualizar testes arquiteturais quando necessário e executar a suíte completa com cobertura mínima de 80%.

## Documentação e verificação final

- [ ] **T-16 [US-01 a US-05]** Documentar no README o contrato do Query Planner, seus status, configurações e limites, sem anunciar Retriever ou rota funcional inexistente.
- [ ] **T-17 [US-05]** Executar Ruff format check, Ruff lint, mypy, import-linter e o comando agregado do backend.
- [ ] **T-18 [US-05]** Executar lint, testes e build do frontend existente para verificar ausência de regressões.
- [ ] **T-19 [US-01 a US-05]** Revisar todos os critérios de aceite, atualizar o registro de decisões e marcar a especificação como concluída somente após aprovação explícita da entrega.
