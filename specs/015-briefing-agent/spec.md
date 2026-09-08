# Especificação 015: Briefing Agent

## Status

Aprovada para implementação em 8 de setembro de 2026 pelo pedido explícito da
funcionalidade.

## Contexto

O fluxo atual encerra após gerar recomendações NVIDIA rastreáveis. O gerente de
Startups & VCs da NVIDIA no Brasil ainda precisa reunir manualmente perfil,
maturidade, evidências, gaps e recomendações para preparar uma conversa executiva.

Esta funcionalidade adiciona o Briefing Agent. Ele consolida somente dados já
validados no `AppState`, produz um contrato estruturado por startup e renderiza uma
representação Markdown equivalente. Não exporta PDF, apresentação ou interface.

## Objetivos

- Consolidar informações úteis à atuação do gerente de Startups & VCs no Brasil.
- Distinguir fatos confirmados, inferências suportadas, incertezas e lacunas.
- Preservar citações exatas da startup e da base oficial NVIDIA.
- Impedir fatos, tecnologias, fontes e conclusões não presentes nas allowlists.
- Produzir saída estruturada e Markdown determinístico, independentes do frontend.
- Tratar dados parciais, recomendações vazias e falhas sem perder resultados válidos.
- Manter testes offline, determinísticos e sem consumo de tokens.

## Elegibilidade

Uma startup é elegível quando possui ao menos uma `StartupRecommendation` válida.
Perfil, classificação e contexto NVIDIA correspondentes enriquecem o briefing, mas
sua ausência não autoriza invenção e deve aparecer em `missing_sections`.

O grafo chama o Briefing Agent somente quando `recommendations` contém ao menos um
item estruturalmente válido. Invocação direta sem recomendações retorna lista vazia,
aviso `briefing_no_recommendations` e não chama o modelo.

## Histórias do usuário

### US-01 — Consolidar fatos e decisões

Como gerente de Startups & VCs, quero um briefing por startup para preparar a
próxima interação com contexto verificável.

Critérios de aceite:

- O briefing contém identificação, resumo do negócio, maturidade de IA, sinais,
  stack, gaps, recomendações NVIDIA, prioridades, complexidades e próximas ações.
- Identidade e seções factuais são copiadas de perfis, classificações, gaps e
  recomendações associados exclusivamente pelo mesmo `startup_id`.
- Campos ausentes produzem seções vazias e valores em `missing_sections`; não são
  preenchidos por conhecimento externo ou suposição do modelo.
- Recomendações preservam tecnologia, justificativas, prioridade, complexidade e
  próxima ação sem recalcular ou alterar a decisão da spec 014.

### US-02 — Distinguir natureza das conclusões

Como pessoa revisora, quero diferenciar fatos, inferências, incertezas e lacunas.

Critérios de aceite:

- Toda declaração narrativa possui `kind`: `confirmed_fact`,
  `supported_inference`, `uncertainty` ou `gap`.
- Fatos confirmados usam somente citações da startup e repetem ou resumem conteúdo
  validado sem mudar seu sentido.
- Inferências suportadas exigem simultaneamente ao menos uma citação da startup e
  uma citação NVIDIA.
- Incertezas e lacunas não são apresentadas como fatos nem como impedimentos certos.
- Linguagem de garantia, certeza de ROI, contrato, preço ou prazo não evidenciado é
  semanticamente inválida.

### US-03 — Preservar citações rastreáveis

Como pessoa auditora, quero abrir a fonte de cada conclusão.

Critérios de aceite:

- Citações da startup preservam `startup_id`, `source_id`, URL, campos e valores
  validados relacionados.
- Citações NVIDIA preservam `chunk_id`, `document_id`, tecnologia, título, URL,
  seção/offsets e scores de recuperação.
- O modelo seleciona somente `citation_id`; referências completas são resolvidas
  pelo agente a partir do estado.
- Todo item narrativo possui uma ou mais citações válidas.
- UUID, URL, tecnologia ou score fabricado invalida o lote da startup.
- Citações da startup e NVIDIA permanecem em coleções distintas.

### US-04 — Sinalizar oportunidades NVIDIA Inception

Como gerente, quero identificar oportunidades possíveis de relacionamento com o
NVIDIA Inception sem transformar possibilidade em elegibilidade confirmada.

Critérios de aceite:

- Uma oportunidade Inception é sempre `supported_inference`.
- Exige ao menos uma citação da startup e um chunk oficial cuja tecnologia seja
  exatamente `nvidia_inception` no contexto NVIDIA da mesma startup.
