# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0109.md, item B6 — sem ACHADO numerado (é resposta a uma pergunta do
Marcelo, não um defeito encontrado no percurso).

O Marcelo — que DECIDIU a regra do veredito em 31/08 — não lembrava o que "não se aplica" e
"ainda vai chegar" fazem no livro. Se quem desenhou não lembra, a assistente administrativa que
usa a Fila de Provisões todo dia não tem chance nenhuma — ela é a dona real da tela. Cada botão de
veredito ganha, no tooltip (`title`), o efeito no livro — texto verbatim da tarefa."""
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


# os 4 vereditos "válidos" aqui são só pra exercitar as 4 tooltips num teste só — na Fila real
# (ACHADO-41) uma linha nunca tem os 4 ao mesmo tempo, sempre 2-3 conforme o sinal do saldo.
_MOCK_FILA = """{"ok": true, "fila": [
  {"projeto_id": "Projeto Mock", "codigo": "2.1.04.02", "nome": "Montagem",
   "provisionado": 1000.0, "efetivado": 400.0, "saldo_aberto": 600.0, "constituida_em": "2026-08-01T00:00:00",
   "vereditos_validos": ["efetivada", "encerrada_valor_menor", "nao_se_aplica", "ainda_vai_chegar"]}
]}"""


def test_cada_veredito_tem_tooltip_com_o_efeito_no_livro(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.evaluate("""(mockJson) => {
      const box = document.createElement('div');
      box.id = 'filaprov-box';
      box.style.cssText = 'position:fixed;top:0;left:0;z-index:999999;background:#111';
      document.body.appendChild(box);
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/api/financeiro/fila-provisoes') && !String(url).includes('/veredito')) {
          return Promise.resolve({json: () => Promise.resolve(JSON.parse(mockJson))});
        }
        return fetchOriginal(url, opts);
      };
    }""", _MOCK_FILA)
    page.evaluate("() => { filaProvisoesCarregar(); }")
    page.wait_for_selector("#filaprov-box button", state="attached")

    esperado = {
        "Efetivada": "provisionado",
        "Encerrada · valor menor": "custou menos",
        "Não se aplica": "NUNCA incidiu",
        "Ainda vai chegar": "IMPEDE a Conciliação Final",
    }
    for rotulo, trecho in esperado.items():
        btn = page.locator("#filaprov-box button", has_text=rotulo)
        assert btn.count() == 1, "botão '%s' não encontrado" % rotulo
        titulo = btn.get_attribute("title") or ""
        assert trecho in titulo, (
            "tooltip de '%s' não explica o efeito no livro (esperado conter %r, veio %r)"
            % (rotulo, trecho, titulo))


# ── ACHADO-41: a tela desenha só os botões que `vereditos_validos` (do backend) permite ──────

_MOCK_FILA_SOBRA = """{"ok": true, "fila": [
  {"projeto_id": "Projeto Mock", "codigo": "2.1.04.02", "nome": "Montagem",
   "provisionado": 1000.0, "efetivado": 400.0, "saldo_aberto": 600.0, "constituida_em": "2026-08-01T00:00:00",
   "vereditos_validos": ["encerrada_valor_menor", "nao_se_aplica", "ainda_vai_chegar"]}
]}"""


def test_linha_em_sobra_nao_desenha_botao_efetivada(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.evaluate("""(mockJson) => {
      const box = document.createElement('div');
      box.id = 'filaprov-box';
      box.style.cssText = 'position:fixed;top:0;left:0;z-index:999999;background:#111';
      document.body.appendChild(box);
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/api/financeiro/fila-provisoes') && !String(url).includes('/veredito')) {
          return Promise.resolve({json: () => Promise.resolve(JSON.parse(mockJson))});
        }
        return fetchOriginal(url, opts);
      };
    }""", _MOCK_FILA_SOBRA)
    page.evaluate("() => { filaProvisoesCarregar(); }")
    page.wait_for_selector("#filaprov-box button", state="attached")

    assert page.locator("#filaprov-box button", has_text="Efetivada").count() == 0, (
        "linha em SOBRA não pode oferecer 'Efetivada' — o backend recusaria")
    assert page.locator("#filaprov-box button", has_text="Encerrada").count() == 1
    assert page.locator("#filaprov-box button", has_text="Não se aplica").count() == 1
    assert page.locator("#filaprov-box button", has_text="Ainda vai chegar").count() == 1
