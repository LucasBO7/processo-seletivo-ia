# AGENTS.md

## Regras gerais

- Sempre ler arquivos em /specs antes de implementar
- Nunca implementar sem critérios de aceitação
- Código deve ser simples e legível
- Evitar overengineering
- O código deve sempre utilizar boas práticas
- No final de cada spec, colocar sempre uma sugestão de commit baseado no que foi/será realizado naquelas tarefas

## Fluxo obrigatório

1. Ler as especs do diretório /specs
2. Gerar tasks.md se não existir
3. Implementar baseado nas tasks
4. Criar testes automatizados
5. Garantir que todos os critérios de aceitação passam

## Testes

- Priorizar cobertura dos critérios de aceitação
- Testes devem ser claros e diretos
- Nunca chamar LLM real em testes automatizados; usar `FakeChatModel`,
  `SequenceChatModel` ou cliente de adaptador falso
- Manter consultas, documentos e respostas falsas no menor tamanho necessário
  para o critério testado
- Serializar payloads de prompt sem espaços opcionais para reduzir tokens

## Restrições

- Não inventar requisitos não descritos
- Não alterar comportamento sem atualizar spec
