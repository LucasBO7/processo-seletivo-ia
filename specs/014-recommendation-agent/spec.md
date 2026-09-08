# Especificação 014: Recommendation Agent

## Status

Implementada e verificada em 8 de setembro de 2026; aguardando aprovação
explícita da entrega para conclusão formal.

## Contexto

O fluxo atual produz perfis e classificações validados e, quando existe entrada
utilizável, recupera contexto técnico oficial da base NVIDIA. Esse contexto já
preserva UUIDs, URLs, tecnologias e scores, mas ainda não é transformado em uma
ação adequada para a startup.

Esta funcionalidade adiciona o Recommendation Agent. O nó cruza necessidades e
gaps técnicos documentalmente sustentados com o perfil validado, a maturidade de
IA validada quando disponível e os trechos suficientes retornados pelo NVIDIA RAG.
Seu resultado deve explicar por que uma tecnologia se relaciona ao problema, qual
valor de negócio é sustentado pelos dados, como priorizá-la, qual a complexidade
esperada e qual próxima ação cabe ao time NVIDIA.

Uma recomendação não é um fato sobre a startup nem uma validação definitiva de
adequação. Ela é uma proposta rastreável, limitada pelas evidências disponíveis.
O nó não consulta internet, PostgreSQL, Qdrant ou BM25 diretamente e não gera o
briefing executivo.

## Objetivos

- Produzir recomendações NVIDIA ligadas a necessidades identificadas e validadas.
- Exigir simultaneamente evidência da startup e documentação oficial NVIDIA.
- Usar somente perfis, classificações, gaps e contextos presentes no `AppState`.
- Tornar prioridade e complexidade reproduzíveis por critérios estruturados.
- Rejeitar tecnologia incompatível, citação fabricada e recomendação duplicada.
- Preservar resultados parciais, avisos, erros sanitizados e métricas do nó.
- Expor saída estruturada e independente da apresentação do frontend.
- Executar depois do NVIDIA RAG apenas para startups elegíveis.
- Manter testes padrão determinísticos, offline e sem consumo de tokens.

## Elegibilidade e fontes de necessidade

Uma startup é elegível quando possui:

1. `ValidatedStartupProfile` utilizável;
2. `NvidiaStartupContext` da mesma startup com `status=sufficient`;
3. ao menos uma necessidade identificada e rastreável.

São necessidades identificadas:

- fatos de `validated_profiles[].technical_needs`; ou
- itens de `technical_gaps` cujos `evidence_ids` possam ser resolvidos em fontes
  aprovadas de `validated_claims` da mesma startup.

O agente não cria gaps novos. Um `TechnicalGap` sem evidência resolvível, associado
a outra startup ou sustentado somente por item rejeitado, conflitante ou
insuficiente é ignorado e gera aviso. Na ausência de `technical_gaps`, necessidades
técnicas explícitas do perfil validado continuam elegíveis. Sem ambos, o agente não
chama o modelo e não força recomendação.

A classificação em `validated_classifications` é usada quando corresponde à
startup. Sua ausência não bloqueia uma necessidade bem sustentada, porque o
roteamento solicitado depende de perfil e contexto suficiente; nesse caso, a saída
não pode fazer afirmações sobre maturidade e registra que ela não foi considerada.

## Critérios de prioridade

Cada candidato deve fornecer uma base estruturada validada antes que a prioridade
final seja calculada pelo código.

### Fatores

`need_criticality`:

- `blocker` = 2 pontos: evidência da startup declara bloqueio, requisito obrigatório,
  falha atual ou impedimento explícito;
- `important` = 1 ponto: necessidade concreta ligada a uma capacidade atual, sem
  evidência de bloqueio;
- `optimization` = 0 pontos: oportunidade de melhoria não obrigatória.

`business_relevance`:

- `core` = 1 ponto: produto, proposta de valor, caso de uso de IA ou operação central
  validada depende diretamente da necessidade;
