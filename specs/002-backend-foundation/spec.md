# Especificação 002: fundação do backend

## Status

Aguardando aprovação da entrega.

A aprovação foi registrada pela solicitação explícita de início da execução das tarefas.
As tarefas T-01 a T-33 foram implementadas e verificadas em 5 de setembro de
2026. Conforme T-34, o status só será alterado para `Concluída` após a validação
explícita desta entrega.

## Contexto

O projeto já possui documentação orientada por especificações e uma fundação de frontend independente. A próxima etapa precisa estabelecer a base técnica do backend sobre a qual serão implementados, em entregas posteriores, os agentes do NVIDIA Startup AI Radar.

O TAPI exige uma pipeline multiagente com LangGraph, consulta a uma base pré-populada de startups, evidências rastreáveis, RAG sobre tecnologias NVIDIA com busca híbrida e reranking, recomendações e briefing executivo. Esta feature não implementa esses comportamentos de negócio: ela cria a arquitetura, os contratos compartilhados e as configurações necessárias para que eles possam ser adicionados sem acoplamento indevido.

## Objetivos

- Criar um backend Python instalável, executável e testável localmente.
- Definir limites claros entre API, orquestração, domínio, grafo e infraestrutura.
- Disponibilizar configuração segura e validada para banco, modelos, embeddings e reranker.
- Preparar persistência relacional, busca vetorial e busca lexical sem popular dados de negócio.
- Definir o estado compartilhado e os contratos mínimos usados pelos futuros agentes.
- Estabelecer qualidade automatizada, migrações, observabilidade básica e documentação operacional.

## Histórias do usuário

### US-01 — Preparar o ambiente do backend

Como pessoa desenvolvedora, quero instalar e executar o backend com comandos documentados para começar a implementar features sem configurar ferramentas manualmente.

Critérios de aceite:

- O backend declara uma versão suportada do Python e todas as dependências em `pyproject.toml`.
- Um arquivo de lock permite reproduzir a resolução de dependências.
- Há comandos documentados para instalar, executar, verificar qualidade, testar e aplicar migrações.
- O backend inicia com um único comando após as variáveis obrigatórias e o banco estarem disponíveis.
- As dependências do frontend permanecem separadas das dependências do backend.

### US-02 — Evoluir o sistema por módulos desacoplados

Como pessoa mantenedora, quero uma arquitetura com responsabilidades explícitas para adicionar agentes, provedores e persistência sem misturar regras de negócio com frameworks.

Critérios de aceite:

- A estrutura separa, no mínimo, API, aplicação, domínio, grafo de agentes e infraestrutura.
- O domínio e os contratos de aplicação não importam FastAPI, classes concretas de banco nem SDKs de provedores externos.
- Dependências externas são acessadas por adaptadores substituíveis definidos a partir de contratos internos.
- A composição das dependências acontece em um ponto explícito da aplicação.
- Um teste arquitetural detecta dependências proibidas entre as camadas.

### US-03 — Operar a API com segurança básica

Como pessoa operadora, quero saber se o processo está vivo e se suas dependências essenciais estão prontas sem expor segredos ou detalhes internos.

Critérios de aceite:

- `GET /health/live` responde sem consultar serviços externos.
- `GET /health/ready` verifica PostgreSQL e Qdrant e usa status HTTP não exitoso quando uma dependência essencial não está pronta.
- Respostas de erro seguem um formato único e incluem um identificador de correlação, sem stack trace ou segredo.
- Cada requisição produz log estruturado com identificador de correlação, método, rota, status e duração.
- CORS utiliza uma allowlist configurável e não combina credenciais com origem curinga.
- A documentação OpenAPI é gerada pelo próprio contrato da API.

### US-04 — Configurar serviços sem segredos no repositório

Como pessoa desenvolvedora, quero configurar ambientes por variáveis validadas para alternar banco e provedores sem alterar código-fonte.

Critérios de aceite:

- Existe `.env.example` com todas as chaves aceitas, valores não sensíveis e comentários suficientes para uso local.
- Arquivos `.env` reais e credenciais não são versionados.
- Configurações inválidas ou variáveis obrigatórias ausentes falham na inicialização com mensagem acionável e sem revelar valores secretos.
- PostgreSQL, Qdrant, chat model, embeddings e reranker têm configurações independentes.
- URLs, nomes de modelos, timeouts, número máximo de tentativas e dimensão dos embeddings são configuráveis quando aplicáveis.
- Configurações possuem testes unitários para valores padrão, parsing e falhas de validação.

