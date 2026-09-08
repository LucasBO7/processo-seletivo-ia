# Tarefas 016: orquestração completa do pipeline

## Grafo e pré-condições

- [x] **T-01 [US-01, RF-01, RF-02]** Declarar e testar a ordem canônica dos oito nós.
- [x] **T-02 [US-02, US-03, RF-03, RF-04]** Endurecer os sete roteamentos condicionais.
- [x] **T-03 [US-03, RF-07]** Preservar continuidade parcial baseada em saídas válidas.
- [x] **T-04 [US-04, RF-05]** Verificar preservação completa do `AppState` e rastreabilidade.
- [x] **T-05 [US-05, RF-06]** Confirmar composição e reuso único no lifespan.

## Testes

- [x] **T-06 [US-01, US-02]** Testar topologia, arestas e ordem.
- [x] **T-07 [US-02, US-03]** Testar todas as decisões de continuar e interromper.
- [x] **T-08 [US-03]** Testar falhas recuperáveis com e sem saída parcial.
- [x] **T-09 [US-04, US-05]** Testar isolamento entre execuções e preservação de estado.
- [x] **T-10 [US-06, RF-08]** Integrar os oito agentes reais com provedores falsos.
- [x] **T-11 [US-06]** Validar IDs, URLs, citações e métricas no resultado integrado.

## Qualidade

- [x] **T-12 [US-01 a US-06]** Atualizar README e revisar ausência de itens fora do escopo.
- [x] **T-13 [US-06]** Executar Ruff, mypy, import-linter e cobertura mínima de 80%.
- [x] **T-14 [US-06]** Executar integrações existentes e regressão do frontend.
- [x] **T-15 [US-01 a US-06]** Revisar todos os critérios de aceite.

## Sugestão de commit

`feat(graph): validate and test full pipeline orchestration`
