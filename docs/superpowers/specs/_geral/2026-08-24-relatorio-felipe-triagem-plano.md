# Relatório de testes do Felipe — triagem e plano de ataque (2026-08-24)

Fonte: `Anotações ORIZON.docx` (Felipe levantou 19 itens usando o sistema; Marcelo comentou cada
um dizendo como imagina resolver). Este documento traduz aquilo em frentes, com ordem e critério.

**Contexto de execução:** o Marcelo está desenvolvendo no `localhost:8765`. A atualização geral das
VPS A e B acontece **depois** desta revisão — então nenhuma frente daqui vai pra deploy agora.

---

## Regra zero — o relatório é de um build ANTERIOR

Os prints dos itens 8 e 9 mostram a Negociação no layout velho (título "TOTAL FLEX — PARCELAMENTO
LIVRE", campos da modalidade em card próprio abaixo da tabela). Desde então entraram os blocos 1–3
e o bloco 7 do `docs/design/brief-negociacao-layout.md`. Parte do que o Felipe reclama no item 8
("não consigo retornar à visualização anterior" para editar as datas das parcelas) pode ter caído
junto com essa reorganização.

**Antes de escrever qualquer linha de código: repassar os 19 itens contra a `main` de hoje** e
classificar cada um em `JÁ RESOLVIDO` / `CONFIRMADO` / `PRECISA REPRO` / `PRECISA PERGUNTA`.
Entregável: essa tabela no DEV_LOG, numa `## Sessão N`. Sem isso corremos o risco de gastar PR em
coisa já resolvida.

---

## Divisão de trabalho

- **Claude Code (esta sessão):** código, testes, specs, PRs.
- **Sessão Cowork (QA ao vivo pelo Chrome do Marcelo, contra o `localhost:8765`):** reproduzir os
  itens **8, 11, 12, 13 e 14** num projeto de teste e devolver passos exatos + diagnóstico.

> **Não implemente os itens 8, 12, 13 e 14 antes desse retorno.** São todos "a data/valor que
> digitei não é a que apareceu" — sem repro confiável a chance de corrigir o sintoma errado é alta.
> O item 11 é a exceção: a correção é de validação de servidor e não depende de repro.

---

## Fase 0 — Verificação (sem código)

1. Reabrir os 19 itens contra a `main`. Produzir a tabela de status descrita na regra zero.
2. **Item 9 (Total Flex → Parcelamento Loja):** a UI já diz "Parcelamento Loja". Falta varrer o
   resto — `grep -rn "Total Flex"` acha ocorrências em `mod_contabil.py` (conta `2.1.05
   "Financiamento Total Flex a Pagar"`), `mod_fin/total_flex.py`, `database.py` e `main.py`.
   Separar em três baldes e **trazer a decisão pro Marcelo antes de mexer**:
   - o que o **cliente vê** (contrato, proposta, PDF, tela) → renomear;
   - **nome de conta contábil** de conta que já tem lançamento → histórico, provavelmente NÃO
     renomear;
   - **nome de módulo/variável interna** → cosmético, decidir se vale o diff.

---

## Fase 1 — PRIORIDADE: integridade da assinatura (item 11)

Isto não é uma dúvida do Felipe, é um furo. Sintoma relatado, com print: **o mesmo usuário clicou e
assinou como "Vendedor" E como "Cliente"**, digitou o nome do cliente com o CPF do vendedor, e o
sistema liberou — resultado na tela: "✓ Contrato assinado — ambas as partes confirmaram".

O que fazer:

1. Mapear o caminho de assinatura: etapa 7 do ciclo (`mod_ciclo.py`), `_contrato_assinado` (1ª
   assinatura) vs `_contrato_totalmente_assinado` (ambas), e o endpoint que registra a assinatura
   em `main.py`.
2. Corrigir **no backend** (validação de servidor — travar só no front não resolve):
   - a segunda assinatura não pode vir do mesmo usuário da primeira;
   - o CPF informado tem que bater com o CPF cadastrado do papel que está assinando (cliente do
     projeto / vendedor responsável);
   - registrar quem assinou: usuário, papel, CPF, timestamp (e IP, se já houver esse campo).
3. **TDD:** teste que tenta assinar as duas pontas com o mesmo usuário e espera recusa; teste que
   tenta assinar com CPF divergente do cadastro e espera recusa.
4. Levantar se existe contrato já assinado nesse padrão (mesma pessoa nas duas pontas) no banco de
   dev/produção e listar pro Marcelo — sem corrigir dado por conta própria.

---

## Fase 2 — Cronograma: itens 12, 13 e 14 são UMA causa raiz

- **12:** a medição não caiu na data digitada, "deve ter seguido uma informação padrão".
- **13:** as datas não batem com a produção real; o dia 30 deveria ser "recebimento loja".
- **14:** as datas não batem e o tempo de montagem não é compatível com o tamanho do projeto; o
  compromisso final de montagem deveria ser 31/10.

Hipótese a testar: **a data digitada pelo usuário está sendo sobrescrita pelo cronograma padrão da
loja** (painel de configurações), em vez de ancorar o cronograma na data informada.

Leituras obrigatórias antes de opinar:
`docs/superpowers/specs/ciclo/2026-07-10-v11-cronograma-do-ciclo-design.md`,
`2026-07-10-v12-responsavel-por-funcao-cronograma.md`,
`2026-06-18-workflow-medicao-design.md` e
`2026-07-17-ancora-entrega-folga-venda-programada-design.md`.

**Entregável desta fase é uma nota de diagnóstico, não o fix** — cruzar com o repro da sessão de QA
antes de mexer. Se o tempo de montagem realmente não escala com o tamanho do projeto, isso é regra
de negócio nova e precisa do Marcelo/Felipe, não de código adivinhado.

---

## Fase 3 — Ajustes curtos (podem ir juntos num PR só)

- **Item 2** — "por que pedir esta informação?": o campo fica. Falta explicar na tela — hint ou
  tooltip curto ("necessário para identificar empresa contribuinte de impostos").
- **Item 5** — "por que já está entrando com este desconto automático (retirar)": o print mostra
  **"Desconto de venda 6,97%"** no modal de Parâmetros, logo abaixo do toggle "Incluir custos
  adicionais". A leitura provável é que esse número é **calculado** (o `Desc_Tot` que o motor
  devolve — desconto total resultante depois dos custos repassados), e não um desconto que o
  sistema aplicou sozinho. **Confirmar isso no código antes de qualquer coisa.**
  - Se for calculado: não é bug, é rótulo. Renomear para algo como "Desconto total resultante" e
    dar o tratamento visual de campo calculado (o mesmo `.calc-flag` que a Negociação usa em "Valor
    da liquidação"), pra ninguém mais achar que o sistema aplicou desconto sozinho.
  - Se for de fato um input com valor default: aí sim é bug, e o default vai a zero.
- **Item 9** — o que a Fase 0 tiver decidido renomear.

---

## Fase 4 — Frentes de verdade (uma por PR, nesta ordem)

Confirmei no código que nenhuma delas existe hoje.

1. **Item 1 — voltar à tela anterior.** Um mecanismo só, sempre no mesmo lugar, em todas as páginas
   internas. Ler `docs/superpowers/specs/2026-07-16-navegacao-consistente-painel-orizon-design.md`
   (que já define breadcrumb) e `docs/design/navegacao-orizon-v1.md` **antes** — o risco aqui é
   criar um segundo padrão de navegação convivendo com o primeiro.
2. **Item 4 — ordenar ambientes.** Arrastar para reposicionar, com renumeração automática
   (exemplo do Marcelo: Cozinha 1 / Suíte Master 2; arrastar a cozinha para baixo troca as duas) e
   **persistência em banco** — não existe coluna de ordem hoje, então é migração + reordenação
   transacional. Refletir a ordem na tabela da Negociação, na proposta e no PDF. O item pede também
   **renomear ambiente**.
3. **Item 3 — incluir vendedor no projeto.** O Felipe não conseguiu adicionar o André. Revisar o
   seletor de vendedores no ato de criação do projeto (e conferir se é bug de UI, de permissão ou
   de escopo por projetista — Consultor só vê os projetos que criou).
4. **Itens 7 + 17 — Kanban do funil (é o mesmo assunto).** Card precisa de nome do vendedor e valor
   do projeto, e a coluna precisa de totalização. E o 17 é a outra ponta: depois do contrato
   fechado o Felipe não achou mais o atendimento — garantir que projeto vendido continua
   localizável e visível por status (o Marcelo levanta a hipótese de um ícone próprio na barra
   lateral, tipo "Contratos"/"Pedidos de venda" — avaliar contra a navegação já existente antes de
   criar item novo de menu).
5. **Item 19 — dashboard Comercial.** Hoje `renderComercialDash` desenha funil + carteira + volume
   **sem nenhum filtro**. Falta recorte por vendedor e por período (mês / intervalo). O Marcelo
   abriu espaço explícito pra propor indicadores melhores — trazer proposta antes de implementar.
6. **Itens 6 + 15 + 16 — Agenda (frente grande, spec própria antes de código).**
   - Item 6: três botões — **Agenda Loja** (todos os eventos), **Minha Agenda** (do usuário logado)
     e **Adicionar Evento/Atividade**. O modal precisa de: atividade, data, hora, avisos (e-mail ou
     Chat Orizon), convidar participante (campo de e-mail; se for da empresa, busca no cadastro) e
     observações. Gerente pode inserir evento na agenda da equipe.
   - Item 15: na agenda geral, mostrar **nome do cliente + posição no processo** (Medição,
     Executivo, Produção, Depósito, No cliente, Em montagem, Em vistoria, Entregue, Assistência) em
     vez do rótulo atual.
   - Item 16: o detalhe do item abre com informação demais e **sem data de conclusão**.
   - Ler `docs/superpowers/specs/agenda/2026-08-03-agenda-da-loja-design.md` e
     `docs/superpowers/specs/ciclo/2026-07-14-agenda-global-projetos-design.md` antes de desenhar do
     zero — pode ser que metade disso já esteja especificado.
7. **Item 18 — chat.** Bloqueado, ver perguntas abaixo.

---

## Bloqueados — precisam de resposta do Felipe antes de virar tarefa

- **Item 10** — "contrato sem formatação para assinatura": o que exatamente está sem formatação?
  O PDF gerado, a tela de assinatura, ou o corpo do modelo da loja (`documento_modelos`)?
- **Item 18** — "como deve ser feito a integração do chat, ela acontece automaticamente?": o que
  ele espera que aconteça no chat quando o projeto é vendido? Grupo criado sozinho, com quem
  dentro, disparando o quê?
- **Item 16** — "não está dinâmica, muita informação": qual informação ele quer ver primeiro no
  detalhe do item da agenda?

---

## Processo (DEV_RULES, resumido)

- Branch `feat/<assunto>` a partir da `main` atualizada — **nunca commit direto na main**.
- Antes do PR: `python3 -m pytest -q` verde; se mexeu em `static/index.html`, `node --check` limpo
  no `<script>` extraído.
- PR contra a `main` em `mbnunes1972/orizon-manager`, descrição com o quê / por quê / como testou,
  linkando a spec.
- **Uma frente por PR.** Não juntar Agenda com Kanban com renomeação — se um trecho travar na
  revisão, trava tudo.
- DEV_LOG atualizado a cada frente fechada (nova `## Sessão N`, com [ESTADO], [PENDENTE],
  [DECIDIDO], [ARQUIVOS]).
- Nada de deploy nas VPS por enquanto — o Marcelo faz a atualização geral A/B depois desta revisão.
