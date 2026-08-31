# Defeitos conhecidos — candidato `v2026.08.31-beta1`

Escrito antes da subida para Produção, como a `ESTEIRA.md` exige: *"um fluxo
quebrado conhecido não impede a subida, mas não pode subir sem alguém ter
decidido que sobe."*

Isto **não** é o backlog. É o que alguém usando o beta pode encontrar ou ler
errado. O backlog inteiro está em `ACHADOS_CONTABEIS.md` e `ROTEIRO.md`.

**Atualização 31/08/2026 — candidato passou a ser `v2026.08.31-beta2`.**
O ACHADO-27 (plano de pagamento longo, ex. Cartão de Crédito 15x, colapsava
o card de ambientes na tela de Negociação — Salvar/Aprovar/Imprimir ficavam
inclicáveis) foi encontrado pelo Marcelo clicando em Homologação, medido,
consertado (`flex-shrink:0` no card, docs/db/ACHADOS_CONTABEIS.md) e provado
por E2E de navegador. Não estava nesta lista porque não tinha sido
encontrado ainda quando ela foi escrita para o beta1. Os oito itens abaixo
seguem exatamente iguais — nenhum foi tocado nesta rodada.

**Atualização 31/08/2026 (2) — candidato passou a ser `v2026.08.31-beta3`**
(pedido original repetia "beta2" — já usada, tag não se move, `ESTEIRA.md`).
O ACHADO-28 (CPF de assinatura sem validação de dígito verificador — nos
três caminhos: contrato, aprovação do PE, solicitação de medição, mais o
webhook ClickSign) foi encontrado pelo Marcelo clicando em Homologação,
consertado (`validacao_doc.erro_doc` dentro das três funções de
assinatura) e provado por `test_aceite_achado28.py` (6 aceites). Conferir o
CPF contra o cadastro da parte fica pro próximo ciclo — LP-02,
`docs/db/LISTA_PARALELA.md`. Os oito itens abaixo seguem exatamente iguais.

---

## O que pode levar a decisão errada

**1. A DRE tem três visões e uma delas calcula errado.**
`competencia_estimada` mistura receita realizada com custo estimado — foi
por isso que foi condenada. Ela só sai na Fase 4, junto com o rename para
DRE Diferida / DRE Antecipada. **Até lá, não decidir por ela.** A visão
`real` (futura Diferida) é o livro e está correta.

**2. A DRE Antecipada ainda não existe.**
O que a tela chama de "Antecipação no Contrato" tem outra semântica e será
substituída. Não é a simulação por safra que foi desenhada.

**3. Não há trava de período fechado.**
Nada impede lançamento com data em mês já reportado. Um relatório impresso
hoje pode não bater com o mesmo relatório amanhã. A tabela
`periodo_fechado` é item da Fase 3.

## O que exige ação manual que o sistema não cobra

**4. Ramo financeira: a retenção esperada não se fecha sozinha.**
O ACHADO-01 foi respondido em desenho e resolvido para `loja_antecipacao`,
mas o **gatilho automático** da conferência no ramo financeira não existe
ainda (passo 12). O saldo fica em aberto esperando alguém conferir.

**5. Lançamento manual ainda consegue zerar provisão.**
A porta dos fundos do ACHADO-26 foi fechada, mas
`/api/financeiro/lancamentos` (ACHADO-07) permite lançar contra conta de
provisão sem passar por veredito. É caminho deliberado e manual, não um
botão — mas contorna a disciplina da Fila de Provisões se alguém usar.

## O que promete o que não faz

**6. A conta `2.1.04.12 "Retenção de Comissão de Vendas"` não retém nada.**
É uma provisão simples. Retenção parcial, liberação condicionada e reversão
em receita **não existem** (ACHADO-17, decisão de produto pendente). Quem lê
o plano de contas acredita que a funcionalidade existe.

**7. `5.3.01` é usada por dois mecanismos com nomes conceitualmente
diferentes** (ACHADO-09). Não erra número; confunde quem lê.

## Medido, sem decisão tomada

**8. Segmentação do aditivo.** Um aditivo assinado depois de uma mudança de
parâmetro é faturado com a segmentação **atual**, não com a que valia quando
foi negociado. Não é alcançável em operação normal (o congelamento na
assinatura protege), e a trava da AF1 cobre a falha do congelamento
(ACHADO-23). Fica registrado porque muda o que vai na nota.

## Higiene que não afeta número

ACHADO-19 (seis rotas respondem `ok` a recálculo que falhou), ACHADO-20
(recursão no complemento auto-referente), ACHADO-22 (docstring do CMV
descreve mecanismo extinto), ACHADO-06 (a medir), P5. Todos Fase 5.

---

## O que este candidato consertou

Doze consertos de Fase 1 e quatro de Fase 2. Em particular: a receita deixou
de contar o custo financeiro duas vezes; o aditivo passou a ser faturado e
cobrado, e deixou de ser cobrado em dobro; a Conciliação Final não fecha
mais projeto com provisão em aberto, nem pela porta da frente nem pelos
fundos; e a assinatura do aditivo voltou a funcionar.

De **31 xfails** no início do roteiro para **4**.

---

## Aceite

Marcelo, ao aprovar a subida, aceita esta lista. Assinatura: a mensagem de
aprovação no histórico da conversa, referenciando a tag do candidato atual,
`v2026.08.31-beta3` (promovido de `v2026.08.31-beta1` → `-beta2` →
`-beta3` em 31/08/2026 — ver as duas "Atualização" no topo deste
documento).
