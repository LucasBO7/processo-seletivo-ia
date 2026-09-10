# Rubrica de avaliação humana

Use esta rubrica somente quando a adequação não puder ser decidida pelos campos
objetivos. Dois avaliadores devem pontuar cada caso de forma independente; divergência
maior que um ponto exige consenso documentado fora do relatório automatizado.

## Dimensões e âncoras

| Nota | Relevância | Fundamentação | Especificidade | Acionabilidade |
| ---: | --- | --- | --- | --- |
| 1 | Não responde ao caso. | Afirmações centrais sem evidência. | Texto genérico aplicável a qualquer empresa. | Não contém próximo passo executável. |
| 2 | Responde parcialmente, com desvio material. | Parte das conclusões possui citação pertinente. | Cita uma necessidade ou tecnologia, mas sem vínculo claro. | Próximo passo existe, mas não define ação ou alvo. |
| 3 | Responde ao objetivo sem desvio material. | Toda conclusão central possui fonte pertinente. | Relaciona necessidade, tecnologia e contexto da startup. | Define ação concreta e responsável implícito. |
| 4 | Prioriza precisamente o que mais importa no caso. | Evidências independentes e localizadores sustentam as conclusões. | Explica vínculo técnico e de negócio sem extrapolação. | Define ação verificável, critério de saída e dependências. |

## Regra de aceite

- Média das quatro dimensões: pelo menos `3,0`.
- Nenhuma dimensão abaixo de `2`.
- A nota é registrada em `rubric` na predição pelo ID do caso.
- Sem notas para todos os casos, o relatório marca `not_evaluated` e não presume
  aprovação humana.

## Dados proibidos

Não copiar para a rubrica prompts, respostas brutas, credenciais, cabeçalhos, dados
pessoais ou stack traces. Registre somente as quatro notas e o ID público do caso.
