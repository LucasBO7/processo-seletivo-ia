# Especificação 004: Query Planner Agent

## Status

Proposta.

Esta especificação deve ser revisada e aprovada explicitamente antes do início
da implementação.

## Contexto

A fundação do backend definiu o estado compartilhado do LangGraph e o protocolo
uniforme dos nós. A especificação 003 definiu a integração Groq, o contrato
assíncrono `ChatModel` e a alocação do perfil rápido ao identificador
`query_planner`. O primeiro comportamento funcional da pipeline será transformar
a consulta livre da pessoa usuária em parâmetros seguros, tipados e úteis para
o futuro Retriever Agent.

Sem esse planejamento, o Retriever teria de interpretar texto livre, misturando
compreensão de intenção com acesso a dados. Além disso, consultas vagas,
inválidas ou ambíguas poderiam gerar filtros inventados e resultados que não
correspondem ao pedido original.

## Objetivos

- Implementar o Query Planner Agent como nó assíncrono e isoladamente testável.
- Converter uma consulta livre em um contrato estruturado e validado.
- Representar, no mínimo, setor, porte, estágio, localização, palavras-chave,
  sinais de uso de IA e estratégia de análise.
- Distinguir consultas prontas, ambíguas e inválidas sem fabricar parâmetros.
- Produzir atualizações parciais compatíveis com o estado compartilhado do
  LangGraph.
- Manter o agente independente de um provedor concreto de modelos.

## Histórias do usuário

### US-01 — Estruturar uma consulta de startups

Como pessoa usuária, quero descrever em linguagem natural as startups que
procuro para que o sistema transforme minha intenção em parâmetros de busca.

Critérios de aceite:

- Uma consulta válida produz um `QueryPlan` validado.
- O plano contém a consulta normalizada e os campos `sectors`, `company_sizes`,
  `stages`, `locations`, `keywords`, `ai_usage_signals` e
  `analysis_strategy`.
- Parâmetros não informados permanecem vazios; o agente não inventa filtros.
- Espaços excedentes são removidos, valores duplicados são eliminados sem
  alterar a ordem semântica e strings vazias não aparecem no resultado.
- Setor, porte e estágio permanecem conceitos separados, mesmo quando a
  linguagem da consulta permitir confundi-los.
- A saída contém apenas dados serializáveis e não transporta clientes, sessões,
  prompts ou segredos.

### US-02 — Escolher uma estratégia de análise

Como pessoa desenvolvedora dos próximos agentes, quero receber uma estratégia
explícita para que as etapas posteriores saibam como tratar a consulta.

Critérios de aceite:

- `analysis_strategy.mode` aceita os modos `targeted`, `exploratory` e
  `comparative`.
- O modo `targeted` representa uma busca com recorte explícito; `exploratory`
  representa descoberta ampla; e `comparative` representa comparação entre
  dois ou mais recortes.
- A estratégia registra objetivos de análise extraídos da consulta, sem
  executar classificação, validação de evidências ou recomendação NVIDIA.
- A justificativa da estratégia é curta, não contém raciocínio interno do
  modelo e pode ser registrada com segurança para diagnóstico.

### US-03 — Tratar consultas ambíguas

Como pessoa usuária, quero ser avisada quando minha intenção admitir
interpretações materialmente diferentes para poder esclarecê-la antes da busca.

Critérios de aceite:

- Uma ambiguidade que altere filtros ou estratégia gera o status
  `needs_clarification`.
- O plano descreve cada ambiguidade de forma objetiva e pode fornecer até o
  limite configurado de perguntas curtas de esclarecimento.
- Campos inequívocos já identificados são preservados.
- O agente não escolhe silenciosamente uma interpretação nem inicia etapas
  posteriores enquanto o status exigir esclarecimento.
- Uma consulta ampla, mas ainda executável, pode ser `ready` com estratégia
  `exploratory`; ausência de filtros, isoladamente, não significa ambiguidade.

### US-04 — Rejeitar consultas inválidas e saídas malformadas

Como pessoa operadora, quero falhas previsíveis e sanitizadas para que erros de
entrada ou do modelo não interrompam a pipeline nem vazem detalhes internos.

Critérios de aceite:

- Consultas vazias, compostas apenas por espaços ou caracteres sem conteúdo
  semântico, ou maiores que o limite configurado são rejeitadas antes de chamar
  o modelo.
