# Especificação 013: NVIDIA RAG Agent

## Status

Implementada e verificada em 7 de setembro de 2026; aguardando aprovação
explícita da entrega para conclusão formal.

## Contexto

A especificação 012 criou o corpus NVIDIA versionado: documentos e chunks
canônicos no PostgreSQL, vetores derivados no Qdrant e um corpus lexical BM25
reconstruível. O fluxo do LangGraph atualmente termina no Evidence Validator,
com perfis e classificações validados, mas ainda não consulta esse corpus.

Esta funcionalidade adiciona o NVIDIA RAG Agent. O nó transforma somente os fatos
validados da startup em consultas, recupera trechos NVIDIA por busca vetorial e
lexical, funde os rankings, aplica o reranker e avalia se o contexto resultante é
suficiente. Seu resultado é evidência técnica citável para agentes posteriores;
ele não escolhe nem recomenda uma tecnologia.

O PostgreSQL permanece a fonte canônica do texto e da URL. Em particular, a URL
oficial retornada deve ser lida de `knowledge_documents.source_url`. Payloads do
Qdrant e entradas do índice BM25 servem para busca e conferência, mas não podem
sobrescrever os dados canônicos.

## Objetivos

- Consultar a base NVIDIA somente a partir de perfis validados utilizáveis.
- Combinar recuperação vetorial no Qdrant e lexical BM25 de forma determinística.
- Normalizar, fundir, deduplicar, limitar e ordenar resultados com regras auditáveis.
- Aplicar o reranker previsto pela arquitetura sem perder os scores anteriores.
- Retornar trechos citáveis com identidade, posição, tecnologia e URL oficial.
- Avaliar a suficiência do contexto e repetir a recuperação dentro de um limite.
- Degradar de forma controlada quando apenas um canal ou o reranker falhar.
- Preservar erros, avisos, métricas e resultados parciais no `AppState`.
- Manter testes unitários offline, determinísticos e sem consumo de tokens.

## Entradas e condição de execução

O nó recebe do `AppState`:

- `validated_profiles`;
- `validated_classifications`, quando houver classificação aprovada para a startup;
- `technical_gaps`, quando já existirem no estado;
- `correlation_id`, `warnings`, `errors` e `metrics`.

Um perfil validado é **utilizável** quando possui `startup_id`, nome e ao menos um
fato validado não vazio em produto, modelo de negócio, setor, público-alvo, casos
de uso de IA, tecnologias, infraestrutura, dependências externas, necessidades
técnicas ou afirmações. Um perfil somente com identidade não é utilizável.

A classificação validada enriquece a consulta, mas sua ausência ou estado incerto
não bloqueia um perfil utilizável. Necessidades técnicas validadas têm prioridade;
`technical_gaps` só podem ser usados quando vinculados a evidências que sobreviveram
ao Evidence Validator. Itens rejeitados, conflitantes ou insuficientes não entram
na consulta como fatos.

## Histórias do usuário

### US-01 — Construir consultas rastreáveis

Como agente posterior, quero saber quais sinais validados originaram cada consulta
para não confundir hipótese de busca com fato sobre a startup.

Critérios de aceite:

- A consulta inicial é construída deterministicamente a partir dos campos permitidos.
- Necessidades técnicas e lacunas validadas aparecem antes de casos de uso,
  tecnologias, infraestrutura, produto, setor e classificação.
- Quantidade de itens, tamanho por item e tamanho total da consulta são limitados.
- Valores duplicados são removidos por texto normalizado, preservando a primeira ordem.
- Cada consulta registra os campos e IDs de evidência que a originaram.
- Não entram dados rejeitados, conflitantes, insuficientes, conteúdo bruto de fonte,
  conhecimento externo nem fatos presumidos.
- A consulta não pede recomendação e não antecipa uma tecnologia NVIDIA sem que ela
  esteja no perfil validado ou no vocabulário controlado de expansão.

### US-02 — Recuperar por dois canais independentes

