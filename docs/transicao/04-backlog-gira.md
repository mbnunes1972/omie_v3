# Backlog conhecido — pronto para o Gira

> Fase 2, item 3 do Plano de Transição: "Todo o backlog conhecido entra no Gira como itens
> únicos, com critério de 'pronto' claro para cada um. Gira passa a ser a única fonte de
> status." Levantado em 2026-08-05 a partir de `CLAUDE.md`, `DEV_LOG.md` (sessões 1–161) e
> `docs/superpowers/specs/`. Sanity check: `pytest --collect-only` bate com o número de testes
> reportado no DEV_LOG (**1736**) — o log está sincronizado com o código.
>
> Cada item abaixo é candidato a um card no Gira. **Nenhum item aqui está confirmado como
> ainda pendente sem checar com Marcelo antes de priorizar** — a natureza deste tipo de
> levantamento (grep num diário de 6000 linhas) é que algo pode ter sido resolvido informalmente
> sem uma sessão nova registrando. Os itens que o próprio DEV_LOG já confirma resolvidos foram
> excluídos (ver rodapé).

## Decisões de arquitetura maiores (adiadas de propósito — não são bug, são escopo grande)

| Item | Categoria | Descrição | Referência |
|---|---|---|---|
| Motor 5.0 — reestruturação `app/core/` + `app/modules/*` | Arquitetura | Reestruturação maior de toda a base ("mesma cara, motor novo"). Execução **deliberadamente adiada** até o empacotamento incremental atual estabilizar em produção. Por ora só documentação/inventário. | `docs/superpowers/specs/_geral/2026-07-16-motor-5-reestruturacao-app-design.md` |
| Segmentação Mercadoria/Serviço no contrato + distribuidora Orizon Soluções | Fiscal / Contrato | Motor fiscal já segrega Val_Cont (65/35) e separa NF-e/NFS-e, mas o **contrato entregue ao cliente não mostra o split**. Falta 2ª CONTRATADA (Orizon Soluções, CNPJ em abertura) + marcadores de valor. **Bloqueado por redação jurídica/contábil externa** (advogado/contador), não é só código. | `docs/superpowers/specs/contrato-documentos/2026-07-16-segmentacao-distribuidora-contrato-design.md` |
| Empacotar o domínio `comercial` (15 arquivos) | Arquitetura / Refactor | `fiscal/`, `integracoes/`, `auth/`, `chat/` já viraram pacote; `comercial` é o mais arriscado (ciclos de import). **Armadilha conhecida:** caminho relativo a `__file__` dentro de pacote aponta pra pasta do pacote, não a raiz — já causou 404 silencioso uma vez. | `CLAUDE.md` |
| Baseline do Alembic | Banco de dados / Infra | Migração de schema hoje é `_migrar_colunas_pg` (ADD/DROP idempotente) + seed, sem baseline formal de migração versionada. | `CLAUDE.md` |

## Chat / Comunicação (frente mais ativa no momento)

| Item | Categoria | Descrição | Referência |
|---|---|---|---|
| Trigger de reengajamento automático (RF-17) | Chat | Conteúdo dos templates já foi semeado (Sessão 155); falta o **mecanismo de disparo** (cron/systemd-timer) — nunca implementado. | Sessão 155, DEV_LOG |
| Remover shims `mod_chat.py`/`mod_chat_externo.py` da raiz | Chat / Arquitetura | Módulo já foi extraído pro pacote `chat/` (Sessão 130); os shims de compatibilidade continuam na raiz. Churn mecânico de ~15 imports, protegido por teste ratchet, mas não executado. | Sessão 130, DEV_LOG |
| `datetime.utcnow()` deprecado — varredura única | Backend / Infra | Achado pela Vera, **deliberadamente não corrigido pontualmente** (misturar datetime naive/aware pontual quebra comparação) — precisa de uma varredura de codebase inteira, não um fix isolado. | Sessão 160/161, DEV_LOG |
| `.gitignore` engolindo specs de comunicação | Infra / Git | Padrão `COMUNICACAO/` sem âncora casa `docs/superpowers/specs/comunicacao/` por engano — specs novas de chat foram parar em `_geral/` como workaround. Trocar para `/COMUNICACAO/` (âncora de raiz). | CLAUDE.md / DEV_LOG |
| Performance de `_atendimento_meta` (Atendimentos) | Chat / Performance | ~2 queries por item de inbox; gerência é auto-participante de toda conversa de projeto fechado. Backburner — medir/paginar antes de escala maior em produção. | Sessão 129, DEV_LOG |
| Plano de Testes Complementar do Chat (MET-001..008) | Chat / QA | Cenários de E2E com WhatsApp real na Instância B ainda não executados por completo. | Plano de testes, DEV_LOG |

