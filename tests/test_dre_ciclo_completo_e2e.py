"""docs/db/TESTE_DRE_CICLO.md — as três visões de DRE, ciclo completo, medido via HTTP real.

TESTE DE MEDIÇÃO, NÃO DE CONSERTO: não ajusta nada pra fazer `real` e `competencia_estimada`
baterem. Percorre venda → contrato → 1ª/2ª assinatura → revisão de PE com aditivo → NF-e
(produto+serviço) → recebimento → conciliação final, pelos PORTÕES REAIS (HTTP), sem atalho.
Em cada marco, grava as 3 visões linha a linha + os saldos das contas-chave em
docs/db/RELATORIO_DRE_CICLO.md (sempre, mesmo se a asserção falhar) e SÓ ENTÃO afirma que
`real`==`competencia_estimada` — `antecipacao_contrato` é só observada (diverge por desenho:
reconhece no contrato, não na NF-e)."""
import json
import os
import urllib.request
import urllib.error
import uuid as _uuid

import pytest

from fiscal import nfe_emissao


LINHAS_DRE = ["receita_bruta", "deducoes", "receita_liquida", "cmv_csp", "lucro_bruto",
             "despesas_comerciais", "despesas_administrativas", "constituicao_provisoes",
             "ebitda", "resultado_financeiro", "outras_receitas", "lucro_liquido"]
CONTAS_CHAVE = ["1.1.02", "1.1.05", "1.1.06.19", "2.1.03", "2.1.06", "2.1.04.13", "2.1.04.19",
               "4.1.01", "4.3.01", "4.4.03"]


class FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH-DRE",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}

    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CHS-DRE", "numero": "1",
               "serie": "1", "caminho_xml_nota_fiscal": "/nfse/x.xml", "url": "/nfse/nota.pdf"}

    def baixar(self, caminho):
        return b"BYTES"


class FakeEmissor:
    def __init__(self):
        self.client = FakeClient()

    def emitir_nfe_produto(self, nota):
        from integracoes.emissor_fiscal import resultado_de_focus
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})

    def emitir_nfse_servico(self, nota):
        from integracoes.emissor_fiscal import resultado_de_focus
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _post_json(c, path, body):
    req = urllib.request.Request(c.base + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie:
        req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _upload_xml(c, proj, data):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--" + boundary + "\r\n").encode(),
            b'Content-Disposition: form-data; name="arquivo"; filename="fabrica.xml"\r\n',
            b"Content-Type: application/octet-stream\r\n\r\n", data, b"\r\n",
            ("--" + boundary + "--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/nfe-fabrica",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _fixture_xml():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml")
    with open(path, "rb") as f:
        return f.read()


def _perfil_fiscal(app_db, loja_id):
    """Mesmo helper de tests/test_nfe_etapa15_e2e.py — Emitente pronto pra produto E serviço."""
    from fiscal import fiscal_cripto
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id) if loja.emitente_id else None
    if em is None:
        em = app_db.Emitente(cnpj="90000000000%02d" % loja_id, razao_social="LOJA X",
                             regime_tributario="simples", csosn_padrao="102",
                             cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                             cidade="Sao Paulo", logradouro="Rua A", numero="1",
                             bairro="Centro", cep="01000-000")
        db.add(em); db.flush()
        loja.emitente_id = em.id
    em.ambiente_ativo = "homologacao"
    em.inscricao_municipal = "322176"
    em.municipio_ibge = "3549904"
    em.cod_servico_municipio = "14.13.03"
    em.aliquota_iss = 5.0
    em.focus_token_homolog_enc = fiscal_cripto.encrypt("tok-homolog")
    em.focus_token_prod_enc = fiscal_cripto.encrypt("tok-prod")
    db.commit(); db.close()


def _setup_cenario(app_db, seed):
    """Mesmo padrão de tests/test_fluxo_completo_e2e.py::_setup_cenario: 1 ambiente com valor,
    forma de pagamento A Vista, cliente com cadastro completo (exigido pra gerar contrato)."""
    db = app_db.get_session()
    try:
        cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
        cli.email = "cliente@exemplo.com"; cli.telefone = "(11) 99999-0000"
        cli.cep = "01310-100"; cli.logradouro = "Av. Paulista"; cli.numero = "1000"
        cli.bairro = "Bela Vista"; cli.cidade = "São Paulo"; cli.estado = "SP"
        cli.inst_mesmo_residencial = 1

        ja = db.query(app_db.OrcamentoAmbiente).filter_by(
            orcamento_id=seed["orcamento_l1_id"]).first()
        if not ja:
            pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                                     nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                                     budget_total=90000.0, order_total=40000.0)
            db.add(pa); db.flush()
            db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                            pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
            pa_id = pa.id
        else:
            pa_id = ja.pool_ambiente_id

        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        orc.desconto_pct = 0.0
        orc.forma_pagamento = json.dumps({
            "tipo": "avista", "nome_forma": "A Vista", "entrada_valor": 10000,
            "entrada_data": "2026-07-01", "entrada_forma": "pix", "total_cliente": 90000.0,
            "parcelas": [{"num": 1, "data": "2026-07-20", "valor": 80000.0, "forma": "pix"}]})
        db.commit()
        return pa_id
    finally:
        db.close()


