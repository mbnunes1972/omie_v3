# -*- coding: utf-8 -*-
"""tests/test_contrato_modelo_versionado_e2e.py — Prova por EXECUÇÃO (não por leitura) de
que o binding de modelo_versao_id funciona nos DOIS call sites reais de main.py:

  1) POST /api/projetos/<nome>/contrato  (main.py ~6070) — cria/regenera o contrato.
     É o call site delicado: contrato.gerado_em era escrito ANTES do binding; se a
     reordenação feita nesta frente estivesse errada, TODO contrato pareceria "legado"
     e modelo_versao_id nunca seria fixado.
  2) PATCH /api/projetos/<nome>/contrato (main.py ~7476) — edita o adendo e regenera.
     (o handler mora dentro de do_PATCH, não do_PUT — confirmado batendo no servidor de
     verdade; ver static/index.html:13475, salvarAdendo() usa method: 'PATCH'.)

Sobe o servidor real (fixture `servidor` de conftest.py) e bate via HTTP — não usa
_ContratoFake nem chama mod_documentos/mod_contrato direto. Intercepta apenas a escrita
do PDF (WeasyPrint) para capturar o HTML renderizado sem depender de parsing de PDF.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture(scope="module")
def dados_l1(app_db, seed):
    """Completa o cliente/ambiente da Loja 1 (seed só traz o mínimo) para o contrato
    conseguir passar pelas validações de cliente/ambientes."""
    db = app_db.get_session()
    try:
        cliente = db.get(app_db.Cliente, seed["cliente_l1_id"])
        cliente.email = "cliente@teste.com"
        cliente.telefone = "(12) 90000-0000"
        cliente.logradouro = "Rua das Flores"
        cliente.numero = "100"
        cliente.bairro = "Centro"
        cliente.cidade = "São José dos Campos"
        cliente.estado = "SP"
        cliente.cep = "12200-000"

        pool = app_db.PoolAmbiente(
            projeto_id=seed["projeto_l1"], nome="cozinha", versao=1,
            nome_exibicao="Cozinha", xml_path="x.xml", ambientes_json="{}",
            budget_total=1000.0, order_total=1000.0,
        )
        db.add(pool); db.flush()
        oa = app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                      pool_ambiente_id=pool.id, ordem=1)
        db.add(oa)
        db.commit()
    finally:
        db.close()
    return seed


@pytest.fixture
def captura_html(monkeypatch):
    """Intercepta mod_contrato._montar_html_contrato: deixa a lógica real rodar (é
    exatamente o que resolve qual corpo usar) e só grava o HTML produzido, evitando
    ter que dar parse em PDF para verificar qual cláusula foi renderizada."""
    import mod_contrato
    capturas = []
    original = mod_contrato._montar_html_contrato

    def _wrapper(ctx):
        html = original(ctx)
        capturas.append(html)
        return html

    monkeypatch.setattr(mod_contrato, "_montar_html_contrato", _wrapper)
    return capturas


def test_post_contrato_novo_fixa_o_modelo_ativo_da_loja(
        app_db, dados_l1, servidor, http_client_factory, captura_html):
    """Call site 1 (main.py ~6070, POST). O contrato ct1 do seed nunca foi gerado
    (gerado_em=None, modelo_versao_id=None) — é o caso 'novo'. Antes da correção desta
    frente, gerado_em era escrito ANTES do binding; qualquer POST (mesmo o primeiro)
    faria contrato.gerado_em não ser mais None no momento em que versao_para_contrato
    olhasse — e o contrato NUNCA adotaria o modelo. Provar que modelo_versao_id fica
    fixado depois de um POST real é a prova de que a reordenação funcionou."""
    import mod_documentos
    db = app_db.get_session()
    try:
        v1 = mod_documentos.criar_versao(
            db, dados_l1["loja1_id"], "contrato",
            "# CLAUSULA PRIMEIRA\n1.1. Texto ORIGINAL da Loja 1 via E2E real.\n",
            "c.docx", 1)
        mod_documentos.ativar(db, v1.id)
        v1_id = v1.id

        contrato_antes = db.get(app_db.Contrato, dados_l1["contrato_l1_id"])
        assert contrato_antes.gerado_em is None, "pré-condição do seed: contrato nunca gerado"
        assert contrato_antes.modelo_versao_id is None
    finally:
        db.close()

    client = http_client_factory()
    status, body = client.login("dir_l1", "senha123")
    assert status == 200, body

    # Gate de contatos (decisão 13, mini-frente 2026-07-25): o ato do contrato exige a
    # confirmação explícita — aqui o teste declara "seguir sem WhatsApp", como o fluxo real.
    client.post(f"/api/projetos/{dados_l1['projeto_l1']}/contatos-comunicacao/confirmar",
                {"modo": "sem_whatsapp"})

    status, body = client.post(
        f"/api/projetos/{dados_l1['projeto_l1']}/contrato",
        {
            "orcamento_id": dados_l1["orcamento_l1_id"],
            "endereco_instalacao": "Rua das Flores, 100",
            "entrada_valor": 100.0,
            "parcelas_descricao": "1x",
            "forma_entrada": "pix",
            "forma_parcelas": "boleto",
            "pagamento_json": "",
            "confirmar_loja_incompleta": True,
        },
    )
    assert status == 200, body
    assert body["ok"] is True, body

    assert len(captura_html) == 1, "gerar_pdf_contrato deve ter chamado _montar_html_contrato 1x"
    assert "Texto ORIGINAL da Loja 1 via E2E real." in captura_html[0], \
        "o corpo renderizado devia vir do modelo ativo da loja, não do template global"

    db = app_db.get_session()
    try:
        contrato_depois = db.get(app_db.Contrato, dados_l1["contrato_l1_id"])
        assert contrato_depois.gerado_em is not None
        assert contrato_depois.modelo_versao_id == v1_id, (
            "PROVA CENTRAL: se isto for None, o binding não fixou o modelo — "
            "sinal de que gerado_em ainda está sendo escrito ANTES do binding "
            "(a regressão que esta frente existe para evitar)."
        )
    finally:
        db.close()


def test_patch_contrato_regenera_e_reproduz_a_versao_fixada(
        app_db, dados_l1, servidor, http_client_factory, captura_html):
    """Call site 2 (main.py ~7476, PATCH — edita adendo e regenera). Depende do teste
    anterior já ter fixado modelo_versao_id=v1 no contrato (mesmo módulo, fixtures
    compartilhadas). A loja troca de modelo (v2 ativo) e o PATCH tem que continuar
    reproduzindo v1 — a garantia jurídica da frente, agora provada no call site 2."""
    import mod_documentos
    db = app_db.get_session()
    try:
        v2 = mod_documentos.criar_versao(
            db, dados_l1["loja1_id"], "contrato",
            "# CLAUSULA PRIMEIRA\n1.1. Texto NOVO depois da troca (não pode vazar).\n",
            "c2.docx", 1)
        mod_documentos.ativar(db, v2.id)

        contrato = db.get(app_db.Contrato, dados_l1["contrato_l1_id"])
        assert contrato.modelo_versao_id is not None, \
            "depende do teste anterior ter fixado a versão"
        v1_id_esperado = contrato.modelo_versao_id
    finally:
        db.close()

    client = http_client_factory()
    st_login, body_login = client.login("dir_l1", "senha123")
    assert st_login == 200, body_login

    # main.py:7476 (dentro de do_PATCH, não do_PUT — o front (static/index.html:13475)
    # chama salvarAdendo() com method: 'PATCH'; verificado por execução, não por leitura
    # do nome do handler que o cerca).
    status, body = client.patch(
        f"/api/projetos/{dados_l1['projeto_l1']}/contrato",
        {"adendo": "Adendo de teste E2E", "confirmar_loja_incompleta": True},
    )
    assert status == 200, body
    assert body["ok"] is True, body

    assert len(captura_html) == 1
    assert "Texto ORIGINAL da Loja 1 via E2E real." in captura_html[0], \
        "regerar via PATCH tem que reproduzir a cláusula fixada, não a nova ativa"
    assert "Texto NOVO depois da troca" not in captura_html[0]

    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, dados_l1["contrato_l1_id"])
        assert contrato.modelo_versao_id == v1_id_esperado, \
            "PATCH não pode ter trocado a versão fixada"
    finally:
        db.close()


def test_patch_contrato_legado_regenera_no_template_global(
        app_db, seed, servidor, projetos_dir, http_client_factory, captura_html):
    """Contrato legado da Loja 2: já foi 'gerado' (simulado com gerado_em setado à
    mão, como um contrato criado antes desta feature existir), modelo_versao_id=None.
    Cria-se um modelo ativo para a Loja 2 DEPOIS — o PATCH de regeração não pode
    adotá-lo: cai no template global. Prova o ramo 'legado' de versao_para_contrato
    através do call site 2 real, com dados verdadeiros da Loja 2."""
    import json as _json
    from datetime import datetime
    import mod_documentos
    import mod_contrato

    db = app_db.get_session()
    try:
        cliente = db.get(app_db.Cliente, seed["cliente_l2_id"])
        cliente.email = "cliente2@teste.com"
        cliente.telefone = "(12) 90000-0001"
        cliente.logradouro = "Rua B"
        cliente.numero = "1"
        cliente.bairro = "Centro"
        cliente.cidade = "São José dos Campos"
        cliente.estado = "SP"
        cliente.cep = "12200-001"

        pool = app_db.PoolAmbiente(
            projeto_id=seed["projeto_l2"], nome="sala", versao=1,
            nome_exibicao="Sala", xml_path="x2.xml", ambientes_json="{}",
            budget_total=500.0, order_total=500.0,
        )
        db.add(pool); db.flush()
        oa = app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l2_id"],
                                      pool_ambiente_id=pool.id, ordem=1)
        db.add(oa)

        contrato = app_db.Contrato(
            projeto_nome=seed["projeto_l2"], orcamento_id=seed["orcamento_l2_id"],
            loja_id=seed["loja2_id"], gerado_em=datetime(2026, 1, 1),
            status="para_assinatura", num_contrato="LJ2-LEGADO-1",
        )
        db.add(contrato); db.flush()
        contrato_id = contrato.id
        db.commit()

        # o "modelo novo" só aparece DEPOIS do contrato legado já existir/ter sido gerado
        v = mod_documentos.criar_versao(
            db, seed["loja2_id"], "contrato",
            "# CLAUSULA PRIMEIRA\n1.1. Modelo novo da Loja 2 (não pode vazar p/ legado).\n",
            "c.docx", 1)
        mod_documentos.ativar(db, v.id)
    finally:
        db.close()

    client = http_client_factory()
    status, body = client.login("dir_l2", "senha123")
    assert status == 200, body

    status, body = client.patch(
        f"/api/projetos/{seed['projeto_l2']}/contrato",
        {"adendo": "", "confirmar_loja_incompleta": True},
    )
    assert status == 200, body
    assert body["ok"] is True, body

    assert len(captura_html) == 1
    assert "Modelo novo da Loja 2" not in captura_html[0], \
        "contrato legado não pode adotar o modelo novo da loja ao regerar"
    global_md = mod_contrato._carregar_md()
    if global_md.strip():
        primeira = [l for l in global_md.split("\n") if l.strip()][0]
        assert primeira[:20] in captura_html[0], \
            "sem versão fixada e já gerado -> tem que cair no template global"

    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, contrato_id)
        assert contrato.modelo_versao_id is None, \
            "legado tem que permanecer sem versão fixada"
    finally:
        db.close()
