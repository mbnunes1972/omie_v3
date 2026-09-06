# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-29 Fatia C.

Relato do Marcelo: o nome do projeto "não aparece em lugar nenhum dentro do ciclo". Medido no
print: o painel de Provisões se identificava como "Orçamento #6" — número de orçamento, não nome
de projeto. Levantamento (antes de consertar, per instrução): dos 8 painéis abertos de dentro do
ciclo, 4 já identificavam o projeto corretamente (Auditoria Contábil, Cronograma, Equipe,
Reconciliação/Recebíveis — cada um com "Projeto <nome>" ou campo dedicado) e 4 não identificavam
nada, ou identificavam errado — Provisões (AF, "Orçamento #N"), Mapa de Atribuições, Retenção,
Grupo de Acompanhamento (nenhum nome). Este teste prova que os 4 corrigidos passam a mostrar o
nome do projeto — mockando o fetch (mesmo padrão de `test_aceite_b6_fila_tooltips.py`) pra não
precisar montar um projeto inteiro pela tela; o nome é setado ANTES do fetch resolver (síncrono,
no topo de cada função), então funciona mesmo com a resposta mockada/vazia."""
import os
import socket
import subprocess
import sys
import time

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
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


def _login(page, base):
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")


def test_mapa_atribuicoes_identifica_projeto(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    page.evaluate("() => { mapaAbrir('ProjetoFatiaC'); }")
    page.wait_for_selector("#modal-mapa[style*='flex']")
    assert page.locator("#mapa-proj-nome").inner_text() == "ProjetoFatiaC"


def test_retencao_identifica_projeto(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    page.evaluate("() => { retidoAbrir('ProjetoFatiaC'); }")
    page.wait_for_selector("#modal-retido[style*='flex']")
    assert page.locator("#retido-proj-nome").inner_text() == "ProjetoFatiaC"


def test_grupo_acompanhamento_identifica_projeto(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    # #modal-contatos-conf é filho de #page-02 (comment em test_e2e_browser_ciclo_overlay.py) —
    # sem navegar pro Ciclo de um projeto a página pode estar escondida; checa o texto direto
    # (attached), não a visibilidade da página inteira, que não é o objeto deste teste.
    page.evaluate("() => { projetoAtivo = {nome_safe: 'ProjetoFatiaC'}; abrirModalContatosConf(); }")
    page.wait_for_selector("#contatos-conf-proj-nome", state="attached")
    assert page.locator("#contatos-conf-proj-nome").text_content() == "ProjetoFatiaC"


def test_provisoes_af_identifica_projeto_alem_do_orcamento(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)
    page.evaluate("""() => {
      projetoAtivo = {nome_safe: 'ProjetoFatiaC'};
      const div = document.createElement('div');
      div.id = 'prov-inline-slot';
      div.style.cssText = 'position:fixed;top:0;left:0;z-index:999999;background:#111;padding:10px';
      document.body.appendChild(div);
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/api/orcamentos/') && String(url).includes('/provisoes')) {
          return Promise.resolve({json: () => Promise.resolve({ok: true, provisoes: {}})});
        }
        return fetchOriginal(url, opts);
      };
      abrirProvisoes(6, '8');
    }""")
    page.wait_for_selector("#prov-inline-slot p")
    texto = page.locator("#prov-inline-slot p").first.inner_text()
    assert "ProjetoFatiaC" in texto, texto
    assert "Orçamento #6" in texto, texto   # continua mostrando o orçamento — é informação real, não erro
