# Especificação 008: taxonomia canônica de filtros

## Status

Proposta. Esta especificação precisa de aprovação explícita antes da
implementação.

## Contexto

O Query Planner atualmente produz filtros textuais livres e o Retriever compara
setor, estágio e localização literalmente, ignorando apenas diferenças entre
maiúsculas e minúsculas. Com isso, uma consulta por "meio financeiro" pode gerar
o setor `Financial`, enquanto o PostgreSQL contém rótulos como
`Fintech / Crédito` e `SaaS de Gestão Financeira`, resultando em uma busca vazia.

Os valores persistidos também misturam conceitos e granularidades. Por exemplo,
`Conversational AI / CPaaS` representa mais de uma categoria e `Growth
(soonicorn)` é uma variação de estágio. A busca precisa usar um vocabulário
controlado sem exigir que a pessoa conheça os rótulos internos do banco.

## Objetivos

- Definir Enums canônicos para setor, estágio e porte.
- Restringir o Query Planner a filtros reconhecidos pelo sistema.
- Resolver sinônimos em português e inglês para valores canônicos.
- Associar uma categoria canônica a um ou mais rótulos existentes no banco.
- Preservar localização, palavras-chave e sinais de IA como campos textuais.
- Manter compatibilidade com a rota `/api/v1/search` e os dados existentes.

## Histórias do usuário

### US-01 — Planejar com filtros válidos

Como pessoa usuária, quero que termos naturais sejam convertidos em opções
conhecidas para evitar buscas vazias causadas por traduções ou rótulos
inventados.

Critérios de aceite:

- `sectors`, `stages` e `company_sizes` usam Enums canônicos no contrato do
  `QueryPlan`.
- A representação JSON dos Enums usa identificadores estáveis em inglês e
  `snake_case`.
- O prompt informa valores permitidos, descrições e aliases relevantes.
- Uma saída do modelo com valor desconhecido não chega ao Retriever.
- Um alias reconhecido pode ser convertido em um ou mais valores canônicos.
- Valores repetidos após expansão são removidos com ordem determinística.
- Campos não solicitados continuam vazios; a taxonomia não autoriza inventar
  filtros ausentes na consulta.

### US-02 — Pesquisar por sinônimos de setor

Como pessoa usuária, quero pesquisar usando termos como "financeiro",
"fintech", "trading" ou `financial` para encontrar startups pertencentes à
categoria financeira cadastrada.

Critérios de aceite:

- Os aliases são comparados sem diferença de caixa ou acentos.
- `financeiro`, `finanças`, `financial`, `fintech`, `crédito`, `trading` e
  `investimentos` resolvem para `financial_services`.
- `financial_services` encontra, inicialmente, rótulos persistidos como
  `Fintech / Crédito` e `SaaS de Gestão Financeira`.
- Uma categoria pode mapear vários rótulos do banco e um rótulo composto pode
  participar de mais de uma categoria.
- Sinônimos são declarados em uma única taxonomia testável, e não espalhados em
  prompts, agentes e queries SQL.

### US-03 — Normalizar estágio e porte

Como pessoa usuária, quero que variações comuns de estágio e porte tenham
comportamento previsível.

Critérios de aceite:

- O Enum de estágio contém inicialmente `pre_seed`, `seed`, `series_a`,
  `series_b`, `series_c`, `growth`, `late_stage`, `public`, `acquired` e
  `business_unit`.
- Variações como `Série C`/`Series C`, `Growth (soonicorn)`,
  `Empresa listada (Nasdaq)` e `Adquirida (M&A pela B3)` são associadas ao
  estágio canônico correspondente.
- O Enum de porte contém `micro`, `small`, `medium` e `large`.
- Os intervalos permanecem: micro 1–10, small 11–50, medium 51–200 e large a
  partir de 201 pessoas.
- Intervalos numéricos explícitos continuam aceitos como critério adicional de
  porte, sem serem transformados em um Enum incorreto.

