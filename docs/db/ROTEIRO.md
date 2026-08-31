# Roteiro — a ordem linear de executar tudo

Criado em 29/08/2026 a pedido do usuário: *"precisamos criar um formato
linear de implementar tudo."* Este arquivo é a **fila**. Um item por vez, de
cima para baixo.

## Os quatro documentos e o que cada um responde

| documento | responde |
|---|---|
| `ACHADOS_CONTABEIS.md` | **o que está errado** — 22 achados, com medição |
| `DESENVOLVIMENTOS.md` | **o que não existe** — ausências, separadas dos defeitos |
| `ACEITE.md` | **como saber que consertou** — teste por achado |
| `TAREFA_*.md` | **como consertar** — um por frente, escrito na hora de fazer |
| `PLANO_AJUSTES.md` | **por quê e em que ordem** — regras, decisões, agrupamento |
| este arquivo | **o que fazer agora** |

**Por que "como consertar" não traz código pronto:** um documento com código
envelhece no primeiro commit e vira uma terceira fonte de verdade. A tarefa
diz o que muda, onde e sob qual regra; o código nasce no commit, e quem
garante o resultado é o teste da etapa anterior — não o texto.

## Onde estamos

Atualizar **a cada passo concluído**. Sem isto ninguém sabe o estado sem
reconstruir o histórico — e a pergunta "a sequência está sendo seguida?"
deixa de ter resposta rápida.

| passo | estado |
|---|---|
| 1 · teste do ACHADO-16 | **feito** — `c7b8834` |
| 2 · teste do ACHADO-03 | **feito** — `b194f0a` |
| 3 · citação da costura 4 | **feito** — `b194f0a` (e a da costura 2, achada no caminho) |
| 4 · aceites do 18/19/20 | **feito** — `b194f0a` |
| 5 · ACHADO-13 delta-aware | **feito** — `8c5aca9` |
| 6 · ACHADO-21 + recebíveis do aditivo | **feito** — `c2c819d` |
| 7 · ACHADO-12, soma contrato+aditivos | **feito** — `50ec18f` |
| 8 · ACHADO-16, vereditos da Conciliação Final | **feito** — `28be877` |
| 9 · ACHADO-18, guarda de `valor_total` | **feito** — `bb32a14` |
| 10 · ACHADO-02 + 03, tabela por ramo | **feito** — `dbeee03` |
| 11 · ACHADO-23, trava na AF1 | **feito** — `e3a6756` |
| **marco** · implantar nos 3 servidores | **feito** — 31/08, todos em `f47f22de46a7`, `confirmar.sh` 15 OK / 0 FALHA |
| **F2-0** · remedir o ciclo das DREs | **feito** — 31/08, `docs/db/RELATORIO_DRE_CICLO_POS_FASE1.md`; ACHADO-15 **aposentado** (divergência de meio de ciclo é o modelo — decisão de 07/08 — não defeito; reconcilia no fechamento) |
| **F2-1** · ACHADO-24, aditivo sem recebível | **feito** — 31/08, `test_aceite_achado24.py`; medidos os DOIS chamadores (aditivo E contrato, os dois expostos); guarda em main.py nos dois; fixture do ciclo corrigido, resíduo de R$5.000 em 1.1.02 desapareceu |
| **F2-2** · auditoria contrato de API × tela | **feito** — 31/08, mapa completo em `docs/db/ACHADOS_CONTABEIS.md`; achou o **ACHADO-26** (Conciliação Final pior que o 25 — trava OU contorna o veredito em silêncio); contrato e NF-e confirmados OK na tela |
| **F2-3** · fila de provisões + ACHADO-26 | **feito** — 31/08, `test_aceite_fila_provisoes.py` (7 aceites); fila (`GET`/`POST /api/financeiro/fila-provisoes[/veredito]`) + tela própria (Financeiro → Fila de Provisões) entraram ANTES do desvio fechar; `resolver-saldo-provisao` só aceita Impostos/Custo Financeiro agora; mensagem da Conciliação Final aponta pra fila; ACHADO-26 **RESOLVIDO** |
| **F2-4** · ACHADO-25, tela do aditivo não envia forma de pagamento | enfileirado — bloco de frontend, depois do F2-3 |
| 12 em diante | não iniciados |

