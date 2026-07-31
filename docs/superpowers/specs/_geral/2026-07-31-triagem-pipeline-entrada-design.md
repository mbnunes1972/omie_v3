# Triagem como pipeline de entrada de toda demanda (design)

**Data:** 2026-07-31 · **Status:** aprovado para implementação (decisão do Marcelo, orientação
2026-07-31) · **Evolui:** `comunicacao/2026-07-28-orizon-chat-revisao-design.md` (seções 5.2/8
RF-08/09/10) e `_geral/2026-07-25-chat-projeto-porta-externa-whatsapp-email-design.md` (decisão 14).

## Demanda

Decisão do Marcelo (reformula a orientação anterior): **Triagem não é só o menu automático de
boas-vindas** que a tela "Triagem" configura. Triagem é o **processo de entrada de qualquer
demanda externa** — do lead frio ao pedido de assistência de um cliente antigo — até ela estar
vinculada ao destino certo (conversa, projeto, atendente, segmento).

Hoje a promessa da decisão 14 ("ambíguo cai em fila de triagem humana") está QUEBRADA no código:
não existe fila. `processar_entrada()` (mod_chat_externo.py ~211) devolve
`{"status": "triagem", "conversa_id": None}` **sem persistir nada**; o handler do webhook
(`main.py`, POST `/webhooks/whatsapp` ~3905) **ignora o retorno**. Primeiro contato de número
nunca visto e mensagem ambígua (2+ conversas candidatas) são **descartados em silêncio** — e
`rotear_entrada()` ainda joga fora a lista `conv_ids` de candidatos que já calculou.

**Regra de ouro: mensagem nenhuma pode ser descartada em silêncio.** Todo caminho de entrada
desagua em um dos dois destinos: ou a automação resolve (casa com conversa/projeto/funcionário e
roteia), ou cai na fila humana **persistida**.

## Hierarquia de nomes (para as telas conviverem sem confusão)

- **Triagem (conceito/área)** — o pipeline de entrada como um todo.
  - **Triagem automática** — o que a tela atual "Triagem" configura: menu de boas-vindas,
    roteamento por resposta numérica, segmentos. (O item de menu atual é renomeado para
    **"Triagem automática"**.)
  - **Fila de triagem** — o que esta spec constrói: mensagens/contatos que a automação não
    resolveu sozinha (número desconhecido, ambíguo, projeto encerrado…) aguardando decisão
    humana, DENTRO da fila de Atendimentos (F7), não numa tela escondida em config.

## Decisões

1. Toda entrada externa que `rotear_entrada` não resolve é **persistida** numa fila
   (`TriagemEntrada`), nunca descartada. Preserva os candidatos quando ambígua.
2. **Idempotência por `id_externo`** (o wamid): comprovado empiricamente que a Meta reentrega o
   mesmo webhook 5-6 vezes até receber 200. Entrada repetida (mesmo `id_externo`) é no-op.
3. A fila aparece na **aba "Novos" da F7 (Atendimentos)** — primeiro os itens de triagem, depois
   os atendimentos com não-lidas. Não é tela separada de config.
4. Resolução humana tem 3 saídas: **vincular** a conversa/projeto existente (com candidatos já
   sugeridos), **criar** novo Cliente/Projeto a partir do contato (lead novo por WhatsApp), ou
   **descartar** (spam/engano) — descartar também é registro, não delete.
