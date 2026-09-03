"""Task 4 — Trava de qualidade no upload do XML + quarentena.

Teste 1: verifica que avaliar_qualidade_xml devolve "bloqueado" para XML ruim (sanidade).
Teste 2: verifica que um PoolAmbiente com qa_selo="bloqueado" não pode ser adicionado
         a um orçamento (POST /orcamentos/<oid>/ambientes/<pid> → 409, ok=False).
"""

def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# XML com acréscimo quase zero (0,009% — abaixo do limiar de "sem acréscimo" de
# avaliar_qualidade_xml, 0,01%) → 🔴 na quarentena de qualidade. ACHADO-45 (DECIDIDO 02/09) trouxe
# uma recusa DURA e separada pra markup <= 1 EXATO (item vendido no custo ou abaixo) — este
# fixture tem que ficar ACIMA dela (margem absoluta de R$9,99, bem além da tolerância de R$0,005
# do novo hard-reject) pra continuar testando a quarentena, não a recusa nova.
XML_RUIM = '''<PROJECT DESCRIPTION="Teste" DATE="01/01/2026"><CATEGORY DESCRIPTION="X"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="100000" TOTAL="100000"><MARGINS><ORDER TOTAL="100000"/><BUDGET TOTAL="100009.99"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def test_upload_xml_ruim_marca_bloqueado(http_client_factory, seed, app_db, monkeypatch):
    from mod_qualidade_xml import avaliar_qualidade_xml
    from integracoes.promob_grupos import ler_xml_str
    amb = ler_xml_str("ruim.xml", XML_RUIM)
    itens = [it for g in amb.get("grupos", []) for it in g.get("itens", [])]
    r = avaliar_qualidade_xml(itens)
    assert r["qa_selo"] == "bloqueado"   # sanidade do dado de teste


def test_ambiente_bloqueado_nao_entra_em_orcamento(http_client_factory, seed, app_db):
    # cria um pool ambiente 🔴 e um orçamento na loja 1; tentar vincular deve falhar
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Ruim", nome_exibicao="Ruim",
                             xml_path="x", ambientes_json="{}", budget_total=100, order_total=100,
                             qa_selo="bloqueado", qa_pct_sem_acrescimo=100.0)
    db.add(pa); db.commit(); pid = pa.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    # rota real: POST /orcamentos/<oid>/ambientes/<pid> (pid no path, sem /api, sem body)
    st, body = c.post(f"/orcamentos/{seed['orcamento_l1_id']}/ambientes/{pid}", {})
    assert body.get("ok") is False


def test_upload_real_grava_selo_bloqueado(http_client_factory, seed, app_db):
    """E2E: subir um XML ruim pelo endpoint real grava qa_selo='bloqueado' no PoolAmbiente."""
    import urllib.request as _urllib_req
    import json as _json

    # 1. Garantir briefing completo para Proj_L1 (seed só cria briefing para Proj_L2)
    db = app_db.get_session()
    from datetime import datetime as _dt
    bf = app_db.Briefing(
        cliente_id=seed["cliente_l1_id"],
        projeto_nome="Proj_L1",
        data_atendimento=_dt(2026, 1, 1),
        tipo_imovel="apartamento",
        budget_declarado=50000.0,
        categoria_proposta="completo",
        data_entrega_desejada="2026-12-01",
        flexibilidade_prazo="sim",
    )
    db.add(bf); db.commit(); db.close()

    # 2. Login como dir_l1 e capturar cookie de sessão
    c = _login(http_client_factory, "dir_l1")
    base = c.base
    cookie = c.cookie

    # 3. Montar corpo multipart/form-data com campo "xmls" e filename único para evitar
    #    colisão com o PoolAmbiente "Ruim" criado manualmente no teste anterior
    boundary = b"----TestBoundary12345"
    xml_bytes = XML_RUIM.encode("utf-8")
    filename = b"RuimE2E.xml"
    nome_base = "RuimE2E"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="xmls"; filename="' + filename + b'"\r\n'
        b"Content-Type: text/xml\r\n"
        b"\r\n"
        + xml_bytes + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    ct = b"multipart/form-data; boundary=" + boundary

    # 4. POST para /projetos/Proj_L1/pool
    req = _urllib_req.Request(
        base + "/projetos/Proj_L1/pool",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", ct.decode())
    if cookie:
        req.add_header("Cookie", cookie)

    try:
        resp = _urllib_req.urlopen(req, timeout=5)
        status, raw = resp.status, resp.read()
    except _urllib_req.URLError as e:
        if hasattr(e, "code"):
            status, raw = e.code, e.read()
        else:
            raise

    data = _json.loads(raw) if raw else {}
    assert data.get("ok") is True, f"Upload falhou: {data}"
    assert data.get("acao") == "criado", f"Esperava acao='criado', obteve: {data}"

    # 5. Verificar que o PoolAmbiente criado tem qa_selo='bloqueado'
    db2 = app_db.get_session()
    pa = (
        db2.query(app_db.PoolAmbiente)
        .filter_by(projeto_id="Proj_L1", nome=nome_base)
        .order_by(app_db.PoolAmbiente.id.desc())
        .first()
    )
    db2.close()
    assert pa is not None, f"PoolAmbiente '{nome_base}' não encontrado no banco"
    assert pa.qa_selo == "bloqueado", (
        f"Esperava qa_selo='bloqueado', obteve qa_selo={pa.qa_selo!r}"
    )


def test_override_libera_ambiente(http_client_factory, seed, app_db):
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="R2", nome_exibicao="R2", xml_path="x",
                             ambientes_json="{}", budget_total=100, order_total=100,
                             qa_selo="bloqueado", qa_pct_sem_acrescimo=100.0)
    db.add(pa); db.commit(); pid = pa.id; db.close()
    c = _login(http_client_factory, "dir_l1")          # diretor: aprovar_financeiro
    st, body = c.post(f"/api/pool/{pid}/qa-override", {"motivo": "ambiente cortesia"})
    assert st == 200 and body["ok"]
    st2, b2 = c.post(f"/orcamentos/{seed['orcamento_l1_id']}/ambientes/{pid}", {})
    assert b2.get("ok") is not False                   # agora entra


def test_override_exige_perfil_e_motivo(http_client_factory, seed, app_db):
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="R3", nome_exibicao="R3", xml_path="x",
                             ambientes_json="{}", budget_total=100, order_total=100, qa_selo="bloqueado")
    db.add(pa); db.commit(); pid = pa.id; db.close()
    # dir_l1 tem aprovar_financeiro — valida que motivo vazio é rejeitado
    cc = _login(http_client_factory, "dir_l1")
    st_nomotivo, b = cc.post(f"/api/pool/{pid}/qa-override", {"motivo": ""})
    assert b.get("ok") is False                        # motivo obrigatório


def test_override_negado_sem_permissao(http_client_factory, seed, app_db):
    """operador sem aprovar_financeiro recebe 403 ao tentar qa-override.
    (super_admin virou god-mode em 2026-07-16 — tem aprovar_financeiro —, então o
    ator negativo passou a ser o operador cons_l1, que legitimamente não tem a capacidade.)"""
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="R4", nome_exibicao="R4", xml_path="x",
                             ambientes_json="{}", budget_total=100, order_total=100,
                             qa_selo="bloqueado", qa_pct_sem_acrescimo=100.0)
    db.add(pa); db.commit(); pid = pa.id; db.close()
    # operador (cons_l1) não tem aprovar_financeiro; o endpoint só faz esse gate de capacidade
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post(f"/api/pool/{pid}/qa-override", {"motivo": "tentativa"})
    assert body.get("ok") is False
    assert st == 403
    # confirma que o campo não foi preenchido
    db2 = app_db.get_session()
    pa2 = db2.query(app_db.PoolAmbiente).filter_by(id=pid).first()
    db2.close()
    assert pa2.qa_override_por_id is None
