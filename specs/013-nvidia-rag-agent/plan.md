# Plano 013: NVIDIA RAG Agent

## Estratégia

Implementar o nó como um caso de uso de leitura, isolado de SDKs. O serviço recebe
um snapshot dos fatos validados, monta consultas determinísticas, executa os dois
canais de recuperação, resolve os UUIDs no PostgreSQL, aplica weighted RRF e chama
o reranker. Uma política pura avalia suficiência e decide se haverá outra tentativa.

O desenho favorece funções pequenas para query building, fusão, deduplicação,
ordenação e suficiência. Assim, a maior parte dos critérios é coberta sem banco,
rede, LLM, embedding ou reranker real.

## Estrutura prevista

```text
backend/src/app/
├── application/
│   ├── contracts/nvidia_rag.py
│   ├── ports/knowledge.py
│   └── services/nvidia_rag.py
├── infrastructure/
│   ├── persistence/repositories.py
│   ├── retrieval/knowledge_bm25.py
│   └── vector/knowledge.py
├── graph/
│   ├── builder.py
│   ├── nodes.py
│   └── state.py
├── api/routes/search.py
└── core/
    ├── config.py
    └── resources.py

backend/tests/
├── unit/test_nvidia_rag_*.py
└── integration/test_nvidia_rag_integration.py
```

Os nomes podem ser ajustados durante a implementação, preservando contratos,
limites de camada e critérios desta spec.

## Fases de implementação

### 1. Contratos e configuração

- Criar contratos estritos para consulta, candidato por canal, scores, chunk final,
  suficiência, lacuna e contexto por startup.
- Definir portas de leitura vetorial, lexical e canônica, reaproveitando
  `EmbeddingModel` e `Reranker` existentes.
- Adicionar configuração validada de top-k, weighted RRF, reranking, limiares,
  tentativas, expansão e tamanho de consulta.
- Definir códigos e mensagens sanitizadas do nó.

### 2. Consulta a partir do perfil validado

- Implementar a regra pura de perfil utilizável.
- Selecionar somente fatos aprovados e gaps com evidência válida.
- Montar consulta inicial com precedência e limites estáveis.
- Produzir consultas subsequentes determinísticas por necessidade técnica e por
  remoção de termos empresariais de menor prioridade.
- Guardar proveniência da consulta sem enviar conteúdo integral a logs ou métricas.

### 3. Portas e adaptadores de recuperação

- Estender o repositório PostgreSQL com leitura ativa por UUID e cobertura do corpus.
- Estender o adaptador Qdrant com busca por vetor, retornando UUID e score bruto.
- Evoluir `KnowledgeBM25Index` para construir o índice dos chunks ativos e pesquisar
  UUID e score bruto em ordem determinística.
- Traduzir indisponibilidade e saída inválida para falhas internas sanitizadas.
- Validar que nenhum adaptador de leitura possui método de ingestão no serviço do nó.

### 4. Fusão e reranking

- Ordenar cada canal com desempate estável e atribuir ranks a partir de 1.
- Deduplicar pela identidade do chunk.
- Implementar o componente de rank normalizado e weighted RRF exatamente como na spec.
- Renormalizar pesos somente quando um canal inteiro estiver indisponível.
- Resolver os candidatos no PostgreSQL e excluir inconsistências antes do reranker.
- Limitar candidatos fundidos, chamar a porta `Reranker`, validar sua resposta e
  ordenar o resultado final.
- Preservar scores brutos, ranks, componentes, score híbrido e score do reranker.

### 5. Suficiência e novas tentativas

- Criar avaliador puro com mínimos de chunks/documentos e limiar por modo de ranking.
- Retornar razões objetivas para cada critério não atingido.
- Ampliar top-k com limite superior e gerar a próxima consulta determinística.
- Unir tentativas pelo UUID, preservando a melhor ocorrência e a proveniência completa.
- Encerrar cedo quando houver suficiência ou previsivelmente ao atingir `max_attempts`.
- Registrar lacuna explícita quando o contexto continuar insuficiente.

### 6. Nó, composição, grafo e API

- Implementar `NvidiaRagAgent` como `GraphNode` e patch parcial do `AppState`.
- Registrar dependências e adaptadores no composition root.
- Alterar a rota após `evidence_validator` para `nvidia_rag` ou `END` conforme a
  existência de perfil utilizável.
- Manter `nvidia_rag -> END`, sem nó de recomendação nesta feature.
- Estender `SearchResponse` de forma aditiva com os novos contratos.
- Atualizar o mapeamento HTTP somente para a indisponibilidade total prevista.

### 7. Testes e documentação

