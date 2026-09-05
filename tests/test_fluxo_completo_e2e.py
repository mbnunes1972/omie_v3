"""E2E do início ao fim — fluxo comercial + financeiro, contra o servidor HTTP real.

Percorre: login → negociação (motor + margem real) → Out_Forn → ciclo → contrato (Venda) →
Provisões (Venda → Rev 1 Concorda → Rev 2 Revisa) → consistência/staleness → isolamento (IDOR).

Notas:
- `test_fluxo_completo_inicio_ao_fim` exercita o efeito do contrato (gravar a "Venda" das
  provisões) chamando diretamente o MESMO hook que o handler de geração usa após persistir o
  contrato (`main._registrar_provisao_venda`), sem passar pela rota HTTP de contrato — mais
  simples para este fluxo, que já é focado em negociação/provisões. A geração REAL via rota HTTP
  (PDF direto, WeasyPrint, sem LibreOffice) é coberta por `test_contrato_real_geracao_e_assinatura`.
- O upload de XML de ambiente é coberto por `test_qualidade_upload_e2e`; aqui o ambiente é montado
  direto no banco (PoolAmbiente), como nos demais e2e financeiros.
"""
import json
import os
import pytest


@pytest.fixture
def contratos_dir(tmp_path):
    """Redireciona CONTRATOS_DIR para um temp (hermético) — a geração real escreve o .pdf ali,
    sem poluir a pasta CONTRATOS do repo. Restaura no teardown."""
    import mod_contrato
    orig = mod_contrato.CONTRATOS_DIR
    mod_contrato.CONTRATOS_DIR = str(tmp_path / "contratos")
    os.makedirs(mod_contrato.CONTRATOS_DIR, exist_ok=True)
    yield mod_contrato.CONTRATOS_DIR
    mod_contrato.CONTRATOS_DIR = orig


def _setup_cenario(app_db, seed):
    """Cenário comercial no banco (idempotente): taxas financeiras da loja, cadastro completo do
    cliente, 1 ambiente com valor, forma de pagamento A Vista e desconto zero no orçamento do seed."""
    import mod_provisoes
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        cfg = mod_provisoes.config_financeira_default()
        cfg["defaults_negociacao"]["carga_trib_pct"] = 8.0
        cfg["provisoes"]["frete_fab_pct"] = 3.0
        cfg["provisoes"]["com_adm_pct"] = 5.0
        loja.config_financeira_json = json.dumps(cfg)

        # cadastro do cliente completo (exigido para gerar contrato)
        cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
        cli.email = "cliente@exemplo.com"; cli.telefone = "(11) 99999-0000"
        cli.cep = "01310-100"; cli.logradouro = "Av. Paulista"; cli.numero = "1000"
        cli.bairro = "Bela Vista"; cli.cidade = "São Paulo"; cli.estado = "SP"
        cli.inst_mesmo_residencial = 1

        # ambiente (idempotente: só adiciona se ainda não houver)
        ja = db.query(app_db.OrcamentoAmbiente).filter_by(
            orcamento_id=seed["orcamento_l1_id"]).first()
        if not ja:
            pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                                     nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                                     budget_total=90000.0, order_total=40000.0)
            db.add(pa); db.flush()
            db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                            pool_ambiente_id=pa.id, desconto_individual_pct=0.0))

        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        orc.desconto_pct = 0.0
        # ACHADO-18 (docs/db/TAREFA_ACHADO18.md, passo 9): gerar contrato agora exige valor_total >
        # 0 — o cenário direto no banco (idempotente, sem passar pelo recálculo real) precisa dar
        # esse valor ele mesmo, como um projeto real teria.
        if not (orc.valor_total or 0) > 0:
            orc.valor_total = 90000.0
        orc.forma_pagamento = json.dumps({
            "tipo": "avista", "nome_forma": "A Vista", "entrada_valor": 10000,
            "entrada_data": "2026-07-01", "entrada_forma": "pix", "total_cliente": 90000.0,
            "parcelas": [{"num": 1, "data": "2026-07-20", "valor": 80000.0, "forma": "pix"}]})
        db.commit()
    finally:
        db.close()


