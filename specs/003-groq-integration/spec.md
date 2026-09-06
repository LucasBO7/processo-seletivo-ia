# Especificação 003: integração Groq para agentes

## Status

Implementada em 6 de setembro de 2026; aguardando aprovação explícita da
entrega para conclusão.

## Contexto

A fundação do backend definiu o protocolo assíncrono `ChatModel`, configurações
genéricas de modelos e os identificadores dos oito nós do LangGraph, mas adiou
a escolha do provedor de chat. Os agentes funcionais precisam de modelos com
perfis distintos de custo, velocidade e capacidade analítica sem depender
diretamente do SDK de um provedor.

Esta feature integra a plataforma Groq, por meio de `ChatGroq` do pacote
`langchain-groq`, e disponibiliza dois perfis reutilizáveis: um modelo rápido
para tarefas de estruturação e um modelo pesado para tarefas de maior raciocínio.
O nome correto do provedor é Groq; Grok é uma família de modelos da xAI e não faz
parte desta entrega.

Em 6 de setembro de 2026, a Groq informa que os modelos inicialmente cogitados,
`llama-3.1-8b-instant` e `llama-3.3-70b-versatile`, foram descontinuados em 16 de
agosto de 2026 para contas free e developer. Esta especificação adota os
substitutos oficiais `openai/gpt-oss-20b` e `openai/gpt-oss-120b`. Os IDs
continuam configuráveis para permitir futuras migrações sem alterar a alocação
lógica entre perfis rápido e pesado.

## Objetivos

- Instalar e encapsular a integração `langchain-groq` no backend.
- Configurar os perfis `llm_fast` e `llm_heavy` em `core/config.py`.
- Construir exatamente uma instância de `ChatGroq` por perfil no composition root.
- Adaptar as instâncias ao protocolo interno `ChatModel` usado pelos agentes.
- Centralizar a alocação de perfil por nó do LangGraph.
- Manter credenciais, clientes concretos e respostas fora do estado compartilhado.
- Permitir trocar IDs de modelo por configuração sem modificar os agentes.

## Histórias do usuário

### US-01 — Configurar a Groq com segurança

Como pessoa operadora, quero configurar credencial, modelos, temperaturas,
timeouts e retentativas para executar os agentes nos ambientes autorizados.

Critérios de aceite:

- O backend declara uma versão compatível de `langchain-groq` em
  `pyproject.toml` e atualiza o lockfile.
- A chave da Groq é recebida por configuração secreta e nunca possui valor real
  versionado.
- `core/config.py` contém configurações validadas e imutáveis para `llm_fast` e
  `llm_heavy`.
- O default de `llm_fast` é o modelo `openai/gpt-oss-20b` com temperatura `0`.
- O default de `llm_heavy` é o modelo `openai/gpt-oss-120b` com temperatura
  `0.1`.
- Modelo, temperatura, timeout e número máximo de retentativas podem ser
  sobrescritos por variáveis de ambiente.
- A ausência de credencial falha com mensagem acionável somente quando a
  composição Groq é solicitada, sem revelar valores secretos.
- `.env.example` documenta todas as variáveis não sensíveis e apenas o nome da
  variável da credencial.

### US-02 — Reutilizar os modelos sem acoplar os agentes

Como pessoa desenvolvedora, quero injetar modelos pelo contrato `ChatModel` para
que os agentes não importem nem construam `ChatGroq` diretamente.

Critérios de aceite:

- Um adaptador de infraestrutura converte `ChatMessage` para mensagens aceitas
  pelo LangChain e converte a resposta para `str`.
- O adaptador implementa `ChatModel.complete` de forma assíncrona usando a API
  assíncrona de `ChatGroq`.
- A construção concreta ocorre uma única vez no composition root e produz os
  recursos nomeados `llm_fast` e `llm_heavy`.
- O domínio, a aplicação, o estado e os módulos dos agentes não importam
  `langchain_groq`.
- Clientes, chaves e objetos de resposta do provedor não são inseridos em
  `AppState`.
- Testes unitários substituem o cliente concreto por fakes e não dependem de
  rede ou cobrança.