- `supporting` = 0 pontos: benefício sustentado, porém secundário.

`evidence_strength` é derivado pelo agente, não pelo modelo:

- `corroborated` = 1 ponto: ao menos dois UUIDs distintos de documentos da startup
  sustentam a necessidade e sua relevância;
- `single_source` = 0 pontos: existe uma única fonte aprovada.

### Regra de cálculo

```text
priority_score = criticality_points + business_relevance_points + evidence_strength_points

0      → low
1 ou 2 → medium
3 ou 4 → high
```

`blocker` e `core` somente são aceitos quando as referências indicadas sustentam
explicitamente essas características. A prioridade retornada pelo modelo é apenas
uma proposta: o agente recalcula o valor e rejeita divergência.

## Critérios de complexidade

A complexidade também é calculada pelo código a partir de três fatores sustentados
pelo perfil e/ou pelos trechos NVIDIA citados.

`integration_scope`:

- `configuration_or_api` = 0 pontos;
- `single_component` = 1 ponto;
- `platform_or_migration` = 2 pontos.

`infrastructure_change`:

- `none` = 0 pontos;
- `moderate` = 1 ponto;
- `major` = 2 pontos.

`specialized_skills`:

- `standard` = 0 pontos;
- `specialized` = 1 ponto;
- `advanced` = 2 pontos.

```text
complexity_score = integration_scope_points
                 + infrastructure_change_points
                 + specialized_skills_points

0 ou 1 → low
2 ou 3 → medium
4 a 6 → high
```

Não conhecer a infraestrutura atual não autoriza classificar a implementação como
simples. Se os fatores não puderem ser sustentados dentro do contexto limitado, o
candidato não se torna recomendação válida. A complexidade representa estimativa
relativa para triagem, não cronograma, orçamento ou garantia de implantação.

## Histórias do usuário

### US-01 — Selecionar entradas elegíveis

Como pessoa analista, quero recomendações somente para startups com dados
validados e contexto técnico suficiente.

Critérios de aceite:

- O agente lê `validated_profiles`, `validated_classifications`, `validated_claims`,
  `technical_gaps` e `nvidia_contexts` do estado.
- Perfil e contexto são associados exclusivamente por `startup_id`.
- Somente contexto `sufficient`, com ao menos um chunk citável, é consumido.
- Necessidades derivam apenas das fontes descritas na seção de elegibilidade.
- Perfil sem necessidade nem gap elegível retorna lista vazia, aviso
  `recommendation_no_identified_need` e não chama o modelo.
- Contexto ausente ou insuficiente retorna lista vazia para a startup, aviso
  `recommendation_nvidia_context_insufficient` e não chama o modelo.
- Gap sem evidência aprovada retorna `recommendation_gap_untraceable` e não entra
  no prompt como fato.
- A ausência de classificação validada não bloqueia a execução, mas impede qualquer
  justificativa baseada em maturidade.

### US-02 — Gerar recomendação com relação explícita

Como time NVIDIA, quero entender qual tecnologia se relaciona a qual necessidade.

Critérios de aceite:

- Cada recomendação contém `startup_id`, tecnologia canônica, uma ou mais
  `need_keys`, justificativa técnica, justificativa de negócio, prioridade,
  complexidade e próxima ação sugerida.
- Cada `need_key` existe na allowlist construída pelo agente e pertence à startup.
- A justificativa técnica descreve a relação entre a capacidade documentada da
  tecnologia e a necessidade, sem afirmar implantação já realizada.
- A justificativa de negócio usa produto, modelo de negócio, público-alvo, caso de
  uso ou operação validada da startup; benefício genérico sem vínculo é inválido.
- A próxima ação é dirigida ao time NVIDIA e é limitada a descoberta técnica,
  validação de aderência, demonstração, workshop, prova de conceito ou encaminhamento
  apropriado; não promete resultado, contrato, preço ou prazo não evidenciado.