### US-04 — Consultar dados existentes sem migração destrutiva

Como pessoa mantenedora, quero adotar a taxonomia sem perder ou reescrever os
rótulos importados.

Critérios de aceite:

- Os valores originais de `startups.sector`, `stage` e `location` permanecem
  preservados.
- O Retriever traduz categorias canônicas para os rótulos reconhecidos na
  persistência antes de montar a consulta parametrizada.
- Valores persistidos ainda não mapeados continuam aparecendo em buscas sem
  filtro e não causam erro de execução.
- A taxonomia pode ser ampliada por mudança explícita de código, testes e spec,
  sem alteração automática baseada em conteúdo gerado pela IA.
- Esta feature não cria nem altera tabelas PostgreSQL.

### US-05 — Manter resultados e falhas explicáveis

Como pessoa operadora, quero saber quando um filtro foi normalizado ou rejeitado
sem receber detalhes internos ou resultados arbitrários.

Critérios de aceite:

- A resposta mantém o `QueryPlan` com valores canônicos efetivamente usados.
- Aliases reconhecidos podem adicionar o aviso `query_filter_normalized`.
- Valor desconhecido após a tentativa de reparo produz
  `query_plan_invalid_output`, sem executar o Retriever.
- Busca legitimamente vazia continua retornando `retriever_no_results` e HTTP
  200.
- A consulta não relaxa ou remove filtros silenciosamente nesta feature.
- Logs não incluem consulta integral, prompt, resposta bruta ou credenciais.

## Taxonomia canônica inicial

### Setores

| Enum | Conceito | Rótulos persistidos iniciais de referência |
| --- | --- | --- |
| `financial_services` | Finanças, crédito, fintech, trading e investimentos | `Fintech / Crédito`, `SaaS de Gestão Financeira` |
| `data_and_ai` | Dados, analytics e IA aplicada | `Dados & IA` |
| `conversational_ai` | Assistentes e IA conversacional | `Conversational AI / CPaaS` |
| `communications` | Comunicação e CPaaS | `CPaaS / Comunicação`, `Conversational AI / CPaaS` |
| `industry_4_0` | Indústria 4.0, IoT e automação industrial | `Indústria 4.0 / IoT+IA` |
| `hr_tech` | Recursos humanos e gestão de pessoas | `HRtech` |
| `accessibility` | Tecnologias de acessibilidade | `Acessibilidade / IA` |
| `vertical_saas` | SaaS especializado por segmento | `SaaS Vertical (condomínios/assinaturas)` |
| `events_and_ticketing` | Eventos e venda de ingressos | `SaaS de Eventos / Ticketing` |
| `managed_it_services` | Serviços gerenciados de tecnologia | `Serviços de TI gerenciados` |
| `printing_services` | Impressão e serviços gráficos digitais | `SaaS de Impressão Online` |

Rótulos sintéticos criados por testes, como `Sector <uuid>`, não integram a
taxonomia funcional e continuam acessíveis em buscas exploratórias sem filtro.

### Estágios

| Enum | Exemplos reconhecidos |
| --- | --- |
| `pre_seed` | Pre-seed, pré-seed |
| `seed` | Seed |
| `series_a` | Série A, Series A |
| `series_b` | Série B, Series B |
| `series_c` | Série C, Series C |
| `growth` | Growth, Growth (soonicorn) |
| `late_stage` | Late stage, Late stage / pré-IPO |
| `public` | Empresa listada, IPO, Nasdaq |
| `acquired` | Adquirida, aquisição, M&A |
| `business_unit` | Unidade de negócio de empresa estabelecida |

## Contrato conceitual

```text
StartupSearchFilters
├── sectors: list[Sector]
├── company_sizes: list[CompanySize | NumericRange]
├── stages: list[StartupStage]
├── locations: list[string]
├── keywords: list[string]
└── ai_usage_signals: list[string]
```

