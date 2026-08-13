# tests/test_desconto_autorizacao_e2e.py
"""Regressão do achado UAT 2026-08-10/11 (bateria da Vera): `/margens` e `/descontos` gravavam
qualquer desconto_pct sem checar `usuario.limite_desconto` — a autorização gerencial (modal de
login/senha) era só decoração de UI, sem trava nenhuma no servidor. Qualquer Operador conseguia
persistir um desconto acima do seu limite direto via rede, sem senha de gerente nenhuma."""


def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


def _reset_orc_descontos(app_db, oid):
    """`seed` é module-scoped: testes anteriores acumulam desconto_pct/individual no MESMO
    orçamento. Os testes de composição precisam de estado limpo pra não herdar desconto de teste
    anterior no cálculo do efetivo composto."""
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.desconto_pct = 0.0
    for lk in db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
        lk.desconto_individual_pct = 0.0
    db.commit()
    db.close()


# ── Desconto global (/api/orcamentos/<id>/margens) ───────────────────────────
def test_margens_recusa_desconto_acima_do_limite_sem_autorizacao(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%
    oid = seed["orcamento_l1_id"]

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 25})
    assert st == 403
    assert body["requer_autorizacao"] is True
    assert body["limite"] == 10.0

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) != 25   # NÃO persistiu
    db.close()


def test_margens_aceita_dentro_do_proprio_limite(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%
    oid = seed["orcamento_l1_id"]

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 8})
    assert st == 200
    assert body["ok"] is True

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert orc.desconto_pct == 8
    db.close()


def test_margens_aceita_acima_do_limite_com_autorizador_valido(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%
    oid = seed["orcamento_l1_id"]

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {
        "desconto_pct": 25,
        "login_autorizador": "dir_l1", "senha_autorizador": "senha123",   # master, limite 50%
    })
    assert st == 200
    assert body["ok"] is True

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert orc.desconto_pct == 25
    log = (db.query(app_db.LogAutorizacao)
             .filter_by(desconto_solicit=25).order_by(app_db.LogAutorizacao.id.desc()).first())
    assert log is not None and log.autorizado == 1
    db.close()


def test_margens_recusa_autorizador_cuja_senha_esta_errada(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "cons_l1")
    oid = seed["orcamento_l1_id"]

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {
        "desconto_pct": 25,
        "login_autorizador": "dir_l1", "senha_autorizador": "senha_errada",
    })
    assert st == 403
    assert body["requer_autorizacao"] is True


def test_margens_recusa_autorizador_com_limite_insuficiente(http_client_factory, seed, app_db):
    # cons_l1 pede pra OUTRO operador (limite 10% também) autorizar 25% — não cobre.
    c = _login(http_client_factory, "cons_l1")
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    u2 = app_db.Usuario(nome="Outro Operador", login="op2_l1", nivel="operador",
                        loja_id=seed["loja1_id"], ativo=1)
    u2.set_senha("senha123")
    db.add(u2); db.commit(); db.close()

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {
        "desconto_pct": 25,
        "login_autorizador": "op2_l1", "senha_autorizador": "senha123",
    })
    assert st == 403
    assert body["requer_autorizacao"] is True


def test_margens_sessao_do_proprio_diretor_dispensa_autorizador(http_client_factory, seed, app_db):
    # Sessão-primeiro: quem já tem limite suficiente não precisa mandar login/senha de novo.
    c = _login(http_client_factory, "dir_l1")   # master, limite 50%
    oid = seed["orcamento_l1_id"]

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 25})
    assert st == 200
    assert body["ok"] is True


# ── Descontos individuais por ambiente (/api/orcamentos/<id>/descontos) ──────
def test_descontos_individuais_recusa_acima_do_limite_sem_autorizacao(http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = seed["loja1_id"]
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="a", nome_exibicao="Cozinha",
                             xml_path="x", ambientes_json="[]", order_total=1000.0, budget_total=2000.0)
    db.add(pa); db.flush()
    oid = seed["orcamento_l1_id"]
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    pa_id = pa.id
    db.close()

    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%
    st, body = c.put(f"/api/orcamentos/{oid}/descontos", {"descontos": {str(pa_id): 30}})
    assert st == 403
    assert body["requer_autorizacao"] is True

    db = app_db.get_session()
    link = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid, pool_ambiente_id=pa_id).first()
    assert (link.desconto_individual_pct or 0) != 30   # NÃO persistiu
    db.close()


