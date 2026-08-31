# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — ACHADO-27 (docs/db/ACHADOS_CONTABEIS.md).

Achado do Marcelo em Homologação, 31/08/2026, não é regressão desta rodada: na tela de
Negociação, com um plano de pagamento longo (ex. Cartão de Crédito, 15x), o card da tabela de
ambientes — que carrega a linha de ações Salvar/Aprovar/Imprimir — colapsava para ~1px e sumia
da tela, com os três botões ainda existindo no DOM ("visíveis" por getComputedStyle/
is_visible() ingênuo, mas recortados pelo pai a ponto de nenhum clique real alcançá-los).

Causa (medida antes de mexer, não suposta): `#page-02.active` é `display:flex;
flex-direction:column` com altura ditada pela viewport. Pela regra do flexbox, o mínimo
automático de um item no eixo principal usa o tamanho do CONTEÚDO — EXCETO quando o item tem
`overflow` diferente de `visible`, caso em que o mínimo automático vira 0 e o item pode encolher
além do próprio conteúdo. `#neg-tbl-ambientes-card` é o ÚNICO filho direto de `#page-02` com
`overflow:hidden` (só para cortar os cantos arredondados da tabela — nada a ver com altura); os
demais filhos (`.neg-top`, os cinco `.mod-panel` `#plano-*`) não têm overflow declarado e por
isso já recusam encolher abaixo do conteúdo — medido: `#plano-cartao` sozinho com 15 parcelas
mede ~847px e não se move. O card de ambientes era o único candidato a absorver o excesso, e
absorvia até perto de zero. Fix: `flex-shrink:0` só nele (static/index.html) — tira o item do
cálculo de encolhimento, sem tocar no `overflow:hidden` que ele usa para outra coisa.

Por que este teste TEM que ser de navegador: nenhuma chamada de API vê isto — o bug é puramente
de layout CSS, renderizado só pelo motor do navegador (foi exatamente o que o F2-2 mostrou sobre
achados de tela vs. achados de HTTP). Critério de aceite: projeto com plano de 15 parcelas, o
card dos ambientes com altura > 0 (de verdade — não recortada) e os três botões (Salvar/Aprovar/
Imprimir) CLICÁVEIS de fato, não só presentes no DOM.
"""
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


def test_plano_15_parcelas_nao_colapsa_card_de_ambientes(page, servidor_e2e):
    base = servidor_e2e

    # ── Login + projeto com um ambiente real (mesmo XML mínimo do E2E terminal) ────────────
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", "Layout Negociacao E2E")
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
    xml_path = "/tmp/e2e_layout_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("text=140.000,00", timeout=10000)

    # ── O gatilho do achado: modalidade com plano longo (Cartão de Crédito, 15x) ────────────
    page.select_option("#neg-pagamento", "cartao_credito")
    page.wait_for_timeout(500)
    page.select_option("#neg-parcelas", "15")
    page.wait_for_timeout(800)

    # ── Critério de aceite 1: altura de verdade, não recortada pelo pai ─────────────────────
    altura = page.evaluate(
        "() => document.getElementById('neg-tbl-ambientes-card').getBoundingClientRect().height")
    assert altura > 100, (
        "Card de ambientes com altura suspeita (%.1fpx) — ACHADO-27 pode ter voltado: "
        "#page-02 é flex e o card é o único filho com overflow:hidden, exposto ao colapso "
        "automático de min-height quando o plano de pagamento é longo." % altura)

    # ── Critério de aceite 2: os três botões CLICÁVEIS de fato (não só is_visible()) ────────
    # is_visible() não pega isto — um elemento recortado por overflow:hidden do pai reporta
    # display/visibility normais; só um clique de verdade (que exige estar na área visível e
    # não coberto) prova a diferença. Ordem: Salvar e Imprimir antes de Aprovar, que abre um
    # modal e mudaria o estado da tela para os cliques seguintes.
    page.click("#btn-salvar-orcamento")
    page.wait_for_selector("text=Orçamento salvo", timeout=5000)

    with page.expect_popup():
        page.click("#btn-imprimir-orcamento")

    page.click("#btn-aprovar-orcamento")
    page.wait_for_selector("#modal-aprovacao-overlay", timeout=5000)
