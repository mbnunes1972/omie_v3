# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — ACHADO-58 (docs/db/ACHADOS_CONTABEIS.md).

O Marcelo percorreu o `v2026.09.05-beta1` e os DOIS botões Remover continuam sem funcionar: o
da etapa 12 (ACHADO-49, F2-20) e o do XML da fábrica na emissão da NF-e (ACHADO-54, F2-23). Os
dois tinham teste verde e controle negativo — `tests/test_achado49_remover_silencioso_e2e.py` e
`tests/test_achado54_tela_erro_oferece_saida_e2e.py`. Nenhum dos dois está na família
`test_e2e_browser_*` (a que sobe navegador de verdade contra o próprio DOM da aplicação, usada
nos ACHADOS 25/27/32/35): o primeiro chama `removerDocCiclo(...)` DIRETO via `page.evaluate`,
pulando o botão inteiro; o segundo chama `_renderCardEmissaoNfe(...)` e confere a STRING de
HTML devolvida, sem nunca inserir no DOM real nem clicar em nada. Os dois provam a ROTA (ou a
função de render isolada), não a TELA — exatamente a classe de "verde falso" que este achado
nomeia: um erro de JavaScript em qualquer lugar da página mata o handler do clique em
silêncio, e nenhum dos dois testes anteriores enxergaria isso.