Como pessoa usuária, quero que termos exatos e similaridade semântica sejam
considerados para reduzir perdas de informação.

Critérios de aceite:

- O texto da consulta é convertido em embedding pela porta `EmbeddingModel` e
  pesquisado no Qdrant por uma porta de busca vetorial.
- O mesmo texto é pesquisado no corpus BM25 reconstruído dos chunks ativos do
  PostgreSQL por uma porta lexical.
- Cada canal retorna no máximo o limite configurado e preserva UUID, score bruto e rank.
- IDs inexistentes, duplicados, inativos ou com score não finito são descartados e
  contabilizados com aviso sanitizado.
- Os textos e metadados finais são carregados do PostgreSQL após a recuperação por IDs.
- Um chunk cuja relação documento/chunk ou metadados canônicos não seja válida não é
  exposto como evidência.

### US-03 — Fundir resultados de maneira verificável

Como pessoa desenvolvedora, quero uma regra explícita de fusão para reproduzir a
ordem sem depender da escala particular de Qdrant ou BM25.

Critérios de aceite:

- Resultados são deduplicados pelo UUID do chunk antes da fusão.
- Dentro de cada canal, o rank começa em 1 e empates de score são resolvidos por
  `document_id`, `chunk_index` e `chunk_id` em ordem crescente.
- O componente normalizado de um rank `r` é
  `rank_score(r) = (rrf_k + 1) / (rrf_k + r)`, no intervalo `(0, 1]`.
- Para os dois canais disponíveis, o score híbrido é
  `vector_weight * vector_rank_score + lexical_weight * lexical_rank_score`;
  a contribuição de um chunk ausente em um canal é zero.
- Os pesos são não negativos, somam 1 e são validados na inicialização.
- Se um canal inteiro estiver indisponível, os pesos dos canais disponíveis são
  renormalizados e o modo degradado fica explícito; ausência individual de um chunk
  em um canal não provoca renormalização.
- Scores brutos, ranks, componentes normalizados, pesos efetivos e score híbrido
  permanecem na saída para auditoria.
- A união é limitada após ordenar por score híbrido decrescente, melhor rank de
  canal crescente e a chave estável `document_id`, `chunk_index`, `chunk_id`.

### US-04 — Aplicar reranking sem perder rastreabilidade

Como agente consumidor, quero os candidatos mais relevantes reordenados pelo
reranker e ainda poder inspecionar como eles foram encontrados.

Critérios de aceite:

- Somente candidatos híbridos já validados contra o PostgreSQL são enviados à porta
  `Reranker`, com UUID, consulta e texto canônico.
- `top_n` é configurável, positivo e não excede o limite de candidatos fundidos.
- A resposta do reranker aceita somente IDs enviados, sem duplicatas e com score
  finito no intervalo documentado pelo adaptador.
- A ordem final usa `reranker_score` decrescente, depois `hybrid_score` decrescente
  e, por fim, a chave estável do chunk.
- Cada item preserva scores e ranks vetorial, BM25, híbrido e do reranker.
- Resposta inválida ou falha do reranker ativa fallback para a ordem híbrida, registra
  aviso e deixa `reranker_score` ausente; não inventa score.
- O fallback não é apresentado como execução bem-sucedida do reranker.

### US-05 — Retornar contexto citável

Como futuro agente de recomendação, quero trechos completos e metadados confiáveis
para citar a documentação oficial.

Critérios de aceite:

- Cada trecho retorna `startup_id`, `chunk_id`, `document_id`, conteúdo, título,
  tecnologia, `source_key`, `source_url`, seção, índice e offsets quando disponíveis.
- `source_url` é obrigatória, usa o valor de `knowledge_documents.source_url` e deve
  coincidir com a URL oficial preservada pela ingestão.
- Cada trecho informa tentativa e consultas em que apareceu, além de todos os scores.
- IDs são UUIDs válidos e não são substituídos por posição, URL ou ID do provedor.
- O conteúdo não é resumido, reescrito nem complementado pelo agente.
- Ausência de título, tecnologia, URL ou localizador obrigatório invalida o trecho.

