"""Recebimento de Venda (2026-08-07, achado da Vera): `recebimento_venda` era chave morta em
mod_contabil.EVENTOS — nada dava baixa em Contas a Receber (1.1.02). Cobre a materialização pura
(mod_recebiveis.materializar) por ramo de pagamento, o motor de confirmação
(mod_contabil.registrar_recebimento_venda) e os endpoints HTTP (confirmar + previstos no
fluxo-caixa)."""
import json
from datetime import date

import mod_contabil as mc
import mod_recebiveis as mr


# ── mod_recebiveis.materializar (puro) ──────────────────────────────────────────

def _pag(tipo, entrada_valor=0.0, entrada_data="", parcelas=None):
    import json
    return json.dumps({"tipo": tipo, "entrada_valor": entrada_valor, "entrada_data": entrada_data,
                       "parcelas": parcelas or []})


def test_avista_entrada_mais_saldo():
    pag = _pag("avista", entrada_valor=3000.0, entrada_data="2026-08-01",
               parcelas=[{"num": 1, "data": "2026-08-15", "valor": 7000.0, "forma": "pix"}])
    linhas = mr.materializar(pag, 10000.0, date(2026, 8, 1), "receb:1")
    assert [l["tipo"] for l in linhas] == ["entrada", "parcela"]
    assert linhas[0]["valor_previsto"] == 3000.0
    assert linhas[0]["data_prevista"] == date(2026, 8, 1)
    assert linhas[1]["valor_previsto"] == 7000.0
    assert linhas[1]["data_prevista"] == date(2026, 8, 15)
    assert round(sum(l["valor_previsto"] for l in linhas), 2) == 10000.0   # bate com Val_Cont
    assert linhas[0]["ref"] == "receb:1:e" and linhas[1]["ref"] == "receb:1:p1"


def test_venda_programada_por_parcela_data_br():
    # datas no formato DD/MM/AAAA (como mod_fin/venda_programada devolve antes do frontend serializar)
    pag = _pag("vp", entrada_valor=0.0, parcelas=[
        {"num": 1, "data": "10/09/2026", "valor": 5000.0, "forma": "boleto"},
        {"num": 2, "data": "10/10/2026", "valor": 5000.0, "forma": "boleto"},
    ])
    linhas = mr.materializar(pag, 10000.0, date(2026, 8, 1), "receb:2")
    assert len(linhas) == 2
    assert linhas[0]["data_prevista"] == date(2026, 9, 10)
    assert linhas[1]["data_prevista"] == date(2026, 10, 10)
    assert round(sum(l["valor_previsto"] for l in linhas), 2) == 10000.0


def test_total_flex_usa_valor_de_face_das_parcelas():
    # decisão do usuário 2026-08-07: TF mostra o valor de face (capital+juros), sem split
    pag = _pag("tf", entrada_valor=2000.0, entrada_data="2026-08-01", parcelas=[
        {"num": 1, "data": "2026-09-01", "valor": 4200.0, "forma": "boleto"},
        {"num": 2, "data": "2026-10-01", "valor": 4200.0, "forma": "boleto"},
    ])
    linhas = mr.materializar(pag, 10000.0, date(2026, 8, 1), "receb:3")
    # soma > Val_Cont (10000) porque as parcelas do TF embutem juros — esperado, documentado
    assert round(sum(l["valor_previsto"] for l in linhas), 2) == 10400.0


def test_cartao_lump_sum_com_prazo_de_antecipacao():
    pag = _pag("cartao", entrada_valor=1000.0, entrada_data="2026-08-01",
               parcelas=[{"num": 1, "data": "", "valor": 9927.0, "forma": "cartao_credito"}])
    linhas = mr.materializar(pag, 10000.0, date(2026, 8, 1), "receb:4",
                             prazo_antecipacao={"cartao": 3, "aymore": 5})
    assert [l["tipo"] for l in linhas] == ["entrada", "financiado"]
    assert linhas[1]["valor_previsto"] == 9000.0                   # Val_Cont - entrada, NÃO a parcela com juros
    assert linhas[1]["data_prevista"] == date(2026, 8, 4)           # +3 dias
    assert round(sum(l["valor_previsto"] for l in linhas), 2) == 10000.0


def test_aymore_lump_sum_default_prazo():
    pag = _pag("aymore", entrada_valor=0.0, parcelas=[{"num": 1, "valor": 1200.0}])
    linhas = mr.materializar(pag, 10000.0, date(2026, 8, 1), "receb:5")   # sem config → fallback
    assert len(linhas) == 1
    assert linhas[0]["tipo"] == "financiado"
    assert linhas[0]["valor_previsto"] == 10000.0
    assert linhas[0]["data_prevista"] == date(2026, 8, 3)           # fallback aymore = 2 dias


