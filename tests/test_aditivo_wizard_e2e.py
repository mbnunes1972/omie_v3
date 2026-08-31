# -*- coding: utf-8 -*-
"""E2E do Termo Aditivo com modelo jurídico + wizard (spec 2026-07-22): contrato →
Revisão de PE (complemento com ambiente ALTERADO + ambiente INCLUÍDO) → defaults dos
modais → preview sem persistir → geração com bloco editado → congelamento do modelo →
2º aditivo após assinatura (ordinal SEGUNDO). Valores conferidos ao centavo:

    contrato: Cozinha 80.000 / arq 10% repassado → VAVA = 88.888,89 (fator 1/0,9)
    compl Cozinha venda 84.000 → diferença = 84.000/0,9 − 88.888,89 = 4.444,44
    Adega NOVA (fora do contrato) venda 9.000 → fator fallback 1/0,9 → diferença 10.000,00
    total: 88.888,89 → 103.333,33 (Δ 14.444,44)
"""
import json
import os
import urllib.request as _urllib_req


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _setup(app_db, seed):
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
    # ambiente NOVO, fora do orçamento contratado — vira INCLUSÃO no aditivo
    pa2 = app_db.PoolAmbiente(nome="Adega", nome_exibicao="Adega", xml_path="fake/adega.xml",
                              ambientes_json="{}", projeto_id=nome,
                              budget_total=9000.0, order_total=3000.0)
    db.add(pa2); db.flush()
    pa2.renegociar_pe = 1
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="Loja",
                                     cpf="000.000.000-00", hash_sha256="x"))
    db.commit()
    pid, pid2 = pa.id, pa2.id
    db.close()
    import main as _main
    pdir = os.path.join(_main.PROJETOS_DIR, nome)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "projeto.json"), "w", encoding="utf-8") as f:
        json.dump({"nome_projeto": nome}, f)
    return nome, pid, pid2


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


def _post_raw(c, path, payload):
    """POST JSON devolvendo (status, bytes, content_type) — p/ resposta PDF do preview."""
    data = json.dumps(payload).encode("utf-8")
    req = _urllib_req.Request(c.base + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie:
        req.add_header("Cookie", c.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=60)
        return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except _urllib_req.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def test_aditivo_wizard_ponta_a_ponta(http_client_factory, seed, app_db):
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")

    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    _upsert_compl(app_db, nome, pid2, venda=9000.0, cfo=3000.0)

    # sem orçamento de complemento negociado, os defaults nem existem
    st, body = c.get(f"/api/projetos/{nome}/aditivo/defaults")
    assert st == 400, body

    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    assert abs(body["orcamento"]["valor_total"] - 14444.44) < 0.05, body["orcamento"]

    # 1) defaults dos modais — ao centavo
    st, body = c.get(f"/api/projetos/{nome}/aditivo/defaults")
    assert st == 200 and body["ok"], body
    assert body["ordinal"] == "PRIMEIRO"
    d = body["defaults"]
    assert "Cozinha: R$ 93.333,33" in d["lista_integral"]
    assert "Adega: R$ 10.000,00" in d["lista_integral"]          # incluído entra no rol
    assert "Adega: R$ 10.000,00" in d["inclusoes"]
    assert "não promove a exclusão" in d["exclusoes"]            # default negativo automático
    assert "passa de R$ 88.888,89 para R$ 103.333,33" in d["valores"]
    assert "diferença de R$ 14.444,44" in d["valores"]
    assert body["blocos_salvos"] is None                          # nunca gerado

    # 2) preview: PDF sem persistir NADA
    st, raw, ct_hdr = _post_raw(c, f"/api/projetos/{nome}/aditivo", {"preview": True})
    assert st == 200 and raw[:4] == b"%PDF", (st, ct_hdr, raw[:80])
    assert "pdf" in ct_hdr
    st, body = c.get(f"/api/projetos/{nome}/aditivo")
    assert st == 200 and body["aditivo"] is None, body            # nada persistido

    # 3) geração com bloco EDITADO; modelo é SEMEADO do contrato_template (nenhum importado)
    editado = "CONSIDERANDO QUE o CLIENTE solicitou apenas a inclusão da Adega;"
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"blocos": {"considerandos": editado}})
    assert st == 200 and body["ok"], body
    a = body["aditivo"]
    assert a["num_aditivo"].startswith("TA") and a["tem_pdf"] is True
    assert a["dados"]["ordinal"] == 1
    blocos = a["dados"]["blocos"]
    assert blocos["considerandos"] == editado                     # editado persistido
    assert "Adega: R$ 10.000,00" in blocos["inclusoes"]           # demais = default
    assert abs(a["dados"]["diferenca"] - 14444.44) < 0.05
    import mod_documentos
    db = app_db.get_session()
    mv_seed = mod_documentos.ativo_de(db, seed["loja1_id"], "termo_aditivo")
    assert mv_seed is not None                                    # seed aconteceu
    aditivo_row = db.get(app_db.Aditivo, a["id"])
    versao_congelada = aditivo_row.modelo_versao_id
    assert versao_congelada == mv_seed.id
    db.close()

    # 4) congelamento: ativar modelo NOVO e regerar → versão congelada NÃO muda
    db = app_db.get_session()
    mv2 = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                      "# OUTRO MODELO [NUM_ADITIVO]\n", "v2.md", None)
    mod_documentos.ativar(db, mv2.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    db = app_db.get_session()
    assert db.get(app_db.Aditivo, body["aditivo"]["id"]).modelo_versao_id == versao_congelada
    db.close()

    # 5) assina loja+cliente → protegido contra regerar; "novo" cria o SEGUNDO
    primeiro_id = body["aditivo"]["id"]
    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = json.dumps({"tipo": "avista", "entrada_valor": 1.0})
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st == 200, body
    assert body["status"] == "assinado"

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 403, body                                        # regerar assinado: nunca

    st, body = c.get(f"/api/projetos/{nome}/aditivo/defaults")
    assert st == 200 and body["ordinal"] == "SEGUNDO", body       # wizard do próximo

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"novo": True})
    assert st == 200 and body["ok"], body
    segundo = body["aditivo"]
    assert segundo["id"] != primeiro_id
    assert segundo["dados"]["ordinal"] == 2
    assert segundo["status"] == "para_assinatura"
    db = app_db.get_session()
    assert db.get(app_db.Aditivo, primeiro_id).status == "assinado"   # o 1º fica intacto
    db.close()