- A tecnologia usa exclusivamente `NvidiaTechnology` da base da spec 012.
- Uma tecnologia só é aceita se houver ao menos um chunk citado com exatamente a
  mesma tecnologia no contexto suficiente da startup.

### US-03 — Preservar evidência dupla

Como pessoa revisora, quero auditar tanto o diagnóstico da startup quanto a
capacidade NVIDIA usada na proposta.

Critérios de aceite:

- Toda recomendação contém ao menos uma `StartupRecommendationEvidence` e uma
  `NvidiaRecommendationEvidence`.
- A evidência da startup preserva `startup_id`, `source_id`, `source_url`, campo e
  valor validado relacionado.
- A fonte NVIDIA preserva `chunk_id`, `document_id`, título, tecnologia, URL oficial,
  seção/offsets e scores de recuperação.
- UUIDs e URLs devem corresponder exatamente às allowlists do perfil, das validações
  e do `NvidiaStartupContext`; o modelo não pode criar ou alterar referências.
- Fontes da startup e fontes NVIDIA permanecem em coleções distintas.
- Uma referência NVIDIA só sustenta a tecnologia registrada no próprio chunk.
- Ao menos uma evidência da startup sustenta a necessidade e ao menos uma sustenta
  a relevância de negócio; a mesma fonte pode cumprir ambos quando o texto validado
  efetivamente contiver as duas informações.

### US-04 — Calcular prioridade verificável

Como pessoa operadora, quero uma prioridade consistente para ordenar o trabalho.

Critérios de aceite:

- O candidato informa `need_criticality` e `business_relevance` com referências.
- O agente deriva `evidence_strength` pela quantidade de documentos distintos.
- O agente calcula `priority_score` e `priority` exatamente pela tabela desta spec.
- `blocker` sem afirmação explícita de bloqueio ou `core` sem evidência de relação
  central torna a saída semanticamente inválida.
- Empates de prioridade são resolvidos por score decrescente, complexidade crescente,
  tecnologia canônica e UUID da startup.
- A justificativa não pode apresentar `low`, `medium` ou `high` como certeza de ROI.

### US-05 — Calcular complexidade verificável

Como pessoa analista técnica, quero distinguir uma integração simples de uma
mudança de plataforma.

Critérios de aceite:

- O candidato informa os três fatores de complexidade e suas referências.
- O agente calcula `complexity_score` e `implementation_complexity` pela tabela.
- `configuration_or_api` exige fonte NVIDIA que descreva API, serviço gerenciado ou
  microserviço e nenhuma restrição validada incompatível.
- `platform_or_migration`, `major` ou `advanced` exige referência que sustente o
  escopo elevado; o agente não infere esses fatores apenas pelo nome da tecnologia.
- Ausência de informação suficiente para os fatores rejeita o candidato em vez de
  assumir baixa complexidade.
- O resultado não contém prazo, preço, dimensionamento de hardware ou esforço em
  pessoas sem que esses dados tenham sido fornecidos e validados.

### US-06 — Validar incompatibilidades e duplicatas

Como pessoa mantenedora, quero impedir recomendações incoerentes de avançarem.

Critérios de aceite:

- Há no máximo uma recomendação por tecnologia e startup; múltiplas necessidades
  compatíveis são agrupadas em `need_keys`.
- Tecnologia ausente do contexto, referência de outra startup, chunk de outra
  tecnologia, necessidade inexistente ou uso de evidência não aprovada invalida o lote.
- Uma recomendação incompatível com restrição explícita do perfil é inválida.
- Prioridade ou complexidade divergente do cálculo determinístico invalida o lote.
- Saída semanticamente inválida recebe a mesma tentativa limitada de reparo da saída
  estruturalmente inválida.
- Se o modelo retornar validamente zero recomendações, o agente registra
  `recommendation_no_compatible_match` e HTTP 200; ele não é obrigado a recomendar.
