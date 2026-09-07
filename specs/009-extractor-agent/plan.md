# Plano 009: Extractor Agent

## Status

Implementação executada, verificada e aprovada em 7 de setembro de 2026.

## Estratégia

Criar contratos Pydantic imutáveis para perfis e fatos citados, implementar um
`ExtractorAgent` que usa o `ChatModel` rápido por injeção e validar cada referência
contra as fontes permitidas. O agente processará uma startup por chamada para
isolar contexto e falhas.

O grafo ganhará uma decisão pura após o Retriever. Somente a presença simultânea
de candidatos e fontes apropriadas encaminhará ao Extractor. O fluxo terminará
após essa etapa até que uma especificação futura implemente o Startup Classifier.

## Arquitetura dentro do escopo

```text
application/contracts/extraction.py
  ├── ProfileField
  ├── ExtractionSource
  ├── ExtractedFact
  ├── ExtractorOutput
  └── StructuredStartupProfile

graph/agents/extractor.py
  ├── agrupamento e limites de contexto
  ├── chamada ao ChatModel
  ├── parsing e reparo
  ├── validação de referências permitidas
  └── atualização parcial do AppState

graph/prompts/extractor.py
  ├── prompt versionado
  ├── contexto delimitado por startup e fonte
  └── prompt de reparo
```

## Contratos e rastreabilidade

`SourceReference` será evoluído para incluir `startup_id`. O Retriever preencherá
esse UUID diretamente do `StartupDocument.startup_id`. Todos os testes e
construtores existentes serão atualizados.

O objeto retornado pelo modelo conterá fatos e referências. O agente validará:

1. schema e limites do texto;
2. ausência de campos extras;
3. referência com UUID e URL fornecidos no contexto;
4. vínculo da referência com a startup em processamento;
5. ao menos uma referência por fato;
6. coerência entre campos preenchidos e `unknown_fields`.

O agente comporá `startup_id` e nome final a partir do candidato, impedindo que a
saída do modelo substitua a identidade da startup.

## Contexto enviado ao modelo

As fontes serão agrupadas pela startup e mantidas na ordem do estado. Cada bloco
terá somente identificador, URL, título e `excerpt`. O `excerpt` será o conteúdo
documental efetivamente analisado pelo modelo para preencher os campos
estruturados; os demais valores servem para identidade, apresentação e
rastreabilidade. Quantidade de fontes e total de caracteres serão limitados por
`ExtractorConfig`.

O truncamento será determinístico: manter a ordem, limitar a quantidade e cortar
o último trecho necessário para respeitar o orçamento. O evento produzirá aviso,
mas UUID e URL da fonte usada permanecerão disponíveis para citação.

## Execução e falhas parciais

O agente percorrerá candidatos na ordem recebida. Startup sem fonte será ignorada
com aviso. Para cada candidata processável:

1. construir contexto permitido;
2. chamar o modelo rápido;
3. validar saída e referências;
4. realizar no máximo um reparo configurado;
5. adicionar o perfil ou registrar erro sanitizado.

Uma falha não remove perfis já produzidos. Para manter implementação simples e
ordem determinística, as chamadas serão sequenciais nesta entrega. Concorrência
controlada poderá ser avaliada posteriormente.

## Configuração

Adicionar `ExtractorConfig` a `Settings` e ao `.env.example`, contendo:

- máximo de fontes por startup;
- máximo de caracteres de contexto por startup;
- tamanho máximo de um fato;
- máximo de itens por lista;
- máximo de tentativas de reparo, limitado a zero ou um.

Os valores exatos serão definidos com defaults conservadores e testes de limites.

## Composição e grafo

O composition root criará uma única instância do Extractor com
`ModelRegistry.resolve(NodeName.EXTRACTOR)`. O builder passará a receber três nós:
Query Planner, Retriever e Extractor.

`route_after_retriever` verificará candidatos e fontes apropriadas. A decisão não
alterará o estado. O aviso para ausência total de fontes será produzido pelo
Retriever, que já conhece os documentos recuperados.

## API

`SearchResponse` ganhará `structured_profiles`. O mapeamento compartilhado de
status incluirá `extractor_invalid_output → 502` e
`extractor_unavailable → 503`. Resultados sem fontes continuam HTTP 200.

## Testes planejados

- serialização e invariantes de todos os contratos de extração;
- fatos nulos/vazios e `unknown_fields` coerentes;
- múltiplas fontes válidas e deduplicação;
- UUID, URL ou startup não permitidos são rejeitados;
- construção segura e limitada do contexto;
- uso exclusivo do modelo `llm_fast`;
- sucesso com uma e várias startups;
- startup sem fonte e conjunto misto de candidatas;
- saída inválida, reparo bem-sucedido e reparo esgotado;
- indisponibilidade do modelo e sanitização de logs/erros;
- métricas e preservação de diagnósticos anteriores;
- topologia e decisões do LangGraph;
- API, OpenAPI e códigos HTTP;
- integração do fluxo com Retriever real e modelo falso.

## Verificação

1. Executar testes unitários de contratos, agente, prompt, grafo e API.
2. Executar integração com PostgreSQL real e modelo falso.
3. Executar Ruff format/check, mypy e import-linter.
4. Executar cobertura do backend com mínimo de 80%.
5. Executar lint, testes e build do frontend.
6. Revisar critérios, logs, OpenAPI e documentação.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Modelo inventar fonte | Validar UUID, URL e startup contra allowlist local |
| Trecho insuficiente omitir informação | Manter campos desconhecidos e aviso; não buscar externamente |
| Contexto exceder limite do modelo | Limites configuráveis e truncamento determinístico |
| Falha de uma startup descartar as anteriores | Acumular perfis validados antes do erro |
| Fontes de startups se misturarem | Uma chamada e uma allowlist separada por startup |
| API expor objetos internos | Response models explícitos e testes OpenAPI |

## Evoluções posteriores

- aresta Extractor → Startup Classifier;
- processamento concorrente com limite explícito;
- persistência ou cache de perfis;
- recuperação de conteúdo documental adicional;
- validação factual e cálculo de confiança.

## Resultado da implementação

- Contratos estritos e imutáveis adicionados, com lacunas e citações validadas.
- Extractor conectado ao LangGraph após o Retriever por roteamento condicional.
- Perfis estruturados expostos em `/api/v1/search`, com erros 502/503 mapeados.
- Testes unitários, arquitetura, Ruff, mypy e integração PostgreSQL aprovados.
- Cobertura do backend verificada acima do mínimo de 80% e frontend validado por
  lint, testes e build.

## Sugestão de commit

`feat(extractor): structure startup profiles from retrieved sources`
