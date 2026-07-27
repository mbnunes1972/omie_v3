# Conversa do Projeto unificada no Orizon Chat (design)

**Data:** 2026-07-27
**Status:** conceito APROVADO (debate com o lojista, 2026-07-27). Spec para revisão; implementação em
fatias, ainda não iniciada.
**Evolui:** `2026-07-27-central-comunicacao-omnichannel-design.md` (Orizon Chat, fatias 1-6). Este
documento unifica a antiga "Mensageria do projeto" (`tipo=projeto`) com o Orizon Chat.

---

## 1. Motivação

Hoje há **dois conceitos sobrepostos**: (a) a **Mensageria do projeto** (`Conversa.tipo=projeto`, o
botão dentro do projeto, integrada ao ciclo — transferência/bloqueador/documento —, mas **fora** da
inbox do Chat); (b) o **Orizon Chat** (inbox direct/grupo/mural/fóruns; `assunto=projeto` é só uma
*etiqueta*). O lojista quer **fundir**: quando o assunto é um projeto, o Orizon Chat vira a **instância
do projeto**, com **todos os envolvidos**, acessível de dentro do projeto E na inbox.

## 2. Decisões do debate (2026-07-27)

1. **Uma conversa por projeto** (`tipo=projeto`, já existe): aparece na **inbox** e abre pelo **botão do
   projeto** — a MESMA. `assunto=projeto` deixa de ser etiqueta e passa a **entrar na conversa do
   projeto** (não existe mais "direct etiquetado como projeto").
2. **Membros = derivados ∪ override manual (override vence).** Base automática (time interno) sincroniza
   com a equipe do projeto; o gerente adiciona/remove na mão e o ajuste **prevalece** no próximo sync.
3. **Cliente e arquiteto são "envolvidos", mas a thread da equipe é INTERNA a eles.** Comunicação com
   externos é **dirigida** (envio externo explícito por WhatsApp/e-mail; a resposta volta pra conversa).
   Nunca repassar a conversa interna inteira ao cliente.
4. **Engrenagens do ciclo continuam DENTRO da conversa:** transferência oficial (grava em `CicloEtapa`),
   bloqueador (trava o avanço) **e documento OFICIAL pelo chat** (cria `CicloDocumento`).
5. **Autoridade stage-aware:** Gerente/Diretor sempre; **e o RESPONSÁVEL DA ETAPA** pode anexar documento
   oficial da sua etapa. O chat **acompanha todas as etapas**; o responsável da etapa é o dono de
   acompanhar as informações dela.
6. **Mensagem privada:** removida do escopo (limpeza).

## 3. Modelo de dados

Reuso máximo. `Conversa.tipo=projeto` já existe (um por projeto, `get_or_create_conversa_projeto`), com
`projeto_nome`/`cliente_id` e `documento_ref_id`/transferência já no modelo de mensagem.

- **`conversa_participantes` ganha `origem`** (`auto` | `manual`) **+ `removido`** (0/1) — IMPLEMENTADO.
  `mod_chat.sincronizar_participantes_projeto(db, conversa, membros_usuarios)` recomputa: adiciona os
  derivados ausentes como `auto`; remove `auto` que saiu do time; **override vence** — `manual` fica e
  `auto` com `removido=1` (remoção manual) NÃO volta. `eh_participante` ignora `removido=1`. A conversa
  `tipo=projeto` entra na **inbox** (`listar_inbox`, título "📁 <projeto>"); o sync roda ao **abrir** a
  conversa do projeto e no **fechamento** (os auto-designados passam a ver o resumo na inbox). O
  **botão do projeto** e o item da inbox abrem a mesma conversa.
  - **`assunto=projeto` na "Nova mensagem" ABRE a conversa do projeto** (não cria direct):
    `POST /api/comunicacao/conversas {assunto_tipo:'projeto', projeto_nome}` faz get-or-create +
    sync e devolve a conversa. Front: seletor de assunto em modo projeto (esconde tipo/Para, botão
    "Abrir conversa do projeto").
  - **Override manual (gerente):** `GET/POST /api/comunicacao/conversas/<id>/participantes`
    (`mod_chat.listar_participantes`/`gerir_participante`). GET = participante/gerência (devolve
    `origem` + `pode_gerir`); POST add|remove = só `ver_todas_conversas`. Front: botão "Membros" na
    conversa do projeto → painel com badges auto/manual + adicionar/remover.
  - **E-mail de lacunas no fechamento** (IMPLEMENTADO): havendo lacunas, o hook do fechamento envia
    e-mail aos gerentes/diretores da loja (`ver_todas_conversas` + e-mail) com o projeto + as funções
    a definir (`mod_chat_externo.notificar_gerentes_email`, config-gated — sem SMTP fica
    `pendente_config`). Os auto-designados já veem o resumo na inbox (são membros da conversa).
    **Falta:** convergência do roster de 7 papéis, gate de PE/montagem, remover modo privado.
