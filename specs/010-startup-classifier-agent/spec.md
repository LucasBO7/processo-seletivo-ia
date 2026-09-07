# Especificação 010: Startup Classifier Agent

## Status

Implementada e verificada em 7 de setembro de 2026; aguarda aprovação explícita
da entrega para conclusão formal.

## Contexto

O fluxo atual transforma a consulta em plano, recupera startups e documentos no
PostgreSQL e usa o Extractor para produzir `structured_profiles` rastreáveis. A
próxima etapa precisa interpretar esses perfis e suas evidências para indicar o
papel da inteligência artificial em cada startup.

A classificação não pode usar conhecimento do modelo sobre a empresa, navegar
URLs ou transformar ausência de informação em certeza. Em particular, não
encontrar um sinal de IA não basta para classificar uma startup como `non-ai`.

## Objetivos

- Implementar o Startup Classifier Agent como nó assíncrono e testável.
- Classificar cada perfil como `ai-native`, `ai-enabled` ou `non-ai` quando as
  evidências sustentarem a conclusão.
- Produzir resultado incerto quando os dados forem insuficientes ou conflitantes.
- Preservar justificativa, confiança, sinais considerados e referências.
- Usar somente `structured_profiles` e `selected_sources` presentes no estado.
- Executar o Classifier após o Extractor somente quando existir perfil válido.
- Expor as classificações na resposta existente de `/api/v1/search`.

## Taxonomia de classificação

### `ai-native`

A IA é parte indispensável do produto ou da proposta de valor principal. O
produto perderia sua função central ou deixaria de entregar o resultado descrito
sem o componente de IA.

Sinais aceitáveis incluem:

- produto explicitamente apresentado como modelo, agente ou plataforma de IA;
- caso de uso de IA diretamente responsável pela função principal do produto;
- afirmação explícita de que inferência, treinamento, visão computacional,
  processamento de linguagem ou outra capacidade de IA constitui o núcleo da
  solução.

A simples menção a uma tecnologia, API, tendência ou intenção futura não é
suficiente. Uma classificação `ai-native` exige ao menos um sinal sustentado de
dependência central de IA.

### `ai-enabled`

A startup possui produto ou operação identificável e usa IA como recurso,
automação, otimização ou componente relevante, mas as evidências não demonstram
que a proposta de valor principal depende integralmente dela.

Sinais aceitáveis incluem:

- funcionalidade de IA adicionada a um produto mais amplo;
- IA usada para recomendação, previsão, automação, personalização ou eficiência;
- uso interno ou operacional de IA que não define sozinho o produto principal.

Uma classificação `ai-enabled` exige ao menos um uso concreto e sustentado de IA.
Menções genéricas ou planos futuros sem uso atual identificado geram incerteza.

### `non-ai`

As evidências sustentam positivamente que a solução ou operação analisada não usa
IA. Essa categoria não pode ser inferida apenas porque `ai_use_cases` ou
`technologies` estão vazios.

Sinais aceitáveis incluem declaração explícita de ausência de IA ou descrição
inequívoca e sustentada de que a capacidade analisada usa abordagem não baseada
em IA. Havendo apenas silêncio, documentação incompleta ou dúvida terminológica,
o resultado deve ser incerto.

## Resultado incerto

O resultado usa `status=uncertain` e `category=null` quando:

- não há fatos ou trechos suficientes para aplicar os critérios;
- existem somente menções genéricas, aspiracionais ou futuras a IA;
- sinais sustentam categorias incompatíveis sem base para resolver o conflito;
- não é possível distinguir se a IA é central ou apenas habilitadora;
- não há sinal de IA, mas também não há evidência positiva para `non-ai`.

Incerteza não é uma quarta categoria de maturidade. É o estado que impede o
sistema de fabricar uma das três classificações solicitadas.

## Histórias do usuário

### US-01 — Classificar perfis com critérios explícitos

Como pessoa analista, quero uma categoria consistente para entender o papel da
IA na startup.