### US-06 — Avaliar e ampliar contexto insuficiente

Como pessoa usuária, quero que uma primeira busca fraca seja ampliada de forma
limitada e que lacunas remanescentes sejam declaradas.

Critérios de aceite:

- A suficiência é avaliada por startup após o reranking ou seu fallback.
- Um contexto só é `sufficient` quando possui, no mínimo, as quantidades configuradas
  de chunks relevantes e documentos distintos, todos citáveis, e o melhor resultado
  atinge o limiar de relevância do modo utilizado.
- Os limiares de reranker e fallback híbrido são separados e validados entre 0 e 1.
- A decisão registra contagens, melhor score, limiar usado, modo de ranking e razões.
- Se insuficiente, a próxima tentativa amplia `top_k` por multiplicador limitado e
  reformula deterministicamente a consulta: primeiro prioriza cada necessidade
  técnica; depois remove sinais empresariais de menor prioridade e usa os termos
  técnicos restantes. Menções NVIDIA explícitas podem ser normalizadas pelo enum e
  aliases versionados da spec 012.
- Nenhuma reformulação usa LLM, internet, fato rejeitado ou tecnologia inferida.
- Consultas repetidas são eliminadas; todas as tentativas ficam registradas.
- O total de tentativas é limitado por `max_attempts`; o valor inclui a tentativa inicial.
- Ao atingir o limite sem suficiência, o resultado é `insufficient` e contém lacunas
  explícitas, sem transformar resultados fracos em evidências suficientes.
- Uma tentativa posterior não duplica chunks: para cada UUID permanece a ocorrência
  com melhor reranker score, ou melhor score híbrido no fallback, mantendo a lista de
  tentativas e consultas em que foi encontrado.

### US-07 — Tratar indisponibilidade e base vazia

Como pessoa operadora, quero degradação previsível e erros seguros para distinguir
ausência de conhecimento de falha de infraestrutura.

Critérios de aceite:

- Base PostgreSQL sem documentos/chunks ativos retorna contexto `insufficient`, aviso
  `nvidia_rag_empty_knowledge_base` e HTTP 200.
- Nenhum item acima do limiar retorna `nvidia_rag_irrelevant_results`, contexto
  `insufficient` e HTTP 200.
- Falha do embedding ou Qdrant desativa somente o canal vetorial quando BM25 funciona.
- Falha de construção ou consulta BM25 desativa somente o canal lexical quando o
  canal vetorial funciona.
- Falha do reranker usa o fallback híbrido definido em US-04.
- Quando nenhum canal de recuperação está disponível, o nó registra
  `nvidia_rag_retrieval_unavailable`, preserva resultados anteriores e a API responde 503.
- Metadados inválidos, inconsistência do corpus ou resposta inválida de adaptador são
  tratados sem expor resposta bruta, DSN, chave, token, vetor ou stack trace.
- Falha de uma startup não apaga contextos válidos de outras startups.

### US-08 — Integrar ao LangGraph e à API

Como aplicação frontend, quero receber o contexto NVIDIA no mesmo fluxo de busca.

Critérios de aceite:

- O grafo executa `nvidia_rag` depois de `evidence_validator` somente quando há ao
  menos um perfil validado utilizável.
- Sem perfil utilizável, o grafo termina previsivelmente, não acessa embedding,
  PostgreSQL, Qdrant, BM25 ou reranker e adiciona aviso apropriado.
- O nó atualiza parcialmente apenas os campos que possui, acumulando avisos, erros e métricas.
- `/api/v1/search` expõe os contextos, trechos, suficiência e lacunas com contrato estrito.
- A execução termina após o NVIDIA RAG nesta spec; não existe aresta para recomendação.
- `/api/v1/query-plans` permanece inalterado.

### US-09 — Testar sem rede, LLM ou serviços pagos

