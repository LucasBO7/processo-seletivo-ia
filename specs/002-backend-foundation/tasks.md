# Tarefas 002: fundação do backend

As tarefas T-01 a T-33 foram implementadas e verificadas em 5 de setembro de
2026. A T-34 permanece aberta até a aprovação explícita desta entrega.

## Preparação

- [x] **T-01 [US-01, RNF-01]** Criar o projeto Python em `backend/` com `pyproject.toml`, layout `src`, grupos de dependências e versão suportada do Python.
- [x] **T-02 [US-01]** Gerar e versionar o lockfile, documentando instalação e atualização de dependências.
- [x] **T-03 [US-01, US-07]** Configurar comandos de desenvolvimento, qualidade, testes unitários, testes de integração e verificação agregada.
- [x] **T-04 [US-07]** Configurar Ruff, mypy, pytest, cobertura, pre-commit e regras de importação entre camadas.

## Arquitetura e configuração

- [x] **T-05 [US-02, RF-10]** Criar o pacote `app` com os módulos de API, aplicação, domínio, grafo, infraestrutura e core descritos no plano, além de uma composition root explícita.
- [x] **T-06 [US-02]** Criar testes arquiteturais que impeçam imports de frameworks e adaptadores no domínio e na aplicação.
- [x] **T-07 [US-04, RF-03]** Implementar configuração tipada e fail-fast para aplicação, HTTP, banco, chat, embeddings, reranker, timeouts e logging.
- [x] **T-08 [US-04]** Criar `.env.example`, proteger arquivos locais no `.gitignore` e testar ausência de valores secretos versionados.
- [x] **T-09 [US-04, RF-07]** Definir protocolos assíncronos mínimos para chat model, embeddings e reranking, encapsular o cliente Cohere em um adaptador e fornecer fakes determinísticos de teste.

## Persistência

- [x] **T-10 [US-05]** Adicionar Compose com PostgreSQL 16 e Qdrant, volumes nomeados e healthchecks para desenvolvimento e CI.
- [x] **T-11 [US-05, RF-05]** Configurar Alembic e criar a migração inicial de tabelas, restrições e índices.
- [x] **T-12 [US-05, RF-06]** Definir contratos de repositório assíncronos na aplicação e implementações PostgreSQL na infraestrutura.
- [x] **T-13 [US-05, RNF-09]** Implementar criação, injeção e encerramento ordenado do engine, pool e cliente Qdrant.
- [x] **T-14 [US-05]** Criar e validar de forma idempotente a coleção Qdrant versionada, com dimensão e distância configuradas.
- [x] **T-15 [US-05]** Criar testes de integração para migrações, schema, coleção vetorial, escrita e leitura mínimas.

## API e operação

- [x] **T-16 [US-03, RF-01, RF-02]** Criar a aplicação FastAPI versionada e os endpoints de liveness e readiness.
- [x] **T-17 [US-03, RF-04]** Implementar middleware de correlação, envelope de erro e logs estruturados com duração.
- [x] **T-18 [US-03]** Configurar CORS por allowlist e validar o contrato OpenAPI.
- [x] **T-19 [US-03]** Criar testes de API para sucesso, dependência indisponível, erros sanitizados, correlação, CORS e limite de latência de liveness.

## Fundação multiagente

- [x] **T-20 [US-06, RF-08]** Definir modelos de domínio para fontes, evidências, citações, diagnósticos e erros recuperáveis.
- [x] **T-21 [US-06, RF-08]** Definir o estado tipado do LangGraph e as regras de atualização parcial, sem lógica de agentes.
- [x] **T-22 [US-06, RF-09]** Centralizar em `graph/nodes.py` os identificadores dos oito nós previstos no TAPI, mantendo sua implementação para specs futuras.
- [x] **T-23 [US-06]** Separar em `graph/contracts.py` e `graph/builder.py` o contrato de nó e a construção futura do grafo, sem compilar um fluxo fictício.
- [x] **T-24 [US-06]** Testar serialização, referências de fonte, atualizações parciais e ausência de clientes ou segredos no estado.

## Integração contínua e documentação

- [x] **T-25 [US-07]** Criar workflow de CI com PostgreSQL, Qdrant e verificações de backend e frontend.
- [x] **T-26 [US-01, RNF-10]** Atualizar o README com arquitetura real, pré-requisitos, variáveis e comandos do backend.
- [x] **T-27 [US-01, US-05]** Atualizar o registro da especificação 001 para explicar a reintrodução aprovada de Compose nesta etapa.
- [x] **T-28 [US-07]** Documentar como diagnosticar falhas de configuração, readiness e migração.

## Verificação final

- [x] **T-29 [US-01, US-07]** Reproduzir instalação e inicialização a partir de um clone limpo.
- [x] **T-30 [US-05]** Validar migrações em PostgreSQL real, a coleção Qdrant e a correspondência dos chunks entre os dois serviços.
- [x] **T-31 [US-07]** Executar formatação em modo check, lint, mypy, testes unitários, testes arquiteturais, testes de integração e cobertura mínima.
- [x] **T-32 [US-07]** Executar lint, testes e build do frontend existente.
- [x] **T-33 [US-03, US-04]** Verificar manualmente logs, shutdown, OpenAPI e ausência de segredos no repositório e nas respostas.
- [ ] **T-34 [US-01 a US-07]** Revisar todos os critérios de aceite, atualizar documentação e marcar a especificação como concluída somente após aprovação da entrega.
