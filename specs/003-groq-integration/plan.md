# Plano 003: integração Groq para agentes

## Estratégia

A integração será implementada como adaptador de infraestrutura sobre
`ChatGroq`. `core/config.py` continuará responsável somente por settings
validados; o composition root materializará uma instância rápida e uma pesada e
as envolverá em objetos compatíveis com o protocolo `ChatModel`.

Uma política central, indexada por `NodeName`, informará qual recurso deve ser
injetado em cada agente. Como os agentes funcionais ainda não existem, esta
feature entrega o registro e a factory de resolução, sem criar nós fictícios.
As specs de cada agente consumirão essa factory em seus construtores.

## Arquitetura dentro do escopo

```text
backend/src/app/
├── application/
│   └── ports/providers.py          # ChatModel e erro interno estável
├── core/
│   ├── config.py                   # GroqConfig, llm_fast e llm_heavy
│   └── resources.py                # ciclo de vida dos recursos compartilhados
├── graph/
│   └── model_policy.py             # NodeName -> fast | heavy | none
├── infrastructure/
│   └── providers/groq.py           # ChatGroq + adaptador ChatModel
└── api/app.py                      # composition root e injeção de recursos

backend/tests/unit/
├── test_config.py                  # defaults, overrides e segredos
├── test_groq_provider.py           # tradução e falhas com cliente fake
└── test_model_policy.py            # oito alocações da tabela
```

## Fluxo de composição

```text
Settings
  ├── groq.api_key
  ├── llm_fast  ──> ChatGroq fast  ──> ChatModel adapter ──┐
  └── llm_heavy ──> ChatGroq heavy ──> ChatModel adapter ─┤
                                                            ▼
                                                   ModelRegistry
                                                            │
                                          NodeName ─────────┘
                                                            │
                                          construtor do agente
```

O Retriever é representado na política como `none`; tentar resolver um
`ChatModel` para ele gera falha de configuração estável antes da execução.

## Configuração

Serão criados modelos Pydantic imutáveis para:

- credencial Groq;
- perfil rápido, com `openai/gpt-oss-20b`, temperatura `0`, timeout e retries;
- perfil pesado, com `openai/gpt-oss-120b`, temperatura `0.1`, timeout e
  retries.

Os nomes de ambiente e defaults seguem a tabela do `spec.md`. A API key será
`SecretStr`, nunca terá default e só será exigida ao criar os recursos Groq. Os
IDs ficam configuráveis porque a disponibilidade depende do plano da conta e do
ciclo de vida comercial da Groq.

## Adaptador Groq

O adaptador:

1. recebe uma instância de `ChatGroq` por injeção;
2. converte a sequência interna de `ChatMessage` para mensagens LangChain;
3. chama `ainvoke` sem bloquear o event loop;
4. aceita somente conteúdo textual como resposta do contrato atual;
5. converte falhas conhecidas do provedor em exceção interna sanitizada;
6. não mantém prompts ou respostas em atributos, estado ou logs.

O wrapper existe porque `ChatGroq` não implementa diretamente o método
`ChatModel.complete` já definido pela aplicação. Assim, nenhuma mudança do SDK
se propaga aos agentes.

## Política de modelos

Será criado um enum interno de perfil (`fast`, `heavy`) e uma tabela imutável:

```text
query_planner       -> fast
retriever           -> none
extractor           -> fast
startup_classifier  -> heavy
evidence_validator  -> fast
nvidia_rag           -> fast
recommendation      -> heavy
briefing             -> heavy
```

A resolução recebe `NodeName`, nunca uma string livre. O teste parametrizado
cobre todos os membros de `ALL_NODE_NAMES`, tornando explícita qualquer futura
alteração da lista.

## Tratamento de falhas

