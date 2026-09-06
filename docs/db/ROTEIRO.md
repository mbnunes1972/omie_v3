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
| `MODELO_CONTABIL.md` | **como o dinheiro vira resultado** — o fato, o reconhecimento e as duas visões (05/09) |
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
| **F2-8** · ACHADO-34, `conciliar_final` exige veredito pelo saldo, não pela decisão | **feito** — 03/09, `83da2fb`; retomado depois do beta3 (ficou pendurado quando o percurso de 01/09 empurrou o F2-9 pra frente); DECIDIDO do Marcelo: a folha GRAVA um `VeredictoProvisao` em vez de ser reconhecida por escrito como veredito — a alternativa deixaria o `relatorio_projetos_encerrados_por_reversao` cego a esses projetos pra sempre, e ele é o contra-controle do ACHADO-16; `mod_contabil.resolver_por_ato_nomeado` é a porta única pra ato nomeado FORA da Conciliação Final (genérica: a folha é o caso real medido, não o único possível — o próximo mecanismo tem porta certa em vez de `resolver_saldo_provisao` direto), veredito derivado do SINAL por `vereditos_validos_para_saldo` (mesma função que recusa, ACHADO-41 — nunca uma segunda cópia dos limites); sem migration (`motivo`/`ref`/`decidido_por_id` já existiam em `VeredictoProvisao`); **o livro não muda** — nos dois sinais o caminho termina no mesmo `resolver_saldo_provisao` de antes, o que entra é o rastro, só o `ref` do lançamento ganha sufixo (conferido que nada dependia da string); `mod_folha.pagar` ganhou `decidido_por_id` e `main.py` passa `usuario.get("id")` (único chamador real, enumerado antes de mudar a assinatura); `tests/test_achado34_veredito_da_folha.py` (5 aceites), suíte 2570 passed / 4 xfailed / 0 failed |
| **F2-9** · Parte B do `docs/db/TAREFA_PERCURSO_0109.md` (B1-B6, percurso de 01/09) | **feito** — 02/09, `cba0159` + `a9c75f4`; B1 (ACHADO-35) **RESOLVIDO**: recusa virou confirmação, total do dia vem do razão (`efetivado_no_dia`), `test_aceite_achado35.py` + `test_e2e_browser_conciliacao_ui.py`; B2 (ACHADO-36) **parcial** (só módulo financeiro/provisões, conforme o item): 36 `showToast(..., true)` viraram `avisoPopup`, 164 restam no resto do sistema (higiene), `test_aceite_achado36.py`; B3 (ACHADO-38) **RESOLVIDO**: estado antes da credencial nas duas pontas (11d já concluído — checagem nova — antes de `_aprovador_financeiro`; `peConciliacaoAprovar` reconfere `/pe/conciliacao` antes de `pedirCredenciaisGerente`), 24 irmãos enumerados sem o mesmo padrão, `test_aceite_achado38.py`; B4 (ACHADO-39) **RESOLVIDO**: medidas 4 linhas reais "Absorver R$0,00" em homologação antes de mexer (não apagadas); decisão passa a vir de Δ a cobrar, zero não é mais pendência, irmão achado (PATCH genérico de ciclo tinha a mesma conta ingênua) também corrigido via helper único, `test_aceite_achado39.py`; B5 (ACHADO-40) **parcial**: sub-colunas de largura fixa na coluna Decisão, prova por screenshot, `test_aceite_achado40.py`; link azul da Fila fica pra Parte A; B6 (sem achado numerado) **feito**: tooltip por veredito da Fila com o efeito no livro, `test_aceite_b6_fila_tooltips.py`; medição sem conserto — Montagem com sobra recusa "Efetivada" (mensagem exata em `test_medicao_montagem_teste1_fila.py`); Parte A (tela de Provisões unificada) **não entrou** — frente própria, decisão do Marcelo |
| **F2-10** · ACHADO-41, a Fila oferecia veredito que o sinal já exclui | **feito** — 02/09, `6aeddbb`; achado ao revisar a Parte B (4ª ocorrência do padrão "tela oferece ação que o servidor recusa" no mesmo dia — ACHADO-32/33/39); causa direta do "não resolveu na Fila" (Montagem do Teste 1); `vereditos_validos` por linha vem do backend (`mod_contabil.vereditos_validos_para_saldo`, mesma função que `resolver_veredito_provisao` chama pra recusar), tela desenha só esses; `test_aceite_achado41.py` + `test_aceite_b6_fila_tooltips.py`; ACHADO-42 **medido, sem conserto**: markup pode ser negativo (`comissao_arq_pct`/`fidelidade_pct` sem limite), Δ a cobrar inverte sinal contra Δ custo nesse caso — decisão de conserto em aberto, `test_medicao_achado42_markup_negativo.py` |
| **F2-11** · ACHADO-42, o mesmo portão do desconto pra comissão/fidelidade | **feito** — 02/09, `9324d40`; DECIDIDO do Marcelo, os 4 itens: comissão/fidelidade passam por `_usuario_autoriza_desconto` (trava no servidor); composto por AMBIENTE via `_maior_composto_com_parametros_pct` (motor de verdade, soma com `max()` ao cálculo de 12/08, nunca substitui — testado nas duas ordens, desconto-depois-comissão e comissão-depois-desconto); `Val_Liq<0` é recusa dura, sem credencial que a levante; `decisao_valida` realinhado a Δ a cobrar (2ª metade do ACHADO-42, fecha a divergência por construção); `test_aceite_achado42_portao.py` + `test_conciliacao_pe.py` atualizado; não corta tag — candidato em percurso |
| **F2-12** · `TAREFA_PERCURSO_0209.md` C1-C6 + ACHADO-43/44/45 | **feito** — 02/09, `594a3c6`; C1 (medição, sem conserto): 3 números por ambiente batiam entre si — a divergência de custo (Banheiro Social/Suite Master) era edição manual do próprio Marcelo em arquivos de teste, não comportamento do Promob (achado corrigido depois de errar a causa na 1ª versão, registrado como estava em ACHADOS_CONTABEIS.md); ACHADO-44 **RESOLVIDO**: `consistencia_interna` recusa NO UPLOAD (pool+PE) um XML que não fecha a conta consigo mesmo — medido antes de travar, `pool_ambientes` reais 0/12 falhavam, `arquivo_pe` 12/12 (arquivos de teste do Marcelo, intocados); ACHADO-45 **PARCIALMENTE RESOLVIDO**: `venda_maior_que_cfo` recusa NO UPLOAD de PE (venda ≤ CFO, sem gate equivalente antes) — medido antes de escolher o momento, 0 violações em toda base real (Homologação/Integração/Produção); achado ao implementar: o pool JÁ tinha trava (`qa_selo='bloqueado'`, mais branda — quarentena, não recusa) — hard-reject ali duplicaria essa porta, não decidido sem perguntar ao Marcelo primeiro; ACHADO-43 **RESOLVIDO**: porta dos fundos do parceiro já estava fechada pela fusão de defaults (ACHADO-42 do mesmo dia) — só faltava o auto-save não engolir a recusa em silêncio; C2 **CORRIGE o próprio B4/ACHADO-39**: Δ custo ≠ 0 sem Δ a cobrar é fato do resultado (empresa absorveu a margem), não "nada a decidir" — pendura a fase até um reconhecimento; C3 (regra "Duas portas", nova em ROTEIRO.md): AF1/Solicitação de Medição tinham duas portas (bloco do Contrato + sub-aba do fichário) — a sub-aba tinha a porta MORTA (upload simples sem teste, superado desde 2026-08-17); porta viva (documento+assinatura) migrou pra dentro da sub-aba, ad-hoc do Contrato removido; C4: reaprovar AF já concluída não pedia mais senha (correto, pós-B3) mas também não avisava nada — `_provAprovar` ganhou o mesmo padrão de estado-antes-de-credencial do B3; C6: `R$`/número quebrando em duas linhas nas caixas de KPI e nas células `.num` da comparação de PE, `white-space:nowrap` + ajuste de tamanho, prova por captura; C5/C7 foram pra LISTA_PARALELA.md (LP-01/LP-12), junto com a tela unificada de Provisões (LP-13) — nenhum dos três iniciado; não corta tag — candidato em percurso, Marcelo ainda percorre o v2026.09.02-beta1 |
| **F2-13** · ACHADO-45 (regra corrigida, pool) + ACHADO-46 + ACHADO-47 | **feito** — 03/09, `ed761b6`; ACHADO-45 **RESOLVIDO** (DECIDIDO corrige a 1ª redação — a regra é uma só, markup > 1 POR ITEM, não três condições misturando XML e contrato): `itens_com_markup_invalido` recusa no upload de pool — medido por item antes de travar, 0/795 itens reais violavam, incl. checado "item zerado sem o ambiente perder margem" (nenhum caso); quarentena `qa_selo` não substituída, convive; ACHADO-46 **RESOLVIDO**: `mod_escopo.funcao_compativel` ganhou papel-primeiro-nome-fallback (mesmo padrão de `funcao_operacional`); `mod_assistencias.FUNCOES_ELEGIVEIS` unificado por import (medido: catálogos idênticos nos 3 reais); aceite — função "Projetista" com papel `projeto_executivo` declarado aparece na transferência; ACHADO-47 **RESOLVIDO** (DECIDIDO: sem papel avulso, papéis vêm da função) — tela de Funções ganha os 3 checkboxes de papel + backfill seletivo das funções padrão correspondentes; bloco Adicional novo no Funcionário (fixo livre, comissão só se a função primária já for comissionada — guarda no servidor, migration `82275b998a4a`) somando no MESMO alimentador de comissão por papel (`mod_comissao.preparar_comissao_etapa`), sem rubrica/veredito novo; achado de arquitetura ao implementar: `funcao_e_comissionada` não podia morar em `mod_folha` (folha depende de cadastro, não o contrário) — pego por `test_arquitetura_modulos.py`, movido para `mod_cadastro.py`; 3 falhas PRÉ-EXISTENTES encontradas na suíte (`test_aceite_achado35.py` ×2, `test_e2e_browser_conciliacao_ui.py` ×1) — confirmadas via `git stash` que já falhavam no commit anterior a esta rodada, fora de escopo, não mexidas, reportadas ao Marcelo |
| **F2-14** · ACHADO-48, o livro é datado em UTC e a empresa vive em UTC−3 | **feito** — 03/09, `626df0a`; achado ao investigar as 3 falhas pré-existentes reportadas no F2-13 (o Marcelo recusou "cortar mesmo assim" e pediu rigor — nome dos testes, se tocam dinheiro, idade real contra o histórico de commits, isolamento); raiz maior que o sintoma: `lancar()` (porta única do razão) carimba com `datetime.utcnow()` quando `data` não é passada, 11 de 27 chamadores não passam; medido ANTES de mexer (`timedatectl` nos 3 servidores + contagem de lançamentos na janela 00h-03h UTC) — Integração/Homologação em `Etc/UTC`, Produção em `America/Sao_Paulo`, zero lançamento deslocado em base real, defeito estrutural sem vítima ainda; DECIDIDO do Marcelo: fuso é configuração (`Loja.config_financeira_json['fuso_horario']`, sem coluna nova), cadeia loja→rede→`America/Sao_Paulo`, nunca o relógio da máquina; `mod_contabil.agora_no_fuso`/`hoje_no_fuso`/`data_emissao_iso_no_fuso` (zoneinfo) viram fonte única — ~32 sites de regra de negócio migrados (carimbo de `lancar`, guarda do ACHADO-35, vencido/atraso, DRE mensal, cronograma, NF-e), ~40 timestamps de auditoria ficaram em `utcnow()` por não decidirem competência (lista completa em ACHADOS_CONTABEIS.md); `tests/test_achado48_fuso_horario.py` (5, incl. os 3 aceites do ACHADO-35 sob TZ=UTC e TZ=America/Sao_Paulo); controle negativo — revertido para `utcnow()`, o teste determinístico (fuso extremo UTC+14) falha; suíte completa 2565 passed/4 xfailed/0 failed |
| **F2-15** · bloco fiscal item 1 — ACHADO-30, documento de fase sem remoção nem imutabilidade | **feito** — 03/09, `15a291d`; primeiro item do `docs/db/TAREFA_BLOCO_FISCAL.md`, que o próprio documento chamava de "o que está travando agora"; medido antes: NÃO existia rota de remoção nenhuma e o modelo promete append-only no docstring — não era consertar porta, era abrir a que nunca existiu, então a pergunta veio antes (regra das duas portas); DECIDIDO do Marcelo: remover é MARCAR (`removido_em`/`removido_por_id`), registro e arquivo preservados — append-only de pé, rastro da tentativa vivo (mesma razão do ACHADO-16), e `PROJETOS/` ainda sem cópia fora do host; migration `b0ecb9ce82d2` (id gerado); `main._docs_vivos` vira porta ÚNICA de leitura com os **8** leitores migrados, dos quais 3 são PORTÃO (conclusão das etapas operacionais, subfases do PE, escolha do XML na emissão) — portão que contasse removido tornaria a remoção cosmética, com falha silenciosa; trava anti-órfão varre `main.py`; rota POST (sem `do_DELETE` no servidor) com 409 em fase concluída e autoridade espelhando a do upload de cada etapa; tela nas subfases do PE, na 12 e na 15, menos no XML que já virou emissão; `tests/test_achado30_remocao_documento.py` (6 aceites, controle negativo embutido no aceite do portão), suíte 2576 passed / 4 xfailed / 0 failed |
| **F2-16** · bloco fiscal item 2 — ACHADO-31, XML da fábrica validado só na emissão | **feito** — 03/09, `bdb16f5`; `fiscal/mod_nfe.problemas_de_upload` no formato `(ok, problemas)` do ACHADO-44 e recusa 400 no `POST /ciclo/15/nfe-fabrica` ANTES de gravar documento; recusa XML mal formado, sem `<infNFe>`, sem item nenhum, e item sem NCM/CFOP/unidade ou quantidade não positiva (a regra do item 4 aplicada ao item: erro de schema da SEFAZ é falha nossa de validação); medido antes de travar nos 5 XML conhecidos — zero violações, nenhum arquivo real seria rejeitado; trava prospectiva, só na porta, a emissão segue parseando (defesa em profundidade); `tests/test_achado31_xml_no_upload.py` (9), rodados junto os 3 arquivos que sobem XML pela mesma porta; suíte 2585 passed / 4 xfailed / 0 failed. **ACHADO-31 fica PARCIAL**: o markup de ajuste decidido em 31/08 nunca foi implementado (medido: `rescalar_itens_para_total` ainda sobrescreve o digitado) e não era item de bloco nenhum — virou LP-15 |
| **F2-17** · bloco fiscal itens 3 e 4 — o erro do Focus sem detalhe; selo de prontidão do emitente | **feito** — 03/09, `6fcd6a4`; item 3 **RESOLVIDO**: `FocusError` guarda a lista da SEFAZ em `.erros`, mas as três rotas que emitem (`nfe/emitir-teste`, `ciclo/15/emitir-nfe`, `ciclo/15/emitir-nfse`) só capturavam `Exception` genérica — regra dos irmãos do ACHADO-26, três endereços do mesmo defeito; `except FocusError` antes do `except Exception` nas três, devolvendo `erros` no JSON; tela mostra item a item nas duas rotas com UI (`emitir-teste` é admin/backend, sem tela); `tests/test_bloco_fiscal_item3_erros_focus.py` (3, uma por rota), controle negativo confirmado; item 4 **MEDIDO, sem conserto** (instrução explícita — medir e parar): `prontidao_emitente` no ramo produto só confere `regime_tributario`+`uf`, endereço do emitente inteiro passa e o destinatário não é conferido em lugar nenhum; contados nos três ambientes reais quantos emitentes/clientes na etapa 15 ficariam incompletos pelos campos nullable listados — não deu zero (2 de 2 emitentes reais, Integração+Homologação, incompletos em pelo menos um grupo; 1 cliente na etapa 15, completo); decisão avisar-vs-barrar pendente do Marcelo, registrada em `docs/db/TAREFA_BLOCO_FISCAL.md`; item 5 não tocado, markup de ajuste (LP-15) não tocado, endereço do destinatário não trocado; suíte 2588 passed / 4 xfailed / 0 failed (`test_aceite_achado12` falhou uma vez isolado à ordem da suíte numa rodada anterior — reproduzido depois: passa sozinho e passa na suíte inteira, dívida de isolamento pré-existente) |
| **F2-18** · bloco fiscal item 4 — selo de prontidão do emitente/destinatário, implementação | **feito** — 03/09, `78e68c3`; DECIDIDO do Marcelo (medido no F2-17): BARRAR + AVISAR; `prontidao_emitente` (ramo produto) ganhou a lista nomeada de identificação + endereço no formato que o ramo serviço já usava (gate de regime intacto, CSOSN sempre exigível por causa dele); `prontidao_destinatario` nova, função IRMÃ (não mistura Cliente na assinatura do emitente); as três rotas de emissão recusam com a lista completa; `GET .../ciclo/15/nfe` ganha `selo_fiscal`, aviso antecipado na etapa 15 antes do botão de emitir; nota de UX nos dois botões de salvar do painel Fiscal; medido antes: regime de Homologação é "simples", CSOSN é o bloqueio ativo, não secundário; `tests/test_mod_fiscal.py` (+7) + `tests/test_bloco_fiscal_item4_selo_emitente.py` (6, novo), controle negativo confirmado (`git stash`); achado ao implementar: seed compartilhado + 5 cópias de `_perfil()` em arquivos de teste nasciam incompletas sob a regra nova, corrigidas; suíte 2599 passed / 2 failed / 4 xfailed — as 2 falhas são pré-existentes (confirmadas via `git worktree` no commit anterior, mesma falha idêntica), janela UTC×América/Sao_Paulo do próprio ACHADO-48 que dois testes não migraram, registrado como LP-17; LP-16 (isolamento do `test_aceite_achado12`, achado no F2-17) também registrado |
| **F2-19** · LP-17, os dois testes de indicadores/lançamentos que ainda comparavam `datetime.utcnow()` com competência do ACHADO-48 | **feito** — 04/09, `b7bb834`; candidato de madrugada, rescaldo do F2-14/F2-18: `test_lancamentos_api.py::test_get_lancamentos_fim_do_dia_inclui_lancamento_de_hoje` montava "hoje" com `datetime.utcnow()` para filtrar o range, mas `POST /api/financeiro/lancamentos` carimba via `agora_no_fuso` — corrigido para `mod_contabil.hoje_no_fuso`, mesma fonte do endpoint; `test_indicadores.py::test_endpoint_tenancy_e_venda_por_assinatura` tinha a mesma classe de mistura na `ContratoAssinatura` sem `assinado_em` explícito (caía no default `datetime.utcnow` da coluna) contra a série "vendas" que já bucketa por `hoje_no_fuso` — corrigido para carimbar `assinado_em=agora_no_fuso(...)` explícito; aceite sob `TZ=UTC`/`TZ=America/Sao_Paulo` forçados (mesmo padrão de `test_achado48_fuso_horario.py`); controle negativo — a janela real de discordância já tinha fechado no momento do conserto, reproduzida com o mesmo truque do ACHADO-48 (fuso extremo, `Pacific/Pago_Pago`, UTC−11, configurado na loja do teste), os dois falham de forma determinística revertidos; LP-17 marcada RESOLVIDA em `docs/db/LISTA_PARALELA.md`; LP-16 não tocada (outra classe de problema). Item 5 do bloco fiscal (as duas decisões pendentes) só MEDIDO em `docs/db/TAREFA_BLOCO_FISCAL.md` (`d8b8c29`) — nada implementado, não é passo do roteiro. Tag `v2026.09.04-beta1` cortada e implantada em Integração+Homologação (migration `b0ecb9ce82d2`, ACHADO-30 — serviços reiniciados nos dois), `confirmar.sh` 15/0, smoke OK, `pytest -q` 2601 passed/0 failed/4 xfailed sob os dois fusos forçados; Produção não tocada (madrugada, sem ninguém acompanhando) |
| **F2-20** · ACHADO-49 (Remover da etapa 12) + ACHADO-50 (pendente reportado como falha) + ACHADO-51 (NF-e da fábrica em duplicata) — a mesma família "a tela não conta o que o servidor fez" (ACHADOS 32/33/38/39/41) | **feito** — 04/09, `cef4587`+`7b6347c`+`f3006c6`+`b9a79ad`+`accc717`; os três achados do percurso do `v2026.09.04-beta1` em Homologação (04/09), tratados juntos por serem a mesma família. Medido antes de consertar: (1a) NF-e produto NÃO tem guarda de status como a NFS-e (`fiscal/nfe_emissao.emitir` só recusa se já "autorizado"), mas a Focus deduplica por `ref` — guarda externa, real, documentada no próprio client; não escala a achado de dinheiro, ordem original mantida; (1b) enumerados os 4 criadores de `CicloDocumento` contra `ETAPAS_OPERACIONAIS`/`SUBFASES_PE` — só a etapa 12 caía no `else` sem ser subfase do PE, nenhum irmão a mais pra corrigir agora (achado à parte, não corrigido: 11b/11c pedem `revisar_pe` pra subir e `executar_pe` pra remover, classe diferente); (1c) medição real em Homologação: 10 `nfe_fabrica_xml` vivos, 1 duplicata genuína (a que o Marcelo viu) e 2 casos de mesma chave em projetos diferentes — decisão sobre esse segundo caso deixada em aberto pro Marcelo. ACHADO-49: autoridade do Remover da etapa 12 passou a espelhar o upload (`_bloqueio_execucao_etapa`, não mais `executar_pe` herdado do `else` pensado pro PE) + `removerDocCiclo` avisa quando a credencial não vem (ACHADO-38 outra vez, 5ª ocorrência do padrão), aceite com E2E Playwright + controle negativo. ACHADO-50: nota `PROCESSANDO` além do timeout de 60s ganha mensagem dedicada ("fila da SEFAZ... use Consultar") em vez de "Falha na emissão"; timeout de 60s mantido de propósito (aumentar só empurra o problema — tratar bem o "ainda não saiu" não tem teto); nota de rigor registrada no achado: o sintoma litteral ("Falha na emissão: ...") não foi reproduzível com o código de hoje via `FakeEmissor` — pode ser versão anterior a algum conserto recente (F2-17) ou resubmissão com erro real da Focus; conserto fecha a classe de qualquer forma. ACHADO-51: nada impedia carregar a mesma NF-e da fábrica duas vezes — DECIDIDO bloquear (Marcelo, 04/09), dedup pela CHAVE do `<infNFe Id>` (nunca pelo nome do arquivo) contra `_docs_vivos` (respeita ACHADO-30 — documento removido não bloqueia reupload); escopo só dentro do mesmo projeto/etapa, mesma chave em projeto diferente fica em aberto. Achado ao rodar a suíte inteira: a trava do ACHADO-51 (corretamente) surfaceu uma dependência de ordem pré-existente em `test_aceite_achado18.py` (dois testes reusando o mesmo projeto/fixture sem reset) — corrigida com `_reset15`, mesmo padrão já usado alhures; suíte completa 2609 passed / 0 failed / 4 xfailed. À margem, não tocado (fora do escopo deste candidato): Produção está com `ciclo_documentos` sem a coluna `removido_em` (migration do ACHADO-30 não aplicada lá) e `git describe` mostra 88 commits à frente de uma tag limpa — reportar ao Marcelo, não corrigido aqui. Não autorizado/tocado: item 5 do bloco fiscal (F2-21, suspenso), markup de ajuste (LP-15), qualquer implementação da LP-18, Produção |
| **F2-21** · bloco fiscal item 5 — NF-e H e NF-e P | **SUSPENSO** — 04/09. O item pressupõe que a emissão é um evento do projeto, e o percurso do Marcelo redesenhou isso: entrada fiscal no recebimento, emissão POR FASE, com escolha entre NF-e de origem e "Estoque". Implementar antes de a frente nova ter decisão é construir sobre chão que se move — e explica o achado do Bloco B (a etapa 15 destravada de propósito: ela nunca foi evento único). Ver LP-18 e `docs/db/TAREFA_FASES_E_RECEBIMENTO.md`. Reabre quando a LP-18 for decidida |
| **F2-22** · diagnóstico de Produção registrado + ACHADO-52 (remoção do PE mais frouxa que o upload) + ACHADO-51 estendido (mesma chave entre projetos) + corte/deploy | **feito** — 04/09, `4626aa9`+`4c44b0c`+`d8d3e08`+`240103d`; quatro frentes. **Bloco A** (registro, sem código): o diagnóstico só-leitura de Produção (pedido à parte, mesmo dia) registrado em `IMPLANTAR.md` (`### Produção — diagnóstico de 04/09`) e apontado do `ESTEIRA.md` — saiu da esteira em 28/08 por `checkout main` manual, 3 dias antes de a regra existir, sem culpa; código/schema em paridade três semanas atrás (alarme de coluna faltando era falso); sem uso real (1 usuário, 0 sessões); sondagens de bot não acharam nada (nginx sem root/alias, `.env` 600, `/root` 700); achado que fica — app roda como root, corrigido só no rebuild. **Bloco B**: ACHADO-52 — subfases do PE têm duas portas (execução: `executar_pe`; revisão: `revisar_pe`, `tipo=pe_relatorio_complementar`), mas a remoção exigia só `executar_pe` — Operador podia remover um relatório de revisão que jamais poderia ter subido (ACHADO-49 na direção oposta: lá a remoção era mais dura, aqui mais frouxa); medido antes de codar — `pe_relatorio_complementar` é discriminador limpo, nenhuma coluna nova; remoção agora exige a capacidade da porta que produziu aquele documento; enunciado do ACHADO-30 corrigido (o espelho é da PORTA, não da etapa); `tests/test_achado52_remover_espelha_porta_de_revisao.py` (3), controle negativo confirmado. **Bloco C**: ACHADO-51 estendido — DECIDIDO (Marcelo): mesma NF-e não cobre dois projetos, bloqueio agora TAMBÉM entre projetos; exceção que muda o desenho — projeto CANCELADO libera a chave (`_projeto_cancelado`, já existente, mesma fonte de `_contrato_assinado` — nenhum estado novo); medido antes de codar (gate explícito no pedido — se não fosse consultável, pararia aqui); medição de hoje: 2 casos cruzados em Homologação, nenhum projeto cancelado entre eles, trava prospectiva, nada a desfazer; `tests/test_achado51_chave_entre_projetos.py` (3), dois controles negativos (escopo entre-projetos e exceção do cancelamento, separados). Também registrado em ACHADO-50: passo explícito pro próximo percurso — reproduzir em Homologação o sintoma litteral que a bancada não reproduziu (achado segue ABERTO até isso acontecer). Suíte completa: **2615 passed, 0 failed, 4 xfailed**. **Bloco D**: sem migration nova; tag `v2026.09.04-beta2` (`240103d`) — carrega junto o F2-20 (nunca tagueado antes) e este candidato; Integração e depois Homologação, `confirmar.sh` 15/0 e smoke OK nos dois, `git describe --tags` exato; Produção NÃO tocada — tratamento próprio, registrado no Bloco A. Não autorizado/tocado: item 5 do bloco fiscal (F2-21, suspenso), markup de ajuste (LP-15), qualquer implementação da LP-18, Produção (inclusive "só" o usuário de serviço — isso é do rebuild) |
| **F2-23** · ACHADO-54 (NF-e rejeitada, beco sem saída) + ACHADO-53 (autosave ao abrir parâmetros) + ACHADO-51 estendido (NF-e cancelada libera a chave; recusas se explicam sozinhas) + ACHADO-36 estendido (faixa do ciclo) + corte/deploy | **feito** — 05/09, `a8a69a4`+`33f2947`+`83c6d7a`+`3a0a8a0`+`a29b7c8`+`5ff46c8`; saído do percurso do Marcelo em Homologação (04/09), miolo mudou depois de print da tela (rejeição é da SEFAZ, não mensagem nossa). ACHADO-54, dois becos empilhados: (causa 1, numeração) `ref` da NF-e produto era constante por `fabrica_doc_id` — retentativa após rejeição pedia à SEFAZ o mesmo número (payload com data/hora nova → chave diferente pro mesmo número → "Duplicidade de NF-e com diferença na Chave de Acesso", exatamente o print); mesma regra da NFS-e aplicada (precedente já existia no arquivo): `ref` novo por tentativa, só autorizado/processando trava, erro/cancelado libera; `GET .../ciclo/15/nfe` corrigido pra refletir a ÚLTIMA tentativa (faltava `ORDER BY`, achado ao consertar); (causa 2, tela) `_renderCardEmissaoNfe` travava a linha (só Consultar/Cancelar) mesmo com emissão em erro — foi isso, não o 409 de etapa conclusiva, que o Marcelo viveu como "o remover não funcionou"; regra do Marcelo ("documento não processado não fica preso na tela") aplicada — só trava em autorizado/processando, erro/cancelado oferece nova tentativa e Remover. ACHADO-53: abrir parâmetros de projeto assinado disparava `POST /parametros` (403 correto, mas pedido sem propósito) — dois portões no ponto de consequência (`_mpPopulando`/`_mpModoLeitura` em `agendarSalvarParametros`), não em cada gatilho possível. ACHADO-51, terceira condição: NF-e cancelada também libera a chave da fábrica (decisão do Marcelo — "pode haver erro na emissão e a NF-e da fábrica será a mesma"), só `cancelado` libera, não `erro`; e as recusas "mesma etapa"/"selo do destinatário" reescritas pra dizer o que bloqueou, por quê, e a saída, mesmo padrão que "outro projeto" já usava. ACHADO-36 estendido: fiscal já limpo (rodadas anteriores); ciclo — 31 `showToast(..., true)` em 15 funções (abrir projeto, transferência de etapa, PE e Medição) convertidos pra `avisoPopup`; 133 seguem no resto do sistema. Achado ao rodar a suíte inteira: 6 testes pré-existentes quebrados por dependerem do `ref` antigo (constante) ou do texto antigo da mensagem de destinatário — corrigidos pra ler os valores reais da resposta em vez de reconstruir; um deles só falhava na suíte inteira (estado de etapa vazando de um teste que abortava cedo pelo mesmo motivo). Suíte completa: **2630 passed, 0 failed, 4 xfailed**. Sem migration nova; tag `v2026.09.05-beta1` (`5ff46c8`), Integração e depois Homologação, `confirmar.sh` 15/0 e smoke OK nos dois, `git describe --tags` exato; Produção NÃO tocada — tratamento próprio (Bloco A do F2-22). Não autorizado/tocado: item 5 do bloco fiscal (F2-21, suspenso), markup de ajuste (LP-15), qualquer implementação da LP-18, Produção. Alvo do próximo percurso: reproduzir em Homologação a sequência do Passo 1 de ponta a ponta — emitir, ser rejeitado, e conseguir sair de lá |
| **F2-24** · ACHADO-55 (decisão do PE, dinheiro) + ACHADO-58 (Remover quebrado de verdade — SyntaxError) + ACHADO-57 (Montagem não se conclui sozinha) + registro (ACHADO-56/LP-19/LP-18/LP-13) + corte/deploy | **feito** — 05/09, `156f978`+`9a395f1`+`5bf80df`+`2d762b2`; saído do percurso do Marcelo em Homologação, CONFIRMADO na tag NOVA (`v2026.09.05-beta1`). **Passo 0** (registro, sem código): ACHADO-56 — Revisão de PE fecha verde antes do veredito de absorver/cobrar, família do ACHADO-39 (C2), só registrado; LP-19 — valor estourando coluna na tabela de decisão, família do C6; LP-18 ganha confirmação do Marcelo — carga de NF-e da fábrica na subfase de recebimento (item 2 da TAREFA já existente); LP-13 recebe o desenho FECHADO (Fila no módulo Financeiro, filtrável por projeto/conta; a tela do ciclo permanece, mas os DOIS apontam pro mesmo endpoint/consulta/box de veredito — um componente, dois pontos de montagem, pra não repetir os ACHADOS 32/33/39/41; veredito vira botão "Resolver" que abre o box na própria linha; opções vêm do servidor; "Vai Chegar" é ADIAMENTO, não veredito) — nada disso implementado. **Passo 1 — ACHADO-55** (a única frente de dinheiro): a decisão do PE (manter/absorver/cobrar/estornar) corrigia o registro (`ConciliacaoPeFase`) a cada redecisão, mas o crédito ao cliente (`registrar_credito_cliente`, ref fixo) só sabia CRIAR, nunca reverter — sair de "estornar" deixava o crédito órfão no razão, mesma família do ACHADO-16/34 (veredito × livro discordando). Medido antes de codar: (a) decidir "estornar" duas vezes NÃO duplica (ref fixo + idempotência de `registrar_evento` já resolvia sozinho — não escalou a segundo achado de dinheiro); (b) "cliente assinou a aprovação do PE" é consultável (`CicloEtapa` etapa "11e", `STATUS_CONCLUSIVOS`); (c) medição real: 1 caso hoje em Homologação (`Teste_4`/pool 16, sequência manter→estornar→manter→manter, R$ 64.043,46 órfão — mesmo projeto e mesmo valor do LP-19). Conserto por LANÇAMENTO, nunca apagamento (ACHADO-16/30/34): `registrar_credito_cliente_pe`/`reverter_credito_cliente_pe` (mod_contabil.py, mesmo desenho do `estornar_rateio` — crédito numerado por tentativa, reversão com rastro); janela nova — redecidir depois da 11e concluída é recusado (409), primeira decisão continua livre. **Passo 2 — ACHADO-58**: os dois botões Remover (etapa 12, ACHADO-49; NF-e da fábrica, ACHADO-54) continuavam sem funcionar apesar de teste verde — os testes E2E antigos chamavam a função JS direto ou conferiam a STRING de HTML de um render isolado, nunca clicavam no botão real (confirmado: nenhum dos dois está na família `test_e2e_browser_*`). Construído `tests/test_e2e_browser_remover_ciclo.py` — projeto/contrato pela tela, documento semeado direto no banco, botão Remover real localizado e CLICADO — e achado o bug de verdade: `Unexpected end of input`, um `SyntaxError` real, sempre, em qualquer clique — `JSON.stringify(nome_original)` interpolado sem escape dentro de um `onclick="..."` também delimitado por aspas duplas, quebrando o atributo na primeira aspa do JSON. Corrigido com `esc(JSON.stringify(...))` nos QUATRO lugares com o padrão (regra dos irmãos) — não só os dois relatados: também a Remover das subfases do PE (11a-e) e o botão "Briefing" da tela de Clientes, nenhum dos dois relatado mas igualmente quebrado. Registrado como classe: aceite que chama a função direto ou confere string de HTML nunca prova que o caminho completo (atributo → parser → clique → handler) chega inteiro. **Passo 3 — ACHADO-57**: a etapa Montagem (código "17", visual "10") se dava por concluída sozinha logo após assinar o contrato — `_statusFichario` aplicava a leniência "toggleável sem linha nenhuma = satisfeita" (certa pra subfase opcional "17a" não travar o grupo) também ao CÓDIGO-MÃE; um projeto novo, sem nenhuma linha de Montagem ainda, "satisfazia" as duas por omissão. Medido ao vivo em Homologação, só leitura: `Projeto_3`/`Teste_2` têm hoje a condição exata (status "pendente", zero linha de "17a"). Conserto: a leniência fica só pros filhos do grupo; a mãe sempre exige status conclusivo de verdade; "17" é o único código que combina cabeça-de-grupo + toggleável, sem irmãos afetados. Suíte completa: **2639 passed, 0 failed, 4 xfailed**. Sem migration nova; tag `v2026.09.05-beta2` (`2d762b2`), Integração e depois Homologação, `confirmar.sh` 15/0 e smoke OK nos dois, `git describe --tags` exato; Produção NÃO tocada — tratamento próprio (Bloco A do F2-22). Não autorizado/tocado: item 5 do bloco fiscal (F2-21, suspenso), markup de ajuste (LP-15), implementação da LP-18 ou da LP-13, Produção |
| **F2-25** · ACHADO-59 (Outros Fornecedores da AF1 não gravava + Custo de Fábrica vira rubrica) + Fila mostra todas as provisões, agrupadas + Lista de Provisões (visual C6/LP-19 + botão Resolver) | **feito** — 05/09, `2efff6e`; saído do Teste 5 do Marcelo em Homologação, CONFIRMADO na tag NOVA (`v2026.09.05-beta3`). **Passo 0** (medição, sem código): confirmados os dois números do Marcelo — 21 contas 2.1.04.% no plano, 19 painel-eligible (painel exclui 2 sem mecanismo), 17 fila-eligible (fila exclui mais 2, rota própria/ACHADO-01) — "16 de 19" e o defeito real é nenhuma tela rotular o que conta (virou o Passo 3/4); a cadeia do `out_forn` medida até achar a exclusão desatualizada em `_AF_ITEM_RUBRICA`. **Passo 1 — ACHADO-59a**: `out_forn` digitado na AF1 era aceito e persistido em `itens_json`, mas `disparar_deltas_af` nunca gerava o lançamento — `_AF_ITEM_RUBRICA` excluía a chave com um comentário que não valia mais. Conserto: `fechamento_venda_outros_forn` em EVENTOS + `_PROV_FECHAMENTO`/`_AF_ITEM_RUBRICA`; convive com a Conferência (Passo 2) por refs em namespaces diferentes. **Passo 2 — ACHADO-59b, DECIDIDO**: Custo de Fábrica vira linha editável na AF1/AF2, reusando a Conferência contábil da etapa 12 (`conferencia_pedido`) sem mecanismo novo — "reduz CFO, migra o resíduo pra Outros Fornecedores". Gate explícito (dobra o custo?) medido e confirmado NEGATIVO por teste dedicado antes de mexer (`_RUBRICA_CUST_FAB` fora de `_RUBRICAS`, mesmo padrão do `_RUBRICAS_CUST_AD`). Achado no meio do caminho: `conferencia_pedido` soma os dois lançamentos — passar o valor novo E o resíduo ao mesmo tempo debitava o CFO duas vezes (4000→3000 dava 2000); corrigido passando `max(novo, atual)` pro primeiro lançamento (fica no-op numa redução cujo resíduo migra inteiro). Não era duplicação do motor contábil, era composição errada da chamada nova — a etapa 12 e `conferencia_pedido` em si não mudaram (regressão de `test_conferencia.py`/`test_contabil_ajustes_excepcionais.py`, 19 testes, confirmando). **Passo 3 — DECIDIDO**: a Fila de Provisões lista as 17 elegíveis SEMPRE (não só as em aberto), agrupadas EM ABERTO/FECHADAS-ZERADAS, migrando de grupo sozinha; contagem rotulada por grupo (`contagens` na resposta). Uma rubrica resolvida não some mais — antes ficava indistinguível de uma nunca tocada. **Passo 4**: `_reconProvTabelaHtml` (Lista de Provisões) — `white-space:nowrap` nas colunas numéricas (família do C6/LP-19); o link que navegava pra Fila virou botão "Resolver" que abre o box na própria linha, opções vindas do servidor (`vereditos_validos_para_saldo`) — antecipa só esta parte da LP-13 (desenho fechado em 05/09), resto fora. Relabeling Absorver/Receber/Encerrar/Adiar (pedido original) ficou PARADO — registrado como **LP-20**: "Receber" revelou precisar de lançamento de receita de verdade no momento fiscal (emissão da NF-e), e o próprio Marcelo levantou um problema em aberto (provisões ainda não fechadas na emissão) — decisão volta pra ele antes de qualquer rótulo novo. Suíte completa: **2650 passed, 4 xfailed, 0 failed**. Sem migration nova; tag `v2026.09.05-beta3` (`2efff6e`), Integração e depois Homologação, `confirmar.sh` 15/0 e smoke OK nos dois (401 login inválido, 200 `login.html`), `git describe --tags` exato; Produção NÃO tocada — tratamento próprio (Bloco A do F2-22). Não autorizado/tocado: item 5 do bloco fiscal (F2-21, suspenso), markup de ajuste (LP-15), LP-18, o restante da LP-13, a Conferência contábil da etapa 12 (só reusada), Produção |
| **F2-26** · MODELO_CONTABIL.md — 3 medições + fecha a pendência 3 (vereditos) + trava anti-NF-e | **feito** — 05/09, `0414838`; rodada de MEDIÇÃO E DECISÃO, sem código de modelo contábil (o modelo em si segue `[ABERTO]` pra implementação — só o registro deste candidato muda). **Medição 1** (pendência 1, a mais importante): `faturar_segmento` (delta-aware, ACHADO-13) já split a o delta em duas pernas — "adiantado" (`D 2.1.06 × C 4.1.01/4.2.01`, consome o pool do contrato) e "a_receber" (`D 1.1.02 × C receita`, só pro excedente); medido em Homologação (3 projetos faturados) que a perna "a_receber" NUNCA disparou — o recebível não dobra, a pendência como formulada estava errada. Achado um problema DIFERENTE e real: `Teste_1`/`Teste_4`, status "fechado", têm 2.1.06 (Receita a Realizar) aberto (R$63k/R$69k) — só o segmento "mercadoria" foi faturado, nunca o "serviço"; nenhuma tela detecta isso hoje, mesma classe de risco do ACHADO-16 (contra-controle que ainda não existe). **Medição 2** (pendência 2): tabela completa das 21 rubricas de provisão sob o critério do CPC 47 (código, grupo hoje, entra no Cust_Var, timing no ciclo, leitura preliminar), preenchida até a penúltima coluna — decisão final linha a linha continua com o Marcelo. **Medição 3**: dos 28 arquivos de teste que tocam `efetivar_provisao`/`resolver_saldo_provisao`/`reconhecer_despesa_efetivacao`, só **7** travam especificamente a doutrina de 07/08 (sobra cancela contra o ativo sem tocar a DRE — verificado por conta 4.4.02/5.6.10/5.x, não só saldo de provisão) — são os que mudam de significado na rederivação, listados no MODELO_CONTABIL.md. **Registro** (pendência 3, fecha): o mapeamento dos vereditos (Absorver→Despesa de Conciliação na FALTA, Receber→Receita de Conciliação na SOBRA, Encerrar→sem tocar resultado, Adiar→mantém aberta) se derivou do modelo sem decisão nova; `LP-20` movida pra Fechados. **Conserto independente**: `tests/test_trava_nfe_real_no_repo.py` — varre `git ls-files` procurando XML com chave de NF-e (nome = 44 dígitos, ou `Id="NFe<44 dígitos>"` no conteúdo) fora de `nfe_amostras/`; allowlist nomeada e auditada pras 2 fixtures sintéticas de `tests/fixtures/nfe/` (chave placeholder, CNPJ óbvio) — heurística de "parece fake" foi descartada (chave toda zero passa no dígito verificador por coincidência), só allowlist explícita por arquivo. Negativo confirmado ao vivo: cópia de amostra real da fábrica stageada em `XML/Nfe/` (nome com chave E depois renomeada, testando as duas rotas de detecção) — pega nos dois casos; desfeito depois, nada ficou no working tree. Suíte completa: **2652 passed, 4 xfailed, 0 failed**. Sem migration; NÃO cortou tag (rodada de medição, não muda comportamento) — a trava nova entra no próximo corte. Não autorizado/tocado: separar as pernas de `efetivar_provisao`, criar as contas de Conciliação, mexer em `resolver_saldo_provisao`, qualquer implementação do modelo, Produção |
| **F2-27** · MODELO_CONTABIL.md — a mudança do modelo contábil: reconhecimento na emissão | **feito** — 05/09, `1a31fa6` (merge de `8a3a821`+`fa25710`+`b770e4b`); implementa o que o F2-26 já tinha decidido, sem decidir nada de novo. **Passo 1** (medição): reconhecimento hoje só em `reconhecer_despesa_efetivacao`, chamada de um único lugar (`efetivar_provisao`) — sem duplicação, PASSO 1 não travou. **Passo 2**: `efetivar_provisao` tinha 5 chamadores (`mod_folha.pagar`, `mod_assistencias.realizar_caso`, `test_*` diretos) — nenhum dependia da assinatura mudando. **Passo 3**: `reconhecer_despesa_efetivacao` passou a disparar só de `reconhecer_provisoes_segmento` (nova, chamada por `_fin_faturamento_segmentado_seguro` na emissão), pelo PROVISIONADO INTEGRAL das 17 rubricas de despesa em tempo real, segmentado Merc/Serv; `efetivar_provisao` ficou perna ÚNICA (provisão×caixa/fornecedores) — o ativo (1.1.06.xx) só se move por constituição/AF/reclass/reconhecimento, nunca por pagamento, o que torna o cálculo do reconhecido estável e independente da ordem de pagamento. **Passo 4**: Contas de Conciliação novas (`4.5.01`/`5.7.01`, migration `a1f2e3c4d5b6`), em bloco PRÓPRIO na DRE (depois do EBIT); vereditos renomeados/colapsados (Absorver/Receber/Encerrar/Adiar), `resolver_veredito_provisao` perdeu `valor_efetivado`/`forma_pagamento`. **Passo 5**: os 7 testes de doutrina do F2-26 rederivados + 1 arquivo novo (`test_f2_27_reconhecimento_na_emissao.py`, 6 testes). **Passo 6**: rótulos "NA NF-E" corrigidos, ACHADO-22 fechado.

