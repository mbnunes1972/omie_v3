import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_tenancy as mt
from types import SimpleNamespace


def _loja(modulos_ativos=None):
    return SimpleNamespace(id=1, modulos_ativos=modulos_ativos)


def test_default_tudo_ligado():
    loja = _loja(None)
    assert mt.modulo_ativo(loja, "fiscal") is True
    assert mt.modulo_ativo(loja, "comercial") is True


def test_nucleo_sempre_ativo():
    loja = _loja(json.dumps(["comercial"]))
    assert mt.modulo_ativo(loja, "auth") is True
    assert mt.modulo_ativo(loja, "tenancy") is True


def test_dominio_desligado():
    loja = _loja(json.dumps(["cadastro", "comercial", "financeiro"]))
    assert mt.modulo_ativo(loja, "fiscal") is False
    assert mt.modulo_ativo(loja, "comercial") is True


def test_lista_ativa_resolve():
    loja = _loja(json.dumps(["cadastro"]))
    assert "cadastro" in mt.modulos_ativos_da_loja(loja)
    assert "fiscal" not in mt.modulos_ativos_da_loja(loja)


def test_get_put_modulos_da_loja(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    st, d = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert st == 200 and "fiscal" in d["ativos"]
    st2, d2 = c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial"]})
    assert st2 == 200
    st3, d3 = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert "fiscal" not in d3["ativos"] and "comercial" in d3["ativos"]


def test_guard_bloqueia_modulo_desligado(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial", "producao", "financeiro"]})
    dc = http_client_factory(); dc.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = dc.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st == 403 and "módulo" in (d.get("erro", "")).lower()
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})
    st2, _ = dc.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 in (200, 404)


def test_guard_bloqueia_modulo_desligado_nos_posts_de_emissao(http_client_factory, seed, app_db):
    """Achado de auditoria 2026-08-13: só o GET /ciclo/15/nfe checava o módulo 'fiscal'
    desligado — os POSTs que de fato emitem/consultam/cancelam nunca checavam, então desligar o
    módulo escondia a tela mas não impedia emissão real via POST direto."""
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    stp, dp = c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial", "financeiro"]})
    assert stp == 200 and dp["ok"], dp
    dc = http_client_factory(); dc.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    for path in (f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                 f"/api/projetos/{proj}/ciclo/15/emitir-nfse",
                 f"/api/projetos/{proj}/ciclo/15/nfe/consultar",
                 f"/api/projetos/{proj}/ciclo/15/nfe/cancelar"):
        st, d = dc.post(path, {})
        assert st == 403 and "módulo" in (d.get("erro", "")).lower(), (path, d)
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})   # restaura pra não vazar pros próximos testes


def test_get_modulos_lista_dominios_com_rotulo(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    st, d = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert st == 200
    ids = [x["id"] for x in d["dominios"]]
    assert "cadastro" in ids and "fiscal" in ids
    cad = next(x for x in d["dominios"] if x["id"] == "cadastro")
    assert cad["rotulo"] and cad["ativo"] is True


def test_post_modulos_rejeita_topologia_quebrada(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    st, d = c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["comercial"]})
    assert st == 400 and "depende" in (d.get("erro", "")).lower()
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})   # religa (não contamina)