| Falha | Resultado |
| --- | --- |
| API key ausente na composição | erro de configuração sanitizado |
| Modelo indisponível ou sem permissão | erro interno de provedor indisponível |
| Timeout ou rate limit | erro interno recuperável, sem resposta bruta |
| Conteúdo de resposta incompatível | erro interno de resposta inválida |
| Tentativa de resolver LLM do Retriever | erro estável de alocação inválida |

Não haverá fallback entre modelos nesta feature. O agente consumidor decide,
em sua própria spec, como representar a falha no estado do LangGraph.

## Testes

Os testes cobrirão:

- defaults exatos dos dois perfis;
- sobrescrita de modelo, temperatura, timeout e retries por ambiente;
- ausência e redação da API key;
- construção única de cada recurso sem rede;
- conversão de mensagens e resposta textual;
- uso assíncrono do cliente;
- sanitização de autenticação, timeout, rate limit e indisponibilidade;
- ausência de prompts, respostas e segredos nos logs e no estado;
- todas as oito decisões da política;
- proibição de LLM para o Retriever;
- ausência de imports de `langchain_groq` no domínio, aplicação e agentes;
- lockfile, Ruff, mypy, import-linter e cobertura do backend.

Um teste de integração real poderá existir com marcador explícito e skip quando
não houver credencial, mas não fará parte do comando padrão nem será necessário
para aceitar a feature.

## Decisões

### D-01 — Dois perfis, uma única fronteira interna

Os agentes recebem `ChatModel`, não `ChatGroq`. Os perfis permitem otimizar custo
e capacidade sem duplicar configuração e tratamento de erro em cada nó.

### D-02 — Configuração separada de instanciação

Os valores ficam em `core/config.py`, mas clientes são criados no composition
root. Isso evita falha de import sem credencial e permite construir a aplicação
de testes sem acessar a Groq.

### D-03 — Alocação central e exaustiva

A associação por `NodeName` evita que cada agente escolha seu modelo e permite
testar a arquitetura inteira em uma única matriz.

### D-04 — Substitutos oficiais como defaults configuráveis

Os modelos `openai/gpt-oss-20b` e `openai/gpt-oss-120b`, recomendados pela Groq
para substituir os modelos Llama descontinuados, são os defaults, porém não são
constantes dentro dos agentes. A configuração permite substituí-los quando a
conta não tiver permissão ou quando o provedor encerrar sua disponibilidade.

### D-05 — Sem fallback implícito

Trocar automaticamente um perfil pode alterar custo e qualidade sem deixar
rastro. Uma política de fallback exigirá especificação própria.

## Verificação

1. Aprovar `spec.md`, `plan.md` e `tasks.md` antes de alterar código.
2. Atualizar dependência e lockfile de forma reproduzível.
3. Executar testes unitários de configuração, adaptador e política.
4. Executar Ruff format check, Ruff lint, mypy e import-linter.
5. Executar a suíte completa do backend com cobertura mínima de 80%.
6. Executar lint, testes e build do frontend para detectar regressões.
7. Inspecionar logs, settings serializados e estado para confirmar ausência de
   credencial, prompt, mensagem integral e resposta bruta.
8. Conferir todos os critérios de aceite e a matriz de alocação.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Modelos default indisponíveis na conta | IDs configuráveis e validação operacional explícita |
| SDK contaminar contratos internos | Adaptador limitado à infraestrutura |
| Instâncias duplicadas elevarem conexões e custo | Construção única e recursos compartilhados |
| Retriever consumir tokens indevidamente | Política `none` e teste de rejeição |
| Logs vazarem dados | Allowlist e testes de sanitização |
| Testes consumirem API paga | Fakes obrigatórios e integração real fora da suíte padrão |

## Decisões adiadas

- Próxima migração de modelos quando os defaults forem descontinuados.
- Fallback entre Groq e outro provedor.
- Rate limiting interno, orçamento de tokens e circuit breaker.
- Streaming, tool calling e recursos multimodais.
- Observabilidade de custo e tokens por execução.
- Implementação e prompts de cada agente consumidor.
