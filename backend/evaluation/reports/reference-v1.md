# Relatório resumido de qualidade

- Dataset: `v1`
- Predições: `v1`
- Execução: `reference-v1` (`offline`)
- Casos avaliados: 3
- Resultado: **APROVADO**
- Rubrica humana: `evaluated`

## Métricas

| Dimensão | Resultado | Mínimo | Status | Casos abaixo do limite |
| --- | ---: | ---: | --- | --- |
| Estruturação da consulta | 1.000 | 0.850 | OK | — |
| Recuperação de startups — recall@5 | 1.000 | 0.800 | OK | — |
| Recuperação de startups — precision@5 | 1.000 | 0.600 | OK | — |
| Recuperação de startups — MRR | 1.000 | 0.750 | OK | — |
| Extração — recall de fatos | 1.000 | 0.850 | OK | — |
| Extração — ausência de fatos proibidos | 1.000 | 1.000 | OK | — |
| Classificação de maturidade | 1.000 | 0.900 | OK | — |
| Suporte factual | 1.000 | 0.900 | OK | — |
| Recuperação NVIDIA — recall@5 | 1.000 | 0.800 | OK | — |
| Recuperação NVIDIA — precision@5 | 0.722 | 0.600 | OK | — |
| Reranking — MRR final | 1.000 | 0.800 | OK | — |
| Reranking — delta de MRR | 0.500 | 0.000 | OK | — |
| Citações — URLs válidas | 1.000 | 0.950 | OK | — |
| Citações — recall esperado | 1.000 | 0.900 | OK | — |
| Adequação das recomendações | 1.000 | 0.800 | OK | — |
| Ausência de recomendações proibidas | 1.000 | 1.000 | OK | — |
| Rubrica humana | 0.917 | 0.750 | OK | — |

## Efeito do reranking

| Ordem | MRR |
| --- | ---: |
| Antes (híbrida) | 0.500 |
| Depois (reranker) | 1.000 |
| Delta | +0.500 |

> O relatório contém apenas métricas e IDs versionados; respostas brutas não são persistidas.
