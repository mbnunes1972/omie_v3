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


def _desmembrar_direto(app_db, nome, retido_ids, pronto_ids, valores=None):
    """Cria direto no banco 1 parcela RETIDA (retido_ids) + 1 que SEGUE (pronto_ids) — atalho
    p/ os testes do gate/liberação (Fatia 2/3), sem passar pelo fluxo de confirmação. `valores`
    (dict id→valor) alimenta ParcelaAmbiente.valor_ambiente e o val_cont_congelado da parcela."""
    valores = valores or {}
    db = app_db.get_session()
    try:
        for ordem, (status, ids) in enumerate([("aguardando", pronto_ids),
                                               ("retido", retido_ids)], start=1):
            vc = sum(float(valores.get(a, 1.0)) for a in ids)
            p = app_db.ParcelaProjeto(projeto_nome=nome, ordem=ordem, status=status,
                                      fracao_val_cont=0.5, val_cont_congelado=vc)
            db.add(p); db.flush()
            for aid in ids:
                db.add(app_db.ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=aid,
                                              valor_ambiente=float(valores.get(aid, 1.0))))
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


def test_liberar_total(app_db, seed):
    """Fatia 3: a obra libera a parcela retida INTEIRA → retoma ('retido'→'aguardando'), sem repartir."""
    ids = _proj_amb(app_db, seed, "RET_lt", 2)
    _desmembrar_direto(app_db, "RET_lt", retido_ids=[ids[1]], pronto_ids=[ids[0]],
                       valores={ids[0]: 700.0, ids[1]: 300.0})
    db = app_db.get_session()
    try:
        ok, erro, afet = mod_retido.liberar(db, "RET_lt", [ids[1]]); db.commit()
        assert ok, erro
        assert afet == [{"id": afet[0]["id"], "status": "aguardando",
                         "val_cont_congelado": 300.0, "ambientes": [ids[1]]}]
        assert mod_retido.ambientes_retidos(db, "RET_lt") == set()   # nada mais retido
    finally:
        db.close()


def test_liberar_parcial_split(app_db, seed):
    """Fatia 3 (ondas): a obra libera só PARTE da parcela retida → SPLIT — liberados seguem, resto
    fica retido; Σ val_cont_congelado preservado ao centavo."""
    ids = _proj_amb(app_db, seed, "RET_lp", 3)
    _desmembrar_direto(app_db, "RET_lp", retido_ids=[ids[1], ids[2]], pronto_ids=[ids[0]],
                       valores={ids[0]: 500.0, ids[1]: 300.0, ids[2]: 200.0})   # retida = 500
    db = app_db.get_session()
    try:
        ok, erro, afet = mod_retido.liberar(db, "RET_lp", [ids[1]]); db.commit()
        assert ok, erro
        by = {p["status"]: p for p in afet}
        assert by["aguardando"]["ambientes"] == [ids[1]]
        assert by["retido"]["ambientes"] == [ids[2]]
        assert round(by["aguardando"]["val_cont_congelado"], 2) == 300.0
        assert round(by["retido"]["val_cont_congelado"], 2) == 200.0     # 500 - 300, exato
        assert mod_retido.ambientes_retidos(db, "RET_lp") == {ids[2]}
        # o gate agora libera ids[1] e ainda barra ids[2]
        assert mod_retido.gate_operacao_ambiente(db, "RET_lp", ids[1])[0] is True
        assert mod_retido.gate_operacao_ambiente(db, "RET_lp", ids[2])[0] is False
    finally:
        db.close()