## Financeiro / Contábil

| Item | Categoria | Descrição | Referência |
|---|---|---|---|
| FASE 3 — individualização de provisão por projeto | Financeiro | Tabela de provisões por conta com saldo por projeto, Marg_Cont recalculada, Markup = Val_Liq/CFO. Regra de negócio já decidida (provisionado vem do razão contábil, não do valor editado no Revisa) — falta implementar. | DEV_LOG (Fase D2/D3) |
| PDF da auditoria contábil | Financeiro / Contábil | Endpoint e modal já existem (estornos destacados); falta gerar o PDF exportável. | DEV_LOG |

## Perfis / Segurança / Config

| Item | Categoria | Descrição | Referência |
|---|---|---|---|
| Step-up dos painéis Admin/Config | Segurança / Perfis | Painéis hoje só ficam escondidos por perfil, sem elevação via step-up (como já existe pra módulo comum). Falta definir a semântica do que uma autorização de painel concede. Prioridade MÉDIA já registrada. | DEV_LOG |
| `contrato_editar.py:61` — gate com slugs legados | Segurança / Bug conhecido | Usa slugs pré-Perfil-4 (`gerente/diretor/admin`), o que torna o gate efetivamente sempre-verdadeiro. Prioridade BAIXA, nunca corrigido. | DEV_LOG |
| Config › Funções editáveis | Config / Perfis | Item de uma lista de 9 tópicos da reforma de perfis, pendente. | DEV_LOG |
| Config › Comissões | Config / Perfis | Idem — pendente. | DEV_LOG |

## Agenda / Cronograma

| Item | Categoria | Descrição | Referência |
|---|---|---|---|
| Cronograma "Passo 3" — editar prazos com senha gerencial | Agenda | Botão "Cronograma próprio" revisado como pendência, sem confirmação de entrega numa sessão posterior. | DEV_LOG |

---

## Itens JÁ RESOLVIDOS — não entram no backlog (registrados aqui só pra não serem
recriados por engano ao ler sessões antigas do DEV_LOG)

- Triagem automática RF-08/09 e distribuição via SAC — fechada nas Sessões 154 e 161.
- Envio de mensagem por template (F3 do plano 28/07) — fechada Sessão 156.
- Aba "Arquivadas" do Chat — implementada Sessão 131.
- Re-chaveamento nível→Função na Agenda/escopo operacional — fechado Sessão 146.
- Fatia 3 da Revisão de PE (complemento contratual + Termo Aditivo) — fechada Sessão 92.
- Custo de Fábrica/CMV não lançado no razão — resolvido pela FASE D2 (Sessão 70).

## Specs recentes conferidas — nenhuma órfã

As 4 specs mais recentes em `docs/superpowers/specs/` (agosto/2026) já viraram código e foram
fechadas no DEV_LOG — não há frente de design "esquecida" sem implementação:

- Fichário do Ciclo (01/08) → Sessões 132–133
- Agenda da Loja (03/08) → Sessões 138–150
- Orizon Chat / Atendimentos UI (04/08) → Sessões 156–161 (promovida até produção na 157)
