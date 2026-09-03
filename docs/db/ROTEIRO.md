# Roteiro — a ordem linear de executar tudo

Criado em 29/08/2026 a pedido do usuário: *"precisamos criar um formato
linear de implementar tudo."* Este arquivo é a **fila**. Um item por vez, de
cima para baixo.

## Os quatro documentos e o que cada um responde

| documento | responde |
|---|---|
| `ACHADOS_CONTABEIS.md` | **o que está errado** — a lista em correção |
| `LISTA_PARALELA.md` | **o que foi adiado** — a fila do ciclo seguinte |
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
| **F2-4** · ACHADO-25, tela do aditivo não envia forma de pagamento | **feito** — 31/08, `89923db`; modal `_abrirModalPagamentoAditivo` em `static/index.html`; prova por E2E de navegador (`test_e2e_browser_conciliacao_final.py`, banco próprio `orizon_e2e`, de volta ao `pytest -q` padrão) |
| **F2-5** · ACHADO-27, card de ambientes colapsa com plano de pagamento longo | **feito** — 31/08, `a2889df`; achado do Marcelo clicando em Homologação, correlacionado ao ciclo do beta (não regressão desta rodada); `flex-shrink:0` em `#neg-tbl-ambientes-card`; prova por E2E de navegador (`test_e2e_browser_negociacao_layout.py`) |
| **F2-6** · ACHADO-28, CPF de assinatura sem validação de dígito | **feito** — 31/08; achado do Marcelo clicando em Homologação; `validacao_doc.erro_doc` dentro dos três `_registrar_assinatura_*` (main.py), cobre interno + webhook ClickSign; `test_aceite_achado28.py` (6 aceites); conferir CPF contra o cadastro adiado — LP-02 em `docs/db/LISTA_PARALELA.md` |
| **F2-7** · ACHADO-32 + tela do veredito + fichário do Ciclo | **feito** — 01/09, `446216b`; quatro itens de `docs/db/TAREFA_CONCILIACAO_UI.md` (1-4; o item 5 é do `TAREFA_BLOCO_FISCAL.md`, frente separada): flag `exige_veredito` do backend, seletor de estado por linha (3 estados), selo+toast+realce, tooltips por efeito no livro, `#page-02.ciclo-on` escondendo a negociação por baixo do Ciclo; ACHADO-32 **RESOLVIDO**, provado por `test_aceite_conciliacao_ui_item1.py` + `test_e2e_browser_conciliacao_ui.py` + `test_e2e_browser_ciclo_overlay.py`; correção `c6fdf38` (01/09) — selo desacoplado da rota, exige movimento real, toast do razão + idempotência do Efetivar; item 6 (ACHADO-33, erro meu na redação do item 1), `c4518df` — Efetivar volta pra rubrica de veredito nomeado (só Resolver saía, não Efetivar), Montagem/Fábrica não têm outro alimentador; item 7 (ACHADO-33) medido e registrado como LP-11, sem implementar — decisão do Marcelo; item 8 (ACHADO-34) medido e generalizado, movido pra F2-8 (fila ativa) |
| **F2-8** · ACHADO-34, `conciliar_final` exige veredito pelo saldo, não pela decisão | **a fazer** — movido da LP-12 em 01/09: quem zera o saldo de uma provisão antes da Conciliação Final atravessa a exigência de veredito sem nunca passar por ela; `mod_folha` (comissão de venda, 2.1.04.12) é o caso real medido, não o único possível |
| **F2-9** · Parte B do `docs/db/TAREFA_PERCURSO_0109.md` (B1-B6, percurso de 01/09) | **feito** — 02/09, `cba0159` + `a9c75f4`; B1 (ACHADO-35) **RESOLVIDO**: recusa virou confirmação, total do dia vem do razão (`efetivado_no_dia`), `test_aceite_achado35.py` + `test_e2e_browser_conciliacao_ui.py`; B2 (ACHADO-36) **parcial** (só módulo financeiro/provisões, conforme o item): 36 `showToast(..., true)` viraram `avisoPopup`, 164 restam no resto do sistema (higiene), `test_aceite_achado36.py`; B3 (ACHADO-38) **RESOLVIDO**: estado antes da credencial nas duas pontas (11d já concluído — checagem nova — antes de `_aprovador_financeiro`; `peConciliacaoAprovar` reconfere `/pe/conciliacao` antes de `pedirCredenciaisGerente`), 24 irmãos enumerados sem o mesmo padrão, `test_aceite_achado38.py`; B4 (ACHADO-39) **RESOLVIDO**: medidas 4 linhas reais "Absorver R$0,00" em homologação antes de mexer (não apagadas); decisão passa a vir de Δ a cobrar, zero não é mais pendência, irmão achado (PATCH genérico de ciclo tinha a mesma conta ingênua) também corrigido via helper único, `test_aceite_achado39.py`; B5 (ACHADO-40) **parcial**: sub-colunas de largura fixa na coluna Decisão, prova por screenshot, `test_aceite_achado40.py`; link azul da Fila fica pra Parte A; B6 (sem achado numerado) **feito**: tooltip por veredito da Fila com o efeito no livro, `test_aceite_b6_fila_tooltips.py`; medição sem conserto — Montagem com sobra recusa "Efetivada" (mensagem exata em `test_medicao_montagem_teste1_fila.py`); Parte A (tela de Provisões unificada) **não entrou** — frente própria, decisão do Marcelo |
| **F2-10** · ACHADO-41, a Fila oferecia veredito que o sinal já exclui | **feito** — 02/09, `6aeddbb`; achado ao revisar a Parte B (4ª ocorrência do padrão "tela oferece ação que o servidor recusa" no mesmo dia — ACHADO-32/33/39); causa direta do "não resolveu na Fila" (Montagem do Teste 1); `vereditos_validos` por linha vem do backend (`mod_contabil.vereditos_validos_para_saldo`, mesma função que `resolver_veredito_provisao` chama pra recusar), tela desenha só esses; `test_aceite_achado41.py` + `test_aceite_b6_fila_tooltips.py`; ACHADO-42 **medido, sem conserto**: markup pode ser negativo (`comissao_arq_pct`/`fidelidade_pct` sem limite), Δ a cobrar inverte sinal contra Δ custo nesse caso — decisão de conserto em aberto, `test_medicao_achado42_markup_negativo.py` |
| **F2-11** · ACHADO-42, o mesmo portão do desconto pra comissão/fidelidade | **feito** — 02/09, `9324d40`; DECIDIDO do Marcelo, os 4 itens: comissão/fidelidade passam por `_usuario_autoriza_desconto` (trava no servidor); composto por AMBIENTE via `_maior_composto_com_parametros_pct` (motor de verdade, soma com `max()` ao cálculo de 12/08, nunca substitui — testado nas duas ordens, desconto-depois-comissão e comissão-depois-desconto); `Val_Liq<0` é recusa dura, sem credencial que a levante; `decisao_valida` realinhado a Δ a cobrar (2ª metade do ACHADO-42, fecha a divergência por construção); `test_aceite_achado42_portao.py` + `test_conciliacao_pe.py` atualizado; não corta tag — candidato em percurso |
| **F2-12** · `TAREFA_PERCURSO_0209.md` C1-C6 + ACHADO-43/44/45 | **feito** — 02/09, `594a3c6`; C1 (medição, sem conserto): 3 números por ambiente batiam entre si — a divergência de custo (Banheiro Social/Suite Master) era edição manual do próprio Marcelo em arquivos de teste, não comportamento do Promob (achado corrigido depois de errar a causa na 1ª versão, registrado como estava em ACHADOS_CONTABEIS.md); ACHADO-44 **RESOLVIDO**: `consistencia_interna` recusa NO UPLOAD (pool+PE) um XML que não fecha a conta consigo mesmo — medido antes de travar, `pool_ambientes` reais 0/12 falhavam, `arquivo_pe` 12/12 (arquivos de teste do Marcelo, intocados); ACHADO-45 **PARCIALMENTE RESOLVIDO**: `venda_maior_que_cfo` recusa NO UPLOAD de PE (venda ≤ CFO, sem gate equivalente antes) — medido antes de escolher o momento, 0 violações em toda base real (Homologação/Integração/Produção); achado ao implementar: o pool JÁ tinha trava (`qa_selo='bloqueado'`, mais branda — quarentena, não recusa) — hard-reject ali duplicaria essa porta, não decidido sem perguntar ao Marcelo primeiro; ACHADO-43 **RESOLVIDO**: porta dos fundos do parceiro já estava fechada pela fusão de defaults (ACHADO-42 do mesmo dia) — só faltava o auto-save não engolir a recusa em silêncio; C2 **CORRIGE o próprio B4/ACHADO-39**: Δ custo ≠ 0 sem Δ a cobrar é fato do resultado (empresa absorveu a margem), não "nada a decidir" — pendura a fase até um reconhecimento; C3 (regra "Duas portas", nova em ROTEIRO.md): AF1/Solicitação de Medição tinham duas portas (bloco do Contrato + sub-aba do fichário) — a sub-aba tinha a porta MORTA (upload simples sem teste, superado desde 2026-08-17); porta viva (documento+assinatura) migrou pra dentro da sub-aba, ad-hoc do Contrato removido; C4: reaprovar AF já concluída não pedia mais senha (correto, pós-B3) mas também não avisava nada — `_provAprovar` ganhou o mesmo padrão de estado-antes-de-credencial do B3; C6: `R$`/número quebrando em duas linhas nas caixas de KPI e nas células `.num` da comparação de PE, `white-space:nowrap` + ajuste de tamanho, prova por captura; C5/C7 foram pra LISTA_PARALELA.md (LP-01/LP-12), junto com a tela unificada de Provisões (LP-13) — nenhum dos três iniciado; não corta tag — candidato em percurso, Marcelo ainda percorre o v2026.09.02-beta1 |
| **F2-13** · ACHADO-45 (regra corrigida, pool) + ACHADO-46 + ACHADO-47 | **feito** — 03/09, `ed761b6`; ACHADO-45 **RESOLVIDO** (DECIDIDO corrige a 1ª redação — a regra é uma só, markup > 1 POR ITEM, não três condições misturando XML e contrato): `itens_com_markup_invalido` recusa no upload de pool — medido por item antes de travar, 0/795 itens reais violavam, incl. checado "item zerado sem o ambiente perder margem" (nenhum caso); quarentena `qa_selo` não substituída, convive; ACHADO-46 **RESOLVIDO**: `mod_escopo.funcao_compativel` ganhou papel-primeiro-nome-fallback (mesmo padrão de `funcao_operacional`); `mod_assistencias.FUNCOES_ELEGIVEIS` unificado por import (medido: catálogos idênticos nos 3 reais); aceite — função "Projetista" com papel `projeto_executivo` declarado aparece na transferência; ACHADO-47 **RESOLVIDO** (DECIDIDO: sem papel avulso, papéis vêm da função) — tela de Funções ganha os 3 checkboxes de papel + backfill seletivo das funções padrão correspondentes; bloco Adicional novo no Funcionário (fixo livre, comissão só se a função primária já for comissionada — guarda no servidor, migration `82275b998a4a`) somando no MESMO alimentador de comissão por papel (`mod_comissao.preparar_comissao_etapa`), sem rubrica/veredito novo; achado de arquitetura ao implementar: `funcao_e_comissionada` não podia morar em `mod_folha` (folha depende de cadastro, não o contrário) — pego por `test_arquitetura_modulos.py`, movido para `mod_cadastro.py`; 3 falhas PRÉ-EXISTENTES encontradas na suíte (`test_aceite_achado35.py` ×2, `test_e2e_browser_conciliacao_ui.py` ×1) — confirmadas via `git stash` que já falhavam no commit anterior a esta rodada, fora de escopo, não mexidas, reportadas ao Marcelo |
| **F2-14** · ACHADO-48, o livro é datado em UTC e a empresa vive em UTC−3 | **feito** — 03/09, `626df0a`; achado ao investigar as 3 falhas pré-existentes reportadas no F2-13 (o Marcelo recusou "cortar mesmo assim" e pediu rigor — nome dos testes, se tocam dinheiro, idade real contra o histórico de commits, isolamento); raiz maior que o sintoma: `lancar()` (porta única do razão) carimba com `datetime.utcnow()` quando `data` não é passada, 11 de 27 chamadores não passam; medido ANTES de mexer (`timedatectl` nos 3 servidores + contagem de lançamentos na janela 00h-03h UTC) — Integração/Homologação em `Etc/UTC`, Produção em `America/Sao_Paulo`, zero lançamento deslocado em base real, defeito estrutural sem vítima ainda; DECIDIDO do Marcelo: fuso é configuração (`Loja.config_financeira_json['fuso_horario']`, sem coluna nova), cadeia loja→rede→`America/Sao_Paulo`, nunca o relógio da máquina; `mod_contabil.agora_no_fuso`/`hoje_no_fuso`/`data_emissao_iso_no_fuso` (zoneinfo) viram fonte única — ~32 sites de regra de negócio migrados (carimbo de `lancar`, guarda do ACHADO-35, vencido/atraso, DRE mensal, cronograma, NF-e), ~40 timestamps de auditoria ficaram em `utcnow()` por não decidirem competência (lista completa em ACHADOS_CONTABEIS.md); `tests/test_achado48_fuso_horario.py` (5, incl. os 3 aceites do ACHADO-35 sob TZ=UTC e TZ=America/Sao_Paulo); controle negativo — revertido para `utcnow()`, o teste determinístico (fuso extremo UTC+14) falha; suíte completa 2565 passed/4 xfailed/0 failed |
| 15 em diante | não iniciados |

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

