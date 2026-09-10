# Plano 018: interface web de análise

## Estratégia

Substituir a página institucional por uma aplicação de página única que mantém o
estado da consulta localmente. Um cliente baseado em `fetch` representa o contrato
da spec 017, aplica timeout e devolve também respostas de domínio não-2xx. A página
orquestra somente interação e apresentação; artefatos continuam sendo produzidos e
validados exclusivamente pelo backend.

## Estrutura

```text
src/
├── api/
│   ├── analysis-client.ts
│   └── analysis-types.ts
├── components/
│   ├── AnalysisState.tsx
│   ├── SearchForm.tsx
│   ├── StartupDetails.tsx
│   └── StartupList.tsx
├── pages/HomePage.tsx
└── styles/global.css
```

## Decisões

- Usar `VITE_API_BASE_URL` somente como endereço público; o default local é
  `http://127.0.0.1:8000`.
- Não estender a API: os filtros escolhidos compõem a consulta textual de forma
  explícita e o Query Planner permanece responsável pela interpretação.
- Mostrar a pipeline como uma operação única em andamento, pois a API não oferece
  streaming nem eventos de progresso.
- Resolver artefatos por `startup_id`, preferindo contratos validados quando existem.
- Renderizar conteúdo como texto React e Markdown em `pre`, nunca com HTML arbitrário.
- Exportar o `markdown` original em Blob, sem gerar uma segunda representação.

## Verificação

1. Testar cliente, composição dos filtros e todos os estados de domínio.
2. Testar seleção, isolamento por startup, URLs seguras e exportação Markdown.
3. Executar `npm run lint`, `npm run test` e `npm run build`.
4. Revisar o bundle por nomes de credenciais e atualizar a documentação operacional.

## Resultado da implementação

- A página institucional foi evoluída para a operação completa de análise.
- O cliente tipado trata timeout, rede, respostas de domínio e payload incompatível.
- A navegação por startup isola perfil, maturidade, evidências, gaps, fontes NVIDIA,
  recomendações e briefing pelo identificador retornado pela API.
- Conteúdo externo permanece como texto; somente URLs permitidas viram links.
- O Markdown original pode ser inspecionado e baixado sem transformação.
- Ausências de recomendação e briefing explicam a etapa bloqueante usando apenas
  diagnósticos sanitizados da API.
- 14 testes de frontend, lint e build de produção passaram.

## Sugestão de commit

`feat(frontend): add full startup analysis interface`