Critérios de aceite:

- O agente recebe `structured_profiles` e `selected_sources` do `AppState`.
- Cada perfil válido gera exatamente um `StartupClassification` na mesma ordem.
- `status=classified` exige `category` igual a `ai-native`, `ai-enabled` ou
  `non-ai`.
- `status=uncertain` exige `category=null`.
- `ai-native`, `ai-enabled` e `non-ai` obedecem aos critérios documentados nesta
  especificação.
- Identidade e nome da startup são copiados do perfil pelo agente e não podem ser
  substituídos pela saída do modelo.
- A atualização retornada pelo nó é parcial e não remove outros campos do estado.

### US-02 — Justificar com sinais e evidências

Como pessoa usuária, quero compreender por que uma categoria foi escolhida.

Critérios de aceite:

- Toda classificação contém justificativa objetiva, nível de confiança e lista
  de sinais considerados.
- `ConfidenceLevel` aceita somente `low`, `medium` ou `high`.
- Cada sinal possui tipo canônico, descrição curta e ao menos uma referência.
- Tipos de sinal incluem dependência central de IA, uso habilitador de IA,
  evidência explícita de não uso, menção futura ou genérica e conflito.
- Toda referência preserva `startup_id`, `source_id` e `source_url`.
- UUID, URL e associação da startup são validados contra `selected_sources`.
- O agente considera somente fatos do perfil e o texto dos `excerpt`s associados
  à mesma startup.
- Fontes de startups diferentes nunca são misturadas.
- A ordem e a deduplicação das referências acompanham `selected_sources`.

### US-03 — Sinalizar insuficiência e conflito

Como pessoa analista, quero ver incerteza quando não houver base confiável para
uma conclusão.

Critérios de aceite:

- Perfil sem fatos sustentados produz resultado incerto determinístico, sem
  chamar o modelo.
- Ausência de sinal de IA, isoladamente, nunca produz `non-ai`.
- Menções exclusivamente futuras ou genéricas produzem resultado incerto.
- Evidências conflitantes produzem resultado incerto e incluem sinal de conflito.
- Resultado incerto usa confiança `low`, justificativa objetiva e pode ter lista
  vazia de referências somente quando não existe evidência utilizável.
- O aviso `classifier_uncertain` é adicionado quando ao menos um perfil não pode
  ser classificado com segurança.
- Nenhum dado ausente é completado por conhecimento presumido.

### US-04 — Validar e reparar a saída

Como pessoa mantenedora, quero impedir classificações ou citações fabricadas no
estado compartilhado.

Critérios de aceite:

- A saída do modelo usa contratos Pydantic estritos, imutáveis e sem campos
  extras.
- A coerência entre status, categoria, confiança e tipos de sinal é validada.
- `ai-native` exige sinal `core_ai_dependency`.
- `ai-enabled` exige sinal `supporting_ai_use`.
- `non-ai` exige sinal `explicit_non_ai`.
- Toda referência da saída é validada contra a allowlist da startup.
- Saída inválida recebe no máximo uma tentativa configurável de reparo.
- O reparo recebe o schema, referências permitidas e saída inválida delimitada,
  sem credenciais ou detalhes internos do provedor.
- Invalidade persistente gera `classifier_invalid_output` sanitizado.
- Indisponibilidade do modelo gera `classifier_unavailable` sanitizado.
- Classificações concluídas antes de uma falha permanecem no estado.

### US-05 — Orquestrar o Classifier

Como pessoa operadora, quero que o grafo execute somente nós que possuem entrada
apropriada.

Critérios de aceite:

- O grafo mantém Query Planner → Retriever → Extractor.
- Após o Extractor, `route_after_extractor` encaminha ao Classifier somente se
  houver ao menos um `StructuredStartupProfile` válido.
- Sem perfil, o fluxo termina em `END` sem chamar o Classifier.
- Após o Classifier, o fluxo termina em `END` nesta entrega.
- O roteamento é puro e não chama modelo, banco ou serviço externo.
- O endpoint isolado `/api/v1/query-plans` permanece inalterado.

