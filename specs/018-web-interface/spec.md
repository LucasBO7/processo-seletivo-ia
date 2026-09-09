# Especificação 018: interface web de análise

## Status

Aprovada para implementação em 9 de setembro de 2026 pelo pedido explícito da
funcionalidade.

## Contexto

A especificação 017 consolidou `POST /api/v1/search` como a única rota da análise
completa e definiu seis desfechos tipados. O frontend React existente ainda apresenta
somente a fundação visual e não permite operar o pipeline.

## Histórias e critérios de aceite

### US-01 — Consultar startups

- A página oferece uma consulta obrigatória em linguagem natural, limitada a 2.000
  caracteres, e envia uma única requisição para `POST /api/v1/search`.
- Setor, estágio, porte e localização podem ser informados como filtros explícitos.
- Setor, estágio e porte oferecem somente valores canônicos aprovados na spec 008.
- Como a API recebe apenas `query`, filtros selecionados são anexados como contexto
  textual inequívoco; planejamento, normalização e aplicação continuam no backend.
- A URL base é uma configuração pública opcional e nenhuma credencial é incluída no
  código ou no bundle.

### US-02 — Acompanhar e compreender o resultado

- Durante a requisição, a interface bloqueia novo envio, anuncia o carregamento e
  apresenta as oito etapas da pipeline sem simular progresso individual.
- Sucesso, esclarecimento, consulta inválida, ausência de resultados,
  indisponibilidade e falha interna possuem mensagens e tratamentos distintos.
- Erros de rede ou respostas incompatíveis são sanitizados antes de serem exibidos.
- Perguntas e ambiguidades do Query Planner aparecem em linguagem compreensível e
  podem ser usadas como apoio para reformular a consulta.

### US-03 — Explorar startups e análise

- As startups encontradas aparecem em uma lista selecionável com nome e score.
- A seleção controla todas as seções por `startup_id`, sem misturar empresas.
- A interface apresenta perfil validado (ou estruturado), maturidade de IA,
  evidências, gaps, contexto NVIDIA, recomendações e briefing executivo disponíveis.
- Ausências e resultados parciais são indicados sem inventar conteúdo.

### US-04 — Acessar fontes e exportar o briefing

- URLs HTTP(S) das evidências de startup e URLs HTTPS das fontes NVIDIA são links
  acessíveis, abertos em nova aba com isolamento do contexto de navegação.
- URLs inválidas ou protocolos não permitidos são mostrados como indisponíveis.
- O briefing é exibido como texto, sem interpretar Markdown ou HTML não confiável.
- A exportação baixa um arquivo UTF-8 `.md` contendo exatamente o campo `markdown`
  retornado pelo backend, com nome de arquivo local sanitizado.

### US-05 — Usar em diferentes dispositivos e por teclado

- Formulário, estados, lista e detalhes usam elementos semânticos e rótulos visíveis.
- Controles são operáveis por teclado, foco é visível e atualizações relevantes usam
  regiões anunciáveis.
- O layout permanece utilizável a partir de 320 px e em desktop.

### US-06 — Manter qualidade e limites arquiteturais

- Um cliente HTTP tipado concentra URL, serialização, timeout, resposta e erros.
- Componentes são simples e reutilizáveis; regras de classificação, evidência,
  recomendação e briefing não são recalculadas no frontend.
- Testes offline cobrem envio, filtros, loading, sucesso e seleção, esclarecimento,
  validação, vazio, indisponibilidade, erro, links seguros e exportação.
- Lint, testes e build permanecem verdes.

## Fora do escopo

- Streaming ou progresso por agente em tempo real.
- Autenticação, histórico, persistência ou edição do resultado.
- PDF, slides ou re-renderização do Markdown.
- Alteração da taxonomia, dos agentes, do grafo ou do contrato do backend.

## Critério de conclusão

A funcionalidade estará concluída quando a pessoa puder consultar a API completa,
compreender qualquer desfecho, navegar pelos artefatos isolados por startup, acessar
fontes seguras, exportar o Markdown do briefing e todas as verificações passarem.

## Sugestão de commit

`feat(frontend): add full startup analysis interface`
