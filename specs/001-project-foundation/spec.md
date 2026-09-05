# Especificação 001: fundação do projeto

## Status

Aprovada para implementação em 5 de setembro de 2026.

## Contexto

O NVIDIA Startup AI Radar deverá evoluir para uma plataforma multiagente que analisa startups brasileiras e recomenda tecnologias NVIDIA. Nesta entrega, porém, é necessário apenas estabelecer a documentação orientada por especificações, converter os diagramas existentes para Mermaid e disponibilizar a fundação do frontend.

A arquitetura do backend será definida posteriormente pelo responsável pelo projeto.

## Objetivos

- Tornar os diagramas do problema e do pipeline legíveis e versionáveis no README.
- Estabelecer um processo SDD simples, rastreável e independente de ferramentas proprietárias.
- Criar um frontend mínimo com React, TypeScript e Vite.
- Documentar como instalar, executar, validar e evoluir o projeto.
- Preservar explicitamente as decisões de backend para uma etapa futura.

## Histórias do usuário

### US-01 — Compreender o problema

Como pessoa desenvolvedora, quero visualizar o problema e o pipeline em Mermaid para compreender o fluxo diretamente no repositório.

Critérios de aceite:

- O README contém dois blocos Mermaid nas seções correspondentes às imagens originais.
- O primeiro diagrama apresenta classificação Non-AI, AI-enabled e AI-native.
- O segundo apresenta os oito agentes e os caminhos condicionais de validação e recuperação.
- As imagens originais continuam disponíveis em `documents/`.

### US-02 — Executar o frontend

Como pessoa desenvolvedora, quero instalar e executar o frontend com comandos documentados para iniciar o desenvolvimento local sem depender de um backend.

Critérios de aceite:

- `npm install` instala as dependências do frontend.
- `npm run dev` inicia a aplicação Vite.
- `npm run lint`, `npm run test` e `npm run build` terminam com sucesso.
- A interface não chama endpoints nem presume contratos de backend.

### US-03 — Evoluir por SDD

Como pessoa mantenedora, quero um modelo explícito de especificação, planejamento e tarefas para que novas funcionalidades sejam discutidas antes da implementação.

Critérios de aceite:

- A pasta desta feature contém `spec.md`, `plan.md` e `tasks.md`.
- O README explica o ciclo SDD.
- Requisitos, decisões e tarefas usam identificadores rastreáveis.

### US-04 — Conhecer as decisões adiadas

Como pessoa mantenedora, quero conhecer as opções técnicas removidas para poder reavaliá-las sem confundi-las com decisões vigentes.

Critérios de aceite:

- Existe um documento separado para as opções removidas.
- O documento deixa claro que nenhuma dessas opções foi instalada ou configurada.
- Docker e Docker Compose não aparecem como parte da solução atual.

## Requisitos funcionais

- **RF-01:** documentar o problema em um fluxograma Mermaid.
- **RF-02:** documentar o pipeline MVP em um fluxograma Mermaid.
- **RF-03:** exibir uma página inicial responsiva com objetivo, estado e limites do projeto.
- **RF-04:** fornecer comandos locais para desenvolvimento e validação do frontend.
- **RF-05:** registrar as decisões técnicas removidas do planejamento inicial.

## Requisitos não funcionais

- **RNF-01:** utilizar TypeScript em modo estrito.
- **RNF-02:** manter compatibilidade com Node.js 20 ou superior.
- **RNF-03:** não exigir backend, banco de dados ou serviços externos para executar o frontend.
- **RNF-04:** manter layout utilizável em telas móveis e desktop.
- **RNF-05:** manter lint, testes e build automatizados por scripts npm.

## Restrições

- Não criar estrutura, contrato ou implementação de backend.
- Não criar agentes LangGraph ou cadeias LangChain executáveis.
- Não criar configuração, schema ou conexão PostgreSQL.
- Não usar Docker ou Docker Compose.
- Não instalar ferramentas sem relação com Python, FastAPI, SDD, React, TypeScript, Vite, LangGraph, LangChain ou PostgreSQL.

## Fora do escopo

- Autenticação e autorização.
- Persistência de dados.
- APIs e integrações externas.
- Implementação do RAG, reranker ou motor de recomendação.
- Exportação real de briefings.
- Pipeline de scraping.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-02 | Inspeção dos blocos Mermaid e das referências às imagens |
| US-02 | RF-03, RF-04, RNF-01 a RNF-05 | Lint, testes e build |
| US-03 | RF-04 | Inspeção de `spec.md`, `plan.md` e `tasks.md` |
| US-04 | RF-05 | Inspeção do documento de decisões removidas |