**Interrupção e protocolo de verificação em camadas**: a suíte completa em segundo plano foi morta aos 35min sem resultado parcial — nada tinha sido commitado. Protegido primeiro (branch `f2-27-wip`, commit "NÃO VERIFICADO", sem push), depois verificado em camadas ascendentes em vez da suíte inteira de uma vez: (a) arquivos novos — verde; (b) os 8 arquivos de teste modificados — verde, 7 rederivados + 1 só ajuste de asserção; (c) subconjunto contábil (`-k "contabil or provis or dre or conciliacao"`) — **49 failed + 60 errors** na primeira passada, causa raiz: mocks E2E de F2-25 com strings de veredito antigas (`efetivada`/`encerrada_valor_menor`/`nao_se_aplica`/`ainda_vai_chegar`), cujo `_FILAPROV_BOTOES` renomeado fazia 0 botões renderizar — travamentos/timeouts em Playwright cascateando em erros de conexão em testes NÃO relacionados (confirmado via `git checkout main` rodando a MESMA suíte limpa, 296/0/0). Rederivados 9 arquivos de teste; 301 passed. Achado no meio do caminho, **ACHADO-60**: `margem_projetada`/`dre_simulada` liam o eixo do PASSIVO (saldo de provisão não pago) pra "pior caso" de resultado — correto enquanto reconhecimento e pagamento andavam juntos, virou duplo-conto quando o F2-27 os separou (o ativo mede o não-reconhecido, não o passivo); corrigido nas duas funções, com teste dedicado pra janela pós-emissão/pré-pagamento que não existia antes do F2-27. (d) suíte inteira sem E2E de navegador — **29 failed**, todas a mesma causa: testes que nunca simulavam a emissão (só `efetivar_provisao`, esperando reconhecimento imediato) — rederivados (`test_bateria_ciclo.py`, 21 cenários num único ponto do helper compartilhado; `test_ciclo_completo_por_ramo.py`; `test_assistencias.py`; `test_comissao.py`, o excedente pago agora vira Despesa de Conciliação; `test_nfe_etapa15_e2e.py`); 2655 passed, 4 xfailed. (e) os 5 E2E de navegador, um por vez, com timeout explícito — nenhum travou; `test_e2e_browser_conciliacao_final.py` precisou de rederivação (o fluxo nunca emite NF-e de propósito, então a despesa nunca é reconhecida — o veredito 'Receber' reverte a provisão inteira pra Receita de Conciliação, não mais pra 5.1.01). Suíte completa (com E2E): **2661 passed, 4 xfailed, 0 failed**, 467s, sem travar.