def test_sem_entrada_e_parcela_zerada_e_omitida():
    pag = _pag("vp", entrada_valor=0.0, parcelas=[{"num": 1, "valor": 0.0}, {"num": 2, "valor": 5000.0}])
    linhas = mr.materializar(pag, 5000.0, date(2026, 8, 1), "receb:6")
    assert len(linhas) == 1
    assert linhas[0]["valor_previsto"] == 5000.0


def test_json_vazio_ou_invalido_vira_avista_sem_linhas():
    assert mr.materializar("", 0.0, date(2026, 8, 1), "receb:7") == []
    assert mr.materializar("não é json", 1000.0, date(2026, 8, 1), "receb:8") == []


# ── mod_contabil.registrar_recebimento_venda ────────────────────────────────────

def _saldo(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_registrar_recebimento_baixa_contas_a_receber(app_db):
    db = app_db.get_session(); ot, oid = "loja", 700; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 10000.0, projeto_id="P", ref="venda:P")
    lan = mc.registrar_recebimento_venda(db, ot, oid, "P", 3000.0, ref="recv:P:1")
    assert lan is not None
    assert _saldo(db, ot, oid, "1.1.01") == 3000.0    # Caixa entrou
    assert _saldo(db, ot, oid, "1.1.02") == 7000.0    # Contas a Receber baixou (era 10000)
    db.close()


def test_registrar_recebimento_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 701; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 5000.0, projeto_id="P", ref="venda:P")
    mc.registrar_recebimento_venda(db, ot, oid, "P", 2000.0, ref="recv:P:1")
    mc.registrar_recebimento_venda(db, ot, oid, "P", 2000.0, ref="recv:P:1")   # 2ª vez, mesmo ref
    assert _saldo(db, ot, oid, "1.1.01") == 2000.0    # não duplicou
    db.close()


def test_registrar_recebimento_capa_ao_saldo_em_aberto(app_db):
    """Protege o razão mesmo com um valor 'previsto' otimista (caso do Total Flex, que mistura
    capital+juros na parcela) — nunca deixa Contas a Receber ficar negativa."""
    db = app_db.get_session(); ot, oid = "loja", 702; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 1000.0, projeto_id="P", ref="venda:P")
    lan = mc.registrar_recebimento_venda(db, ot, oid, "P", 5000.0, ref="recv:P:1")   # pede 5000, só há 1000
    assert lan["valor"] == 1000.0
    assert _saldo(db, ot, oid, "1.1.02") == 0.0
    db.close()


def test_registrar_recebimento_valor_zero_nao_lanca(app_db):
    db = app_db.get_session(); ot, oid = "loja", 703; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 1000.0, projeto_id="P", ref="venda:P")
    assert mc.registrar_recebimento_venda(db, ot, oid, "P", 0.0, ref="recv:P:1") is None
    assert _saldo(db, ot, oid, "1.1.02") == 1000.0
    db.close()


def test_registrar_recebimento_nao_toca_recebivel_de_juros(app_db):
    """Não pode duplicar a apropriação de juros do ramo loja (1.1.07/apropriar_juros_loja) —
    registrar_recebimento_venda só mexe em 1.1.01/1.1.02."""
    db = app_db.get_session(); ot, oid = "loja", 704; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 1000.0, projeto_id="P", ref="venda:P")
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 200.0, projeto_id="P", ref="cj:P")
    mc.registrar_recebimento_venda(db, ot, oid, "P", 1000.0, ref="recv:P:1")
    assert _saldo(db, ot, oid, "1.1.07") == 200.0     # recebível de juros intocado
    db.close()


# ── HTTP: confirmar + previstos no fluxo-caixa ──────────────────────────────────

def _criar_recebivel_com_saldo(app_db, seed, tag, valor=4000.0, data_prevista=None):
    """Monta um Recebivel 'previsto' com Contas a Receber já constituída no MESMO owner que o
    handler HTTP resolve (mod_contabil.resolver_owner({"loja_id": loja1_id, "rede_id": None})).
    `tag` deve ser único por chamada (o banco é module-scoped — refs colidiriam entre testes)."""
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", valor, projeto_id=seed["projeto_l1"],
                        ref="venda:%s:%s" % (seed["projeto_l1"], tag))
    rec = app_db.Recebivel(loja_id=seed["loja1_id"], projeto_nome=seed["projeto_l1"],
                           orcamento_id=seed["orcamento_l1_id"], tipo="parcela", numero=1,
                           forma="pix", valor_previsto=valor,
                           data_prevista=data_prevista or date.today(), status="previsto",
                           ref="recv:http:%s:%s" % (seed["projeto_l1"], tag))
    db.add(rec); db.commit()
    rid = rec.id
    db.close()
    return rid


