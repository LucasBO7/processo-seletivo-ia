# Plano 011: Evidence Validator Agent

## Status

Implementação executada e verificada em 7 de setembro de 2026. A aprovação final
da entrega permanece pendente.

## Estratégia

Enumerar localmente todos os fatos do perfil com chaves determinísticas e enviar,
por startup, os itens, a classificação e os excerpts apropriados ao `llm_fast`.
O modelo avaliará suporte documental; o agente validará cobertura total, coerência
dos status e allowlist de fontes antes de compor resultados finais.

O perfil e a classificação originais nunca serão modificados. Novas coleções
`validated_*` formarão a fronteira segura para os agentes posteriores.

## Arquitetura dentro do escopo

```text
application/contracts/evidence_validation.py
  ├── EvidenceStatus
  ├── SourceVerdict
  ├── SourceAssessment
  ├── ClaimAssessmentOutput
  ├── ValidatorOutput
  ├── ClaimValidation
  ├── ClassificationValidation
  └── ValidatedStartupProfile

graph/agents/evidence_validator.py
  ├── enumeração de afirmações
  ├── agrupamento de perfil, classificação e fontes
  ├── validações determinísticas de lacunas
  ├── parsing, cobertura, allowlist e reparo
  ├── composição de perfis filtrados
  └── atualização parcial do AppState

graph/prompts/evidence_validator.py
  ├── semântica dos quatro status
  ├── itens e excerpts delimitados
  └── prompt de reparo
```

## Enumeração de afirmações

O agente percorrerá os campos na ordem do contrato:

1. `product`;
2. `business_model`;
3. `sector`;
4. `target_audience`;
5. `ai_use_cases`;
6. `technologies`;
7. `infrastructure`;
8. `external_dependencies`;
9. `technical_needs`;
10. `claims`.

Campos escalares usam o próprio nome como `claim_key`. Listas usam índice, como
`technologies[0]`. A classificação usa a chave reservada `classification`. Chave,
texto, campo e identidade são controlados pelo agente.

## Contexto e fontes

Cada chamada processará uma startup. O contexto incluirá os itens enumerados, a
classificação recebida, quando existir, e os `excerpt`s recuperados para a mesma startup. Títulos,
URLs e identificadores são metadados e não sustentam afirmações sozinhos.

Classificação ausente será registrada localmente como `insufficient`, sem impedir
a validação das afirmações extraídas. Fontes sem URL ou excerpt serão excluídas do contexto analisável, mas produzirão
lacuna e aviso. Limites de fontes, itens e caracteres serão determinísticos. Se o
truncamento impedir avaliação suficiente, o resultado afetado não poderá ser
promovido a `supported`. Para manter a decisão auditável, itens que excederem o
limite configurado serão registrados localmente como `insufficient`, nunca
omitidos.

## Validação local

O agente verificará:

1. schema estrito e limites;
2. conjunto exato de chaves solicitadas;
3. uma avaliação por chave;
4. referências pertencentes à startup e a `selected_sources`;
5. `supported`: ao menos um `supports`, nenhum `contradicts`;
6. `conflicting`: ao menos um `supports` e um `contradicts`;
7. `unsupported`: zero `supports` e documento analisável;
8. `insufficient`: nenhuma base documental adequada;
9. justificativa não vazia e sanitizada;
10. composição final a partir dos fatos originais, nunca do texto do modelo.

## Perfil e coleções derivadas

O agente reconstruirá cada `ValidatedStartupProfile` copiando apenas fatos cuja
avaliação seja `supported`. A ordem original será mantida e `unknown_fields` será
recalculado. O texto virá do fato original e suas referências serão compostas
somente a partir das fontes avaliadas como `supports`.

As listas de diagnóstico serão derivadas de `claim_validations`, evitando
divergência entre cópias:

- `validated_claims`: `supported`;
- `rejected_claims`: `unsupported`;
- `conflicting_claims`: `conflicting`;
- `evidence_gaps`: `insufficient`.