### US-06 — Operar com limites e métricas

Como pessoa operadora, quero observar custo e falhas sem expor conteúdo.

Critérios de aceite:

- O Classifier usa `ModelRegistry.resolve(NodeName.STARTUP_CLASSIFIER)` e o perfil
  `llm_heavy` definido na política central.
- Cada chamada ao modelo processa uma startup e suas fontes associadas.
- Quantidade de fontes, caracteres de contexto, tamanho da justificativa, sinais
  e reparos possuem limites configuráveis e validados.
- Truncamento adiciona `classifier_context_truncated`.
- Métricas incluem duração, perfis recebidos, perfis processados, classificações,
  resultados incertos, fontes utilizadas, chamadas ao modelo, reparos e falhas.
- Logs contêm somente nó, versão do prompt, status, duração e contagens.
- Perfis, excerpts, prompts, respostas, consultas, URLs e segredos não são
  registrados.

### US-07 — Disponibilizar classificações para o frontend

Como frontend, quero consumir a classificação e suas evidências na busca atual.

Critérios de aceite:

- `POST /api/v1/search` inclui `classifications` na resposta.
- UUIDs são serializados como strings e URLs permanecem inalteradas.
- Resultados incertos retornam HTTP 200 com aviso.
- `classifier_invalid_output` retorna HTTP 502.
- `classifier_unavailable` retorna HTTP 503.
- O OpenAPI descreve status, categorias, confiança, sinais e referências.

### US-08 — Preservar responsabilidades dos agentes

Como pessoa mantenedora, quero que a classificação não altere dados produzidos
por outros nós.

Critérios de aceite:

- O Classifier não remove nem reescreve fatos de `structured_profiles`.
- O Classifier não valida definitivamente a veracidade das afirmações.
- O Classifier não consulta PostgreSQL, Qdrant, internet ou base NVIDIA.
- O Classifier não recomenda produtos ou tecnologias NVIDIA.
- O Classifier depende somente da abstração `ChatModel`.

## Contratos conceituais

```text
ClassificationStatus
├── classified
└── uncertain

ConfidenceLevel
├── low
├── medium
└── high

ClassificationSignalType
├── core_ai_dependency
├── supporting_ai_use
├── explicit_non_ai
├── generic_ai_mention
├── future_ai_intent
└── conflicting_evidence

ClassificationSignal
├── type: ClassificationSignalType
├── description: string
└── sources: list[ExtractionSource] (mínimo 1)

ClassifierOutput
├── status: ClassificationStatus
├── category: AIMaturity | null
├── justification: string
├── confidence: ConfidenceLevel
└── signals: list[ClassificationSignal]

StartupClassification
├── startup_id: UUID
├── name: string
├── status: ClassificationStatus
├── category: AIMaturity | null
├── justification: string
├── confidence: ConfidenceLevel
├── signals: list[ClassificationSignal]
└── evidence_references: list[ExtractionSource]
```

`evidence_references` é derivado e ordenado pelo agente a partir das referências
dos sinais. O modelo não define `startup_id`, nome ou essa lista agregada.

## Fluxo do grafo

```text
START
  ↓
query_planner
  ↓ ready
retriever
  ↓ candidatos + fontes apropriadas
extractor
  ↓ route_after_extractor
  ├── ao menos um perfil válido → startup_classifier → END
  └── nenhum perfil válido ───────────────────────────→ END
```

Os encerramentos já definidos após Query Planner e Retriever permanecem
inalterados.

## Códigos e avisos

| Identificador | Tipo | Situação |
| --- | --- | --- |
| `classifier_uncertain` | aviso | Ao menos um perfil teve resultado incerto |
| `classifier_context_truncated` | aviso | Fontes ou contexto excederam o limite |
| `classifier_invalid_output` | erro | Saída continuou inválida após reparo |
| `classifier_unavailable` | erro | Modelo não conseguiu concluir a classificação |

