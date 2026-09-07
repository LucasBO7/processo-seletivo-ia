# Especificação 011: Evidence Validator Agent

## Status

Implementada e verificada em 7 de setembro de 2026; aguarda aprovação explícita
da entrega para conclusão formal.

## Contexto

O fluxo atual produz perfis estruturados citados pelo Extractor e classificações
de maturidade pelo Startup Classifier. Uma referência existente demonstra
rastreabilidade, mas ainda não garante que o texto do documento realmente
sustente a afirmação ou a classificação associada.

O Evidence Validator deve comparar cada afirmação com os `excerpt`s recuperados,
sem navegar nas URLs, buscar novas fontes ou verificar a verdade no mundo real.
Nesta especificação, `supported` significa apenas “há suporte documental
suficiente nos documentos analisados”.

Os dados originais em `structured_profiles` e `classifications` permanecem
imutáveis para auditoria. Agentes posteriores deverão consumir exclusivamente
`validated_profiles` e `validated_classifications` como fatos aprovados.

## Objetivos

- Avaliar todas as afirmações extraídas e a classificação de cada startup.
- Produzir resultados `supported`, `unsupported`, `conflicting` ou `insufficient`.
- Preservar startup, UUID e URL das fontes analisadas.
- Construir perfis validados somente com fatos `supported`.
- Separar itens rejeitados, conflitos e lacunas de evidência.
- Impedir que afirmações não aprovadas sejam consumidas como fatos confirmados.
- Executar depois do Classifier somente quando houver entrada correspondente.
- Encerrar de modo previsível quando nenhum fato sobreviver.

## Semântica dos resultados

### `supported`

Ao menos uma fonte analisada sustenta diretamente a afirmação e nenhuma fonte
analisada a contradiz. A conclusão deve estar baseada no texto do `excerpt`, não
somente no título, URL, nome ou metadados.

### `unsupported`

Existe material documental analisável, mas nenhuma fonte sustenta a afirmação.
Esse resultado também se aplica quando o texto contradiz a afirmação sem haver
outra fonte que a sustente. O item é rejeitado e não entra no perfil validado.

### `conflicting`

Ao menos uma fonte sustenta e ao menos uma fonte contradiz a mesma afirmação. O
item é registrado como conflito e não entra no perfil validado.

### `insufficient`

Não há conteúdo adequado para decidir: fonte ausente, associação inválida, URL
ausente, `excerpt` vazio, contexto truncado de forma material, texto ambíguo ou
quantidade de evidência insuficiente. Ausência de documentação não equivale a
`unsupported`.

## Regras para múltiplas fontes

- Todas as fontes apropriadas da startup, dentro dos limites configurados, podem
  ser consideradas, inclusive fontes diferentes da citação original.
- Cada fonte analisada recebe `supports`, `contradicts` ou `not_found`.
- Uma fonte não pode ser criada pelo modelo e nunca pode pertencer a outra
  startup.
- Referências duplicadas são removidas preservando a ordem de `selected_sources`.
- `supported` exige ao menos uma fonte `supports` e zero `contradicts`.
- `conflicting` exige simultaneamente `supports` e `contradicts`.
- Sem `supports` e com documento analisável, o resultado é `unsupported`.
- Sem documento analisável suficiente, o resultado é `insufficient`.
- Uma fonte contraditória não é apagada mesmo quando outra fonte sustenta o item.

## Histórias do usuário

### US-01 — Validar cada afirmação extraída

Como pessoa analista, quero saber quais informações do perfil possuem suporte
documental suficiente.

Critérios de aceite:

- O agente recebe `structured_profiles`, `classifications` e `selected_sources`.
- Todo `ExtractedFact` não nulo recebe exatamente um `ClaimValidation`.
- Cada afirmação possui uma chave determinística composta por campo e índice,
  como `product` ou `technologies[0]`.
- O valor da afirmação e a identidade da startup são copiados do perfil, nunca da
  saída do modelo.
- O resultado usa somente um dos quatro status documentados.
- A justificativa é objetiva e não afirma verdade além do suporte documental.
- O agente não omite silenciosamente uma afirmação recebida.

### US-02 — Validar a classificação de maturidade

Como pessoa usuária, quero saber se a categoria de maturidade também é sustentada
pelos documentos.

Critérios de aceite:

