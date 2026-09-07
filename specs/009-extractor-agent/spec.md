# Especificação 009: Extractor Agent

## Status

Concluída em 7 de setembro de 2026 após implementação, verificação e aprovação
explícita da entrega pelo responsável pelo projeto.

## Contexto

O fluxo atual transforma uma consulta em plano, recupera startups no PostgreSQL
e transporta referências de documentos em `selected_sources`. A próxima etapa
precisa converter esse conteúdo não estruturado em perfis verificáveis, sem
classificar maturidade de IA ou fabricar informações ausentes.

O `AppState` já reserva `structured_profiles`, mas o contrato atual contém apenas
campos preliminares e não obriga cada afirmação a apontar para sua fonte. Além
disso, `SourceReference` ainda não carrega `startup_id`, portanto o Extractor não
consegue associar uma fonte à startup de forma segura apenas pelo estado. Esta
feature deve completar esses contratos antes de conectar o novo nó.

## Objetivos

- Implementar o Extractor Agent como nó assíncrono e isoladamente testável.
- Usar o perfil `llm_fast` já alocado ao nó `extractor`.
- Gerar um perfil estruturado para cada startup que possua fontes apropriadas.
- Manter toda informação extraída ligada à startup, ao UUID do documento e à URL.
- Representar campos ausentes sem completar dados por suposição.
- Tratar fontes insuficientes, saída inválida e indisponibilidade de forma segura.
- Executar o Extractor após o Retriever somente quando houver candidatos e fontes
  utilizáveis.
- Expor os perfis na resposta atual de `/api/v1/search`.

## Histórias do usuário

### US-01 — Estruturar o perfil da startup

Como próximo agente da pipeline, quero receber um perfil estruturado para não
precisar interpretar novamente os documentos brutos.

Critérios de aceite:

- O agente recebe `candidate_startups` e `selected_sources` do `AppState`.
- O agente analisa o conteúdo textual de `SourceReference.excerpt` de cada fonte
  apropriada e transforma as informações identificáveis nesses trechos nos
  campos estruturados do perfil.
- Para cada startup com ao menos uma fonte apropriada, produz exatamente um
  `StructuredStartupProfile`.
- O perfil preserva `startup_id` e o nome recebido em `candidate_startups`.
- O contrato contempla produto, modelo de negócio, setor, público-alvo, casos de
  uso de IA, tecnologias mencionadas, infraestrutura, dependências externas,
  possíveis necessidades técnicas e afirmações adicionais.
- Produto, modelo de negócio, setor e público-alvo aceitam um fato ou `null`.
- Campos de múltiplos valores usam listas vazias por padrão, nunca `null`.
- Duplicatas textuais dentro do mesmo campo são removidas sem perder a primeira
  ordem sustentada pelas fontes.
- O agente retorna somente uma atualização parcial do estado.

### US-02 — Preservar rastreabilidade por afirmação

Como pessoa analista, quero verificar a origem de cada informação extraída para
consultar o documento que a sustenta.

Critérios de aceite:

- Toda informação não nula do perfil é representada por `ExtractedFact`.
- Cada `ExtractedFact` contém texto não vazio e uma ou mais
  `ExtractionSource`.
- Cada `ExtractionSource` contém `startup_id`, `source_id` e `source_url`.
- `source_id` e `source_url` precisam formar um par presente em
  `selected_sources` para a mesma startup.
- O Extractor rejeita UUID, URL ou associação de startup que não existam na
  entrada; a IA não pode criar uma nova fonte.
- Um fato pode citar mais de um documento, sem repetir a mesma referência.
- A ordem das fontes acompanha a ordem de `selected_sources`.
- `SourceReference` passa a preservar `startup_id`, permitindo agrupamento
  determinístico sem nova consulta ao PostgreSQL.

### US-03 — Não inventar informações ausentes