def test_endpoint_liberar_permissao(http_client_factory, app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_lb", 2)
    _desmembrar_direto(app_db, "RET_lb", retido_ids=[ids[1]], pronto_ids=[ids[0]])
    op = _login(http_client_factory, "cons_l1")
    assert op.post("/api/projetos/RET_lb/retido/liberar", {"pool_ambiente_ids": [ids[1]]})[0] == 403
    ger = _login(http_client_factory, "dir_l1")                            # master = autorizar
    st, b = ger.post("/api/projetos/RET_lb/retido/liberar", {"pool_ambiente_ids": [ids[1]]})
    assert st == 200 and b["parcelas"][0]["status"] == "aguardando"


def test_fracao_reconhecivel(app_db, seed):
    """Fatia 4: a fração ELEGÍVEL a reconhecer = parcelas não retidas / total (por val_cont_congelado).
    None quando o projeto não foi desmembrado (reconhece o inteiro, legado)."""
    ids = _proj_amb(app_db, seed, "RET_fr", 3)
    db = app_db.get_session()
    try:
        assert mod_retido.fracao_reconhecivel(db, "RET_fr") is None       # sem parcela = legado
    finally:
        db.close()
    _desmembrar_direto(app_db, "RET_fr", retido_ids=[ids[2]], pronto_ids=[ids[0], ids[1]],
                       valores={ids[0]: 500.0, ids[1]: 300.0, ids[2]: 200.0})   # retido = 200 de 1000
    db = app_db.get_session()
    try:
        assert round(mod_retido.fracao_reconhecivel(db, "RET_fr"), 4) == 0.8   # 800/1000
        mod_retido.liberar(db, "RET_fr", [ids[2]]); db.commit()
        assert round(mod_retido.fracao_reconhecivel(db, "RET_fr"), 4) == 1.0   # tudo liberado
    finally:
        db.close()


def test_endpoints_isolados_por_loja(http_client_factory, app_db, seed):
    """Achado da Vera 🟡: os endpoints novos respeitam o isolamento de loja — usuário da loja 2 não
    enxerga (404) o projeto da loja 1 em /parcelas nem age nele em /retido/*."""
    ids = _proj_amb(app_db, seed, "RET_iso", 2)                     # projeto na loja 1
    outro = _login(http_client_factory, "dir_l2")                  # master da loja 2
    assert outro.get("/api/projetos/RET_iso/parcelas")[0] == 404
    assert outro.post("/api/projetos/RET_iso/retido/sinalizar",
                      {"pool_ambiente_ids": [ids[0]]})[0] == 404
    assert outro.post("/api/projetos/RET_iso/retido/confirmar", {})[0] == 404
    assert outro.post("/api/projetos/RET_iso/retido/liberar",
                      {"pool_ambiente_ids": [ids[0]]})[0] == 404


def test_endpoint_conciliar_barrado_por_retido(http_client_factory, app_db, seed):
    """Fatia 4 (achado da Vera 🔴): a Conciliação Final (etapa 21) NÃO pode fechar enquanto houver
    ambiente retido — senão reconheceria a provisão retida como sobra (receita) antes da execução."""
    ids = _proj_amb(app_db, seed, "RET_cf", 2)
    _desmembrar_direto(app_db, "RET_cf", retido_ids=[ids[1]], pronto_ids=[ids[0]])
    ger = _login(http_client_factory, "dir_l1")                            # master = passa no contábil
    st, b = ger.post("/api/projetos/RET_cf/ciclo/21/conciliar", {})
    assert st == 409 and "retido" in (b.get("erro") or "").lower()


def test_endpoint_conciliar_barrado_por_etapas_pendentes(http_client_factory, app_db, seed):
    """Achado do usuário (2026-08-08, bateria de teste da Vera): a Etapa 21 (Conciliação Final)
    não tinha NENHUM gate sequencial — só o de ambiente retido. Dava pra concluí-la (e ENCERRAR o
    projeto) com 16-20 ("Entrega no cliente".."Aprovação final") ainda pendentes; reproduzido em
    vários projetos da bateria. A Etapa 15 (NF-e) segue destravada de propósito (decisão do
    usuário) — só a Etapa 20, a imediatamente anterior na sequência canônica, precisa estar
    concluída."""
    _proj_amb(app_db, seed, "RET_seq", 1)   # sem retido — passa no gate de ambiente, cai no de etapa
    db = app_db.get_session()
    for cod in ("1", "2", "3", "4", "7", "8", "9", "10", "11", "12", "13", "14"):
        db.add(app_db.CicloEtapa(projeto_nome="RET_seq", etapa_codigo=cod, status="concluido"))
    db.commit(); db.close()

    ger = _login(http_client_factory, "dir_l1")
    st, b = ger.post("/api/projetos/RET_seq/ciclo/21/conciliar", {})
    assert st == 409
    assert "anterior" in (b.get("erro") or "").lower()
    assert "aprovação final" in (b.get("erro") or "").lower()   # nome da Etapa 20


def test_endpoint_conciliar_super_admin_com_loja_ativa_nao_da_404(http_client_factory, app_db, seed):
    """Achado de auditoria 2026-08-13: usava usuario.get("loja_id") cru pra achar o projeto —
    sempre None pra super_admin/admin_rede (que não têm loja_id PRÓPRIO, só a loja ATIVA via
    X-Loja-Ativa) — 404 "Não encontrado" indevido mesmo com uma loja corretamente selecionada.
    Com o fix, super_admin com loja ativa=loja1 chega ao MESMO gate que o usuário da própria loja
    chegaria (409 de etapa pendente) — prova que o projeto foi achado, não bloqueado por engano."""
    _proj_amb(app_db, seed, "RET_super", 1)
    db = app_db.get_session()
    for cod in ("1", "2", "3", "4", "7", "8", "9", "10", "11", "12", "13", "14"):
        db.add(app_db.CicloEtapa(projeto_nome="RET_super", etapa_codigo=cod, status="concluido"))
    db.commit(); db.close()

    sup = _login(http_client_factory, "super")
    sup.loja_ativa = seed["loja1_id"]
    st, b = sup.post("/api/projetos/RET_super/ciclo/21/conciliar", {})
    assert st == 409, b   # antes do fix: 404 "Não encontrado"
    assert "anterior" in (b.get("erro") or "").lower()


def test_endpoint_sinalizar_e_permissao(http_client_factory, app_db, seed):
    ids = _proj_amb(app_db, seed, "RET_ep", 2)
    op = _login(http_client_factory, "cons_l1")                            # operador tem registrar_medicao
    st, b = op.post("/api/projetos/RET_ep/retido/sinalizar",
                    {"pool_ambiente_ids": [ids[1]], "motivo": "obra"})
    assert st == 200 and b["marcados"] == [ids[1]]
    # operador NÃO confirma (exige 'autorizar' = gerência)
    assert op.post("/api/projetos/RET_ep/retido/confirmar", {})[0] == 403
