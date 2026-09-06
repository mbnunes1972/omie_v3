# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — ACHADO-64, F2-32 Fatia 4 (docs/db/ACHADOS_CONTABEIS.md).

MEDIDO: existiam DUAS implementações do "digite o valor e o sistema deduz o desconto" — o campo
VISÍVEL #neg-total-final (herói da tela) usava `_negBaseValues`/`estrutural` (caminho legado, que
nasce vazio no EP-07 — `if(estTotal <= 0) return;` fazia o handler não fazer NADA: digitar o
valor e nada acontecer). A implementação que ENTENDIA o motor (negValorBrutoAtual → VBNO, entrada
e taxa de retenção) morava em negValorTotalConfirmar, atrelada a #neg-parcelado — um campo
ESCONDIDO (display:none), inalcançável por qualquer usuário.

Por que este teste TEM que ser de navegador: o defeito só existe no fio que liga o clique/blur do
campo VISÍVEL ao handler — nenhuma chamada de API isolada vê essa ligação (as duas funções, cada
uma sozinha, "funcionavam" nos seus próprios termos: uma sempre não fazia nada, a outra fazia,
mas em um campo que ninguém via). Critério de aceite: digitar um novo Total do Contrato no campo
VISÍVEL muda de verdade o desconto do orçamento (prova que a lógica viva foi migrada pra cá, não
só copiada e deixada morta de novo)."""
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
<PRICE TABLE="100000" TOTAL="100000"><MARGINS><ORDER TOTAL="70000"/><BUDGET TOTAL="100000"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def _sessao_teste():
    """Mesma guarda de docs/db/ESTEIRA.md (ACHADO-18): afirma o nome do banco antes de
    devolver a sessão — nunca `database.get_session()` direto num teste."""
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
    """Reseta o schema do banco PRÓPRIO do E2E (`orizon_e2e`) e sobe `python3 main.py` de
    verdade, do código atual, num subprocesso — nunca um servidor já no ar (mesma disciplina de
    tests/test_e2e_browser_conciliacao_final.py)."""
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
                    saida = proc.stdout.read()
                    raise RuntimeError("servidor E2E morreu no boot:\n" + saida)
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


def test_digitar_total_do_contrato_visivel_muda_o_desconto(page, servidor_e2e):
    base = servidor_e2e

    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", "Achado64 E2E")
    page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
    page.select_option("#bf-tipo-imovel", index=1)
    page.fill("#bf-budget", "100000")
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
    xml_path = "/tmp/e2e_achado64_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("#neg-subtotal:has-text('100.000,00')", timeout=10000)

    desc_antes = page.input_value("#neg-desconto")
    assert (float(desc_antes.replace(",", ".")) if desc_antes else 0) == 0

    # ── O gatilho do ACHADO-64: digitar no campo VISÍVEL Total do Contrato ──────────────────
    page.click("#neg-total-final")
    page.wait_for_timeout(200)
    # 90.000,00 == 90% de 100.000,00 (Bruto) — sem custo financeiro nesta modalidade padrão
    # (À Vista), então o desconto equivalente esperado é ~10%.
    page.fill("#neg-total-final", "90000,00")
    page.press("#neg-total-final", "Enter")
    page.wait_for_timeout(1200)

    desc_depois = page.input_value("#neg-desconto")
    assert desc_depois, "campo #neg-desconto ficou vazio — handler não rodou"
    valor_depois = float(desc_depois.replace(",", "."))
    assert abs(valor_depois - 10.0) < 0.5, (
        "ACHADO-64: digitar 90.000,00 no Total do Contrato visível (Bruto=100.000,00) tinha "
        "que produzir um desconto de ~10%% — leu %r. Antes do conserto este handler usava "
        "_negBaseValues (vazio no EP-07) e NUNCA FAZIA NADA (desconto ficava em 0)." % desc_depois)
    assert valor_depois != 0.0

    # ── Confirma que a tela reagiu de verdade (não só o campo escondido) ────────────────────
    avista_txt = page.inner_text("#neg-avista")
    assert "90.000,00" in avista_txt or "90.000,0" in avista_txt.replace("R$", "").strip(), (
        "Valor à Vista não bateu com o total digitado: %r" % avista_txt)
