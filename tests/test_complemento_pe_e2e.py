"""Correção da Fatia 3 (2026-07-21) — E2E HTTP: Complemento por DIFERENÇA + Aprovação do PE.

O orçamento de complemento contém APENAS a diferença por ambiente marcado:
    à_vista_compl_i = venda_XML_complemento_i × (VAVA_contratado_i / VBVA_contratado_i)
O fator é a razão do PRÓPRIO ambiente contratado (à vista ÷ bruto): descontos e carga de
custos adicionais idênticos aos negociados. Propriedade (em QUALQUER composição — ver
test_propriedade_zero_com_composicao_completa): XML idêntico ⇒ diferença ZERO.
A 11e conclui com a APROVAÇÃO DO PE assinada (documento do sistema, não mais upload).
"""
import json
import os


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _setup(app_db, seed):
    """Contrato assinado com 1 ambiente de 80k e comissão de arquiteto 10% repassada
    (Cust_Ad/VAVO = 10% exato → fator do complemento = 1/0,9)."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    proj = db.query(app_db.Projeto).filter_by(nome_safe=nome).first()
    proj.parametros_json = json.dumps({"incluir_custos": True, "comissao_arq_ativa": True,
                                       "comissao_arq_pct": 10.0, "carga_trib": 0.0})
    pa = app_db.PoolAmbiente(nome="Cozinha", nome_exibicao="Cozinha", xml_path="fake/coz.xml",
                             ambientes_json="{}", projeto_id=nome,
                             budget_total=80000.0, order_total=30000.0)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    pa.renegociar_pe = 1
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="Loja",
                                     cpf="000.000.000-00", hash_sha256="x"))
    db.commit()
    pid = pa.id
    db.close()
    import main as _main
    pdir = os.path.join(_main.PROJETOS_DIR, nome)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "projeto.json"), "w", encoding="utf-8") as f:
        json.dump({"nome_projeto": nome}, f)
    return nome, pid, oid


def _upsert_compl(app_db, nome, pid, venda, cfo=30000.0):
    db = app_db.get_session()
    reg = (db.query(app_db.ArquivoPE)
             .filter_by(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_compl").first())
    if reg is None:
        reg = app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_compl")
        db.add(reg)
    reg.valor_venda = venda
    reg.valor_atualizado = cfo
    db.commit(); db.close()


def test_complemento_por_diferenca_ponta_a_ponta(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")

    # contrato: VAVA = 80.000/0,9 = 88.888,89 (arq 10% repassado); p = 10%; fator = 1/0,9
    # 1) PROPRIEDADE: XML de complemento idêntico ao do contrato ⇒ diferença ZERO
    _upsert_compl(app_db, nome, pid, venda=80000.0)
    st, body = c.get(f"/api/projetos/{nome}/pe/complemento/comparativo")
    assert st == 200 and body["ok"], body
    l = body["linhas"][0]
    assert abs(l["vava_contratado"] - 88888.89) < 0.05
    assert abs(l["diferenca"]) < 0.05, l          # idêntico → zero
    assert abs(body["resumo"]["pct_custos_adicionais"] - 10.0) < 0.05

    # 2) complemento real: venda 84.000 → diferença = 84.000/0,9 − 88.888,89 = 4.444,44
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.get(f"/api/projetos/{nome}/pe/complemento/comparativo")
    l = body["linhas"][0]
    assert abs(l["diferenca"] - 4444.44) < 0.05, l
    assert abs(l["cfo_diferenca"] - 2000.0) < 0.05

    # 3) orçamento de complemento = A DIFERENÇA (não o valor cheio)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj = body["orcamento"]
    assert aj["complemento_pe"] is True and aj["nome"] == "Complemento PE"
    assert abs(aj["valor_total"] - 4444.44) < 0.05, aj["valor_total"]
    aj_id = aj["id"]

    # 4) desconto GLOBAL não tem efeito (travado em zero no motor do complemento)…
    st, body = c.post(f"/api/orcamentos/{aj_id}/margens", {"desconto_pct": 50})
    assert st == 200, body
    db = app_db.get_session()
    assert abs((db.get(app_db.Orcamento, aj_id).valor_total or 0) - 4444.44) < 0.05
    db.close()
    # …e o desconto POR AMBIENTE aplica sobre a diferença: 4.444,44 × 0,9 = 4.000,00
    st, body = c.put(f"/api/orcamentos/{aj_id}/descontos", {"descontos": {str(pid): 10}})
    assert st == 200, body
    db = app_db.get_session()
    assert abs((db.get(app_db.Orcamento, aj_id).valor_total or 0) - 4000.0) < 0.05
    db.close()
    # contratado segue travado
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 5})
    assert st == 403, body

    # 4b) contaminação (bug do teste do usuário): o pagamento do CONTRATADO vazava para o
    # complemento via tela+auto-save — total_cliente do contrato inflava o cust_fin e o
    # Val_Cont virava o total do contrato. Um novo "Negociar Complemento" DESCONTAMINA:
    # plano zerado (padrão à vista, entrada 0) e valor_total = diferença.
    db = app_db.get_session()
    oc = db.get(app_db.Orcamento, aj_id)
    oc.forma_pagamento = json.dumps({"tipo": "tf", "total_cliente": 200000.0,
                                     "entrada_valor": 10000.0})
    db.commit(); db.close()
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    assert abs(body["orcamento"]["valor_total"] - 4000.0) < 0.05, body["orcamento"]["valor_total"]
    db = app_db.get_session()
    assert db.get(app_db.Orcamento, aj_id).forma_pagamento is None
    db.close()

    # 5) aditivo documenta a diferença NEGOCIADA
    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    d = body["aditivo"]["dados"]
    assert abs(d["valor_original"] - 88888.89) < 0.05
    assert abs(d["diferenca"] - 4000.0) < 0.05
    assert abs(d["valor_novo"] - 92888.89) < 0.05

    # 6) Aprovação do PE: exige modelo → gera → assina loja+cliente → 11e conclui
    st, body = c.post(f"/api/projetos/{nome}/aprovacao-pe", {})
    assert st == 400 and "modelo" in (body.get("erro") or "").lower(), body
    db = app_db.get_session()
    mv2 = mod_documentos.criar_versao(db, seed["loja1_id"], "aprovacao_pe",
                                      "# APROVAÇÃO DO PROJETO EXECUTIVO [NUM_APROVACAO_PE]\n"
                                      "1. Ambientes aprovados:\n[AMBIENTES_APROVADOS]\n", "a.md", None)
    mod_documentos.ativar(db, mv2.id)
    # 11a-11d concluídas (pré-requisito do gate da 11e)
    for cod, stt in (("11a", "concluido"), ("11b", "concluido"), ("11c", "concluido"),
                     ("11d", "aprovado")):
        db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo=cod, status=stt))
    db.commit(); db.close()

    st, body = c.post(f"/api/projetos/{nome}/ciclo/11e/concluir",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 400 and "Aprove" in (body.get("erro") or ""), body   # sem aprovação assinada

    st, body = c.post(f"/api/projetos/{nome}/aprovacao-pe", {})
    assert st == 200 and body["ok"], body
    ap = body["aprovacao"]
    assert ap["num_aprovacao"].startswith("AP") and ap["tem_pdf"] is True
    assert any(a["ambiente"] == "Cozinha" for a in ap["dados"]["ambientes"])
    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        st, body = c.post(f"/api/projetos/{nome}/aprovacao-pe/assinar",
                          {"parte": parte, "nome": quem, "cpf": "111.444.777-35"})
        assert st == 200, body
    assert body["status"] == "assinado"

    st, body = c.post(f"/api/projetos/{nome}/ciclo/11e/concluir",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"], body


def test_aditivo_assinado_constitui_provisao_contabil(http_client_factory, seed, app_db):
    """Achado Vera 2026-08-12: assinatura completa (loja+cliente) do Termo Aditivo não gerava
    nenhum lançamento — a diferença negociada ficava órfã. A assinatura completa agora constitui
    as provisões do complemento, mesmo mecanismo/contas do fechamento da venda original, sem gate
    de Aprovação Financeira própria (decisão do usuário — AF1/AF2 já ocorreram antes da 11e)."""
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")

    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj_id = body["orcamento"]["id"]
    assert body["orcamento"]["valor_total"] > 0

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    aditivo_id = body["aditivo"]["id"]

    # 1ª assinatura (loja): ainda sem as 2 partes → nenhum lançamento novo
    db = app_db.get_session()
    import mod_contabil
    ator = {"loja_id": seed["loja1_id"], "rede_id": None}
    ot, owner_id = mod_contabil.resolver_owner(db, ator)
    antes = db.query(app_db.Lancamento).filter_by(
        owner_tipo=ot, owner_id=owner_id, projeto_id=nome).count()
    db.close()

    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "loja", "nome": "Rep Loja", "cpf": "111.444.777-35"})
    assert st == 200 and body["status"] == "assinado_loja", body

    db = app_db.get_session()
    meio = db.query(app_db.Lancamento).filter_by(
        owner_tipo=ot, owner_id=owner_id, projeto_id=nome).count()
    db.close()
    assert meio == antes   # só 1 parte assinou — sem lançamento ainda

    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "cliente", "nome": "Cliente L1", "cpf": "222.333.444-05"})
    assert st == 200 and body["status"] == "assinado", body

    db = app_db.get_session()
    novos = (db.query(app_db.Lancamento)
               .filter_by(owner_tipo=ot, owner_id=owner_id, projeto_id=nome)
               .filter(app_db.Lancamento.ref.like("prov:aditivo:%d:%%" % aditivo_id)).all())
    db.close()
    assert len(novos) > 0, "assinatura completa do aditivo deveria constituir provisão(ões)"

    # idempotência: reassinar não é permitido pelo endpoint (já assinado), então re-chamar o
    # helper de wiring diretamente confirma que não duplica por ref
    db = app_db.get_session()
    orc_aj = db.get(app_db.Orcamento, aj_id)
    import main as _main
    _main._fin_provisoes_venda_seguro(orc_aj, nome, "prov:aditivo:" + str(aditivo_id))
    depois = (db.query(app_db.Lancamento)
                .filter_by(owner_tipo=ot, owner_id=owner_id, projeto_id=nome)
                .filter(app_db.Lancamento.ref.like("prov:aditivo:%d:%%" % aditivo_id)).count())
    db.close()
    assert depois == len(novos)   # idempotente por ref

    # A Conciliação Final (etapa 21) reusa a MESMA reconciliação (por conta × projeto, não por
    # origem/ref) — o acréscimo do aditivo precisa aparecer nela automaticamente, e some do saldo
    # em aberto assim que cada rubrica é efetivada/resolvida (pedido do usuário: o saldo final,
    # depois de tudo resolvido, tem que fechar em ZERO).
    db = app_db.get_session()
    rec_antes = mod_contabil.reconciliacao(db, ot, owner_id, projeto_id=nome)
    provs_com_saldo = [p for p in rec_antes["provisoes"] if abs(p["saldo_aberto"]) > 0.005]
    assert provs_com_saldo, "a provisão do aditivo deveria aparecer com saldo em aberto na reconciliação"
    for p in provs_com_saldo:
        mod_contabil.resolver_saldo_provisao(db, ot, owner_id, nome, p["codigo"],
                                             ref="resolve:aditivo-teste:" + p["codigo"])
    db.commit()
    rec_depois = mod_contabil.reconciliacao(db, ot, owner_id, projeto_id=nome)
    for p in rec_depois["provisoes"]:
        assert abs(p["saldo_aberto"]) < 0.01, p   # tudo resolvido → saldo zero
    db.close()


def test_complemento_sem_marcados_e_escopo(http_client_factory, seed, app_db):
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
    nome = orc.projeto_id
    for pa in db.query(app_db.PoolAmbiente).filter_by(projeto_id=nome).all():
        pa.renegociar_pe = 0
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 400 and "marcado" in (body.get("erro") or "").lower()
    c2 = _login(http_client_factory, "dir_l2")
    st, body = c2.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 404


def test_propriedade_zero_com_composicao_completa(http_client_factory, seed, app_db):
    # Adversarial (estava sendo perseguido pelo QA): a propriedade "XML idêntico ⇒ diferença zero"
    # tem que valer com TODOS os custos adicionais juntos — arq (proporcional), fidelidade,
    # viagem (rateio proporcional), brinde (rateio IGUAL — quebrava o fator único) e Custo
    # Especial (linha do orçamento — o fator único o cobraria DE NOVO). O fator por ambiente
    # (VAVA/VBVA do contratado) é exato por construção.
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    proj = db.query(app_db.Projeto).filter_by(nome_safe=nome).first()
    proj.parametros_json = json.dumps({
        "incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0,
        "fidelidade_ativa": True, "fidelidade_pct": 5.0,
        "fora_da_sede": True, "custo_viagem": 2000.0,
        "brinde_ativo": True, "brinde": 500.0,
        "custo_especial_ativo": True, "custo_especial": 1000.0, "carga_trib": 0.0})
    pas = []
    for nm, b, o in (("CozC", 80000.0, 30000.0), ("SalaC", 40000.0, 16000.0)):
        pa = app_db.PoolAmbiente(nome=nm, nome_exibicao=nm, xml_path=f"fake/{nm}.xml",
                                 ambientes_json="{}", projeto_id=nome,
                                 budget_total=b, order_total=o)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
        pa.renegociar_pe = 1
        pas.append((pa.id, b, o))
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="L",
                                     cpf="0", hash_sha256="x"))
    db.commit(); db.close()

    # XMLs de complemento IDÊNTICOS aos do contrato → diferença zero POR AMBIENTE
    for pid, b, o in pas:
        _upsert_compl(app_db, nome, pid, venda=b, cfo=o)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/projetos/{nome}/pe/complemento/comparativo")
    assert st == 200 and body["ok"], body
    minhas = [l for l in body["linhas"] if l["ambiente"] in ("CozC", "SalaC")]
    assert len(minhas) == 2
    for l in minhas:
        assert abs(l["diferenca"]) < 0.02, l    # zero por construção, em qualquer composição

    # crescimento de 10% num ambiente → diferença = 10% do à vista contratado DAQUELE ambiente
    pid0, b0, o0 = pas[0]
    _upsert_compl(app_db, nome, pid0, venda=b0 * 1.10, cfo=o0)
    st, body = c.get(f"/api/projetos/{nome}/pe/complemento/comparativo")
    l = [x for x in body["linhas"] if x["pool_ambiente_id"] == pid0][0]
    assert abs(l["diferenca"] - 0.10 * l["vava_contratado"]) < 0.05, l
