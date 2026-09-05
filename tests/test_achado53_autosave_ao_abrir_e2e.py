# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-53 — metade "abrir não emite POST" do aceite, no
mecanismo real do navegador (não simulado). `_mpPopulando`/`_mpModoLeitura` são os dois portões
que `agendarSalvarParametros` respeita; prova aqui que, com qualquer um dos dois ligado, chamar o
agendamento (como populate faz, direto ou por efeito colateral de um toggle) NÃO dispara
`salvarParametrosAuto` nem depois do debounce (500ms) — e que, com os dois desligados (estado
normal de edição pelo usuário), o agendamento funciona como sempre funcionou."""
import os
import socket
import subprocess
import sys
import time

import pytest

NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO
REPO = os.path.join(os.path.dirname(__file__), "..")


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


def _login(page, base):
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")


def _espiar_e_agendar(page, populando, modo_leitura):
    """Instrumenta `salvarParametrosAuto` (espião), força os dois portões no estado pedido,
    chama `agendarSalvarParametros()` (o mesmo caminho que o populate do modal usa) e espera
    passar do debounce (500ms) antes de checar se o espião foi chamado."""
    return page.evaluate("""({populando, modoLeitura}) => {
      window.__chamouSalvar = false;
      const orig = window.salvarParametrosAuto;
      window.salvarParametrosAuto = function(...args) { window.__chamouSalvar = true; };
      _mpPopulando = populando;
      _mpModoLeitura = modoLeitura;
      agendarSalvarParametros();
      window.salvarParametrosAuto = orig;   // restaura logo (o timer já capturou o espião)
    }""", {"populando": populando, "modoLeitura": modo_leitura})


def _leu_chamou(page):
    page.wait_for_timeout(800)   # > 500ms do debounce
    return page.evaluate("() => window.__chamouSalvar")


def test_populando_bloqueia_o_agendamento(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    _espiar_e_agendar(page, populando=True, modo_leitura=False)
    assert _leu_chamou(page) is False


def test_modo_leitura_bloqueia_o_agendamento(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    _espiar_e_agendar(page, populando=False, modo_leitura=True)
    assert _leu_chamou(page) is False


def test_sem_nenhum_portao_o_agendamento_funciona_normalmente(page, servidor_e2e):
    """Controle: fora do populate e fora do modo leitura (edição normal do usuário), o
    agendamento continua funcionando como sempre — o conserto não emudeceu o auto-save real."""
    base = servidor_e2e
    _login(page, base)
    _espiar_e_agendar(page, populando=False, modo_leitura=False)
    assert _leu_chamou(page) is True


def test_abrir_modal_com_contrato_assinado_deixa_os_dois_portoes_no_estado_certo(page, servidor_e2e):
    """Prova o `abrirModalParams` de verdade: ao final, `_mpPopulando` volta a false (não trava a
    edição normal) e `_mpModoLeitura` fica true (contrato assinado) — o segundo portão que
    protege qualquer coisa que precise ser reaberta depois."""
    base = servidor_e2e
    _login(page, base)
    estado = page.evaluate("""() => {
      _nfe15 = { fabrica_xmls: [] };
      projetoAtivo = { nome_safe: 'sonda-53', margens: {}, ambientes: [] };
      _orcamentoAtivoId = null;
      _negSelLocal = {};
      _negBaseValues = [];
      _contratoAssinado = true;   // `let` no topo do script — não `window._contratoAssinado`
      abrirModalParams();
      return { populando: _mpPopulando, modoLeitura: _mpModoLeitura };
    }""")
    assert estado["populando"] is False
    assert estado["modoLeitura"] is True
