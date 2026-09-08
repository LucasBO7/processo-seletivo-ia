# Plano 016: orquestração completa do pipeline

## Estratégia

O trabalho será feito sobre `app.graph.builder`, mantendo sua API pública. A
ordem TAPI será declarada centralmente e cada rota continuará retornando uma
decisão curta de continuar/parar. As verificações passarão a exigir instâncias
válidas dos contratos relevantes e vínculos coerentes por `startup_id`.

Erros não serão inspecionados por uma lista global que impediria resultados
parciais. Cada transição observará a saída válida disponível; sem saída, qualquer
falha ou ausência termina naturalmente. O bloqueio explícito do Planner será
preservado porque uma consulta inválida não pode iniciar I/O.

## Alterações

1. Declarar `PIPELINE_NODE_ORDER` com os oito `NodeName`.
2. Endurecer predicados de roteamento para não aceitar objetos malformados.
3. Preservar as decisões aprovadas nas specs anteriores, incluindo validação sem
   classificação e continuidade parcial.
4. Ampliar testes unitários de topologia, associações, interrupções e falhas.
5. Criar integração controlada usando agentes reais e seis respostas falsas de
   modelo, além de repositories e mecanismos de recuperação falsos.
6. Confirmar por teste que o lifespan reutiliza um único workflow.
7. Atualizar documentação e executar a matriz completa de qualidade.

## Teste integrado

O cenário mínimo terá uma startup com um documento citável e dois chunks NVIDIA:
NIM e Inception. O modelo rápido responderá Planner, Extractor e Validator; o
modelo pesado responderá Classifier, Recommendation e Briefing. O NVIDIA RAG
usará embedding, busca vetorial, busca lexical e reranker falsos.

O resultado deverá conter perfil, classificação, validação, contexto NVIDIA,
recomendação e briefing, mantendo os UUIDs e URLs originais e métricas dos oito
nós.

## Verificação

- Ruff check e format check.
- mypy estrito.
- import-linter.
- testes unitários com cobertura mínima de 80%.
- integração controlada e integrações existentes.
- lint, testes e build do frontend.

## Resultado da implementação

- O único builder existente passou a declarar explicitamente a ordem dos oito nós.
- Os roteamentos validam contratos, conteúdo mínimo e associação por `startup_id`.
- Interrupções sem pré-condição e continuidade com resultado parcial foram testadas.
- A integração controlada percorreu os oito agentes reais e preservou UUIDs, URLs,
  citações e métricas.
- 323 testes unitários passaram com 90,02% de cobertura.
- 4 integrações passaram, incluindo PostgreSQL/Qdrant e o pipeline controlado.
- Ruff, mypy e os dois contratos do import-linter passaram.
- Teste, lint e build do frontend passaram.

## Sugestão de commit

`feat(graph): validate and test full pipeline orchestration`
