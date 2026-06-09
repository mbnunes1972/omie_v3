# Fluxo de 38 Etapas - Processo Comercial Dalmobile

Status: [REFERENCIA] - mapeamento do processo completo
Modulo relacionado: docs/modulos/kanban/SPEC.md

---

## Visao geral

O processo comercial da Dalmobile e dividido em 6 fases,
totalizando 38 etapas desde a captacao do cliente ate o pos-venda.
Este fluxo e a base para o Kanban comercial (v0.4.0).

---

## Fase 1 - Pre-venda / Captacao

| Etapa | Descricao | Responsavel |
|---|---|---|
| 01 | Identificacao do lead (indicacao, visita, campanha) | Consultor |
| 02 | Primeiro contato e qualificacao | Consultor |
| 03 | Agendamento de visita a loja ou ao imove | Consultor |
| 04 | Visita e levantamento de necessidades | Consultor |
| 05 | Registro do cliente no sistema | Consultor |
| 06 | Registro do parceiro indicador (se houver) | Consultor |

---

## Fase 2 - Projeto

| Etapa | Descricao | Responsavel |
|---|---|---|
| 07 | Briefing tecnico do projeto | Consultor / Projetista |
| 08 | Elaboracao do projeto no Promob | Projetista |
| 09 | Revisao interna do projeto (Conferente) | Conferente |
| 10 | Apresentacao do projeto ao cliente | Consultor |
| 11 | Ajustes do projeto apos feedback do cliente | Projetista |
| 12 | Aprovacao final do projeto pelo cliente | Cliente / Consultor |

---

## Fase 3 - Negociacao

| Etapa | Descricao | Responsavel |
|---|---|---|
| 13 | Importacao do XML do Promob para o Omie_V3 | Consultor |
| 14 | Configuracao de margens e parametros | Consultor |
| 15 | Definicao da forma de pagamento | Consultor |
| 16 | Aplicacao de desconto (com autorizacao se necessario) | Consultor / Gerente |
| 17 | Apresentacao da proposta ao cliente | Consultor |
| 18 | Negociacao e ajuste final de condicoes | Consultor |
| 19 | Fechamento verbal do negocio | Consultor |

---

## Fase 4 - Contrato e Pedido

| Etapa | Descricao | Responsavel |
|---|---|---|
| 20 | Emissao da proposta comercial formal | Consultor |
| 21 | Assinatura do contrato pelo cliente | Cliente / Consultor |
| 22 | Registro do contrato no sistema | Consultor |
| 23 | Exportacao do pedido para o Omie | Consultor |
| 24 | Confirmacao do pedido na fabrica | Gerente / Adm |
| 25 | Registro e controle do pagamento (entrada + parcelas) | Adm / Financeiro |

---

## Fase 5 - Producao e Logistica

| Etapa | Descricao | Responsavel |
|---|---|---|
| 26 | Acompanhamento da producao na fabrica | Gerente |
| 27 | Medicao tecnica no imove do cliente | Tecnico |
| 28 | Elaboracao do projeto executivo | Projetista |
| 29 | Aprovacao do projeto executivo pelo cliente | Cliente / Consultor |
| 30 | Confirmacao de data de entrega com cliente | Consultor |
| 31 | Transporte e entrega dos moveis | Logistica |

---

## Fase 6 - Pos-venda

| Etapa | Descricao | Responsavel |
|---|---|---|
| 32 | Montagem dos moveis | Montador |
| 33 | Vistoria pos-montagem | Tecnico / Consultor |
| 34 | Aprovacao da montagem pelo cliente | Cliente |
| 35 | Abertura de ocorrencia em caso de nao conformidade | Consultor |
| 36 | Resolucao de nao conformidades | Tecnico / Fabrica |
| 37 | Pesquisa de satisfacao com o cliente | Consultor |
| 38 | Indicacao de novos clientes / recompra | Cliente |

---

## Implementacao no Kanban

O Kanban comercial (v0.4.0) representa cada etapa como uma coluna.
Cada projeto e um cartao que avanca pelas colunas conforme o processo evolui.

Agrupamento sugerido no Kanban:
- Coluna 01-06: Captacao
- Coluna 07-12: Projeto
- Coluna 13-19: Negociacao
- Coluna 20-25: Contrato
- Coluna 26-31: Producao
- Coluna 32-38: Pos-venda

---

## Referencias

- docs/modulos/kanban/SPEC.md
- docs/modulos/pos_venda/SPEC.md
- docs/historias/BACKLOG.md
