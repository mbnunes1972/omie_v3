# TAREFA — a tela do veredito e o fichário do Ciclo

Quatro achados do percurso de homologação do Marcelo, 01/09. Os três
primeiros são a mesma tela (Conciliação Final, etapa 21); o quarto é o
fichário do Ciclo inteiro.

**Ordem de execução:** 1 antes de 2 — não adianta dar status a um botão que
não deveria existir naquela linha.

---

## 1 · O botão que o servidor recusa (ACHADO-32)

Ler o ACHADO-32 antes de começar. Em resumo: `resolver-saldo-provisao`
devolve 409 para toda rubrica de veredito nomeado desde o F2-3, e a tabela
da etapa 21 continua desenhando "Resolver" em todas as linhas.

**A tabela precisa saber a regra.** Hoje `_reconProvTabelaHtml` decide o
estado dos botões por um único critério — `saldo_aberto ≈ 0`. Passa a haver
três estados por linha, e quem decide é o **backend**, não a tela:

| estado | de onde vem | o que a linha oferece |
|---|---|---|
| resolvida | `saldo_aberto ≈ 0` | nada editável, selo de concluída |
| veredito nomeado | rubrica fora de `_PROV_FORA_DO_VEREDITO` | link "Dar veredito na Fila de Provisões", sem Efetivar/Resolver genéricos |
| rota genérica | Impostos (2.1.04.13) e Custo Financeiro (2.1.04.19) | Efetivar/Resolver como hoje |

**O campo vem do servidor.** `reconciliacao()` já monta cada linha; ela
ganha uma flag por provisão (`exige_veredito`, ou o nome que a Vera achar
melhor) derivada da **mesma constante** que o endpoint usa. Duplicar a lista
de códigos no JavaScript recria o defeito de outra forma — a tela voltaria a
divergir do servidor na próxima mudança de regra.

**O texto do card também mente.** A frase *"use Efetivar/Resolver na tabela
se precisar agir nelas"* foi escrita em 07/08 e o F2-3 a invalidou em 31/08.
Reescrever dizendo o que vale hoje: as duas rubricas de rota própria se
resolvem ali; as demais, na Fila de Provisões.

**Irmãos:** o modal de Reconciliação do projeto (`modal-recon-proj`) usa o
mesmo construtor com `editavel:true`. Mesmo botão, mesmo 409, mesmo conserto.

**Teste:** um caso por estado, batendo a linha renderizada contra a resposta
real do endpoint para aquela conta. O controle negativo é o que interessa:
mova uma rubrica para dentro de `_PROV_FORA_DO_VEREDITO` e o teste da linha
"veredito nomeado" tem que falhar.

---

## 2 · Falta status de veredito na linha

Pedido do Marcelo, direto: *"falta um status de veredito (mudar a aparência
dos botões e dar algum sinal de ok)"*.

O que existe hoje: quando o saldo zera, os botões desabilitam e mudam para
`--status-ok` com `opacity:.7`. Foi desenhado em 07/08 e a intenção estava
certa — o problema é que **verde com borda verde lê como "clique aqui",
não como "pronto"**. Na tela dele a linha da Provisão de Garantia estava
resolvida e era a que mais parecia acionável.

E o único sinal de que a ação foi aceita é um `showToast` que some. Numa
tabela onde a linha não se move, o operador não tem como distinguir
"funcionou" de "não fez nada" — foi exatamente o que aconteceu.

**O que a linha precisa mostrar, sem depender de o usuário ter visto o
toast:**

**Um selo de estado na própria linha**, coluna própria ou ao lado do nome:
`EM ABERTO` / `EFETIVADA` / `RESOLVIDA` / `NA FILA` (o estado 2 do item 1).
Texto, não só cor — a cor sozinha já falhou uma vez aqui.

**Botões concluídos param de parecer botões.** Sem borda, sem cor de ação:
texto apagado com um ✓, ou some o botão e fica o selo. O que não pode
continuar é o botão desabilitado com a cor mais viva da linha.

**A linha que acabou de mudar se anuncia.** Um realce de um segundo na
linha recarregada, ou o selo entrando com transição. É o sinal de "aconteceu
aqui" que o toast não dá.

