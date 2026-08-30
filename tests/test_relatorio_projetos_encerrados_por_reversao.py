"""ACHADO-16 (docs/db/TAREFA_ACHADO16.md, passo 8) — o contra-controle do veredito nomeado.

Reversão de resíduo melhora a margem, então "projetos encerrados por reversão" é exatamente o
relatório que evita o veredito virar uma formalidade em três meses: lista, por projeto, o total
revertido ('encerrada_valor_menor' + 'nao_se_aplica'), ordenado do maior pro menor, com o motivo
ao lado. 'efetivada' e 'ainda_vai_chegar' não entram — não são reversão."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_relatorio_ordena_por_valor_revertido_desc_e_traz_motivo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 746; mc.seed_plano(db, ot, oid)

    # Projeto A: reversão pequena (nao_se_aplica, 50)
    mc.constituir_provisoes_fechamento(db, ot, oid, "A", {"cust_esp": 50.0}, ref_base="pf:A")
    mc.conciliar_final(db, ot, oid, "A", ref_base="cf:A", vereditos={
        "2.1.04.20": {"veredito": "nao_se_aplica", "motivo": "obra não usou Custo Especial"},
    })

    # Projeto B: reversão grande (encerrada_valor_menor, resíduo de 900 sobre 1000)
    mc.constituir_provisoes_fechamento(db, ot, oid, "B", {"custo_fabrica": 1000.0}, ref_base="pf:B")
    mc.conciliar_final(db, ot, oid, "B", ref_base="cf:B", vereditos={
        "2.1.04.06": {"veredito": "encerrada_valor_menor", "valor_efetivado": 100.0},
    })

    # Projeto C: 'efetivada' (sem sobra) — não é reversão, não deve aparecer no relatório
    mc.constituir_provisoes_fechamento(db, ot, oid, "C", {"custo_fabrica": 500.0}, ref_base="pf:C")
    mc.efetivar_provisao(db, ot, oid, "C", "2.1.04.06", 600.0, ref="ef:C")   # falta -100
    mc.conciliar_final(db, ot, oid, "C", ref_base="cf:C", vereditos={
        "2.1.04.06": {"veredito": "efetivada"},
    })

    rel = mc.relatorio_projetos_encerrados_por_reversao(db, ot, oid)
    nomes = [p["projeto_nome"] for p in rel]
    assert nomes == ["B", "A"]                        # maior reversão primeiro
    assert rel[0]["valor_revertido_total"] == 900.0
    assert rel[1]["valor_revertido_total"] == 50.0
    assert "C" not in nomes                           # 'efetivada' não é reversão

    rub_a = rel[1]["rubricas"][0]
    assert rub_a["motivo"] == "obra não usou Custo Especial"
    assert rub_a["veredito"] == "nao_se_aplica"
    rub_b = rel[0]["rubricas"][0]
    assert rub_b["veredito"] == "encerrada_valor_menor" and rub_b["valor_efetivado"] == 100.0
    db.close()


def test_endpoint_projetos_encerrados_por_reversao(http_client_factory, seed, app_db):
    nome = "RelEndpoint"
    db = app_db.get_session()
    db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"], status="fechado"))
    db.add(app_db.PoolAmbiente(projeto_id=nome, nome="A0", nome_exibicao="Amb 0",
                               xml_path="x", ambientes_json="[]"))
    db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo="20", status="concluido"))
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"cust_esp": 300.0},
                                       ref_base="pf:" + nome)
    db.commit(); db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {
        "vereditos": {"2.1.04.20": {"veredito": "nao_se_aplica", "motivo": "não incidiu"}},
    })
    assert st == 200 and body.get("ok"), body

    st, body = c.get("/api/financeiro/projetos-encerrados-por-reversao")
    assert st == 200 and body["ok"] is True
    linhas = {p["projeto_nome"]: p for p in body["projetos"]}
    assert linhas["RelEndpoint"]["valor_revertido_total"] == 300.0
    assert linhas["RelEndpoint"]["rubricas"][0]["motivo"] == "não incidiu"