### US-05 — Persistir dados e preparar recuperação híbrida

Como pessoa desenvolvedora dos agentes, quero uma fundação de dados versionada para consultar startups, guardar evidências e posteriormente recuperar conhecimento NVIDIA.

Critérios de aceite:

- Migrações criam as tabelas iniciais para startups, documentos de evidência, execuções de análise, documentos da base de conhecimento e chunks.
- Todo documento de evidência mantém sua URL de origem e vínculo com a startup.
- Todo chunk mantém vínculo com seu documento de origem e metadados necessários para citação.
- Chunks mantêm representação textual para o índice BM25 e correspondência estável com os pontos vetoriais do Qdrant.
- Índices atendem chaves estrangeiras e filtros principais no PostgreSQL; uma coleção Qdrant versionada atende similaridade vetorial.
- Migrações podem avançar a partir de um banco vazio e reverter a revisão desta feature.
- A camada de aplicação acessa dados por contratos de repositório; detalhes de SQL permanecem na infraestrutura.
- Testes de integração comprovam conexão, migração, escrita e leitura mínimas em PostgreSQL e Qdrant reais.

### US-06 — Preparar a orquestração multiagente

Como pessoa desenvolvedora dos agentes, quero contratos tipados de estado e execução do grafo para implementar cada nó de forma incremental e rastreável.

Critérios de aceite:

- Existe um estado tipado do LangGraph que contempla consulta, filtros, startups candidatas, perfis estruturados, classificações, afirmações validadas, gaps, trechos NVIDIA, recomendações, briefing e diagnósticos.
- Itens de evidência e trechos recuperados carregam identificador da fonte e dados suficientes para produzir citação.
- Os identificadores dos oito nós previstos no TAPI são definidos em um único local, sem implementar sua lógica.
- Nós futuros dependem de um contrato uniforme, testável isoladamente e compatível com atualização parcial de estado.
- A construção do grafo fica separada da implementação dos nós e da inicialização da API.
- A fundação não simula resultados, não chama LLMs e não expõe uma rota de análise incompleta.

### US-07 — Verificar qualidade continuamente

Como pessoa mantenedora, quero verificações automatizadas e determinísticas para impedir regressões na base técnica.

Critérios de aceite:

- Formatação, lint, análise estática de tipos e testes possuem comandos separados e um comando agregado de verificação.
- A suíte distingue testes unitários de testes de integração que dependem de PostgreSQL e Qdrant.
- Testes não fazem chamadas reais a LLM, embeddings ou reranker.
- A integração contínua executa as verificações do backend e preserva as verificações existentes do frontend.
- O backend mantém cobertura mínima de 80% para o código introduzido nesta feature, sem excluir módulos apenas para elevar a métrica.

## Requisitos funcionais

- **RF-01:** fornecer uma aplicação FastAPI versionada sob o prefixo `/api/v1`.
- **RF-02:** fornecer endpoints independentes de liveness e readiness.
- **RF-03:** carregar e validar configuração a partir do ambiente.
- **RF-04:** propagar um identificador de correlação em requisições, erros e logs.
- **RF-05:** versionar o schema do PostgreSQL por migrações reversíveis.
- **RF-06:** fornecer contratos assíncronos para persistência de startups, documentos, execuções e chunks.
- **RF-07:** fornecer contratos independentes para chat model, embeddings e reranking.
- **RF-08:** definir modelos de domínio e o estado compartilhado da pipeline multiagente.
- **RF-09:** definir os identificadores dos nós Query Planner, Retriever, Extractor, Startup Classifier, Evidence Validator, NVIDIA RAG, Recommendation e Briefing.
- **RF-10:** fornecer composição explícita das configurações, conexões e adaptadores da aplicação.

## Requisitos não funcionais