def test_descontos_individuais_aceita_com_autorizador_valido(http_client_factory, seed, app_db):
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="b", nome_exibicao="Quarto",
                             xml_path="y", ambientes_json="[]", order_total=1000.0, budget_total=2000.0)
    db.add(pa); db.flush()
    oid = seed["orcamento_l1_id"]
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    pa_id = pa.id
    db.close()

    c = _login(http_client_factory, "cons_l1")
    st, body = c.put(f"/api/orcamentos/{oid}/descontos", {
        "descontos": {str(pa_id): 30},
        "login_autorizador": "dir_l1", "senha_autorizador": "senha123",
    })
    assert st == 200
    assert body["ok"] is True

    db = app_db.get_session()
    link = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid, pool_ambiente_id=pa_id).first()
    assert link.desconto_individual_pct == 30
    db.close()


# ── Composição global × individual (achado Vera 2026-08-12) ─────────────────
# Cada campo isolado respeitava o limite (45% ≤ 50%), mas o efeito composto
# (1-0.55)*(1-0.55) = 69,75% de desconto real furava o teto do próprio Diretor.
def test_composicao_global_individual_bloqueada_mesmo_dentro_do_limite_isolado(
        http_client_factory, seed, app_db):
    _reset_orc_descontos(app_db, seed["orcamento_l1_id"])
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="c", nome_exibicao="Suíte",
                             xml_path="z", ambientes_json="[]", order_total=1000.0, budget_total=2000.0)
    db.add(pa); db.flush()
    oid = seed["orcamento_l1_id"]
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    pa_id = pa.id
    db.close()

    c = _login(http_client_factory, "dir_l1")   # master, limite 50%

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 45})
    assert st == 200 and body["ok"] is True   # isolado, dentro do limite

    st, body = c.put(f"/api/orcamentos/{oid}/descontos", {"descontos": {str(pa_id): 45}})
    assert st == 403   # composto (69,75%) fura o limite — precisa ser bloqueado
    assert body["requer_autorizacao"] is True

    db = app_db.get_session()
    link = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid, pool_ambiente_id=pa_id).first()
    assert (link.desconto_individual_pct or 0) != 45   # NÃO persistiu
    db.close()


def test_composicao_bloqueada_na_ordem_inversa_individual_depois_global(http_client_factory, seed, app_db):
    _reset_orc_descontos(app_db, seed["orcamento_l1_id"])
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="d", nome_exibicao="Cozinha 2",
                             xml_path="w", ambientes_json="[]", order_total=1000.0, budget_total=2000.0)
    db.add(pa); db.flush()
    oid = seed["orcamento_l1_id"]
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    pa_id = pa.id
    db.close()

    c = _login(http_client_factory, "dir_l1")   # master, limite 50%

    st, body = c.put(f"/api/orcamentos/{oid}/descontos", {"descontos": {str(pa_id): 45}})
    assert st == 200 and body["ok"] is True   # isolado, dentro do limite

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 45})
    assert st == 403   # composto (69,75%) fura o limite — precisa ser bloqueado
    assert body["requer_autorizacao"] is True

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) != 45   # NÃO persistiu
    db.close()


def test_composicao_pequena_dentro_do_limite_nao_e_bloqueada(http_client_factory, seed, app_db):
    # 5% global + 5% individual → efetivo 9,75%, dentro do limite de 10% do operador. Não pode
    # virar falso-positivo por causa da checagem composta.
    _reset_orc_descontos(app_db, seed["orcamento_l1_id"])
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="e", nome_exibicao="Escritório",
                             xml_path="v", ambientes_json="[]", order_total=1000.0, budget_total=2000.0)
    db.add(pa); db.flush()
    oid = seed["orcamento_l1_id"]
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    pa_id = pa.id
    db.close()

    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 5})
    assert st == 200 and body["ok"] is True

    st, body = c.put(f"/api/orcamentos/{oid}/descontos", {"descontos": {str(pa_id): 5}})
    assert st == 200 and body["ok"] is True

    db = app_db.get_session()
    link = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid, pool_ambiente_id=pa_id).first()
    assert link.desconto_individual_pct == 5
    db.close()