Os valores JSON dos Enums são parte do contrato público. Os nomes das classes e
a forma exata de representar intervalos numéricos serão definidos no plano sem
alterar os comportamentos desta especificação.

## Requisitos funcionais

- **RF-01:** definir Enums canônicos para setor, estágio e porte.
- **RF-02:** centralizar aliases, descrições e rótulos persistidos reconhecidos.
- **RF-03:** incluir a taxonomia permitida nas instruções do Query Planner.
- **RF-04:** normalizar aliases antes da validação final do `QueryPlan`.
- **RF-05:** rejeitar valores desconhecidos após a tentativa de reparo existente.
- **RF-06:** traduzir filtros canônicos para critérios de persistência.
- **RF-07:** permitir expansão de uma categoria para múltiplos rótulos usando OR.
- **RF-08:** manter AND entre campos diferentes, conforme a spec 006.
- **RF-09:** preservar filtros textuais abertos e dados originais persistidos.
- **RF-10:** expor os valores canônicos nos endpoints existentes sem criar nova
  rota.

## Requisitos não funcionais

- **RNF-01:** manter tipagem estrita com `StrEnum` e validação Pydantic.
- **RNF-02:** manter a taxonomia independente de FastAPI, SQLAlchemy e Groq.
- **RNF-03:** manter consultas SQL parametrizadas e assíncronas.
- **RNF-04:** resolver aliases deterministicamente, sem nova chamada de LLM.
- **RNF-05:** aceitar aliases em português e inglês com normalização Unicode.
- **RNF-06:** não criar chamadas de rede ou banco nos testes unitários.
- **RNF-07:** preservar compatibilidade de UUIDs, URLs, ordenação e limites do
  Retriever.
- **RNF-08:** manter Ruff, mypy, testes arquiteturais e cobertura mínima de 80%.

## Regras de compatibilidade

- A semântica dos campos `sectors`, `stages` e `company_sizes` muda de texto
  livre para valores controlados; essa evolução deve ser registrada nas specs
  004 e 006 durante a implementação.
- `/api/v1/query-plans` e `/api/v1/search` mantêm suas URLs e envelopes.
- Clientes que enviam apenas `query` não precisam mudar.
- Consumidores do `QueryPlan` devem passar a tratar os valores canônicos como
  contrato público.
- A busca sem filtros permanece capaz de retornar todos os registros, inclusive
  os que não possuem mapeamento na taxonomia.

## Fora do escopo

- Busca vetorial, embeddings, BM25 ou reranking.
- Relaxamento automático de filtros e fallback silencioso.
- Criação de uma taxonomia administrável por interface ou banco de dados.
- Inferência automática de novos aliases a partir dos dados.
- Alteração destrutiva ou recategorização permanente dos registros importados.
- Enum fechado de cidades, estados ou países.
- Classificação de maturidade, recomendação NVIDIA ou agentes posteriores.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01, RF-03 a RF-05, RF-10, RNF-01 | Testes de schema, prompt, normalização e rejeição |
| US-02 | RF-02, RF-04, RF-06, RF-07, RNF-04, RNF-05 | Testes parametrizados de aliases financeiros e expansão |
| US-03 | RF-01, RF-02, RF-06, RNF-01 | Testes de estágios, portes e intervalos |
| US-04 | RF-06 a RF-09, RNF-02, RNF-03, RNF-07 | Integração com dados persistidos existentes |
| US-05 | RF-04, RF-05, RF-10, RNF-06, RNF-08 | Testes de API, erros, logs e suíte completa |

## Critério de conclusão

A feature estará concluída quando consultas por sinônimos produzirem filtros
canônicos, `financial_services` recuperar os rótulos financeiros existentes,
valores desconhecidos forem bloqueados, os dados originais forem preservados e
todos os critérios passarem após aprovação explícita da entrega.

## Sugestão de commit

`feat(search): add canonical filter taxonomy and aliases`
