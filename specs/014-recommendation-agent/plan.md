# Plano 014: Recommendation Agent

## Estratégia

Implementar o Recommendation Agent como nó assíncrono com três etapas separadas:
preparação determinística da entrada, geração estruturada de candidatos pelo
`llm_heavy` e validação determinística antes da publicação no estado.

O modelo nunca define identidades ou referências completas. Ele seleciona somente
chaves e UUIDs de allowlists, descreve as justificativas e propõe fatores. O agente
resolve as evidências originais, recalcula prioridade e complexidade e rejeita o
lote inteiro da startup se houver incoerência. Essa separação mantém as decisões
auditáveis e permite testar a maior parte da lógica sem LLM.

## Estrutura prevista

```text
backend/src/app/
├── application/contracts/recommendation.py
├── core/config.py
├── core/resources.py
├── graph/
│   ├── agents/recommendation.py
│   ├── prompts/recommendation.py
│   ├── builder.py
│   ├── model_policy.py
│   └── state.py
└── api/
    ├── routes/search.py
    └── status.py

backend/tests/
├── unit/test_recommendation_agent.py
├── unit/test_graph.py
├── unit/test_api.py
├── unit/test_config.py
└── architecture/test_dependencies.py
```

Os nomes podem ser ajustados durante a implementação, preservando os contratos,
critérios e limites de camada desta especificação.

## Fases de implementação

### 1. Contratos e configuração

- Criar enums e modelos estritos para necessidade, fatores, evidências e recomendação.
- Separar contrato cru do modelo e contrato final derivado pelo agente.
- Adicionar limites validados para recomendações, necessidades, fontes, chunks,
  caracteres, justificativas, próxima ação e reparo.
- Definir códigos de aviso e erro sanitizados.

### 2. Elegibilidade e allowlists

- Associar perfil, classificação, validações, gaps e contexto por `startup_id`.
- Enumerar `technical_needs` com chaves estáveis na ordem do perfil.
- Resolver `technical_gaps` somente quando seus IDs intersectarem fontes aprovadas
  de uma única startup.
- Construir allowlists separadas de necessidades, evidências da startup e chunks NVIDIA.
- Ignorar deterministicamente entradas não rastreáveis e registrar o motivo.
- Detectar contexto de negócio insuficiente antes de chamar o modelo.

### 3. Prompt mínimo e geração

- Criar prompt versionado, compacto e delimitado para uma startup por chamada.
- Incluir somente fatos validados, classificação opcional, necessidades elegíveis e
  os chunks suficientes mais relevantes dentro dos limites.
- Pedir JSON compatível com o contrato cru e permitir lista vazia.
- Resolver `NodeName.RECOMMENDATION` pelo `ModelRegistry` e usar `llm_heavy`.
- Não incluir dados rejeitados, contexto de outra startup ou campos derivados pelo código.

### 4. Validação semântica e evidências

- Validar necessidade, tecnologia e todos os IDs contra as allowlists.
- Exigir tecnologia idêntica à dos chunks NVIDIA citados.
- Exigir referências distintas para diagnóstico da startup e documentação NVIDIA.
- Validar que justificativa de negócio aponta para fato de produto, modelo de negócio,
  público-alvo, caso de uso ou operação aprovada.
- Detectar restrições explícitas incompatíveis sem inventar incompatibilidades.
- Rejeitar duplicatas por startup/tecnologia e agrupar necessidades no mesmo candidato.

### 5. Prioridade, complexidade e ordenação

- Implementar funções puras para pontuar fatores e mapear scores aos enums.
- Derivar força de evidência por UUIDs distintos de documentos da startup.
- Verificar que fatores elevados possuem as referências exigidas.
- Recalcular prioridade e complexidade, rejeitando divergência com a proposta do modelo.
- Ordenar por prioridade, complexidade, tecnologia e UUID com desempate estável.

### 6. Reparo, falhas e resultados parciais

- Aplicar a mesma validação estrutural e semântica antes e depois do reparo.
- Enviar ao reparo apenas schema compacto, IDs permitidos, códigos das violações e
  saída inválida delimitada.
- Preservar recomendações de startups anteriores se outra falhar.
- Tratar lote vazio válido, ausência de necessidade, classificação e contexto.
- Sanitizar indisponibilidade e invalidade persistente.
- Registrar métricas e logs sem conteúdo.

### 7. Grafo, estado e API

- Evoluir `AppState.recommendations` para o contrato final tipado.
- Implementar `RecommendationAgent` como patch parcial do estado.
- Registrar o agente no composition root.
- Adicionar `route_after_nvidia_rag` e a aresta condicional.
- Manter `recommendation -> END`, sem Briefing nesta spec.
- Expor recomendações em `SearchResponse` e mapear 502/503.

### 8. Testes e documentação