Como pessoa mantenedora, quero validar toda a lógica localmente e sem consumo de tokens.

Critérios de aceite:

- Testes unitários usam repositório, embedding, Qdrant, BM25 e reranker fakes mínimos.
- Nenhum teste da suíte padrão instancia cliente real, usa LLM, acessa rede ou depende
  de credenciais presentes no ambiente.
- Fusão, desempates, deduplicação, limites, fallback, suficiência e tentativas usam
  fixtures pequenas e resultados determinísticos.
- Testes reais de PostgreSQL e Qdrant são marcados `integration` e exigem
  `RUN_INTEGRATION_TESTS=1`.
- Teste real de embedding ou reranker é marcado `external` e exige habilitação e
  credenciais explícitas adicionais.
- A cobertura prioriza todos os critérios de aceite e preserva o mínimo global de 80%.

### US-10 — Preservar o limite da feature

Como pessoa mantenedora, quero recuperação técnica sem decisão prematura.

Critérios de aceite:

- O agente não cria `Recommendation`, prioridade, plano de implementação ou argumento comercial.
- O agente não altera o perfil, a classificação, as validações ou as evidências da startup.
- Similaridade, presença de palavra ou score não são tratados como prova de adequação final.
- O agente não coleta internet, não ingere fontes e não atualiza a base NVIDIA.
- O agente não usa documentos de startups como se fossem documentação NVIDIA.

## Contratos conceituais

```text
NvidiaRetrievalScores
├── vector_raw_score: float | null
├── vector_rank: integer | null
├── vector_rank_score: float | null
├── bm25_raw_score: float | null
├── bm25_rank: integer | null
├── bm25_rank_score: float | null
├── hybrid_score: float
├── reranker_score: float | null
└── reranker_rank: integer | null

NvidiaRetrievedChunk
├── startup_id: UUID
├── chunk_id: UUID
├── document_id: UUID
├── content: string
├── title: string
├── technology: NvidiaTechnology
├── source_key: string
├── source_url: URL
├── chunk_index: integer
├── source_section: string | null
├── start_offset: integer | null
├── end_offset: integer | null
├── retrieval_attempts: list[integer]
├── matched_queries: list[string]
└── scores: NvidiaRetrievalScores

NvidiaContextSufficiency
├── status: sufficient | insufficient
├── relevant_chunk_count: integer
├── distinct_document_count: integer
├── best_score: float | null
├── threshold: float
├── ranking_mode: reranker | hybrid_fallback
└── reasons: list[string]

NvidiaStartupContext
├── startup_id: UUID
├── startup_name: string
├── attempted_queries: list[string]
├── attempts: integer
├── chunks: list[NvidiaRetrievedChunk]
├── sufficiency: NvidiaContextSufficiency
└── gaps: list[NvidiaContextGap]
```

Todos os modelos públicos são estritos (`extra="forbid"`), imutáveis quando
apropriado e validam limites, UUIDs, URLs, scores finitos e coerência entre status.

## Portas previstas

- `KnowledgeRetrievalRepository`: lista a cobertura ativa e carrega documentos e
  chunks canônicos por UUID em ordem estável.
- `KnowledgeVectorSearch`: pesquisa UUIDs e scores no Qdrant a partir de um vetor.
- `KnowledgeLexicalSearch`: constrói/carrega o corpus ativo e pesquisa UUIDs e
  scores BM25.
- `EmbeddingModel`: gera o vetor da consulta sem expor SDK à aplicação.
- `Reranker`: reordena somente os candidatos fundidos.

As portas de ingestão da spec 012 podem ser estendidas quando a responsabilidade
for a mesma; contratos de escrita e leitura devem permanecer separados o bastante
para o agente não receber permissão de alterar o corpus.

## Configuração mínima

