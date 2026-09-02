# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-43 — o lado da tela: `salvarParametrosAuto` (auto-save de
comissão/fidelidade) ignorava silenciosamente `d.ok===false` — o portão do ACHADO-42 recusava no
servidor e a tela não dizia nada (ACHADO-36 de novo). Prova de navegador: quando o servidor
recusa por `requer_autorizacao`, o auto-save abre o modal de credenciais (`pedirCredenciaisGerente`
— o mecanismo genérico, não um modal próprio)."""
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


def test_autosave_recusado_abre_modal_de_credenciais(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.evaluate("""() => {
      projetoAtivo = {nome_safe: 'projeto-inexistente-so-para-o-mock'};
      _orcamentoAtivoId = 1;
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/parametros')) {
          return Promise.resolve({json: () => Promise.resolve(
            {ok:false, requer_autorizacao:true, limite:10,
             erro:'Efeito composto de 45.0% excede seu limite (10%). Autorização gerencial necessária.'})});
        }
        return fetchOriginal(url, opts);
      };
    }""")
    # fire-and-forget: `salvarParametrosAuto()` (sem parênteses vazios como expressão de retorno)
    # devolveria a Promise pro evaluate, que travaria esperando o clique no modal.
    page.evaluate("() => { salvarParametrosAuto(); }")

    page.wait_for_selector("#_cred-login", timeout=5000)
    titulo = page.locator("h4", has_text="Comissão/fidelidade acima do limite")
    assert titulo.count() == 1
