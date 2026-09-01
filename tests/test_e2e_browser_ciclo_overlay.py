# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — ACHADO-32 (docs/db/ACHADOS_CONTABEIS.md), item 4 de
docs/db/TAREFA_CONCILIACAO_UI.md.

Relato do Marcelo: "no painel de etapas permanece aparecendo o valor do contrato com as
parcelas de pagamento abaixo na tela... parece ser a tela que aparece na negociação e depois
fica por lá, nunca é fechada". Diagnóstico: `#ciclo-panel` é `position:absolute;inset:0` dentro
de `#page-02` — cobre a ALTURA USADA do contêiner, não a do conteúdo que TRANSBORDA. Com o Plano
de Pagamento aberto, `#page-02` fica mais alto que a tela; `.content` rola; e ao passar do fim
do fichário o operador cai na negociação, que nunca foi coberta além de uma tela de altura.

Conserto: com o Ciclo aberto, o resto de `#page-02` não fica sobreposto — fica ESCONDIDO
(`#page-02.ciclo-on > *:not(#ciclo-panel):not(.modal-overlay){display:none}`). A exceção
`.modal-overlay` é o próprio objeto deste teste: `#modal-recon-proj` é filho de `#page-02`,
aberto DE DENTRO do Ciclo (uma das telas do item 1) — escondê-lo junto quebraria a Reconciliação
do projeto."""
import os
import socket
import subprocess
import sys
import time

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO

XML_ONE_AMBIENTE = '''<PROJECT DESCRIPTION="Cozinha E2E" DATE="01/01/2026"><CATEGORY DESCRIPTION="Cozinha"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="Modulados" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="140000" TOTAL="140000"><MARGINS><ORDER TOTAL="100000"/><BUDGET TOTAL="140000"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


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


def test_ciclo_aberto_esconde_a_negociacao_por_baixo(page, servidor_e2e):
    base = servidor_e2e

    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", "Ciclo Overlay E2E")
    page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
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
    xml_path = "/tmp/e2e_ciclo_overlay_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("text=140.000,00", timeout=10000)

    # Plano de Pagamento longo — o mesmo gatilho do ACHADO-27, aqui usado só pra garantir que
    # #page-02 realmente transborda a tela (sem isso o achado nem chega a se manifestar).
    page.select_option("#neg-pagamento", "cartao_credito")
    page.wait_for_timeout(500)
    page.select_option("#neg-parcelas", "15")
    page.wait_for_timeout(800)

    # ── Abre o Ciclo — #page-02 ganha .ciclo-on ──────────────────────────────────────────────
    page.click("#btn-abrir-ciclo")
    page.wait_for_selector("#ciclo-panel.active", timeout=10000)
    assert page.evaluate("() => document.getElementById('page-02').classList.contains('ciclo-on')")

    # ── Rola .content até o fim — antes do conserto, a negociação aparecia por baixo aqui. ────
    page.evaluate("""() => {
        const c = document.querySelector('.content');
        if (c) c.scrollTop = c.scrollHeight;
    }""")
    page.wait_for_timeout(300)

    # Elementos da negociação (card de ambientes, plano de pagamento) não podem estar visíveis
    # enquanto o Ciclo está aberto — nem "existirem escondidos atrás", de verdade ocultos.
    assert not page.locator("#neg-tbl-ambientes-card").is_visible()
    assert not page.locator("#plano-cartao").is_visible()
    assert not page.locator("#btn-salvar-orcamento").is_visible()

    # ── A exceção .modal-overlay: a Reconciliação do projeto, aberta DE DENTRO do Ciclo, tem
    #    que continuar aparecendo — é uma das telas do item 1, não pode sumir junto. ──────────
    page.evaluate("() => abrirReconciliacaoProjeto()")
    page.wait_for_selector("#modal-recon-proj", state="visible", timeout=10000)
    assert page.locator("#modal-recon-proj").is_visible()

    # ── Fechar o Ciclo desfaz o esconderijo — a negociação volta a existir normalmente. ───────
    page.evaluate("() => document.getElementById('modal-recon-proj').style.display='none'")
    fechou_sem_ciclo_on = page.evaluate("""() => {
        fecharCiclo();
        return !document.getElementById('page-02').classList.contains('ciclo-on');
    }""")
    assert fechou_sem_ciclo_on
    assert page.locator("#neg-tbl-ambientes-card").is_visible()
