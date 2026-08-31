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
    orc.desconto_pct = 0.0   # previsibilidade: VAVA contratado == VBVA (sem desconto/custo adicional)
    # limpa resíduo de outros testes deste arquivo (DROP SCHEMA é só por MÓDULO, não por teste —
    # o mesmo projeto/orçamento de `seed` é reaproveitado em todas as funções aqui).
    db.query(app_db.ConciliacaoPeFase).filter_by(projeto_nome=nome).delete()
    db.query(app_db.ArquivoPE).filter_by(projeto_nome=nome).delete()
    db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome).delete()
    db.query(app_db.ProvisaoRegistro).filter(
        app_db.ProvisaoRegistro.orcamento_id == oid).delete(synchronize_session=False)
    db.query(app_db.LogAcaoGerencial).filter_by(projeto_nome=nome).delete()
    conv = (db.query(app_db.Conversa).filter_by(projeto_nome=nome).first()
            if hasattr(app_db, "Conversa") else None)
    if conv is not None:
        db.query(app_db.ConversaMensagem).filter_by(conversa_id=conv.id).delete()
    aditivos_velhos = [a.id for a in db.query(app_db.Aditivo).filter_by(projeto_nome=nome).all()]
    if aditivos_velhos:
        db.query(app_db.AditivoAssinatura).filter(
            app_db.AditivoAssinatura.aditivo_id.in_(aditivos_velhos)).delete(synchronize_session=False)
        db.query(app_db.Aditivo).filter(app_db.Aditivo.id.in_(aditivos_velhos)).delete(synchronize_session=False)
    compls = [o.id for o in db.query(app_db.Orcamento)
              .filter_by(projeto_id=nome, complemento_pe=1).all()]
    if compls:
        # ACHADO-24 (F2-1): desde que o aditivo materializa Recebivel de verdade, a FK
        # recebivel_orcamento_id_fkey passou a bloquear este DELETE se não limpar antes.
        db.query(app_db.Recebivel).filter(
            app_db.Recebivel.orcamento_id.in_(compls)).delete(synchronize_session=False)
        db.query(app_db.OrcamentoAmbiente).filter(
            app_db.OrcamentoAmbiente.orcamento_id.in_(compls)).delete(synchronize_session=False)
        db.query(app_db.Orcamento).filter(app_db.Orcamento.id.in_(compls)).delete(synchronize_session=False)
    parcelas_velhas = [p.id for p in db.query(app_db.ParcelaProjeto).filter_by(projeto_nome=nome).all()]
    if parcelas_velhas:
        db.query(app_db.ParcelaAmbiente).filter(
            app_db.ParcelaAmbiente.parcela_id.in_(parcelas_velhas)).delete(synchronize_session=False)
        db.query(app_db.ParcelaProjeto).filter(
            app_db.ParcelaProjeto.id.in_(parcelas_velhas)).delete(synchronize_session=False)
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
    # 11a/11b/11c concluídas: este arquivo testa a 11d isoladamente (checagem derivada sobre
    # ConciliacaoPeFase), não a ordem do PE — sem isto, mod_ciclo.subfases_pe_pendentes (achado
    # da Vera 2026-08-26, ordem 11a→11b→11c→11d) bloquearia a 11d antes de chegar nas checagens
    # que este arquivo de fato quer exercitar.
    for _cod in ("11a", "11b", "11c"):
        db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo=_cod, status="concluido"))
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    # Assinatura das DUAS partes + data de entrega: exigidas por _contrato_totalmente_assinado
    # pra concluir a AF (8/11d, mesmo gate do PATCH genérico de ciclo, achado 2026-08-14).
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="Loja",
                                     cpf="000.000.000-00", hash_sha256="x"))
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="cliente", nome="Cliente",
                                     cpf="111.222.333-44", hash_sha256="y"))
    proj = db.query(app_db.Projeto).filter_by(nome_safe=nome).first()
    if proj is not None:
        from datetime import datetime as _dt, timedelta as _td
        proj.data_entrega = _dt.utcnow() + _td(days=60)
    db.commit()
    pid = pa.id
    db.close()
    import main as _main
    pdir = os.path.join(_main.PROJETOS_DIR, nome)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "projeto.json"), "w", encoding="utf-8") as f:
        json.dump({"nome_projeto": nome}, f)
    return nome, pid, oid


