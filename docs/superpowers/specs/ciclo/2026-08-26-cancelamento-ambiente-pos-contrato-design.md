# Cancelamento de ambiente pós-contrato (design)

**Data:** 2026-08-26
**Status:** conceito em discussão (levantado pelo lojista 2026-08-26, a partir de um achado da Vera
em bateria E2E). Spec para revisão; implementação NÃO iniciada.
**Relaciona-se com:** `ciclo/2026-07-21-revisao-pe-venda-renegociacao-design.md` (Conciliação de PE/
AF2 — ajuste de VALOR por ambiente), `ciclo/2026-07-27-desmembramento-operacional-desde-medicao-
design.md` (retenção por obra — o precedente de "split de parcela por ambiente" que este documento
reaproveita).

---

## 1. Motivação (a dor)

Depois que o contrato está assinado, o cliente às vezes pede uma mudança no que foi vendido — de um
acréscimo pontual até "não quero mais esse armário". O lojista propôs a régua (2026-08-26):

> A mudança de escopo em certa medida pode ser tratada como revisão, desde que preservado o conceito
> de ambiente. Um acréscimo de itens provoca aumento de valor e uma redução de escopo, como eliminação
> de um armário, pode provocar devolução parcial de valores. Mudanças que alterem completamente o
> escopo podem ser tratadas como cancelamento e geração de crédito, a ser negociado pontualmente.

Uma auditoria E2E da Vera (2026-08-26) tinha acabado de achar, ao reproduzir ao vivo, que a ÚNICA
ferramenta hoje capaz de reabrir escopo real (não só valor) — a revisão de subfase do PE
(`POST /ciclo/11b/revisao` e `/11c/revisao`) — tem uma cascata sem fronteira: reabrir a 11b reseta
TODAS as etapas posteriores já existentes, inclusive etapas operacionais (12-20) já executadas de
verdade (produção encaminhada, NFe emitida, montagem concluída), apagando o rastro de conclusão em
silêncio. Esse achado foi corrigido separadamente (ver DEV_LOG, Sessão pós-2026-08-26 — nova função
`mod_ciclo.etapas_operacionais_ja_iniciadas`) e é o que expôs esta lacuna maior: mesmo com a cascata
seguindo em frente, ela nunca resolveria uma mudança de escopo GRANDE — só reabre etapas do PE, não
lida com "o cliente não quer mais esse ambiente".

## 2. O que já existe (mapeado 2026-08-26)

O modelo de dados já trata **ambiente como a unidade atômica** de escopo/preço:
`PoolAmbiente` → `OrcamentoAmbiente` (N:N com o orçamento) → `ParcelaAmbiente` (N:N com a parcela de
cobrança, quando o projeto está desmembrado). Isso já casa com "desde que preservado o conceito de
ambiente" — não é preciso inventar uma unidade nova.

E os primitivos financeiros pós-assinatura, por ambiente, já existem via `ConciliacaoPeFase`
(decisão da AF2 quando o PE muda o custo de um ambiente — `mod_conciliacao_pe.TIPOS_DECISAO`):

| Regra do lojista | Cobertura hoje |
|---|---|
| Acréscimo de item → aumento de valor | ✅ `tipo_decisao="cobrar"` — cobra a diferença do cliente |
| Redução dentro do ambiente (ex. tirar um armário, ambiente continua existindo) → devolução parcial | ✅ `tipo_decisao="estornar"` — credita em Créditos a Clientes (`2.1.11`), `mod_contabil.estornar_credito_cliente` |
| Mudança completa de escopo → cancelamento + crédito negociado à parte | ⚠️ **o veículo existe, a ação não (§3)** |

O "crédito negociado pontualmente" já tem mecanismo pronto e **deliberadamente desacoplado**:
`mod_contabil.saldo_credito_cliente`/`baixar_credito_cliente` nunca compensam automaticamente com um
Complemento de Projeto futuro — é o gerente Adm/Fin que decide quando e como tratar (abater em Contas
a Receber ou devolver em caixa). Isso já É "negociado pontualmente".

E o **Termo Aditivo** (`Aditivo`/`AditivoAssinatura`, tabela própria, versionado, assinado por
loja+cliente, `dados_json` com snapshot da diferença) já é o formato certo para registrar
formalmente uma mudança de contrato pós-assinatura — é o mesmo veículo que hoje documenta o
Complemento de Projeto (aumento de custo do PE).

