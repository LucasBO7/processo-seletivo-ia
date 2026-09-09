# Especificação 017: API de análise

## Status

Implementada e validada tecnicamente em 8 de setembro de 2026.

## Contexto

A rota `/api/v1/search` já aciona o único `StateGraph` da aplicação e retorna os
artefatos produzidos pelos agentes. Esta entrega consolida essa rota como a API
do pipeline completo, explicita seus desfechos HTTP e garante que falhas internas
não exponham detalhes operacionais.

## Decisão de rota

`POST /api/v1/search` será evoluída e permanecerá como a única rota de análise.
Não será criada `/api/v1/analysis`: as duas teriam a mesma entrada, acionariam o
mesmo grafo e devolveriam os mesmos dados, criando contratos duplicados.
`/api/v1/query-plans` permanece disponível por possuir responsabilidade distinta
e já aprovada: planejar uma consulta sem executar o pipeline completo.

## Histórias e critérios de aceite

### US-01 — Executar a análise completa

- A API aceita uma consulta textual e chama uma vez o workflow criado no lifespan.
- A resposta preserva plano, startups, fontes, perfis, classificações, evidências,
  contexto NVIDIA, recomendações, briefings, avisos, erros e métricas permitidas.
- IDs, URLs e citações são serializados sem reescrita.

### US-02 — Distinguir desfechos de forma tipada

- Toda resposta de análise possui um `outcome` enumerado.
- São distinguíveis: sucesso, necessidade de esclarecimento, consulta inválida,
  ausência de resultados, indisponibilidade temporária e falha interna.
- Consulta inválida retorna 422; falha de dependência/modelo inválido retorna 502;
  indisponibilidade recuperável retorna 503; exceção inesperada retorna 500.
- Esclarecimento e ausência de resultados são resultados válidos com HTTP 200.

### US-03 — Proteger informações internas

- Exceções inesperadas geram mensagem pública estável e correlacionável.
- Prompts, respostas brutas, SQL, stack traces e credenciais não aparecem no corpo.
- Apenas métricas numéricas dos oito agentes são expostas.

### US-04 — Documentar e preservar infraestrutura HTTP

- O OpenAPI descreve entrada, saída, enum de desfecho e exemplos dos seis cenários.
- CORS e `X-Correlation-ID` continuam funcionando.
- O workflow e seus recursos continuam sendo criados uma vez por lifespan.
- Não existe segunda rota com a responsabilidade de análise completa.

### US-05 — Testar sem serviços reais

- Testes unitários cobrem classificação de desfecho e filtragem de métricas.
- Testes HTTP cobrem os contratos, sanitização, correlação e OpenAPI.
- Um teste integrado conecta a API ao `StateGraph` compilado com infraestrutura
  controlada e sem LLM, rede ou banco reais.

## Fora do escopo

- Nova interface ou exportação visual.
- Streaming, autenticação, memória conversacional ou intervenção humana.
- Novo grafo, scraping ou persistência do resultado da análise.
- Mudanças nas decisões internas dos agentes.

## Critério de conclusão

A funcionalidade estará concluída quando a rota única executar o workflow,
representar os seis desfechos sem vazar informações internas, estiver documentada
no OpenAPI e todos os testes e verificações de qualidade passarem.

## Sugestão de commit

`feat(api): expose typed full-pipeline analysis results`