def _carrega_pe(app_db, nome, pid, cfo_pe, venda_pe=None):
    db = app_db.get_session()
    db.add(app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_pe",
                            valor_atualizado=cfo_pe, valor_venda=venda_pe))
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
    assert body["etapa_status"] == "pendente"
    assert body["motivo_reprovacao"] is None
    assert body["rev2_aprovada"] is False


def test_get_conciliacao_usa_fator_venda_quando_pe_tem_xml_com_venda(http_client_factory, seed, app_db):
    # achado do usuário 2026-08-15: com venda_pe carregado, a tela deve mostrar o MESMO valor que
    # o Complemento vai cobrar de fato (fator VAVA/VBVA), não mais a estimativa CFO×markup médio.
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    c = _login(http_client_factory)

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    amb = body["fases"][0]["ambientes"][0]
    assert amb["diferenca"] == 3000.0          # Δ custo (CFO) — não muda
    assert amb["diferenca_valor_contrato"] == 4000.0   # fator: 84000*(80000/80000) - 80000 = 4000
    # NÃO é mais a estimativa antiga (6000.0 = 3000 * markup 2.0)


def test_decisao_cobrar_bate_com_complemento_gerado_depois(http_client_factory, seed, app_db):
    # fecha o loop do achado do usuário: o valor que o gerente aprova na AF2 deve ser exatamente
    # o valor que o Complemento de Projeto cobra quando gerado — nunca mais dois números diferentes.
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    c = _login(http_client_factory)

    st, body = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                      {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})
    assert st == 200 and body["ok"], body
    valor_decidido = body["decisao"]["valor_aprovado"]

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/fase/none", {})
    assert st == 200 and body["ok"], body
    assert body["resumo"]["total_diferenca"] == valor_decidido == 4000.0


