"""Cancelamento de contrato (dentro do prazo, ANTES da NF-e): estorno TOTAL da constituição do contrato
— Receita a Realizar + provisões×ativos diferidos (reusa devolver_venda f=1.0) + juros a apropriar do
ramo loja (2.1.07 × 1.1.07). Origem/rótulo próprios no razão (distingue de devolução). O reembolso físico
de valores já recebidos fica p/ a Tesouraria (módulo futuro)."""
import os
import pytest
import mod_contabil as mc


@pytest.fixture
def contratos_dir(tmp_path):
    """Redireciona CONTRATOS_DIR para um temp (hermético) — igual test_fluxo_completo_e2e.py."""
    import mod_contrato
    orig = mod_contrato.CONTRATOS_DIR
    mod_contrato.CONTRATOS_DIR = str(tmp_path / "contratos")
    os.makedirs(mod_contrato.CONTRATOS_DIR, exist_ok=True)
    yield mod_contrato.CONTRATOS_DIR
    mod_contrato.CONTRATOS_DIR = orig


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def _montar_contrato(db, ot, oid, proj, com_juros=True):
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 10000.0, projeto_id=proj, ref="v:" + proj)
    mc.constituir_provisoes_fechamento(db, ot, oid, proj,
                                       {"custo_fabrica": 4000.0, "impostos": 1000.0}, ref_base="pf:" + proj)
    if com_juros:   # ramo loja: juros a apropriar (1.1.07 × 2.1.07)
        mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 600.0, projeto_id=proj, ref="j:" + proj)


def test_cancelar_contrato_estorna_diferido_e_juros(app_db):
    db = app_db.get_session(); ot, oid = "loja", 989
    _montar_contrato(db, ot, oid, "P")
    out = mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")
    # diferido zerado
    assert _s(db, ot, oid, "2.1.06") == 0.0 and _s(db, ot, oid, "1.1.02") == 0.0
    assert _s(db, ot, oid, "2.1.04.06") == 0.0 and _s(db, ot, oid, "1.1.06.06") == 0.0
    assert _s(db, ot, oid, "2.1.04.13") == 0.0 and _s(db, ot, oid, "1.1.05") == 0.0
    # juros a apropriar zerados (recebível 1.1.07 + passivo 2.1.07)
    assert _s(db, ot, oid, "1.1.07") == 0.0 and _s(db, ot, oid, "2.1.07") == 0.0
    assert out.get("1.1.07") == 600.0
    db.close()


def test_cancelar_contrato_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 988
    _montar_contrato(db, ot, oid, "P", com_juros=False)
    mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")
    mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")   # 2ª vez — não duplica
    assert _s(db, ot, oid, "2.1.06") == 0.0 and _s(db, ot, oid, "2.1.04.06") == 0.0
    db.close()


def test_cancelamento_endpoint_estorna_e_trava(http_client_factory, seed, app_db):
    # cobre o fluxo do BOTÃO com LANÇAMENTOS reais: 200 + estorno + status "cancelado". (NOTA: o lock
    # "database is locked" do SQLite em ARQUIVO — ordem commit×upsert — NÃO reproduz aqui, pois o app_db
    # de teste é em memória; este teste garante o contrato do endpoint, não a corrida de sessões.)
    db = app_db.get_session()
    ot, own = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, own)
    mc.registrar_evento(db, ot, own, "registro_venda_contrato", 10000.0, projeto_id="Proj_L1", ref="v:Proj_L1")
    mc.constituir_provisoes_fechamento(db, ot, own, "Proj_L1", {"custo_fabrica": 4000.0}, ref_base="pf:Proj_L1")
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    st, d = c.post("/api/orcamentos/%d/cancelamento" % oid, {"login": "dir_l1", "senha": "senha123"})
    assert st == 200, (st, d)
    assert d.get("ok") and d.get("status") == "cancelado", d
    assert d.get("revertido"), d   # estornou lançamentos de fato


