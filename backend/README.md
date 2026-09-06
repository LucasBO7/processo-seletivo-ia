# Backend do NVIDIA Startup AI Radar

Fundação assíncrona e modular descrita na especificação `002-backend-foundation`.
Os comandos operacionais estão documentados no README da raiz do repositório.

## Modelos Groq

A aplicação disponibiliza dois perfis de chat reutilizáveis por meio do contrato
interno `ChatModel`:

- `llm_fast`: `openai/gpt-oss-20b`, temperatura `0`;
- `llm_heavy`: `openai/gpt-oss-120b`, temperatura `0.1`.

Defina `GROQ__API_KEY` no arquivo `.env` local antes de iniciar a composição
completa da aplicação. O valor não deve ser versionado nem registrado em logs.
Modelos, temperaturas, timeouts e retentativas podem ser substituídos pelos
grupos `LLM_FAST__` e `LLM_HEAVY__`.
Como os IDs publicados pela Groq possuem ciclo de vida próprio e podem depender
das permissões da conta, qualquer substituição deve ser validada no ambiente
antes de ser promovida.

O Query Planner, Extractor, Evidence Validator e NVIDIA RAG usam o perfil rápido.
Startup Classifier, Recommendation e Briefing usam o perfil pesado. O Retriever
executa somente código de recuperação e não recebe LLM.