- Invalidade persistente não publica parte do lote daquela startup e gera erro
  sanitizado, preservando recomendações concluídas para startups anteriores.

### US-07 — Validar e reparar saída estruturada

Como pessoa desenvolvedora, quero impedir texto livre ou citações fabricadas no estado.

Critérios de aceite:

- Entrada e saída usam modelos Pydantic estritos, imutáveis e `extra="forbid"`.
- O modelo produz somente os campos sob sua responsabilidade; identidade, referências
  completas, `evidence_strength`, scores e ordenação são derivados pelo agente.
- Cada chamada processa uma startup e recebe somente o contexto limitado daquela empresa.
- Saída inválida recebe no máximo uma tentativa de reparo configurável, limitada a 1.
- O reparo contém schema compacto, códigos/UUIDs permitidos e saída inválida delimitada,
  sem repetir todo o contexto quando não for necessário.
- Saída ainda inválida gera `recommendation_invalid_output` e HTTP 502.
- Indisponibilidade do provedor gera `recommendation_unavailable` e HTTP 503.
- Erros não contêm prompt, resposta bruta, trechos, URLs privadas, chave, token ou stack trace.

### US-08 — Integrar ao grafo e à API

Como frontend, quero consumir recomendações rastreáveis no fluxo atual.

Critérios de aceite:

- O grafo mantém o fluxo atual até `nvidia_rag`.
- Depois de `nvidia_rag`, `route_after_nvidia_rag` encaminha ao Recommendation Agent
  somente quando existe um perfil validado utilizável e um contexto `sufficient`
  correspondente com chunks citáveis.
- Sem startup elegível, o fluxo termina em `END` sem chamar o Recommendation Agent.
- Após o Recommendation Agent, o fluxo termina em `END` nesta spec.
- O nó retorna patch parcial com recomendações, avisos, erros e métricas, sem apagar
  campos produzidos anteriormente.
- `POST /api/v1/search` expõe recomendações em contrato aditivo e independente de UI.
- UUIDs são serializados como strings, URLs preservadas e enums como valores canônicos.
- `/api/v1/query-plans` permanece inalterado.

### US-09 — Operar com limites, métricas e logs seguros

Como pessoa operadora, quero controlar custo e observar o comportamento do nó.

Critérios de aceite:

- O agente usa `ModelRegistry.resolve(NodeName.RECOMMENDATION)` e `llm_heavy`.
- Quantidade de recomendações, necessidades, evidências, chunks e caracteres de
  contexto possuem limites configuráveis.
- Truncamento é determinístico, preserva os itens de maior relevância já ordenados e
  adiciona `recommendation_context_truncated`.
- Métricas incluem duração, startups recebidas/elegíveis/processadas, startups
  ignoradas por motivo, necessidades, chunks, chamadas ao modelo, reparos, lotes
  inválidos, recomendações aceitas e falhas.
- Logs contêm somente nó, versão do prompt, status, duração e contagens.
- Logs e métricas não contêm perfil, gaps, consultas, prompts, respostas, trechos,
  justificativas, URLs, UUIDs de fonte ou segredos.

### US-10 — Testar sem serviços externos

Como pessoa mantenedora, quero validar regras e cenários do TAPI sem custo ou rede.

Critérios de aceite:

- Testes unitários usam `FakeChatModel` ou `SequenceChatModel` com JSON mínimo.
- Nenhum teste da suíte padrão usa LLM real, internet, banco, Qdrant, BM25, embedding
  ou reranker.
- Os prompts de teste usam somente o menor contexto necessário para cada cenário.
- Cenários representativos incluem startup AI-native com inferência, AI-enabled com
  integração por API, non-AI sem necessidade compatível, ausência de gaps, contexto
  NVIDIA insuficiente, duplicata, tecnologia incompatível e citação fabricada.