5. Cada resolução gera **evento inline** na conversa de destino ("Contato vinculado por Fulano
   via triagem em …"). Permissões pelo padrão `perfis.pode(...)`.
6. A triagem automática (menu RF-08/09) roda ANTES da fila: quando conectada, a resposta
   numérica do cliente define `segmento_sugerido` e a entrada cai na fila **já classificada**,
   na frente do time certo. (A conexão do menu ao webhook é a fatia F6 pendente do plano
   2026-07-28 — esta spec prepara o campo `segmento_sugerido` para recebê-la, sem depender dela.)
7. Não se mexe em: envs `ORIZON_WA_*`, validação HMAC, verify-token e o parse
   `iter_mensagens_whatsapp` (validados com a Meta em homolog). O problema é só o DESTINO do que
   o parse produz.

## 1) Modelo de dados

Tabela nova `triagem_entradas` (model `TriagemEntrada`), no padrão dos models do chat:

| Campo | Tipo | Nota |
|---|---|---|
| `id` | Integer PK | |
| `loja_id` | Integer FK lojas, NOT NULL, index | Tenancy: a loja do número que recebeu (v1: loja do `NumeroConectado`; fallback loja padrão do transporte). |
| `meio` | String(16) NOT NULL | `whatsapp` \| `email` |
| `remetente` | Text NOT NULL | Número/e-mail NORMALIZADO (dígitos p/ WhatsApp). |
| `texto` | Text | Corpo recebido. |
| `id_externo` | Text **UNIQUE**, index | wamid — chave da idempotência (decisão 2). |
| `id_externo_ref` | Text | id citado (reply), se houver. |
| `status` | String(12) NOT NULL default `pendente` | `pendente` \| `resolvido` \| `descartado` |
| `candidatos_json` | Text | JSON `[conversa_id, …]` quando ambíguo (o que `rotear_entrada` calculou). |
| `segmento_sugerido` | String(20) | Resposta do menu de triagem automática (decisão 6), quando houver. |
| `conversa_id` | Integer FK conversas | Nulo até vincular. |
| `resolvido_por_id` | Integer FK usuarios | Quem resolveu. |
| `resolvido_em` | DateTime | |
| `criado_em` | DateTime default utcnow | |

Migração: tabela NOVA → `create_all()` cria; sem ALTER em tabela existente. (**Nota:** a
orientação pedia "migração Alembic nomeada", mas o Alembic do projeto **ainda não tem baseline**
— CLAUDE.md, Etapa 2 pendente. O padrão vigente é `create_all()` + `_migrar_colunas_pg`; esta
spec segue o padrão vigente e a migração Alembic nomeada entra quando o baseline existir.)

## 2) Backend

- `rotear_entrada()` passa a devolver também os candidatos no caso ambíguo (retorno
  `(conversa | None, candidatos: list[int])` — assinatura interna; `processar_entrada` absorve).
- `processar_entrada()`: quando não roteia, **persiste** `TriagemEntrada` (status `pendente`,
  candidatos preservados) e devolve `{"status": "triagem", "triagem_id": N}`. Idempotente por
  `id_externo` (entrada já existente → devolve a existente, não duplica). Não commita (padrão).
- Handler do webhook: deixa de ignorar o retorno — loga o resultado (roteado/triagem) no nível
  info. O ack 200 segue incondicional (dormência e HMAC intactos).
- Funções de fila em `mod_chat_externo` (v1; movem p/ `chat/triagem.py` no empacotamento):
  `triagem_listar(db, loja_id)` (pendentes, mais antigos primeiro),
  `triagem_resolver_vincular(db, entrada, conversa, usuario_id)` (posta a mensagem original na
  conversa via `enviar_mensagem(..., _permitir_externo=True)` + `EnvioExterno` de entrada +
  evento inline decisão 5 + marca resolvida),
  `triagem_resolver_criar(db, entrada, usuario_id, nome_cliente)` (cria Cliente com o
  WhatsApp do remetente + conversa nova + idem),
  `triagem_descartar(db, entrada, usuario_id)`.
- Endpoints: `GET /api/comunicacao/triagem/fila` e
  `POST /api/comunicacao/triagem/fila/<id>/resolver` (`{acao: vincular|criar|descartar, …}`).
  Autenticado + `escopo_operacional`; resolver exige participação no destino ou gerência.

## 3) Frontend (depende da spec de unificação full-page)

- Aba **"Novos"** da F7 lista primeiro as entradas de triagem (badge "Triagem", remetente,
  prévia, tempo, candidatos quando houver) e depois os atendimentos com não-lidas.
- Ação na entrada: painel com os 3 botões (Vincular — com os candidatos pré-carregados quando
  ambíguo —, Criar cliente/projeto, Descartar).

## 4) Casos de teste obrigatórios (pedido explícito da orientação)

1. Primeiro contato de número nunca visto → entrada `pendente` persistida (não descartada).
2. Contato fora da janela de 24h → roteia normal se inequívoco (janela é restrição de RESPOSTA,
   não de entrada).
3. Número compartilhado por 2+ projetos → `pendente` com `candidatos_json` preenchido.
4. Reply citando mensagem arquivada/antiga → roteia determinístico pelo `id_externo_ref`.
5. Reentrega Meta do mesmo `id_externo` → não duplica (nem mensagem nem entrada de fila).
6. Funcionário que também é cliente com o mesmo número → `processar_entrada_usuario` vence
   (comportamento atual CONFIRMADO como desejado — a ponte do funcionário tem precedência).
7. Mensagem para projeto finalizado/arquivado → cai na fila (não reabre conversa morta sozinha).
8. Tenancy: usuário de outra loja não vê nem resolve a fila (404/403).

## Riscos

- `rotear_entrada` é chamada também nos testes existentes (`test_chat_externo`, `test_chat_wa`)
  — a mudança de retorno é interna; `processar_entrada` mantém contrato externo.
- Volume: fila sem TTL pode crescer com spam; descarte manual é suficiente na v1 (uma loja).
