# Tarefas 009: Extractor Agent

A implementação foi autorizada explicitamente em 7 de setembro de 2026. As
tarefas permanecem pendentes até sua execução e verificação.

## Contratos e configuração

- [x] **T-01 [US-01 a US-03, RF-01, RNF-01]** Criar contratos estritos de perfil, fato, campo desconhecido e referência.
- [x] **T-02 [US-02, RF-02, RNF-07]** Adicionar `startup_id` a `SourceReference` e atualizar produtores e consumidores.
- [x] **T-03 [US-06, RF-04, RF-07, RNF-02]** Criar `ExtractorConfig`, defaults, variáveis e validações.
- [x] **T-04 [US-01 a US-03, RF-06]** Implementar validação cruzada entre fatos, fontes permitidas e campos desconhecidos.

## Agente e prompt

- [x] **T-05 [US-01, US-03, RF-05, RNF-03]** Criar e versionar o prompt de extração sem inferências.
- [x] **T-06 [US-01, US-04, RF-03, RF-04, RF-05a]** Agrupar candidatos e fontes e construir contexto limitado por startup, usando `excerpt` como conteúdo analisável.
- [x] **T-07 [US-01, US-02, RF-05, RF-06]** Implementar extração, parsing e composição segura de identidade.
- [x] **T-08 [US-05, RF-07]** Implementar tentativa limitada de reparo com allowlist de fontes.
- [x] **T-09 [US-04, US-05, RF-08]** Tratar fontes insuficientes, falhas parciais e erros sanitizados.
- [x] **T-10 [US-06, RF-09, RNF-06]** Adicionar métricas, avisos e logs permitidos.
- [x] **T-11 [US-06, RF-12]** Criar factory e resolver `llm_fast` pela política central.

## Grafo, composição e API

- [x] **T-12 [US-04, RF-10]** Implementar e testar `route_after_retriever`.
- [x] **T-13 [US-04, US-07, RF-10]** Registrar Extractor e arestas Retriever → Extractor/END → END.
- [x] **T-14 [US-06, RF-12, RNF-04]** Compor e reutilizar uma instância do Extractor no lifespan.
- [x] **T-15 [US-07, RF-11]** Expor `structured_profiles` e códigos 502/503 em `/api/v1/search`.
- [x] **T-16 [US-07]** Atualizar OpenAPI, `.env.example`, README e evolução das specs anteriores.

## Testes e verificação

- [x] **T-17 [US-01 a US-03, RNF-05]** Testar contratos, campos ausentes, deduplicação e referências.
- [x] **T-18 [US-01, US-05, US-06]** Testar agente com fakes, reparo, limites, métricas, isolamento e sanitização.
- [x] **T-19 [US-04, US-07]** Testar topologia, roteamento, busca vazia, fontes ausentes e estado final.
- [x] **T-20 [US-07]** Testar API, OpenAPI, respostas de sucesso e erros do Extractor.
- [x] **T-21 [US-01, US-02, US-07, RNF-08]** Executar integração PostgreSQL real com Retriever e modelo falso.
- [x] **T-22 [US-01 a US-07, RNF-08]** Executar qualidade, cobertura e regressão do frontend.
- [x] **T-22A [US-01, US-02]** Tornar explícita no prompt a extração exaustiva de todos os campos e de necessidades documentadas como requisitos, gargalos, limitações ou metas.
- [x] **T-23 [US-01 a US-07]** Revisar critérios e concluir somente após aprovação explícita da entrega.

## Sugestão de commit

`feat(extractor): structure startup profiles from retrieved sources`