def test_confirmar_recebivel_http(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t1", valor=4000.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/recebiveis/%d/confirmar" % rid, {})
    assert st == 200 and d["ok"] is True, d
    assert d["recebivel"]["status"] == "confirmado"
    assert d["recebivel"]["valor_confirmado"] == 4000.0
    # segunda confirmação → 409
    st2, d2 = c.post("/api/recebiveis/%d/confirmar" % rid, {})
    assert st2 == 409 and d2["ok"] is False


def test_confirmar_recebivel_valor_override(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t2", valor=6000.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/recebiveis/%d/confirmar" % rid, {"valor": 2500.0})
    assert st == 200 and d["ok"] is True, d
    assert d["recebivel"]["valor_confirmado"] == 2500.0


def test_fluxo_caixa_lista_previstos_e_some_apos_confirmar(http_client_factory, seed, app_db):
    hoje = date.today().isoformat()
    rid = _criar_recebivel_com_saldo(app_db, seed, "t3", valor=1500.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/fluxo-caixa?de=%s&ate=%s" % (hoje, hoje))
    assert st == 200 and d["ok"] is True, d
    ids = {p["id"] for p in d["previstos"]}
    assert rid in ids
    linha = next(p for p in d["previstos"] if p["id"] == rid)
    assert linha["valor_previsto"] == 1500.0 and linha["projeto"] == seed["projeto_l1"]
    c.post("/api/recebiveis/%d/confirmar" % rid, {})
    st2, d2 = c.get("/api/financeiro/fluxo-caixa?de=%s&ate=%s" % (hoje, hoje))
    assert rid not in {p["id"] for p in d2["previstos"]}


# ── HTTP: GET /api/financeiro/recebiveis (Reconciliação — Provisões/Recebíveis) ─────────────────

def test_endpoint_recebiveis_por_projeto(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t4", valor=2200.0,
                                     data_prevista=date(2026, 12, 1))   # futuro, não vencido
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/recebiveis?projeto=%s" % seed["projeto_l1"])
    assert st == 200 and d["ok"] is True, d
    linha = next(r for r in d["recebiveis"] if r["id"] == rid)
    assert linha["status"] == "previsto" and linha["vencido"] is False
    assert linha["valor_previsto"] == 2200.0 and linha["projeto"] == seed["projeto_l1"]
    assert d["totais"]["previsto"] >= 2200.0


def test_endpoint_recebiveis_vencido(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t5", valor=800.0,
                                     data_prevista=date(2020, 1, 1))   # passado, ainda previsto
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/recebiveis?projeto=%s" % seed["projeto_l1"])
    assert st == 200 and d["ok"] is True, d
    linha = next(r for r in d["recebiveis"] if r["id"] == rid)
    assert linha["vencido"] is True
    assert d["totais"]["vencido"] >= 800.0


def test_endpoint_recebiveis_confirmado_aparece_nos_totais(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t6", valor=3300.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/recebiveis/%d/confirmar" % rid, {})
    st, d = c.get("/api/financeiro/recebiveis?projeto=%s" % seed["projeto_l1"])
    assert st == 200 and d["ok"] is True, d
    linha = next(r for r in d["recebiveis"] if r["id"] == rid)
    assert linha["status"] == "confirmado" and linha["valor_confirmado"] == 3300.0
    assert linha["vencido"] is False   # confirmado nunca é vencido
    assert d["totais"]["confirmado"] >= 3300.0


def test_endpoint_recebiveis_consolidado_sem_projeto(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t7", valor=555.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/recebiveis")
    assert st == 200 and d["ok"] is True, d
    assert rid in {r["id"] for r in d["recebiveis"]}


# ── Não-recebimento: mod_contabil.reclassificar_recebivel_duvidoso ──────────────────────────────

def test_reclassificar_duvidoso_move_saldo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 710; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 8000.0, projeto_id="P", ref="venda:P")
    lan = mc.reclassificar_recebivel_duvidoso(db, ot, oid, "P", 3000.0, ref="duv:P:1")
    assert lan is not None
    assert _saldo(db, ot, oid, "1.1.02") == 5000.0
    assert _saldo(db, ot, oid, "1.1.10") == 3000.0
    db.close()


def test_reclassificar_duvidoso_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 711; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 4000.0, projeto_id="P", ref="venda:P")
    mc.reclassificar_recebivel_duvidoso(db, ot, oid, "P", 1000.0, ref="duv:P:1")
    mc.reclassificar_recebivel_duvidoso(db, ot, oid, "P", 1000.0, ref="duv:P:1")
    assert _saldo(db, ot, oid, "1.1.10") == 1000.0
    db.close()


