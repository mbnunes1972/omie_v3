# Brief — reorganizar a tela de Negociação

Mockup visual: https://claude.ai/code/artifact/3d92b3e0-2311-4d19-a0f7-bd6ba4e44b05

Reorganize a tela de Negociação (`static/index.html`, ~linhas 1012–1480). É layout + hierarquia. **Não mude fórmula de cálculo nem nome de campo.**

## Regras do projeto

- CSS vive no `<style>` do topo de `static/index.html`.
- Cor / espaçamento / raio **só** via `var(--token)` de `design-system/orizon-tokens.css`. Se faltar token, crie lá. O pre-commit bloqueia hex literal fora dele.
- Preserve **todos** os ids (`#neg-subtotal`, `#neg-desc-val`, `#neg-avista`, `#neg-parcelado`, `#neg-total-final`, `#neg-orc-bar`, `#neg-orc-tabs`, `#btn-pool`, `#btn-novo-ambiente`, `#btn-novo-orc`) e todos os handlers inline.

## Diagnóstico

No estado do print (desconto 0, à vista), `R$ 108.541,26` aparece **sete vezes**: Valor Bruto, Valor à Vista, Valor Total do Contrato (topo), Total à vista (tabela), Total com financiamento (tabela), Valor da liquidação, Total do Contrato (rodapé).

Nem toda repetição é erro — total de coluna é legítimo. Mas **duas delas são o mesmo campo editável duplicado**: `#neg-parcelado` (topo, `onclick="negValorTotalIniciarEdicao"`) e `#neg-total-final` (rodapé, `onclick="negTotalIniciarEdicao"`). Ambos recalculam o desconto pelo valor. Um dos dois tem que sair.

E a hierarquia está invertida: os quatro KPIs do topo são os maiores números da tela (19px), seguidos do total da tabela (18px), enquanto o **Total do Contrato do rodapé — o número que vai para o contrato — é o menor dos três** (15px, via `.total-line .value` em `orizon-components.css`). Seis números disputando o mesmo peso, e o mais importante perdendo.

---

## 1. Seletor de Orçamento entra no quadro de Negociação

Mova `#neg-orc-tabs` para dentro de `.neg-hdr-box`, logo abaixo de Projeto/Cliente, precedido do rótulo "Orçamento".

- `#btn-novo-orc` vira um botão `＋` ao lado das abas (mesmo `onclick`).
- `#btn-pool` e `#btn-novo-ambiente` saem de `#neg-orc-bar` e vão para um cabeçalho novo da tabela de ambientes (à direita).
- `#neg-orc-bar` deixa de existir como faixa; mantenha o id num wrapper oculto se algum JS o referenciar.

## 2. Total do Contrato vira o herói, dentro do quadro

Mova o input `#neg-total-final` (hoje na `.total-line.emphasis` do rodapé, ~linha 1472) para dentro de `.neg-hdr-box`, abaixo do seletor de orçamento, separado por um filete:

```html
<div class="neg-hero">
  <span class="neg-hero-lbl">Total do Contrato ✎</span>
  <input id="neg-total-final" …mesmos handlers…>
  <div class="neg-hero-cond">À vista · entrada Pix · liquidação Pix</div>
</div>
```

```css
.neg-hero      { border-top:1px solid var(--border); margin-top:var(--sp-3);
                 padding-top:var(--sp-3); }
.neg-hero input{ font-family:var(--font-display); font-weight:700;
                 font-size:var(--fs-h1); font-variant-numeric:tabular-nums;
                 background:transparent; border:0;
                 border-bottom:1px dashed var(--field-border);
                 color:var(--text); padding:0 0 2px; width:100%; }
.neg-hero-cond { font-size:var(--fs-xs); color:var(--text-2);
                 margin-top:var(--sp-2); }
```

Apague a `<div class="total-line emphasis">` do rodapé. O card `#neg-parcelado-cell` do topo sai da faixa; mantenha o input `#neg-parcelado` num span oculto (`display:none`) para não quebrar o JS que escreve nele, ou aponte esses writes para `#neg-total-final`.

> **Atenção:** doze trechos de JS escrevem em `#neg-total-final` (`negTotalConfirmar`, `atualizarTF`, `_aplicarPreviewNaTela`, `negMostrarParcelado`, entre outros). Mover o elemento mantendo o mesmo `id` e os mesmos handlers é seguro; recriar um elemento novo não é.

## 3. Bruto → Desconto → À vista viram uma linha dentro das condições

Hoje é um grid de 7 colunas solto (~linha 1170). Mova para dentro do card de parâmetros, abaixo dos campos, separado por filete:

```css
.neg-cond-chain     { display:grid; grid-template-columns:repeat(3,1fr);
                      border-top:1px solid var(--border); }
.neg-cond-seg       { padding:var(--sp-3) var(--sp-4); position:relative; }
.neg-cond-seg + .neg-cond-seg { border-left:1px solid var(--border); }
.neg-cond-seg + .neg-cond-seg::before {
    content:"→"; position:absolute; left:0; top:50%;
    transform:translate(-50%,-50%); background:var(--surface);
    padding:2px 6px; color:var(--text-3); font-size:var(--fs-xs); }
```

`#sb-params` e essa linha passam a ser **um card só** (`.neg-params-box`), não dois blocos com gap.

## 4. Grid do topo

```css
.neg-top { display:grid; grid-template-columns:340px 1fr;
           gap:var(--sp-3); align-items:stretch; }
.neg-hdr-box { display:flex; flex-direction:column; }   /* remove min-width */
.neg-hdr-box .neg-hdr-actions { margin-top:auto; padding-top:var(--sp-4); }
```

Remova os `width` fixos (88/170/120px) dos campos de `#sb-params` e use `grid-template-columns:88px repeat(4,minmax(0,1fr))` com `gap:var(--sp-3)`.

## 5. Escala dos números

| Elemento | Hoje | Proposto | Token |
|---|---|---|---|
| `#neg-subtotal` `#neg-desc-val` `#neg-avista` | 19px | 15px | `var(--fs-h3)` |
| `#neg-parcelado` (4º KPI do topo) | 19px | **removido** | vira o herói |
| `#neg-total` (tfoot, com financiamento) | 18px | 14px | `var(--fs-body)` |
| `.total-line.emphasis` do rodapé | 15px | **removida** | vira o herói |
| `#neg-total-avista` (tfoot, à vista) | 14px | 13px | `var(--fs-sm)` |
| células de valor por ambiente | 14px | 13px | `var(--fs-sm)` |
| `#neg-total-final` (herói) | — | **24px** | `var(--fs-h1)` |

Regra: **só o herói passa de 15px.** Todos com `font-variant-numeric: tabular-nums`.

Conta líquida: hoje são seis números entre 15px e 19px brigando entre si; depois, um de 24px e todo o resto ≤15px. Se 24px parecer demais no monitor real, `var(--fs-h2)` (18px) é o degrau abaixo e ainda mantém o herói isolado no topo.

## 6. Painéis de modalidade

`.mod-panel-title` de `#painel-avista` / `#painel-aymore` / `#painel-cartao` passa a ser "Plano de pagamento" + um badge com a modalidade ativa (À vista / Aymoré / Cartão de Crédito), em vez do título com emoji.

No fim de `#painel-avista`, uma linha de conferência: `Entrada X + Liquidação Y = Z ✓ confere com o Total do Contrato` — usa `#av-entrada-valor` e `#av-liq-valor`, marca em `var(--err)` se não bater com `#neg-total-final`.

---

## O que isso NÃO toca

Verificado por `grep`, não por suposição:

- **Backend Python:** nenhum `.py` referencia `neg-total-final`, `neg-parcelado`, `neg-orc-bar`, `total-line` ou `neg-subtotal`. O `main.py` serve `static/` como arquivo.
- **Motor:** `mod_negociacao.py` e `mod_provisoes.py` intocados. A tela segue lendo por `negPreview` / `_aplicarPreviewNaTela`.
- **Banco / endpoints:** nada.
- **Suíte pytest:** não há teste de JS no projeto; a suíte é toda Python e não toca `static/index.html`.

## O que isso TOCA — não quebre

Quatro `getElementById` sem guarda dependem do DOM atual:

| Ponto | Linha | Por que quebra |
|---|---|---|
| `#neg-parcelado-cell` / `#neg-parcelado-sep` | 8497–8498 | `getElementById(...).style.display` sem guarda. Mantenha os elementos no DOM com `display:none`. |
| `#neg-orc-bar` | 7416 | Mesmo padrão — o JS liga/desliga a barra conforme o projeto tenha orçamentos. O id tem que sobreviver. |
| `#painel-cartao-titulo` | 8882 | `textContent = desc` apaga filhos. O badge da modalidade tem que ser **irmão** do título, nunca filho. |
| `.total-line .value input` | components.css 73 / index.html 9928 | Toda a aparência do `#neg-total-final` vem daí (mono, 15px, `width:160px`), e a linha 9928 faz `style.color=''` contando com a classe. Ao sair de `.total-line`, `.neg-hero input` precisa declarar `font-family`, `font-size` e `color`. |

A linha de conferência do item 6 é o único código de fato novo — leitura e comparação, não altera valor nenhum.

## Aceite

