# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0109.md, item B2 — os aceites do ACHADO-36.

`showToast(msg, true)` não caía no canto: já redirecionava para `mostrarErroModal`, um overlay
manuscrito próprio (`#erro-modal-overlay`, cores/z-index hard-coded, comentário de 2026-08-17) —
FORA do design system. `avisoPopup`/`confirmarPopup` já existem e são o componente correto (mesmo
`_popupOverlay`, foco, Esc/Enter). O conserto é roteamento: trocar a chamada, não criar componente.
Este teste prova, num navegador de verdade, que o módulo financeiro/provisões usa o popup do design
system — não o overlay manuscrito — e que nenhum `showToast(..., true)` sobrou no módulo."""
import os
import re
import socket
import subprocess
import sys
import time

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO, "static", "index.html")

# Faixa do módulo financeiro/provisões levantada para o B2 (funções recon*/filaProv*/efetivar*/
# resolver*/folha*/contasPagar*/pagarFornecedor*/provisao*/lancamento*/rateio*/periodo*).
FAIXA_INICIO, FAIXA_FIM = 14655, 16700


def _texto_do_modulo():
    with open(INDEX_HTML, encoding="utf-8") as f:
        linhas = f.readlines()
    return "".join(linhas[FAIXA_INICIO - 1:FAIXA_FIM])


def test_nenhum_showtoast_de_erro_sobra_no_modulo_financeiro():
    """Levantamento do B2: 200 `showToast(..., true)` no sistema todo (v2026.09.01-beta1); o
    módulo financeiro/provisões (onde 'mensagem não vista vira lançamento errado') tem que estar
    zerado. Regex atravessa quebra de linha — pega qualquer chamada dividida em duas linhas."""
    achados = re.findall(r"showToast\([^;]*,\s*true\)", _texto_do_modulo())
    assert achados == [], "showToast(..., true) ainda no módulo financeiro/provisões:\n%r" % achados


def test_contagem_total_de_showtoast_de_erro_no_sistema():
    """Reporta o número pedido no documento — não é aceite de conserto, é a medição do item 2.

    A regex usa `[^;]*`, que atravessa quebra de linha — por isso a contagem certa não é a de
    `grep` (linha a linha; perde a chamada de main.py:4211/index.html que quebra em duas linhas).
    200 no candidato v2026.09.01-beta1 (antes desta rodada); 36 convertidos nesta rodada
    (financeiro/provisões, B1+B2); 164 seguem no resto do sistema — higiene, fica pra depois."""
    with open(INDEX_HTML, encoding="utf-8") as f:
        conteudo = f.read()
    total = len(re.findall(r"showToast\([^;]*,\s*true\)", conteudo))
    assert total == 164, "a contagem mudou — reveja o número reportado (%d)" % total


# ── E2E de navegador: prova que o popup É o do design system, não o overlay manuscrito ──────────

NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO


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


def test_recusa_do_modulo_financeiro_usa_o_popup_do_design_system(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    # Sem projeto ativo — abrirReconciliacaoProjeto() recusa ("Abra um projeto.").
    assert page.evaluate("() => !!window.projetoAtivo") is False
    page.evaluate("() => abrirReconciliacaoProjeto()")

    # É o avisoPopup do design system (_popupOverlay: <h4> com título, botão data-act="ok") —
    # não o #erro-modal-overlay manuscrito (achado de 2026-08-17, ícone ⚠, botão OK sem data-act).
    page.wait_for_selector('h4:has-text("Financeiro")', timeout=5000)
    page.wait_for_selector("text=Abra um projeto.", timeout=5000)
    assert page.locator("#erro-modal-overlay").count() == 0, (
        "isto é o overlay manuscrito antigo — o conserto do B2 é sair dele")
    ok_btn = page.locator('[data-act="ok"]')
    assert ok_btn.count() == 1
    ok_btn.click()
    page.wait_for_selector('h4:has-text("Financeiro")', state="detached", timeout=5000)
