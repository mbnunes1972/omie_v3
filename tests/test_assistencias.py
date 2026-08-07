import mod_assistencias as ma
import mod_contabil as mc


# ── Mapeamento motivo -> tipo de custo (tabela do doc) ───────────────────────
def test_motivo_deriva_tipo_custo():
    assert ma.tipo_custo_de("alteracao_projeto") == "paga"
    assert ma.tipo_custo_de("complemento") == "paga"
    assert ma.tipo_custo_de("erro_projeto") == "loja"
    assert ma.tipo_custo_de("erro_montagem") == "loja"
    assert ma.tipo_custo_de("defeito_fabricacao") == "fabrica"
    assert ma.tipo_custo_de("empenamento") == "fabrica"
    assert ma.tipo_custo_de("xpto") is None


# ── Motor de lançamento: cada tipo de custo posta no razão certo (v7 §6) ─────
def _saldo(db, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, "loja", oid, c.id) if c else 0.0


def _nova_loja_e_usuario(app_db, db, tag):
    """AssistenciaCaso.loja_id e .criado_por_id são FK reais (lojas/usuarios) — cria as duas
    linhas de verdade em vez de literais fabricados (Postgres valida FK; SQLite não)."""
    loja = app_db.Loja(nome="Loja Assist %s" % tag)
    db.add(loja); db.flush()
    u = app_db.Usuario(nome="User Assist %s" % tag, login="assist_%s" % tag, nivel="operador",
                       loja_id=loja.id, ativo=1)
    u.set_senha("senha123")
    db.add(u); db.flush()
    return loja.id, u.id


def test_realizar_loja_baixa_provisao_assistencia(app_db):
    db = app_db.get_session()
    loja_id, usuario_id = _nova_loja_e_usuario(app_db, db, "1")
    mc.seed_plano(db, "loja", loja_id)
    caso = ma.criar_caso(db, loja_id, None, "montagem", "erro_montagem", "x", 300.0, usuario_id)
    ok, err = ma.realizar_caso(db, "loja", loja_id, caso)
    assert ok, err
    # Débito 2.1.04.05 (baixa provisão assist. técnica) -> saldo do passivo cai 300
    assert _saldo(db, loja_id, "2.1.04.05") == -300.0
    assert caso.status == "realizado"
    db.close()


def test_realizar_fabrica_baixa_provisao_garantia(app_db):
    db = app_db.get_session()
    loja_id, usuario_id = _nova_loja_e_usuario(app_db, db, "2")
    mc.seed_plano(db, "loja", loja_id)
    caso = ma.criar_caso(db, loja_id, None, "pos_conclusao", "defeito_fabricacao", "x", 500.0, usuario_id)
    assert caso.tipo_custo == "fabrica"
    ma.realizar_caso(db, "loja", loja_id, caso)
    assert _saldo(db, loja_id, "2.1.04.03") == -500.0        # provisão de garantia baixada
    rel = ma.a_cobrar_fabrica(db, loja_id)
    assert rel["total"] == 500.0 and rel["qtd"] == 1     # entra no "a cobrar da fábrica"
    db.close()


def test_realizar_paga_gera_venda_sem_provisao(app_db):
    db = app_db.get_session()
    loja_id, usuario_id = _nova_loja_e_usuario(app_db, db, "3")
    mc.seed_plano(db, "loja", loja_id)
    caso = ma.criar_caso(db, loja_id, None, "montagem", "complemento", "x", 250.0, usuario_id)
    assert caso.tipo_custo == "paga"
    ma.realizar_caso(db, "loja", loja_id, caso)
    assert _saldo(db, loja_id, "1.1.02") == 250.0             # Contas a Receber
    assert _saldo(db, loja_id, "4.1.02") == 250.0             # Receita com Vendas de Assistência
    assert ma.a_cobrar_fabrica(db, loja_id)["total"] == 0.0   # Paga não entra no repasse da fábrica
    db.close()


def test_realizar_loja_reconhece_despesa_na_competencia_real(app_db):
    """2026-08-07: realizar um caso Loja/Fábrica também reconhece a despesa formal (baixa do ativo
    diferido), na competência REAL do atendimento — não mais estimada de uma vez na NF-e. Cenário
    realista: a provisão nasce na venda (constituir_provisoes_fechamento) ANTES do caso ser aberto."""
    db = app_db.get_session()
    loja_id, usuario_id = _nova_loja_e_usuario(app_db, db, "5")
    mc.seed_plano(db, "loja", loja_id)
    mc.constituir_provisoes_fechamento(db, "loja", loja_id, "Proj5", {"assistencia": 1000.0}, ref_base="pf:Proj5")
    caso = ma.criar_caso(db, loja_id, "Proj5", "pos_conclusao", "erro_montagem", "x", 300.0, usuario_id)
    ok, err = ma.realizar_caso(db, "loja", loja_id, caso)
    assert ok, err
    assert _saldo(db, loja_id, "5.2.13") == 300.0        # despesa formal reconhecida (Assistência Técnica)
    assert _saldo(db, loja_id, "1.1.06.05") == 700.0     # ativo diferido baixado só na proporção efetivada
    assert _saldo(db, loja_id, "2.1.04.05") == 700.0     # provisão sobrevive (700 ainda em aberto)
    db.close()


def test_realizar_idempotente(app_db):
    db = app_db.get_session()
    loja_id, usuario_id = _nova_loja_e_usuario(app_db, db, "4")
    mc.seed_plano(db, "loja", loja_id)
    caso = ma.criar_caso(db, loja_id, None, "montagem", "erro_projeto", "x", 100.0, usuario_id)
    ma.realizar_caso(db, "loja", loja_id, caso)
    ma.realizar_caso(db, "loja", loja_id, caso)               # 2ª vez não duplica
    assert _saldo(db, loja_id, "2.1.04.05") == -100.0
    db.close()


# ── HTTP: criar/listar/realizar via endpoints ────────────────────────────────
def test_endpoints_criar_listar_realizar(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/assistencias/casos", {"sub_tipo": "montagem", "motivo": "defeito_fabricacao",
                                               "descricao": "porta empenou", "valor": 400})
    assert st == 201 and d["tipo_custo"] == "fabrica", d
    cid = d["id"]
    st, lst = c.get("/api/assistencias/casos")
    assert st == 200
    assert any(x["id"] == cid and x["tipo_custo_label"] == "Fábrica" for x in lst["casos"])
    assert lst["a_cobrar_fabrica"]["total"] == 400
    assert {m["id"] for m in lst["meta"]["motivos"]} >= {"erro_montagem", "defeito_fabricacao"}
    st, _ = c.post("/api/assistencias/casos/%d/realizar" % cid, {})
    assert st == 200
    _, lst2 = c.get("/api/assistencias/casos?tipo=fabrica")
    assert next(x for x in lst2["casos"] if x["id"] == cid)["status"] == "realizado"


def test_caso_de_outra_loja_nao_realiza(http_client_factory, seed, app_db):
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    _, d = c1.post("/api/assistencias/casos", {"sub_tipo": "montagem", "motivo": "erro_projeto", "valor": 50})
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    st, _ = c2.post("/api/assistencias/casos/%d/realizar" % d["id"], {})
    assert st == 404
