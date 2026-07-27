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


def _desmembrar_direto(app_db, nome, retido_ids, pronto_ids):
    """Cria direto no banco 1 parcela RETIDA (retido_ids) + 1 que SEGUE (pronto_ids) — atalho
    p/ os testes do gate operacional (Fatia 2), sem passar pelo fluxo de confirmação."""
    db = app_db.get_session()
    try:
        for ordem, (status, ids) in enumerate([("aguardando", pronto_ids),
                                               ("retido", retido_ids)], start=1):
            p = app_db.ParcelaProjeto(projeto_nome=nome, ordem=ordem, status=status,
                                      fracao_val_cont=0.5, val_cont_congelado=1.0)
            db.add(p); db.flush()
            for aid in ids:
                db.add(app_db.ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=aid))
        db.commit()
    finally:
        db.close()


def test_gate_operacao_ambiente(app_db, seed):
    """Fatia 2: parcela retida NÃO avança — o gate bloqueia operação em ambiente retido, libera
    ambiente que segue e ambiente sem parcela (legado)."""
    ids = _proj_amb(app_db, seed, "RET_g", 3)   # [0,1] seguem; [2] retido; sem parcela: nenhum aqui
    _desmembrar_direto(app_db, "RET_g", retido_ids=[ids[2]], pronto_ids=[ids[0], ids[1]])
    db = app_db.get_session()
    try:
        assert mod_retido.ambiente_retido(db, "RET_g", ids[2]) is True
        assert mod_retido.ambiente_retido(db, "RET_g", ids[0]) is False
        assert mod_retido.ambientes_retidos(db, "RET_g") == {ids[2]}
        assert mod_retido.parcela_do_ambiente(db, "RET_g", ids[1]).status == "aguardando"
        assert mod_retido.gate_operacao_ambiente(db, "RET_g", ids[2])[0] is False   # retido: barra
        assert mod_retido.gate_operacao_ambiente(db, "RET_g", ids[0])[0] is True    # segue: passa
        assert mod_retido.gate_operacao_ambiente(db, "RET_g", 999999)[0] is True    # sem parcela: passa
    finally:
        db.close()


def test_endpoint_pe_upload_barrado_por_retido(http_client_factory, app_db, seed):
    """Upload de PE num ambiente de parcela RETIDA é barrado (409) — a parcela retida não executa."""
    ids = _proj_amb(app_db, seed, "RET_pe", 2)
    _desmembrar_direto(app_db, "RET_pe", retido_ids=[ids[0]], pronto_ids=[ids[1]])
    op = _login(http_client_factory, "cons_l1")
    st, b = op.post_multipart("/api/projetos/RET_pe/pe/upload",
                              files={"arquivo": ("pe.promob", b"conteudo")},
                              fields={"pool_ambiente_id": ids[0]})
    assert st == 409 and "retido" in (b.get("erro") or "").lower()


def test_endpoint_sinalizar_e_permissao(http_client_factory, app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_ep", 2)
    op = _login(http_client_factory, "cons_l1")                            # operador tem registrar_medicao
    st, b = op.post("/api/projetos/RET_ep/retido/sinalizar",
                    {"pool_ambiente_ids": [ids[1]], "motivo": "obra"})
    assert st == 200 and b["marcados"] == [ids[1]]
    # operador NÃO confirma (exige 'autorizar' = gerência)
    assert op.post("/api/projetos/RET_ep/retido/confirmar", {})[0] == 403
