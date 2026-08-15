"""Conciliação de PE/AF2 por fase — E2E HTTP (spec 2026-08-14).

Fatia 3: decisão por ambiente na AF2 (Manter/Absorver/Cobrar/Estornar), conclusão da 11d
(checagem derivada sobre ConciliacaoPeFase, sem mexer no que a AF1 usa) e auditoria dupla
(LogAcaoGerencial + arquivo JSONL).
"""
import json
import os


def _login(f, who="dir_l1"):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _setup(app_db, seed, cfo_original=30000.0, budget=80000.0):
    """Contrato assinado + 1 ambiente + markup direto no orçamento (bypass do motor completo)."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    orc.markup = 2.0
    # limpa resíduo de outros testes deste arquivo (DROP SCHEMA é só por MÓDULO, não por teste —
    # o mesmo projeto/orçamento de `seed` é reaproveitado em todas as funções aqui).
    db.query(app_db.ConciliacaoPeFase).filter_by(projeto_nome=nome).delete()
    db.query(app_db.ArquivoPE).filter_by(projeto_nome=nome).delete()
    conv = (db.query(app_db.Conversa).filter_by(projeto_nome=nome).first()
            if hasattr(app_db, "Conversa") else None)
    if conv is not None:
        db.query(app_db.ConversaMensagem).filter_by(conversa_id=conv.id).delete()
    velhos = [pa2.id for pa2 in db.query(app_db.PoolAmbiente).filter_by(projeto_id=nome).all()]
    if velhos:
        db.query(app_db.OrcamentoAmbiente).filter(
            app_db.OrcamentoAmbiente.pool_ambiente_id.in_(velhos)).delete(synchronize_session=False)
        db.query(app_db.PoolAmbiente).filter(app_db.PoolAmbiente.id.in_(velhos)).delete(synchronize_session=False)
    db.commit()
    pa = app_db.PoolAmbiente(nome="Cozinha", nome_exibicao="Cozinha", xml_path="fake/coz.xml",
                             ambientes_json="{}", projeto_id=nome,
                             budget_total=budget, order_total=cfo_original)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="Loja",
                                     cpf="000.000.000-00", hash_sha256="x"))
    db.commit()
    pid = pa.id
    db.close()
    import main as _main
    pdir = os.path.join(_main.PROJETOS_DIR, nome)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "projeto.json"), "w", encoding="utf-8") as f:
        json.dump({"nome_projeto": nome}, f)
    return nome, pid, oid


def _carrega_pe(app_db, nome, pid, cfo_pe):
    db = app_db.get_session()
    db.add(app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_pe",
                            valor_atualizado=cfo_pe))
    db.commit(); db.close()


def _aprova_af1_af2(c, oid):
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "concorda", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body
    st, body = c.post("/api/orcamentos/%d/provisoes/rev2" % oid,
                      {"decisao": "concorda", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body


def _registra_venda_baseline(app_db, oid):
    import main
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    main._registrar_provisao_venda(db, orc, por_id=1)
    db.commit(); db.close()


# ── GET /pe/conciliacao ────────────────────────────────────────────────────────────────────

def test_get_conciliacao_mostra_diferenca_e_sem_decisao(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)   # custo subiu 3000
    c = _login(http_client_factory)

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    assert body["markup"] == 2.0
    fase = body["fases"][0]
    assert fase["parcela_id"] is None
    amb = fase["ambientes"][0]
    assert amb["diferenca"] == 3000.0
    assert amb["diferenca_valor_contrato"] == 6000.0   # 3000 * markup 2.0
    assert amb["decisao"] is None
    assert fase["completa"] is False
    assert fase["faltam"] == [pid]


# ── POST /pe/conciliacao/<pool_ambiente_id> ────────────────────────────────────────────────

def test_post_conciliacao_cobrar_custo_subiu(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    c = _login(http_client_factory)

    st, body = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                      {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})
    assert st == 200 and body["ok"], body
    assert body["decisao"]["tipo_decisao"] == "cobrar"
    assert body["decisao"]["valor_aprovado"] == 6000.0

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    fase = body["fases"][0]
    assert fase["ambientes"][0]["decisao"] == {"tipo_decisao": "cobrar", "valor_aprovado": 6000.0}
    assert fase["completa"] is True


def test_post_conciliacao_decisao_incompativel_com_sinal_400(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)   # custo SUBIU — estornar não é válido aqui
    c = _login(http_client_factory)

    st, body = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                      {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "estornar"})
    assert st == 400 and not body["ok"]


def test_post_conciliacao_estornar_lanca_credito_imediato(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=27000.0)   # custo caiu 3000 → estornar é válido
    c = _login(http_client_factory)

    st, body = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                      {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "estornar",
                       "valor_aprovado": 5000.0})
    assert st == 200 and body["ok"], body
    assert body["decisao"]["valor_aprovado"] == 5000.0   # valor editado pelo gerente, não o calculado

    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid_c = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    assert mc.saldo_credito_cliente(db, ot, oid_c, nome) == 5000.0
    db.close()


def test_post_conciliacao_registra_auditoria_dupla(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    c = _login(http_client_factory)
    c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
          {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "absorver"})

    db = app_db.get_session()
    log = db.query(app_db.LogAcaoGerencial).filter_by(
        projeto_nome=nome, acao="pe_conciliacao_absorver").first()
    assert log is not None
    db.close()

    import main
    caminho = os.path.join(main.PROJETOS_DIR, nome, "conciliacao_pe", "auditoria.jsonl")
    assert os.path.exists(caminho)
    with open(caminho, encoding="utf-8") as f:
        linhas = [json.loads(l) for l in f if l.strip()]
    assert any(l["tipo_decisao"] == "absorver" and l["pool_ambiente_id"] == pid for l in linhas)


def test_post_conciliacao_pe_nao_carregado_400(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    # NÃO carrega PE pro ambiente
    c = _login(http_client_factory)
    st, body = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                      {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "manter"})
    assert st == 400 and not body["ok"]


# ── POST /ciclo/11d/aprovar ─────────────────────────────────────────────────────────────────

def test_11d_concluir_bloqueia_sem_rev2(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    c = _login(http_client_factory)
    c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
          {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})

    st, body = c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 400 and "Revisão de Provisões" in body["erro"]


def test_11d_concluir_bloqueia_decisao_faltante(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    _registra_venda_baseline(app_db, oid)
    c = _login(http_client_factory)
    _aprova_af1_af2(c, oid)
    # decisão do ambiente NUNCA foi registrada

    st, body = c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 400 and pid in body["faltam"]


def test_11d_concluir_sucesso_marca_ciclo_etapa(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    _registra_venda_baseline(app_db, oid)
    c = _login(http_client_factory)
    _aprova_af1_af2(c, oid)
    c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
          {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})

    st, body = c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body

    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="11d").first()
    assert et is not None and et.status == "concluido"
    log = db.query(app_db.LogAcaoGerencial).filter_by(
        projeto_nome=nome, acao="pe_11d_aprovar").first()
    assert log is not None
    db.close()


def test_11d_aprovar_notifica_no_chat_do_projeto(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    _registra_venda_baseline(app_db, oid)
    c = _login(http_client_factory)
    _aprova_af1_af2(c, oid)
    c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
          {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})
    c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar", {"login": "dir_l1", "senha": "senha123"})

    db = app_db.get_session()
    import mod_chat
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], nome)
    msgs = db.query(app_db.ConversaMensagem).filter_by(
        conversa_id=conv.id, evento="pe_af2_aprovada").all()
    assert len(msgs) == 1 and "aprovada" in msgs[0].corpo
    db.close()


# ── POST /ciclo/11d/reprovar ────────────────────────────────────────────────────────────────

def test_11d_reprovar_exige_motivo(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    c = _login(http_client_factory)
    st, body = c.post(f"/api/projetos/{nome}/ciclo/11d/reprovar",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 400 and not body["ok"]


def test_11d_reprovar_marca_status_e_notifica(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    c = _login(http_client_factory)
    c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
          {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})

    st, body = c.post(f"/api/projetos/{nome}/ciclo/11d/reprovar",
                      {"login": "dir_l1", "senha": "senha123",
                       "motivo": "Valor do Complemento parece alto, revisar o XML do ambiente"})
    assert st == 200 and body["ok"], body

    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="11d").first()
    assert et is not None and et.status == "reprovado"
    assert et.status not in __import__("mod_ciclo").STATUS_CONCLUSIVOS   # não satisfaz gate nenhum
    log = db.query(app_db.LogAcaoGerencial).filter_by(
        projeto_nome=nome, acao="pe_11d_reprovar").first()
    assert log is not None and "Valor do Complemento" in log.contexto

    import mod_chat
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], nome)
    msgs = db.query(app_db.ConversaMensagem).filter_by(
        conversa_id=conv.id, evento="pe_af2_reprovada").all()
    assert len(msgs) == 1 and "revisar o XML" in msgs[0].corpo
    db.close()
