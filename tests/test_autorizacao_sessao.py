# -*- coding: utf-8 -*-
"""Autorização SESSÃO-PRIMEIRO (pedido 2026-07-24): logado com a permissão não redigita
senha; a senha gerencial só é exigida quando o logado NÃO tem a permissão (aí valem as
credenciais de um terceiro que tem). E: operador sem Fiscal (módulo) — matriz + registro.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, "login falhou para %s" % who
    return c


# ── /api/gerente/verificar ───────────────────────────────────────────────────

def test_verificar_sem_senha_ok_para_quem_autoriza(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")            # master: pode autorizar
    st, out = c.post("/api/gerente/verificar", {"senha": ""})
    assert st == 200 and out["ok"] is True


def test_verificar_sem_senha_nega_operador(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")           # operador: não autoriza
    st, out = c.post("/api/gerente/verificar", {"senha": ""})
    assert out["ok"] is False


# ── desfazer_aprovacao / reabrir: sessão-primeiro + credenciais de terceiro ──

def test_reabrir_sem_credenciais_com_permissao(http_client_factory, app_db, seed):
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="1",
                             status="concluido"))
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")            # master: reabre sem redigitar senha
    st, out = c.post("/api/projetos/%s/ciclo/1/reabrir" % seed["projeto_l1"], {})
    assert st == 200 and out["ok"], (st, out)


def test_reabrir_operador_sem_credenciais_nega(http_client_factory, app_db, seed, projetos_dir):
    db = app_db.get_session()
    et = (db.query(app_db.CicloEtapa)
            .filter_by(projeto_nome=seed["projeto_l1"], etapa_codigo="1").first())
    if et is None:
        db.add(app_db.CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="1",
                                 status="concluido"))
    else:
        et.status = "concluido"
    db.commit(); db.close()
    c = _login(http_client_factory, "cons_l1")
    st, out = c.post("/api/projetos/%s/ciclo/1/reabrir" % seed["projeto_l1"], {})
    assert out.get("ok") is not True                     # sem permissão e sem credenciais


def test_reabrir_operador_com_credenciais_do_diretor(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "cons_l1")
    st, out = c.post("/api/projetos/%s/ciclo/1/reabrir" % seed["projeto_l1"],
                     {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and out["ok"], (st, out)            # fluxo antigo segue valendo


# ── Operador sem Fiscal ──────────────────────────────────────────────────────

def test_matriz_operador_sem_fiscal(app_db, seed):
    from auth import perfis
    # o seed cria o registro por loja (DB manda): operador sem 'fiscal' no modulos_json
    assert perfis.acessa_modulo("operador", "fiscal") is False
    assert perfis.acessa_modulo("operador", "financeiro") is False
    assert perfis.acessa_modulo("operador", "comercial") is True


def test_auth_me_do_operador_sem_fiscal(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, out = c.get("/api/auth/me")
    assert st == 200
    assert "fiscal" not in out["usuario"]["modulos_ativos"]
    # e as flags novas de capacidade chegam ao frontend
    assert out["usuario"]["pode_autorizar"] is False
    d = _login(http_client_factory, "dir_l1")
    st, out = d.get("/api/auth/me")
    assert out["usuario"]["pode_autorizar"] is True
    assert out["usuario"]["pode_aprovar_financeiro"] is True


def test_operador_403_no_perfil_fiscal(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, out = c.get("/api/admin/lojas/%d/perfil-fiscal" % seed["loja1_id"])
    assert st == 403


def test_backfill_remove_fiscal_do_operador_existente(app_db, seed):
    import json as _json
    from auth import perfil_store, perfis as _perfis
    db = app_db.get_session()
    p = (db.query(app_db.PerfilAcesso)
           .filter_by(loja_id=seed["loja1_id"], slug="operador", sistema=1).first())
    assert p is not None
    p.modulos_json = _json.dumps(_json.loads(p.modulos_json or "[]") + ["fiscal"])  # simula legado
    db.commit()
    perfil_store.backfill_perfis_todas_lojas(db)
    db.refresh(p)
    assert "fiscal" not in _json.loads(p.modulos_json)
    db.close()
    _perfis.recarregar()