- Cada perfil recebe exatamente um `ClassificationValidation` para a classificação
  correspondente.
- Se a classificação estiver ausente por falha anterior, a validação da
  classificação é `insufficient`, sem impedir a validação dos fatos do perfil.
- Classificação `uncertain` ou com categoria nula produz resultado
  `insufficient` determinístico, sem transformar incerteza em categoria.
- Classificação `classified` é avaliada usando categoria, justificativa, sinais e
  excerpts da mesma startup.
- Somente classificação com resultado `supported` entra em
  `validated_classifications`.
- Classificação rejeitada ou conflitante não altera o objeto original.
- Validar suporte não significa confirmar definitivamente a maturidade real.

### US-03 — Preservar fontes analisadas

Como pessoa auditora, quero reproduzir por que uma afirmação foi aprovada ou
rejeitada.

Critérios de aceite:

- Cada validação contém `startup_id`, `source_id`, `source_url` e o veredito da
  fonte analisada.
- UUID, URL e associação são validados contra `selected_sources`.
- URLs permanecem inalteradas; o agente não abre nem consulta seus conteúdos.
- O texto integral do `excerpt` não é duplicado na saída de validação.
- Fontes com URL vazia, `excerpt` ausente ou associação inválida são registradas
  como lacuna e nunca consideradas suporte.
- A ordem das fontes acompanha `selected_sources`.
- A IA não pode incluir uma fonte que não estava no estado recebido.

### US-04 — Produzir perfil validado

Como próximo agente da pipeline, quero consumir apenas fatos com suporte
documental aprovado.

Critérios de aceite:

- Para cada perfil de entrada, o agente produz um `ValidatedStartupProfile`.
- O perfil validado preserva `startup_id` e nome do perfil original.
- Campos escalares são mantidos somente quando sua validação é `supported`; caso
  contrário ficam `null`.
- Campos de lista contêm somente fatos `supported`, preservando a ordem original.
- O texto de cada fato aprovado é copiado do perfil original, enquanto suas
  referências no perfil validado são reconstruídas somente com fontes cujo
  veredito seja `supports`.
- `unknown_fields` é recalculado de acordo com os campos que ficaram sem fatos.
- `structured_profiles` e suas afirmações não são removidos nem alterados.
- Agentes posteriores devem usar `validated_profiles`, não
  `structured_profiles`, como fonte de fatos confirmados.

### US-05 — Separar rejeições, conflitos e lacunas

Como pessoa analista, quero distinguir falta de suporte, contradição e falta de
documentação.

Critérios de aceite:

- `claim_validations` contém todos os resultados na ordem dos perfis e campos.
- `validated_claims` contém somente resultados `supported`.
- `rejected_claims` contém somente resultados `unsupported`.
- `conflicting_claims` contém somente resultados `conflicting`.
- `evidence_gaps` contém somente resultados `insufficient`.
- Cada lista preserva a justificativa e referências do resultado original.
- Resultados da validação de classificação permanecem separados dos fatos do
  perfil, evitando tratá-los como afirmações extraídas.

### US-06 — Tratar ausência de afirmações aprovadas

Como pessoa operadora, quero um encerramento previsível quando nada puder ser
confirmado.

Critérios de aceite:

- Se nenhum fato de uma startup for `supported`, seu perfil validado permanece
  presente apenas com identidade e campos vazios.
- O aviso `validator_no_supported_claims` é adicionado quando nenhuma afirmação
  extraída sobreviver em toda a execução.
- O resultado continua HTTP 200, desde que não haja falha técnica.
- Nenhuma afirmação rejeitada, conflitante ou insuficiente é copiada para o
  perfil validado.
- O grafo termina em `END` após o Validator nesta entrega.

### US-07 — Validar saída e recuperar falhas

Como pessoa mantenedora, quero impedir resultados incompletos ou evidências
fabricadas.

Critérios de aceite:

- A saída do modelo usa contratos Pydantic estritos, imutáveis e sem campos
  extras.
- A resposta deve conter exatamente uma avaliação para cada chave enviada.
- Chaves duplicadas, ausentes ou desconhecidas invalidam toda a resposta da
  startup.
