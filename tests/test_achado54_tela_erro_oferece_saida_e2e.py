# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-54, causa 2 — `_renderCardEmissaoNfe` (static/index.html)
travava a linha do XML assim que existia QUALQUER emissão, mesmo em `erro`: só "Consultar" (e
"Cancelar" se autorizado), nunca uma saída. Regra do Marcelo: "caso a nota não seja carregada ela
precisa sair da tela, não precisa ficar nenhum registro de um documento que não foi processado."

Prova por NAVEGADOR: chama `_renderCardEmissaoNfe` de verdade (função pura, lê o global `_nfe15`)
com uma emissão em `erro` e confirma que o HTML devolvido tem "Emitir NF-e da Loja" e "Remover" —
não apenas "Consultar". Controle: emissão `autorizado` continua travada (só Consultar/Cancelar)."""
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


def _render(page, emissao):
    # `_nfe15` é `let` no topo do script (não `window._nfe15`) — atribuir sem prefixo pra
    # mutar o mesmo binding léxico que `_renderCardEmissaoNfe` lê.
    return page.evaluate("""(emissao) => {
      _nfe15 = { fabrica_xmls: [{id: 777, nome_original: 'nota_fabrica.xml', emissao: emissao}] };
      return _renderCardEmissaoNfe({status: 'em_andamento'}, false);
    }""", emissao)


def test_emissao_em_erro_oferece_nova_tentativa_e_remover(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    html = _render(page, {"status": "erro", "ref": "NFE-x-1", "mensagem_sefaz":
                          "Rejeição: Duplicidade de NF-e com diferença na Chave de Acesso"})
    assert "Emitir NF-e da Loja" in html, html
    assert "Remover" in html, html
    assert "removerDocCiclo" in html and "777" in html
    assert "Tentativa anterior" in html and "Duplicidade" in html


def test_emissao_autorizada_continua_travada_so_consultar_cancelar(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    html = _render(page, {"status": "autorizado", "ref": "NFE-x-1", "chave": "CH-1"})
    assert "Emitir NF-e da Loja" not in html, html
    assert "Consultar" in html
    assert "Cancelar" in html


def test_emissao_processando_continua_travada_sem_saida(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    html = _render(page, {"status": "processando", "ref": "NFE-x-1"})
    assert "Emitir NF-e da Loja" not in html, html
    assert "Consultar" in html