- Testar funções puras com tabelas completas de prioridade e complexidade.
- Testar agente com respostas JSON mínimas de fakes, sem cliente real.
- Cobrir cenários TAPI representativos e todas as rejeições de allowlist.
- Testar reparo, falha, sucesso parcial, truncamento, métricas e sanitização.
- Testar roteamento, API, OpenAPI e preservação do estado anterior.
- Atualizar README e `.env.example`.
- Executar Ruff, mypy, import-linter, pytest/cobertura e regressão do frontend.

## Decisões

### D-01 — Candidato do modelo, recomendação final do agente

O LLM produz uma proposta limitada por IDs. Identidade, referências completas,
scores e níveis finais são calculados localmente. Isso reduz a superfície em que
uma saída convincente, porém incompatível, poderia entrar no estado.

### D-02 — Evidência dupla obrigatória

A evidência da startup demonstra a necessidade e a relevância. A documentação
NVIDIA demonstra a capacidade da tecnologia. Uma sem a outra não sustenta uma
recomendação e não pode ser compensada por confiança do modelo.

### D-03 — Necessidade técnica validada substitui gap ausente

O fluxo atual não possui um agente dedicado de gaps. Um `technical_need` que
sobreviveu ao Evidence Validator já é uma necessidade identificada e pode ser
usado. `technical_gaps` adicionais só entram quando seus IDs resolvem para
evidências aprovadas da mesma startup.

### D-04 — Classificação opcional, afirmações de maturidade condicionais

O roteamento solicitado exige perfil e contexto suficiente, não classificação.
A maturidade validada enriquece a análise; sua ausência é explícita e impede que a
justificativa a utilize, mas não descarta uma necessidade independente e bem citada.

### D-05 — Prioridade e complexidade calculadas por funções puras

Fatores semânticos são propostos com referências, enquanto scores e níveis são
derivados por tabelas fixas. Testes podem provar todos os resultados sem chamar LLM.

### D-06 — Lote atômico por startup

Uma duplicata ou referência fabricada invalida o lote da startup e aciona reparo.
Não publicar parte de um lote semanticamente inconsistente evita seleção arbitrária.
Lotes válidos de outras startups permanecem preservados.

### D-07 — Lista vazia é resultado válido

O agente pode concluir que o contexto limitado não sustenta correspondência. Esse
resultado gera aviso, não erro, e é preferível a forçar uma tecnologia.

### D-08 — Testes sem tokens

Todos os testes padrão usam fakes e JSONs compactos. Credenciais no ambiente não
ativam Groq nem qualquer outro cliente; testes externos exigem opt-in explícito.

## Verificação prevista

1. Validar contratos, enums, limites e invariantes.
2. Executar testes tabulares de prioridade e complexidade.
3. Testar elegibilidade, allowlists e associação por startup.
4. Testar cenários representativos com fakes de respostas mínimas.
5. Testar saída vazia, incompatibilidade, duplicata, reparo e falha do provedor.
6. Testar grafo, estado, API, OpenAPI e códigos HTTP.
7. Executar Ruff format/check, mypy e import-linter.
8. Executar suíte offline e cobertura mínima de 80%.
9. Executar lint, testes e build do frontend.
10. Revisar todos os critérios antes de solicitar aprovação da entrega.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| LLM recomendar tecnologia conhecida, mas não recuperada | Enum + allowlist exata de chunks |
| Mistura de startups | Particionamento e validação obrigatória de `startup_id` |
| Justificativa genérica | Necessidade e evidência de negócio obrigatórias |
| Prioridade arbitrária | Fatores citados e cálculo determinístico |
| Complexidade otimista sem dados | Fatores obrigatórios; ausência rejeita candidato |
| Duplicatas com textos diferentes | Unicidade por startup/tecnologia |
| Prompt injection em documento | Delimitação, instrução de dados e pós-validação |
| Contexto ou prompt excessivo | Limites e truncamento determinístico |
| Testes consumirem tokens | Fakes, guardas e testes externos opt-in |

## Resultado da execução

- O contrato cru ficou restrito a chaves, fatores e UUIDs permitidos; identidade,
  referências completas, maturidade, scores e níveis finais são derivados localmente.
- O limite de caracteres trunca apenas a representação enviada ao modelo. As
  evidências finais continuam sendo resolvidas sem alteração a partir do estado.
- A validação semântica conservadora exige sobreposição explícita entre necessidade,
  documentação e justificativas, além de bloquear promessas, estimativas não
  validadas, maturidade ausente e ações fora do escopo.
- Verificação concluída com Ruff, mypy, import-linter, 299 testes offline (89,45% de
  cobertura), 3 testes de integração e lint, teste e build do frontend.

T-41 permanece aberta até a aprovação explícita da entrega, conforme o critério de
conclusão da especificação.

## Evoluções posteriores

- Briefing Agent e narrativa executiva com as mesmas citações;
- exportação PDF ou apresentação mediante spec própria;
- feedback humano sobre aceitação e prioridade;
- avaliação offline de qualidade com dataset ampliado;
- persistência e histórico de recomendações, se necessário.

## Sugestão de commit

`feat(recommendation): generate grounded NVIDIA recommendations`
