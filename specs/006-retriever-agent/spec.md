# Especificação 006: Retriever Agent

## Status

Implementada e verificada em 6 de setembro de 2026; aguardando aprovação
explícita da entrega para conclusão.

A implementação foi autorizada por solicitação explícita do responsável pelo
projeto. As tarefas T-01 a T-10 foram concluídas; a T-11 permanece aberta até a
validação da entrega.

## Contexto

O Query Planner produz um `QueryPlan` validado com filtros de setor, porte,
estágio, localização, palavras-chave e sinais de IA. O Retriever deve consumir
somente planos `ready`, consultar a base PostgreSQL já populada e entregar
startups e documentos rastreáveis aos próximos agentes.

## Objetivos

- Consultar PostgreSQL usando os critérios do Query Planner.
- Selecionar e ordenar startups relevantes com limite configurável.
- Recuperar documentos das startups selecionadas sem consultas N+1.
- Preservar UUIDs e URLs das evidências.
- Representar busca sem resultados e falhas de persistência de forma previsível.

## Histórias e critérios de aceite

### US-01 — Selecionar startups pelos filtros planejados

Como pipeline, quero aplicar os filtros do plano para selecionar somente
startups compatíveis com a intenção da pessoa usuária.

Critérios de aceite:

- O Retriever só executa quando `query_plan.status` é `ready`.
- Setores, estágios e localizações são comparados sem diferença de maiúsculas e
  minúsculas; valores do mesmo campo usam OR e campos diferentes usam AND.
- Porte é traduzido para `team_size`: `micro` (1–10), `small`/`pequena`
  (11–50), `medium`/`média` (51–200), `large`/`grande` (201 ou mais), além de
  números e intervalos numéricos explícitos.
- Palavras-chave e sinais de IA procuram correspondência textual em dados da
  startup e em seus documentos.
- Todos os valores são enviados ao banco como parâmetros; nenhum texto do plano
  é interpolado em SQL.

### US-02 — Ordenar resultados relevantes

Como próximo agente, quero receber resultados em ordem estável para processar
primeiro as startups mais aderentes.

Critérios de aceite:

- Cada correspondência textual contribui para um score de relevância.
- Filtros estruturados contribuem com score base sem alterar sua função de filtro.
- A ordenação usa score decrescente, nome crescente e UUID crescente como desempates.
- A quantidade de startups é limitada por configuração validada, com padrão 20.
- Uma consulta exploratória sem filtros retorna startups por nome e UUID, dentro
  do limite, sem fabricar critérios.

### US-03 — Recuperar evidências rastreáveis

Como Extractor futuro, quero receber os documentos das startups selecionadas
com identidade e origem preservadas.

Critérios de aceite:

- Os documentos de todas as startups selecionadas são carregados em uma única
  consulta em lote.
- `candidate_startups` preserva o UUID da startup, nome e score.
- `selected_sources` preserva UUID, URL, título e trecho do documento.
- As fontes seguem a ordem das startups selecionadas e, dentro de cada startup,
  data de publicação decrescente, título e UUID.
- Startups sem documentos continuam nos candidatos sem criar fontes fictícias.

### US-04 — Tratar ausência e falhas

Como pessoa operadora, quero resultados vazios e falhas previsíveis sem quebrar
o grafo ou vazar detalhes do banco.

Critérios de aceite:

- Uma busca sem correspondências retorna listas vazias e o aviso
  `retriever_no_results`, sem exceção.
- Plano ausente retorna `retriever_plan_missing`; plano não pronto retorna
  `retriever_plan_not_ready`, ambos sem consultar repositórios.
- Falha esperada ou inesperada de persistência retorna
  `retriever_unavailable`, sem SQL, credencial, stack trace ou mensagem bruta.
- O nó retorna atualização parcial e preserva avisos, erros e métricas anteriores.

## Requisitos funcionais

- **RF-01:** ler o `QueryPlan` de `AppState` e validar seu status.
- **RF-02:** traduzir filtros para um contrato interno de busca.
- **RF-03:** consultar startups e calcular score com ordenação determinística.
- **RF-04:** carregar documentos em lote para os IDs selecionados.
- **RF-05:** preencher `candidate_startups` e `selected_sources`.
- **RF-06:** tratar busca vazia e indisponibilidade com códigos estáveis.
- **RF-07:** aplicar limite configurável e registrar duração e contagens.

## Requisitos não funcionais

- **RNF-01:** usar SQLAlchemy assíncrono e queries parametrizadas.
- **RNF-02:** evitar N+1 e limitar linhas antes de carregar documentos.
- **RNF-03:** usar índices nas colunas de filtro e join relevantes.
- **RNF-04:** manter o agente independente de SQLAlchemy e testável com fakes.
- **RNF-05:** não usar LLM, Qdrant, internet ou credenciais nos testes unitários.
- **RNF-06:** manter tipagem estrita, arquitetura e cobertura mínima de 80%.

## Fora do escopo

- Busca vetorial, BM25, reranking ou consulta à base NVIDIA.
- Taxonomia de setores, estágios e localidades além dos valores do plano.
- Classificação de maturidade, validação factual ou recomendação.
- Paginação pública, rota HTTP própria ou integração visual do frontend.
- Alterar o Query Planner ou executar o grafo completo.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01 a RF-03, RNF-01, RNF-03 | Testes de filtros, porte e SQL parametrizado |
| US-02 | RF-03, RF-07, RNF-02 | Testes de score, desempate, limite e exploração |
| US-03 | RF-04, RF-05, RNF-02 | Testes de lote, ordem, IDs e URLs |
| US-04 | RF-01, RF-06, RF-07, RNF-04 a RNF-06 | Fakes, erros sanitizados e suíte completa |

## Critério de conclusão

A feature estará concluída quando os critérios de aceite passarem, a consulta
real ao PostgreSQL for coberta por integração, a suíte completa permanecer
aprovada e a entrega receber aprovação explícita.

## Sugestão de commit

`feat(retriever): query PostgreSQL from structured query plans`
