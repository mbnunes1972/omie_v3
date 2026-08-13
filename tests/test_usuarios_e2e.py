# tests/test_usuarios_e2e.py
# Task 4 — endpoint GET /api/admin/usuarios/perfis-permitidos
# (base para tasks 5-7 também)


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_perfis_permitidos_loja_para_diretor(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id={seed['loja1_id']}")
    assert st == 200 and body["ok"]
    slugs = {p["slug"] for p in body["perfis"]}
    assert "operador" in slugs and "super_admin" not in slugs and "admin_rede" not in slugs


def test_perfis_permitidos_plataforma_so_super(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/admin/usuarios/perfis-permitidos?escopo=plataforma")
    assert st == 200 and [p["slug"] for p in body["perfis"]] == ["super_admin"]
    c2 = _login(http_client_factory, "dir_l1")
    st2, body2 = c2.get("/api/admin/usuarios/perfis-permitidos?escopo=plataforma")
    assert st2 == 200 and body2["perfis"] == []


# Task 5 — filtros de escopo + campos de contato na lista de usuários

def test_lista_escopo_loja_so_da_loja(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    assert st == 200
    logins = {u["login"] for u in body["usuarios"]}
    assert "dir_l1" in logins and "dir_l2" not in logins and "super" not in logins


def test_lista_escopo_plataforma_so_super(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/admin/usuarios?escopo=plataforma")
    assert st == 200
    niveis = {u["nivel"] for u in body["usuarios"]}
    assert niveis == {"super_admin"}


def test_lista_inclui_campos_contato(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    u = body["usuarios"][0]
    assert "email" in u and "cpf" in u and "whatsapp" in u


def test_lista_escopo_gestores_inclui_super_admin_rede_e_master(http_client_factory, seed):
    """Painel Orizon › Gestores (2026-08-08): TODO gestor do sistema — antes 'Gestores gerais'
    só mostrava super_admin (escopo=plataforma). Agora junta os 3 tipos que administram algo."""
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/admin/usuarios?escopo=gestores")
    assert st == 200 and body["ok"], (st, body)
    niveis = {u["nivel"] for u in body["usuarios"]}
    assert niveis == {"super_admin", "admin_rede", "master"}


def test_lista_escopo_gestores_exclusivo_de_gerir_redes(http_client_factory, seed):
    """CPF vaza nesse endpoint — exclusivo de quem tem gerir_redes (só super_admin), mesmo que
    o gestor de rede/diretor de loja também tenham gerir_usuarios."""
    for who in ("adm_rede", "dir_l1"):
        c = _login(http_client_factory, who)
        st, _ = c.get("/api/admin/usuarios?escopo=gestores")
        assert st == 403, (who, st)


def test_override_por_conta_do_gestor_de_rede_bloqueia_endpoint_real(http_client_factory, seed, app_db):
    """Ponta a ponta do achado de 2026-08-08: desligar gerir_usuarios NA CONTA (não no nível) de
    um admin_rede específico precisa realmente bloquear um endpoint gated por essa capacidade —
    sem afetar outros admin_rede (o override é por Usuario, não por nível)."""
    import json
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="adm_rede").first()
    u.capacidades_override_json = json.dumps({"gerir_usuarios": False})
    db.commit()
    db.close()
    try:
        c = _login(http_client_factory, "adm_rede")
        st, _ = c.get("/api/admin/usuarios?escopo=loja&loja_id=%d" % seed["loja1_id"])
        assert st == 403
    finally:
        db = app_db.get_session()
        u = db.query(app_db.Usuario).filter_by(login="adm_rede").first()
        u.capacidades_override_json = None   # não vaza pro resto da suíte (fixture é module-scoped)
        db.commit()
        db.close()


# Task 6 — POST /api/admin/usuarios grava contato e admin_rede cria par

def test_diretor_cria_usuario_loja_com_contato(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Nova Pessoa", "login": "nova1", "senha": "s1", "nivel": "operador",
        "telefone": "1", "whatsapp": "2", "email": "n@p.com", "cpf": "390.533.447-05",
        "loja_id": seed["loja1_id"]})
    assert st == 200 and body["ok"]
    st2, lst = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    novo = next(u for u in lst["usuarios"] if u["login"] == "nova1")
    assert novo["email"] == "n@p.com" and novo["whatsapp"] == "2"


def test_criar_usuario_login_conflitante_devolve_erro_limpo_nao_500(
        http_client_factory, seed, app_db, monkeypatch):
    """Achado de auditoria 2026-08-13 (achado 12): POST /api/admin/usuarios só tinha
    try/finally, sem except — a checagem de login duplicado (`validar_novo_usuario` contra a
    lista de logins lida ANTES do commit) é TOCTOU: uma corrida real (2 requests concorrentes)
    passa pela checagem e um dos dois estoura IntegrityError crua, 500. Simulado aqui via
    monkeypatch da validação (bypassa o check em memória, como a corrida faria na prática) —
    o login já existe de verdade no banco, então o INSERT tem que estourar a constraint mesmo
    assim, e o servidor precisa devolver JSON limpo, não 500."""
    import auth.mod_usuarios as mod_usuarios
    c = _login(http_client_factory, "dir_l1")
    st0, d0 = c.post("/api/admin/usuarios", {
        "nome": "Primeiro", "login": "corrida@loja.com", "senha": "s1", "nivel": "operador",
        "loja_id": seed["loja1_id"]})
    assert st0 == 200 and d0["ok"], d0

    monkeypatch.setattr(mod_usuarios, "validar_novo_usuario", lambda dados, logins: [])
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Segundo (corrida)", "login": "corrida@loja.com", "senha": "s2",
        "nivel": "operador", "loja_id": seed["loja1_id"]})
    assert body.get("ok") is False
    assert st == 409, body
    assert "login" in body.get("erro", "").lower()


def test_admin_rede_cria_par(http_client_factory, seed):
    c = _login(http_client_factory, "adm_rede")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Outro Adm", "login": "adm2", "senha": "s1", "nivel": "admin_rede"})
    assert st == 200 and body["ok"]


def test_diretor_nao_cria_super(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "X", "login": "x9", "senha": "s", "nivel": "super_admin",
        "loja_id": seed["loja1_id"]})
    assert body["ok"] is False