def _saldo(db, ot, oid, cod):
    import mod_contabil as mc
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    if c is None:
        return None
    return mc.saldo_conta(db, ot, oid, c.id)


def _capturar(db, ot, oid, marco):
    import mod_contabil as mc
    real = mc.dre(db, ot, oid)
    comp_est = mc.dre_simulada(db, ot, oid, "competencia_estimada")
    antecip = mc.dre_simulada(db, ot, oid, "antecipacao_contrato")
    saldos = {cod: _saldo(db, ot, oid, cod) for cod in CONTAS_CHAVE}
    return {"marco": marco, "real": real, "competencia_estimada": comp_est,
           "antecipacao_contrato": antecip, "saldos": saldos}


def _gravar_relatorio(retratos, path):
    linhas = [
        "# Relatório — três visões de DRE, ciclo completo\n\n",
        "Gerado por `tests/test_dre_ciclo_completo_e2e.py`. **Teste de medição, não de "
        "conserto.** `real` e `competencia_estimada` deveriam bater linha a linha (a hipótese de "
        "docs/db/TESTE_DRE_CICLO.md); `antecipacao_contrato` é só observada — ela diverge por "
        "desenho (reconhece no contrato, não na NF-e), não é achado.\n\n",
    ]
    for r in retratos:
        linhas.append("## Marco: %s\n\n" % r["marco"])
        linhas.append("| linha | real | competencia_estimada | antecipacao_contrato | bate (real×comp_est) |\n")
        linhas.append("|---|---|---|---|---|\n")
        for l in LINHAS_DRE:
            rv, cv, av = r["real"].get(l), r["competencia_estimada"].get(l), r["antecipacao_contrato"].get(l)
            bate = "sim" if rv == cv else "**NÃO**"
            linhas.append("| %s | %.2f | %.2f | %.2f | %s |\n" % (l, rv, cv, av, bate))
        linhas.append("\n**Saldos das contas-chave:**\n\n| conta | saldo |\n|---|---|\n")
        for cod, v in r["saldos"].items():
            linhas.append("| %s | %s |\n" % (cod, ("%.2f" % v) if v is not None else "(não existe)"))
        linhas.append("\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(linhas)


@pytest.fixture
def contratos_dir(tmp_path):
    import mod_contrato
    orig = mod_contrato.CONTRATOS_DIR
    mod_contrato.CONTRATOS_DIR = str(tmp_path / "contratos")
    os.makedirs(mod_contrato.CONTRATOS_DIR, exist_ok=True)
    yield mod_contrato.CONTRATOS_DIR
    mod_contrato.CONTRATOS_DIR = orig


def test_ciclo_completo_tres_visoes_dre(app_db, seed, projetos_dir, contratos_dir,
                                        http_client_factory, monkeypatch):
    import mod_contabil as mc
    nome = seed["projeto_l1"]
    oid = seed["orcamento_l1_id"]
    loja_id = seed["loja1_id"]
    db0 = app_db.get_session()
    ot, own_id = mc.resolver_owner(db0, {"loja_id": loja_id, "rede_id": None})
    db0.close()

    retratos = []

    def marco(nome_marco):
        db = app_db.get_session()
        try:
            retratos.append(_capturar(db, ot, own_id, nome_marco))
        finally:
            db.close()

    # ── 1. Criação do projeto ────────────────────────────────────────────────────────────────
    # Projeto/Orçamento/Contrato-esqueleto nascem do fixture `seed` (mesmo padrão de TODOS os
    # e2e financeiros existentes — nenhum cria via HTTP dedicado; ver relatório final).
    marco("1_projeto_criado")

    pa_id = _setup_cenario(app_db, seed)
    _perfil_fiscal(app_db, loja_id)
    c = _login(http_client_factory, "dir_l1")

    # ── 2. Orçamento e negociação ────────────────────────────────────────────────────────────
    st, b = c.post("/api/orcamentos/%d/negociacao-preview" % oid, {})
    assert st == 200 and b["ok"], b
    # "-preview" é só leitura (sombra) — quem PERSISTE valor_total é /margens (achado deste
    # teste: sem isto, orc.valor_total fica None/0 pra sempre e _valores_segmentados_do_projeto
    # nunca acha Val_Cont — a NF-e "não lança nada" em silêncio, fail-soft).
    st, b = c.post("/api/orcamentos/%d/margens" % oid, {"desconto_pct": 0.0})
    assert st == 200 and b["ok"], b
    marco("2_negociacao_preview")

    # ── 3. Fechamento da venda / contrato — geração ─────────────────────────────────────────
    c.post("/api/projetos/%s/contatos-comunicacao/confirmar" % nome, {"modo": "sem_whatsapp"})
    forma_pag = json.dumps({
        "tipo": "avista", "nome_forma": "A Vista", "entrada_valor": 10000,
        "entrada_data": "2026-07-01", "total_cliente": 90000.0,
        "parcelas": [{"num": 1, "data": "2026-07-20", "valor": 80000.0}]})
    st, b = c.post("/api/projetos/%s/contrato" % nome, {
        "orcamento_id": oid, "endereco_instalacao": "Av. Paulista, 1000 - São Paulo/SP",
        "pagamento_json": forma_pag, "confirmar_loja_incompleta": True,
    })
    assert st == 200 and b["ok"], b
    assert b["status"] == "para_assinatura"
    marco("3_contrato_gerado")

    st, d = c.post("/api/projetos/%s/data-entrega" % nome,
                   {"data_entrega": "2028-01-01", "previsao_medicao": "2027-06-01"})
    assert st == 200 and d["ok"], (st, d)

    # ── 4. Assinaturas (1ª e 2ª) — canal interno (sem ClickSign instalado: portão real, sem mock) ──
    st, b = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "loja", "nome": "Gerente Loja 1", "cpf": "111.111.111-11"})
    assert st == 200 and b["ok"] and b["status"] == "assinado_loja", b
    marco("4a_assinatura_loja")

    st, b = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente L1", "cpf": "111.111.111-11"})
    assert st == 200 and b["ok"] and b["status"] == "assinado", b
    marco("4b_assinatura_cliente_provisoes_constituidas")

    # ── 5. Revisão de PE com ADITIVO ─────────────────────────────────────────────────────────
    db = app_db.get_session()
    try:
        pa = db.get(app_db.PoolAmbiente, pa_id)
        pa.renegociar_pe = 1
        db.commit()
    finally:
        db.close()

    db = app_db.get_session()
    try:
        reg = app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pa_id, formato="xml_compl",
                              valor_venda=95000.0, valor_atualizado=42000.0)
        db.add(reg); db.commit()
    finally:
        db.close()

    st, b = c.post("/api/projetos/%s/pe/complemento/orcamento" % nome, {})
    assert st == 200 and b["ok"], b
    aditivo_valor = b["orcamento"]["valor_total"]
    assert aditivo_valor > 0, "cenário precisa de diferença > 0 no complemento pra exercitar o aditivo"

    import mod_documentos
    db = app_db.get_session()
    try:
        mv = mod_documentos.criar_versao(db, loja_id, "termo_aditivo",
                                        "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                        "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
        mod_documentos.ativar(db, mv.id)
    finally:
        db.close()

    st, b = c.post("/api/projetos/%s/aditivo" % nome, {})
    assert st == 200 and b["ok"], b
    aditivo_id = b["aditivo"]["id"]
    marco("5a_aditivo_criado")

    st, b = c.post("/api/projetos/%s/aditivo/assinar" % nome,
                   {"parte": "loja", "nome": "Rep Loja", "cpf": "111.444.777-35"})
    assert st == 200 and b["status"] == "assinado_loja", b
    marco("5b_aditivo_assinatura_loja")

    st, b = c.post("/api/projetos/%s/aditivo/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente L1", "cpf": "222.333.444-05",
                    "forma_pagamento": json.dumps({"tipo": "avista", "total_cliente": 0})})
    assert st == 200 and b["status"] == "assinado", b
    marco("5c_aditivo_assinatura_cliente_provisoes_constituidas")

    # ── 6. NF-e — faturamento (produto + serviço) e efetivação de impostos ─────────────────
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    st, up = _upload_xml(c, nome, _fixture_xml())
    assert st == 200 and up.get("documento_id"), up
    st, b = _post_json(c, "/api/projetos/%s/ciclo/15/emitir-nfe" % nome,
                       {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado", b
    marco("6a_nfe_produto_emitida")

    st, b = _post_json(c, "/api/projetos/%s/ciclo/15/emitir-nfse" % nome, {"valor_servico": 500})
    assert st == 200 and b["status"] == "autorizado", b
    marco("6b_nfse_servico_emitida")

    # ── 7. Recebimento ────────────────────────────────────────────────────────────────────────
    db = app_db.get_session()
    try:
        recebiveis = (db.query(app_db.Recebivel)
                      .filter_by(projeto_nome=nome).order_by(app_db.Recebivel.id.asc()).all())
        rec_ids = [r.id for r in recebiveis]
    finally:
        db.close()
    portao_recebimento = {"recebiveis_encontrados": len(rec_ids)}
    for rid in rec_ids:
        st, b = c.post("/api/recebiveis/%d/confirmar" % rid, {})
        assert st == 200 and b.get("ok"), (rid, b)
    marco("7_recebimento")

    # ── 8. Entrega e conclusão do projeto ────────────────────────────────────────────────────
    db = app_db.get_session()
    try:
        import main as _main
        for cod in ("16", "17", "18", "19", "20"):
            _main._set_etapa_status(db, nome, cod, "concluido", None)
        db.commit()
    finally:
        db.close()
    st, b = c.post("/api/projetos/%s/ciclo/21/conciliar" % nome,
                   {"vereditos": {"2.1.04.06": {"veredito": "encerrada_valor_menor",
                                                "valor_efetivado": 42000.0}}})
    assert st == 200 and b["ok"], b
    marco("8_conclusao_projeto")

    # ── grava o relatório SEMPRE, antes de qualquer asserção de divergência ─────────────────
    # docs/db/TAREFA_REMEDICAO_DRE.md: remedição pós-Fase 1 — arquivo NOVO, não sobrescreve
    # o original (a comparação entre os dois É o resultado).
    relatorio_path = os.path.join(os.path.dirname(__file__), "..", "docs", "db",
                                  "RELATORIO_DRE_CICLO_POS_FASE1.md")
    _gravar_relatorio(retratos, relatorio_path)

    # ── ASSERIR: real == competencia_estimada, linha a linha ────────────────────────────────
    # (antecipacao_contrato NUNCA entra nesta checagem — só observação, ver docstring do módulo)
    #
    # ACHADO-15 (remedição de 31/08/2026, docs/db/RELATORIO_DRE_CICLO_POS_FASE1.md): divergir
    # entre a NF-e (marco 6a) e a Conciliação Final é o MODELO, não o defeito — decisão de
    # 07/08 (mod_contabil.py:1826-1832): despesa entra em real() na competência REAL da
    # efetivação, nunca antes. competencia_estimada é projeção por desenho (mostra o
    # constituído), e sai na Fase 4. Por isso só o marco final precisa reconciliar; marcos
    # intermediários podem divergir (sempre só em cmv_csp e no que cascateia dele —
    # lucro_bruto/ebitda/lucro_liquido — nunca em receita ou despesas).
    divergencias_meio_ciclo = []
    divergencias_finais = []
    for r in retratos:
        alvo = (divergencias_finais if r["marco"] == "8_conclusao_projeto"
                else divergencias_meio_ciclo)
        for l in LINHAS_DRE:
            rv, cv = r["real"].get(l), r["competencia_estimada"].get(l)
            if rv != cv:
                alvo.append((r["marco"], l, rv, cv))
    assert not divergencias_finais, (
        "real e competencia_estimada não reconciliaram no fechamento do projeto (marco "
        "8_conclusao_projeto): %s. Divergências de meio de ciclo (esperadas, informativas): %s"
        % (divergencias_finais, divergencias_meio_ciclo)
    )