- A suíte padrão falha antes de criar cliente real, mesmo se houver credenciais no ambiente.
- Teste real de provedor, se existir, usa marca `external` e habilitação explícita.
- Ruff, mypy, import-linter, cobertura mínima de 80% e regressão do frontend permanecem verdes.

### US-11 — Preservar o limite da feature

Como pessoa mantenedora, quero uma saída analítica sem antecipar o briefing.

Critérios de aceite:

- O agente não gera narrativa executiva, resumo geral, PDF, apresentação ou conteúdo visual.
- O agente não reclassifica a startup, não valida fatos novamente e não cria gaps.
- O agente não consulta nem altera a base NVIDIA.
- O agente não transforma score de recuperação em garantia comercial ou técnica.
- O agente não persiste recomendações nem cria endpoint próprio nesta funcionalidade.

## Contratos conceituais

```text
RecommendationPriority
├── low
├── medium
└── high

ImplementationComplexity
├── low
├── medium
└── high

RecommendationNeed
├── key: string
├── kind: validated_technical_need | validated_technical_gap
├── description: string
└── startup_evidence_ids: list[UUID]

PriorityBasis
├── need_criticality: blocker | important | optimization
├── business_relevance: core | supporting
├── evidence_strength: corroborated | single_source  # derivado
├── priority_score: integer                           # derivado
└── evidence_ids: list[UUID]

ComplexityBasis
├── integration_scope: configuration_or_api | single_component | platform_or_migration
├── infrastructure_change: none | moderate | major
├── specialized_skills: standard | specialized | advanced
├── complexity_score: integer                         # derivado
└── nvidia_chunk_ids: list[UUID]

StartupRecommendationEvidence
├── startup_id: UUID
├── source_id: UUID
├── source_url: URL
├── field: ProfileField
└── value: string

NvidiaRecommendationEvidence
├── chunk_id: UUID
├── document_id: UUID
├── title: string
├── technology: NvidiaTechnology
├── source_url: URL
├── source_section: string | null
├── start_offset: integer | null
├── end_offset: integer | null
└── retrieval_scores: NvidiaRetrievalScores

StartupRecommendation
├── startup_id: UUID
├── startup_name: string
├── maturity_considered: AIMaturity | null
├── technology: NvidiaTechnology
├── need_keys: list[string]
├── technical_justification: string
├── business_justification: string
├── priority: RecommendationPriority
├── priority_basis: PriorityBasis
├── implementation_complexity: ImplementationComplexity
├── complexity_basis: ComplexityBasis
├── next_action: string
├── startup_evidence: list[StartupRecommendationEvidence]
└── nvidia_evidence: list[NvidiaRecommendationEvidence]
```

O modelo retorna identificadores permitidos e fatores propostos. O agente resolve
as referências completas a partir do estado, deriva força de evidência, calcula
prioridade/complexidade e copia `startup_id`, nome e maturidade. Nenhuma URL, UUID,
score ou identidade fornecida pelo modelo é aceita diretamente.

## Política de contexto e prompt

O prompt contém somente:

- fatos de `ValidatedStartupProfile` dentro dos limites;
- classificação validada correspondente, se existir;
- necessidades elegíveis com chaves atribuídas pelo agente;
- chunks do contexto `sufficient`, na ordem produzida pelo NVIDIA RAG;
- IDs curtos necessários para a saída e regras compactas do schema.

Conteúdo rejeitado, conflitante, insuficiente, resultados NVIDIA abaixo do limiar e
dados de outras startups não entram. Trechos são delimitados e tratados como dados,
nunca como instruções. O modelo pode retornar zero candidatos.

## Códigos e avisos mínimos

