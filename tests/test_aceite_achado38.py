# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0109.md, item B3 — o aceite do ACHADO-38.

`peConciliacaoAprovar` (frontend) e `POST /ciclo/11d/aprovar` (main.py) validavam credencial
ANTES de saber se a AF2 já estava aprovada — nenhum dos dois tinha, na verdade, um `já aprovada`
explícito: `_set_etapa_status` sobrescreve o status sem checar o anterior, então uma segunda
aprovação (aba antiga, dois cliques, replay) reprocessava tudo de novo — relança
`LogAcaoGerencial`, reenvia o aviso no chat — depois de já ter pedido a senha do gerente pra nada.

Prova de ORDEM (não só de existência): a segunda chamada usa credencial INVÁLIDA. Se o estado
fosse checado primeiro, a recusa é "AF2 já aprovada" (400) — a senha errada nunca chega a ser
avaliada. Se a credencial fosse checada primeiro (o defeito), a recusa seria "Senha/perfil
inválido" (403), mascarando o estado real."""
import os
import socket
import subprocess
import sys
import time

import pytest

from tests.test_conciliacao_pe_e2e import (
    _setup, _carrega_pe, _registra_venda_baseline, _aprova_af1_af2, _login,
)


def _projeto_com_af2_aprovada(app_db, seed):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=33000.0)
    _registra_venda_baseline(app_db, oid)
    return nome, pid, oid


def test_segunda_aprovacao_recusa_pelo_estado_antes_de_avaliar_a_senha(http_client_factory, seed, app_db):
    nome, pid, oid = _projeto_com_af2_aprovada(app_db, seed)
    c = _login(http_client_factory)
    _aprova_af1_af2(c, oid)
    c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
          {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "cobrar"})

    st1, body1 = c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar",
                        {"login": "dir_l1", "senha": "senha123"})
    assert st1 == 200 and body1["ok"], body1

    # Segunda aprovação, credencial ERRADA de propósito — a recusa tem que ser sobre o ESTADO
    # (já aprovada), não sobre a senha. Prova a ORDEM: estado primeiro, credencial só depois.
    st2, body2 = c.post(f"/api/projetos/{nome}/ciclo/11d/aprovar",
                        {"login": "dir_l1", "senha": "senha_ERRADA_de_proposito"})
    assert st2 == 400, body2
    assert "já" in body2.get("erro", "").lower() and "aprovada" in body2.get("erro", "").lower(), body2

    db = app_db.get_session()
    logs = db.query(app_db.LogAcaoGerencial).filter_by(
        projeto_nome=nome, acao="pe_11d_aprovar").all()
    assert len(logs) == 1, "a segunda chamada não pode reprocessar — só um log de aprovação"
    db.close()


# ── E2E de navegador: o lado da tela do mesmo achado ────────────────────────────────────────
# `peConciliacaoAprovar()` reconfere o estado (GET /pe/conciliacao) antes de chamar
# `pedirCredenciaisGerente` — a prova de navegador é que o modal de senha NUNCA abre quando o
# estado já diz "concluído": mocka o fetch pra devolver `etapa_status:'concluido'` (não precisa
# reconstruir toda a esteira de PE/AF1/AF2/ambientes só pra isto — o achado é sobre ORDEM de
# chamada no JS, não sobre o cálculo de `fase_completa`, já coberto no teste HTTP acima).

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


def test_aprovar_af2_ja_concluida_nao_abre_modal_de_senha(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.evaluate("""() => {
      // `projetoAtivo` é `let` no escopo do script — não é propriedade de `window`, precisa da
      // atribuição nua (sem `let`/`var`) pra alcançar o binding real que a função enxerga.
      projetoAtivo = {nome_safe: 'projeto-inexistente-so-para-o-mock'};
      window._chamouAprovarEndpoint = false;
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/pe/conciliacao') && !String(url).includes('/pe/conciliacao/')) {
          return Promise.resolve({json: () => Promise.resolve({ok:true, etapa_status:'concluido', fases:[], rev2_aprovada:true})});
        }
        if (String(url).includes('/ciclo/11d/aprovar')) { window._chamouAprovarEndpoint = true; }
        return fetchOriginal(url, opts);
      };
    }""")
    # fire-and-forget: `() => peConciliacaoAprovar()` retornaria a Promise da função pro
    # `evaluate`, que ESPERA ela resolver — e ela só resolve depois do clique no popup, que ainda
    # não aconteceu. `{ peConciliacaoAprovar(); }` não retorna nada, evaluate não trava.
    page.evaluate("() => { peConciliacaoAprovar(); }")

    page.wait_for_selector("text=A AF2 já foi aprovada.", timeout=5000)
    assert page.locator("#_cred-login").count() == 0, (
        "o modal de credenciais não podia ter aberto — o estado já dizia 'concluído'")
    assert page.evaluate("() => window._chamouAprovarEndpoint") is False
    page.click('[data-act="ok"]')
