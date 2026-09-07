# Plano 008: taxonomia canônica de filtros

## Status

Planejamento aprovado em 7 de setembro de 2026.

## Estratégia

Criar um módulo de aplicação independente contendo os Enums, seus aliases e os
rótulos persistidos reconhecidos. O Query Planner receberá no prompt somente as
opções permitidas, normalizará aliases conhecidos e representará termos não
resolvidos com até três sugestões válidas antes de validar o plano. O Retriever
converterá os Enums em conjuntos de rótulos aceitos pelo repositório, sem alterar
os dados existentes.

A taxonomia será estática e versionada com o código. Essa escolha torna o
contrato previsível e auditável, evitando que a IA ou um CSV modifiquem os
filtros disponíveis implicitamente.

## Componentes

### Contrato de taxonomia

Criar um módulo na camada `application` com:

- `Sector`, `StartupStage` e `CompanySize` como `StrEnum`;
- descrições curtas para orientar o Planner;
- aliases normalizados por Enum;
- mapeamento entre Enum e rótulos persistidos;
- funções puras de normalização, expansão e deduplicação.
- contratos tipados para filtro não resolvido e sugestões.

O módulo não importará FastAPI, SQLAlchemy, SDKs de IA ou configurações de
infraestrutura.

### Query Planner

O schema de `StartupSearchFilters` passará a usar os Enums. A leitura da resposta
do modelo ocorrerá em duas etapas:

1. normalizar valores exatos ou aliases reconhecidos;
2. representar um termo explícito não reconhecido em `unresolved_filters`;
3. sugerir até três valores permitidos do mesmo campo;
4. validar o objeto final com Pydantic.

Um alias poderá expandir para mais de um valor. Um termo legítimo da consulta que
não tenha correspondência produzirá `needs_clarification`, sem ser descartado ou
enviado ao Retriever. Sugestões inválidas ou respostas estruturalmente
malformadas acionarão a tentativa de reparo já existente; persistindo o erro,
será mantido `query_plan_invalid_output`.

O prompt apresentará identificadores, descrições e aliases necessários e pedirá
ao mesmo modelo que ordene as três opções semanticamente mais próximas quando
houver um termo não resolvido. O validador aceitará apenas Enums do campo
correto, sem consultar o PostgreSQL ou fazer uma segunda chamada ao modelo. O
prompt continuará versionado e a consulta continuará tratada como dado não
confiável.

### Retriever e persistência

O Retriever transformará os Enums canônicos em critérios contendo os rótulos
persistidos reconhecidos. Dentro do campo, os rótulos usarão OR; campos distintos
continuarão usando AND. O repositório permanecerá responsável somente pela query
parametrizada.

O schema PostgreSQL e os valores originais não serão alterados. Buscas sem setor
ou estágio continuarão incluindo registros não mapeados.

### API

As rotas e envelopes atuais serão preservados. OpenAPI passará a publicar os
valores permitidos para os campos enumerados e os contratos de sugestões. O
exemplo de Postman será atualizado para demonstrar uma consulta financeira e um
pedido de esclarecimento com sugestões.

## Decisões

### D-01 — Enum de conceito, não cópia dos rótulos

Um Enum representa um conceito de busca estável. Um conceito pode reconhecer
vários rótulos persistidos, e um rótulo composto pode participar de mais de um
conceito. Isso permite que `financial_services` encontre tanto fintechs de
crédito quanto SaaS de gestão financeira.

### D-02 — Localização permanece aberta

Cidades e combinações como `São Paulo/Boston` não formam um conjunto pequeno ou
estável. Nesta entrega, localização terá apenas normalização textual e não será
convertida em Enum.

### D-03 — Sem migração de dados

O mapeamento será aplicado na leitura. Isso reduz risco sobre o CSV importado e
permite validar o comportamento antes de redesenhar o modelo relacional.

### D-04 — Sem fallback automático

Uma busca vazia continuará vazia e explicável. Relaxamento progressivo poderá ser
tratado por uma especificação própria, pois altera a precisão esperada.