Como pessoa usuária, quero que lacunas permaneçam explícitas para não confundir
suposição do modelo com evidência documental.

Critérios de aceite:

- O prompt instrui o modelo a extrair somente conteúdo identificável no texto
  fornecido em `excerpt`.
- Os campos estruturados e afirmações adicionais devem ser derivados dos
  `excerpt`s associados à startup; IDs, URLs, títulos, nome da startup e a
  consulta original não são evidência textual suficiente por si só.
- Campos escalares sem suporte ficam `null`; campos de lista sem suporte ficam
  vazios.
- `unknown_fields` enumera os campos previstos que não puderam ser sustentados.
- Um campo listado em `unknown_fields` não pode conter fato extraído.
- O agente não usa conhecimento externo, a consulta original ou atributos sem
  fonte para completar o perfil.
- “Possíveis necessidades técnicas” representam somente necessidades, limitações
  ou desafios mencionados ou diretamente identificáveis no documento; não são
  recomendações criadas pelo modelo.
- Resumos ou afirmações adicionais seguem as mesmas regras de citação dos demais
  fatos.

### US-04 — Tratar fontes ausentes ou insuficientes

Como pessoa operadora, quero encerramento previsível quando não houver conteúdo
adequado para extração.

Critérios de aceite:

- Sem `candidate_startups`, o grafo encerra após o Retriever e não chama o modelo.
- Com candidatos, mas sem fonte apropriada para qualquer um deles, o grafo
  encerra sem executar o Extractor.
- Fonte apropriada possui `startup_id` candidato, UUID, URL e `excerpt` textual
  não vazio.
- O Retriever adiciona `retriever_no_sources` quando encontra candidatos, mas
  nenhuma fonte apropriada.
- Quando apenas parte das startups possui fontes, o Extractor processa somente
  essa parte e adiciona `extractor_sources_missing` para as demais.
- Ausência ou insuficiência de fonte não cria perfil fictício, não é erro HTTP e
  preserva candidatos e fontes no estado.
- O grafo termina em `END` após o Extractor, pois o Startup Classifier continua
  fora do escopo desta entrega.

### US-05 — Validar e reparar a saída do modelo

Como pessoa mantenedora, quero uma saída estrita para impedir dados malformados
ou citações fabricadas no estado compartilhado.

Critérios de aceite:

- A saída do modelo é validada por contrato Pydantic estrito, sem campos extras.
- O modelo retorna somente campos extraíveis e referências; `startup_id`, nome e
  status do perfil são definidos ou confirmados pelo agente a partir da entrada.
- Após validação estrutural, o agente valida todas as referências contra as fontes
  permitidas da startup.
- Saída inválida passa por no máximo uma tentativa configurável de reparo.
- O reparo recebe somente o schema, os identificadores permitidos e a saída
  candidata delimitada; não recebe segredos ou detalhes do provedor.
- Persistindo a invalidade, o agente retorna `extractor_invalid_output` de forma
  sanitizada.
- Falha do `ChatModel` retorna `extractor_unavailable` sem resposta bruta,
  stack trace, credencial ou mensagem interna.
- Perfis concluídos antes de uma falha permanecem no estado; a execução registra
  o erro e não fabrica perfil para a startup que falhou.

### US-06 — Operar o nó com limites e métricas

Como pessoa operadora, quero controlar o custo da extração e observar seu
resultado sem registrar documentos sensíveis.

Critérios de aceite:

- O Extractor usa `ModelRegistry.resolve(NodeName.EXTRACTOR)` e, portanto,
  `llm_fast`.
- Cada chamada processa uma startup e somente suas fontes apropriadas.
- Quantidade de fontes e caracteres de contexto por startup possuem limites
  configuráveis e validados.
- Quando o conteúdo é truncado pelo limite, o agente adiciona
  `extractor_context_truncated`.
- Métricas incluem duração, startups recebidas, startups processadas, perfis
  produzidos, fontes utilizadas, chamadas ao modelo, reparos e falhas.
