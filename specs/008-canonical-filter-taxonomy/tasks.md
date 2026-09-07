# Tarefas 008: taxonomia canônica de filtros

A implementação foi autorizada explicitamente em 7 de setembro de 2026. As
tarefas permanecem pendentes até sua execução e verificação.

## Taxonomia e contratos

- [x] **T-01 [US-01, US-03, RF-01, RNF-01]** Criar Enums canônicos de setor, estágio e porte.
- [x] **T-02 [US-02, US-04, RF-02, RNF-02]** Centralizar descrições, aliases e rótulos persistidos reconhecidos.
- [x] **T-03 [US-01, US-02, RF-04, RNF-04, RNF-05]** Implementar normalização e expansão determinísticas.
- [x] **T-04 [US-01, US-03, RF-01]** Atualizar e validar o contrato `StartupSearchFilters`.
- [x] **T-05 [US-01, US-05, RF-05, RF-11, RF-12]** Criar contratos tipados de filtros não resolvidos e sugestões.

## Query Planner

- [x] **T-06 [US-01, RF-03]** Atualizar e versionar o prompt com a taxonomia permitida.
- [x] **T-07 [US-01, US-05, RF-04, RF-05]** Normalizar aliases e separar consulta ampla de filtro não resolvido.
- [x] **T-08 [US-05, RF-11, RF-12, RNF-09]** Gerar e validar até três sugestões na chamada existente do Planner.
- [x] **T-09 [US-01, US-05, RF-10]** Preservar filtros canônicos, pendências, sugestões e avisos nas respostas HTTP.

## Retriever

- [x] **T-10 [US-02, US-04, RF-06, RF-07]** Traduzir categorias canônicas para rótulos persistidos.
- [x] **T-11 [US-02, RF-07, RF-08]** Aplicar OR na expansão e preservar AND entre campos.
- [x] **T-12 [US-03, RF-06]** Preservar intervalos de porte e mapeamentos canônicos de estágio.
- [x] **T-13 [US-04, RF-09, RNF-07]** Manter registros não mapeados em buscas sem filtro e preservar resultados rastreáveis.

## API, documentação e compatibilidade

- [x] **T-14 [US-05, RF-10 a RF-12]** Atualizar OpenAPI e exemplos de Postman com sugestões, sem criar novas rotas.
- [x] **T-15 [US-04, US-05]** Registrar a evolução de comportamento nas specs 004 e 006 e atualizar READMEs.

## Testes e verificação

- [x] **T-16 [US-01 a US-03, RNF-04 a RNF-06]** Criar testes unitários de Enums, aliases, expansão e rejeição.
- [x] **T-17 [US-01, US-05]** Testar Query Planner com consulta ampla, filtro desconhecido, sugestões, reparo e erros sanitizados.
- [x] **T-18 [US-02 a US-04, RNF-03, RNF-07]** Testar Retriever, rótulos compostos e busca sem filtros.
- [x] **T-19 [US-02, US-04]** Executar integração PostgreSQL real para a categoria financeira.
- [x] **T-20 [US-05, RNF-08]** Executar qualidade, cobertura e regressão do frontend.
- [ ] **T-21 [US-01 a US-05]** Revisar critérios e concluir somente após aprovação explícita da entrega.

## Sugestão de commit

`feat(search): add canonical filter taxonomy and aliases`
