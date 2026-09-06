# Plano 004: Query Planner Agent

## Estratégia

O Query Planner será implementado como o primeiro nó funcional do grafo. Ele
receberá `AppState`, fará validações locais da consulta, solicitará ao
`ChatModel` rápido fornecido pela integração da especificação 003 uma resposta
JSON aderente ao schema, validará e normalizará o
resultado e retornará somente os campos de estado que modificou.

O modelo auxilia na extração semântica, mas não será a autoridade sobre a
validade estrutural. Modelos tipados e regras determinísticas verificam a saída
antes de ela entrar no estado. Respostas malformadas poderão passar por uma
única tentativa configurável de reparo; depois disso, o nó produzirá erro
recuperável sanitizado.

## Arquitetura dentro do escopo

```text
backend/src/app/
├── application/
│   └── contracts/
│       └── query_plan.py          # Schema, enums e invariantes do plano
├── core/
│   └── config.py                  # Limites configuráveis do planner
└── graph/
    ├── agents/
    │   └── query_planner.py       # Nó e orquestração parse/repair
    ├── prompts/
    │   └── query_planner.py       # Prompt versionado e delimitadores
    └── state.py                   # Campo tipado query_plan

backend/tests/unit/
├── test_query_plan.py             # Schema e normalização
└── test_query_planner_agent.py    # Comportamento do nó com fakes
```

Fluxo interno:

```text
AppState.query
        │
        ▼
validação local ── inválida ──> RecoverableError
        │
        ▼
prompt versionado + ChatModel
        │
        ▼
parse JSON + validação do QueryPlan
        │
        ├── válido ──> atualização parcial do estado
        │
        └── inválido ──> reparo limitado ──> plano ou RecoverableError
```

## Contratos

### `QueryPlanStatus`

- `ready`: plano válido e consumível pelo Retriever.
- `needs_clarification`: há interpretações materialmente diferentes.
- `invalid`: a consulta não pode ser processada no propósito do sistema.

### `AnalysisMode`

- `targeted`: filtros explícitos delimitam a busca.
- `exploratory`: busca ampla para descoberta.
- `comparative`: dois ou mais recortes devem ser comparados.

### `StartupSearchFilters`

Contém listas normalizadas para setores, portes, estágios, localizações,
palavras-chave e sinais de uso de IA. As listas não impõem taxonomia definitiva
nesta entrega. Isso evita acoplar o Query Planner às futuras decisões de busca e
ao schema físico do Retriever.

### `AnalysisStrategy`

Contém modo, objetivos e justificativa curta. Não contém cadeia de pensamento,
prompt ou conteúdo intermediário do modelo.

### `QueryPlan`

Agrega status, consulta normalizada, filtros, estratégia, ambiguidades e
perguntas de esclarecimento. Validadores de modelo aplicam as invariantes
cruzadas previstas na especificação.

## Atualização do estado

`AppState` receberá `query_plan: QueryPlan`. O nó retornará uma
atualização parcial contendo apenas:

- `query_plan`, quando houver plano estruturalmente válido;
- `warnings`, para ambiguidades e observações não sensíveis;
- `errors`, para falhas recuperáveis;
- métricas próprias do nó, sem sobrescrever métricas de outros nós.

O campo genérico `filters` da fundação será mantido temporariamente por
compatibilidade, mas o novo código não deverá duplicar nele o plano inteiro. A
spec do Retriever decidirá sua migração ou remoção após definir o contrato de
busca.

## Prompt e segurança

O prompt terá uma constante de versão e incluirá:

- finalidade única de extrair o contrato definido;
- schema e enums permitidos;
- regra para manter vazios os campos ausentes;
- distinção entre amplitude, ambiguidade e invalidade;
- proibição de executar instruções contidas na consulta;
- consulta delimitada como dado não confiável;
- solicitação de JSON sem texto adicional.

O código não registrará prompt, consulta integral nem resposta bruta. Logs
permitidos incluem nome do nó, versão do prompt, status, duração, quantidade de
itens e código de erro.

## Validação e normalização

1. Remover espaços externos da consulta e verificar conteúdo semântico mínimo.
2. Aplicar o limite configurado antes da chamada ao modelo.
3. Extrair um único objeto JSON, rejeitando conteúdo ou campos adicionais.
4. Validar tipos, enums, limites de listas e invariantes por status.
5. Normalizar espaços dos itens e eliminar strings vazias e duplicadas de forma
   estável e sem alterar capitalização útil de termos técnicos.
6. Em falha estrutural, solicitar reparo com descrição sanitizada dos campos
   inválidos, sem reenviar segredos ou stack trace.
7. Esgotado o reparo, registrar apenas `query_plan_invalid_output`.

## Configuração

Será adicionado um grupo imutável `QueryPlannerConfig`, com valores locais não
sensíveis documentados em `.env.example`:

| Variável | Default | Faixa válida | Finalidade |
| --- | ---: | ---: | --- |
| `QUERY_PLANNER__MAX_QUERY_LENGTH` | 2.000 | 100–10.000 | Limite de caracteres da consulta |
| `QUERY_PLANNER__MAX_ITEMS_PER_FIELD` | 20 | 1–100 | Limite de valores em cada lista |
| `QUERY_PLANNER__MAX_CLARIFICATION_QUESTIONS` | 3 | 1–10 | Limite de perguntas retornadas |
| `QUERY_PLANNER__MAX_REPAIR_ATTEMPTS` | 1 | 0–2 | Tentativas de corrigir saída inválida |