- **Derivação do conjunto interno D — FONTE ÚNICA por FUNÇÃO (decisão 2026-07-27).** A origem é a
  **função responsável de cada etapa** (`CicloEtapa.funcao_responsavel_id`, vinda do Cronograma Padrão
  da loja — data-driven). O funcionário é **derivado**: **1 candidato ativo → automático**; **>1 →
  LACUNA** (ação gerencial no fechamento); **0 → sem responsável**. Funcionário já fixado na etapa
  (`responsavel_funcionario_id`) é respeitado. **Montagem** mantém o refinamento **por AMBIENTE** no
  Mapa de Atribuições (função geral + ambiente). O **criador** sempre entra. Implementado em
  `mod_equipe.equipe_do_projeto()` → `{membros, membros_usuarios, lacunas, criador_usuario_id}`.
  **Convergência:** o roster de 7 papéis (`mod_equipe.equipe()`, client-facing) passará a **DERIVAR
  desta fonte** numa fatia seguinte — os seletores medidor/finalizador/montagem viram **resolução de
  lacuna** (grava `responsavel_funcionario_id`), aposentando o `equipe_json`.
- **Montagem da equipe no FECHAMENTO** (2ª assinatura → `fechado`, decisão 2026-07-27): resolve os
  automáticos, deixa as lacunas, e **notifica** — os auto-designados ("novo contrato, veja o
  cronograma") e os gerentes/diretores (e-mail + chat) com a equipe definida + as lacunas a preencher.
- **TERCEIROS na equipe (decisão 2026-07-27).** Montador/Medidor/PE costumam ser **terceiros**, não
  funcionários — e `Terceiro` já tem `funcao_id`. Então `candidatos_da_funcao` = **funcionários ∪
  terceiros** da função. Terceiro **não é usuário** (não loga): participa como **EXTERNO dirigido**
  (WhatsApp/telefone), mesma regra de cliente/arquiteto (thread interna privada). `equipe_do_projeto`
  separa `membros` (funcionários → usuários internos) de `externos` (terceiros). UI: seção "Equipe
  terceirizada".
- **BLOQUEADOR INVERTIDO — gate de EXECUÇÃO por etapa (decisão 2026-07-27).** Além do bloqueador que
  impede avançar, há o inverso: **uma etapa não pode ser EXECUTADA sem responsável definido**
  (`mod_equipe.etapa_executavel` — definido OU 1 candidato; lacuna/sem-candidato = travado). Trava
  **só a etapa**, não o fluxo → a **venda programada** fecha com equipe incompleta e cada etapa
  (medição, PE, montagem) só executa quando seu responsável for indicado, o que pode vir **até a época
  do pedido**.
- **Externos (cliente/arquiteto) NÃO entram em `conversa_participantes`** — não são usuários. São
  alcançados por **envio externo dirigido** (o `EnvioExterno`/canal externo que já existe), e as
  respostas roteiam de volta pra conversa (roteamento de entrada já implementado).
- **Documento oficial pelo chat:** o compositor ganha o modo "documento oficial" → etapa + tipo + arquivo
  → cria um `CicloDocumento` (reusa a lógica do upload do ciclo) e uma mensagem com `documento_ref_id`
  apontando pra ele. Diferente do anexo casual (`mensagem_anexos`), que continua existindo.
- **Narração das etapas:** `mensagem_passagem_fase` (já existe) posta a transição de fase na conversa —
  é o "o chat acompanha as etapas".

## 4. Autoridade / permissões

- **Gerir membros na mão:** Gerente/Diretor (`ver_todas_conversas`).
- **Documento oficial pelo chat:** Gerente/Diretor **OU o responsável da etapa** em questão (stage-aware),
  respeitando também o gate do ciclo (`executar_pe`/`gerir_documentos`) onde já se aplica.
- **Ler a thread interna:** participantes internos (+ oversight de Gerente/Diretor). Externos NUNCA veem a
  thread interna.

## 5. Tenancy / privacidade

- Conversa do projeto escopada na **loja do projeto**. Thread interna só para participantes internos.
  Externos recebem apenas mensagens **dirigidas** (via `EnvioExterno`), jamais a thread interna.
- Compatível com as correções recentes de contexto de loja (a conversa herda a loja do projeto).

## 6. O que muda para o usuário

- O botão **"Mensageria/Conversa"** dentro do projeto passa a abrir a **conversa do projeto no Orizon
  Chat** (mesma thread). A tela avulsa antiga se aposenta; transferência/bloqueador/documento migram para
  a thread do Chat.
- **`assunto=projeto`** em "Nova mensagem" → **entra na conversa do projeto** (não cria direct).
- Conversas de projeto aparecem na **inbox** para seus membros, com não-lidos.

## 7. Migração

- As conversas `tipo=projeto` já existem — passam a aparecer na inbox e ganham os membros derivados no
  primeiro sync. Sem migração destrutiva. Registros de `assunto=projeto` em direct/grupo antigos (poucos,
  do dev) podem ficar como estão ou ser convertidos — decidir na Fatia 1.

## 8. Fatiamento proposto (TDD backend → UI)

1. **Membership + inbox:** `conversa_participantes.origem/removido`; derivação + sync (com override);
   conversa de projeto entra na inbox; `assunto=projeto` abre a conversa do projeto.
2. **Unificar a UI:** botão do projeto abre a conversa no Orizon Chat; mover transferência/bloqueador para
   a thread; aposentar a tela avulsa.
3. **Documento oficial pelo chat:** modo documento no compositor → `CicloDocumento` (stage-aware,
   autoridade da etapa/gerência).
4. **Override manual de membros (UI):** gerente adiciona/remove, ciente da `origem`.
5. **Remover o modo privado** (limpeza).
6. **Externo dirigido na conversa unificada:** confirmar o canal externo (cliente/arquiteto) a partir da
   nova UI + roteamento de resposta.

Cada fatia: suíte verde, DEV_LOG + spec atualizados, Vera antes de fechar (área sensível: ciclo + tenancy).
