# -*- coding: utf-8 -*-
"""PDV — Diretor da mãe acessa o PDV como acessa a própria loja (pedido 2026-07-24).

Acesso DERIVADO em lojas_acessiveis_ids (nada gravado em usuario_lojas): o Diretor
(base master) da loja-mãe ganha os PDVs ativos dela no seletor multi-loja e pode
operar dentro deles via X-Loja-Ativa. Direção única e restrito ao Diretor.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from conftest import HttpClient


@pytest.fixture(scope="module")
def pdv(servidor, app_db, seed):
    c = HttpClient(servidor); c.login("super", "senha123")
    st, out = c.post("/api/admin/lojas/%d/pdvs" % seed["loja1_id"],
                     {"nome": "PDV Acesso", "codigo": "ACE"})
    assert st == 200 and out.get("ok"), (st, out)
    return out["pdv"]


@pytest.fixture(scope="module")
def pdv_user(app_db, pdv):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Master PDV", login="mst_pdv3", nivel="master",
                       loja_id=pdv["id"], ativo=1)
    u.set_senha("senha123")
    db.add(u); db.flush()
    db.add(app_db.UsuarioLoja(usuario_id=u.id, loja_id=pdv["id"]))
    db.commit(); db.close()
    return "mst_pdv3"


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, "login falhou para %s" % who
    return c


def test_diretor_da_mae_ve_o_pdv_no_seletor(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")            # master da mãe
    st, out = c.get("/api/auth/me")
    assert st == 200 and out["ok"]
    ids = {l["id"] for l in out["usuario"]["lojas"]}
    assert pdv["id"] in ids and seed["loja1_id"] in ids  # seletor multi-loja aparece


def test_operador_e_gerencial_da_mae_nao_ganham_o_pdv(http_client_factory, app_db, seed, pdv):
    c = _login(http_client_factory, "cons_l1")           # operador
    st, out = c.get("/api/auth/me")
    assert pdv["id"] not in {l["id"] for l in out["usuario"]["lojas"]}
    db = app_db.get_session()                            # gerencial da mãe: também não
    u = app_db.Usuario(nome="Ger L1", login="ger_l1x", nivel="gerencial",
                       loja_id=seed["loja1_id"], ativo=1)
    u.set_senha("senha123"); db.add(u); db.commit(); db.close()
    c2 = _login(http_client_factory, "ger_l1x")
    st, out = c2.get("/api/auth/me")
    assert pdv["id"] not in {l["id"] for l in out["usuario"]["lojas"]}


def test_diretor_de_outra_loja_nao_ganha_o_pdv(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l2")
    st, out = c.get("/api/auth/me")
    assert pdv["id"] not in {l["id"] for l in out["usuario"]["lojas"]}


def test_diretor_opera_dentro_do_pdv_via_loja_ativa(http_client_factory, seed, pdv, pdv_user):
    # cliente criado DENTRO do PDV pelo usuário do PDV
    cp = _login(http_client_factory, pdv_user)
    st, d = cp.post("/api/clientes", {"nome": "Cliente do PDV", "cpf": "390.533.447-05",
                                      "email": "pdv@x.com", "telefone": "(12) 90000-0001"})
    assert st == 200 and d["ok"], (st, d)
    cid = d["cliente"]["id"]

    # Diretor da mãe SEM header: não vê o cliente do PDV (escopo = mãe)
    c = _login(http_client_factory, "dir_l1")
    st, _ = c.get("/api/clientes/%d" % cid)
    assert st == 404

    # com X-Loja-Ativa = PDV: enxerga e opera como se fosse a própria loja
    c.loja_ativa = pdv["id"]
    st, d2 = c.get("/api/clientes/%d" % cid)
    assert st == 200 and d2["cliente"]["nome"] == "Cliente do PDV"


def test_operador_da_mae_nao_entra_no_pdv_por_header(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "cons_l1")
    c.loja_ativa = pdv["id"]                             # header fora do escopo dele
    st, out = c.get("/api/clientes")
    assert st == 403


def test_direcao_unica_pdv_nao_ganha_a_mae(http_client_factory, seed, pdv, pdv_user):
    c = _login(http_client_factory, pdv_user)            # master DO PDV
    st, out = c.get("/api/auth/me")
    assert seed["loja1_id"] not in {l["id"] for l in out["usuario"]["lojas"]}
    c.loja_ativa = seed["loja1_id"]                      # tenta forçar a mãe
    st, out = c.get("/api/clientes")
    assert st == 403


def test_pdv_desativado_sai_do_escopo(http_client_factory, app_db, seed, pdv):
    db = app_db.get_session()
    l = db.get(app_db.Loja, pdv["id"]); l.ativo = 0; db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/auth/me")
    assert pdv["id"] not in {l2["id"] for l2 in out["usuario"]["lojas"]}
    db = app_db.get_session()
    l = db.get(app_db.Loja, pdv["id"]); l.ativo = 1; db.commit(); db.close()
