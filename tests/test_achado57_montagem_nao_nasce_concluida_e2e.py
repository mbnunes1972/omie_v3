# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-57 — a etapa Montagem (código interno "17", número
visual "10" no fichário) se dava por concluída sozinha. Relato + print do Marcelo (05/09,
projeto novo em Homologação): logo após a aprovação/assinatura do contrato, "Montagem"
apareceu "✓ Concluída" — e o MESMO card mostrava, ao mesmo tempo, "🔒 Conclua a etapa anterior"
e "Pendente", com a etapa anterior (Logística e Expedição) ainda em aberto. Depois, sozinha,
ela voltou a ficar em aberto.

Medido (`static/index.html`, `_statusFichario`): "17" é cabeça de grupo (`_FICHA_SUBS['17'] =
['17a']`) e, ao mesmo tempo, está marcado `toggleavel: true` — a MESMA leniência que
`_etapaSatisfeita` usa pra não travar o grupo numa subfase opcional sem pendência ("17a",
achado da Vera 2026-08-26: "toggleável sem linha nenhuma = satisfeita") se aplicava também ao
CÓDIGO-MÃE. Resultado: um projeto novo, ANTES de Montagem sequer começar (nem "17" nem "17a"
têm linha no banco ainda), tinha as duas "satisfeitas" por omissão — e `_statusFichario('17')`
devolvia 'concluida' sempre, desde a criação do projeto, até que QUALQUER linha real de "17"
nascesse (aí a leniência parava de valer e o "Concluída" sumia sozinho — exatamente o relato).

Medido em Homologação (só leitura, 05/09): `Projeto_3` e `Teste_2` têm hoje "17" com status
"pendente" e NENHUMA linha de "17a" — a condição exata do achado, ao vivo, hoje.

Conserto: a leniência do "toggleável sem linha" continua valendo pros FILHOS do grupo (17a);
a MÃE do grupo (17) sempre precisa de um status conclusivo de verdade (`STATUS_CONCLUSIVOS`),
nunca da omissão."""
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


def test_montagem_nao_nasce_concluida_projeto_novo(page, servidor_e2e):
    """Projeto novo — "17" e "17a" sem NENHUMA linha ainda (exatamente a condição real medida
    em Homologação, Projeto_3/Teste_2). `_statusFichario('17')` não pode devolver 'concluida'."""
    base = servidor_e2e
    _login(page, base)
    st = page.evaluate("""() => {
      _cicloData = {};   // nem "17" nem "17a" têm linha — projeto recém-criado
      return _statusFichario('17');
    }""")
    assert st != "concluida", "Montagem não pode nascer 'concluída' sem nenhuma linha no banco"


def test_montagem_nao_nasce_concluida_com_16_pendente(page, servidor_e2e):
    """Mesma condição, mas com a etapa anterior ("16", Entrega no cliente) explicitamente
    pendente — reproduz o card contraditório do print (Concluída + Conclua a etapa anterior +
    Pendente ao mesmo tempo): _statusFichario('17') tem que concordar com _etapaBloqueada('17')
    (bloqueada por '16' não estar concluída), não dizer 'concluida' enquanto isso."""
    base = servidor_e2e
    _login(page, base)
    resultado = page.evaluate("""() => {
      _cicloData = {'16': {status: 'pendente'}};
      return {status: _statusFichario('17'), bloqueada: _etapaBloqueada('17')};
    }""")
    assert resultado["bloqueada"] is True, resultado
    assert resultado["status"] != "concluida", (
        "card contraditório: 'Concluída' e 'conclua a etapa anterior' não podem coexistir")
    assert resultado["status"] == "nao_iniciada", resultado


def test_montagem_concluida_de_verdade_continua_reconhecida(page, servidor_e2e):
    """Controle-irmão: a leniência original (17a sem pendência não trava o grupo) continua
    funcionando quando "17" está REALMENTE concluída — não virou 'preso em andamento pra
    sempre' de novo (o problema que a exceção original resolvia, achado da Vera 2026-08-26)."""
    base = servidor_e2e
    _login(page, base)
    st = page.evaluate("""() => {
      _cicloData = {'16': {status: 'concluido'}, '17': {status: 'concluido'}};
      // "17a" sem linha nenhuma — nenhuma pendência de montagem foi aberta.
      return _statusFichario('17');
    }""")
    assert st == "concluida", "Montagem genuinamente concluída, sem pendência, tem que aparecer concluída"