- Uma consulta semanticamente alheia à descoberta ou análise de startups pode
  ser marcada como `invalid` pelo plano validado.
- Saídas que não atendam ao schema passam por no máximo uma tentativa
  configurável de reparo usando o mesmo `ChatModel`.
- Se a saída continuar inválida, o nó retorna um `RecoverableError` com código
  estável, sem incluir resposta bruta, stack trace, prompt ou segredo.
- Falhas esperadas não são propagadas como exceções não tratadas pelo grafo.

### US-05 — Evoluir o agente com segurança

Como pessoa mantenedora, quero testes determinísticos e contratos desacoplados
para trocar prompts ou provedores sem alterar o restante da pipeline.

Critérios de aceite:

- O agente depende do protocolo interno `ChatModel`, não de SDK de provedor.
- Testes utilizam fakes e não realizam chamadas reais de rede ou a modelos pagos.
- O prompt possui versão explícita e instrui o modelo a tratar a consulta como
  dado, não como instrução de sistema.
- Mudanças no schema ou na semântica dos modos exigem atualização desta spec ou
  uma nova especificação.
- Formatação, lint, mypy, testes arquiteturais e testes unitários permanecem
  aprovados, mantendo a cobertura mínima definida pelo projeto.

## Contrato de saída

O resultado validado terá a seguinte forma conceitual. Os nomes definitivos no
código permanecem em inglês para acompanhar os contratos existentes.

```text
QueryPlan
├── status: ready | needs_clarification | invalid
├── normalized_query: string
├── filters
│   ├── sectors: list[string]
│   ├── company_sizes: list[string]
│   ├── stages: list[string]
│   ├── locations: list[string]
│   ├── keywords: list[string]
│   └── ai_usage_signals: list[string]
├── analysis_strategy
│   ├── mode: targeted | exploratory | comparative
│   ├── objectives: list[string]
│   └── rationale: string
├── ambiguities: list[string]
└── clarification_questions: list[string]
```

Os campos textuais de filtro não terão taxonomias fechadas nesta feature. Eles
serão normalizados sem substituir termos de domínio por categorias não
informadas. O mapeamento desses valores para colunas, intervalos de equipe ou
vocabulários controlados pertence à especificação do Retriever Agent.

## Requisitos funcionais

- **RF-01:** ler a consulta original do campo `query` de `AppState`.
- **RF-02:** validar a entrada localmente antes de qualquer chamada ao modelo.
- **RF-03:** produzir o contrato `QueryPlan` com todos os campos mínimos
  definidos nesta especificação.
- **RF-04:** normalizar e deduplicar os valores textuais sem inventar filtros.
- **RF-05:** classificar a estratégia como `targeted`, `exploratory` ou
  `comparative` e registrar seus objetivos.
- **RF-06:** validar integralmente a saída estruturada antes de inseri-la no
  estado do grafo.
- **RF-07:** representar ambiguidade com status e perguntas de esclarecimento.
- **RF-08:** representar consultas inválidas e falhas de parsing por erros
  recuperáveis com códigos estáveis.
- **RF-09:** retornar somente uma atualização parcial do estado, contendo o
  plano, avisos, erros e métricas pertencentes ao nó.
- **RF-10:** utilizar o protocolo `ChatModel` por injeção de dependência.
- **RF-11:** permitir uma tentativa limitada e configurável de reparo quando a
  resposta do modelo não cumprir o schema.
- **RF-12:** impedir a continuidade para o Retriever enquanto o plano não tiver
  status `ready`; o roteamento completo será implementado em spec futura.

## Requisitos não funcionais

- **RNF-01:** manter tipagem estrita e validação explícita dos limites e enums.
- **RNF-02:** executar chamadas ao modelo de forma assíncrona.
- **RNF-03:** não registrar consulta integral, prompt, resposta bruta, chaves ou
  tokens; logs usam apenas metadados permitidos, como status, duração e versão
  do prompt.
- **RNF-04:** limitar o tamanho da consulta, a quantidade de itens por campo e o
  número de perguntas de esclarecimento por configuração validada.
- **RNF-05:** tratar a consulta como conteúdo não confiável e resistir a
  instruções que tentem alterar o schema ou o papel do agente.