## Requisitos funcionais

- **RF-01:** definir contratos estritos de classificação, confiança e sinais.
- **RF-02:** implementar critérios explícitos para as três categorias.
- **RF-03:** representar insuficiência ou conflito sem forçar categoria.
- **RF-04:** construir contexto isolado com perfil e excerpts da mesma startup.
- **RF-05:** preservar referências e validar sua associação contra as fontes.
- **RF-06:** validar coerência semântica mínima entre categoria e sinais.
- **RF-07:** executar no máximo uma tentativa configurável de reparo.
- **RF-08:** preservar resultados parciais e emitir falhas sanitizadas.
- **RF-09:** atualizar somente classificações, avisos, erros e métricas.
- **RF-10:** adicionar Classifier e roteamento posterior ao Extractor no grafo.
- **RF-11:** expor classificações em `/api/v1/search` e mapear erros HTTP.
- **RF-12:** resolver o modelo pela política central existente.

## Requisitos não funcionais

- **RNF-01:** contratos imutáveis, estritos e sem campos extras.
- **RNF-02:** execução assíncrona, sequencial e com limites finitos.
- **RNF-03:** nenhuma dependência de adaptador concreto ou serviço externo.
- **RNF-04:** nenhuma memória global ou estado compartilhado entre invocações.
- **RNF-05:** testes determinísticos usam fakes e não chamam Groq ou banco.
- **RNF-06:** logs e erros não expõem conteúdo ou credenciais.
- **RNF-07:** preservar UTF-8, UUIDs, URLs e ordem das startups.
- **RNF-08:** manter Ruff, mypy, testes arquiteturais, cobertura mínima de 80% e
  regressão do frontend.

## Restrições

- LangGraph permanece responsável pelo encadeamento.
- O agente usa somente o estado recebido.
- Evidências são suporte para classificação, não validação factual definitiva.
- A ordem de `structured_profiles` determina a ordem das classificações.
- Nenhuma alteração no schema PostgreSQL é necessária.

## Fora do escopo

- Remover, corrigir ou reescrever afirmações do Extractor.
- Validar definitivamente evidências ou atribuir veracidade factual.
- Consultar base NVIDIA, Qdrant, PostgreSQL, internet ou URLs.
- Recomendar tecnologias ou produtos NVIDIA.
- Implementar Evidence Validator ou agentes posteriores.
- Persistir classificações, streaming, paralelismo ou checkpoint.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01 a RF-03, RF-09 | Testes de categorias, identidade, ordem e estado parcial |
| US-02 | RF-04 a RF-06, RNF-07 | Testes de sinais, referências, agrupamento e deduplicação |
| US-03 | RF-02, RF-03, RNF-05 | Testes de insuficiência, silêncio, futuro e conflito |
| US-04 | RF-05 a RF-08, RNF-01 | Testes de contrato, allowlist, reparo e falhas |
| US-05 | RF-10 | Testes de topologia, roteamento e encerramento |
| US-06 | RF-04, RF-09, RF-12, RNF-02 a RNF-06 | Testes de limites, modelo, métricas e logs |
| US-07 | RF-10, RF-11, RNF-07, RNF-08 | Testes de API, OpenAPI, HTTP e suíte completa |
| US-08 | RF-09, RNF-03 | Testes de preservação e arquitetura |

## Critério de conclusão

A feature estará concluída quando o Classifier produzir resultados rastreáveis e
coerentes para todos os perfis, sinalizar incerteza sem forçar categoria, executar
somente após perfis válidos, preservar o estado anterior, expor o contrato pela
API, passar todas as verificações e receber aprovação explícita da entrega.

## Sugestão de commit

`feat(classifier): classify structured startup profiles from evidence`

## Evolução posterior

A especificação 011 substitui o encerramento direto pelo Evidence Validator. Os
perfis e classificações originais permanecem para auditoria, enquanto agentes
posteriores passam a consumir somente as coleções `validated_*`.