- Sem chunk Inception citável, a seção fica vazia, registra
  `briefing_inception_context_unavailable` e não pede ao modelo que invente a seção.
- O texto não promete ingresso, benefício, aprovação ou elegibilidade no programa.

### US-05 — Gerar Markdown equivalente

Como pessoa usuária, quero uma versão textual pronta para futura exportação.

Critérios de aceite:

- Cada briefing contém `markdown` gerado deterministicamente pelo código.
- O Markdown representa todas as seções estruturadas sem acrescentar conclusões.
- Citações usam marcadores estáveis e uma seção final de fontes com URLs exatas.
- Conteúdo textual é escapado ou normalizado para não criar estrutura arbitrária.
- A ordem é estável: identificação, negócio, IA e sinais, stack, gaps,
  recomendações, Inception, síntese, incertezas/lacunas e fontes.

### US-06 — Validar e reparar saída do modelo

Como pessoa desenvolvedora, quero impedir narrativa livre ou citações inventadas.

Critérios de aceite:

- Contratos são Pydantic estritos, imutáveis e `extra="forbid"`.
- Cada chamada processa uma startup e recebe apenas seu contexto limitado.
- A saída do modelo contém somente declarações narrativas e `citation_id` permitidos.
- Saída estrutural ou semanticamente inválida recebe no máximo uma tentativa de
  reparo configurável, limitada a 1.
- Invalidade persistente gera `briefing_invalid_output` e HTTP 502.
- Indisponibilidade do provedor gera `briefing_unavailable` e HTTP 503.
- Erros não contêm prompt, resposta bruta, trechos, URLs privadas ou segredos.

### US-07 — Tratar dados parciais e resultados parciais

Como pessoa operadora, quero preservar briefings válidos quando outra startup falhar.

Critérios de aceite:

- Recomendações de uma startup são agrupadas em um único briefing.
- Ausência de perfil, classificação, stack, gaps ou sinais não invalida
  recomendações já válidas; a ausência é registrada em `missing_sections`.
- Gap sem evidência resolvível é omitido e gera `briefing_citation_unavailable`.
- Falha de uma startup não apaga briefings concluídos anteriormente.
- O lote de declarações do modelo é atômico por startup.

### US-08 — Integrar ao grafo e à API

Como frontend, quero consumir briefing estruturado e Markdown no fluxo existente.

Critérios de aceite:

- `route_after_recommendation` encaminha ao Briefing Agent somente se houver ao
  menos uma recomendação válida.
- Sem recomendação, o fluxo termina em `END` sem chamar o Briefing Agent.
- Depois do Briefing Agent, o fluxo termina em `END`.
- O nó retorna patch parcial com `briefings`, avisos, erros e métricas.
- `POST /api/v1/search` expõe `briefings` de forma aditiva; endpoints existentes
  permanecem inalterados.

### US-09 — Operar com limites e logs seguros

Como pessoa operadora, quero controlar custo e observar a execução sem expor dados.

Critérios de aceite:

- O agente usa `ModelRegistry.resolve(NodeName.BRIEFING)` e `llm_heavy`.
- Startups, fatos, sinais, gaps, recomendações, citações, declarações, caracteres de
  contexto e Markdown possuem limites configuráveis.
- Truncamento determinístico preserva a ordem existente e adiciona
  `briefing_context_truncated`.
- Métricas incluem duração, entradas, elegíveis, processadas, chamadas, reparos,
  itens, briefings aceitos, truncamentos e falhas.
- Logs contêm somente nó, versão do prompt, status, duração e contagens.

### US-10 — Testar sem serviços externos

Como pessoa mantenedora, quero validar o briefing sem rede ou tokens.

Critérios de aceite:

- Testes usam `FakeChatModel` ou `SequenceChatModel` com JSON mínimo.
- A suíte padrão não usa LLM real, internet, banco, Qdrant, embedding ou reranker.
- Cenários cobrem sucesso completo, dados parciais, recomendações vazias, citação
  fabricada, Inception com/sem fonte, reparo, falha e preservação parcial.
- Roteamento, API, OpenAPI, Markdown, sanitização e limites são testados.
- Ruff, mypy, import-linter, cobertura mínima de 80% e frontend permanecem verdes.

### US-11 — Preservar o limite da feature

Como pessoa mantenedora, quero gerar o conteúdo sem antecipar exportação visual.

Critérios de aceite:

- Não há PDF, PowerPoint, imagem, template visual ou alteração de frontend.
- O agente não pesquisa, não recupera novos documentos, não reclassifica, não cria
  gaps, não altera recomendações e não persiste briefings.
- Não existe endpoint próprio; o resultado integra somente `/api/v1/search`.

