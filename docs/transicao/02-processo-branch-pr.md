# Processo de Branch / Pull Request

> **ATIVO desde 2026-08-13 (Sessão 197)** — deixou de ser plano da Fase 3 e passou a ser o
> processo corrente: já com Marcelo + Juliana desenvolvendo, todo código novo entra por branch +
> PR, sem esperar o Wesley entrar. Fase 3, item 5 do Plano de Transição: "Fluxo de branches/PR
> (sem etapa de ambiente local compartilhado): cada dev trabalha isolado na própria máquina, abre
> PR, Juliana revisa e aprova o merge direto em Instância A/Integração." Juliana segue livre pra
> ajustar o que achar necessário antes de repassar pro Wesley no onboarding técnico dele.

## Por que muda

Até 2026-08-05, todo o desenvolvimento foi feito por Marcelo com o Claude Code, numa única
máquina, commitando **direto na `main`** — sem branch de feature, sem PR, sem revisão de
terceiro (a "revisão" era o próprio Claude Code auditando o diff, mais teste manual do
Marcelo). Isso funcionou por ser 1 pessoa só. Com 2+ devs no mesmo repo, commit direto na
`main` gera conflito e código sem segundo par de olhos antes de ir pro ambiente compartilhado
(Instância A). A partir de 2026-08-13 (Sessão 197), todo código novo entra por PR.

## Fluxo

1. **Branch a partir da `main` atualizada.** Nome sugerido: `feat/<assunto>`, `fix/<assunto>`
   (mesmo padrão que já aparece no histórico do repo — ver `git log --oneline` pra exemplos
   reais de nomes usados). Uma branch por frente de trabalho, não uma branch guarda-chuva.
2. **Desenvolve isolado.** Sem servidor local compartilhado — cada dev roda `./run.sh` na
   própria máquina, contra o próprio Postgres local (dev), não contra o Postgres de nenhum
   ambiente remoto.
3. **Antes de abrir o PR:**
   - `python3 -m pytest -q` **verde** (backend). Não abre PR com teste quebrado, nem "vou
     arrumar depois".
   - Se mexeu em `static/index.html`: `node --check` no `<script>` extraído, limpo.
   - Se mexeu em área sensível (contrato, negociação, financeiro/D2, tenancy/escopo, Chat) —
     ver a lista em `CLAUDE.md` §"Áreas sensíveis" — descrever no PR o que foi validado.
4. **Abre o Pull Request no GitHub** (`mbnunes1972/orizon-manager`) contra a `main`.
   Descrição mínima: o que mudou, por quê, como foi testado. Se a mudança tem uma spec em
   `docs/superpowers/specs/`, linkar.
5. **Juliana revisa.** Critérios de aprovação:
   - Suíte passa (CI ou rodada local — decidir se/quando entra CI automatizado; não existe
     ainda).
   - O código bate com a spec/decisão registrada, quando houver uma.
   - Sem regressão óbvia em área sensível.
   - Convenções do projeto respeitadas (ver `CLAUDE.md`: não usar `git add .`, testes TDD nos
     módulos Python, etc.).
6. **Merge na `main`.** Squash ou merge normal — decidir e documentar aqui quando a equipe
   escolher (não há preferência registrada ainda).
7. **Deploy na Instância A** segue o runbook existente (`DEV_RULES.md`) — quem tiver acesso
   SSH à VPS de dev roda o deploy depois do merge (não é automático/CI ainda; virar pipeline
   automatizado é uma melhoria futura, não bloqueia a transição).
8. **Promoção pra Instância B e Produção** exige **aprovação visual de Marcelo** antes de cada
   uma — isso é o gate que sempre existiu e continua existindo, só que agora depois de já ter
   passado por PR + merge na A.

## O que NÃO muda

- Os 3 ambientes (Integração, Homolog, Produção) e seus runbooks de deploy — `DEV_RULES.md`
  continua sendo a referência.
- A suíte de testes como critério técnico de "pronto".
- `DEV_LOG.md` como registro do que foi feito — toda frente fechada ganha uma entrada nova lá
  (`## Sessão N`), documentando o quê e o porquê, igual sempre foi feito.
- Reingestão do grafo MCP (se a equipe optar por manter essa ferramenta de consulta) depois de
  merge relevante.

## Pontos em aberto (decidir com a equipe, não assumidos aqui)

- **CI automatizado** (GitHub Actions rodando a suíte a cada PR) — hoje não existe; é rodada
  manual. Vale considerar assim que Wesley estiver ativo, pra não depender de disciplina manual
  de cada dev.
- **Squash vs. merge commit** — sem convenção definida ainda.
- **Quem faz o deploy físico** (SSH na VPS) depois do merge — hoje é o Marcelo/quem estiver com
  acesso; decidir se Juliana assume esse passo ou se automatiza.
