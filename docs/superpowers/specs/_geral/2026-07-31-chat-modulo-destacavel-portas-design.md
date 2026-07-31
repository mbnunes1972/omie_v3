# Orizon Chat — acoplamento ao ciclo por eventos e módulo destacável com portas (design)

**Data:** 2026-07-31 · **Status:** aprovado para implementação (orientação 2026-07-31) ·
**Evolui:** `_geral/2026-07-27-conversa-projeto-no-orizon-chat-design.md` (grupos evolutivos,
documento oficial) e conversa com o plano Motor 5.0
(`_geral/2026-07-16-motor-5-reestruturacao-app-design.md`).

## Demanda

Duas frentes que se completam:

**(a) O diferencial do Orizon Chat sobre um chat genérico é o ciclo do projeto** — a conversa
acompanha as fases, o grupo evolui com a equipe, documentos do ciclo circulam nela. O embrião
existe (`mensagem_passagem_fase`, decisões 16-19; transferência aditiva; `sincronizar_participantes_projeto`);
falta formalizar como EVENTOS visíveis na timeline.

**(b) Decisão do Marcelo: o chat vira módulo destacável, vendável separadamente.** Conversa
direto com o Motor 5.0 (`app/modules/*`) e com o padrão de empacotamento em uso
(`fiscal/`, `integracoes/`, `auth/`).

## Decisões

