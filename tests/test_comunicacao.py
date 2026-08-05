# -*- coding: utf-8 -*-
"""Central de Comunicação — Fatia 1 (núcleo interno), spec
docs/superpowers/specs/_geral/2026-07-27-central-comunicacao-omnichannel-design.md.

Escopo DESTA fatia: conversa `direct` (1:1, idempotente pela dupla) e `grupo` (N + título),
inbox por usuário, envio/listagem de mensagens com auth por participante, seletor de usuários
da loja e segmento derivado da função. Tenancy: nada cruza loja. FORA: público, não-lidos,
anexos, ponte WhatsApp (fatias 2-4)."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _uid(app_db, login):
    db = app_db.get_session()
    try:
        return db.query(app_db.Usuario).filter_by(login=login).first().id
    finally:
        db.close()


# ── direct ────────────────────────────────────────────────────────────────────

def test_criar_direct_idempotente(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": alvo})
    assert st == 201 and b["ok"], b
    assert b["conversa"]["tipo"] == "direct"
    cid = b["conversa"]["id"]
    st, b2 = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": alvo})
    assert st == 201 and b2["conversa"]["id"] == cid          # não duplica a dupla


def test_direct_consigo_mesmo_400(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    eu = _uid(app_db, "dir_l1")
    st, b = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": eu})
    assert st == 400 and b["ok"] is False


def test_direct_com_usuario_de_outra_loja_400(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    outro = _uid(app_db, "dir_l2")                            # loja 2
    st, b = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": outro})
    assert st == 400 and b["ok"] is False                     # não vaza entre lojas


# ── grupo ───────────────────────────────────────────────────────────────────--

def test_criar_grupo(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"tipo": "grupo", "titulo": "Equipe Obra", "participante_ids": [alvo]})
    assert st == 201 and b["conversa"]["tipo"] == "grupo"
    assert b["conversa"]["titulo"] == "Equipe Obra"


def test_grupo_sem_titulo_400(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"tipo": "grupo", "titulo": "  ", "participante_ids": [alvo]})
    assert st == 400 and b["ok"] is False


def test_gerir_membros_de_grupo(http_client_factory, app_db, seed):
    """F1 (unificação): add/remover membro vale para GRUPO (antes só projeto). Gerência gere;
    operador 403; loja 2 não enxerga (404)."""
    ger = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = ger.post("/api/comunicacao/conversas",
                   {"tipo": "grupo", "titulo": "Grupo F1", "participante_ids": [alvo]})[1]["conversa"]["id"]
    # gerência adiciona e remove membro no GRUPO
    st, b = ger.post("/api/comunicacao/conversas/%d/participantes" % cid, {"usuario_id": alvo, "acao": "remove"})
    assert st == 200 and alvo not in [p["usuario_id"] for p in b["participantes"]]
    st, b = ger.post("/api/comunicacao/conversas/%d/participantes" % cid, {"usuario_id": alvo, "acao": "add"})
    assert st == 200 and any(p["usuario_id"] == alvo for p in b["participantes"])
    # operador não gere membros
    op = _login(http_client_factory, "cons_l1")
    assert op.post("/api/comunicacao/conversas/%d/participantes" % cid, {"usuario_id": alvo, "acao": "add"})[0] == 403
    # loja 2 não enxerga o grupo da loja 1
    outro = _login(http_client_factory, "dir_l2")
    assert outro.post("/api/comunicacao/conversas/%d/participantes" % cid, {"usuario_id": alvo, "acao": "add"})[0] == 404


def test_participante_externo_e_espelho(app_db, seed):
    """Contato EXTERNO (WhatsApp) entra na conversa (destacado) e as mensagens ESPELHAM — config-gated:
    sem credencial Meta o envio nasce 'pendente_config' (a rede não é tocada)."""
    import mod_chat, mod_chat_externo
    from database import EnvioExterno
    db = app_db.get_session()
    try:
        crid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        mid = db.query(app_db.Usuario).filter_by(login="cons_l1").first().id
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G ext", [mid]); db.flush()
        e = mod_chat.adicionar_externo(db, conv, "Arquiteto João", telefone="11912345678"); db.commit()
        ext = [p for p in mod_chat.listar_participantes(db, conv) if p.get("externo")]
        assert ext and ext[0]["nome"] == "Arquiteto João" and ext[0]["meio"] == "whatsapp"
        msg = mod_chat.enviar_mensagem(db, conv, crid, "olá arquiteto"); db.flush()
        ids = mod_chat_externo.espelhar_para_externos(db, conv, msg, autor_nome="Diretor"); db.commit()
        assert len(ids) == 1
        env = db.get(EnvioExterno, ids[0])
        assert env.status == "pendente_config" and env.meio == "whatsapp" and "11912345678" in (env.destino or "")
        assert mod_chat.remover_externo(db, conv, e.id) is True; db.commit()
        assert not [p for p in mod_chat.listar_participantes(db, conv) if p.get("externo")]
    finally:
        db.close()


def test_endpoint_criar_grupo_com_externo(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"tipo": "grupo", "titulo": "Obra X", "participante_ids": [alvo],
                    "externos": [{"nome": "Cliente Ana", "telefone": "11999998888", "meio": "whatsapp"}]})
    assert st == 201, b
    cid = b["conversa"]["id"]
    st, b = c.post("/api/comunicacao/conversas/%d/participantes" % cid,
                   {"acao": "add_externo", "nome": "Arq Beto", "telefone": "1188887777"})
    assert st == 200 and sum(1 for p in b["participantes"] if p.get("externo")) == 2


def test_mensagem_dirigida_a_um_membro(http_client_factory, app_db, seed):
    """F2: mensagem 'para um membro' grava/serializa o destinatário (marcação visual — todos leem);
    sem destinatário = todos (None)."""
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = c.post("/api/comunicacao/conversas",
                 {"tipo": "grupo", "titulo": "G dest", "participante_ids": [alvo]})[1]["conversa"]["id"]
    # dirigida ao alvo
    st, _ = c.post("/api/comunicacao/conversas/%d/mensagens" % cid,
                   {"corpo": "confirma?", "destinatario_usuario_id": alvo})
    assert st == 201
    # sem destinatário = todos
    c.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "geral"})
    st, b = c.get("/api/comunicacao/conversas/%d/mensagens" % cid)
    msgs = {m["corpo"]: m for m in b["mensagens"]}
    assert msgs["confirma?"]["destinatario_usuario_id"] == alvo
    assert msgs["confirma?"]["destinatario_nome"]   # nome resolvido p/ o "→ para"
    assert msgs["geral"]["destinatario_usuario_id"] is None


def test_destinatario_deve_ser_participante(http_client_factory, app_db, seed):
    """Achado da Vera 🟠: destinatário dirigido só vale se for PARTICIPANTE; id de outra loja/não-membro
    é ignorado (vira 'todos'), não vaza '→ para <nome>'."""
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    outro = _uid(app_db, "dir_l2")   # usuário de OUTRA loja, não participante
    cid = c.post("/api/comunicacao/conversas", {"tipo": "grupo", "titulo": "G val", "participante_ids": [alvo]})[1]["conversa"]["id"]
    c.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "x", "destinatario_usuario_id": outro})
    c.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "y", "destinatario_usuario_id": alvo})
    msgs = {m["corpo"]: m for m in c.get("/api/comunicacao/conversas/%d/mensagens" % cid)[1]["mensagens"]}
    assert msgs["x"]["destinatario_usuario_id"] is None and msgs["x"]["destinatario_nome"] == ""  # não-membro ignorado
    assert msgs["y"]["destinatario_usuario_id"] == alvo                                            # membro aceito


def test_endpoint_individual_externo_vira_grupo(http_client_factory, app_db, seed):
    """Individual só com contato externo → cria conversa (grupo) com o criador + o externo."""
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"tipo": "direct", "participante_ids": [],
                    "externos": [{"nome": "Cliente Zé", "telefone": "11970001122", "meio": "whatsapp"}]})
    assert st == 201 and b["conversa"]["tipo"] == "grupo", b


# ── mensagens + auth por participante ──────────────────────────────────────────

def test_enviar_e_listar(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    st, b = dono.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "olá"})
    assert st == 201 and b["mensagem"]["corpo"] == "olá", b
    # o outro participante lê
    outro = _login(http_client_factory, "cons_l1")
    st, b = outro.get("/api/comunicacao/conversas/%d/mensagens" % cid)
    assert st == 200 and [m["corpo"] for m in b["mensagens"]] == ["olá"]


def test_nao_participante_nao_le_nem_posta(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    # 3º usuário da MESMA loja, mas fora da conversa
    db = app_db.get_session()
    u = app_db.Usuario(nome="Fulano L1", login="fulano_l1", nivel="operador",
                       loja_id=seed["loja1_id"], ativo=1)
    u.set_senha("senha123"); db.add(u); db.commit(); db.close()
    terceiro = _login(http_client_factory, "fulano_l1")
    assert terceiro.get("/api/comunicacao/conversas/%d/mensagens" % cid)[0] == 404
    assert terceiro.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "x"})[0] == 404


def test_conversa_de_outra_loja_404(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    forasteiro = _login(http_client_factory, "dir_l2")
    assert forasteiro.get("/api/comunicacao/conversas/%d/mensagens" % cid)[0] == 404


# ── inbox ──────────────────────────────────────────────────────────────────────

def test_inbox_lista_conversas_do_usuario(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    dono.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "oi inbox"})
    st, b = dono.get("/api/comunicacao/inbox")
    assert st == 200 and b["ok"]
    achou = [x for x in b["conversas"] if x["id"] == cid]
    assert achou and achou[0]["ultima_previa"] == "oi inbox"
    # direct: o título mostrado é o nome do OUTRO
    assert achou[0]["titulo"] == "Consultor L1"


# ── seletor de usuários da loja ────────────────────────────────────────────────

def test_usuarios_da_loja_exclui_o_proprio(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    st, b = c.get("/api/comunicacao/usuarios")
    assert st == 200 and b["ok"]
    logins_nomes = [u["nome"] for u in b["usuarios"]]
    assert "Consultor L1" in logins_nomes
    assert "Diretor L1" not in logins_nomes                   # não se lista
    assert "Diretor L2" not in logins_nomes                   # outra loja não aparece


# ── segmento derivado da função ────────────────────────────────────────────────

def test_canal_segmento_vem_da_funcao(http_client_factory, app_db, seed):
    # dá a cons_l1 uma função "Financeiro" na loja 1
    db = app_db.get_session()
    fn = app_db.Funcao(nome="Financeiro", loja_id=seed["loja1_id"])
    db.add(fn); db.flush()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.funcao_id = fn.id
    db.commit(); db.close()

    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    autor = _login(http_client_factory, "cons_l1")
    st, b = autor.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "fin"})
    assert st == 201 and b["mensagem"]["canal_segmento"] == "financeiro", b


# ── Fatia 2: assunto ────────────────────────────────────────────────────────--

def test_criar_e_listar_assunto(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post("/api/comunicacao/assuntos", {"nome": "Marketing"})
    assert st == 201 and b["assunto"]["nome"] == "Marketing", b
    st, b = c.get("/api/comunicacao/assuntos")
    assert st == 200 and b["ok"]
    assert "Marketing" in [a["nome"] for a in b["assuntos"]]
    assert "Proj_L1" in [p["nome_safe"] for p in b["projetos"]]   # projetos entram no seletor


def test_assunto_projeto_abre_a_conversa_do_projeto(http_client_factory, app_db, seed):
    # Unificação 2026-07-27: assunto=projeto NÃO cria direct — abre a conversa DO PROJETO.
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"assunto_tipo": "projeto", "projeto_nome": "Proj_L1"})
    assert st == 201, b
    assert b["conversa"]["tipo"] == "projeto"
    assert b["conversa"]["projeto_nome"] == "Proj_L1"


def test_direct_e_canonico_por_assunto(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    livre1 = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    livre2 = c.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    assert livre1 == livre2                                        # mesma dupla+assunto → mesma
    aid = c.post("/api/comunicacao/assuntos", {"nome": "Canonico QA"})[1]["assunto"]["id"]
    custom = c.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo,
                     "assunto_tipo": "custom", "assunto_id": aid})[1]["conversa"]["id"]
    assert custom != livre1                                        # assunto diferente → thread nova


def test_assunto_projeto_de_outra_loja_400(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"tipo": "direct", "usuario_id": alvo,
                    "assunto_tipo": "projeto", "projeto_nome": "Proj_L2"})   # loja 2
    assert st == 400 and b["ok"] is False


# ── Fatia 2: painel admin (ver_todas_conversas) ────────────────────────────────

def test_admin_ve_todas_e_operador_nao(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    dono.post("/api/comunicacao/conversas", {"tipo": "direct", "usuario_id": alvo})
    # master (Diretor) enxerga o painel
    st, b = dono.get("/api/comunicacao/admin/conversas")
    assert st == 200 and b["ok"] and len(b["conversas"]) >= 1
    # operador não
    op = _login(http_client_factory, "cons_l1")
    assert op.get("/api/comunicacao/admin/conversas")[0] == 403


def test_admin_filtra_por_participante(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    st, b = dono.get("/api/comunicacao/admin/conversas?participante=%d" % alvo)
    assert st == 200 and cid in [x["id"] for x in b["conversas"]]


def test_admin_le_conversa_que_nao_participa(http_client_factory, app_db, seed):
    # conversa entre cons_l1 e um 3º usuário da loja (dir_l1 não participa)
    db = app_db.get_session()
    u = app_db.Usuario(nome="Beltrano L1", login="beltrano_l1", nivel="operador",
                       loja_id=seed["loja1_id"], ativo=1)
    u.set_senha("senha123"); db.add(u); db.commit(); uid_b = u.id; db.close()
    autor = _login(http_client_factory, "cons_l1")
    alvo = uid_b
    cid = autor.post("/api/comunicacao/conversas",
                     {"tipo": "direct", "usuario_id": alvo})[1]["conversa"]["id"]
    autor.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "particular"})
    # Diretor (master) NÃO participa, mas lê (oversight)
    diretor = _login(http_client_factory, "dir_l1")
    st, b = diretor.get("/api/comunicacao/conversas/%d/mensagens" % cid)
    assert st == 200 and [m["corpo"] for m in b["mensagens"]] == ["particular"]


# ── Fatia 3/4: MURAL de avisos (por loja, gerência posta, todos leem) ───────────

def _mural_id(client):
    b = client.get("/api/comunicacao/inbox")[1]
    m = [x for x in b["conversas"] if x["tipo"] == "mural"]
    assert m, "mural não veio na inbox"
    return m[0]["id"]


def test_mural_na_inbox_de_todos(http_client_factory, seed):
    for who in ("dir_l1", "cons_l1"):
        c = _login(http_client_factory, who)
        b = c.get("/api/comunicacao/inbox")[1]
        m = [x for x in b["conversas"] if x["tipo"] == "mural"]
        assert m and m[0]["titulo"] == "📣 Mural da loja"


def test_mural_so_gerencia_posta_todos_leem(http_client_factory, seed):
    # operador NÃO posta (403)
    op = _login(http_client_factory, "cons_l1")
    mid = _mural_id(op)
    assert op.post("/api/comunicacao/conversas/%d/mensagens" % mid, {"corpo": "x"})[0] == 403
    # Diretor (master) posta; todos leem
    dir1 = _login(http_client_factory, "dir_l1")
    assert dir1.post("/api/comunicacao/conversas/%d/mensagens" % mid, {"corpo": "aviso oficial"})[0] == 201
    st, b = op.get("/api/comunicacao/conversas/%d/mensagens" % mid)
    assert st == 200 and "aviso oficial" in [m["corpo"] for m in b["mensagens"]]


def test_mural_isolado_por_loja(http_client_factory, seed):
    c1 = _login(http_client_factory, "dir_l1"); m1 = _mural_id(c1)
    c2 = _login(http_client_factory, "dir_l2"); m2 = _mural_id(c2)
    assert m1 != m2
    assert c2.get("/api/comunicacao/conversas/%d/mensagens" % m1)[0] == 404   # não cruza loja


# ── Fatia 4: Fórum da Loja (debates com assunto) ───────────────────────────────

def test_forum_loja_debate_lista_busca_e_posta(http_client_factory, seed):
    dono = _login(http_client_factory, "dir_l1")
    st, b = dono.post("/api/comunicacao/forum",
                      {"escopo": "loja", "titulo": "Reforma da vitrine"})
    assert st == 201, b
    did = b["debate"]["id"]
    # aparece na lista e na busca por título
    st, b = dono.get("/api/comunicacao/forum?escopo=loja&q=vitrine")
    assert st == 200 and did in [x["id"] for x in b["debates"]]
    # qualquer usuário da loja lê e posta
    op = _login(http_client_factory, "cons_l1")
    assert op.post("/api/comunicacao/conversas/%d/mensagens" % did, {"corpo": "boa ideia"})[0] == 201
    st, b = op.get("/api/comunicacao/conversas/%d/mensagens" % did)
    assert st == 200 and "boa ideia" in [m["corpo"] for m in b["mensagens"]]


def test_forum_loja_nao_cruza_loja(http_client_factory, seed):
    dono = _login(http_client_factory, "dir_l1")
    did = dono.post("/api/comunicacao/forum", {"escopo": "loja", "titulo": "Só da L1"})[1]["debate"]["id"]
    outra = _login(http_client_factory, "dir_l2")
    assert outra.get("/api/comunicacao/conversas/%d/mensagens" % did)[0] == 404


# ── Fatia 4: Fórum Orizon (cross-loja pela rede) ───────────────────────────────

def test_forum_orizon_cross_loja_mesma_rede(http_client_factory, seed):
    # dir_l1 (loja1) e dir_l2 (loja2) estão na MESMA rede (seed)
    dono = _login(http_client_factory, "dir_l1")
    st, b = dono.post("/api/comunicacao/forum", {"escopo": "orizon", "titulo": "Compra conjunta"})
    assert st == 201 and b["debate"]["tipo"] == "forum_orizon", b
    did = b["debate"]["id"]
    # loja 2 (mesma rede) VÊ o debate e posta
    outra = _login(http_client_factory, "dir_l2")
    st, b = outra.get("/api/comunicacao/forum?escopo=orizon")
    assert st == 200 and did in [x["id"] for x in b["debates"]]
    assert outra.post("/api/comunicacao/conversas/%d/mensagens" % did, {"corpo": "topo"})[0] == 201


# ── Fatia 3: não-lidos ──────────────────────────────────────────────────────---

def test_nao_lidos_conta_e_zera(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    alvo = _uid(app_db, "cons_l1")
    # assunto próprio → conversa NOVA (isola do estado de outros testes do módulo)
    aid = dono.post("/api/comunicacao/assuntos", {"nome": "NaoLidos QA"})[1]["assunto"]["id"]
    cid = dono.post("/api/comunicacao/conversas",
                    {"tipo": "direct", "usuario_id": alvo,
                     "assunto_tipo": "custom", "assunto_id": aid})[1]["conversa"]["id"]
    dono.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "m1"})
    dono.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "m2"})
    outro = _login(http_client_factory, "cons_l1")
    item = [x for x in outro.get("/api/comunicacao/inbox")[1]["conversas"] if x["id"] == cid][0]
    assert item["nao_lidas"] == 2                                # 2 mensagens do outro
    outro.get("/api/comunicacao/conversas/%d/mensagens" % cid)   # abrir marca como lido
    item = [x for x in outro.get("/api/comunicacao/inbox")[1]["conversas"] if x["id"] == cid][0]
    assert item["nao_lidas"] == 0
    # as PRÓPRIAS mensagens não contam como não-lidas para quem escreveu
    item_dono = [x for x in dono.get("/api/comunicacao/inbox")[1]["conversas"] if x["id"] == cid][0]
    assert item_dono["nao_lidas"] == 0


# ── Fatia 5: anexos (foto/arquivo) ─────────────────────────────────────────────

def _direct_isolado(dono, app_db, nome_assunto):
    aid = dono.post("/api/comunicacao/assuntos", {"nome": nome_assunto})[1]["assunto"]["id"]
    alvo = _uid(app_db, "cons_l1")
    return dono.post("/api/comunicacao/conversas",
                     {"tipo": "direct", "usuario_id": alvo,
                      "assunto_tipo": "custom", "assunto_id": aid})[1]["conversa"]["id"]


def test_anexo_imagem_upload_e_download(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    cid = _direct_isolado(dono, app_db, "Anexo IMG")
    dados = b"\x89PNG\r\n\x1a\n" + b"conteudo-fake-de-imagem"
    st, b = dono.post_multipart("/api/comunicacao/conversas/%d/anexos" % cid,
                                files={"arquivo": ("foto.png", dados)},
                                fields={"corpo": "olha a foto"})
    assert st == 201, b
    anx = b["mensagem"]["anexos"]
    assert len(anx) == 1 and anx[0]["tipo"] == "imagem" and anx[0]["nome"] == "foto.png"
    # download devolve os MESMOS bytes
    st, raw = dono.get(anx[0]["url"])
    assert st == 200 and raw == dados


def test_anexo_arquivo_detecta_tipo(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    cid = _direct_isolado(dono, app_db, "Anexo DOC")
    st, b = dono.post_multipart("/api/comunicacao/conversas/%d/anexos" % cid,
                                files={"arquivo": ("contrato.pdf", b"%PDF-1.4 fake")})
    assert st == 201 and b["mensagem"]["anexos"][0]["tipo"] == "arquivo"   # corpo vazio ok
    assert b["mensagem"]["corpo"] == ""


def test_anexo_aparece_na_listagem(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    cid = _direct_isolado(dono, app_db, "Anexo LISTA")
    dono.post_multipart("/api/comunicacao/conversas/%d/anexos" % cid,
                        files={"arquivo": ("nota.txt", b"abc")}, fields={"corpo": "segue"})
    st, b = dono.get("/api/comunicacao/conversas/%d/mensagens" % cid)
    m = b["mensagens"][-1]
    assert m["anexos"] and m["anexos"][0]["nome"] == "nota.txt"


def test_anexo_nao_participante_bloqueado(http_client_factory, app_db, seed):
    dono = _login(http_client_factory, "dir_l1")
    cid = _direct_isolado(dono, app_db, "Anexo PRIV")
    _, b = dono.post_multipart("/api/comunicacao/conversas/%d/anexos" % cid,
                               files={"arquivo": ("x.png", b"\x89PNG data")})
    url = b["mensagem"]["anexos"][0]["url"]
    # terceiro da loja, fora da conversa: nem baixa nem sobe
    db = app_db.get_session()
    if not db.query(app_db.Usuario).filter_by(login="anx_terceiro").first():
        u = app_db.Usuario(nome="Anx Terceiro", login="anx_terceiro", nivel="operador",
                           loja_id=seed["loja1_id"], ativo=1); u.set_senha("senha123")
        db.add(u); db.commit()
    db.close()
    terc = _login(http_client_factory, "anx_terceiro")
    assert terc.get(url)[0] == 404
    assert terc.post_multipart("/api/comunicacao/conversas/%d/anexos" % cid,
                               files={"arquivo": ("y.png", b"data")})[0] == 404


# ── auth ────────────────────────────────────────────────────────────────────---

def test_inbox_exige_login(http_client_factory, seed):
    c = http_client_factory()
    assert c.get("/api/comunicacao/inbox")[0] == 401