- Logs incluem somente nó, duração, contagens, status e versão do prompt.
- Consultas, conteúdo dos documentos, prompts, respostas brutas e URLs completas
  não são registrados.

### US-07 — Consumir os perfis pela API e pelo grafo

Como frontend, quero receber os perfis extraídos na busca existente para exibir
informações estruturadas e suas fontes.

Critérios de aceite:

- `POST /api/v1/search` inclui `structured_profiles` na resposta.
- UUIDs são serializados como strings e URLs permanecem inalteradas.
- Fontes insuficientes retornam HTTP 200 com avisos.
- `extractor_invalid_output` retorna HTTP 502.
- `extractor_unavailable` retorna HTTP 503.
- O endpoint isolado `/api/v1/query-plans` não executa o Extractor e mantém seu
  contrato.
- O OpenAPI descreve perfis, fatos, campos desconhecidos e referências.

## Contratos conceituais

```text
ProfileField
├── product
├── business_model
├── sector
├── target_audience
├── ai_use_cases
├── technologies
├── infrastructure
├── external_dependencies
├── technical_needs
└── claims

ExtractionSource
├── startup_id: UUID
├── source_id: UUID
└── source_url: string

ExtractedFact
├── value: string
└── sources: list[ExtractionSource] (mínimo 1)

StructuredStartupProfile
├── startup_id: UUID
├── name: string
├── product: ExtractedFact | null
├── business_model: ExtractedFact | null
├── sector: ExtractedFact | null
├── target_audience: ExtractedFact | null
├── ai_use_cases: list[ExtractedFact]
├── technologies: list[ExtractedFact]
├── infrastructure: list[ExtractedFact]
├── external_dependencies: list[ExtractedFact]
├── technical_needs: list[ExtractedFact]
├── claims: list[ExtractedFact]
└── unknown_fields: list[ProfileField]
```

`ExtractionSource` é um ponteiro validado para uma `SourceReference`; ele não
duplica o conteúdo do documento. O perfil não contém classificação de maturidade,
confiança factual definitiva ou recomendação.

## Fluxo do grafo

```text
START
  ↓
query_planner
  ↓ ready
retriever
  ↓ route_after_retriever
  ├── candidatos + fontes apropriadas → extractor → END
  └── sem candidatos ou sem fontes ───────────────→ END
```

O roteamento após o Query Planner permanece inalterado. `route_after_retriever`
é uma função pura e não chama modelo, banco ou serviço externo.

## Códigos e avisos

| Identificador | Tipo | Situação |
| --- | --- | --- |
| `retriever_no_sources` | aviso | Há candidatos, mas nenhuma fonte apropriada |
| `extractor_sources_missing` | aviso | Parte dos candidatos não possui fonte apropriada |
| `extractor_context_truncated` | aviso | Fontes ou texto excederam o limite configurado |
| `extractor_invalid_output` | erro | A saída continuou inválida após reparo |
| `extractor_unavailable` | erro | O modelo necessário não pôde concluir a extração |

## Requisitos funcionais

- **RF-01:** definir contratos estritos de perfil, fato e referência de extração.
- **RF-02:** associar cada `SourceReference` à startup correspondente.
- **RF-03:** agrupar candidatos e fontes por `startup_id` sem nova consulta ao banco.
- **RF-04:** construir contexto somente com fontes apropriadas e dentro dos limites.
- **RF-05:** extrair os campos definidos sem preencher informações ausentes.
- **RF-05a:** usar `SourceReference.excerpt` como conteúdo documental analisável
  para preencher os campos estruturados e as afirmações do perfil.