| Identificador | Tipo | Situação |
| --- | --- | --- |
| `recommendation_no_eligible_startups` | aviso | Nenhum perfil possui contexto suficiente correspondente |
| `recommendation_no_identified_need` | aviso | Startup não possui necessidade ou gap elegível |
| `recommendation_gap_untraceable` | aviso | Gap não pôde ser ligado a evidência aprovada da startup |
| `recommendation_nvidia_context_insufficient` | aviso | Contexto NVIDIA ausente, insuficiente ou sem chunks citáveis |
| `recommendation_classification_unavailable` | aviso | Maturidade validada não está disponível |
| `recommendation_business_context_insufficient` | aviso | Não há fato aprovado para justificar valor de negócio |
| `recommendation_context_truncated` | aviso | Entrada excedeu limites configurados |
| `recommendation_no_compatible_match` | aviso | Modelo retornou validamente zero recomendações |
| `recommendation_invalid_output` | erro | Lote permaneceu estrutural ou semanticamente inválido após reparo |
| `recommendation_unavailable` | erro | Provedor não conseguiu produzir o lote |

Avisos retornam HTTP 200. `recommendation_invalid_output` retorna 502 e
`recommendation_unavailable` retorna 503. Todas as mensagens externas são sanitizadas.

## Métricas mínimas

- `recommendation_duration_ms`;
- `recommendation_input_startup_count`;
- `recommendation_eligible_startup_count`;
- `recommendation_processed_startup_count`;
- `recommendation_skipped_no_need_count`;
- `recommendation_skipped_context_count`;
- `recommendation_skipped_business_context_count`;
- `recommendation_need_count`;
- `recommendation_nvidia_chunk_count`;
- `recommendation_model_call_count`;
- `recommendation_repair_count`;
- `recommendation_invalid_batch_count`;
- `recommendation_accepted_count`;
- `recommendation_failure_count`.

## Configuração mínima

```text
RECOMMENDATION__MAX_RECOMMENDATIONS_PER_STARTUP
RECOMMENDATION__MAX_NEEDS_PER_STARTUP
RECOMMENDATION__MAX_STARTUP_EVIDENCE
RECOMMENDATION__MAX_NVIDIA_CHUNKS
RECOMMENDATION__MAX_CONTEXT_CHARACTERS
RECOMMENDATION__MAX_JUSTIFICATION_LENGTH
RECOMMENDATION__MAX_NEXT_ACTION_LENGTH
RECOMMENDATION__MAX_REPAIR_ATTEMPTS
```

Os limites possuem faixas conservadoras. `MAX_REPAIR_ATTEMPTS` aceita somente 0 ou
1. Configuração inválida impede o startup da aplicação com erro sanitizado.

## Requisitos funcionais

- **RF-01:** selecionar e associar entradas elegíveis por startup.
- **RF-02:** resolver necessidades e gaps somente a partir de fatos aprovados.
- **RF-03:** construir contexto isolado, limitado e rastreável.
- **RF-04:** gerar candidatos estruturados pelo modelo pesado configurado.
- **RF-05:** exigir relação explícita entre tecnologia e necessidade.
- **RF-06:** exigir evidências da startup e da base NVIDIA em cada recomendação.
- **RF-07:** calcular prioridade determinística conforme fatores validados.
- **RF-08:** calcular complexidade determinística conforme fatores validados.
- **RF-09:** rejeitar duplicatas, incompatibilidades e referências fora da allowlist.
- **RF-10:** reparar saída inválida no máximo uma vez e sanitizar falhas.
- **RF-11:** preservar resultados parciais, avisos, erros e métricas.
- **RF-12:** estender `AppState`, LangGraph e `/api/v1/search` de forma aditiva.
- **RF-13:** não gerar briefing nem consultar serviços de recuperação.

## Requisitos não funcionais

