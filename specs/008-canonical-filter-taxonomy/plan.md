# Plano 008: taxonomia canônica de filtros

## Status

Planejamento proposto. A implementação depende da aprovação da especificação.

## Estratégia

Criar um módulo de aplicação independente contendo os Enums, seus aliases e os
rótulos persistidos reconhecidos. O Query Planner receberá no prompt somente as
opções permitidas e normalizará aliases conhecidos antes de validar o plano. O
Retriever converterá os Enums em conjuntos de rótulos aceitos pelo repositório,
sem alterar os dados existentes.

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

O módulo não importará FastAPI, SQLAlchemy, SDKs de IA ou configurações de
infraestrutura.

### Query Planner

O schema de `StartupSearchFilters` passará a usar os Enums. A leitura da resposta
do modelo ocorrerá em duas etapas:

1. normalizar valores exatos ou aliases reconhecidos;
2. validar o objeto final com Pydantic.

Um alias poderá expandir para mais de um valor. Valores desconhecidos acionarão
a tentativa de reparo já existente; persistindo o erro, será mantido
`query_plan_invalid_output`.

O prompt apresentará identificadores, descrições e aliases necessários, sem
consultar o PostgreSQL. O prompt continuará versionado e a consulta continuará
tratada como dado não confiável.

### Retriever e persistência

O Retriever transformará os Enums canônicos em critérios contendo os rótulos
persistidos reconhecidos. Dentro do campo, os rótulos usarão OR; campos distintos
continuarão usando AND. O repositório permanecerá responsável somente pela query
parametrizada.

O schema PostgreSQL e os valores originais não serão alterados. Buscas sem setor
ou estágio continuarão incluindo registros não mapeados.

### API

As rotas e envelopes atuais serão preservados. OpenAPI passará a publicar os
valores permitidos para os campos enumerados. O exemplo de Postman será atualizado
para demonstrar que uma consulta financeira retorna filtros canônicos.

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

## Testes planejados

- contrato aceita todos os Enums e rejeita valores desconhecidos;
- normalização ignora caixa, acentos e espaços;
- aliases financeiros em português e inglês resolvem para
  `financial_services`;
- aliases duplicados produzem um único valor canônico;
- rótulos compostos são associados às categorias esperadas;
- estágios persistidos são traduzidos corretamente;
- portes canônicos e intervalos numéricos preservam a semântica atual;
- saída desconhecida do modelo usa reparo e depois erro sanitizado;
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
| IA retornar tradução não permitida | Normalizar apenas aliases conhecidos e rejeitar o restante |
| Mudança quebrar consumidores do plano | Manter strings JSON estáveis, documentar OpenAPI e testar endpoints |
| Rótulo composto pertencer a duas categorias | Permitir mapeamento muitos-para-muitos na taxonomia |

## Evoluções posteriores

- tabela administrável de taxonomia e aliases;
- normalização de localização por cidade, estado e país;
- filtros múltiplos por startup no modelo relacional;
- fallback progressivo e busca semântica.

## Sugestão de commit

`feat(search): add canonical filter taxonomy and aliases`