Este arquivo prova pelo NAVEGADOR de verdade: projeto criado e contrato assinado pela tela (só
isso é dinheiro/decisão de propósito, mesmo critério de `test_e2e_browser_conciliacao_final.py`);
as etapas anteriores marcadas concluídas DIRETO NO BANCO (puro "marcar como feito", nunca objeto
de achado); o documento de cada caso também semeado direto no banco; e SÓ ENTÃO o botão Remover
é localizado no DOM real e CLICADO de verdade — com `page.on("console")`/`page.on("pageerror")`
capturando qualquer erro de JS que um teste de rota nunca veria."""
import os
import socket
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REPO = os.path.join(os.path.dirname(__file__), "..")
NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO

XML_ONE_AMBIENTE = '''<PROJECT DESCRIPTION="Cozinha E2E" DATE="01/01/2026"><CATEGORY DESCRIPTION="Cozinha"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="Modulados" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="140000" TOTAL="140000"><MARGINS><ORDER TOTAL="100000"/><BUDGET TOTAL="140000"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def _sessao_teste():
    """Mesma disciplina de test_e2e_browser_conciliacao_final.py — bind PRÓPRIO em
    TEST_DB_URL, nunca database.get_session() direto num teste."""
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as conn:
        atual = conn.execute(text("SELECT current_database()")).scalar()
    if atual != NOME_BANCO_ESPERADO:
        eng.dispose()
        raise RuntimeError("Recusado: sessão de teste só abre em %r — conectou em %r."
                          % (NOME_BANCO_ESPERADO, atual))
    return sessionmaker(bind=eng)()


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor_e2e():
    porta = _porta_livre()
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "_e2e_bootstrap.py"),
                       TEST_DB_URL], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, "bootstrap do banco falhou:\n" + r.stdout + r.stderr

    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DB_URL
    env["ORIZON_PORT"] = str(porta)
    env["ORIZON_HOST"] = "127.0.0.1"
    env.pop("ORIZON_WA_TOKEN", None); env.pop("ORIZON_SMTP_PASS", None)
    proc = subprocess.Popen([sys.executable, "main.py"], cwd=REPO, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base_url = "http://127.0.0.1:%d" % porta
    try:
        import urllib.request
        ok = False
        for _ in range(60):
            try:
                urllib.request.urlopen(base_url, timeout=1)
                ok = True
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError("servidor E2E morreu no boot:\n" + proc.stdout.read())
                time.sleep(0.5)
        assert ok, "servidor E2E não respondeu em 30s"
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def page(page):
    page.set_default_timeout(15000)
    return page


def _criar_projeto_e_assinar_contrato(page, base, nome_exibicao):
    """Preâmbulo idêntico a test_e2e_browser_conciliacao_final.py até 'Contrato assinado' —
    a única parte deste fluxo que é dinheiro/decisão de propósito. Devolve o nome_safe real."""
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", nome_exibicao)
    page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
    nome_projeto = page.evaluate("() => projetoAtivo.nome_safe")

    page.select_option("#bf-tipo-imovel", index=1)
    page.fill("#bf-budget", "150000")
    page.select_option("#bf-categoria", index=1)
    page.fill("#bf-data-entrega", "2027-06-01")
    page.select_option("#bf-flexibilidade", index=1)
    page.click('button:has-text("Salvar Briefing")')
    page.wait_for_selector("#modal-briefing", state="hidden")

    page.click("#btn-novo-orc")
    page.fill("#novo-orc-nome-input", "Orçamento 1")
    page.locator("#modal-novo-orc").get_by_role("button", name="Criar", exact=True).click()
    page.wait_for_selector("#modal-novo-orc", state="hidden")
    try:
        page.wait_for_selector('[data-act="salvar"]', timeout=2000)
        page.click('[data-act="salvar"]')
    except Exception:
        pass
    page.click("#btn-novo-ambiente")
    xml_path = "/tmp/e2e_a58_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("#neg-subtotal:has-text('140.000,00')", timeout=10000)

    page.click("#btn-aprovar-orcamento")
    page.wait_for_selector("#modal-aprovacao-overlay")
    page.click('#modal-aprovacao-overlay button:has-text("Gerar Contrato")')
    deadline = time.time() + 20
    while time.time() < deadline:
        if page.locator("text=Contrato gerado").count():
            break
        clicado = False
        for sel in ('[data-act="ok"]', 'button:has-text("Confirmar contatos")',
                   'button:has-text("Gerar assim")'):
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                clicado = True
                break
        page.wait_for_timeout(300 if clicado else 400)
    page.wait_for_selector("text=Contrato gerado", timeout=10000)

    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    btn_transferir = page.locator('button:has-text("Sim, transferir")')
    if btn_transferir.count() and btn_transferir.first.is_visible():
        btn_transferir.first.click()
        page.wait_for_timeout(300)
    ciclo.locator(".ficha-tab", has_text="Contrato").first.click()
    page.wait_for_timeout(500)
    if btn_transferir.count() and btn_transferir.first.is_visible():
        btn_transferir.first.click()
        page.wait_for_timeout(300)

    page.fill("#ct-previsao-medicao", "2027-03-01")
    page.fill("#ct-data-entrega", "2027-06-01")
    page.click('button:has-text("Validar")')
    page.wait_for_timeout(500)

    with page.expect_popup():
        ciclo.get_by_role("link", name="Imprimir").first.click()
    assinatura = page.locator("#secao-assinatura-contrato")
    page.check("#conf-ct-loja")
    page.fill("#conf-ct-loja-nome", "Rep Loja E2E")
    page.fill("#conf-ct-loja-cpf", "111.444.777-35")
    page.check("#conf-ct-cliente")
    page.fill("#conf-ct-cliente-nome", "Cliente E2E")
    page.fill("#conf-ct-cliente-cpf", "111.444.777-35")
    assinatura.get_by_role("button", name="Confirmar", exact=True).click()
    page.wait_for_selector("text=Contrato assinado", timeout=10000)
    return nome_projeto


def _marcar_concluidas(nome_projeto, codigos):
    """Etapas anteriores, puro 'marcar como feito' direto no banco — mesmo critério já
    estabelecido em test_e2e_browser_conciliacao_final.py (Medição lá; aqui, tudo que precede
    a etapa sob teste e não é o objeto do achado)."""
    import database
    db = _sessao_teste()
    try:
        for cod in codigos:
            et = db.query(database.CicloEtapa).filter_by(
                projeto_nome=nome_projeto, etapa_codigo=cod).first()
            if et is None:
                et = database.CicloEtapa(projeto_nome=nome_projeto, etapa_codigo=cod)
                db.add(et)
            et.status = "concluido"
        db.commit()
    finally:
        db.bind.dispose()
        db.close()


def test_remover_etapa12_funciona_no_clique_real(page, servidor_e2e):
    base = servidor_e2e
    console_errs = []
    page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
    page_errs = []
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))

    nome = _criar_projeto_e_assinar_contrato(page, base, "E2E A58 Etapa12")
    _marcar_concluidas(nome, ["8", "9", "10", "11", "11a", "11b", "11c", "11d", "11e"])

    import database
    db = _sessao_teste()
    try:
        doc = database.CicloDocumento(projeto_nome=nome, etapa_codigo="12", tipo="implantacao_pedido_xml",
                                      arquivo_path="ciclo/12/pedido.xml", nome_original="pedido.xml")
        db.add(doc); db.commit(); doc_id = doc.id
    finally:
        db.bind.dispose()
        db.close()

    page.evaluate("() => carregarCiclo()")
    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    ciclo.locator(".ficha-tab", has_text="Conferência e Implantação do Pedido").first.click()
    page.wait_for_selector("text=pedido.xml", timeout=10000)

    botao = ciclo.locator('button:has-text("Remover")')
    assert botao.count() >= 1, "o botão Remover precisa existir no DOM real da etapa 12"
    console_errs.clear(); page_errs.clear()
    botao.first.click()

    page.wait_for_selector('h4:has-text("Remover documento")', timeout=5000)
    page.click('[data-act="ok"]')
    page.wait_for_selector("text=Documento removido da fase.", timeout=10000)
    assert page_errs == [], "erro de JS não tratado durante o clique real: %r" % page_errs

    import database as db2
    dbv = _sessao_teste()
    try:
        doc = dbv.get(db2.CicloDocumento, doc_id)
        assert doc.removido_em is not None, "o clique real tem que ter removido de verdade"
    finally:
        dbv.bind.dispose()
        dbv.close()


def test_remover_nfe_fabrica_em_erro_funciona_no_clique_real(page, servidor_e2e):
    base = servidor_e2e
    page_errs = []
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))

    nome = _criar_projeto_e_assinar_contrato(page, base, "E2E A58 Etapa15")
    _marcar_concluidas(nome, ["8", "9", "10", "11", "11a", "11b", "11c", "11d", "11e",
                              "12", "13", "14"])

    import database
    db = _sessao_teste()
    try:
        doc = database.CicloDocumento(projeto_nome=nome, etapa_codigo="15", tipo="nfe_fabrica_xml",
                                      arquivo_path="ciclo/15/nota.xml", nome_original="nota_fabrica.xml")
        db.add(doc); db.flush()
        reg = database.DocumentoFiscal(ref="NFE-%s-%d-1" % (nome, doc.id), projeto_nome=nome,
                                       tipo_documento="produto", etapa_codigo="15",
                                       fabrica_doc_id=doc.id, status="erro",
                                       mensagem_sefaz="Rejeição de teste (semeada)")
        db.add(reg); db.commit()
    finally:
        db.bind.dispose()
        db.close()

    page.evaluate("() => carregarCiclo()")
    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    ciclo.locator(".ficha-tab", has_text="Logística e Expedição").first.click()
    page.wait_for_timeout(500)
    # Sub-aba "15" dentro do grupo "13" — _fichaSelecionar é o mesmo onclick que a sub-aba usa
    # de verdade (mesmo padrão real de clique, só sem depender do texto exato/posição do span).
    page.evaluate("() => _fichaSelecionar('15')")
    page.wait_for_selector("text=nota_fabrica.xml", timeout=10000)
    page.wait_for_selector("text=Tentativa anterior", timeout=10000)   # aviso do ACHADO-54

    botao = ciclo.locator('button:has-text("Remover")')
    assert botao.count() >= 1, "o botão Remover precisa existir na linha da NF-e em erro"
    botao.first.click()

    page.wait_for_selector('h4:has-text("Remover documento")', timeout=5000)
    page.click('[data-act="ok"]')
    page.wait_for_selector("text=Documento removido da fase.", timeout=10000)
    assert page_errs == [], "erro de JS não tratado durante o clique real: %r" % page_errs
