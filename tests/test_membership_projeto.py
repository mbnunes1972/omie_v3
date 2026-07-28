# -*- coding: utf-8 -*-
"""Conversa do Projeto — membership derivada + override manual (spec
conversa-projeto-no-orizon-chat, 2026-07-27). A conversa `tipo=projeto` sincroniza seus
participantes com a equipe derivada; adição/remoção manual do gerente PREVALECEM."""
import mod_chat
from database import Conversa, ConversaParticipante


def _users(app_db, *logins):
    db = app_db.get_session()
    try:
        return [db.query(app_db.Usuario).filter_by(login=l).first().id for l in logins]
    finally:
        db.close()


def _conv_proj(app_db, seed, nome):
    db = app_db.get_session()
    try:
        c = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], nome)
        db.commit(); return c.id
    finally:
        db.close()


def _sync(app_db, conv_id, membros):
    db = app_db.get_session()
    try:
        res = mod_chat.sincronizar_participantes_projeto(db, db.get(Conversa, conv_id), membros)
        db.commit(); return res
    finally:
        db.close()


def _parts(app_db, conv_id):
    db = app_db.get_session()
    try:
        return {(p.usuario_id, p.origem, p.removido) for p in
                db.query(ConversaParticipante).filter_by(conversa_id=conv_id).all()}
    finally:
        db.close()


def test_sync_adiciona_derivados_como_auto(app_db, seed):
    a, b = _users(app_db, "dir_l1", "cons_l1")
    cid = _conv_proj(app_db, seed, "MP_add")
    assert set(_sync(app_db, cid, [a, b])) == {a, b}
    assert _parts(app_db, cid) == {(a, "auto", 0), (b, "auto", 0)}


def test_sync_remove_auto_que_saiu_do_time(app_db, seed):
    a, b = _users(app_db, "dir_l1", "cons_l1")
    cid = _conv_proj(app_db, seed, "MP_rem")
    _sync(app_db, cid, [a, b])
    assert set(_sync(app_db, cid, [a])) == {a}
    assert _parts(app_db, cid) == {(a, "auto", 0)}


def test_remocao_manual_prevalece(app_db, seed):
    (a,) = _users(app_db, "dir_l1")
    cid = _conv_proj(app_db, seed, "MP_manrem")
    _sync(app_db, cid, [a])
    db = app_db.get_session()                          # simula remoção manual (tombstone)
    try:
        p = db.query(ConversaParticipante).filter_by(conversa_id=cid, usuario_id=a).first()
        p.removido = 1; db.commit()
    finally:
        db.close()
    _sync(app_db, cid, [a])                             # a segue derivado, mas removido manual
    assert _parts(app_db, cid) == {(a, "auto", 1)}      # NÃO readiciona
    db = app_db.get_session()
    try:
        assert mod_chat.eh_participante(db, cid, a) is False
    finally:
        db.close()


def test_adicao_manual_fica(app_db, seed):
    a, b = _users(app_db, "dir_l1", "cons_l1")
    cid = _conv_proj(app_db, seed, "MP_manadd")
    db = app_db.get_session()                          # b entra à mão (não é da equipe)
    try:
        db.add(ConversaParticipante(conversa_id=cid, usuario_id=b, papel="membro",
                                    origem="manual", removido=0)); db.commit()
    finally:
        db.close()
    _sync(app_db, cid, [a])                             # só a derivado
    assert _parts(app_db, cid) == {(a, "auto", 0), (b, "manual", 0)}


def test_gerencia_participa_por_padrao(app_db, seed):
    """Diretor/Gerente participam de TODA conversa de projeto por padrão, mesmo fora da equipe
    derivada (decisão do lojista 2026-07-27)."""
    (ger,) = _users(app_db, "dir_l1")                  # master = gerência
    (op,) = _users(app_db, "cons_l1")                  # operador (não gerência)
    cid = _conv_proj(app_db, seed, "MP_ger")
    res = _sync(app_db, cid, [op])                     # sincroniza só com o operador
    assert ger in res and op in res                    # gerência entra sozinha
    db = app_db.get_session()
    try:
        assert mod_chat.eh_participante(db, cid, ger) is True
    finally:
        db.close()


def test_gerencia_pode_se_autoexcluir(app_db, seed):
    """A gerência é auto, mas a remoção manual (tombstone) prevalece — o sync não readiciona."""
    (ger,) = _users(app_db, "dir_l1")
    cid = _conv_proj(app_db, seed, "MP_gerrem")
    _sync(app_db, cid, [])                             # gerência entra
    db = app_db.get_session()
    try:
        p = db.query(ConversaParticipante).filter_by(conversa_id=cid, usuario_id=ger).first()
        p.removido = 1; db.commit()
    finally:
        db.close()
    _sync(app_db, cid, [])                             # não readiciona
    db = app_db.get_session()
    try:
        assert mod_chat.eh_participante(db, cid, ger) is False
    finally:
        db.close()


