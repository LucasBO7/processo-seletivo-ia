# Tarefas 017: API de análise

## Contrato e comportamento

- [x] **T-01 [US-01, US-02]** Adicionar o desfecho tipado ao contrato existente.
- [x] **T-02 [US-01]** Preservar todos os artefatos rastreáveis do `AppState`.
- [x] **T-03 [US-02]** Mapear os seis desfechos e seus status HTTP.
- [x] **T-04 [US-03]** Filtrar métricas e sanitizar exceções inesperadas.
- [x] **T-05 [US-04]** Manter uma única rota de análise e o reuso do lifespan.
- [x] **T-06 [US-04]** Publicar exemplos de requisição e resposta no OpenAPI.

## Testes

- [x] **T-07 [US-02, US-03]** Testar classificação e métricas permitidas.
- [x] **T-08 [US-01 a US-04]** Testar contratos HTTP, correlação e sanitização.
- [x] **T-09 [US-04]** Testar OpenAPI e ausência de endpoint duplicado.
- [x] **T-10 [US-05]** Integrar a API com o `StateGraph` controlado.

## Qualidade

- [x] **T-11 [US-01 a US-05]** Atualizar README e revisar o escopo.
- [x] **T-12 [US-05]** Executar backend, integrações e verificações estáticas.
- [x] **T-13 [US-05]** Executar regressão do frontend.
- [x] **T-14 [US-01 a US-05]** Revisar todos os critérios de aceite.
- [x] **T-15 [US-02, US-03]** Corrigir status de esclarecimento sem suporte observado no modelo real.
- [x] **T-16 [US-01]** Compatibilizar escopo nacional Brasil com localizações persistidas por cidade.
- [x] **T-17 [US-01, US-03]** Evitar truncamento e normalizar a estrutura redundante do Extractor.
- [x] **T-18 [US-01, US-03, US-05]** Corrigir ingestão NVIDIA no Windows, deduplicar chunks reais, isolar dados de integração e preservar lotes válidos do Validator em falhas recuperáveis.

## Sugestão de commit

`feat(api): expose typed full-pipeline analysis results`
