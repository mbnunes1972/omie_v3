# -*- coding: utf-8 -*-
"""Desmembramento OPERACIONAL — Fatia 1 (retido por ambiente + confirmação → parcelas).
Spec: docs/superpowers/specs/ciclo/2026-07-27-desmembramento-operacional-desde-medicao-design.md.

Medidor SINALIZA ambientes retidos (por ambiente); gerência CONFIRMA → parcela PRONTA × RETIDA
(reusa mod_parcelas). NÃO toca no razão. `particionar_por_selecao` exige ≥1 pronto (não dá pra
desmembrar com tudo retido)."""
import mod_retido


def _proj_amb(app_db, seed, nome, n):
    db = app_db.get_session()
    try:
        db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"], status="fechado"))
        ids = []
        for i in range(n):
            pa = app_db.PoolAmbiente(projeto_id=nome, nome="A%d" % i, nome_exibicao="Amb %d" % i,
                                     xml_path="x", ambientes_json="[]")
            db.add(pa); db.flush(); ids.append(pa.id)
        db.commit(); return ids
    finally:
        db.close()


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_sinalizar_e_listar(app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_a", 3)
    db = app_db.get_session()
    try:
        assert mod_retido.sinalizar(db, "RET_a", [ids[2]], medidor_id=None, motivo="obra") == [ids[2]]
        db.commit()
        assert [s["pool_ambiente_id"] for s in mod_retido.listar_sinais(db, "RET_a")] == [ids[2]]
        assert mod_retido.sinalizar(db, "RET_a", [999999], None) == []   # fora do pool é ignorado
    finally:
        db.close()


def test_confirmar_cria_pronta_e_retida(app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_b", 3)
    valores = {ids[0]: 600.0, ids[1]: 400.0, ids[2]: 1000.0}
    db = app_db.get_session()
    try:
        mod_retido.sinalizar(db, "RET_b", [ids[2]], None); db.commit()
        ok, erro, parc = mod_retido.confirmar(db, "RET_b", orcamento_id=None,
                                              valores_por_ambiente=valores, val_cont=2000.0,
                                              criado_por_id=None)
        db.commit()
        assert ok, erro
        by = {p["status"]: p for p in parc}
        assert set(by) == {"aguardando", "retido"}
        assert by["retido"]["ambientes"] == [ids[2]]
        assert round(by["retido"]["val_cont_congelado"], 2) == 1000.0
        assert sorted(by["aguardando"]["ambientes"]) == sorted([ids[0], ids[1]])
        assert round(by["aguardando"]["val_cont_congelado"]
                     + by["retido"]["val_cont_congelado"], 2) == 2000.0    # soma exata (#5)
        assert mod_retido.listar_sinais(db, "RET_b") == []                 # sinais confirmados
    finally:
        db.close()


def test_confirmar_sem_sinal_erro(app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_c", 2)
    db = app_db.get_session()
    try:
        ok, erro, _ = mod_retido.confirmar(db, "RET_c", None, {ids[0]: 1.0, ids[1]: 1.0}, 2.0, None)
        assert ok is False and "sinaliz" in (erro or "").lower()
    finally:
        db.close()


def test_confirmar_todos_retidos_erro(app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_d", 2)
    db = app_db.get_session()
    try:
        mod_retido.sinalizar(db, "RET_d", ids, None); db.commit()
        ok, erro, _ = mod_retido.confirmar(db, "RET_d", None, {ids[0]: 1.0, ids[1]: 1.0}, 2.0, None)
        assert ok is False                                                 # nada a desmembrar
    finally:
        db.close()


def test_endpoint_sinalizar_e_permissao(http_client_factory, app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_ep", 2)
    op = _login(http_client_factory, "cons_l1")                            # operador tem registrar_medicao
    st, b = op.post("/api/projetos/RET_ep/retido/sinalizar",
                    {"pool_ambiente_ids": [ids[1]], "motivo": "obra"})
    assert st == 200 and b["marcados"] == [ids[1]]
    # operador NÃO confirma (exige 'autorizar' = gerência)
    assert op.post("/api/projetos/RET_ep/retido/confirmar", {})[0] == 403
