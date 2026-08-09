"""Painel Estratégico (2026-08-09, pedido do usuário): snapshot consolidado de indicadores —
custos fixos, econômico-financeiro, rentabilidade, comercial/operacional, comparativo entre
lojas. Escopo desta 1ª entrega: só indicadores cujo dado já existe (ver mod_estrategico.py)."""
from datetime import date, datetime

import mod_contabil as mc
import mod_estrategico as me


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_snapshot_estrutura_e_periodo(app_db, seed):
    # loja AVULSA de propósito (sem rede_id) — as duas lojas do seed pertencem à mesma rede
    # (resolver_owner consolidaria em "rede"); pra testar o owner "loja" preciso de uma sem rede.
    db = app_db.get_session()
    avulsa = app_db.Loja(nome="Loja Avulsa Teste", codigo="AVT")
    db.add(avulsa); db.flush()
    ot, oid = mc.resolver_owner(db, {"loja_id": avulsa.id, "rede_id": None})
    assert ot == "loja"
    mc.seed_plano(db, ot, oid)
    db.commit()
    dados = me.snapshot(db, ot, oid, "mes", date(2026, 8, 15))
    db.close()
    assert dados["periodo"]["tipo"] == "mes"
    assert dados["periodo"]["ini"] == "2026-08-01"
    assert dados["periodo"]["fim"] == "2026-08-31"
    assert dados["periodo"]["ini_anterior"] == "2026-07-01"
    for bloco in ("custos_fixos", "economico_financeiro", "rentabilidade", "comercial_operacional"):
        assert bloco in dados, bloco
    # loja avulsa (não-rede) não tem comparativo entre lojas
    assert dados["comparativo_lojas"] is None


def test_snapshot_custo_fixo_reflete_relatorio_natureza(app_db, seed):
    db = app_db.get_session()
    avulsa = app_db.Loja(nome="Loja Avulsa Teste 2", codigo="AV2")
    db.add(avulsa); db.flush()
    ot, oid = mc.resolver_owner(db, {"loja_id": avulsa.id, "rede_id": None})
    mc.seed_plano(db, ot, oid)
    db.commit()
    # seed_plano não classifica natureza_custo por si (isso é migração/edição à parte) — marca
    # uma conta analítica de despesa como "fixo" pra exercitar o agrupamento de verdade.
    conta_fixa = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="5.2.04").first()
    assert conta_fixa is not None and conta_fixa.tipo == "analitica"
    conta_fixa.natureza_custo = "fixo"
    caixa = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="1.1.01").first()
    mc.lancar(db, ot, oid, conta_fixa.id, caixa.id, 3000.0,
             data=datetime(2026, 8, 10), ref="despesa-fixa-teste")
    db.commit()
    dados = me.snapshot(db, ot, oid, "mes", date(2026, 8, 15))
    db.close()
    assert dados["custos_fixos"]["atual_periodo"] == 3000.0
    assert dados["custos_fixos"]["serie"]["valores"][-1] == 3000.0
    assert len(dados["custos_fixos"]["serie"]["labels"]) == 6


def test_snapshot_rede_traz_comparativo_entre_lojas(app_db, seed):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": None, "rede_id": seed["rede_id"]})
    mc.seed_plano(db, ot, oid)
    db.commit()
    dados = me.snapshot(db, ot, oid, "mes", date(2026, 8, 15))
    db.close()
    assert dados["comparativo_lojas"] is not None
    ids = {r["loja_id"] for r in dados["comparativo_lojas"]}
    assert {seed["loja1_id"], seed["loja2_id"]} <= ids
    for r in dados["comparativo_lojas"]:
        assert "benchmark_vs_media_pct" in r


def test_janela_periodo_trimestre_e_ano_tambem_funcionam(app_db, seed):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    db.commit()
    for tipo in ("trimestre", "ano"):
        dados = me.snapshot(db, ot, oid, tipo, date(2026, 8, 15))
        assert dados["periodo"]["tipo"] == tipo
    db.close()


def test_endpoint_exclusivo_de_acesso_estrategico(http_client_factory, seed, app_db):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    db.commit(); db.close()
    # master (dir_l1) tem acesso_estrategico por padrão
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/estrategico/indicadores")
    assert st == 200 and body["ok"], body
    assert "custos_fixos" in body["indicadores"]
    assert body["indicadores"]["periodo"]["tipo"] == "mes"   # default


def test_endpoint_gerencial_nao_acessa(http_client_factory, seed, app_db):
    """Gerencial não tem acesso_estrategico por padrão (só Master, decisão do usuário)."""
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    u = app_db.Usuario(nome="Gerente Teste", login="ger_estrategico_teste", nivel="gerencial",
                       loja_id=seed["loja1_id"], ativo=1)
    u.set_senha("senha123")
    db.add(u); db.commit(); db.close()
    c = _login(http_client_factory, "ger_estrategico_teste")
    st, body = c.get("/api/estrategico/indicadores")
    assert st == 403


def test_endpoint_periodo_invalido_cai_no_default_mes(http_client_factory, seed, app_db):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/estrategico/indicadores?periodo=bagunca")
    assert st == 200 and body["indicadores"]["periodo"]["tipo"] == "mes"


def test_endpoint_periodo_trimestre_e_ano(http_client_factory, seed, app_db):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    for tipo in ("trimestre", "ano"):
        st, body = c.get(f"/api/estrategico/indicadores?periodo={tipo}")
        assert st == 200 and body["indicadores"]["periodo"]["tipo"] == tipo


def test_endpoint_loja_id_dentro_da_mesma_rede_funciona(http_client_factory, seed, app_db):
    """loja1 e loja2 do seed pertencem à MESMA rede — drill-down de dir_l1 (master da rede
    consolidada) pra loja2 é DENTRO do escopo."""
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    assert ot == "rede"   # confirma a premissa do teste
    mc.seed_plano(db, ot, oid)
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/estrategico/indicadores?loja_id={seed['loja2_id']}")
    assert st == 200 and body["ok"], body
    assert body["indicadores"]["loja_id"] == seed["loja2_id"]


def test_endpoint_loja_id_de_outra_rede_barrado(http_client_factory, seed, app_db):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    outra_rede = app_db.Rede(nome="Outra Rede Teste")
    db.add(outra_rede); db.flush()
    loja_de_outra_rede = app_db.Loja(nome="Loja de Outra Rede", codigo="OUT", rede_id=outra_rede.id)
    db.add(loja_de_outra_rede); db.commit()
    loja_de_outra_rede_id = loja_de_outra_rede.id
    db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/estrategico/indicadores?loja_id={loja_de_outra_rede_id}")
    assert st == 403