- **RNF-06:** manter códigos de erro e status estáveis, independentes do provedor.
- **RNF-07:** executar testes sem rede, banco de dados ou credenciais.
- **RNF-08:** preservar UTF-8 e aceitar consultas em português; termos técnicos
  em outros idiomas podem ser preservados.
- **RNF-09:** manter cobertura mínima de 80% para o backend sem excluir módulos
  apenas para elevar a métrica.

## Regras de validação

- `ready` não pode conter ambiguidades bloqueantes nem perguntas de
  esclarecimento.
- `needs_clarification` deve conter ao menos uma ambiguidade e uma pergunta.
- `invalid` não pode ser consumido pelo Retriever.
- Listas são vazias por padrão, nunca `null`.
- Todos os itens de lista devem ser strings não vazias e únicas após
  normalização.
- O limite padrão da consulta é 2.000 caracteres; após remover espaços
  externos, uma entrada precisa conter ao menos uma letra ou número Unicode.
- Cada lista do plano aceita por padrão até 20 itens, as perguntas de
  esclarecimento aceitam até três itens e a justificativa aceita até 500
  caracteres.
- A resposta do modelo não pode adicionar campos fora do schema.
- Informações ausentes na consulta não podem ser preenchidas por conhecimento
  presumido sobre uma empresa, setor ou região.
- Sinais de IA descrevem indícios solicitados ou mencionados, como tecnologias,
  capacidades ou casos de uso; eles não classificam a maturidade da startup.
- A justificativa da estratégia descreve o critério escolhido, sem expor cadeia
  de pensamento.

## Códigos de erro mínimos

| Código                      | Situação                                               |
| --------------------------- | ------------------------------------------------------ |
| `query_empty`               | Consulta vazia ou sem conteúdo semântico               |
| `query_too_long`            | Consulta maior que o limite configurado                |
| `query_invalid`             | Consulta validada como alheia ao propósito do sistema  |
| `query_plan_invalid_output` | Saída permaneceu incompatível com o schema após reparo |
| `query_planner_unavailable` | Falha recuperável ao acessar o `ChatModel`             |

## Restrições

- LangGraph permanece o mecanismo de orquestração.
- O agente deve respeitar `GraphNode` e o estado criado pela especificação 002.
- SDKs de provedores não podem aparecer no agente nem nos contratos de domínio
  ou aplicação.
- Nenhuma consulta a PostgreSQL, Qdrant ou internet será feita pelo Query
  Planner.
- O nó não pode executar tarefas pertencentes aos demais sete agentes.

## Fora do escopo

- Implementar o Retriever Agent ou consultar startups.
- Definir a taxonomia definitiva de setores, portes, estágios ou regiões.
- Classificar maturidade de IA, validar evidências ou identificar gaps.
- Consultar a base NVIDIA, recomendar tecnologias ou produzir briefing.
- Alterar a integração Groq ou a alocação de modelos definida na especificação 003.
- Expor uma rota HTTP de análise ou integrar o frontend.
- Compilar e executar o grafo completo ou definir todas as suas transições.
- Persistir o plano da consulta ou alterar o schema do PostgreSQL.
- Implementar memória conversacional ou fluxo completo de esclarecimento.

## Matriz de rastreabilidade

| História | Requisitos                                  | Validação                                                          |
| -------- | ------------------------------------------- | ------------------------------------------------------------------ |
| US-01    | RF-01 a RF-04, RNF-01, RNF-08               | Testes do contrato, normalização e atualização do estado           |
| US-02    | RF-03, RF-05, RNF-01                        | Testes dos três modos e seus objetivos                             |
| US-03    | RF-07, RF-09, RF-12                         | Testes de ambiguidade, preservação de filtros e bloqueio semântico |
| US-04    | RF-02, RF-06, RF-08, RF-11, RNF-03 a RNF-06 | Testes de entrada inválida, parsing, reparo e erros sanitizados    |
| US-05    | RF-10, RNF-02, RNF-07, RNF-09               | Fakes, testes arquiteturais, mypy e cobertura                      |

## Critério de conclusão da feature

A feature estará concluída quando todos os critérios de aceite forem
verificados, o agente produzir somente planos validados, casos inválidos e
ambíguos forem tratados sem filtros inventados, a suíte não realizar chamadas
reais a modelos e todas as tarefas estiverem concluídas após aprovação da
entrega.

## Sugestão de commit

`feat(query-planner): implement structured query planning with Groq fast model`