**Fase 0 fechada.** Prova de que ela não mudou comportamento nenhum:
`git log 2764c31..HEAD -- main.py mod_contabil.py` volta **vazio**.
(A partir do passo 5 isso deixa de valer por desenho — é o primeiro
conserto.)

**O contador de progresso:**

```
grep -rn "ACHADO-" tests/*.py | grep -i xfail | wc -l
```

Hoje **6** linhas (era 7) — só 4 são `@pytest.mark.xfail` de verdade citando
achado: 2 do ACHADO-19 e 1 do ACHADO-20 (Fase 5), 1 do ACHADO-01 (Fase 2,
ramo financeira sem conferência — deliberado, ver passo 10). O do ACHADO-15
saiu em 31/08 (aposentado — divergência de meio de ciclo é o modelo, não
defeito) e o do ACHADO-24 saiu no mesmo dia (F2-1, conserto aplicado). As
outras 2 linhas são comentário, não marcador. Linhas, não testes — serve
como tendência, não como precisão. No fim da Fase 4 tem que ser zero. No
início do roteiro eram 31.

**O contador tem um ponto cego, demonstrado no fechamento da Fase 1.** Ele
só enxerga achado que tem teste. O ACHADO-23 nasceu de uma medição, nunca
ganhou xfail, e por isso a suíte deu a Fase 1 por fechada com ele ainda
aberto — resolvido no passo 11, com teste (`tests/test_aceite_achado23.py`)
e linha própria em `ACEITE.md`, que também não o tinha até então.

Por isso o aceite de cada fase tem **duas** travas, não uma:
- `pytest -q` sem xfail citando achado da fase;
- `docs/db/ACEITE.md` sem nenhuma linha da fase em "SEM PROVA".

**Fase 1 fechada de verdade (31/08/2026)** — as duas travas conferidas: nenhum
xfail citando achado da Fase 1, e nenhuma linha da Fase 1 em "SEM PROVA" em
`ACEITE.md`.

## A suíte prova o servidor, não o sistema

Descoberto em 31/08, pelo ACHADO-25: o passo 6-c passou a exigir um campo
novo num endpoint, o frontend nunca foi atualizado, e **os 2466 testes
continuaram verdes** — porque todos chamam a API direto, mandando o campo
novo. Em produção, nenhum aditivo consegue ser assinado desde então.

**A regra irmã, do ACHADO-26:** antes de guardar uma operação, **enumere os
irmãos** — todo endpoint capaz de produzir a mesma mudança de estado. Quatro
achados desta auditoria são a mesma omissão (19, 03, 24, 26): guardamos uma
porta e havia outra.

**Toda mudança de campo obrigatório é invisível para a suíte.** A regra, até
existir trava melhor: passo que muda contrato de endpoint tem que dizer
**quem chama** e conferir o chamador real em `static/index.html`. Tarefa que
muda a API sem essa checagem está incompleta — e as que eu escrevi na Fase 1
estavam.

## Quando aparece achado novo no meio de um passo

Vai acontecer — o ACHADO-21 nasceu assim, no meio de uma medição. A regra:

1. O achado ganha número e entra em `ACHADOS_CONTABEIS.md` **na hora**.
2. Entra na fila deste roteiro, na posição que a gravidade dele pedir.
3. **Não é consertado dentro do passo em andamento** — a não ser que
   bloqueie o passo. Fora isso, o passo termina primeiro.

Inserir trabalho no meio de um passo é como um plano linear volta a ser
exploratório sem ninguém decidir isso.

## A regra de cada passo