**E o toast tem que dizer o que foi feito.** Hoje `reconProvResolver`
mostra *"Saldo resolvido."* mesmo quando o backend devolveu `None` por não
haver saldo (`abs(saldo) < 0.005` → `return None`, e o endpoint responde
`ok:true` com `lancamento:null`). Distinguir: *"Resolvido R$ X"* quando
houve lançamento, *"Nada a resolver — saldo já estava zerado"* quando não.

---

## 3 · Tooltip explicando cada veredito

Pedido do Marcelo: *"colocar a função que explica o que é e o que faz
efetivamente cada veredito ao passar o mouse sobre o botão"*.

O padrão já existe na própria tabela — o `title` do "Efetivar" travado de
Assistência/Garantia. Estender a todos, dizendo **o que acontece no livro**,
não o que o botão se chama:

**Efetivar** — "Registra o custo real desta rubrica: reconhece a despesa na
competência de hoje e baixa o ativo diferido. Informe o valor efetivamente
gasto."

**Resolver** — o texto muda com a rubrica, porque o efeito muda, e essa é
justamente a informação que falta:

- rubrica com despesa em tempo real: "Cancela o saldo que sobrou contra o
  ativo diferido. **Não mexe no resultado** — sobra é dinheiro nunca gasto,
  não é receita."
- rubrica com destino de variância: "Fecha o saldo contra <conta de
  destino>. Sobra e falta vão para a mesma conta, com sinais opostos."
- rubrica de veredito nomeado: o link para a Fila, com "esta rubrica exige
  veredito nomeado — Efetivar/Resolver genérico não vale aqui."

O destino já é conhecido pelo backend (`_PROV_DESTINO_VARIANCIA`,
`_PROV_DESPESA_POR_ATIVO`). **Vem de lá pronto**, pela mesma razão do item 1.

---

## 4 · A negociação aparece embaixo do fichário do Ciclo

Relato do Marcelo: *"no painel de etapas permanece aparecendo o valor do
contrato com as parcelas de pagamento abaixo na tela... parece ser a tela que
aparece na negociação e depois fica por lá, nunca é fechada"*.

**Está diagnosticado.** `#ciclo-panel` é `position:absolute; inset:0` dentro
de `#page-02` (que é `position:relative`). Um absoluto com `inset:0` cobre a
**altura usada** do contêiner — não a altura do conteúdo que transborda. Com
o `#plano-aymore` (o Plano de Pagamento, linha 1583) aberto, `#page-02` tem
conteúdo mais alto que a tela; `.content` rola; e ao rolar, o operador passa
pelo fim do fichário e cai na negociação que continua embaixo. Não é resíduo
de estado: é a página inteira aparecendo sob um "overlay" que nunca cobriu
mais que uma tela de altura.

**Conserto:** quando o Ciclo está aberto, o resto da página não é sobreposto
— é escondido.

```
#page-02.ciclo-on > *:not(#ciclo-panel):not(.modal-overlay){display:none}
```

`abrirCiclo()` põe a classe, `fecharCiclo()` tira.

**A exceção `.modal-overlay` não é detalhe.** `#modal-recon-proj` e
`#modal-contatos-conf` são filhos de `#page-02` e são abertos **de dentro do
Ciclo**. Escondê-los junto quebraria a Reconciliação do projeto — que é
justamente uma das telas do item 1.

**Teste:** o E2E abre o Ciclo com o Plano de Pagamento visível, rola até o
fim de `.content` e afirma que nenhum elemento da negociação está visível; e
abre a Reconciliação a partir do Ciclo, afirmando que o modal aparece.

---

## 5 · O selo fiscal — confirmação de campo

Não é item novo, é medição para o item 4 do `TAREFA_BLOCO_FISCAL.md`.
Marcelo, depois de preencher o endereço do emitente: *"preenchi os dados e
salvei, não veio informação nenhuma de que estava em condição de emitir a
NF-e ou não, mas dessa vez funcionou."*

**Descobrir que deu certo emitindo é o defeito.** Confirma os três blocos do
selo (identificação, endereço do emitente, endereço do destinatário) e
confirma que o retorno do "Salvar configuração fiscal" precisa dizer o
estado, não só que salvou.

---

## O que reportar

1. Cada item com aceite próprio, com o teste que prova.
2. Do item 1, especialmente: a flag saiu do backend ou foi duplicada no
   JavaScript? Se foi duplicada, não passou.
3. Se aparecer uma quarta tela usando `_reconProvTabelaHtml` que este
   documento não citou, isso é achado — a regra é enumerar todos os irmãos.