def test_get_conciliacao_expoe_status_reprovado_com_motivo(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    c = _login(http_client_factory)
    c.post(f"/api/projetos/{nome}/ciclo/11d/reprovar",
          {"login": "dir_l1", "senha": "senha123", "motivo": "Falta revisar o ambiente X"})

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["ok"], body
    assert body["etapa_status"] == "reprovado"
    assert body["motivo_reprovacao"] == "Falta revisar o ambiente X"


def test_get_conciliacao_expoe_rev2_aprovada(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _registra_venda_baseline(app_db, oid)
    c = _login(http_client_factory)
    _aprova_af1_af2(c, oid)

    st, body = c.get(f"/api/projetos/{nome}/pe/conciliacao")
    assert st == 200 and body["rev2_aprovada"] is True


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


# ── POST /pe/complemento/fase/<parcela_id|none> ─────────────────────────────────────────────

def _decide_cobrar(c, nome, pid):
    st, body = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                      {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})
    assert st == 200 and body["ok"], body


def test_complemento_fase_none_projeto_nao_desmembrado(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    c = _login(http_client_factory)
    _decide_cobrar(c, nome, pid)

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/fase/none", {})
    assert st == 200 and body["ok"], body
    assert body["resumo"]["total_complemento"] == 84000.0   # fator 1.0 (sem desconto/custo ad.)
    assert body["resumo"]["total_diferenca"] == 4000.0      # 84000 - 80000

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, body["orcamento"]["id"])
    assert orc.complemento_pe == 1 and orc.parcela_id is None
    ambs = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all()
    assert {a.pool_ambiente_id for a in ambs} == {pid}
    db.close()


def test_complemento_fase_sem_decisao_cobrar_400(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    c = _login(http_client_factory)
    # decisão NUNCA registrada

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/fase/none", {})
    assert st == 400 and not body["ok"]


def test_complemento_fase_por_parcela_nao_colide_com_legado(http_client_factory, seed, app_db):
    """Um complemento por FASE (parcela_id=X) e o mecanismo legado (parcela_id=None) são
    Orcamento DIFERENTES — a query de cada endpoint nunca pega o do outro."""
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    c = _login(http_client_factory)
    _decide_cobrar(c, nome, pid)

    db = app_db.get_session()
    parcela = app_db.ParcelaProjeto(projeto_nome=nome, ordem=1, status="aguardando")
    db.add(parcela); db.flush()
    db.add(app_db.ParcelaAmbiente(parcela_id=parcela.id, pool_ambiente_id=pid, valor_ambiente=80000.0))
    db.commit()
    parcela_id = parcela.id
    db.close()

    # decisão do ambiente foi registrada ANTES da fase existir (parcela_id fica None nela) —
    # o complemento por fase, filtrando por parcela_id=X, não deve achar nada.
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/fase/{parcela_id}", {})
    assert st == 400 and not body["ok"], body

    # o legado (fase "none") continua funcionando normalmente
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/fase/none", {})
    assert st == 200 and body["ok"], body
    orc_legado_id = body["orcamento"]["id"]

    db = app_db.get_session()
    n = db.query(app_db.Orcamento).filter_by(projeto_id=nome, complemento_pe=1).count()
    assert n == 1   # só o legado existe — a chamada por parcela falhou antes de criar nada
    orc = db.get(app_db.Orcamento, orc_legado_id)
    assert orc.parcela_id is None
    db.close()


def test_complemento_fase_registrado_apos_desmembrar(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    db = app_db.get_session()
    parcela = app_db.ParcelaProjeto(projeto_nome=nome, ordem=1, status="aguardando")
    db.add(parcela); db.flush()
    db.add(app_db.ParcelaAmbiente(parcela_id=parcela.id, pool_ambiente_id=pid, valor_ambiente=80000.0))
    db.commit()
    parcela_id = parcela.id
    db.close()

    c = _login(http_client_factory)
    _decide_cobrar(c, nome, pid)   # agora a decisão já nasce com parcela_id resolvido

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/fase/{parcela_id}", {})
    assert st == 200 and body["ok"], body
    assert body["resumo"]["total_diferenca"] == 4000.0

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, body["orcamento"]["id"])
    assert orc.parcela_id == parcela_id
    assert "Fase" in orc.nome
    db.close()


# ── Aditivo do complemento por fase — reaproveita o mecanismo já existente (achado Vera 2026-08-12:
# a assinatura completa já constitui provisão contábil; só faltava o /aditivo saber ESCOLHER o
# complemento certo quando há mais de um simultâneo no mesmo projeto) ──────────────────────────

def _add_ambiente_extra(app_db, nome, oid, budget=50000.0, cfo=20000.0):
    """2º ambiente do projeto, fora da fase — pro cenário de 2 complementos simultâneos."""
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(nome="Sala", nome_exibicao="Sala", xml_path="fake/sala.xml",
                             ambientes_json="{}", projeto_id=nome, budget_total=budget, order_total=cfo)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=2))
    db.commit()
    pid2 = pa.id
    db.close()
    return pid2


def test_aditivo_por_parcela_nao_pega_o_complemento_errado(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    pid2 = _add_ambiente_extra(app_db, nome, oid)
    _carrega_pe(app_db, nome, pid2, cfo_pe=22000.0, venda_pe=53000.0)
    c = _login(http_client_factory)

    db = app_db.get_session()
    parcela = app_db.ParcelaProjeto(projeto_nome=nome, ordem=1, status="aguardando")
    db.add(parcela); db.flush()
    db.add(app_db.ParcelaAmbiente(parcela_id=parcela.id, pool_ambiente_id=pid, valor_ambiente=80000.0))
    db.commit()
    parcela_id = parcela.id
    db.close()
    _decide_cobrar(c, nome, pid)    # ambiente DA FASE → decisão nasce com parcela_id resolvido
    _decide_cobrar(c, nome, pid2)   # ambiente FORA da fase → decisão nasce com parcela_id=None

    # cria os DOIS complementos no mesmo projeto: o legado (fase "none", pega só pid2) e o por fase (só pid)
    st, body_legado = c.post(f"/api/projetos/{nome}/pe/complemento/fase/none", {})
    assert st == 200 and body_legado["ok"], body_legado
    orc_legado_id = body_legado["orcamento"]["id"]

    st, body_fase = c.post(f"/api/projetos/{nome}/pe/complemento/fase/{parcela_id}", {})
    assert st == 200 and body_fase["ok"], body_fase
    orc_fase_id = body_fase["orcamento"]["id"]
    assert orc_fase_id != orc_legado_id

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()

    # pedindo o aditivo DA FASE explicitamente — tem que amarrar no complemento da fase, não no legado
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"parcela_id": parcela_id})
    assert st == 200 and body["ok"], body
    db = app_db.get_session()
    aditivo = db.get(app_db.Aditivo, body["aditivo"]["id"])
    assert aditivo.orcamento_complemento_id == orc_fase_id
    db.close()