# Task 7 — PATCH: contato, escalonamento admin_rede e anti-lockout

def test_admin_rede_edita_par(http_client_factory, seed, app_db):
    # cria um par admin_rede para editar
    c = _login(http_client_factory, "adm_rede")
    c.post("/api/admin/usuarios", {"nome": "Par", "login": "par1", "senha": "s", "nivel": "admin_rede"})
    db = app_db.get_session()
    pid = db.query(app_db.Usuario).filter_by(login="par1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{pid}", {"telefone": "55", "email": "p@p.com"})
    assert st == 200 and body["ok"]


def test_nao_inativa_a_si_mesmo(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"ativo": False})
    assert body["ok"] is False


def test_nao_rebaixa_proprio_perfil(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"nivel": "consultor"})
    assert body["ok"] is False


def test_diretor_nao_promove_para_admin_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    alvo = db.query(app_db.Usuario).filter_by(login="dir_l2").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{alvo}", {"nivel": "admin_rede"})
    assert body["ok"] is False


def test_admin_rede_nao_promove_para_super(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    db = app_db.get_session()
    id_dir_l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{id_dir_l1}", {"nivel": "super_admin"})
    assert body["ok"] is False


def test_edita_proprio_contato_permitido(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"telefone": "1199", "email": "eu@loja.com"})
    assert body["ok"] is True


def test_perfis_permitidos_super_admin_honra_loja_id(http_client_factory, seed, app_db):
    """Bug 2026-07-22: super_admin (sem loja própria) criando usuário na gestão geral — o
    endpoint deve honrar o loja_id do request e devolver os perfis DAQUELA loja, inclusive
    os customizados (antes ignorava e caía no fallback genérico master/gerencial/operador)."""
    from auth import perfil_store
    db = app_db.get_session()
    perfil_store.seed_perfis_loja(db, seed["loja2_id"])
    p, err = perfil_store.criar_perfil(db, seed["loja2_id"], "Diretor", "master", ["comercial"])
    assert p is not None, err
    db.close()
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id={seed['loja2_id']}")
    assert st == 200 and body["ok"], body
    rotulos = {x["rotulo"] for x in body["perfis"]}
    assert "Diretor" in rotulos, rotulos            # perfil customizado da loja aparece
    slugs = {x["slug"] for x in body["perfis"]}
    assert {"master", "gerencial", "operador"} <= slugs


