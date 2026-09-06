# Decisões técnicas removidas do escopo

## Status

Registro histórico da especificação 001. Alguns itens foram posteriormente reavaliados e aprovados pela especificação 002; a tabela abaixo preserva o motivo da remoção original, sem representar o estado técnico atual.

Durante o planejamento inicial, algumas ferramentas e estruturas foram consideradas para antecipar a implementação completa. Após a revisão de escopo, a arquitetura de backend foi reservada para uma ideação futura do responsável pelo projeto e todo uso de Docker foi descartado desta etapa.

## Opções removidas

| Opção anteriormente considerada | Motivo da remoção atual |
| --- | --- |
| Estrutura FastAPI e endpoint de health check | Anteciparia a arquitetura do backend |
| Pastas de agentes, grafo, domínio, serviços, repositórios e infraestrutura | Imporia limites antes da ideação arquitetural |
| Estado tipado e nós iniciais do LangGraph | A modelagem multiagente ainda será definida |
| Pydantic no backend | Não existe backend no escopo atual |
| PostgreSQL configurado e extensão pgvector | Schema, persistência e estratégia vetorial ainda não foram definidos |
| Abstrações e SDKs de provedores de LLM | A seleção de modelos e provedores permanece aberta |
| Ruff, mypy e pytest para o backend Python | Não há código Python para validar nesta etapa |
| Hooks com pre-commit | Automação geral adiada até a definição da estrutura completa |
| Workflow de integração contínua | Adiado até existirem componentes e critérios de entrega definitivos |
| Docker e Docker Compose | Removidos expressamente do projeto nesta etapa |

## Possível reavaliação

Este registro não constitui recomendação para adoção futura. Cada item só poderá retornar ao projeto por meio de uma nova especificação SDD, com justificativa, alternativas, impactos e critérios de aceite próprios.

## Evolução aprovada pela especificação 002

Em 5 de setembro de 2026, a especificação `002-backend-foundation` aprovou a reintrodução de FastAPI, Pydantic, PostgreSQL, Qdrant, LangGraph, Ruff, mypy, pytest, pre-commit, integração contínua e Compose. A decisão não altera retroativamente o escopo da especificação 001; ela registra uma nova etapa, com critérios de aceite e validações próprios.

Dockerfile e implantação da API continuam fora do escopo.