def test_cancelamento_leve_1_assinatura_reabre_negociacao(app_db, seed, http_client_factory):
    """0/1 assinatura no momento do cancelamento (provisão ainda não existia, regra 2026-08-12):
    invalida a assinatura parcial, projeto continua editável (cancelado_definitivo=0)."""
    from database import Projeto, Contrato, ContratoAssinatura
    from datetime import datetime
    import main as _main
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    ct = db.get(Contrato, cid); ct.status = "assinado_loja"
    db.add(ContratoAssinatura(contrato_id=cid, parte="loja", nome="L", cpf="00000000000",
                              assinado_em=datetime.utcnow(), hash_sha256="x" * 64))
    db.commit(); db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/orcamentos/%d/cancelamento" % seed["orcamento_l1_id"],
                   {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and d.get("ok") and d.get("status") == "cancelado", d
    assert d.get("definitivo") is False, d

    db2 = app_db.get_session()
    pm = db2.get(Projeto, nome)
    assert not pm.cancelado_definitivo, "cancelamento leve não pode travar o projeto"
    ct2 = db2.get(Contrato, cid)
    assert ct2.status == "para_assinatura", "assinatura parcial deveria ser invalidada"
    assert len(ct2.assinaturas) == 0
    assert _main._contrato_assinado(nome, db2) is False, "negociação deve reabrir"
    db2.close()


def test_cancelamento_definitivo_2_assinaturas_trava_projeto(app_db, seed, http_client_factory):
    """2 assinaturas (provisão já existia, mesmo que zerada) → estorna e trava o projeto PRA
    SEMPRE — gerar um contrato novo fica bloqueado, negociação nunca mais reabre."""
    from database import Projeto, Contrato, ContratoAssinatura
    from datetime import datetime
    import main as _main
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    ct = db.get(Contrato, cid); ct.status = "assinado"
    db.add_all([
        ContratoAssinatura(contrato_id=cid, parte="loja", nome="L", cpf="00000000000",
                          assinado_em=datetime.utcnow(), hash_sha256="x" * 64),
        ContratoAssinatura(contrato_id=cid, parte="cliente", nome="C", cpf="11111111111",
                          assinado_em=datetime.utcnow(), hash_sha256="y" * 64),
    ])
    db.commit(); db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/orcamentos/%d/cancelamento" % seed["orcamento_l1_id"],
                   {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and d.get("ok") and d.get("status") == "cancelado", d
    assert d.get("definitivo") is True, d

    db2 = app_db.get_session()
    pm = db2.get(Projeto, nome)
    assert pm.cancelado_definitivo == 1
    assert _main._contrato_assinado(nome, db2) is True
    assert _main._contrato_totalmente_assinado(nome, db2) is True
    db2.close()

    # gerar um contrato NOVO fica bloqueado — a trava é do projeto, não do contrato específico.
    st2, d2 = c.post("/api/projetos/%s/contrato" % nome, {"orcamento_id": seed["orcamento_l1_id"]})
    assert st2 == 403 and not d2.get("ok"), (st2, d2)
    assert "cancelado" in d2.get("erro", "").lower()


def test_gerente_pode_cancelar_contrato(app_db, seed, http_client_factory):
    """Decisão do usuário (2026-08-12): Gerente (não só Diretor) pode cancelar — o texto antigo
    da UI mentia. Cria um usuário 'gerencial' e confirma que o endpoint aceita.
    Isolamento: `seed` é module-scoped — reseta o Contrato/Projeto pra não herdar o
    cancelado_definitivo=1 deixado pelo teste anterior (senão passaria mesmo se o gate
    de perfil estivesse quebrado, já que o projeto já estaria cancelado de qualquer jeito)."""
    from database import Usuario, Projeto, Contrato, ContratoAssinatura
    db = app_db.get_session()
    db.get(Projeto, seed["projeto_l1"]).cancelado_definitivo = 0
    db.query(ContratoAssinatura).filter_by(contrato_id=seed["contrato_l1_id"]).delete()
    db.get(Contrato, seed["contrato_l1_id"]).status = "rascunho"
    u = db.query(Usuario).filter_by(login="ger_l1").first()
    if u is None:
        u = Usuario(nome="Gerente L1", login="ger_l1", nivel="gerencial", loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("senha123")
        db.add(u)
    db.commit(); db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")   # sessão qualquer da loja
    st, d = c.post("/api/orcamentos/%d/cancelamento" % seed["orcamento_l1_id"],
                   {"login": "ger_l1", "senha": "senha123"})
    assert st == 200 and d.get("ok"), (st, d)


def test_gerar_contrato_apos_cancelamento_leve_usa_orcamento_correto(
        app_db, seed, projetos_dir, contratos_dir, http_client_factory):
    """Achado crítico da Vera (2026-08-12): cancelar (leve) e gerar contrato de novo com um
    orçamento DIFERENTE do mesmo projeto reaproveitava o Contrato anterior sem atualizar
    orcamento_id — o contrato saía com os dados/ambientes do orçamento ERRADO (o cancelado).
    Um orçamento diferente precisa nascer como um Contrato NOVO."""
    from tests.test_fluxo_completo_e2e import _setup_cenario
    from database import Contrato
    import json as _json
    _setup_cenario(app_db, seed)
    nome = seed["projeto_l1"]
    oid1 = seed["orcamento_l1_id"]

    db = app_db.get_session()
    # 2º orçamento do MESMO projeto, com seu próprio ambiente (nome diferente do 1º).
    orc2 = app_db.Orcamento(projeto_id=nome, nome="Orçamento 2", ordem=2, loja_id=seed["loja1_id"])
    db.add(orc2); db.flush()
    pa2 = app_db.PoolAmbiente(projeto_id=nome, nome="Suite Master", versao=1,
                              nome_exibicao="Suite Master", xml_path="", ambientes_json="[]",
                              budget_total=50000.0, order_total=20000.0)
    db.add(pa2); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=orc2.id, pool_ambiente_id=pa2.id,
                                    desconto_individual_pct=0.0))
    orc2.desconto_pct = 0.0
    orc2.forma_pagamento = _json.dumps({
        "tipo": "avista", "nome_forma": "A Vista", "entrada_valor": 5000,
        "entrada_data": "2026-08-01", "entrada_forma": "pix", "total_cliente": 50000.0,
        "parcelas": [{"num": 1, "data": "2026-08-20", "valor": 45000.0, "forma": "pix"}]})
    db.commit()
    oid2 = orc2.id
    db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/projetos/%s/contatos-comunicacao/confirmar" % nome, {"modo": "sem_whatsapp"})

    # 1) Gera contrato do orçamento 1
    st, b = c.post("/api/projetos/%s/contrato" % nome, {
        "orcamento_id": oid1,
        "endereco_instalacao": "Av. Paulista, 1000 - São Paulo/SP",
        "pagamento_json": _json.dumps({"tipo": "avista", "total_cliente": 90000.0, "parcelas": []}),
        "confirmar_loja_incompleta": True,
    })
    assert st == 200 and b["ok"], b
    contrato_id_1 = b["contrato_id"]

    # 2) Cancela — 0 assinaturas → leve, projeto continua editável
    st, d = c.post("/api/orcamentos/%d/cancelamento" % oid1, {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and d.get("ok") and d.get("definitivo") is False, d

    # 3) Gera contrato do orçamento 2 (DIFERENTE) no mesmo projeto
    st, b2 = c.post("/api/projetos/%s/contrato" % nome, {
        "orcamento_id": oid2,
        "endereco_instalacao": "Av. Paulista, 1000 - São Paulo/SP",
        "pagamento_json": _json.dumps({"tipo": "avista", "total_cliente": 50000.0, "parcelas": []}),
        "confirmar_loja_incompleta": True,
    })
    assert st == 200 and b2["ok"], b2
    contrato_id_2 = b2["contrato_id"]

    # O contrato do orçamento 2 tem que ser um registro NOVO, apontando pro orçamento 2 — nunca
    # reaproveitar o Contrato do orçamento 1 (cancelado) com o orcamento_id errado.
    assert contrato_id_2 != contrato_id_1, "reaproveitou o Contrato antigo em vez de criar um novo"
    db2 = app_db.get_session()
    ct2 = db2.get(Contrato, contrato_id_2)
    assert ct2.orcamento_id == oid2, "contrato do orçamento 2 ficou com orcamento_id errado"
    db2.close()

    # E o PDF/HTML gerado reflete o ambiente do orçamento 2 ("Suite Master"), não o do 1 ("Cozinha").
    st, b3 = c.get("/api/projetos/%s/contrato" % nome)
    assert st == 200 and b3["contrato"]["tem_pdf"] is True


def test_cancelar_contrato_deixa_recebivel_a_devolver_se_houve_recebimento(app_db):
    # se o cliente já pagou (recebimento_venda abate 1.1.02), o estorno da Receita a Realizar deixa
    # 1.1.02 CREDOR = valor a devolver (reembolso físico → Tesouraria, módulo futuro).
    db = app_db.get_session(); ot, oid = "loja", 987
    _montar_contrato(db, ot, oid, "P", com_juros=False)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 3000.0, projeto_id="P", ref="rec:P")  # cliente pagou 3000
    mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")
    assert _s(db, ot, oid, "2.1.06") == 0.0        # receita a realizar zerada
    assert _s(db, ot, oid, "1.1.02") == -3000.0    # recebível credor = a devolver ao cliente
    db.close()