### US-03 — Alocar o perfil correto a cada nó

Como pessoa mantenedora, quero uma política central de alocação para que cada
agente receba o perfil previsto e o Retriever não consuma LLM.

Critérios de aceite:

- A política usa `NodeName` como chave e não replica strings de nomes dos nós.
- O registro associa os nós aos perfis conforme a tabela desta especificação.
- `query_planner`, `extractor`, `evidence_validator` e `nvidia_rag` recebem
  `llm_fast`.
- `startup_classifier`, `recommendation` e `briefing` recebem `llm_heavy`.
- `retriever` não recebe modelo e sua resolução de LLM é rejeitada de forma
  explícita.
- A integração entrega uma factory ou registro pronto para injeção nos
  construtores dos agentes; a implementação funcional de cada agente continua
  pertencendo à sua própria especificação.
- Testes verificam todas as associações e impedem que um novo nó consumidor seja
  adicionado sem decisão explícita de perfil.

### US-04 — Tratar indisponibilidade de forma previsível

Como pessoa operadora, quero que falhas da Groq sejam convertidas em falhas
sanitizadas para que detalhes do provedor e segredos não vazem pela pipeline.

Critérios de aceite:

- Timeout, autenticação, rate limit e indisponibilidade são capturados na
  fronteira do adaptador.
- O adaptador lança uma exceção interna estável e sanitizada, sem corpo bruto,
  prompt, chave, stack trace do SDK ou mensagem sensível do provedor.
- A política global não faz fallback silencioso do perfil pesado para o rápido,
  nem o inverso.
- Logs usam allowlist com perfil, modelo configurado, duração, resultado e código
  de erro, sem prompt, mensagem integral ou resposta bruta.
- A inicialização das instâncias não realiza chamada de rede nem consome tokens.

## Configuração dos modelos

A configuração conceitual solicitada é:

```python
llm_fast = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
llm_heavy = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)
```

Os valores ficam definidos e validados em `core/config.py`; a instanciação de
`ChatGroq` ocorre no composition root para evitar efeitos colaterais durante o
import e para permitir testes sem credenciais. A API key, timeout e retentativas
também são fornecidos explicitamente na construção.

Variáveis previstas:

| Variável | Default | Regra |
| --- | --- | --- |
| `GROQ__API_KEY` | sem default | segredo obrigatório ao compor a Groq |
| `LLM_FAST__MODEL` | `openai/gpt-oss-20b` | string não vazia |
| `LLM_FAST__TEMPERATURE` | `0` | entre `0` e `2` |
| `LLM_FAST__TIMEOUT_SECONDS` | `30` | maior que `0` e até `300` |
| `LLM_FAST__MAX_RETRIES` | `2` | entre `0` e `10` |
| `LLM_HEAVY__MODEL` | `openai/gpt-oss-120b` | string não vazia |
| `LLM_HEAVY__TEMPERATURE` | `0.1` | entre `0` e `2` |
| `LLM_HEAVY__TIMEOUT_SECONDS` | `30` | maior que `0` e até `300` |
| `LLM_HEAVY__MAX_RETRIES` | `2` | entre `0` e `10` |

## Alocação por nó do LangGraph

| Ordem | Agente | Perfil | Modelo default | Justificativa técnica |
| ---: | --- | --- | --- | --- |
| 1 | Query Planner Agent | `llm_fast` | `openai/gpt-oss-20b` | Conversão de linguagem natural em JSON de parâmetros, priorizando velocidade e baixo consumo de TPM. |
| 2 | Retriever Agent | nenhum | nenhum | Recuperação por código com PostgreSQL/SQL, sem consumo de LLM. |
| 3 | Extractor Agent | `llm_fast` | `openai/gpt-oss-20b` | Extração de entidades e estruturação com Structured Outputs/JSON Schema. |
| 4 | Startup Classifier Agent | `llm_heavy` | `openai/gpt-oss-120b` | Análise de sinais falsos de IA e classificação de maior complexidade. |
| 5 | Evidence Validator Agent | `llm_fast` | `openai/gpt-oss-20b` | Validação de factibilidade e presença de URL de fonte entre afirmação e documento. |
| 6 | NVIDIA RAG Agent | `llm_fast` | `openai/gpt-oss-20b` | Consolidação do contexto recuperado por Qdrant, BM25 e Cohere Rerank. |
| 7 | Recommendation Agent | `llm_heavy` | `openai/gpt-oss-120b` | Cruzamento crítico de gaps técnicos com o catálogo NVIDIA. |
| 8 | Briefing Agent | `llm_heavy` | `openai/gpt-oss-120b` | Redação executiva coesa com citações rigorosas. |