def test_reclassificar_duvidoso_capa_ao_saldo_aberto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 712; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 500.0, projeto_id="P", ref="venda:P")
    lan = mc.reclassificar_recebivel_duvidoso(db, ot, oid, "P", 2000.0, ref="duv:P:1")
    assert lan["valor"] == 500.0
    assert _saldo(db, ot, oid, "1.1.02") == 0.0
    db.close()


def test_registrar_recebimento_duvidoso_credita_1_1_10(app_db):
    """Confirmar um recebível já duvidoso baixa 1.1.10, NÃO 1.1.02 de novo."""
    db = app_db.get_session(); ot, oid = "loja", 713; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 6000.0, projeto_id="P", ref="venda:P")
    mc.reclassificar_recebivel_duvidoso(db, ot, oid, "P", 6000.0, ref="duv:P:1")
    lan = mc.registrar_recebimento_venda(db, ot, oid, "P", 6000.0, ref="recv:P:1", duvidoso=True)
    assert lan is not None
    assert _saldo(db, ot, oid, "1.1.01") == 6000.0
    assert _saldo(db, ot, oid, "1.1.10") == 0.0
    assert _saldo(db, ot, oid, "1.1.02") == 0.0   # já tinha sido reclassificado, não mexe de novo
    db.close()


# ── HTTP: reprogramar + duvidoso ─────────────────────────────────────────────────────────────

def test_endpoint_reprogramar_muda_data(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t8", valor=1200.0, data_prevista=date(2020, 1, 1))
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/recebiveis/%d/reprogramar" % rid, {"data_prevista": "2027-01-15"})
    assert st == 200 and d["ok"] is True, d
    assert d["recebivel"]["data_prevista"] == "2027-01-15"
    st2, d2 = c.get("/api/financeiro/recebiveis")
    linha = next(r for r in d2["recebiveis"] if r["id"] == rid)
    assert linha["vencido"] is False   # não vencido mais, a data virou futuro


def test_endpoint_reprogramar_audita_log_acao_gerencial(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t9", valor=700.0, data_prevista=date(2020, 1, 1))
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/recebiveis/%d/reprogramar" % rid, {"data_prevista": "2027-02-01"})
    db = app_db.get_session()
    log = (db.query(app_db.LogAcaoGerencial).filter_by(acao="reprogramar_recebivel")
           .order_by(app_db.LogAcaoGerencial.id.desc()).first())
    assert log is not None
    ctx = json.loads(log.contexto)
    assert ctx["recebivel_id"] == rid and ctx["valor_novo"] == "2027-02-01"
    db.close()


def test_endpoint_reprogramar_bloqueado_se_ja_confirmado(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t10", valor=400.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/recebiveis/%d/confirmar" % rid, {})
    st, d = c.post("/api/recebiveis/%d/reprogramar" % rid, {"data_prevista": "2027-01-01"})
    assert st == 409 and d["ok"] is False


def test_endpoint_duvidoso_reclassifica_e_bloqueia_dobra(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t11", valor=2500.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/recebiveis/%d/duvidoso" % rid, {})
    assert st == 200 and d["ok"] is True, d
    assert d["recebivel"]["status"] == "duvidoso"
    st2, d2 = c.get("/api/financeiro/recebiveis")
    linha = next(r for r in d2["recebiveis"] if r["id"] == rid)
    assert linha["status"] == "duvidoso" and linha["vencido"] is False
    assert d2["totais"]["duvidoso"] >= 2500.0
    # não pode marcar como duvidoso de novo
    st3, d3 = c.post("/api/recebiveis/%d/duvidoso" % rid, {})
    assert st3 == 409 and d3["ok"] is False


def test_endpoint_confirmar_apos_duvidoso_credita_1_1_10(http_client_factory, seed, app_db):
    rid = _criar_recebivel_com_saldo(app_db, seed, "t12", valor=1800.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/recebiveis/%d/duvidoso" % rid, {})
    st, d = c.post("/api/recebiveis/%d/confirmar" % rid, {})
    assert st == 200 and d["ok"] is True, d
    assert d["recebivel"]["status"] == "confirmado"
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    lan = mc.lancamento_por_ref(db, ot, oid, "recv:http:%s:t12" % seed["projeto_l1"])
    conta_debito = db.query(mc.Conta).filter_by(id=lan["conta_debito_id"]).first()
    conta_credito = db.query(mc.Conta).filter_by(id=lan["conta_credito_id"]).first()
    assert conta_debito.codigo == "1.1.01" and conta_credito.codigo == "1.1.10"
    db.close()
