# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — ACHADO-32 (docs/db/ACHADOS_CONTABEIS.md), itens 1/2/3 de
docs/db/TAREFA_CONCILIACAO_UI.md, com as correções sobre o commit 446216b.

O F2-3 fechou `resolver-saldo-provisao` no servidor (409 pra qualquer conta fora de
`_PROV_FORA_DO_VEREDITO`) e `_reconProvTabelaHtml` continuou desenhando Efetivar/Resolver em toda
linha — nenhum teste de API pega isto, é achado de RENDERIZAÇÃO. Prova aqui, num navegador de
verdade, contra o modal de Reconciliação do projeto (`modal-recon-proj`) — um dos dois "irmãos"
editáveis que `_reconProvTabelaHtml` compartilha com a Etapa 21 (mesma função, mesmo HTML; a
Etapa 21 exige um contrato assinado só pra o BOTÃO aparecer, não pra tabela renderizar diferente).

Dois EIXOS por linha, batidos contra o JSON que o próprio endpoint devolveu (não um valor
hardcoded no teste): o SELO diz o que é verdade sobre o dinheiro (Em Aberto / Parcialmente
Efetivada / Efetivada / Resolvida / "—" pra quem nunca teve movimento nenhum); a célula de AÇÃO
diz só onde se age (Efetivar/Resolver genéricos na rota própria, link pra Fila nas demais, nada
quando já resolvida) — os dois são independentes: "2.1.04.10" (Comissão, exige_veredito=True)
prova isso ficando "Parcialmente Efetivada" no selo (tem efetivação real registrada) enquanto a
ação continua sendo só o link pra Fila (o botão genérico permanece bloqueado pra ela)."""
import os
import socket
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REPO = os.path.join(os.path.dirname(__file__), "..")
NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO


def _sessao_teste():
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as conn:
        atual = conn.execute(text("SELECT current_database()")).scalar()
    if atual != NOME_BANCO_ESPERADO:
        eng.dispose()
        raise RuntimeError("Recusado: sessão de teste só abre em %r — conectou em %r."
                          % (NOME_BANCO_ESPERADO, atual))
    return sessionmaker(bind=eng)()


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


def test_tabela_de_provisoes_respeita_os_tres_estados_do_backend(page, servidor_e2e):
    base = servidor_e2e

    # ── Projeto mínimo (não precisa de orçamento/contrato — a tabela de provisões não exige) ──
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", "Conciliacao UI E2E")
    page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
    nome_projeto = page.evaluate("() => projetoAtivo.nome_safe")
    page.select_option("#bf-tipo-imovel", index=1)
    page.fill("#bf-budget", "150000")
    page.select_option("#bf-categoria", index=1)
    page.fill("#bf-data-entrega", "2027-06-01")
    page.select_option("#bf-flexibilidade", index=1)
    page.click('button:has-text("Salvar Briefing")')
    page.wait_for_selector("#modal-briefing", state="hidden")

    # ── Seed direto no razão: constitui provisões reais nos dois "eixos" que o item 1 corrigiu.
    #    O achado é sobre RENDERIZAÇÃO/decoupling — os valores contábeis em si não são o objeto.
    #    "2.1.04.10" ganha uma efetivação PARCIAL de verdade (efetivar_provisao, sem passar pelo
    #    botão genérico — exatamente como uma rubrica de veredito nomeado acumula `efetivado`
    #    fora desta tela, via eventos reais do projeto) pra provar que o SELO ("Parcialmente
    #    Efetivada") e a AÇÃO (só o link pra Fila, nunca Efetivar/Resolver) são independentes.
    db = _sessao_teste()
    try:
        import mod_contabil as mc
        import database
        loja = db.query(database.Loja).order_by(database.Loja.id).first()
        ot, oid = mc.resolver_owner(db, {"loja_id": loja.id, "rede_id": None})
        mc.registrar_evento(db, ot, oid, "fechamento_venda_com_medidor", 5000.0,
                            projeto_id=nome_projeto, ref="e2e:seed:comissao")
        mc.efetivar_provisao(db, ot, oid, nome_projeto, "2.1.04.10", 2000.0,
                             ref="e2e:seed:comissao:efetivacao-parcial")
        mc.registrar_evento(db, ot, oid, "fechamento_venda_impostos", 800.0,
                            projeto_id=nome_projeto, ref="e2e:seed:impostos")
        mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_financeiro", 1000.0,
                            projeto_id=nome_projeto, ref="e2e:seed:custo-financeiro")
        db.commit()
    finally:
        db.bind.dispose()
        db.close()

    # ── Abre o modal de Reconciliação do projeto direto (mesmo _reconProvTabelaHtml da Etapa 21;
    #    o botão que abre isto na tela normal só aparece com contrato assinado — irrelevante aqui,
    #    o que se testa é a tabela, não o gate de visibilidade do botão que a abre). ────────────
    page.evaluate("() => abrirReconciliacaoProjeto()")
    page.wait_for_selector("#modal-recon-proj", state="visible")
    page.wait_for_selector('tr[data-prov-codigo="2.1.04.10"]', timeout=10000)

    # ── Confere contra a resposta REAL do endpoint pra este projeto — não um valor fixo. ───────
    resp = page.evaluate(
        "(nome) => fetch('/api/financeiro/reconciliacao-provisoes?projeto=' + encodeURIComponent(nome), "
        "{credentials:'same-origin'}).then(r=>r.json())", nome_projeto)
    provs = {p["codigo"]: p for p in resp["reconciliacao"]["provisoes"]}
    assert provs["2.1.04.10"]["exige_veredito"] is True
    assert provs["2.1.04.13"]["exige_veredito"] is False

    # Linha "2.1.04.10" (veredito nomeado, com efetivação PARCIAL real de 2000/5000 seedada
    # acima): selo e ação são EIXOS INDEPENDENTES — o selo relata o fato do dinheiro
    # ("Parcialmente Efetivada"), a ação continua travada no link pra Fila, nunca no botão
    # genérico (que o servidor recusaria com 409). Antes da correção, "Na Fila" vinha ANTES na
    # cadeia do selo e tornava "Efetivada"/"Parcialmente Efetivada" inalcançável aqui.
    linha_comissao = page.locator('tr[data-prov-codigo="2.1.04.10"]')
    assert linha_comissao.locator('button:has-text("Efetivar")').count() == 0, (
        "veredito nomeado não pode oferecer Efetivar genérico — o servidor recusa com 409")
    assert linha_comissao.locator('button:has-text("Resolver")').count() == 0, (
        "veredito nomeado não pode oferecer Resolver genérico — o servidor recusa com 409")
    link_fila = linha_comissao.locator('a:has-text("Dar veredito na Fila de Provisões")')
    assert link_fila.count() == 1
    assert "veredito nomeado" in (link_fila.get_attribute("title") or "").lower()
    # inner_text() reflete o text-transform:uppercase do CSS do selo (não o texto cru do DOM).
    assert "PARCIALMENTE EFETIVADA" in linha_comissao.inner_text().upper(), (
        "selo tem que refletir o dinheiro (efetivado=2000 < provisionado=5000), não a rota — "
        "'Na Fila' não é um estado do fato, é onde se age, e não pode aparecer no selo")

    # Linha "2.1.04.13" (rota genérica, Impostos): Efetivar/Resolver presentes, com tooltip de
    # destino de variância — não o nome do botão.
    linha_impostos = page.locator('tr[data-prov-codigo="2.1.04.13"]')
    assert linha_impostos.locator('button:has-text("Efetivar")').count() == 1
    btn_resolver_impostos = linha_impostos.locator('button:has-text("Resolver")')
    assert btn_resolver_impostos.count() == 1
    titulo_resolver = btn_resolver_impostos.get_attribute("title") or ""
    assert "4.3.01" in titulo_resolver and "mesma conta" in titulo_resolver.lower()
    titulo_efetivar = linha_impostos.locator('button:has-text("Efetivar")').get_attribute("title") or ""
    assert "despesa" in titulo_efetivar.lower() and "competência" in titulo_efetivar.lower()

    # Linha NUNCA tocada (ex. "2.1.04.11") — provisionado=efetivado=resolvido=0 já satisfaz
    # |saldo_aberto|<0.005 sozinho, mas isso não é "Resolvida": nada foi resolvido, nada
    # aconteceu. Correção sobre o commit 446216b: o selo passou a exigir movimento real
    # (provisionado, efetivado ou resolvido != 0) antes de anunciar qualquer fato — sem
    # movimento, "—". A ASSERÇÃO ANTIGA aqui (`"RESOLVIDA" in ...`) gravava o defeito como
    # correto; a que vale agora é a de baixo.
    linha_sem_movimento = page.locator('tr[data-prov-codigo="2.1.04.11"]')
    assert "—" in linha_sem_movimento.inner_text(), (
        "rubrica nunca constituída não é 'Resolvida' — não teve o que resolver")
    assert "RESOLVIDA" not in linha_sem_movimento.inner_text().upper()
    assert linha_sem_movimento.locator('button:has-text("Efetivar")').count() == 0
    assert linha_sem_movimento.locator('button:has-text("Resolver")').count() == 0
    assert linha_sem_movimento.locator("a").count() == 0

    # ── Item 2: Efetivar de verdade em Impostos — toast tem que dizer o valor DO RAZÃO
    # (d.lancamento.valor), e a linha realça e muda de selo (efetivado==provisionado → Resolvida).
    # (id contém pontos — inválido como seletor CSS "#id"; endereça por atributo [id=...].)
    page.fill('[id="efp-2.1.04.13"]', "800")
    page.click('tr[data-prov-codigo="2.1.04.13"] button:has-text("Efetivar")')
    # _fBRL não prefixa "R$" — o toast é "Efetivado 800,00." (item 2: diz o valor, não só "Ok").
    page.wait_for_selector("text=Efetivado 800,00", timeout=10000)
    # O toast aparece ANTES do _reconRealcarLinha (que recarrega a tabela) terminar — espera a
    # própria linha mudar de estado, não só o toast, senão a leitura corre contra o reload.
    page.wait_for_selector('tr[data-prov-codigo="2.1.04.13"]:has-text("resolvida")', timeout=10000)

    # ── Item 3, controle de idempotência: Custo Financeiro (2.1.04.19), efetivado PARCIAL
    # (400/1000) — o botão continua visível (não resolvido), e um 2º clique com o MESMO valor
    # no MESMO dia é idempotente (efetivar_provisao não lança de novo). O toast tem que dizer
    # "Já efetivado hoje.", não fingir um novo lançamento que não aconteceu.
    page.fill('[id="efp-2.1.04.19"]', "400")
    page.click('tr[data-prov-codigo="2.1.04.19"] button:has-text("Efetivar")')
    page.wait_for_selector("text=Efetivado 400,00", timeout=10000)
    page.wait_for_selector('tr[data-prov-codigo="2.1.04.19"]:has-text("parcialmente efetivada")',
                          timeout=10000)
    page.fill('[id="efp-2.1.04.19"]', "400")
    page.click('tr[data-prov-codigo="2.1.04.19"] button:has-text("Efetivar")')
    page.wait_for_selector("text=Já efetivado hoje.", timeout=10000)
    # O segundo clique não pode ter dobrado o efetivado (400+400=800) — confere contra o
    # endpoint de novo, não contra a leitura visual (que poderia atrasar o mesmo tanto do toast).
    resp2 = page.evaluate(
        "(nome) => fetch('/api/financeiro/reconciliacao-provisoes?projeto=' + encodeURIComponent(nome), "
        "{credentials:'same-origin'}).then(r=>r.json())", nome_projeto)
    custo_fin = next(p for p in resp2["reconciliacao"]["provisoes"] if p["codigo"] == "2.1.04.19")
    assert custo_fin["efetivado"] == 400.0, (
        "clique repetido no mesmo dia/valor não pode duplicar o efetivado — idempotência por ref")