## O beta e a decisão de 01/09

O candidato `v2026.08.31-beta3` **não sobe para produção como está**. O
percurso manual do Marcelo em Homologação, que era o teste de aceite do
candidato, encontrou quatro defeitos na Conciliação Final e no fichário do
Ciclo — um deles (ACHADO-32) criado pelo próprio F2-3 de ontem: a guarda
entrou no servidor e a tela continuou oferecendo a porta fechada.

**A decisão foi consertar os quatro antes de subir**, e não aceitá-los como
defeitos conhecidos. A razão vale como regra: *o percurso manual serve para
achar o que a suíte não vê — descartar o que ele achou é desperdiçar o único
teste que custou tempo de gente.*

Consequência aceita: mais um ciclo bancada → Integração → Homologação, e a
primeira subida à produção fica para o candidato seguinte
(`v2026.09.01-beta4` ou o que a Vera nomear na hora — a tag sai da data real
da construção, não desta linha).

**O percurso manual se repete inteiro no candidato novo.** Não é retestar só
a Conciliação Final: as quatro correções tocam o fichário do Ciclo, que é o
contêiner de todas as etapas.

## Duas portas para o mesmo destino — a regra de 02/09

Decisão do Marcelo, depois de achar "Aprovação Financeira" e "Solicitação de
Medição" repetidos dentro do contrato e ao lado da Visão Geral (e um dos
dois nem funcionando):