## 3. O gap real

**Hoje é fisicamente impossível remover um ambiente do escopo depois do contrato assinado.**
`POST /orcamentos/<id>/ambientes/<id>/remover` (main.py) tem trava dura sem exceção:
```python
if _contrato_assinado(orc.projeto_id, db):
    self.send_json({"ok": False, "erro": "Contrato assinado — alterações não permitidas."}, code=403)
```
Só existe ajuste de *valor* dentro do ambiente (cobrar/estornar via AF2). Não existe caminho — nem
manual, nem via API — para tirar um ambiente inteiro do escopo e gerar o crédito correspondente.

## 4. Modelo proposto (reaproveitando o que já existe)

O `mod_retido.py` (retenção por obra, 2026-07-27) já resolve um problema estruturalmente parecido:
dado um subconjunto de ambientes de uma parcela, faz o **split** (a parcela original segue com o
resto; uma nova parcela nasce só com os selecionados), reusando `mod_parcelas.particionar_por_selecao`
+ `congelar_parcelas` pra manter `Σ val_cont_congelado` exato ao centavo. A diferença é só o
DESFECHO: retenção é uma pausa (`retido` → volta a `aguardando` quando a obra libera); cancelamento
seria definitivo.

Proposta: um **novo status terminal de parcela**, `"cancelado"` (ao lado de `aguardando|em_aprovacao|
liquidada|retido`), com o mesmo mecanismo de split de `mod_retido.reter`/`liberar` — mas sem volta.
Ao cancelar:

1. **Split da parcela** (reaproveita `mod_parcelas.desmembrar_fase`/`particionar_por_selecao`, mesmo
   código do split de retenção): o(s) ambiente(s) cancelado(s) saem para uma parcela própria, status
   `cancelado`, com o `val_cont_congelado` exato daquele(s) ambiente(s) — a mesma conta que já embasa
   o crédito hoje (é o valor congelado no contrato, não um recálculo).
2. **Crédito ao cliente** — reusa `mod_contabil.estornar_credito_cliente` (o mesmo lançamento A que a
   decisão "estornar" da AF2 já faz: DR 4.3.02 Devolução de Vendas × CR 2.1.11 Créditos a Clientes),
   pelo `val_cont_congelado` da parcela cancelada. Fica em aberto até baixa manual — mesmo padrão, "a
   ser negociado pontualmente" já é o comportamento de `baixar_credito_cliente`.
3. **Registro formal** — gera um `Aditivo` (mesmo modelo do Complemento de Projeto: `dados_json` com
   o snapshot do que foi cancelado + valor creditado, assinatura loja+cliente). Diferente do
   Complemento (que SOMA valor ao contrato), este subtrai — mas a mecânica de versionamento/
   assinatura/histórico é idêntica; não precisa de tabela nova, só um `tipo`/flag no `Aditivo`
   existente pra distinguir na exibição ("Termo Aditivo de Cancelamento" vs "de Complemento").