- **RNF-01:** contratos estritos, imutáveis e sem campos extras.
- **RNF-02:** execução assíncrona, sequencial por startup e com limites finitos.
- **RNF-03:** nenhuma dependência concreta de Groq na aplicação ou no domínio.
- **RNF-04:** determinismo na validação, nos cálculos e na ordenação final.
- **RNF-05:** isolamento absoluto entre startups.
- **RNF-06:** logs, métricas e erros não expõem conteúdo ou segredos.
- **RNF-07:** testes padrão não usam rede, banco, LLM ou serviços pagos.
- **RNF-08:** preservar UTF-8, UUIDs, URLs e enums canônicos.
- **RNF-09:** manter Ruff, mypy, import-linter, cobertura mínima de 80% e frontend verde.
- **RNF-10:** manter compatibilidade HTTP por adição de campos.

## Alterações de estado, grafo e API previstas

`AppState.recommendations` passará a usar `list[StartupRecommendation]` em vez do
modelo de domínio genérico criado na fundação. `empty_state` continuará iniciando
uma lista vazia. Não haverá migração de banco.

O grafo será estendido assim:

```text
evidence_validator
  → nvidia_rag
      → route_after_nvidia_rag
          ├── perfil utilizável + contexto sufficient → recommendation → END
          └── nenhuma startup elegível                → END
```

`POST /api/v1/search` incluirá `recommendations`. Nenhum endpoint separado será
criado e os campos atuais permanecerão inalterados.

## Restrições

- Nenhum item rejeitado, conflitante ou insuficiente pode virar premissa.
- Nenhuma tecnologia ausente do contexto suficiente pode ser recomendada.
- Toda recomendação exige evidência dupla e necessidade explícita.
- Scores de recuperação auxiliam seleção, mas não provam adequação final.
- Conteúdo recuperado é dado não confiável e não pode alterar instruções do agente.
- O agente não consulta fontes ou adaptadores externos além de `ChatModel`.
- Nenhuma credencial, prompt ou resposta bruta entra no estado ou nos logs.

## Fora do escopo

- Briefing executivo, relatório, PDF, apresentação ou visualização.
- Persistência ou histórico de recomendações.
- Nova classificação, validação factual ou geração de gaps.
- Consulta direta a PostgreSQL, Qdrant, BM25, internet ou URLs.
- Ingestão ou atualização da base NVIDIA.
- Estimativa de preço, prazo, hardware, equipe ou retorno financeiro.
- Contato real com startup ou envio de mensagem pelo sistema.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-02 | Testes de elegibilidade, associação, ausência e gaps sem fonte |
| US-02 | RF-04, RF-05 | Cenários de necessidade, tecnologia e próxima ação |
| US-03 | RF-03, RF-06, RNF-05, RNF-08 | Allowlist dupla, IDs, URLs, startup e tecnologia |
| US-04 | RF-07, RNF-04 | Testes tabulares de fatores, scores, níveis e desempates |
| US-05 | RF-08, RNF-04 | Testes tabulares de complexidade e evidência dos fatores |
| US-06 | RF-09 a RF-11 | Duplicatas, incompatibilidades, vazio válido, reparo e parcial |
| US-07 | RF-04, RF-09, RF-10, RNF-01, RNF-03 | Schema, parse, reparo e falhas sanitizadas |
| US-08 | RF-11, RF-12, RNF-10 | Estado, grafo, API, HTTP e OpenAPI |
| US-09 | RF-03, RF-11, RNF-02, RNF-06 | Limites, métricas, truncamento e logs |
| US-10 | RNF-07, RNF-09 | Fakes mínimos, cenários TAPI, cobertura e regressão |
| US-11 | RF-13 | Testes arquiteturais e inspeção de escopo |

## Critério de conclusão

A feature estará concluída quando recomendações elegíveis relacionarem necessidade,
tecnologia e evidência dupla; prioridade e complexidade forem recalculadas pelas
regras desta spec; incompatibilidades e duplicatas forem bloqueadas; ausência e
falhas tiverem comportamento previsível; o grafo e a API estiverem estendidos; os
testes offline, qualidade e regressões passarem; e a entrega receber aprovação explícita.

## Sugestão de commit

`feat(recommendation): generate grounded NVIDIA recommendations`