> **Toda vez que houver mais uma porta para o mesmo destino, perguntar
> antes de abrir.** As três respostas possíveis são: abrir a porta nova,
> mudar a porta antiga (com uma sugestão de mudança escrita), ou manter a
> antiga sem tocar nela.

**Por que isto vira regra e não recado.** É a mesma família que produziu, em
dois dias, o ACHADO-26, o 32, o 33 e o 41 — a mesma ação existindo em mais
de um lugar, com as regras divergindo sozinhas depois. Aqueles quatro foram
encontrados *depois* de construídos. Esta regra move a pergunta para
**antes**, que é onde ela custa um minuto em vez de um ciclo.

A pergunta é obrigatória mesmo quando a porta nova parece obviamente melhor:
a resposta "mude a antiga" só aparece se alguém perguntar, e é ela que evita
o botão órfão que ninguém mantém — como o "Solicitação de Medição" que já
está lá e não funciona.

**Vale para portas de qualquer tipo:** botão, link, atalho de menu,
endpoint. Se leva ao mesmo lugar por outro caminho, pergunte.

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

## Duas filas, uma ativa

`ACHADOS_CONTABEIS.md` é o que se corrige agora; `LISTA_PARALELA.md` é o que
foi adiado para o ciclo seguinte. Ao fim de cada etapa de estabilização a
paralela é revisada, **vira a lista ativa**, e o que for adiado dela começa
a nova paralela.

**Adiar não é rejeitar.** Item decidido contra fica fechado onde nasceu, com
o motivo — não vai para a paralela. E achado **correlacionado** ao que está
sendo consertado entra na fila ativa, não na paralela: tratar junto custa
menos, foi o que aconteceu com os ACHADOS 24, 26 e 27.

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
