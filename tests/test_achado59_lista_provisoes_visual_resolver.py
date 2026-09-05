# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-59, Passo 4 — DECIDIDO pelo Marcelo (05/09): a tela Lista
de Provisões (`_reconProvTabelaHtml`) tem duas correções, família do C6/LP-19 e antecipação da
LP-13 (desenho já FECHADO em 05/09, docs/db/LISTA_PARALELA.md):

1. "As colunas do canto direito saíram do formato" — mesma classe do C6 (docs/db/
   TAREFA_PERCURSO_0209.md): coluna estreita pro tamanho da fonte com um valor negativo/longo
   ("R$ -64.043,46") quebrando em duas linhas. Conserto idêntico ao C6: `white-space:nowrap`.
2. O veredito era TEXTO — um link `<a>` que navegava pra Fila. Vira botão "Resolver" que abre o
   box NA PRÓPRIA LINHA (nunca navega), com as opções vindas do SERVIDOR
   (`vereditos_validos_para_saldo`, ACHADO-41) — nunca fixas na tela.

Prova por CAPTURA (mesmo padrão do C6/B5) + asserções de DOM/CSS computado."""
import os

import pytest

NOME_BANCO_ESPERADO = "orizon_e2e"


@pytest.fixture(scope="module")
def servidor_e2e():
    import socket
    import subprocess
    import sys
    import time
    import urllib.request

    TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO
    REPO = os.path.join(os.path.dirname(__file__), "..")

    def porta_livre():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    porta = porta_livre()
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
        except Exception:
            proc.kill()


@pytest.fixture
def page(page):
    page.set_default_timeout(15000)
    return page


_PROVS = """[
  {"codigo": "2.1.04.06", "nome": "Custo de Fábrica", "tipo": "C",
   "provisionado": 64043.46, "efetivado": 0.0, "saldo": -64043.46, "resolvido": 0.0,
   "resolvido_liquido": 0.0, "saldo_aberto": -64043.46, "exige_veredito": true,
   "resolucao_tipo": null, "resolucao_destino_nome": null,
   "vereditos_validos": ["absorver", "adiar"],
   "data_prevista": null, "vencido": false}
]"""


def _login(page, base):
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")


def test_coluna_de_valor_negativo_longo_nao_quebra_linha(page, servidor_e2e, tmp_path):
    base = servidor_e2e
    _login(page, base)

    page.evaluate("""(provs) => {
      const div = document.createElement('div');
      div.id = 'lista-prov-container';
      div.style.cssText = 'position:fixed;top:0;left:0;background:var(--bg,#0b0d12);padding:16px;'
        + 'z-index:999999;width:640px';
      document.body.appendChild(div);
      div.innerHTML = _reconProvTabelaHtml(JSON.parse(provs), {editavel:false});
    }""", _PROVS)
    page.wait_for_selector("#lista-prov-container table")

    out_dir = os.environ.get("ORIZON_E2E_SCREENSHOT_DIR") or str(tmp_path)
    screenshot_path = os.path.join(out_dir, "achado59_passo4_coluna_sem_quebra.png")
    page.locator("#lista-prov-container").screenshot(path=screenshot_path)
    print("\nACHADO-59 Passo 4 — prova por captura salva em:", screenshot_path)

    saldo_cel = page.locator("#lista-prov-container table td", has_text="-64.043,46").first
    assert saldo_cel.evaluate("el => getComputedStyle(el).whiteSpace") == "nowrap", (
        "célula de Saldo sem white-space:nowrap — família do C6/LP-19, valor negativo/longo pode quebrar")


def test_resolver_abre_box_na_linha_com_opcoes_do_servidor_e_nao_navega(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)

    page.evaluate("""(provs) => {
      window._reconProvProj = 'ProjetoMockPasso4';
      const div = document.createElement('div');
      div.id = 'lista-prov-container';
      div.style.cssText = 'position:fixed;top:0;left:0;background:var(--bg,#0b0d12);padding:16px;'
        + 'z-index:999999;width:900px';
      document.body.appendChild(div);
      div.innerHTML = _reconProvTabelaHtml(JSON.parse(provs), {editavel:true});
    }""", _PROVS)
    page.wait_for_selector("#lista-prov-container table")

    urlAntes = page.url
    box = page.locator("#lista-prov-container [data-prov-box='2.1.04.06']")
    assert box.is_hidden(), "o box de veredito tem que começar escondido"

    page.locator("#lista-prov-container button", has_text="Resolver").click()
    assert box.is_visible(), "'Resolver' tem que abrir o box NA PRÓPRIA LINHA — nunca navegar"
    assert page.url == urlAntes, "clicar em 'Resolver' não pode navegar (era um link <a> antes)"

    # só os vereditos que o SERVIDOR mandou (absorver, adiar) — nunca fixos na tela
    # (ACHADO-41): "Receber"/"Encerrar" não vieram em vereditos_validos.
    assert box.locator("button", has_text="Absorver").count() == 1
    assert box.locator("button", has_text="Adiar").count() == 1
    assert box.locator("button", has_text="Receber").count() == 0
    assert box.locator("button", has_text="Encerrar").count() == 0

    page.locator("#lista-prov-container button", has_text="Resolver").click()
    assert box.is_hidden(), "'Resolver' de novo tem que fechar o box (alterna)"
