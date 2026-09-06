# Tarefas 003: integração Groq para agentes

A implementação foi autorizada em 6 de setembro de 2026.

## Dependência e configuração

- [x] **T-01 [US-01, RF-01]** Adicionar `langchain-groq` ao `pyproject.toml` com faixa compatível e atualizar `uv.lock`.
- [x] **T-02 [US-01, RF-02, RF-03, RF-09]** Criar configurações imutáveis para `groq`, `llm_fast` e `llm_heavy`, com os modelos, temperaturas, timeouts e retries definidos na spec.
- [x] **T-03 [US-01]** Atualizar `.env.example` e a documentação operacional sem incluir credencial real.

## Adaptador e composição

- [x] **T-04 [US-02, RF-04, RNF-01, RNF-02]** Implementar o adaptador assíncrono entre `ChatGroq` e o protocolo interno `ChatModel`.
- [x] **T-05 [US-02, US-04, RF-08, RNF-03]** Implementar erros internos estáveis, sanitização e logging por allowlist para falhas da Groq.
- [x] **T-06 [US-02, RF-05, RNF-06]** Construir uma única instância de `llm_fast` e `llm_heavy` no composition root e adicioná-las aos recursos da aplicação.
- [x] **T-07 [US-03, RF-06, RF-07]** Criar a política exaustiva `NodeName` para perfil rápido, pesado ou nenhum, rejeitando LLM para o Retriever.
- [x] **T-08 [US-03, RF-10]** Disponibilizar uma factory tipada para que as specs dos agentes injetem o `ChatModel` alocado em seus construtores.

## Testes

- [x] **T-09 [US-01]** Testar defaults, overrides, limites, ausência de credencial e redação de segredos.
- [x] **T-10 [US-02, US-04, RNF-02 a RNF-04]** Testar mensagens, resposta textual, execução assíncrona e falhas sanitizadas com cliente fake e sem rede.
- [x] **T-11 [US-02, RF-05, RNF-06]** Testar construção única dos recursos e ausência de chamadas na inicialização.
- [x] **T-12 [US-03, RF-06, RF-07]** Testar de forma parametrizada todos os nós, os dois perfis e a rejeição do Retriever.
- [x] **T-13 [US-02, RNF-01, RNF-05]** Atualizar testes arquiteturais para impedir imports de `langchain_groq` no domínio, aplicação, estado e agentes.
- [x] **T-14 [US-01 a US-04, RNF-05]** Executar a suíte completa com cobertura mínima de 80%, sem chamada real à Groq.

## Documentação e verificação final

- [x] **T-15 [US-01, US-03]** Documentar configuração, perfis, matriz de alocação, limitação atual dos modelos e uso pelas futuras specs de agentes.
- [x] **T-16 [US-01 a US-04]** Executar Ruff format check, Ruff lint, mypy, import-linter e o comando agregado do backend.
- [x] **T-17 [US-01 a US-04]** Executar lint, testes e build do frontend para verificar ausência de regressões.
- [ ] **T-18 [US-01 a US-04]** Revisar os critérios de aceite e marcar a spec como concluída somente após aprovação explícita da entrega.

## Sugestão de commit

`feat(groq): add reusable fast and heavy LLM profiles for graph agents`