- **RF-06:** validar estrutura, UUID, URL e associação de cada referência.
- **RF-07:** executar no máximo uma tentativa configurável de reparo.
- **RF-08:** preservar resultados parciais e emitir falhas sanitizadas.
- **RF-09:** atualizar `structured_profiles`, avisos, erros e métricas no `AppState`.
- **RF-10:** adicionar o Extractor e o roteamento posterior ao Retriever no grafo.
- **RF-11:** expor `structured_profiles` em `/api/v1/search` e mapear erros HTTP.
- **RF-12:** resolver o modelo do Extractor pela política central existente.

## Requisitos não funcionais

- **RNF-01:** manter tipagem estrita, contratos imutáveis e saída sem campos extras.
- **RNF-02:** manter execução assíncrona e limites finitos de contexto.
- **RNF-03:** não acessar PostgreSQL, Qdrant, internet ou SDK concreto no agente.
- **RNF-04:** usar uma nova instância de dados por invocação, sem estado global ou
  memória conversacional.
- **RNF-05:** testes unitários usam fakes e não chamam Groq ou banco.
- **RNF-06:** não registrar conteúdo de documento, URL completa, prompt, resposta
  bruta ou segredo.
- **RNF-07:** preservar UTF-8, UUIDs e URLs recebidos.
- **RNF-08:** manter Ruff, mypy, testes arquiteturais, cobertura mínima de 80% e
  regressão do frontend.

## Restrições

- LangGraph permanece responsável pelo encadeamento dos agentes.
- O Extractor usa somente dados presentes no estado recebido.
- O agente depende de `ChatModel`, não de Groq ou LangChain concretos.
- Citações devem apontar para fontes fornecidas ao modelo e validadas localmente.
- Nenhuma alteração de schema PostgreSQL é necessária nesta feature.
- A ordem de `candidate_startups` determina a ordem dos perfis produzidos.

## Fora do escopo

- Classificar a startup como `ai-native`, `ai-enabled` ou `non-ai`.
- Confirmar definitivamente que uma afirmação é verdadeira ou suficiente.
- Calcular confiança factual definitiva.
- Recomendar produtos ou tecnologias NVIDIA.
- Consultar a base NVIDIA, Qdrant, BM25 ou reranker.
- Buscar documentos adicionais, navegar URLs ou enriquecer dados externamente.
- Persistir perfis extraídos ou alterar tabelas PostgreSQL.
- Implementar Startup Classifier, Evidence Validator ou os agentes seguintes.
- Streaming, paralelismo distribuído, checkpoint ou intervenção humana.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-03 a RF-05, RF-09, RNF-01 | Testes de contrato, campos, ordem e atualização parcial |
| US-02 | RF-01, RF-02, RF-06, RNF-07 | Testes de UUID, URL, startup, fontes múltiplas e rejeição |
| US-03 | RF-04 a RF-06, RNF-03 | Testes de ausências, `unknown_fields` e não inferência |
| US-04 | RF-03, RF-08, RF-10 | Testes de roteamento, busca vazia, fontes ausentes e resultado parcial |
| US-05 | RF-06 a RF-08, RNF-01, RNF-05 | Testes de parsing, reparo, referência inválida e falha sanitizada |
| US-06 | RF-04, RF-09, RF-12, RNF-02, RNF-04, RNF-06 | Testes de limites, modelo, métricas, isolamento e logs |
| US-07 | RF-10, RF-11, RNF-07, RNF-08 | Testes de grafo, API, OpenAPI, HTTP e suíte completa |

## Critério de conclusão

A feature estará concluída quando o Extractor produzir perfis estritos e
rastreáveis apenas para startups com fontes apropriadas, o grafo encerrar
corretamente os demais casos, a API expuser os perfis, todos os testes e critérios
passarem e a entrega receber aprovação explícita.

## Sugestão de commit

`feat(extractor): structure startup profiles from retrieved sources`

## Evolução posterior

A especificação 010 substitui o encerramento direto após o Extractor por
`Extractor → Startup Classifier/END`. O Classifier usa os perfis e as fontes sem
alterar as afirmações extraídas.
