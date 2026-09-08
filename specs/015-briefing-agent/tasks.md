# Tarefas 015: Briefing Agent

## Contratos e preparação

- [x] **T-01 [US-01 a US-05, RF-01 a RF-07]** Criar contratos estritos crus e finais.
- [x] **T-02 [US-09, RF-09]** Adicionar limites validados e códigos operacionais.
- [x] **T-03 [US-01, US-07, RF-01, RF-02]** Agrupar entradas exclusivamente por startup.
- [x] **T-04 [US-01, US-03, RF-02, RF-03]** Derivar seções factuais e catálogos de citações.
- [x] **T-05 [US-07, US-09, RF-02, RF-09]** Aplicar limites e registrar dados parciais.

## Geração, validação e Markdown

- [x] **T-06 [US-02, US-06, RF-04]** Criar prompt compacto e versionado por startup.
- [x] **T-07 [US-09, RF-04]** Resolver `NodeName.BRIEFING` pelo `ModelRegistry`.
- [x] **T-08 [US-02, US-03, RF-05]** Validar natureza, texto e IDs de citações.
- [x] **T-09 [US-04, RF-06]** Exigir suporte duplo e chunk Inception oficial.
- [x] **T-10 [US-05, RF-07]** Renderizar Markdown determinístico e limitado.
- [x] **T-11 [US-06, US-07, RF-08]** Implementar reparo, atomicidade e erros sanitizados.
- [x] **T-12 [US-09, RF-09]** Implementar métricas e logs sem conteúdo.

## Integração

- [x] **T-13 [US-08, RF-10]** Evoluir `AppState` e composição de recursos.
- [x] **T-14 [US-08, RF-10]** Adicionar `route_after_recommendation` e arestas do grafo.
- [x] **T-15 [US-08, RF-10]** Expor `briefings` e erros em `/api/v1/search` e OpenAPI.
- [x] **T-16 [US-11, RF-11]** Confirmar ausência de exportação, persistência e recuperação.

## Testes e qualidade

- [x] **T-17 [US-01 a US-07]** Testar sucesso completo, parcialidade e seções derivadas.
- [x] **T-18 [US-03, US-04, US-06]** Testar citações, Inception, reparo e falhas.
- [x] **T-19 [US-05]** Testar Markdown, fontes, ordem, escaping e limite.
- [x] **T-20 [US-08]** Testar grafo, patch, API, OpenAPI e status HTTP.
- [x] **T-21 [US-09, US-10]** Testar limites, métricas, isolamento e guardas offline.
- [x] **T-22 [US-08, US-09]** Atualizar README e `.env.example`.
- [x] **T-23 [US-10]** Executar Ruff, mypy, import-linter e cobertura mínima de 80%.
- [x] **T-24 [US-10]** Executar integração e regressão do frontend.
- [x] **T-25 [US-01 a US-11]** Revisar todos os critérios de aceite.

## Sugestão de commit

`feat(briefing): generate cited executive startup briefings`