- Testar funções puras com tabelas pequenas e valores de score calculáveis à mão.
- Testar serviço e nó com fakes de todas as portas, inclusive falhas independentes.
- Testar grafo e API para perfil utilizável, ausência, suficiência e lacunas.
- Manter guardas contra rede, LLM, embedding e reranker reais na suíte padrão.
- Criar integração opt-in para PostgreSQL e Qdrant; manter provedores externos em
  teste separado e duplamente habilitado.
- Atualizar README e `.env.example` com configuração e modo degradado.
- Executar Ruff, mypy, import-linter, pytest/cobertura e regressão do frontend.

## Decisões

### D-01 — Weighted RRF em vez de min-max dos scores brutos

Qdrant e BM25 produzem escalas distintas e dependentes do corpus. A fusão usa ranks
normalizados, preserva os valores brutos apenas para auditoria e evita instabilidade
quando um conjunto tem scores iguais ou um único item.

### D-02 — PostgreSQL resolve a evidência final

Os índices retornam identidades e scores. Texto, documento, título, tecnologia,
posição e URL final são lidos do estado ativo no PostgreSQL. Isso mantém
`knowledge_documents.source_url` como fonte canônica e impede payload obsoleto do
Qdrant de virar citação.

### D-03 — Falha parcial degrada; falha total interrompe

Se Qdrant ou BM25 falhar isoladamente, o outro canal continua e seus pesos são
renormalizados. Se o reranker falhar, a ordem híbrida é usada. Somente a perda de
todos os canais impede a recuperação e produz erro 503.

### D-04 — Suficiência determinística

Contagem de chunks, diversidade de documentos, metadados citáveis e limiar de
relevância formam uma decisão reproduzível. Ela não afirma adequação de produto;
apenas indica se existe contexto mínimo para o próximo agente trabalhar.

### D-05 — Reformulação local e limitada

As consultas adicionais são projeções determinísticas dos mesmos fatos validados.
Não há LLM, custo de tokens nem possibilidade de inserir fatos sobre a startup. O
vocabulário NVIDIA usado para normalizar menções é o catálogo versionado da spec 012.

### D-06 — Resultado por startup

Cada perfil gera contexto e suficiência próprios. Isso evita misturar necessidades,
scores ou citações entre startups e permite preservar sucesso parcial.

## Verificação prevista

1. Validar contratos e todas as faixas de configuração.
2. Executar testes puros de consulta, fórmula, deduplicação, desempate e suficiência.
3. Executar testes do serviço/nó com fakes e matriz completa de falhas.
4. Executar testes do roteamento LangGraph e do contrato HTTP.
5. Executar suíte offline com guardas de rede e provedores.
6. Habilitar integração PostgreSQL/Qdrant e validar IDs, texto e URL canônicos.
7. Executar Ruff, mypy, import-linter e cobertura mínima de 80%.
8. Executar lint, testes e build do frontend.
9. Revisar todos os critérios de aceite antes de solicitar aprovação.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Scores incomparáveis entre canais | Weighted RRF baseado em rank |
| Payload vetorial desatualizado | Resolver texto e URL no PostgreSQL |
| Um serviço externo derrubar o fluxo | Fallback independente e erros sanitizados |
| Resultados irrelevantes parecerem suficientes | Limiares separados e razões de suficiência |
| Tentativas ampliarem custo indefinidamente | Máximo de 3, top-k e multiplicador limitados |
| Mistura de evidências entre startups | Contextos e consultas particionados por UUID |
| Resultado não determinístico em empates | Chave estável explícita em todas as etapas |
| Testes consumirem rede ou tokens | Fakes mínimos e integração/external opt-in |

## Evoluções posteriores

- agente de recomendação usando apenas contextos suficientes;
- explicações que combinem evidências da startup e citações NVIDIA;
- avaliação offline de recall, precisão e qualidade do reranker com dataset curado;
- cache de consultas e índice lexical persistente, mediante medição;
- observabilidade operacional sem exposição de conteúdo.

## Resultado da implementação

- O nó consome somente perfis validados utilizáveis e não usa LLM.
- Qdrant e BM25 operam por portas independentes e degradam isoladamente.
- A fusão weighted RRF preserva scores, ranks, pesos e desempates estáveis.
- PostgreSQL resolve o texto, os metadados e a `source_url` canônica.
- O reranker possui validação estrita e fallback explícito para a ordem híbrida.
- Suficiência, expansão limitada, reformulações determinísticas e lacunas são
  retornadas por startup.
- O LangGraph e `/api/v1/search` expõem `nvidia_contexts` sem executar o agente
  quando não há perfil validado utilizável.
- Testes offline, integração PostgreSQL/Qdrant, qualidade estática, cobertura e
  regressão do frontend foram aprovados.

## Sugestão de commit

`feat(rag): add hybrid NVIDIA knowledge retrieval agent`
