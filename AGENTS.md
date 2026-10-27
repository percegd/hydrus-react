# AGENTS.md

## Regras de comportamento para agentes de código (Karpathy)

Fonte: [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md), baseado nas observações de Andrej Karpathy sobre erros comuns de LLMs ao programar.

Estas regras priorizam cautela em vez de velocidade. Em tarefas triviais, use bom senso.

### 1. Pense antes de codar

**Não presuma. Não esconda dúvidas. Exponha os prós e contras.**

Antes de implementar:
- Declare suas premissas de forma explícita. Se estiver em dúvida, pergunte.
- Se houver mais de uma interpretação, apresente-as; não escolha uma em silêncio.
- Se existir um caminho mais simples, diga. Discorde quando fizer sentido.
- Se algo não estiver claro, pare. Diga o que está confuso. Pergunte.

### 2. Simplicidade primeiro

**O mínimo de código que resolve o problema. Nada especulativo.**

- Nenhuma funcionalidade além do que foi pedido.
- Nenhuma abstração para código usado uma única vez.
- Nenhuma "flexibilidade" ou "configurabilidade" que não foi pedida.
- Nenhum tratamento de erro para cenários impossíveis.
- Se você escreveu 200 linhas e dava para fazer em 50, reescreva.

Pergunte-se: "Um engenheiro sênior diria que isso está complicado demais?" Se sim, simplifique.

### 3. Mudanças cirúrgicas

**Mexa só no necessário. Limpe só a sua própria bagunça.**

Ao editar código existente:
- Não "melhore" código, comentários ou formatação vizinhos.
- Não refatore o que não está quebrado.
- Siga o estilo existente, mesmo que você fizesse diferente.
- Se notar código morto sem relação com a tarefa, mencione; não apague.

Quando suas mudanças deixarem sobras:
- Remova imports, variáveis e funções que as SUAS mudanças deixaram sem uso.
- Não remova código morto que já existia, a menos que peçam.

O teste: cada linha alterada deve ter ligação direta com o pedido do usuário.

### 4. Execução orientada a objetivos

**Defina critérios de sucesso. Repita até verificar.**

Transforme tarefas em objetivos verificáveis:
- "Adicionar validação" → "Escrever testes para entradas inválidas e depois fazê-los passar"
- "Corrigir o bug" → "Escrever um teste que reproduz o bug e depois fazê-lo passar"
- "Refatorar X" → "Garantir que os testes passam antes e depois"

Em tarefas com várias etapas, apresente um plano curto:
```
1. [Etapa] → verificar: [checagem]
2. [Etapa] → verificar: [checagem]
3. [Etapa] → verificar: [checagem]
```

Critérios fortes permitem trabalhar sozinho até o fim. Critérios fracos ("fazer funcionar") exigem pedir esclarecimento o tempo todo.

**Sinais de que as regras estão funcionando:** diffs com menos mudanças desnecessárias, menos reescritas por excesso de complexidade e perguntas de esclarecimento antes da implementação, não depois dos erros.

## Segurança

- Use a skill `security-audit` (Cloudflare, Apache-2.0) em `.agents/skills/security-audit/`. O opencode a descobre sozinho nesse caminho.
- Padrão: modo guia (perguntas e revisões pontuais de segurança). Auditoria completa só quando alguém pedir explicitamente.
- Relatórios ficam fora do repo, em `~/security-audit-skill/hydrus-react/`. Nunca commite relatórios.

## Revisão com Ponytail

- Plugin `@dietrichgebert/ponytail` do opencode.
- Revisão: `opencode run -m <modelo> --command ponytail-review "<escopo>" < /dev/null`
- Auditoria de dívida técnica: `opencode run -m <modelo> --command ponytail-audit "<escopo>" < /dev/null`

## Regras do Arthur para mudanças

1. **Menos texto na interface.** Remova slogans desnecessários, textos explicativos e tags secundárias. Se, depois da remoção, a interface ficar incompreensível, o problema está no layout. Nesse caso, refaça o layout em vez de devolver o texto.
2. **Três experiências.** Toda modificação deve considerar a experiência do usuário, a experiência de desenvolvimento e a experiência de uso por agentes de IA. As três devem melhorar, sem comprometer as funcionalidades existentes.