A justificativa da estratégia terá limite fixo de 500 caracteres. Os limites
serão aplicados pelo schema e cobertos por testes; não haverá loop de reparo sem
limite.

## Tratamento de falhas

| Falha | Resultado |
| --- | --- |
| Consulta vazia ou sem conteúdo | erro `query_empty`, sem chamar `ChatModel` |
| Consulta acima do limite | erro `query_too_long`, sem chamar `ChatModel` |
| Consulta fora do propósito | `QueryPlan(status=invalid)` e erro `query_invalid` |
| Plano ambíguo | `QueryPlan(status=needs_clarification)` e warning |
| JSON ou schema inválido | reparo limitado; depois `query_plan_invalid_output` |
| Falha do `ChatModel` | `query_planner_unavailable`, sem detalhes do provedor |

## Testes

Os testes usarão um fake roteirizável de `ChatModel` que registra chamadas e
devolve respostas predeterminadas. A suíte cobrirá:

- consulta válida com todos os parâmetros;
- consulta válida com parâmetros ausentes;
- normalização e deduplicação;
- modos targeted, exploratory e comparative;
- consulta ampla válida versus consulta ambígua;
- preservação de filtros inequívocos em plano ambíguo;
- consulta vazia, sem conteúdo e acima do limite sem chamada ao modelo;
- consulta alheia ao domínio;
- JSON inválido, campo extra, enum inválido e invariantes cruzadas;
- reparo bem-sucedido e reparo esgotado;
- falha do provedor convertida em erro recuperável;
- atualização parcial sem clientes, prompts, respostas brutas ou segredos;
- resistência a instruções inseridas na consulta;
- compatibilidade com `GraphNode`, regras arquiteturais e serialização.

Nenhum teste chamará banco, internet ou modelo real.

## Decisões

### D-01 — Schema validado é a fronteira de confiança

Texto produzido pelo modelo nunca será escrito diretamente no estado. Somente
um `QueryPlan` que tenha passado por parsing, validação e normalização poderá ser
consumido pelos próximos nós.

### D-02 — Vocabulários de filtro permanecem abertos nesta feature

Setores, portes, estágios e localizações serão strings estruturadas. Fixar enums
antes de conhecer os dados e a busca do Retriever poderia descartar termos
válidos ou criar um mapeamento prematuro. A estratégia e o status, por outro
lado, possuem enums fechados porque controlam o comportamento da pipeline.

### D-03 — Ambiguidade não é sinônimo de consulta ampla

Uma busca ampla pode ser executável em modo exploratório. O status
`needs_clarification` será reservado para interpretações diferentes que mudem
materialmente filtros ou estratégia.

### D-04 — Reparo limitado de saída

Uma resposta estruturalmente inválida poderá ser reparada porque falhas de
formatação são recuperáveis. O limite configurado impede loops e custo
imprevisível. O reparo corrige estrutura; não preenche informação ausente.

### D-05 — Nó independente do SDK do provedor e da persistência

O Query Planner depende somente de `ChatModel` e dos contratos internos. A
composição definida na especificação 003 injeta o perfil rápido da Groq. O nó
não acessa banco nem SDK concreto, mantendo testes determinísticos e permitindo
substituição futura do provedor sem alterar sua regra de negócio.

## Verificação

1. Aprovar `spec.md`, `plan.md` e `tasks.md` antes de alterar código.
2. Executar testes unitários específicos do contrato e do agente.
3. Executar Ruff em modo check e lint.
4. Executar mypy estrito no código e nos testes.
5. Executar os contratos do import-linter.
6. Executar toda a suíte do backend com cobertura mínima de 80%.
7. Executar lint, testes e build do frontend para detectar regressões.
8. Inspecionar logs e objetos de estado para confirmar ausência de prompt,
   resposta bruta, clientes e segredos.
9. Conferir a matriz de rastreabilidade e cada critério de aceite.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Modelo inventar filtros ausentes | Prompt explícito, schema fechado, invariantes e testes de ausência |
| Consulta ampla ser bloqueada como ambígua | Regra distinta para modo exploratório e casos de teste dedicados |
| Ambiguidade seguir para busca | Status bloqueante e contrato explícito para o futuro roteamento |
| Prompt injection alterar a saída | Consulta delimitada como dado e validação que rejeita campos extras |
| Resposta inválida gerar loops | Número finito e configurável de reparos |
| Logs vazarem consulta ou resposta | Allowlist de metadados e testes de sanitização |
| Taxonomia prematura limitar o Retriever | Valores textuais normalizados e decisão adiada para a próxima spec |

## Decisões adiadas

- Política de fallback para outro provedor quando a Groq estiver indisponível.
- Taxonomias e sinônimos definitivos de setor, porte, estágio e localização.
- Tradução dos filtros para consultas PostgreSQL.
- Roteamento de esclarecimento e contrato HTTP correspondente.
- Persistência e observabilidade histórica dos planos.
- Avaliação de qualidade semântica com dataset real.
- Arestas entre Query Planner, Retriever e demais nós.