**Teste primeiro, sempre.** O `xfail(strict=True)` que descreve o erro entra
antes do conserto. Quando o conserto entra, o teste passa, o `strict` quebra
a suíte no XPASS e obriga a remover o marcador. É o que impede consertar em
silêncio e o que impede declarar consertado sem prova.

---

## FASE 0 — a rede, antes de tocar em número
Nada aqui muda comportamento. É barato e é o que torna o resto verificável.

1. **Teste do ACHADO-16.** O mais grave da auditoria não tem prova nenhuma
   hoje. Projeto que fecha com provisão não efetivada → margem fictícia.
2. **Teste do ACHADO-03.** Hoje só existe menção em comentário.
3. **Corrigir a citação** do teste da costura 4: cita ACHADO-12, é ACHADO-21.
4. **Testes de aceite para 18 e 19.** Os de hoje são de medição — provam o
   presente, não viram verdes com o conserto.

## FASE 1 — o número da venda
Bloqueia usar o sistema para decidir. **Esta ordem não é negociável:** somar
antes de 13 transforma defeito raro em defeito de todo projeto com aditivo.

5. **ACHADO-13** — `faturar_segmento` delta-aware na conta de receita.
6. **ACHADO-21 + recebíveis do aditivo, juntos**, precedidos da extração de
   `valor_contratado_do_projeto` (contrato + aditivos assinados). Dependem um
   do outro: a forma de pagamento coletada na assinatura seria apagada pelo
   recálculo, e é a imutabilidade pós-assinatura que impede.
   `docs/db/TAREFA_ACHADO21.md`.
   *Ajustado em 30/08: o predicado explícito e a segmentação congelada saíram
   daqui para o passo 7 — são sobre a soma para faturar, não sobre
   imutabilidade.*
7. **ACHADO-12** — soma contrato + aditivos em `_valores_segmentados_do_projeto`,
   mais a seleção explícita do orçamento no `POST /aditivo` e a medição da
   segmentação congelada. `docs/db/TAREFA_ACHADO12.md`.
8. **ACHADO-16** — vereditos da Conciliação Final + relatório de reversões.
   `docs/db/TAREFA_ACHADO16.md`.
9. **ACHADO-18** — guarda `valor_total > 0` antes de contrato e NF-e.
   `docs/db/TAREFA_ACHADO18.md`.
10. **ACHADO-02 + ACHADO-03, juntos.** *Fundidos em 30/08:* os dois vivem em
    `_fin_provisoes_venda_seguro` e são a mesma decisão — o que o ramo faz com
    o `cust_fin`. O 02 é a consequência (receita financeira contada duas
    vezes), o 03 é o roteador ambíguo que a produz. Consertar um sem o outro
    é arrumar o efeito e deixar a causa escolhendo sozinha.
    `docs/db/TAREFA_ACHADO02_03.md`. **A tabela `_RAMO_CFIN_EVENTO` também
    está errada** — decidido em 30/08; ver a tabela por ramo no plano.
11. **ACHADO-23** — segmentação não congelada trava a AF1, que consegue
    congelar ali mesmo. Decidido em 30/08.

**Marco:** rodar a suíte. Nenhum xfail citando achado da Fase 1 pode sobrar.

## Implantação da Fase 1 — feita em 31/08/2026

**Três migrations, não duas.** `95c7e64afc6a` (rename 2.1.05 Total Flex →
Parcelamento Loja, ACHADO-14) nunca tinha entrado nesta lista — achada só na
hora de aplicar, ao rodar `alembic current` nos três ambientes ANTES de
mexer em qualquer coisa (mesmo instinto que salvou o ACHADO-23: conferir
antes de confiar na lista). Os três ambientes partiram de `46a93cfd591b`.

**A regra que sai disso:** a lista de migrations pendentes se monta do
`alembic current` **dos servidores**, nunca do histórico do repositório. A
versão anterior desta seção listava duas porque foi montada a partir do que
o roteiro tinha produzido. **Achado resolvido no repositório não é achado
implantado** — a `95c7e64afc6a` estava marcada RESOLVIDO desde 29/08 e
nunca saíra do localhost.