- **RNF-01:** utilizar Python 3.12 ou superior, com tipagem estrita no código da aplicação.
- **RNF-02:** utilizar operações assíncronas nos limites de I/O da API, banco e provedores.
- **RNF-03:** manter tempo de resposta de `GET /health/live` inferior a 200 ms no ambiente local, medido sem carga e sem incluir a inicialização do processo.
- **RNF-04:** não registrar chaves, tokens, credenciais, conteúdo integral de prompts ou documentos.
- **RNF-05:** utilizar timeouts finitos em toda integração de rede e permitir tentativas apenas para falhas transitórias e operações seguras.
- **RNF-06:** representar datas em UTC e identificadores persistentes em UUID.
- **RNF-07:** manter migrações compatíveis com PostgreSQL 16 e testes de integração compatíveis com as versões de PostgreSQL e Qdrant fixadas para o projeto.
- **RNF-08:** utilizar UTF-8 e preservar textos em português.
- **RNF-09:** encerrar conexões e pools de forma ordenada no shutdown da aplicação.
- **RNF-10:** manter documentação suficiente para uma nova pessoa executar o backend a partir de um clone limpo.

## Regras de dados e contratos

- Uma startup pode possuir muitos documentos de evidência.
- Uma execução de análise registra status, timestamps e a consulta original; seus resultados completos serão definidos em specs posteriores.
- Um documento da base de conhecimento pode possuir muitos chunks.
- Uma afirmação só poderá ser considerada validada futuramente quando referenciar ao menos um documento de evidência existente.
- Uma recomendação futura deverá referenciar evidências da startup e chunks da base NVIDIA; esta feature apenas garante que os identificadores possam transitar no estado.
- Exclusões em cascata só são permitidas entre um agregado e seus filhos técnicos, nunca entre uma execução de análise e suas fontes.

## Restrições

- LangGraph é o mecanismo obrigatório de orquestração da pipeline multiagente.
- PostgreSQL é a fonte de verdade dos dados estruturados e dos textos citáveis.
- Qdrant armazena e consulta os vetores derivados dos chunks, sem se tornar fonte única do conteúdo.
- A recuperação deve poder combinar similaridade vetorial no Qdrant, busca lexical BM25 e reranking pelo adaptador Cohere.
- O repositório não pode conter credenciais nem depender de serviços pagos para executar testes.
- A API deve continuar no mesmo repositório do frontend, com comandos e dependências isolados.
- Toda mudança de comportamento posterior deve possuir sua própria especificação aprovada.

## Fora do escopo

- Implementar prompts ou lógica dos oito agentes.
- Montar ou executar o grafo completo de negócio.
- Implementar consulta de startups, classificação, validação, recomendação ou briefing.
- Ingerir, limpar, dividir ou gerar embeddings de conteúdo real.
- Popular a base com as 30 a 80 startups sugeridas pelo TAPI.
- Construir crawlers, scrapers ou enriquecimento automático por fontes externas.
- Expor endpoints de análise ou integrar o frontend à API.
- Implementar autenticação, autorização, filas distribuídas, cache ou intervenção humana.
- Definir o diferencial competitivo do projeto.
- Implantar a aplicação em nuvem ou em produção.

## Matriz de rastreabilidade

| História | Requisitos | Validação |
| --- | --- | --- |
| US-01 | RNF-01, RNF-10 | Instalação a partir do lockfile e execução dos comandos documentados |
| US-02 | RF-06 a RF-10 | Inspeção da arquitetura e teste automatizado de dependências entre camadas |
| US-03 | RF-01, RF-02, RF-04, RNF-03 a RNF-05, RNF-09 | Testes da API, logs e ciclo de vida |
| US-04 | RF-03, RF-07, RNF-04, RNF-05 | Testes unitários da configuração e inspeção de arquivos versionados |
| US-05 | RF-05, RF-06, RNF-02, RNF-06 a RNF-08 | Migrações e testes de integração com PostgreSQL e Qdrant |
| US-06 | RF-07 a RF-10 | Testes de tipos, serialização e atualização parcial do estado |
| US-07 | RNF-01, RNF-07, RNF-10 | Pipeline de qualidade, cobertura e integração contínua |

## Critério de conclusão da feature

A feature estará concluída somente quando todos os critérios de aceite forem verificados, todas as tarefas estiverem marcadas como concluídas, as integrações tiverem sido testadas em PostgreSQL e Qdrant reais, os comandos de qualidade do frontend e do backend passarem e a documentação refletir a arquitetura efetivamente implementada.