def test_perfis_permitidos_nao_vaza_loja_fora_do_escopo(http_client_factory, seed, app_db):
    """dir_l1 pedindo os perfis da loja 2 NÃO recebe os customizados de lá — o loja_id só é
    honrado dentro do escopo do ator (super/admin_rede da rede/a própria loja)."""
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id={seed['loja2_id']}")
    assert st == 200 and body["ok"], body
    rotulos = {x["rotulo"] for x in body["perfis"]}
    assert "Diretor" not in rotulos                  # criado no teste anterior, loja 2


def test_super_admin_cria_outro_super_admin(http_client_factory, seed):
    """Pedido 2026-07-22: o Super Admin pode criar outros usuários Super Admin (o botão
    '+ Novo gestor' do Painel Orizon usa escopo=plataforma)."""
    c = _login(http_client_factory, "super")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Segundo Gestor", "login": "super2", "senha": "s1", "nivel": "super_admin"})
    assert st == 200 and body["ok"], body
    st, lst = c.get("/api/admin/usuarios?escopo=plataforma")
    assert any(u["login"] == "super2" for u in lst["usuarios"])


# ── Permissões por CONTA (2026-08-08) — GET/PUT /api/admin/usuarios/<id>/permissoes ─────────

def test_permissoes_get_admin_rede_mostra_padrao_sem_override(http_client_factory, seed, app_db):
    db = app_db.get_session()
    alvo = db.query(app_db.Usuario).filter_by(login="adm_rede").first()
    alvo_id = alvo.id
    db.close()
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios/{alvo_id}/permissoes")
    assert st == 200 and body["ok"], body
    assert body["nivel"] == "admin_rede" and body["editavel"] is True
    assert body["capacidades"] == body["capacidades_padrao"]


def test_permissoes_get_master_nao_editavel(http_client_factory, seed, app_db):
    db = app_db.get_session()
    alvo = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    alvo_id = alvo.id
    db.close()
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios/{alvo_id}/permissoes")
    assert st == 200 and body["ok"] and body["editavel"] is False


def test_permissoes_put_super_admin_grava_e_reflete_em_pode_usuario(http_client_factory, seed, app_db):
    db = app_db.get_session()
    alvo = db.query(app_db.Usuario).filter_by(login="adm_rede").first()
    alvo_id = alvo.id
    db.close()
    c = _login(http_client_factory, "super")
    try:
        st, body = c.put(f"/api/admin/usuarios/{alvo_id}/permissoes",
                         {"capacidades": {"gerir_perfis": True, "gerir_usuarios": False}})
        assert st == 200 and body["ok"], body
        assert body["capacidades"]["gerir_perfis"] is True
        assert body["capacidades"]["gerir_usuarios"] is False
        # a mesma conta perde acesso a um endpoint gated por gerir_usuarios de verdade
        c2 = _login(http_client_factory, "adm_rede")
        st2, _ = c2.get("/api/admin/usuarios?escopo=loja&loja_id=%d" % seed["loja1_id"])
        assert st2 == 403
    finally:
        db = app_db.get_session()
        alvo = db.get(app_db.Usuario, alvo_id)
        alvo.capacidades_override_json = None
        db.commit(); db.close()


def test_permissoes_put_rejeita_capacidade_fora_da_allowlist(http_client_factory, seed, app_db):
    db = app_db.get_session()
    alvo_id = db.query(app_db.Usuario).filter_by(login="adm_rede").first().id
    db.close()
    c = _login(http_client_factory, "super")
    st, body = c.put(f"/api/admin/usuarios/{alvo_id}/permissoes",
                     {"capacidades": {"gerir_lojas": False}})
    assert st == 400 and "gerir_lojas" in body["erro"]


def test_permissoes_put_rejeitado_para_master(http_client_factory, seed, app_db):
    db = app_db.get_session()
    alvo_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    c = _login(http_client_factory, "super")
    st, body = c.put(f"/api/admin/usuarios/{alvo_id}/permissoes",
                     {"capacidades": {"gerir_usuarios": False}})
    assert st == 400


def test_permissoes_diretor_de_loja_nao_acessa(http_client_factory, seed, app_db):
    """dir_l1 (master, sem gerir_redes/gerir_lojas) não enxerga a rota — nem GET nem PUT."""
    db = app_db.get_session()
    alvo_id = db.query(app_db.Usuario).filter_by(login="adm_rede").first().id
    db.close()
    c = _login(http_client_factory, "dir_l1")
    st, _ = c.get(f"/api/admin/usuarios/{alvo_id}/permissoes")
    assert st == 404
    st2, _ = c.put(f"/api/admin/usuarios/{alvo_id}/permissoes", {"capacidades": {}})
    assert st2 == 404