def test_fluxo_completo_inicio_ao_fim(app_db, seed, projetos_dir, http_client_factory):
    _setup_cenario(app_db, seed)
    oid = seed["orcamento_l1_id"]
    c = http_client_factory()

    # 1) Login — diretor da loja 1 (tem aprovar_financeiro)
    st, _ = c.login("dir_l1", "senha123")
    assert st == 200

    # 2) Negociação: o motor calcula a cadeia e a margem real
    st, b = c.post("/api/orcamentos/%d/negociacao-preview" % oid, {})
    assert st == 200 and b["ok"], b
    s = b["sombra"]
    assert s["VBVO"] == 90000.0 and s["CFO"] == 40000.0 and s["Num_Amb"] == 1
    assert s["Val_Liq"] > 0
    assert s["Cust_Var"] > s["CFO"]          # provisões (frete fábrica etc.) entram no Cust_Var
    assert 0 < s["Marg_Cont"] < 1

    # 3) Out_Forn editável reflete no Cust_Var
    st, b = c.put("/api/orcamentos/%d/out-forn" % oid, {"out_forn": 1500})
    assert st == 200 and b["ok"] and b["sombra"]["Out_Forn"] == 1500

    # 4) Ciclo do projeto carrega (etapas)
    st, b = c.get("/api/projetos/%s/ciclo" % seed["projeto_l1"])
    assert st == 200

    # 5) [Etapa 7 — Contrato] Exercita o MESMO hook que o handler de geração chama após
    #    persistir o contrato: grava a "Venda" das provisões (a geração REAL da rota é
    #    coberta por test_contrato_real_geracao_e_assinatura).
    import main
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, oid)
        main._registrar_provisao_venda(db, orc, por_id=1)
        db.commit()
    finally:
        db.close()

    # 6) Provisões: "Venda" registrada e coerente com o cálculo atual
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert st == 200 and b["ok"], b
    prov = b["provisoes"]
    assert prov["venda"] is not None
    assert prov["rev1"] is None and prov["rev2"] is None
    assert prov["desatualizado"] is False
    itens_venda = prov["venda"]["itens"]
    assert set(itens_venda.keys()) == {
        "frete_fab", "com_adm", "com_venda", "com_med", "com_proj_exec",
        "frete_loc", "assist", "ins_loc", "prov_imp", "out_forn", "prov_mont", "prov_gar",
        # F0 (bug ①): custos adicionais + custo financeiro agora entram como linha
        "com_arq", "pro_fid", "cust_via", "brinde", "cust_esp", "custo_financeiro",
        # F2-25 Passo 2 (05/09, DECIDIDO): + Custo de Fábrica, mesma família (linha no painel)
        "custo_fabrica"}
    assert itens_venda["out_forn"] == 1500           # Out_Forn entrou na Venda
    assert itens_venda["frete_fab"] > 0              # taxa de frete fábrica da loja aplicada

    # 7) Aprovação Financeira I — Concorda: Rev 1 = cópia da Venda
    st, b = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                   {"decisao": "concorda", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and b["ok"], b
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert b["provisoes"]["rev1"]["itens"] == b["provisoes"]["venda"]["itens"]
    assert b["provisoes"]["rev1"]["decisao"] == "concorda"
    venda_cust_var = b["provisoes"]["venda"]["cust_var"]
    venda_marg = b["provisoes"]["venda"]["marg_cont"]

    # 8) Aprovação Financeira II — Revisa: edita Out_Forn; margem recalcula da base congelada
    novos = dict(b["provisoes"]["venda"]["itens"])
    novos["out_forn"] = 5000.0
    st, b = c.post("/api/orcamentos/%d/provisoes/rev2" % oid,
                   {"decisao": "revisa", "itens": novos, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and b["ok"], b
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    rev2 = b["provisoes"]["rev2"]
    assert rev2["decisao"] == "revisa"
    assert rev2["itens"]["out_forn"] == 5000.0
    assert rev2["cust_var"] > venda_cust_var          # custo maior → margem menor
    assert rev2["marg_cont"] < venda_marg

    # 9) Consistência: negociação muda APÓS a Venda → aviso de desatualizado
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, oid)
        orc.desconto_pct = 15.0
        db.commit()
    finally:
        db.close()
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert b["provisoes"]["desatualizado"] is True

    # 10) Isolamento: diretor de OUTRA loja não acessa as provisões deste orçamento
    c2 = http_client_factory()
    c2.login("dir_l2", "senha123")
    st, _ = c2.get("/api/orcamentos/%d/provisoes" % oid)
    assert st in (403, 404)


def test_contrato_real_geracao_e_assinatura(app_db, seed, projetos_dir, contratos_dir,
                                            http_client_factory, monkeypatch):
    """Geração REAL do contrato (HTML -> PDF via WeasyPrint, sempre) + assinatura das duas
    partes → contrato 'assinado', etapa 7 concluída, projeto 'fechado'."""
    _setup_cenario(app_db, seed)
    nome = seed["projeto_l1"]
    oid = seed["orcamento_l1_id"]
    c = http_client_factory()
    c.login("dir_l1", "senha123")

    # Espiona o ctx passado a gerar_pdf_contrato: a geração de PDF não expõe o HTML
    # intermediário, então reconstruímos com _montar_html_contrato p/ checar as seções
    # injetadas (ambientes/forma de pagamento) — equivalente ao antigo guard do .docx.
    import main as _main_mod
    _ctxs = []
    _orig_gerar_pdf = _main_mod.gerar_pdf_contrato

    def _gerar_pdf_espiao(contrato_id, ctx, destino=None):
        _ctxs.append(ctx)
        return _orig_gerar_pdf(contrato_id, ctx, destino=destino)

    monkeypatch.setattr(_main_mod, "gerar_pdf_contrato", _gerar_pdf_espiao)

    forma_pag = json.dumps({
        "tipo": "avista", "nome_forma": "A Vista", "entrada_valor": 10000,
        "entrada_data": "2026-07-01", "total_cliente": 90000.0,
        "parcelas": [{"num": 1, "data": "2026-07-20", "valor": 80000.0}]})

    # Gate de contatos (decisão 13): confirma antes de gerar, como o fluxo real
    c.post("/api/projetos/%s/contatos-comunicacao/confirmar" % nome, {"modo": "sem_whatsapp"})
    # 1) GERAÇÃO REAL (loja incompleta no seed → confirmar_loja_incompleta)
    st, b = c.post("/api/projetos/%s/contrato" % nome, {
        "orcamento_id": oid,
        "endereco_instalacao": "Av. Paulista, 1000 - São Paulo/SP",
        "pagamento_json": forma_pag,
        "confirmar_loja_incompleta": True,
    })
    assert st == 200 and b["ok"], b
    assert b["status"] == "para_assinatura"
    assert "aviso" not in b     # PDF sempre gerado (WeasyPrint) → sem degradação/aviso

    # 1b) PDF gravado em disco (contrato_<id>.pdf) e seção "Ambientes" com os dados do
    #     projeto (Task 4 — injeção de _ambientes) presente no HTML que o originou.
    import os as _os
    _contrato_id = b["contrato_id"]
    _pdf = _os.path.join(contratos_dir, f"contrato_{_contrato_id}.pdf")
    assert _os.path.exists(_pdf)
    with open(_pdf, "rb") as _f:
        assert _f.read(5) == b"%PDF-"
    assert len(_ctxs) == 1
    from mod_contrato import _montar_html_contrato
    _html = _montar_html_contrato(_ctxs[0])
    assert "4. Ambientes do Projeto" in _html
    assert "5. Forma de Pagamento" in _html
    assert "Cozinha" in _html   # nome do ambiente do cenário — confirma a injeção real

    # 1c) Rota de EDIÇÃO/REGENERAÇÃO (PATCH) também injeta a seção de ambientes
    #     — garante que a remoção de _ambientes em do_PATCH seja detectada (Task 4 guard).
    st, b = c.patch("/api/projetos/%s/contrato" % nome, {
        "adendo": "Observação de teste",
        "confirmar_loja_incompleta": True,
    })
    assert st == 200, b
    assert len(_ctxs) == 2
    _html2 = _montar_html_contrato(_ctxs[1])
    assert "4. Ambientes do Projeto" in _html2, "PATCH/regeneração NÃO injetou a seção de ambientes"
    assert "5. Forma de Pagamento" in _html2
    assert "Cozinha" in _html2

    # 2) Contrato persistido: status + arquivo (PDF) disponível
    st, b = c.get("/api/projetos/%s/contrato" % nome)
    assert st == 200
    assert b["contrato"]["status"] == "para_assinatura"
    assert b["contrato"]["tem_pdf"] is True
    assert b["contrato"]["arquivo_tipo"] == "pdf"

    # 3) O hook REAL de geração registrou a "Venda" das provisões
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert b["provisoes"]["venda"] is not None

    # 4) Arquivo do contrato é servível
    st, _ = c.get("/api/projetos/%s/contrato/pdf" % nome)
    assert st == 200

    # (cronograma/Fatia 2) as datas do acordo (previsão de medição + expectativa de entrega) precisam
    # estar definidas ANTES de qualquer assinatura — a trava vale desde a 1ª. Folgadas o bastante pra caber.
    st, d = c.post("/api/projetos/%s/data-entrega" % nome,
                   {"data_entrega": "2028-01-01", "previsao_medicao": "2027-06-01"})
    assert st == 200 and d["ok"], (st, d)

    # 5) ASSINATURA — loja
    st, b = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "loja", "nome": "Gerente Loja 1", "cpf": "111.444.777-35"})
    assert st == 200 and b["ok"], b
    assert b["status"] == "assinado_loja"

    # 6) ASSINATURA — cliente → 'assinado'
    st, b = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente L1", "cpf": "111.444.777-35"})
    assert st == 200 and b["ok"], b
    assert b["status"] == "assinado"

    # 7) Estado final: contrato assinado pelas 2 partes
    st, b = c.get("/api/projetos/%s/contrato" % nome)
    assert b["contrato"]["status"] == "assinado"
    assert {a["parte"] for a in b["contrato"]["assinaturas"]} == {"loja", "cliente"}

    # 8) Etapa 7 (Contrato) concluída no ciclo
    st, b = c.get("/api/projetos/%s/ciclo" % nome)
    assert st == 200
