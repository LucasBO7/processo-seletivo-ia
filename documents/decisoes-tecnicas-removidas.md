# Decisões técnicas removidas do escopo

## Status

Registro histórico. Os itens deste documento **não estão aprovados, instalados ou configurados** no projeto atual.

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