## Contratos conceituais

```text
BriefingStatementKind = confirmed_fact | supported_inference | uncertainty | gap

BriefingStatement
├── kind
├── text
└── citation_ids: list[string]

BriefingStartupCitation
├── citation_id
├── startup_id
├── source_id
├── source_url
├── fields: list[ProfileField]
└── values: list[string]

BriefingNvidiaCitation
├── citation_id
├── chunk_id
├── document_id
├── technology
├── title
├── source_url
├── locator
└── retrieval_scores

StartupBriefing
├── startup_id
├── startup_name
├── business_facts
├── ai_maturity
├── classification_signals
├── identified_stack
├── technical_gaps
├── recommendations
├── executive_summary
├── inception_opportunities
├── uncertainties_and_gaps
├── startup_citations
├── nvidia_citations
├── missing_sections
└── markdown
```

## Códigos mínimos

| Código | Tipo | Situação |
| --- | --- | --- |
| `briefing_no_recommendations` | aviso | Não há recomendação elegível |
| `briefing_profile_unavailable` | aviso | Perfil validado não existe |
| `briefing_classification_unavailable` | aviso | Maturidade validada não existe |
| `briefing_citation_unavailable` | aviso | Item parcial não possui fonte resolvível |
| `briefing_inception_context_unavailable` | aviso | Não há chunk oficial Inception citável |
| `briefing_context_truncated` | aviso | O contexto excedeu limites |
| `briefing_invalid_output` | erro | Saída permaneceu inválida após reparo |
| `briefing_unavailable` | erro | Provedor não produziu o lote |

Avisos retornam HTTP 200; erros mapeiam respectivamente para 502 e 503.

## Configuração mínima

```text
BRIEFING__MAX_STARTUPS
BRIEFING__MAX_FACTS_PER_SECTION
BRIEFING__MAX_SIGNALS
BRIEFING__MAX_GAPS
BRIEFING__MAX_RECOMMENDATIONS
BRIEFING__MAX_CITATIONS
BRIEFING__MAX_STATEMENTS
BRIEFING__MAX_CONTEXT_CHARACTERS
BRIEFING__MAX_STATEMENT_LENGTH
BRIEFING__MAX_MARKDOWN_CHARACTERS
BRIEFING__MAX_REPAIR_ATTEMPTS
```

## Requisitos

- **RF-01:** selecionar e agrupar recomendações válidas por startup.
- **RF-02:** construir seções factuais apenas com entradas validadas correspondentes.
- **RF-03:** construir allowlists separadas de citações da startup e NVIDIA.
- **RF-04:** gerar sínteses e inferências estruturadas pelo modelo pesado.
- **RF-05:** validar natureza, texto e citações de cada declaração.
- **RF-06:** condicionar oportunidades Inception a documentação oficial citável.
- **RF-07:** renderizar Markdown deterministicamente a partir do contrato final.
- **RF-08:** reparar uma vez, sanitizar falhas e preservar resultados parciais.
- **RF-09:** registrar métricas, limites, truncamentos e logs seguros.
- **RF-10:** integrar estado, grafo e `/api/v1/search` de forma aditiva.
- **RF-11:** não exportar, persistir, pesquisar nem alterar análises anteriores.
- **RNF-01:** contratos estritos, UTF-8, UUIDs, URLs e enums canônicos.
- **RNF-02:** execução assíncrona, sequencial por startup e determinística fora do LLM.
- **RNF-03:** isolamento absoluto entre startups.
- **RNF-04:** nenhuma dependência concreta de provedor na aplicação ou domínio.
- **RNF-05:** logs, métricas e erros não expõem conteúdo nem segredos.
- **RNF-06:** testes padrão são offline e cobertura global permanece acima de 80%.
- **RNF-07:** compatibilidade HTTP é preservada por adição de campos.

## Fora do escopo

- Exportação PDF, slides, imagens ou templates visuais.
- Alteração de componentes frontend.
- Persistência, histórico, envio ou aprovação humana do briefing.
- Nova busca, classificação, evidência, gap ou recomendação.
- Elegibilidade definitiva ou inscrição no NVIDIA Inception.
- Preço, prazo, dimensionamento, contrato ou garantia de resultado.

## Critério de conclusão

A feature estará implementada quando briefings estruturados e Markdown forem
produzidos somente para recomendações válidas, todas as conclusões forem citáveis e
classificadas, Inception depender de fonte oficial, ausências e falhas forem tratadas,
grafo/API estiverem estendidos e todas as verificações offline e regressões passarem.

## Sugestão de commit

`feat(briefing): generate cited executive startup briefings`
