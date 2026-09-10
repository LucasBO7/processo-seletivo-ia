# Plano 019: avaliação de qualidade

## Estratégia

Criar um módulo `app.evaluation` independente de infraestrutura e um diretório de
artefatos em `backend/evaluation`. Casos esperados e predições usam JSON simples. O
scorer transforma ambos em métricas puras; o relatório consome somente os agregados.
O adaptador opcional de API converte a resposta pública da spec 017 no mesmo formato
de predição, evitando uma segunda implementação das regras dos agentes.

## Estrutura

```text
backend/
├── evaluation/
│   ├── cases.v1.json
│   ├── predictions.reference.v1.json
│   ├── thresholds.v1.json
│   └── RUBRIC.md
└── src/app/evaluation/
    ├── cli.py
    ├── loader.py
    ├── metrics.py
    ├── models.py
    └── report.py
```

## Decisões

- Métricas usam matching normalizado exato de IDs, enums e fragmentos anotados.
- Rankings ausentes valem zero; conjuntos esperados vazios são excluídos da média da
  métrica correspondente, não convertidos artificialmente em acerto.
- O antes do reranking é ordenado pelo `hybrid_score`; o depois usa a ordem pública
  dos chunks retornados pelo RAG.
- Métricas globais são macro-médias por caso para não favorecer consultas maiores.
- O relatório lista somente IDs reprovados e agregados seguros.
- A CLI ao vivo usa a API HTTP local e nunca lê chaves de provedor.

## Verificação

1. Validar schema, unicidade, referências e thresholds dos artefatos.
2. Testar fórmulas com exemplos mínimos e bordas de listas vazias.
3. Testar aprovação, regressão de reranking, violações e sanitização do relatório.
4. Testar o bloqueio de execução real sem opt-in antes de qualquer rede.
5. Executar o benchmark de referência, Ruff, mypy, import-linter e pytest offline.

## Resultado da implementação

- Benchmark de referência aprovado nas 17 métricas objetivas/subjetivas.
- MRR NVIDIA evoluiu de 0,500 antes do reranking para 1,000 depois dele.
- Suíte backend: 359 testes aprovados e 7 testes de integração opcionais ignorados.
- Ruff, mypy, import-linter, lint, testes e build do frontend aprovados.

## Sugestão de commit

`feat(evaluation): add reproducible pipeline quality benchmark`