def test_listar_participantes_traz_funcao_e_gerencia(app_db, seed):
    """A lista de membros identifica a FUNÇÃO (cargo) e sinaliza a gerência (p/ a tabela do modal)."""
    (ger,) = _users(app_db, "dir_l1")
    cid = _conv_proj(app_db, seed, "MP_lp")
    _sync(app_db, cid, [])
    db = app_db.get_session()
    try:
        parts = mod_chat.listar_participantes(db, db.get(Conversa, cid))
    finally:
        db.close()
    row = [p for p in parts if p["usuario_id"] == ger][0]
    assert row["gerencia"] is True and "funcao_nome" in row


def test_inbox_inclui_conversa_projeto(app_db, seed):
    (a,) = _users(app_db, "dir_l1")
    cid = _conv_proj(app_db, seed, "MP_inbox")
    _sync(app_db, cid, [a])
    db = app_db.get_session()
    try:
        itens = mod_chat.listar_inbox(db, seed["loja1_id"], a)
    finally:
        db.close()
    proj = [x for x in itens if x["id"] == cid]
    assert proj and proj[0]["tipo"] == "projeto" and proj[0]["titulo"].startswith("📁")


# ── endpoints: assunto=projeto abre a conversa + override manual ────────────────

def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_conversa_projeto_respeita_escopo_projetista(http_client_factory, app_db, seed):
    """Achado da Vera 🔴: os endpoints da conversa do projeto aplicam o escopo por projetista
    (Consultor só vê os que criou), não só a loja — leitura E escrita barram fora do escopo (404).
    Usa projeto PRÓPRIO (não muta o Proj_L1 compartilhado do seed)."""
    db = app_db.get_session()
    try:
        u = app_db.Usuario(nome="Consultor B", login="cons_l1_b", nivel="operador",
                           loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("senha123"); db.add(u)
        dono = db.query(app_db.Usuario).filter_by(login="cons_l1").first().id
        db.add(app_db.Projeto(nome_safe="Proj_Esc", loja_id=seed["loja1_id"],
                              status="fechado", criado_por_id=dono))
        db.commit()
    finally:
        db.close()
    intruso = http_client_factory(); intruso.login("cons_l1_b", "senha123")
    assert intruso.get("/api/projetos/Proj_Esc/conversa")[0] == 404          # não lê a conversa
    assert intruso.post("/api/projetos/Proj_Esc/conversa/mensagens", {"corpo": "intruso"})[0] == 404
    dono_c = http_client_factory(); dono_c.login("cons_l1", "senha123")      # o criador acessa
    assert dono_c.get("/api/projetos/Proj_Esc/conversa")[0] == 200


def test_assunto_projeto_abre_conversa_do_projeto(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post("/api/comunicacao/conversas",
                   {"assunto_tipo": "projeto", "projeto_nome": "Proj_L1"})
    assert st == 201 and b["conversa"]["tipo"] == "projeto"
    assert b["conversa"]["projeto_nome"] == "Proj_L1"
    cid = b["conversa"]["id"]
    b2 = c.post("/api/comunicacao/conversas",
                {"assunto_tipo": "projeto", "projeto_nome": "Proj_L1"})[1]
    assert b2["conversa"]["id"] == cid                        # get-or-create


def test_override_manual_add_remove_e_permissao(http_client_factory, app_db, seed):
    c = _login(http_client_factory, "dir_l1")
    cid = c.post("/api/comunicacao/conversas",
                 {"assunto_tipo": "projeto", "projeto_nome": "Proj_L1"})[1]["conversa"]["id"]
    (alvo,) = _users(app_db, "cons_l1")
    st, b = c.post("/api/comunicacao/conversas/%d/participantes" % cid,
                   {"usuario_id": alvo, "acao": "add"})
    assert st == 200 and any(p["usuario_id"] == alvo and p["origem"] == "manual"
                             for p in b["participantes"])
    st, b = c.post("/api/comunicacao/conversas/%d/participantes" % cid,
                   {"usuario_id": alvo, "acao": "remove"})
    assert st == 200 and alvo not in [p["usuario_id"] for p in b["participantes"]]
    # operador não pode gerir membros
    op = _login(http_client_factory, "cons_l1")
    assert op.post("/api/comunicacao/conversas/%d/participantes" % cid,
                   {"usuario_id": alvo, "acao": "add"})[0] == 403


def test_get_participantes(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    cid = c.post("/api/comunicacao/conversas",
                 {"assunto_tipo": "projeto", "projeto_nome": "Proj_L1"})[1]["conversa"]["id"]
    st, b = c.get("/api/comunicacao/conversas/%d/participantes" % cid)
    assert st == 200 and b["pode_gerir"] is True and isinstance(b["participantes"], list)