```text
NVIDIA_RAG_VECTOR_TOP_K
NVIDIA_RAG_LEXICAL_TOP_K
NVIDIA_RAG_FUSED_TOP_K
NVIDIA_RAG_RERANK_TOP_N
NVIDIA_RAG_RRF_K
NVIDIA_RAG_VECTOR_WEIGHT
NVIDIA_RAG_LEXICAL_WEIGHT
NVIDIA_RAG_MIN_RELEVANT_CHUNKS
NVIDIA_RAG_MIN_DISTINCT_DOCUMENTS
NVIDIA_RAG_MIN_RERANKER_SCORE
NVIDIA_RAG_MIN_HYBRID_SCORE
NVIDIA_RAG_MAX_ATTEMPTS
NVIDIA_RAG_EXPANSION_MULTIPLIER
NVIDIA_RAG_MAX_QUERY_ITEMS
NVIDIA_RAG_MAX_QUERY_CHARS
```

Limites devem possuir faixas conservadoras. `max_attempts` inclui a tentativa
inicial e não pode exceder 3; pesos devem somar 1; limites de saída não podem
exceder os candidatos das etapas anteriores. Configuração inválida impede o
startup da aplicação com mensagem sanitizada.

## Códigos mínimos

| Código | Situação | Comportamento |
| --- | --- | --- |
| `nvidia_rag_no_usable_profiles` | Nenhum perfil validado utilizável | Encerra sem I/O, HTTP 200 |
| `nvidia_rag_empty_knowledge_base` | Corpus canônico vazio | Contexto insuficiente, HTTP 200 |
| `nvidia_rag_vector_unavailable` | Embedding ou Qdrant falhou | Usa BM25, se disponível |
| `nvidia_rag_lexical_unavailable` | Índice BM25 falhou | Usa Qdrant, se disponível |
| `nvidia_rag_reranker_unavailable` | Reranker falhou ou respondeu inválido | Usa ranking híbrido |
| `nvidia_rag_irrelevant_results` | Nada atingiu o limiar | Contexto insuficiente, HTTP 200 |
| `nvidia_rag_context_insufficient` | Tentativas esgotadas | Lacuna explícita, HTTP 200 |
| `nvidia_rag_result_invalid` | ID, score ou metadado incoerente | Descarta item e registra aviso |
| `nvidia_rag_retrieval_unavailable` | Nenhum canal disponível | Erro recuperável, HTTP 503 |

## Métricas mínimas

- `nvidia_rag_duration_ms`;
- `nvidia_rag_input_profile_count`;
- `nvidia_rag_processed_startup_count`;
- `nvidia_rag_attempt_count`;
- `nvidia_rag_vector_query_count` e `nvidia_rag_lexical_query_count`;
- `nvidia_rag_vector_candidate_count` e `nvidia_rag_lexical_candidate_count`;
- `nvidia_rag_deduplicated_candidate_count`;
- `nvidia_rag_reranker_call_count` e `nvidia_rag_reranker_failure_count`;
- `nvidia_rag_selected_chunk_count`;
- `nvidia_rag_sufficient_context_count` e `nvidia_rag_insufficient_context_count`;
- `nvidia_rag_vector_fallback_count`, `nvidia_rag_lexical_fallback_count` e
  `nvidia_rag_hybrid_fallback_count`.

Métricas são numéricas, acumuláveis e não contêm consultas, textos ou segredos.

## Requisitos funcionais

- **RF-01:** selecionar somente perfis validados utilizáveis.
- **RF-02:** construir consultas determinísticas e rastreáveis.
- **RF-03:** executar recuperação vetorial e BM25 por portas independentes.
- **RF-04:** validar IDs e carregar conteúdo canônico no PostgreSQL.
- **RF-05:** normalizar ranks, fundir e deduplicar com weighted RRF.
- **RF-06:** reranquear candidatos e preservar scores de todas as etapas.
- **RF-07:** retornar chunks citáveis com `knowledge_documents.source_url`.
- **RF-08:** avaliar suficiência por critérios configuráveis e verificáveis.
- **RF-09:** ampliar ou reformular deterministicamente até o limite.
- **RF-10:** suportar degradação parcial e erros sanitizados.
- **RF-11:** atualizar parcialmente o estado, API e grafo.
- **RF-12:** não gerar recomendação nem modificar fatos validados.