**Não fez** (fora do escopo do candidato, por instrução explícita): DRE Diferida/visão por safra, remoção de `2.1.04.01`/construção de Devolução, painel fiscal/papel_cnpj/percentuais, `4.3.01`/`4.4.05` (já corretos), Produção (intocada — tratamento próprio, Bloco A do F2-22). Tag `v2026.09.05-beta4` (`1a31fa6`), Integração e depois Homologação, `confirmar.sh` 15/0 e smoke OK nos dois, `git describe --tags` exato. |
| **F2-28** · percurso do Marcelo no beta4 (Teste_6) — "Atual" lê o razão, Custo de Fábrica read-only com contrapartida automática, uma linha só na lista, AF revisável até "Concluir Contrato" | **feito, Passo 1a PARCIAL — corrigido no F2-29 Fatia A** (06/09: o conserto só cobriu `custo_fabrica`/`out_forn`, as duas rubricas que o percurso exercitou; as outras 17 de `itens_provisao` continuavam lendo `_negociacao_breakdown`, nunca o razão — ver F2-29 abaixo) — 05/09, `8ed182e`; primeiro percurso conferindo o razão com o modelo do F2-27 valendo. **Passo 1 — medido, antes de qualquer conserto**: (1a) a coluna "Atual" do painel de Provisões (Venda\|Rev1\|Atual) lia `_negociacao_breakdown` — recomputa da NEGOCIAÇÃO salva (parametros_json/desconto), nunca do razão; por construção repetia "Venda" sempre que a AF/Conferência mexesse no razão sem reabrir a negociação (achado do Marcelo, print do Teste_6: Outros Fornecedores 0,00\|3.000,00\|0,00 e Custo de Fábrica 101.446,51\|98.446,51\|101.446,51, quando o razão já mostrava os dois lançamentos da migração). (1b) rastreado até `main.py` (invólucro da AF, F2-25 Passo 2): o alvo passado pra `ajustar_provisao_delta` era deliberadamente `max(novo, atual)` — igual a `atual` numa redução, porque a migração (`reclassificar_provisao`) sozinha já levava o CFO ao valor novo (o próprio conserto do achado "4000→3000 dava 2000" do F2-25) — CONFIRMADA a hipótese (a): delta zero por design, não silêncio; o campo "Custo de Fábrica" digitado só alimentava o cálculo do resíduo, nunca virava alvo de lançamento sozinho — exatamente a razão de dois campos poderem divergir, e a razão do Passo 2. **Passo 2 (DECIDIDO)**: Custo de Fábrica virou READ-ONLY na AF (`_PROV_RUBRICAS`, mesmo padrão do Custo Financeiro) — o gerente só digita "Outros Fornecedores" (o INCREMENTO sobre o saldo atual, não mais o alvo do CFO); o invólucro da AF (`main.py`, POST `.../provisoes/<rev>`) lança a reclassificação 2.1.04.06→2.1.04.14 automaticamente pelo incremento — migração só numa direção (nunca reverte), mesma trava de antes; qualquer valor digitado em `custo_fabrica` é ignorado (não tem entrada em `_AF_ITEM_RUBRICA`, nunca teve). **Passo 1a, conserto**: `GET /api/orcamentos/<id>/provisoes` — "Atual" de `custo_fabrica`/`out_forn` passou a ler o SALDO VIVO da provisão (`mod_contabil._mov`), as duas únicas contas que a migração da AF efetivamente move; excluídas do cálculo de "desatualizado" (uma migração legítima não é "negociação desatualizada"). **Passo 3 (DECIDIDO)**: a lista de rubricas ficou com UMA linha de Custo de Fábrica (o saldo vivo, read-only); o CFO CONGELADO (base da fórmula, nunca muda por edição) saiu da lista e foi pro bloco de totais, junto de Val_Líquido/Custo Variável/Margem Contribuição — dois rótulos quase idênticos e 18 linhas distantes eram lidos como duplicação. **Passo 4 (DECIDIDO)**: `Contrato.financeiro_concluido_em`/`financeiro_concluido_por_id` (migration `c2d3e4f5a6b7`), distinto de `status` (que continua "vigente", intocado — não governa mais a revisão da AF); `POST /api/projetos/<nome>/contrato/concluir-financeiro` confere consistência ANTES de fechar — AF1/AF2 concluídas (se existirem), documentos das subfases do PE realmente concluídas ainda vivos (`_docs_vivos`, ACHADO-30), e `mod_contabil.conferir_provisao_ativo_par` (par provisão×ativo batendo por rubrica, nova função) — recusa tudo ou nada, sempre lista o que falta; passando, fecha a fase financeira. A partir daí, reabrir a AF (`POST .../provisoes/<rev>`) exige "autorizar" (Diretor/Gerente — medido: `perfis.py` dá "autorizar" TAMBÉM ao Gerente, não só Master; só um perfil customizado sem essa capacidade é recusado de verdade, testado com um `PerfilAcesso` dedicado). Botão "Concluir Contrato" na ficha do Contrato, visível com `status=='vigente'` e ainda sem fechar. **Princípio registrado** (docs/db/PLANO_AJUSTES.md, 5ª regra): "nenhuma etapa encerra sem conferir o que ela prometeu; nenhuma etapa trava o andamento por causa disso" — terceira ocorrência em dois dias (NF-e de serviço; bloco fiscal item 5/F2-21, que errou a mão travando o ANDAMENTO; a AF, que travava a REVISÃO em vez de só o FECHAMENTO). Achado ao rodar a suíte inteira: `test_achado59_cfo_vira_rubrica_af.py` e `test_achado59_outros_forn_af1.py` (F2-25) rederivados pro mecanismo novo (out_forn como incremento, custo_fabrica ignorado); `test_fluxo_completo_e2e.py::test_contrato_real_geracao_e_assinatura` falhou uma vez isolado — confirmado via `git stash` que já falha identicamente no `main` sem nenhuma mudança deste candidato (flaky pré-existente, não reproduziu na rodada seguinte), reportado, não investigado mais fundo aqui. Suíte completa (com E2E): verde, 4 xfailed, 0 failed determinístico. Sem migration de dado (só schema novo, `c2d3e4f5a6b7`); tag `v2026.09.05-beta5`, Integração e depois Homologação, `confirmar.sh` 15/0 e smoke OK nos dois, `git describe --tags` exato; Produção NÃO tocada. Não autorizado/tocado: item 5 do bloco fiscal (F2-21, suspenso), markup de ajuste (LP-15), LP-18, o restante da LP-13, a Conferência contábil da etapa 12 (só reusada, intocada), Produção |
| **F2-29** · montado em FATIAS (pedido do Marcelo) — B (AF1 não reabre) + A ("Atual" das outras 17 rubricas) + C (projeto não se identifica) + D (isolamento de testes instáveis) | **em andamento** — Fatia B fechada (06/09, sem código): medido que `Contrato.financeiro_concluido_em` do Teste_6 estava NULL (o gate do F2-28 nunca disparou) e que `mod_ciclo.reabertura_bloqueada_por_contrato` também não bloqueia reabrir a etapa 8 (computado contra o estado real do ciclo do Teste_6 — a cascata de "8" nunca inclui "7"). Reproduzido localmente (`http_client_factory`) o caminho de uma conta `operador` tentando reabrir com as próprias credenciais: 403 "Credenciais inválidas ou perfil sem permissão" — mensagem genuína mas confusa (soa como senha errada, não "esta conta não tem autoridade"); comecei a escrever uma mensagem mais clara quando o Marcelo confirmou que era navegação (achou o botão certo, não era defeito) — revertido, nenhuma mudança de código nesta fatia. **Fatia A fechada** (06/09, `c8eca40`): confirmado que o F2-28 cobriu SÓ `custo_fabrica`/`out_forn` — as outras 17 rubricas de `mod_provisoes.itens_provisao` continuavam lendo `_negociacao_breakdown` (regra dos irmãos, ACHADO-26); F2-28 marcado **PARCIAL** no seu próprio registro acima. Conserto: `mod_contabil._PAINEL_ITEM_RUBRICA_TODAS` (nova, 17 chaves — as 16 de `_AF_ITEM_RUBRICA` + `cust_esp`, que tem par ativo×provisão mas nunca foi AF-editável) mapeia toda rubrica pro código de conta; `GET /api/orcamentos/<id>/provisoes` passa a ler o saldo vivo de cada uma via `_mov()`, fora do cálculo de "desatualizado" (mesma razão do F2-28: uma efetivação/AF/veredito sozinha não é "negociação mudou"). `custo_financeiro` fica de fora, de propósito — rota do ramo financeiro, sem conta de provisão própria nesta família (controle negativo testado). Aceite: `tests/test_f2_29_fatia_a_atual_le_razao.py` (3) — Provisão de Montagem cai de 1000 pra 600 no "Atual" após uma efetivação parcial de 400 (F2-27: só a perna de caixa), `desatualizado=False`; `cust_esp` também lê o vivo; `custo_financeiro` controle negativo. Suíte completa (sem E2E): 2666 passed, 4 xfailed, 0 failed determinístico (`test_contrato_real_geracao_e_assinatura` flaky pré-existente, já registrado no F2-28, não reproduziu nesta rodada). Fatias C e D seguem. Não corta tag — aguarda a rodada fechar (o Marcelo percorre uma vez). |
| 30 em diante | não iniciados |

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