4. **`PoolAmbiente` não é apagado** (mesma filosofia do resto do sistema — "Pool permanente... nunca
   deletado"). Ganha um flag/status próprio (`cancelado_em`, `cancelado_por_id`) pra sumir das telas
   operacionais sem perder o histórico.

### 4.1 O limite físico — até onde dá pra cancelar

Um cancelamento não desfaz trabalho já feito no mundo real. A mesma fronteira que a correção da
cascata de revisão (§1) acabou de formalizar em `mod_ciclo.etapas_operacionais_ja_iniciadas` serve
aqui: se o ambiente já tem pedido implantado na fábrica (etapa 12), produção em curso (13), ou além,
"cancelar" não é mais uma operação de dados — é uma devolução/perda física que precisa de um fluxo
excepcional (negociação com a fábrica, eventual custo de produção já incorrido a debitar do crédito).
Proposta: o cancelamento simples (self-service, sem aprovação extra) fica disponível **só até a
etapa 11 (Projeto Executivo) inclusive** — no PE, ainda não houve pedido físico. A partir da 12,
cancelar deveria **exigir uma decisão gerencial explícita** (aprovação financeira, como a AF2/AF1),
com o valor do crédito sujeito a ajuste manual (descontar o custo de produção já gasto) — não um
cálculo automático.

## 5. Fluxo alvo (rascunho, sujeito a decisão)

1. Consultor/Gerente identifica que o cliente quer cancelar um ambiente já contratado — abre uma
   tela nova (ou uma seção dentro do que hoje é "Renegociação de ambientes" da 11e) e seleciona o(s)
   ambiente(s).
2. Sistema mostra o `val_cont_congelado` daquele(s) ambiente(s) (o mesmo número que já aparece na
   AF2/reconciliação) como o crédito proposto.
3. Se algum ambiente selecionado já passou da 11 (pedido implantado/produção): bloqueia o caminho
   simples, direciona pra aprovação gerencial com ajuste manual de valor (§4.1).
4. Gerente/Diretor confirma (login+senha, mesmo padrão de `_aprovador_financeiro`) → gera o `Aditivo`
   de cancelamento, faz o split de parcela, lança o crédito (`estornar_credito_cliente`).
5. Assinatura loja+cliente do Aditivo (mesmo fluxo do Complemento) formaliza o cancelamento.
6. Crédito fica em aberto em `saldo_credito_cliente` até o Adm/Fin decidir a baixa (abater ou
   devolver em caixa) — sem prazo, sem automação.

## 6. Impactos a mapear antes de implementar

- **Fiscal:** se o ambiente já tem NF-e emitida (etapa 15) cobrindo aquele valor, cancelar depois
  exige nota de devolução/complementar — fora do escopo puramente de ciclo, precisa de olhar fiscal
  dedicado (`fiscal/` — mod_nfe).
- **Conciliação Final (21):** como uma parcela `cancelado` se comporta no fechamento — provavelmente
  fica de fora do `Σ` que a Etapa 21 resolve à força (mesmo tratamento que `mod_retido` já dá pra
  `retido`, ver `mod_retido.fracao_reconhecivel`).
- **Comissão:** se o ambiente cancelado já gerou comissão calculada (venda registrada), o
  cancelamento precisa reverter/ajustar a comissão do consultor — não mapeado aqui, precisa de
  olhar em `mod_comissao.py`.
- **Migração:** nenhuma — é feature nova, projetos existentes simplesmente nunca terão parcela
  `cancelado` até o dia em que alguém usar o recurso.

## 7. Decisões em aberto (para o lojista fechar antes de codar)

1. Onde fica a tela/botão de "cancelar ambiente" — dentro da 11e (perto de Renegociação), ou um
   ponto novo mais genérico do fichário?
2. Cancelamento acima da etapa 11 (produção já iniciada): quem aprova — mesmo perfil da AF2
   (Gerente Adm/Fin, Diretor), ou precisa de um novo gate?
3. O ajuste manual de valor (descontar custo de produção já incorrido) é um campo livre editado pelo
   aprovador, ou precisa de uma fórmula (ex.: CFO do ambiente na fábrica, se já tiver PE carregado)?
4. `Aditivo` ganha um campo `tipo` (`complemento` | `cancelamento`) ou basta inferir pelo sinal do
   valor em `dados_json`? (Recomendo campo explícito — mais fácil de filtrar/exibir sem parsear JSON.)

## 8. Fatiamento sugerido (quando for implementar)

1. Status `cancelado` em `ParcelaProjeto` + split reaproveitando `mod_retido`/`mod_parcelas` (só até
   etapa 11, sem aprovação extra) — TDD, sem tocar razão ainda.
2. Lançamento de crédito (`estornar_credito_cliente`) + geração do `Aditivo` de cancelamento
   (reaproveita template/assinatura do Complemento).
3. UI (tela/botão, seleção de ambiente, confirmação com login+senha).
4. Gate pós-etapa-11 (aprovação gerencial + ajuste manual de valor) — só depois da fatia 1-3
   validada, é a parte que mexe com produção física real.
5. Fiscal (NF-e já emitida) e Comissão (venda já reconhecida) — avaliar se entram nesta rodada ou
   ficam como "cancelamento só permitido antes da NF-e/comissão", mais simples pra uma primeira
   versão.

Cada fatia: suíte verde, DEV_LOG + spec atualizada, Vera antes de fechar (área sensível: ciclo +
contábil + fiscal).