### D-05 — Sugestões estruturadas e não vinculantes

As opções próximas serão parte do `QueryPlan`, e não apenas texto em uma
pergunta. Isso permite renderização segura no frontend. A pessoa usuária precisa
escolher ou reformular a consulta; o sistema não seleciona automaticamente a
primeira sugestão.

### D-06 — Consulta ampla não é filtro desconhecido

Ausência intencional de filtros permanece uma busca exploratória válida. Somente
um conceito explicitamente solicitado e não resolvido bloqueia o Retriever e
gera sugestões.

## Testes planejados

- contrato aceita todos os Enums e rejeita valores desconhecidos inseridos
  diretamente nos campos enumerados;
- normalização ignora caixa, acentos e espaços;
- aliases financeiros em português e inglês resolvem para
  `financial_services`;
- aliases duplicados produzem um único valor canônico;
- rótulos compostos são associados às categorias esperadas;
- estágios persistidos são traduzidos corretamente;
- portes canônicos e intervalos numéricos preservam a semântica atual;
- saída que coloca um valor desconhecido diretamente em campo enumerado usa
  reparo e depois erro sanitizado;
- consulta sem filtros permanece `ready` e recupera resultados exploratórios;
- filtro explícito desconhecido produz `needs_clarification` e não chama o
  Retriever;
- sugestões contêm três Enums distintos do campo correto, em ordem de
  proximidade, quando houver ao menos três opções disponíveis;
- nenhuma sugestão é aplicada automaticamente;
- Retriever expande categorias e preserva AND entre campos;
- consulta financeira encontra registros reais dos dois rótulos mapeados;
- busca sem filtros continua incluindo registros não mapeados;
- endpoints preservam envelopes e OpenAPI apresenta os Enums;
- testes não usam Groq ou PostgreSQL, exceto a integração explicitamente marcada.

## Verificação

1. Executar testes unitários da taxonomia, Query Planner e Retriever.
2. Executar testes HTTP dos endpoints existentes.
3. Executar integração com PostgreSQL real e modelo falso.
4. Executar Ruff format/check, mypy e import-linter.
5. Executar cobertura do backend com mínimo de 80%.
6. Executar lint, testes e build do frontend.
7. Revisar a evolução registrada nas specs 004 e 006.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Taxonomia ficar desatualizada após novo CSV | Registros não mapeados continuam acessíveis sem filtro; inclusão exige mudança explícita e teste |
| Alias amplo gerar falso positivo | Manter aliases revisados e categorias conceituais documentadas |
| IA colocar tradução não permitida em campo enumerado | Exigir que o Planner use `unresolved_filters`, reparar a estrutura e rejeitar se continuar inválida |
| Sugestões irrelevantes confundirem a pessoa | Expor como alternativas não vinculantes, preservar termo original e permitir busca textual |
| Mudança quebrar consumidores do plano | Manter strings JSON estáveis, documentar OpenAPI e testar endpoints |
| Rótulo composto pertencer a duas categorias | Permitir mapeamento muitos-para-muitos na taxonomia |

## Evoluções posteriores

- tabela administrável de taxonomia e aliases;
- normalização de localização por cidade, estado e país;
- filtros múltiplos por startup no modelo relacional;
- fallback progressivo e busca semântica.

## Resultado da execução

- A taxonomia canônica foi implementada sem alteração do schema ou dos dados
  persistidos.
- Aliases são normalizados na aplicação e os Enums são expandidos para igualdade
  parametrizada no PostgreSQL, preservando os índices existentes.
- Filtros não resolvidos bloqueiam o Retriever e retornam três sugestões
  estruturadas e não vinculantes.
- A integração real comprovou que `financial_services` recupera os dois rótulos
  financeiros previstos, preservando IDs e URLs.
- A suíte do backend, arquitetura, Ruff, mypy e import-linter passaram com
  cobertura de 87,25%.
- Lint, testes e build do frontend passaram.

## Sugestão de commit

`feat(search): add canonical filter taxonomy and aliases`
