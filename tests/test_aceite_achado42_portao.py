# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-42, seção "DECIDIDO 02/09 — o mesmo portão do desconto".

`comissao_arq_pct`/`fidelidade_pct` (POST /api/projetos/<nome>/parametros) passam a exigir o
MESMO portão de `desconto_pct` (/margens) e desconto individual (/descontos): limite do perfil
(`Usuario.limite_desconto`), autorização de gerente pra estourar, e — item novo — margem líquida
negativa é recusa DURA, sem credencial que a levante.

Item 2 é a composição: comissão + fidelidade + o desconto JÁ APLICADO, nunca campo a campo (mesmo
achado da Vera de 12/08 — `_maior_desconto_efetivo_pct` — agora com uma terceira alavanca)."""
import json

import pytest


def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


def _preparar_projeto(app_db, seed, vbva=10000.0, cfa=4000.0):
    """Ambiente único, projeto/orçamento limpos de desconto e parametros — os testes deste
    arquivo assumem estado conhecido (seed é module-scoped, testes anteriores podem ter deixado
    resíduo)."""
    db = app_db.get_session()
    oid = seed["orcamento_l1_id"]
    orc = db.get(app_db.Orcamento, oid)
    orc.desconto_pct = 0.0
    for lk in db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
        db.delete(lk)
    db.flush()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="portao", nome_exibicao="Cozinha",
                             xml_path="p", ambientes_json="[]", order_total=cfa, budget_total=vbva)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    proj = db.get(app_db.Projeto, seed["projeto_l1"])
    proj.parametros_json = None
    db.commit()
    db.close()
    return oid


def _parametros(app_db, nome_projeto):
    db = app_db.get_session()
    proj = db.get(app_db.Projeto, nome_projeto)
    par = json.loads(proj.parametros_json) if proj.parametros_json else {}
    db.close()
    return par


# ── Item 1: comissão/fidelidade sozinhas, mesmo portão do desconto ──────────────────────────

def test_parametros_recusa_comissao_acima_do_limite_sem_autorizacao(http_client_factory, seed, app_db):
    _preparar_projeto(app_db, seed)
    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%
    nome = seed["projeto_l1"]

    st, body = c.post(f"/api/projetos/{nome}/parametros",
                      {"comissao_arq_ativa": True, "comissao_arq_pct": 30})
    assert st == 403
    assert body["requer_autorizacao"] is True
    assert body["limite"] == 10.0
    assert _parametros(app_db, nome).get("comissao_arq_pct", 0) != 30   # não persistiu


def test_parametros_aceita_comissao_dentro_do_proprio_limite(http_client_factory, seed, app_db):
    _preparar_projeto(app_db, seed)
    c = _login(http_client_factory, "dir_l1")   # master, limite 50%
    nome = seed["projeto_l1"]

    st, body = c.post(f"/api/projetos/{nome}/parametros",
                      {"comissao_arq_ativa": True, "comissao_arq_pct": 30})
    assert st == 200 and body["ok"] is True
    assert _parametros(app_db, nome)["comissao_arq_pct"] == 30


def test_parametros_aceita_comissao_acima_do_limite_com_autorizador_valido(http_client_factory, seed, app_db):
    _preparar_projeto(app_db, seed)
    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%
    nome = seed["projeto_l1"]

    st, body = c.post(f"/api/projetos/{nome}/parametros", {
        "comissao_arq_ativa": True, "comissao_arq_pct": 30,
        "login_autorizador": "dir_l1", "senha_autorizador": "senha123",
    })
    assert st == 200 and body["ok"] is True
    assert _parametros(app_db, nome)["comissao_arq_pct"] == 30

    db = app_db.get_session()
    log = (db.query(app_db.LogAutorizacao)
             .filter_by(desconto_solicit=30).order_by(app_db.LogAutorizacao.id.desc()).first())
    assert log is not None and log.autorizado == 1
    db.close()


def test_parametros_recusa_autorizador_cuja_senha_esta_errada(http_client_factory, seed, app_db):
    _preparar_projeto(app_db, seed)
    c = _login(http_client_factory, "cons_l1")
    nome = seed["projeto_l1"]

    st, body = c.post(f"/api/projetos/{nome}/parametros", {
        "comissao_arq_ativa": True, "comissao_arq_pct": 30,
        "login_autorizador": "dir_l1", "senha_autorizador": "senha_errada",
    })
    assert st == 403
    assert body["requer_autorizacao"] is True
    assert _parametros(app_db, nome).get("comissao_arq_pct", 0) != 30


# ── Item 2: COMPOSIÇÃO — desconto + comissão, nunca campo a campo ───────────────────────────
# Números (VBVA=10000, CFA=4000, sem desconto por ambiente): desconto 30% sozinho -> Desc_Tot
# 30%; comissão 30% sozinha (sem desconto) -> Desc_Tot 30%; os dois juntos -> Desc_Tot 51% —
# cada um sozinho passa no limite de 50% (master), juntos furam.

def test_composicao_desconto_mais_comissao_bloqueada_mesmo_dentro_do_limite_isolado(
        http_client_factory, seed, app_db):
    oid = _preparar_projeto(app_db, seed)
    nome = seed["projeto_l1"]
    c = _login(http_client_factory, "dir_l1")   # master, limite 50%

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 30})
    assert st == 200 and body["ok"] is True   # desconto sozinho, dentro do limite

    st, body = c.post(f"/api/projetos/{nome}/parametros",
                      {"comissao_arq_ativa": True, "comissao_arq_pct": 30})
    # comissão sozinha (30%) passaria no limite de 50% — mas o desconto de 30% JÁ ESTÁ aplicado;
    # composto = 51% > 50% -> tem que bloquear
    assert st == 403, body
    assert body["requer_autorizacao"] is True
    assert _parametros(app_db, nome).get("comissao_arq_pct", 0) != 30   # não persistiu


def test_composicao_bloqueada_na_ordem_inversa_comissao_depois_desconto(http_client_factory, seed, app_db):
    oid = _preparar_projeto(app_db, seed)
    nome = seed["projeto_l1"]
    c = _login(http_client_factory, "dir_l1")   # master, limite 50%

    st, body = c.post(f"/api/projetos/{nome}/parametros",
                      {"comissao_arq_ativa": True, "comissao_arq_pct": 30})
    assert st == 200 and body["ok"] is True   # comissão sozinha, dentro do limite

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 30})
    # desconto sozinho (30%) passaria — mas a comissão de 30% JÁ ESTÁ salva; composto 51% -> bloqueia
    assert st == 403, body
    assert body["requer_autorizacao"] is True

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) != 30   # não persistiu
    db.close()


def test_composicao_pequena_dentro_do_limite_nao_e_bloqueada(http_client_factory, seed, app_db):
    """Controle: quando a composição fica dentro do limite, nada é bloqueado — o portão não pode
    virar bloqueio de qualquer combinação."""
    oid = _preparar_projeto(app_db, seed)
    nome = seed["projeto_l1"]
    c = _login(http_client_factory, "dir_l1")   # master, limite 50%

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200 and body["ok"] is True

    st, body = c.post(f"/api/projetos/{nome}/parametros",
                      {"comissao_arq_ativa": True, "comissao_arq_pct": 10})
    assert st == 200 and body["ok"] is True, body   # composto bem abaixo de 50%
    assert _parametros(app_db, nome)["comissao_arq_pct"] == 10


# ── Item 3: margem líquida negativa é recusa DURA, sem credencial que a levante ─────────────

def test_parametros_recusa_dura_quando_margem_liquida_fica_negativa(http_client_factory, seed, app_db):
    """Master é o nível de MAIOR limite_desconto que existe (50%) — mesmo assim, sua própria
    credencial (válida, dele mesmo) não resolve: o corte de margem negativa é anterior e
    incondicional à checagem de limite/autorização."""
    _preparar_projeto(app_db, seed)
    c = _login(http_client_factory, "dir_l1")   # master, limite 50%
    nome = seed["projeto_l1"]

    st, body = c.post(f"/api/projetos/{nome}/parametros", {
        "comissao_arq_ativa": True, "comissao_arq_pct": 150,   # Val_Liq vira negativo
        "login_autorizador": "dir_l1", "senha_autorizador": "senha123",   # a própria credencial, válida
    })
    assert st == 400, body
    assert body.get("requer_autorizacao") is not True, (
        "não é 'precisa de autorização' — é recusa dura, credencial nenhuma resolve")
    assert _parametros(app_db, nome).get("comissao_arq_pct", 0) != 150   # não persistiu


def test_margens_recusa_dura_quando_desconto_deixa_margem_negativa(http_client_factory, seed, app_db):
    """O mesmo corte duro vale pro lado do desconto — margem negativa não se autoriza, não
    importa qual alavanca a causou. Isola do gate comum de limite: comissão de 110% já salva
    (setup direto, não pelo portão — não é o que este teste mede) + desconto de só 40% (bem
    dentro do limite de qualquer perfil) já deixam Val_Liq negativo juntos — a recusa aqui não
    pode ser "precisa de autorização", tem que ser a recusa dura."""
    oid = _preparar_projeto(app_db, seed)
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    proj = db.get(app_db.Projeto, nome)
    proj.parametros_json = json.dumps({"comissao_arq_ativa": True, "comissao_arq_pct": 110.0})
    db.commit()
    db.close()

    c = _login(http_client_factory, "dir_l1")   # master, limite 50% — 40% sozinho nem chegaria perto
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {
        "desconto_pct": 40,
        "login_autorizador": "dir_l1", "senha_autorizador": "senha123",
    })
    assert st == 400, body
    assert body.get("requer_autorizacao") is not True, (
        "40% de desconto sozinho não estoura limite nenhum — se recusou, tem que ser a recusa "
        "dura de margem negativa, não o gate de autorização")

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) != 40
    db.close()
