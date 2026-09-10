# Especificação 019: avaliação de qualidade

## Status

Aprovada para implementação em 9 de setembro de 2026 pelo pedido explícito da
funcionalidade.

## Contexto

A pipeline completa possui testes de contrato e integração, mas ainda não possui um
benchmark versionado que detecte regressões sem confundir correção estrutural com
qualidade do resultado. A avaliação precisa separar as nove etapas solicitadas,
comparar a ordem híbrida com a ordem pós-reranking e permitir execuções reais sem
torná-las requisito do CI.

## Histórias e critérios de aceite

### US-01 — Manter casos de referência versionados

- Um dataset JSON versionado contém ID, consulta, origem do caso, expectativas do
  plano, startups relevantes, fatos obrigatórios/proibidos, classificação, suporte
  factual, chunks/fontes NVIDIA, recomendações aceitáveis e resultados proibidos.
- Casos reais são snapshots com URLs públicas e data de revisão; casos sintéticos
  são identificados explicitamente e usados somente para cobertura de bordas.
- IDs são únicos e todas as seções mínimas são validadas antes da avaliação.

### US-02 — Medir separadamente cada etapa

- Estruturação: acurácia de status e F1 dos filtros esperados.
- Recuperação de startups: `recall@5`, `precision@5` e reciprocal rank médio (MRR).
- Extração: recall dos fatos obrigatórios e taxa de ausência de fatos proibidos.
- Maturidade: acurácia da categoria esperada.
- Suporte factual: acurácia do status esperado por afirmação.
- Recuperação NVIDIA: `recall@5` e `precision@5` das fontes relevantes.
- Reranking: MRR antes/depois e delta, usando a mesma lista candidata.
- Citações: validade de URL e recall das fontes esperadas.
- Recomendações: taxa de tecnologias aceitáveis e ausência de resultados proibidos.

### US-03 — Aplicar limites mínimos objetivos

- O arquivo de thresholds é versionado e validado no intervalo `[0, 1]`.
- Mínimos iniciais: estruturação 0,85; recall/precision@5 de startups 0,80/0,60; MRR
  de startups 0,75; recall de extração 0,85; ausência de fatos proibidos 1,00; classificação
  0,90; suporte factual 0,90; recall/precision@5 NVIDIA 0,80/0,60; MRR pós-reranking 0,80;
  delta de MRR 0,00; validade de citações 0,95; recall de citações 0,90;
  adequação de recomendações 0,80; ausência de recomendações proibidas 1,00.
- O comando retorna código diferente de zero quando qualquer limite falha.

### US-04 — Tornar julgamento subjetivo reproduzível

- Relevância, fundamentação, especificidade e acionabilidade usam escala 1–4 com
  âncoras textuais por nível.
- Avaliadores registram somente notas por dimensão e ID do caso, nunca prompts ou
  respostas brutas no relatório.
- Quando fornecida, a rubrica exige média mínima 3,0 e nenhuma dimensão abaixo de 2;
  quando ausente, o relatório marca a avaliação humana como `não executada`.

### US-05 — Executar offline e opcionalmente ao vivo

- A execução padrão lê predições versionadas, é determinística e não usa rede, LLM,
  banco, embedding ou reranker reais.
- A execução ao vivo exige simultaneamente `--live-api` e
  `RUN_LIVE_EVALUATION=1`; sem ambos, falha antes de qualquer requisição.
- O modo ao vivo chama somente a API informada, não recebe credenciais por argumento
  e registra apenas IDs de casos, métricas agregadas e status.
- Testes comuns não habilitam nem simulam provedores pagos.

### US-06 — Comparar e relatar regressões

- O relatório Markdown contém versão do dataset, execução, tabela de métricas,
  thresholds, status, comparação MRR pré/pós-reranking e casos reprovados.
- Um relatório JSON equivalente permite comparação automatizada.
- O relatório não contém consultas, evidências textuais, respostas de modelo,
  cabeçalhos HTTP, stack traces ou segredos.
- O README documenta execução offline, execução real e interpretação dos resultados.

## Fora do escopo

- Treinar modelos, alterar prompts automaticamente ou escolher tecnologias NVIDIA.
- Executar avaliações pagas no CI padrão.
- Persistir respostas brutas ou construir um dashboard histórico.
- Substituir testes unitários, de integração ou revisão humana especializada.

## Critério de conclusão

A funcionalidade estará concluída quando dataset, thresholds, scorer, CLI, rubrica,
relatórios e testes offline estiverem versionados, as nove dimensões forem reportadas
separadamente, o reranking puder ser comparado e todas as verificações passarem.

## Sugestão de commit

`feat(evaluation): add reproducible pipeline quality benchmark`