- A coerência entre status e vereditos das fontes é validada localmente.
- Toda referência é validada contra a allowlist da startup.
- Saída inválida recebe no máximo uma tentativa configurável de reparo.
- Invalidade persistente gera `evidence_validator_invalid_output` sanitizado.
- Indisponibilidade gera `evidence_validator_unavailable` sanitizado.
- Resultados concluídos antes de uma falha permanecem no estado.

### US-08 — Orquestrar e observar o nó

Como pessoa operadora, quero executar o Validator somente com entrada adequada e
acompanhar seu custo sem vazar documentos.

Critérios de aceite:

- `route_after_classifier` encaminha ao Validator quando existe ao menos um
  perfil estruturado; uma classificação ausente será tratada como lacuna.
- Sem perfil estruturado, o grafo termina após o Classifier.
- O Validator usa `ModelRegistry.resolve(NodeName.EVIDENCE_VALIDATOR)` e o perfil
  `llm_fast` da política central.
- Cada chamada ao modelo processa uma startup, seus itens e suas fontes.
- Quantidade de fontes, itens, caracteres, justificativas e reparos possuem
  limites configuráveis e validados.
- Truncamento adiciona `evidence_validator_context_truncated` e nunca converte
  automaticamente um item afetado em `supported`.
- Métricas incluem duração, startups, itens recebidos, resultados por status,
  perfis validados, classificações aprovadas, fontes, chamadas, reparos e falhas.
- Logs contêm somente nó, versão do prompt, status, duração e contagens.
- Consultas, perfis, afirmações, excerpts, prompts, respostas, URLs e segredos não
  são registrados.

### US-09 — Disponibilizar o resultado pela API

Como frontend, quero consumir perfis validados e diagnósticos de evidência na
busca existente.

Critérios de aceite:

- `POST /api/v1/search` inclui `validated_profiles`,
  `validated_classifications`, `claim_validations`, `classification_validations`,
  `validated_claims`, `rejected_claims`, `conflicting_claims` e `evidence_gaps`.
- UUIDs são strings e URLs permanecem inalteradas.
- Resultado sem afirmações aprovadas retorna HTTP 200 com aviso.
- `evidence_validator_invalid_output` retorna HTTP 502.
- `evidence_validator_unavailable` retorna HTTP 503.
- O OpenAPI descreve todos os contratos e enums adicionados.
- `/api/v1/query-plans` permanece inalterado e não executa o Validator.

### US-10 — Preservar limites de responsabilidade

Como pessoa mantenedora, quero que o agente valide somente suporte documental.

Critérios de aceite:

- O agente não altera perfis, afirmações ou classificações originais.
- O agente não consulta internet, URLs, PostgreSQL, Qdrant ou base NVIDIA.
- O agente não cria novas evidências.
- O agente não gera recomendações, tecnologias ou enriquecimento.
- O agente depende apenas de `ChatModel` e do estado recebido.

## Contratos conceituais

```text
EvidenceStatus
├── supported
├── unsupported
├── conflicting
└── insufficient

SourceVerdict
├── supports
├── contradicts
└── not_found

SourceAssessment
├── startup_id: UUID
├── source_id: UUID
├── source_url: string
└── verdict: SourceVerdict

ClaimValidation
├── startup_id: UUID
├── claim_key: string
├── field: ProfileField
├── value: string
├── status: EvidenceStatus
├── justification: string
├── original_sources: list[ExtractionSource]
└── analyzed_sources: list[SourceAssessment]

ClassificationValidation
├── startup_id: UUID
├── category: AIMaturity | null
├── status: EvidenceStatus
├── justification: string
└── analyzed_sources: list[SourceAssessment]

ValidatedStartupProfile
├── startup_id: UUID
├── name: string
├── mesmos campos factuais de StructuredStartupProfile
└── unknown_fields: list[ProfileField]
```

O modelo retorna apenas `claim_key`, status, justificativa e avaliações das
fontes. Startup, campo, valor, fontes originais, categoria e identidade final são
compostos pelo agente a partir das entradas.

## Fluxo do grafo

```text
START
  ↓
query_planner
  ↓
retriever
  ↓
extractor
  ↓ perfis válidos
startup_classifier
  ↓ route_after_classifier
  ├── ao menos um perfil estruturado → evidence_validator → END
  └── nenhum perfil estruturado ──────────────────────────→ END
```

## Códigos e avisos

