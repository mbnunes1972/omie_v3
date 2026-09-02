# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0109.md, item B5 — o aceite do ACHADO-40.

A célula decidida da coluna Decisão (`peConciliacaoRender`, static/index.html) era um flex livre
(`<span>rótulo</span> valor <button>alterar</button>`) — rótulo, valor e botão caíam em posições
diferentes a cada linha, conforme o comprimento do texto ("Manter" vs "Estornar", R$50 vs
R$123.456,78). Sub-colunas de largura FIXA.

Defeito visual — o TAREFA_PERCURSO_0109.md pede prova por CAPTURA, não por asserção de DOM.
Este teste tira um screenshot real (salvo em disco, path impresso no relatório) E, pra ter um
sinal de PASS/FAIL automatizável pro controle negativo, mede a posição horizontal (bounding box)
da sub-coluna de valor nas duas linhas — mesma posição = alinhado."""
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


_MOCK_JSON = """{
  "ok": true, "markup": 2.0, "etapa_status": "pendente", "motivo_reprovacao": null, "rev2_aprovada": true,
  "fases": [{"parcela_id": null, "completa": true, "faltam": [], "ambientes": [
    {"ambiente": "Cozinha", "pool_ambiente_id": 1, "pe_carregado": true,
     "cfo_original": 10000.0, "cfo_pe": 10050.0, "diferenca": 50.0, "diferenca_valor_contrato": 100.0,
     "decisao": {"tipo_decisao": "manter", "valor_aprovado": 100.0}},
    {"ambiente": "Suíte Master", "pool_ambiente_id": 2, "pe_carregado": true,
     "cfo_original": 40000.0, "cfo_pe": 30000.0, "diferenca": -10000.0, "diferenca_valor_contrato": -20000.0,
     "decisao": {"tipo_decisao": "estornar", "valor_aprovado": 123456.78}}
  ]}]
}"""


def test_coluna_decisao_alinha_entre_linhas_de_texto_diferente(page, servidor_e2e, tmp_path):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    # `pe-cmp-container-af` só entra no DOM quando o card de Aprovação Financeira do Ciclo é
    # desenhado (projeto aberto de verdade) — o achado é sobre a RENDERIZAÇÃO da célula, não sobre
    # navegação, então cria o alvo direto, visível, sem depender do fichário do Ciclo.
    page.evaluate("""(mockJson) => {
      projetoAtivo = {nome_safe: 'projeto-inexistente-so-para-o-mock'};
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/pe/conciliacao') && !String(url).includes('/pe/conciliacao/')) {
          return Promise.resolve({json: () => Promise.resolve(JSON.parse(mockJson))});
        }
        return fetchOriginal(url, opts);
      };
      const div = document.createElement('div');
      div.id = 'pe-cmp-container-af';
      div.style.cssText = 'position:fixed;top:0;left:0;background:var(--bg,#0b0d12);padding:24px;' +
        'z-index:999999;width:820px';
      document.body.appendChild(div);
    }""", _MOCK_JSON)
    page.evaluate("() => { peConciliacaoRender(); }")
    page.wait_for_selector("#pe-cmp-container-af table")

    out_dir = os.environ.get("ORIZON_E2E_SCREENSHOT_DIR") or str(tmp_path)
    screenshot_path = os.path.join(out_dir, "achado40_coluna_decisao_alinhada.png")
    page.locator("#pe-cmp-container-af").screenshot(path=screenshot_path)
    print("\nACHADO-40 (B5) — prova por captura salva em:", screenshot_path)

    valores = page.locator("#pe-cmp-container-af tr td:last-child span:nth-of-type(2)")
    assert valores.count() == 2, "as duas linhas decididas têm que ter a sub-coluna de valor"
    x0 = valores.nth(0).bounding_box()["x"]
    x1 = valores.nth(1).bounding_box()["x"]
    assert abs(x0 - x1) < 0.5, (
        "sub-coluna de VALOR desalinhada entre 'Manter'/100,00 e 'Estornar'/123.456,78 — "
        "x0=%.2f x1=%.2f" % (x0, x1))