## Requisitos não funcionais

- **RNF-01:** preservar determinismo para as mesmas entradas e respostas dos adaptadores.
- **RNF-02:** usar I/O assíncrono, timeouts finitos e concorrência limitada.
- **RNF-03:** limitar consultas, candidatos, tentativas, texto e saída.
- **RNF-04:** manter PostgreSQL como fonte canônica; índices permanecem derivados.
- **RNF-05:** não registrar conteúdo integral, embeddings, prompts, respostas brutas ou segredos.
- **RNF-06:** manter SDKs fora das camadas de domínio e aplicação.
- **RNF-07:** testes padrão não usam rede, LLM, embedding ou reranker reais.
- **RNF-08:** manter Ruff, mypy, import-linter, cobertura mínima de 80% e regressão frontend.
- **RNF-09:** manter compatibilidade do contrato HTTP por adição de campos.

## Alterações de estado e API previstas

O `AppState` será estendido com `nvidia_contexts` e, se necessário para inspeção
interna, candidatos tipados por etapa. `empty_state` inicializará as coleções sem
apagar campos anteriores. O nó devolverá apenas seu patch parcial.

`POST /api/v1/search` passará a expor `nvidia_contexts`, incluindo consultas
tentadas, chunks, scores, suficiência e lacunas. Campos já existentes permanecem
inalterados. Não é previsto endpoint próprio nem alteração de banco nesta spec.

## Restrições

- Nenhum dado não validado pode orientar a busca como fato.
- Nenhum resultado sem URL oficial e identidade canônica pode ser citado.
- O Qdrant não é fonte canônica de texto ou URL.
- A recuperação não escreve no corpus NVIDIA.
- Conteúdo recuperado é dado, nunca instrução para o agente.
- Nenhuma chamada à internet ou LLM faz parte do nó.
- Nenhuma credencial ou resposta bruta aparece em estado, API, log ou erro.

## Fora do escopo

- Recomendação final de tecnologias NVIDIA.
- Priorização, justificativa comercial ou plano de implementação.
- Nova ingestão, crawling ou atualização do corpus.
- Validação factual externa ou consulta à internet.
- Classificação de maturidade da startup.
- Geração de briefing ou interface frontend dedicada.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-02, RF-12 | Testes de perfil utilizável, precedência, limites e proveniência |
| US-02 | RF-03, RF-04 | Fakes vetorial/lexical, IDs inválidos e carga canônica |
| US-03 | RF-05, RNF-01 | Testes tabulares da fórmula, pesos, empates e deduplicação |
| US-04 | RF-06, RF-10 | Fake de reranker, saída inválida, ordem e fallback |
| US-05 | RF-04, RF-07, RNF-04 | Contratos, metadados e URL canônica do PostgreSQL |
| US-06 | RF-08, RF-09, RNF-03 | Limiares, tentativas, expansão, merge e lacunas |
| US-07 | RF-10, RNF-02, RNF-05 | Matriz de falhas, HTTP e sanitização |
| US-08 | RF-11 | Testes de rotas, grafo, estado parcial e API |
| US-09 | RNF-06 a RNF-08 | Guardas offline, fakes, integração opt-in e qualidade |
| US-10 | RF-12 | Testes arquiteturais e ausência de recomendações |

## Critério de conclusão

A feature estará concluída quando o grafo executar o NVIDIA RAG somente para
perfis validados utilizáveis; Qdrant e BM25 forem consultados, fundidos e
reranqueados conforme as fórmulas desta spec; os chunks retornarem metadados e
`source_url` canônicos; suficiência, novas tentativas e todas as degradações forem
testadas; a API expuser o novo contexto; a suíte offline e as integrações
habilitadas passarem; e a entrega receber aprovação explícita.

## Sugestão de commit

`feat(rag): add hybrid NVIDIA knowledge retrieval agent`
