# Expectativa da Vistoria Final + capacidade de montagem — design (2026-08-24)

Origem: correção do item 14 do relatório de testes do Felipe, levantada na sessão de QA ao vivo de
2026-08-24 (ver `_geral/2026-08-24-relatorio-felipe-triagem-plano.md`) e fechada com o Marcelo na
mesma sessão. **A conta de capacidade de montagem é regra de negócio nova**, ditada pelo Marcelo —
não inferir nada além do que está aqui.

---

## 1. O problema

Hoje existe **um** campo de data na tela de contrato — "Expectativa de entrega" — e ele é usado como
âncora do regressivo na etapa **16 · Entrega no cliente**:

- `mod_cronograma.py:247` — `cronogramas(etapas, entrega, entrega, codigo_entrega="16")`, com
  `entrega = Projeto.data_entrega`.
- `mod_cronograma.py:184` — `folga_medicao_entrega(cfg, previsao_medicao, data_entrega,
  codigo_medicao="10", codigo_entrega="16")`.

Mas os dois marcos são coisas diferentes:

| Marco | O que é |
|---|---|
| **16 · Entrega no cliente** (ciclo) | entrega do MATERIAL **para** montar. É a referência do Cronograma Padrão. |
| **Expectativa do cliente** (contrato) | o **projeto MONTADO**. É o compromisso comercial. |

Colapsar os dois num campo só é o que produz o sintoma do Felipe: o vendedor digita a data pensando
em projeto pronto, o sistema pendura essa data na entrega-para-montar, e montagem, vistoria e
aprovação final caem todas **depois** do prometido.

**Reproduzido em 2026-08-24** no projeto `QA Vera 2026-08-24 Cronograma` (contrato R$ 98.959,41,
líquido R$ 96.852,25): informada medição 01/09/2026 e expectativa 31/10/2026, o cronograma gerado
pôs Entrega no cliente com limite 31/10 ✓, mas Montagem planejada 30/11, Vistoria final 08/12 e
Aprovação final 10/12/2026 — limite até 05/01/2027.

---

## 2. O modelo correto

1. O campo do contrato passa a se chamar **"Expectativa da Vistoria Final"** e ancora o regressivo
   na etapa de **Vistoria final**, não na 16.
2. A **Entrega no cliente** volta a ser derivada do Cronograma Padrão (entrega-para-montar), como
   sempre foi a referência do padrão.
3. A Expectativa da Vistoria Final é **guia, não promessa dura** — a montagem sofre interrupções.
   Decidir se ela BLOQUEIA a assinatura (como a folga bloqueia hoje) ou apenas AVISA — ver §6.
4. Essa expectativa também passa a ser **registrada na Agenda** como marco de referência do projeto
   montado. Hoje não existe.
5. `folga_medicao_entrega` passa a medir **medição → vistoria final**.

---

## 3. A conta (capacidade de montagem)

Entradas:

| Entrada | Onde vive | Default |
|---|---|---|
| `VL` — Valor Líquido de Venda | **Valor à Vista do contrato − Custos Adicionais** (definido pelo Marcelo, 2026-08-24). É exatamente o `Val_Liq` que o motor já devolve: `mod_negociacao.calcular_orcamento` faz `val_liq = VAVO - cust_ad`. **Usar o `Val_Liq` do motor, não recalcular.** | — |
| `prod` — Produtividade Média Diária por Dupla | `produtividade_montagem_rs_dupla_dia` | **R$ 7.000,00** por **dia útil** por dupla |
| `duplas` — Número de Equipes de Montagem | campo NOVO, ao lado das datas do contrato | **1** |

```
dias_montagem   = ceil( VL / (prod × duplas) )      # sempre arredonda PRA CIMA
dias_com_folga  = ceil( dias_montagem × 1,4 )        # folga de 40% sobre o prazo de montagem
```

O exemplo do Marcelo: estimativa de 5 dias úteis → acrescenta 2 → **7 dias úteis**.
(`ceil(5×1,4) = 7`; e `5 + ceil(5×0,4) = 7` — as duas formas coincidem para `dias_montagem`
inteiro, então tanto faz qual implementar; escolher uma e comentar.)

Conferência com o projeto de teste: `96.852,25 / 7.000 = 13,84 → 14 dias úteis` com 1 dupla;
`ceil(14 × 1,4) = 20 dias úteis` de janela de montagem até a vistoria.

**Dias ÚTEIS, não corridos.** Já existe `mod_cronograma.somar_dias_uteis(data, n)` (linha 207) —
reusar. ⚠️ Ela pula só sábado e domingo, **não conhece feriados** (está escrito na própria
docstring). Como o Marcelo grifou "importante observar que são dias úteis", decidir se entra
calendário de feriados agora ou se fica registrado como limitação conhecida.

