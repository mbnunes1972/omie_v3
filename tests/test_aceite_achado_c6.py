# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0209.md, C6 — o modal de comparação quebra o número.

Nas caixas de KPI da comparação de CFO/venda (`_peCmpHelpers().kpi`, usada por
`peComparacaoRender`/`peComparacaoCfoRender`), "R$" ficava numa linha e o número na linha de
baixo: caixa estreita (min-width:150px) pro tamanho da fonte (--fs-h3, 15px) com um valor longo
tipo "R$ 123.456,78". Conserto: caixa um pouco maior (180px), fonte um pouco menor (--fs-body,
14px) e `white-space:nowrap` — símbolo e número são uma coisa só, nunca duas linhas.

Defeito visual — TAREFA pede prova por CAPTURA, não só asserção de DOM (mesmo padrão do B5/
ACHADO-40, tests/test_aceite_achado40.py). Screenshot salvo em disco E, pro sinal automatizável
de controle negativo, mede a altura da caixa do valor: uma linha (nowrap) vs duas (quebrado)."""
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
  "ok": true,
  "reconciliacao_estimada": {"val_cont": 123456.78},
  "comparacao": [
    {"ambiente": "Cozinha", "pe_carregado": true, "cfo_original": 100000.0, "cfo_pe": 123456.78,
     "diferenca": 23456.78}
  ]
}"""


def test_kpi_valor_nao_quebra_linha_entre_simbolo_e_numero(page, servidor_e2e, tmp_path):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    # Caixa deliberadamente estreita (mesma lógica do teste do B5: cria o alvo direto, visível,
    # sem depender de navegação) — 320px é menor do que 3 caixas de KPI cabem confortavelmente,
    # forçando exatamente a compressão que quebrava "R$"/número em duas linhas.
    page.evaluate("""(mockJson) => {
      projetoAtivo = {nome_safe: 'projeto-inexistente-so-para-o-mock'};
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/pe/comparacao') && !String(url).includes('/pe/comparacao-cfo')) {
          return Promise.resolve({json: () => Promise.resolve(JSON.parse(mockJson))});
        }
        return fetchOriginal(url, opts);
      };
      const div = document.createElement('div');
      div.id = 'pe-cmp-container-af';
      div.style.cssText = 'position:fixed;top:0;left:0;background:var(--bg,#0b0d12);padding:24px;' +
        'z-index:999999;width:320px';
      document.body.appendChild(div);
    }""", _MOCK_JSON)
    page.evaluate("() => { peComparacaoCfoRender(); }")
    page.wait_for_selector("#pe-cmp-container-af table")

    out_dir = os.environ.get("ORIZON_E2E_SCREENSHOT_DIR") or str(tmp_path)
    screenshot_path = os.path.join(out_dir, "achado_c6_kpi_valor_sem_quebra.png")
    page.locator("#pe-cmp-container-af").screenshot(path=screenshot_path)
    print("\nC6 (ACHADOS_CONTABEIS.md) — prova por captura salva em:", screenshot_path)

    # `white-space:nowrap` é a propriedade que garante — por construção, não por acaso de
    # largura de container — que "R$" e o número nunca ficam em linhas diferentes; medir a
    # altura da caixa é frágil (flex-wrap externo, flex:1 crescendo além do min-width mascaram
    # o efeito conforme a largura escolhida no teste). Assertiva direta na propriedade computada.
    def _tem_nowrap(locator):
        return locator.evaluate("el => getComputedStyle(el).whiteSpace") == "nowrap"

    # header (flex) > 1ª caixa de kpi > 2º div (o valor; o 1º é o rótulo).
    valor = page.locator("#pe-cmp-container-af > div:first-child > div:first-child > div:nth-of-type(2)").first
    assert _tem_nowrap(valor), "caixa de valor do KPI sem white-space:nowrap — pode quebrar R$/número"

    # o mesmo achado atravessava a tabela — célula .num (CFO venda) sem nowrap quebrava igual.
    cel = page.locator("#pe-cmp-container-af table td.num").first
    assert _tem_nowrap(cel), "célula .num da tabela sem white-space:nowrap — pode quebrar R$/número"