Upgrade **incremental** (`git pull` + `alembic upgrade head`, sem
DROP/recriar banco — decisão do Marcelo: `confirmar.sh` já reconstrói do
zero num banco descartável e compara, a garantia vem sem tocar na config
real). Medição antes de aplicar: `lancamento`/`contratos`/`orcamentos` ZERO
nos três — nenhuma decisão sobre dado de teste foi necessária.

**Integração → Homologação → Produção, nesta ordem, cada uma:** backup →
stop → pull → `alembic upgrade head` → `alembic current` (confirma
`f47f22de46a7`) → start → `confirmar.sh`. **15 OK / 0 FALHA nos três.**
Detalhes, armadilhas novas (banco `orizon_baseline_teste` inexistente nos
servidores; senha com `$`/`#` quebrando `.env`/URI) e o registro completo em
`docs/db/IMPLANTAR.md`.

**Lembrete que já custou um susto:** tabela nova precisa entrar no manifesto
de `modulos.py`. O passo 8 descobriu isso por acidente; o `periodo_fechado`
da Fase 3 vai passar pelo mesmo lugar. O passo 10 achou a variante disso:
**conta nova em `PLANO_PADRAO` também precisa de migration** (`seed_plano`
só cria o que falta num owner já existente) — `f47f22de46a7` faz isso pra
`4.4.05`, com o mesmo padrão de `46a93cfd591b` (owners dinâmicos) mais um
INSERT literal pros 3 owners fixos do `orizon_baseline_teste`
(`tests/test_gabarito_migration_x_seed.py` não tem dado de instância).

## FASE 2 — custo e fechamento

**Leia `docs/db/FASE2.md` antes de escrever a primeira tarefa desta fase.**
A Fase 1 mudou o escopo de três dos quatro itens, e o primeiro passo não é
conserto: é rodar de novo a medição de ciclo das DREs.

12. **ACHADO-01** — a perna de liquidação da provisão. *Encolhido no passo 10:*
    a função (`conferir_retencao_financeira`) já existe e está testada —
    `loja_antecipacao` fechou por completo (não constitui mais provisão).
    Falta só o gatilho (endpoint/fluxo) que chama a função quando o
    assistente financeiro confere o extrato da financeira/cartão.
13. **Fila de provisões em aberto** (dona: assistente administrativa).
14. **P5**, **ACHADO-06** (medir antes), **ACHADO-17** (decisão pendente).

## FASE 3 — integridade estrutural
Não toca número; pode andar em paralelo com a Fase 2.

15. `garantir_projeto()` extraído **antes** da FK.
16. `projeto_id` → FK, com os dois testes de integridade.
17. `periodo_fechado` + `lancar()` recusando mês fechado.
18. Vocabulário controlado de `origem`; tipo de registro; competência referida.

## FASE 4 — as visões
**Só depois da Fase 1.** Relatório em cima de número errado é o pior
resultado possível — errado e confiável.

19. Rename Diferida/Antecipada; remover `competencia_estimada`.
20. DRE Antecipada lendo o **constituído** por safra.
21. Exportação Excel; variância por safra; endividamento; decomposição.

## FASE 5 — higiene
22. Os três consertos de causa do ACHADO-19 (o de `/parametros` primeiro).
23. ACHADO-20, ACHADO-22, ACHADO-07, `_migrar_colunas_pg`, ciclos de FK,
    FKs sem índice, `Environment=` da produção, rotação do `sad2026`.

---

## O aceite final

Depois da Fase 4, a verificação completa é uma coisa só:

```
pytest -q
```

e **não sobrar nenhum xfail citando achado**. Um xfail que sobrou é conserto
que não fechou; um XPASS que quebrou a suíte é conserto que fechou com o
marcador velho. Nenhum dos dois passa despercebido — é para isso que o
`strict=True` existe.