## Requisitos funcionais

- **RF-01:** declarar e instalar a integração Python `langchain-groq`.
- **RF-02:** configurar credencial e dois perfis independentes no sistema de
  settings existente.
- **RF-03:** criar `llm_fast` e `llm_heavy` com os defaults definidos.
- **RF-04:** fornecer adaptador assíncrono compatível com `ChatModel`.
- **RF-05:** construir os modelos uma única vez no composition root.
- **RF-06:** resolver o modelo de cada nó pela política central de alocação.
- **RF-07:** impedir alocação de LLM ao Retriever.
- **RF-08:** converter falhas externas em erros internos sanitizados.
- **RF-09:** permitir substituição dos IDs por configuração.
- **RF-10:** disponibilizar os recursos para injeção nas specs funcionais dos
  agentes, começando pelo Query Planner da especificação 004.

## Requisitos não funcionais

- **RNF-01:** preservar o desacoplamento entre contratos internos e SDK Groq.
- **RNF-02:** não realizar chamadas síncronas dentro do fluxo assíncrono.
- **RNF-03:** não registrar chaves, prompts, mensagens integrais ou respostas
  brutas.
- **RNF-04:** não realizar chamadas reais à Groq na suíte padrão.
- **RNF-05:** manter tipagem estrita, Ruff, mypy, import-linter e cobertura mínima
  de 80% do backend.
- **RNF-06:** instanciar clientes sem chamada de rede e compartilhar cada
  instância durante o ciclo de vida da aplicação.
- **RNF-07:** manter modelos e parâmetros operacionais configuráveis devido à
  disponibilidade variável dos IDs na Groq.

## Restrições

- LangGraph permanece o mecanismo de orquestração.
- Os agentes dependem apenas de `ChatModel`; `ChatGroq` fica na infraestrutura e
  na composição.
- O Retriever não pode receber ou chamar LLM.
- Não serão criados stubs funcionais dos sete agentes ainda não especificados.
- Não haverá fallback automático entre perfis ou provedores.
- Credenciais reais não serão versionadas nem usadas nos testes padrão.

## Fora do escopo

- Implementar regras funcionais dos oito agentes.
- Implementar o Query Planner, que pertence à especificação 004.
- Alterar recuperação PostgreSQL, Qdrant, BM25 ou Cohere Rerank.
- Criar prompts ou schemas de saída específicos de agentes.
- Implementar fallback para outro provedor.
- Realizar benchmark comparativo ou seleção automática de modelos.
- Garantir disponibilidade comercial dos modelos na conta Groq utilizada.
- Expor uma rota HTTP de análise ou compilar o fluxo completo do LangGraph.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RF-01 a RF-03, RF-09, RNF-07 | Testes de configuração, defaults, overrides e segredos |
| US-02 | RF-04, RF-05, RNF-01, RNF-02, RNF-06 | Testes do adaptador, composição e arquitetura |
| US-03 | RF-06, RF-07, RF-10 | Teste parametrizado de todos os `NodeName` |
| US-04 | RF-08, RNF-03, RNF-04 | Fakes de falhas, inspeção de logs e suíte sem rede |

## Critério de conclusão da feature

A feature estará concluída quando os dois perfis forem configuráveis e
construídos como recursos reutilizáveis, o adaptador cumprir `ChatModel`, todas
as alocações da tabela forem verificadas, o Retriever permanecer sem LLM,
segredos não vazarem e todas as verificações automatizadas passarem sem chamadas
reais à Groq.

## Sugestão de commit

`feat(groq): add reusable fast and heavy LLM profiles for graph agents`
