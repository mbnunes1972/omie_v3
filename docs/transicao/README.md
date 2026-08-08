# Transição do desenvolvimento — Orizon Manager

Documentos de apoio ao **Plano de Transição** (`Plano-Transicao-Orizon.docx`, Marcelo,
2026-08-05): passagem do desenvolvimento — hoje Marcelo + Claude Code numa máquina só — para
uma equipe interna (Juliana como líder técnica, Wesley em desenvolvimento).

## O que tem aqui

| Documento | Serve pra | Fase do plano |
|---|---|---|
| [01-arquitetura-e-fluxo-ambientes.md](01-arquitetura-e-fluxo-ambientes.md) | O documento único pedido no item 1: o que é o sistema, como o código é organizado, onde estão as áreas sensíveis, e o **novo** fluxo de ambientes (PR → Instância A → Instância B → Produção) | Fase 1, item 1 |
| [02-processo-branch-pr.md](02-processo-branch-pr.md) | Define o fluxo de branch/PR que substitui o push direto na `main` de hoje — quem revisa, quem aprova, quando cada ambiente é promovido | Fase 3, item 5 |
| [03-checklist-acessos.md](03-checklist-acessos.md) | Inventário do que precisa ir pro cofre de senhas compartilhado — **sem nenhum segredo em texto**, só o que existe e onde procurar | Fase 1, item 2 |
| [04-backlog-gira.md](04-backlog-gira.md) | Backlog conhecido, extraído do DEV_LOG e das specs, pronto pra virar itens no Gira | Fase 2, item 3 |

## Como usar

1. Juliana e Marcelo revisam o **01** juntos (é o documento que o plano pede que os dois
   "reúnam" — este é o rascunho, não a versão final; ajustem o que estiver desatualizado ou
   incompleto).
2. O **03** vira a lista de tarefas de quem for popular o cofre de senhas — ninguém copia
   segredo daqui, porque não tem nenhum aqui.
3. O **04** entra no Gira como está, ou reorganizado como a ferramenta pedir.
4. O **02** é o que muda no dia a dia assim que Wesley começar a commitar — vale revisar com
   ele no onboarding técnico (Fase 2, item 4).

Fonte viva do projeto continua sendo `CLAUDE.md` (auto-carregado pelo Claude Code) +
`DEV_LOG.md` (histórico e estado atual) + `DEV_RULES.md` (regras de processo/deploy) — estes
quatro documentos aqui são um **resumo de entrada**, não substituem aqueles.

**Achado ao preparar este material:** existe uma pasta `docs/arquitetura/`, `docs/processos/`,
`docs/modulos/*/SPEC.md` e `docs/historias/BACKLOG.md` no repo que **não é atualizada desde
early julho/2026** (antes da migração pra Postgres, antes do Orizon Chat inteiro, antes da
Fase D2 financeira — praticamente metade do projeto não está lá). Não usem como referência;
vale decidir entre apagar ou marcar como arquivo morto pra não confundir quem entra agora.