| Identificador | Tipo | Situação |
| --- | --- | --- |
| `validator_no_supported_claims` | aviso | Nenhuma afirmação extraída foi aprovada |
| `evidence_validator_context_truncated` | aviso | Contexto excedeu limite configurado |
| `evidence_validator_source_gap` | aviso | Há fonte ausente, inválida ou sem conteúdo |
| `evidence_validator_invalid_output` | erro | Saída continuou inválida após reparo |
| `evidence_validator_unavailable` | erro | Modelo não concluiu a validação |

## Requisitos funcionais

- **RF-01:** enumerar deterministicamente todas as afirmações dos perfis.
- **RF-02:** avaliar afirmações nos quatro status documentados.
- **RF-03:** avaliar separadamente o suporte da classificação.
- **RF-04:** registrar veredito e referência de cada fonte analisada.
- **RF-05:** validar chaves, referências e coerência local dos resultados.
- **RF-06:** compor perfis validados somente com fatos aprovados.
- **RF-07:** separar aprovados, rejeitados, conflitos e lacunas no estado.
- **RF-08:** tratar ausência total de fatos aprovados sem fabricar conteúdo.
- **RF-09:** executar no máximo uma tentativa configurável de reparo.
- **RF-10:** preservar resultados parciais e falhas sanitizadas.
- **RF-11:** adicionar Validator e roteamento após o Classifier no grafo.
- **RF-12:** expor resultados na API e mapear erros HTTP.
- **RF-13:** resolver `llm_fast` pela política central.

## Requisitos não funcionais

- **RNF-01:** contratos imutáveis, estritos e sem campos extras.
- **RNF-02:** execução assíncrona, sequencial e com limites finitos.
- **RNF-03:** nenhuma dependência de banco, rede ou SDK concreto no agente.
- **RNF-04:** nenhuma mutação dos objetos recebidos ou memória global.
- **RNF-05:** testes determinísticos usam fakes e não chamam serviços externos.
- **RNF-06:** logs e erros não expõem dados, URLs ou credenciais.
- **RNF-07:** preservar UTF-8, UUIDs, URLs e ordem de entrada.
- **RNF-08:** manter Ruff, mypy, testes arquiteturais, cobertura mínima de 80% e
  regressão do frontend.

## Restrições

- Suporte documental não representa verdade factual definitiva.
- Somente `excerpt`s já recuperados podem ser analisados.
- Fontes não podem ser criadas, abertas ou enriquecidas.
- Agentes posteriores deverão usar as coleções `validated_*`.
- Nenhuma alteração no schema PostgreSQL é necessária.

## Fora do escopo

- Consultar internet, URLs, PostgreSQL, Qdrant ou base NVIDIA.
- Buscar documentos adicionais ou produzir novas evidências.
- Corrigir ou reescrever afirmações originais.
- Confirmar definitivamente fatos sobre a startup.
- Gerar recomendações ou implementar agentes posteriores.
- Persistir validações, streaming, paralelismo ou checkpoint.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-02, RF-05 | Testes de enumeração, cobertura total e identidade |
| US-02 | RF-03, RF-05 | Testes de classificação aprovada, incerta e rejeitada |
| US-03 | RF-04, RF-05, RNF-07 | Testes de referências, URLs, ordem e associação |
| US-04 | RF-06, RNF-04 | Testes de filtragem e preservação dos originais |
| US-05 | RF-07 | Testes das coleções separadas e justificativas |
| US-06 | RF-08 | Testes sem fatos aprovados e HTTP 200 |
| US-07 | RF-05, RF-09, RF-10, RNF-01 | Testes de parsing, reparo e falhas |
| US-08 | RF-11, RF-13, RNF-02 a RNF-06 | Testes de grafo, limites, modelo, métricas e logs |
| US-09 | RF-12, RNF-07, RNF-08 | Testes de API, OpenAPI, HTTP e suíte completa |
| US-10 | RF-10, RNF-03, RNF-04 | Testes de arquitetura e não mutação |

## Critério de conclusão

A feature estará concluída quando toda afirmação e classificação recebida tiver
resultado rastreável, somente fatos aprovados compuserem os perfis validados,
rejeições, conflitos e lacunas estiverem separados, o grafo encerrar corretamente
sem fatos sobreviventes, todos os testes passarem e a entrega receber aprovação
explícita.

## Sugestão de commit

`feat(validator): validate documentary support for startup claims`
