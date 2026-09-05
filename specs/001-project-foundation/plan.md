# Plano 001: fundação do projeto

## Estratégia

A entrega é documental e frontend-first. O repositório recebe uma aplicação Vite independente, enquanto todas as decisões de backend permanecem deliberadamente abertas.

## Arquitetura dentro do escopo

```text
index.html
└── src/main.tsx
    └── pages/HomePage.tsx
        └── components/ProjectScope.tsx
```

- `main.tsx` inicializa o React e carrega os estilos globais.
- `HomePage.tsx` compõe a única página desta fundação.
- `ProjectScope.tsx` apresenta itens reutilizáveis de escopo.
- Não há camada de acesso a dados, cliente HTTP ou estado remoto.

## Decisões

### D-01 — Vite como fundação do frontend

Vite fornece o ciclo de desenvolvimento e o build de uma aplicação React/TypeScript com configuração pequena e explícita.

### D-02 — Aplicação independente de backend

Nenhum contrato de API será antecipado. Isso evita restringir a arquitetura que será desenhada posteriormente.

### D-03 — SDD armazenado no repositório

Cada mudança relevante deverá possuir especificação, plano e tarefas versionados em `specs/`. A documentação é a fonte de verdade para o escopo aprovado.

### D-04 — Testes restritos à experiência atual

Os testes verificam apenas conteúdo e comportamento do frontend. Não serão criados mocks de APIs inexistentes.

### D-05 — Sem contêineres

Não serão adicionados Dockerfile, Compose, imagens, volumes ou instruções relacionadas a Docker.

## Verificação

1. Instalar dependências com npm.
2. Executar ESLint.
3. Executar os testes do frontend.
4. Executar a checagem TypeScript e o build Vite.
5. Inspecionar a estrutura do repositório para garantir a ausência de backend e Docker.
6. Conferir a coerência entre README, especificação e tarefas.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Diagramas muito largos no GitHub | Organizar etapas em subgraphs e manter textos condensados |
| Frontend criar dependência acidental do backend | Não adicionar cliente HTTP, variáveis de endpoint ou mocks de API |
| Opções removidas parecerem aprovadas | Mantê-las em documento separado com status explícito |
| SDD se tornar apenas documentação histórica | Exigir critérios de aceite e matriz de rastreabilidade em cada feature |