`validated_classifications` será derivada apenas de classificações com suporte.

## Falhas e reparo

Uma saída inválida receberá no máximo um reparo. O reparo conterá schema, chaves e
fontes permitidas, além da saída candidata delimitada. Falhas serão sanitizadas e
não descartarão startups já concluídas.

Quando perfil, classificação ou fontes não oferecerem dados analisáveis, o agente
produzirá resultados `insufficient` localmente sempre que isso puder ser feito sem
modelo.

## Configuração

Adicionar `EvidenceValidatorConfig` com:

- máximo de fontes por startup;
- máximo de itens por startup;
- máximo de caracteres de contexto;
- tamanho máximo da justificativa;
- máximo de tentativas de reparo, limitado a zero ou um.

## Grafo e composição

Adicionar `route_after_classifier`, baseado na presença de perfis, e substituir
Classifier → END por Classifier → Validator/END. O composition root criará uma instância reutilizável com
`ModelRegistry.resolve(NodeName.EVIDENCE_VALIDATOR)`. O Validator termina em
`END` nesta entrega.

## API

Adicionar à `SearchResponse` os perfis e classificações validados, todas as
avaliações e as coleções separadas. Mapear saída inválida para 502 e
indisponibilidade para 503. Ausência de fatos aprovados permanece HTTP 200.

## Testes planejados

- enumeração determinística de todos os campos e índices;
- contratos, campos extras, chaves ausentes, duplicadas e desconhecidas;
- regras de `supported`, `unsupported`, `conflicting` e `insufficient`;
- múltiplas fontes, deduplicação, ordem e associação incorreta;
- URL ausente, excerpt vazio, fonte ausente e truncamento;
- classificação suportada, rejeitada, conflitante e incerta;
- composição do perfil somente com fatos aprovados;
- separação de rejeitados, conflitos e lacunas;
- nenhuma afirmação sobrevivente e aviso correspondente;
- reparo, falha do provedor e preservação de resultados parciais;
- métricas, logs sanitizados, limites e uso do `llm_fast`;
- topologia e roteamento do LangGraph;
- API, OpenAPI e códigos HTTP;
- integração PostgreSQL com modelos falsos;
- qualidade, cobertura e regressão do frontend.

## Verificação

1. Executar testes unitários de contratos, agente, prompt, grafo e API.
2. Executar integração real do fluxo com modelos falsos.
3. Executar Ruff format/check, mypy e import-linter.
4. Executar cobertura mínima de 80%.
5. Executar lint, testes e build do frontend.
6. Revisar critérios, logs, OpenAPI e documentação.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Confundir suporte com verdade | Linguagem explícita e escopo documental |
| Modelo omitir afirmação | Validar conjunto exato de chaves |
| Evidência fabricada | Allowlist local de UUID, URL e startup |
| Contradição ser descartada | Status e lista próprios para conflitos |
| Rejeitado chegar ao próximo agente | Fronteira `validated_profiles` obrigatória |
| Truncamento gerar falso suporte | Bloquear promoção quando contexto for materialmente insuficiente |
| Alterar dados de auditoria | Reconstruir saídas sem mutar entradas |

## Evoluções posteriores

- aresta Validator → NVIDIA RAG;
- políticas configuráveis de quorum entre fontes;
- revisão humana de conflitos;
- persistência e histórico de decisões.

## Resultado da implementação

- Afirmações e classificações recebem avaliações documentais estruturadas.
- Perfis validados contêm somente fatos `supported`, com fontes de suporte.
- Rejeições, conflitos e lacunas são preservados em coleções separadas.
- Em indisponibilidade do modelo, fatos que aparecem literalmente nas fontes
  originalmente citadas permanecem aprovados por um fallback local conservador;
  classificações e fatos sem correspondência literal continuam insuficientes.
- Validator conectado ao LangGraph após o Classifier e exposto na API de busca.
- Testes, integração PostgreSQL, qualidade, cobertura e frontend aprovados.

## Sugestão de commit

`feat(validator): validate documentary support for startup claims`
