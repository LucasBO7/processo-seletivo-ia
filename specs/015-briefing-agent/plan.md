# Plano 015: Briefing Agent

## Estratégia

Separar a consolidação determinística da narrativa gerada. O agente agrupa o estado
por startup, copia fatos e recomendações sem reescrita, constrói catálogos de
citações e permite ao `llm_heavy` produzir somente declarações tipadas que escolhem
IDs permitidos. Após validação, o código resolve as referências e renderiza Markdown.

## Estrutura prevista

```text
backend/src/app/application/contracts/briefing.py
backend/src/app/graph/agents/briefing.py
backend/src/app/graph/prompts/briefing.py
backend/src/app/core/config.py
backend/src/app/core/resources.py
backend/src/app/graph/state.py
backend/src/app/graph/builder.py
backend/src/app/api/routes/search.py
backend/src/app/api/status.py
backend/tests/unit/test_briefing_agent.py
```

## Fases

1. Definir contratos cru/final, seções, citações e configuração.
2. Agrupar recomendações e entradas auxiliares por `startup_id`.
3. Construir fatos e catálogos citáveis com limites determinísticos.
4. Gerar declarações por startup com prompt compacto e versionado.
5. Validar IDs, tipos de declaração, suporte duplo e regra Inception.
6. Resolver citações e renderizar Markdown somente do contrato validado.
7. Implementar reparo, parcialidade, métricas, logs e erros sanitizados.
8. Integrar composição, estado, grafo, API, documentação e testes.

## Decisões

### D-01 — Seções factuais não são geradas pelo modelo

Perfil, maturidade, sinais, stack, gaps e recomendações são derivados diretamente do
estado. O modelo não recebe autoridade para mudar prioridade, tecnologia ou fonte.

### D-02 — Narrativa mínima e citada

O modelo retorna somente `executive_summary`, `inception_opportunities` e
`uncertainties_and_gaps`, compostos por texto, natureza e IDs permitidos.

### D-03 — Markdown como projeção

O Markdown é renderizado pelo código a partir do contrato final. Assim, a versão
textual não diverge da resposta estruturada e não constitui uma segunda geração.

### D-04 — Inception condicionado a chunk oficial

Oportunidades só são aceitas com citação de startup e citação NVIDIA cuja tecnologia
seja `nvidia_inception`; ausência de fonte produz seção vazia e aviso.

### D-05 — Lote atômico por startup

Uma declaração inválida aciona reparo e, se persistir, impede somente o briefing
daquela startup. Briefings anteriores permanecem no patch.

## Verificação

1. Testar contratos, limites, agrupamento e ausência de recomendações.
2. Testar fatos, maturidade, sinais, stack, gaps e recomendações derivadas.
3. Testar allowlists, citações fabricadas, suporte duplo e Inception.
4. Testar Markdown, ordem, fontes, escaping e limite.
5. Testar reparo, indisponibilidade, dados parciais e sucesso parcial.
6. Testar roteamento, estado, API, OpenAPI e HTTP 502/503.
7. Executar Ruff, mypy, import-linter, pytest com cobertura e integrações.
8. Executar lint, testes e build do frontend.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Narrativa criar fatos | Seções derivadas + IDs permitidos + validação semântica |
| Mistura entre startups | Particionamento obrigatório por `startup_id` |
| Citação fabricada | Modelo seleciona IDs; agente resolve referências completas |
| Inception tratado como elegibilidade | Tipo inferência + chunk Inception obrigatório |
| Markdown divergir | Renderização única a partir do contrato final |
| Contexto excessivo | Limites e truncamento determinístico |
| Falha apagar resultados | Atomicidade por startup e patch acumulativo |

## Sugestão de commit

`feat(briefing): generate cited executive startup briefings`