1. **Grupos de acompanhamento evolutivos:** a conversa do projeto é UMA só, atravessando as
   fases; a cada transição, a composição do grupo evolui (entra o montador na fase de montagem
   etc.). A rotina `sincronizar_grupo_da_fase(db, conversa, fase)` formaliza o que hoje só
   acontece no get-or-create de `abrirConversaProjeto` — disparada pela transição de fase, e
   **cada entrada/saída de membro vira evento inline** ("João (Montador) entrou no
   acompanhamento — fase Montagem"). Override manual segue vencendo (tombstone `removido=1`).
2. **Registro de documentos na conversa:** documento anexado ao ciclo (`CicloDocumento`) pode
   ser registrado como evento na conversa do projeto ("Contrato assinado registrado na etapa 7
   — [abrir]"). A infra existe (`documento_ref_id` + seletor `conv-transf-doc`); generaliza-se
   para fora da transferência.
3. **Encaminhamento de documento ao cliente externo:** enviar um `CicloDocumento` pelo WhatsApp
   da conversa — dentro da janela de 24h como mídia; fora, template + link. Gera `EnvioExterno`
   e evento inline. (Depende da F3 — envio por template — para o ramo "fora da janela"; o ramo
   dentro-da-janela pode nascer antes.)
4. **Eventos inline são MENSAGENS de sistema**, não uma entidade nova: `ConversaMensagem` ganha
   `evento` (String(24), NULL) — `membro_entrou` | `membro_saiu` | `fase_transicao` |
   `documento_registrado` | `documento_encaminhado` | `triagem_vinculo`. Autor NULL + `evento`
   preenchido = faixa de evento no render (não balão). Reusa TODA a infra (ordem, leitura,
   tenancy); transferência/passagem de fase seguem como estão (natureza=transferencia já é
   evento por natureza).
5. **Roteamento pós-transição garantido por teste:** cliente manda mensagem → fase muda,
   responsável muda → cliente manda de novo → cai na MESMA conversa, notificando o responsável
   atual (`rotear_entrada` casa por número, não por funcionário — o teste TRAVA isso). A
   transição de fase não interfere na `janela_da_conversa` (teste também).
6. **Empacotamento `chat/`:** `mod_chat.py` + `mod_chat_externo.py` + triagem →
   `chat/core.py`, `chat/externo.py`, `chat/triagem.py`, `chat/ports.py` (+ `chat/__init__.py`
   reexportando a API). ⚠️ Armadilha documentada: caminho relativo a `__file__` dentro de
   pacote — subir um nível; `test_caminhos_de_pacote.py` é o ratchet. Shims `mod_chat.py`/
   `mod_chat_externo.py` na raiz (reexport) durante a transição, para não quebrar os ~15
   pontos de import de `main.py`/testes de uma vez — removidos ao fim da frente.
7. **Portas em vez de imports diretos do host.** O pacote `chat/` NÃO importa `mod_ciclo`,
   `mod_equipe`, models de Projeto etc. `chat/ports.py` define o contrato pequeno que o host
   implementa e injeta:
   - `IdentityPort` — usuários, permissões (`perfis.pode`), presença;
   - `TenancyPort` — escopo loja/rede (`mod_tenancy.escopo_operacional`);
   - `AssuntoPort` — o "assunto" âncora da conversa como referência genérica
     `(tipo, id, título)`. No OrizonOne o assunto é o Projeto; num cliente externo do módulo
     pode ser pedido/ticket/OS — é isso que torna o produto vendável fora;
   - `EventosPort` — pub/sub in-process simples (sem broker): o host emite `fase_alterada`,
     `responsavel_alterado`, `documento_anexado` e o chat consome (atualiza grupo via decisão
     1, registra evento via decisão 4); o chat emite `mensagem_recebida`, `triagem_pendente`,
     `atendimento_concluido` e o host consome se quiser;
   - `StoragePort` — anexos; `NotifyPort` — e-mail.
   O acoplamento ao ciclo (decisões 1-3) nasce JÁ pendurado no `EventosPort` — o gancho da
   transição de fase no host emite o evento; o chat reage. Nada de import cruzado novo.
8. **Ratchet de arquitetura ANTES de fechar a frente** (senão o desacoplamento regride em três
   commits): `test_arquitetura_modulos` ganha o teste que proíbe import de módulos do host
   dentro de `chat/` (fora de `chat/ports.py` e dos adaptadores registrados pelo host).
   Estado herdado documentado como exceção transitória se necessário — mas o alvo é zero.
9. **Frontend:** o `static/index.html` (17k linhas) não se destaca agora. O passo realista:
   telas do chat num **bloco contíguo e demarcado** (spec de unificação, decisão 7), sem
   referências cruzadas além de pontos de entrada explícitos. Extração física = Motor 5.0.
10. **Migrações:** coluna nova `conversa_mensagens.evento` entra no bloco CHAT demarcado de
    `_migrar_colunas_pg`; tabelas novas do chat idem (comentário `— CHAT —` delimita o schema
    do módulo, preparando o isolamento). Alembic nomeado fica gated pelo baseline (pendente,
    CLAUDE.md) — mesma nota da spec de triagem.

## 1) Sequência de execução

1. Decisão 4 (coluna `evento` + render de faixa) — pré-requisito das demais.
2. Decisões 1-2 (sincronizar_grupo_da_fase + registro de documento) penduradas em `EventosPort`
   (o gancho no host pode, na 1ª fatia, chamar o barramento diretamente do endpoint de
   transição — vira adapter depois).
3. Decisão 5 (testes de roteamento pós-transição).
4. Decisões 6-7 (pacote + portas) — mecânica, com suíte verde a cada passo.
5. Decisão 8 (ratchet) — obrigatória antes do fechamento.
6. Decisão 3 (encaminhamento externo) — o ramo fora-da-janela pode ficar pendente junto da F3.

## Riscos e pontos de atenção

- `main.py` importa `mod_chat`/`mod_chat_externo` em ~15 pontos (grep) — os shims da decisão 6
  evitam um big-bang; o ratchet só endurece depois que os shims somem.
- `test_arquitetura_modulos` detecta pacotes automaticamente (`PACOTES_LOCAIS`) e expande os
  .py internos — `chat/` precisa ser classificado em `modulos.py` (senão o teste de órfãos
  quebra: é o comportamento desejado).
- `_status_transporte_whatsapp` importa `mod_chat_externo` de dentro de `mod_chat` — no pacote
  vira import relativo (`from . import externo`).
- O `EventosPort` é in-process e síncrono; handlers precisam ser best-effort (evento nunca
  derruba a transição de fase — mesmo padrão do espelhamento externo).