---

## 4. Comportamento na tela

- Ao registrar a **data de medição** no contrato, o sistema **sugere** a Expectativa da Vistoria
  Final aplicando a conta acima. É sugestão — o usuário pode sobrescrever.
- O campo **Número de Equipes de Montagem** fica junto das datas do contrato, default `1`, e
  recalcula a sugestão quando muda.
- Mostrar a conta na tela (ex.: "20 dias úteis de montagem · 14 + 40% de folga · 1 equipe"), senão
  o vendedor não entende de onde saiu a data.

---

## 5. O que já existe (não recriar)

- **A produtividade por dupla JÁ EXISTE e já tem o default certo**: `Config → Agenda`, campo
  "Produtividade por dupla (R$/dupla/dia)" (`cfg-ag-produtividade` →
  `produtividade_montagem_rs_dupla_dia`, default `7000`, hint "Valor líquido que uma dupla monta por
  dia útil") — `static/index.html:4868` e `:4905`.
- **Já é usada** em `mod_agenda.capacidade()` (`mod_agenda.py:321`): `duplas = ⌈Σ montagem / prod⌉`.
  A conta nova tem que ser **coerente com essa**, não uma segunda fórmula paralela.
- **O espaço na aba Montagem do Operacional já está reservado**: `static/index.html:5716` tem o chip
  tracejado `Produtividade (configurar depois)`, com comentário explicando que era placeholder.
  **É esse chip que vira o campo**, com a tag **"Produtividade Média Diária por Dupla"**, editável
  por loja (grava no mesmo `produtividade_montagem_rs_dupla_dia` — uma fonte só, não duplicar
  config).

---

## 5-bis. Alerta de carência de montadores (pedido do Marcelo, 2026-08-24)

O campo **Número de Equipes de Montagem** do contrato é um **input de planejamento do projeto**
(quantas duplas eu pretendo alocar), **não** uma validação travada contra a disponibilidade atual da
loja. O contrato é fechado com antecedência suficiente para a loja **planejar mais montadores** —
então a resposta certa a "não tem dupla disponível" não é bloquear a venda, é **avisar quem decide**.

Portanto, além da conta de prazo, o sistema deve produzir um **aviso de carência de montadores por
período**, dirigido a **gerentes e diretores**: em tal janela, a demanda agregada de montagem
(soma dos projetos contratados) excede a capacidade instalada (duplas disponíveis × dias úteis).

O dado para isso **já é calculado hoje** — a aba Operacional → Montagem já imprime, no topo da
grade: *"Necessário no período visível: 65 dias-dupla · capacidade: 2 dupla(s) × 22 dias úteis = 44
— estouro no período"* (visto ao vivo em 2026-08-24). Ou seja, o motor de capacidade e o conceito de
estouro existem; falta **elevar isso a um alerta de gestão**, fora da tela operacional, e olhando
para a frente (projetos já contratados com montagem prevista), não só para a grade visível.

**Onde essa caixa aparece está em aberto — o Marcelo está decidindo.** Implementar primeiro o
cálculo e o endpoint que responde "carência por período"; a superfície (Painel Estratégico,
Pendências, Comercial, ou caixa própria) entra depois, sem retrabalho no motor.

---

## 6. Em aberto — confirmar com o Marcelo antes de implementar

1. **De onde a janela de montagem parte** para chegar na data de vistoria: a duração calculada
   substitui a duração padrão da etapa Montagem no cronograma (e a vistoria cai logo depois), ou a
   sugestão é `medição + padrão até o início da montagem + dias_com_folga`?
2. A Expectativa da Vistoria Final **bloqueia** a assinatura quando não cabe, ou só avisa?
3. Terminologia na UI: "Equipes de Montagem" ou "Duplas"? O texto do Marcelo usa os dois.
4. Feriados no cálculo de dias úteis — entra agora ou fica como limitação registrada?
5. **Onde mora a caixa de carência de montadores** (§5-bis) — o Marcelo está decidindo. Implementar
   o cálculo e o dado primeiro; a superfície entra depois.

---

## 7. Impacto

- `mod_cronograma.py` — âncora do regressivo, `folga_medicao_entrega`, duração da montagem.
- `main.py` — gate de assinatura (`/contrato/assinar`), que hoje valida a folga medição→entrega.
- `static/index.html` — tela de contrato (rótulo + campo novo + sugestão), aba Montagem do
  Operacional (o chip vira campo).
- `mod_agenda.py` — marco novo da expectativa na Agenda.
- Migração: campo do número de equipes no projeto/contrato.
- Testes: a conta é pura → TDD direto (casos: 13,84→14→20; 5→7; 1 dupla × N duplas; VL zero).
