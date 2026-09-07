# Tarefas 008: taxonomia canônica de filtros

Todas as tarefas permanecem pendentes enquanto a especificação estiver como
`Proposta`.

## Taxonomia e contratos

- [ ] **T-01 [US-01, US-03, RF-01, RNF-01]** Criar Enums canônicos de setor, estágio e porte.
- [ ] **T-02 [US-02, US-04, RF-02, RNF-02]** Centralizar descrições, aliases e rótulos persistidos reconhecidos.
- [ ] **T-03 [US-01, US-02, RF-04, RNF-04, RNF-05]** Implementar normalização e expansão determinísticas.
- [ ] **T-04 [US-01, US-03, RF-05]** Atualizar e validar o contrato `StartupSearchFilters`.

## Query Planner

- [ ] **T-05 [US-01, RF-03]** Atualizar e versionar o prompt com a taxonomia permitida.
- [ ] **T-06 [US-01, US-05, RF-04, RF-05]** Normalizar aliases antes da validação final e preservar reparo/erro.
- [ ] **T-07 [US-01, US-05, RF-10]** Preservar filtros canônicos e avisos no estado e nas respostas HTTP.

## Retriever

- [ ] **T-08 [US-02, US-04, RF-06, RF-07]** Traduzir categorias canônicas para rótulos persistidos.
- [ ] **T-09 [US-02, RF-07, RF-08]** Aplicar OR na expansão e preservar AND entre campos.
- [ ] **T-10 [US-03, RF-06]** Preservar intervalos de porte e mapeamentos canônicos de estágio.
- [ ] **T-11 [US-04, RF-09, RNF-07]** Manter registros não mapeados em buscas sem filtro e preservar resultados rastreáveis.

## API, documentação e compatibilidade

- [ ] **T-12 [US-05, RF-10]** Atualizar OpenAPI e exemplos de Postman sem criar novas rotas.
- [ ] **T-13 [US-04, US-05]** Registrar a evolução de comportamento nas specs 004 e 006 e atualizar READMEs.

## Testes e verificação

- [ ] **T-14 [US-01 a US-03, RNF-04 a RNF-06]** Criar testes unitários de Enums, aliases, expansão e rejeição.
- [ ] **T-15 [US-01, US-05]** Testar Query Planner com modelo falso, reparo e erros sanitizados.
- [ ] **T-16 [US-02 a US-04, RNF-03, RNF-07]** Testar Retriever, rótulos compostos e busca sem filtros.
- [ ] **T-17 [US-02, US-04]** Executar integração PostgreSQL real para a categoria financeira.
- [ ] **T-18 [US-05, RNF-08]** Executar qualidade, cobertura e regressão do frontend.
- [ ] **T-19 [US-01 a US-05]** Revisar critérios e concluir somente após aprovação explícita da entrega.

## Sugestão de commit

`feat(search): add canonical filter taxonomy and aliases`
