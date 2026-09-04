# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-49, causa 2 — `removerDocCiclo` fazia `return` silencioso
quando `pedirCredenciaisGerente` devolvia vazio (cancelado, ou sem a capacidade). Padrão "estado
antes da credencial" do ACHADO-38/B3, pela quinta vez: o usuário clica em Remover, cancela (ou
não tem a permissão), e nada acontece — sem aviso nenhum.

Prova por NAVEGADOR: chama `removerDocCiclo` de verdade (não mocka a função), confirma o primeiro
popup ("Remover desta fase?"), cancela o de credenciais, e prova que aparece um aviso — não
silêncio."""
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


def _preparar(page, base):
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")
    page.evaluate("""() => {
      projetoAtivo = {nome_safe: 'projeto-a49-probe'};
      // Força o modal de credenciais a aparecer (não o atalho de sessão-já-tem-a-capacidade) —
      // o achado é sobre quem CANCELA ou não tem a permissão, não sobre quem já tem.
      if (_usuarioAtual) _usuarioAtual.pode_executar_pe = false;
    }""")


def test_remover_cancelado_avisa_em_vez_de_silenciar(page, servidor_e2e):
    base = servidor_e2e
    _preparar(page, base)
    page.evaluate("() => { removerDocCiclo('11a', 999999, 'arquivo-teste.pdf'); }")

    # 1º popup: "Remover ... desta fase?" — confirma.
    titulo1 = page.locator("h4", has_text="Remover documento")
    titulo1.first.wait_for(timeout=5000)
    page.locator('[data-act="ok"]').first.click()

    # 2º popup: credenciais gerenciais — cancela.
    login_field = page.locator("#_cred-login")
    login_field.wait_for(timeout=5000)
    page.locator('[data-act="cancel"]').first.click()

    # Aceite: aparece aviso, não silêncio.
    aviso = page.locator("text=Remoção cancelada")
    aviso.wait_for(timeout=5000)
    assert aviso.count() >= 1