def test_aditivo_da_fase_assinatura_completa_constitui_provisao(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0, budget=80000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0, venda_pe=84000.0)
    c = _login(http_client_factory)

    db = app_db.get_session()
    parcela = app_db.ParcelaProjeto(projeto_nome=nome, ordem=1, status="aguardando")
    db.add(parcela); db.flush()
    db.add(app_db.ParcelaAmbiente(parcela_id=parcela.id, pool_ambiente_id=pid, valor_ambiente=80000.0))
    db.commit()
    parcela_id = parcela.id
    db.close()
    _decide_cobrar(c, nome, pid)   # decide DEPOIS da fase existir → parcela_id já resolvido

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/fase/{parcela_id}", {})
    assert st == 200 and body["ok"], body

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"parcela_id": parcela_id})
    assert st == 200 and body["ok"], body
    aditivo_id = body["aditivo"]["id"]

    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "loja", "nome": "Rep Loja", "cpf": "111.444.777-35"})
    assert st == 200 and body["status"] == "assinado_loja", body
    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "cliente", "nome": "Cliente L1", "cpf": "222.333.444-05",
                       "forma_pagamento": json.dumps({"tipo": "avista", "entrada_valor": 1.0})})
    assert st == 200 and body["status"] == "assinado", body

    import mod_contabil
    db = app_db.get_session()
    ot, owner_id = mod_contabil.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    novos = (db.query(app_db.Lancamento)
               .filter_by(owner_tipo=ot, owner_id=owner_id, projeto_id=nome)
               .filter(app_db.Lancamento.ref.like("prov:aditivo:%d:%%" % aditivo_id)).all())
    db.close()
    assert len(novos) > 0, "assinatura completa do aditivo da FASE deveria constituir provisão(ões)"


# ── Defesa em profundidade: o PATCH genérico /ciclo/<codigo> também respeita fase_completa ──────
# pode_avancar('11d') sobe pra etapa-mãe '11', que exige a PRINCIPAL anterior ('10') concluída —
# atalho de seed direto (mesmo padrão já usado em test_complemento_pe_e2e.py) pra não montar o
# ciclo inteiro só pra provar que o PATCH genérico respeita a checagem nova.
def _seed_etapas_ate_10(app_db, nome):
    db = app_db.get_session()
    for cod in ("1", "2", "3", "4", "7", "9", "10"):
        if db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo=cod).first() is None:
            db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo=cod, status="concluido"))
    db.commit(); db.close()


def test_patch_generico_ciclo_11d_tambem_bloqueia_decisao_faltante(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    _registra_venda_baseline(app_db, oid)
    c = _login(http_client_factory)
    _aprova_af1_af2(c, oid)
    _seed_etapas_ate_10(app_db, nome)
    # decisão do ambiente NUNCA foi registrada — nem pelo endpoint dedicado, nem pelo genérico

    st, body = c.patch(f"/api/projetos/{nome}/ciclo/11d",
                       {"status": "concluido", "login": "dir_l1", "senha": "senha123"})
    assert st == 400 and "ambiente" in body["erro"], body

    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="11d").first()
    assert et is None or et.status != "concluido"
    db.close()


def test_patch_generico_ciclo_11d_conclui_com_fase_completa(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    _registra_venda_baseline(app_db, oid)
    c = _login(http_client_factory)
    _aprova_af1_af2(c, oid)
    _seed_etapas_ate_10(app_db, nome)
    _decide_cobrar(c, nome, pid)

    st, body = c.patch(f"/api/projetos/{nome}/ciclo/11d",
                       {"status": "concluido", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body

    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="11d").first()
    assert et is not None and et.status == "concluido"
    db.close()