1. As faixas do topo terminam na mesma borda direita.
2. Existe exatamente **um** campo editável de Total do Contrato na tela.
3. Nenhum número da tela passa de 15px, exceto o herói (24px).
4. Botões de ambiente estão no cabeçalho da tabela; `＋` de orçamento junto das abas.
5. `git grep -nE "#[0-9a-fA-F]{3,8}" static/index.html` não retorna nada novo.
6. `python3 -m pytest -q` verde; Ctrl+F5 em 1280 / 1600 / 1920px, tema claro e escuro.

---

## 7. Campos da modalidade entram no card de condições (adendo, 2026-08-24)

Achado do usuário sobre o resultado dos blocos 1–3: sobrou um **vazio grande no centro** do card de
condições (`.neg-params-box`), entre a linha Desconto/Modalidade/Parcelas e a faixa
Bruto→Desconto→À vista — o card estica pra acompanhar a altura do quadro de identidade ao lado.
E o frame que define as condições de pagamento assumia **dois formatos diferentes**: À Vista com
rótulo flutuante (`.field-float`) e as financiadas com rótulo em cima (`.mod-grid`).

**O que mudou**

- Os **campos** das cinco modalidades subiram pros `.neg-cond-campos` / `.neg-cond-grid` dentro do
  card de condições — um grid só, 4 colunas, `.field-float` pras cinco. `.mod-grid` foi aposentado
  (era o único uso no sistema).
- Os ids `#painel-avista` / `#painel-aymore` / `#painel-cartao` / `#painel-vp` / `#painel-tf`
  **viajaram junto com os campos**: é o `display` deles que o JS lê como "modalidade ativa"
  (`_atualizarPaineisAbertos`, `_lerCondicaoPagamentoAtual`, `negConfirmarDesconto`). Mudou só o
  valor — `grid`, não `block` — por isso todo mundo passa por `_negModExibir()`.
- O que ficou abaixo da tabela é o **plano de pagamento**, em wrappers novos `#plano-*`. Eles só
  aparecem quando há plano de verdade (`_negPlanoResumo()`), senão sobraria um card vazio só com o
  título. `#painel-cartao-titulo` continua sendo o alvo do `textContent` de `cartaoMostrarPainel()`.
- **Redundância eliminada:** "Forma da entrada" / "Forma da liquidação" do À Vista eram um
  *segundo* par de selects, além de `#neg-forma-entrada` / `#neg-forma-parcela` da linha de cima
  (que o à vista escondia). Agora o à vista usa os de cima — com `_FORMAS_AVISTA` (inclui
  cheque/dinheiro) e "Forma das parcelas" virando "Forma da liquidação" via
  `#neg-forma-parcela-lbl`. `#av-entrada-forma` / `#av-liq-forma` sobrevivem **ocultos** como
  espelho (`_avSincronizarFormas()`), porque `_NEG_CAMPOS_POR_MODALIDADE` os salva no snapshot e
  `avistaRecalcular()` lê deles pra montar `window._planoPagamento`.
- **Ambientes / Novo Ambiente** foram pra **esquerda** do cabeçalho da tabela, e **Salvar / Aprovar
  / Imprimir** subiram do rodapé pra **direita do mesmo cabeçalho**. A `.action-row` continua sendo
  `.action-row` dentro de `#page-02` — é assim que `atualizarBotoesAprovacao()` a encontra e
  pendura o "Assinar Contrato".

**Bug pré-existente corrigido junto:** o JS procurava Salvar/Aprovar por `.btn-ok` / `.btn-amber`,
classes que o commit `481ade8` (hierarquia ghost/primary) tirou do HTML — `atualizarBotoesAprovacao`
e `atualizarBannerBloqueio` estavam achando `null` em silêncio, então "Aprovar" não desabilitava em
projeto bloqueado e Salvar/Aprovar não sumiam depois de aprovado. Agora são
`#btn-salvar-orcamento` / `#btn-aprovar-orcamento`. Os rótulos do estado bloqueado encurtaram
("✓ Aprovar" / "🔒 Aprovado") pra caber no cabeçalho da tabela.

**Efeito colateral a conferir:** `_sbParamsAtualizar()` esconde `#sb-params` inteiro pós-assinatura
— e agora os campos da modalidade estão lá dentro. Pós-assinatura eles somem junto (o plano de
pagamento, abaixo da tabela, continua visível). Antes ficavam na tela em modo travado.

**Aceite (adendo)**

1. Não há mais área vazia no card de condições em nenhuma das cinco modalidades.
2. Os campos das cinco modalidades usam o mesmo componente e as mesmas 4 colunas.
3. Existe **um** par de selects de forma na tela (o da linha de parâmetros).
4. Cabeçalho da tabela: ambientes à esquerda, ações à direita; nada de `.action-row` no rodapé.
5. `git grep -nE "#[0-9a-fA-F]{3,8}" static/index.html` não retorna nada novo.
6. `node --check` limpo no `<script>` extraído; `python3 -m pytest -q` verde.
