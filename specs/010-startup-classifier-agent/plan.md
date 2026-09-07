# Plano 010: Startup Classifier Agent

## Status

Implementação executada e verificada em 7 de setembro de 2026. A aprovação final
da entrega permanece pendente.

## Estratégia

Criar contratos Pydantic imutáveis para classificação, confiança e sinais. O
`StartupClassifierAgent` processará um perfil por vez com o `llm_heavy`, usando
somente o perfil e os excerpts associados à mesma startup. Referências e
coerência mínima da categoria serão verificadas localmente.

Perfis sem qualquer fato sustentado terão resultado incerto determinístico sem
chamada ao modelo. Nos demais casos, o modelo aplicará a taxonomia documentada;
uma saída inválida poderá receber um único reparo.

## Arquitetura dentro do escopo

```text
application/contracts/classification.py
  ├── ClassificationStatus
  ├── ConfidenceLevel
  ├── ClassificationSignalType
  ├── ClassificationSignal
  ├── ClassifierOutput
  └── StartupClassification

graph/agents/startup_classifier.py
  ├── isolamento de perfil e fontes
  ├── classificação e incerteza determinística
  ├── parsing, coerência e reparo
  ├── validação das referências
  └── atualização parcial do AppState

graph/prompts/startup_classifier.py
  ├── taxonomia e prompt versionado
  ├── perfil e excerpts delimitados
  └── prompt de reparo
```

## Regras locais de coerência

Após validar o JSON, o agente aplicará invariantes independentes do modelo:

1. `classified` exige categoria não nula e confiança `medium` ou `high`;
2. `uncertain` exige categoria nula e confiança `low`;
3. `ai-native` exige `core_ai_dependency`;
4. `ai-enabled` exige `supporting_ai_use`;
5. `non-ai` exige `explicit_non_ai`;
6. conflito exige resultado incerto;
7. todas as referências devem pertencer à startup e às fontes fornecidas;
8. a lista agregada de evidências é composta localmente na ordem das fontes.

Essas regras verificam coerência estrutural, não a verdade definitiva do texto.

## Contexto e limites

Cada chamada conterá um único `StructuredStartupProfile` serializado e somente
os `excerpt`s apropriados da mesma startup. O contexto preservará a ordem de
`selected_sources` e terá limites de quantidade e caracteres. O último trecho
poderá ser cortado deterministicamente para respeitar o orçamento.

O prompt tratará os excerpts como dados não confiáveis, nunca como instruções, e
proibirá conhecimento externo, navegação, recomendações e validação factual.

## Falhas e resultados parciais

O agente percorrerá os perfis na ordem recebida. Para cada perfil:

1. verificar se existe algum fato sustentado;
2. produzir incerteza local se não houver informação utilizável;
3. montar contexto isolado;
4. chamar o modelo e validar a saída;
5. reparar no máximo uma vez;
6. acumular a classificação ou registrar erro recuperável.

Falhas não removerão classificações já concluídas nem modificarão perfis.

## Configuração

Adicionar `StartupClassifierConfig` a `Settings` e ao `.env.example` com:

- máximo de fontes por startup;
- máximo de caracteres de contexto;
- tamanho máximo da justificativa;
- máximo de sinais;
- tamanho máximo da descrição de sinal;
- máximo de tentativas de reparo, restrito a zero ou um.

## Grafo e composição

Adicionar `route_after_extractor`, registrar `startup_classifier` e substituir a
aresta direta Extractor → END pela decisão Extractor → Classifier/END. O
composition root criará uma única instância do agente com
`ModelRegistry.resolve(NodeName.STARTUP_CLASSIFIER)`.

## API

Evoluir `SearchResponse.classifications` para o novo contrato explícito. Mapear
`classifier_invalid_output` para 502 e `classifier_unavailable` para 503. O
OpenAPI deverá expor todos os enums e contratos.

## Testes planejados

- contratos, serialização, campos extras e invariantes de status/categoria;
- critérios positivos de `ai-native`, `ai-enabled` e `non-ai`;
- ausência de IA sem evidência positiva resulta incerta;
- informação insuficiente, menção futura e conflito;
- sinais, referências inválidas, associação e ordem das fontes;
- perfil vazio sem chamada ao modelo;
- reparo bem-sucedido, reparo esgotado e indisponibilidade;
- preservação de perfis e classificações anteriores;
- limites, truncamento, métricas e logs sanitizados;
- resolução do `llm_heavy` pela política central;
- topologia e roteamento do LangGraph;
- API, OpenAPI e mapeamento HTTP;
- integração Retriever → Extractor → Classifier com modelos falsos;
- qualidade, cobertura e regressão do frontend.

## Verificação

1. Executar testes unitários de contratos, agente, prompt, grafo e API.
2. Executar integração com PostgreSQL real e modelos falsos.
3. Executar Ruff format/check, mypy e import-linter.
4. Executar cobertura do backend com mínimo de 80%.
5. Executar lint, testes e build do frontend.
6. Revisar critérios, logs, OpenAPI e documentação.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Ausência de sinal virar `non-ai` | Exigir `explicit_non_ai`; caso contrário, incerteza |
| Modelo usar conhecimento prévio | Contexto fechado, prompt explícito e validação de referências |
| Confundir IA central e habilitadora | Tipos de sinal obrigatórios por categoria |
| Misturar fontes entre empresas | Uma chamada e uma allowlist por startup |
| Alterar fatos ao classificar | Atualização parcial somente de classificações e diagnósticos |
| Expor conteúdo em logs | Logs restritos a metadados operacionais |

## Evoluções posteriores

- aresta Classifier → Evidence Validator;
- calibração empírica dos níveis de confiança;
- processamento concorrente com limite explícito;
- persistência ou auditoria histórica das classificações.

## Resultado da implementação

- Contratos estritos de categoria, incerteza, confiança, sinais e referências.
- Classifier conectado ao LangGraph após o Extractor por roteamento condicional.
- Uso conservador de `non-ai`, exigindo evidência positiva em vez de silêncio.
- Classificações expostas em `/api/v1/search`, com erros 502/503 mapeados.
- Testes, integração PostgreSQL, qualidade, cobertura e frontend aprovados.

## Sugestão de commit

`feat(classifier): classify structured startup profiles from evidence`
