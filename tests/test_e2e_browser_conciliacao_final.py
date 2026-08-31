# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — o fluxo terminal que mais atravessa o que foi consertado nos
últimos dias (ACHADO-24, ACHADO-26): projeto criado pela interface, orçamento com um ambiente
real (XML), contrato aprovado (exercita a guarda de recebível do ACHADO-24), assinado, veredito
dado PELA FILA DE PROVISÕES (não pela API), Conciliação Final concluída pela tela de sempre
(corpo `{}`, sem campo de veredito — ACHADO-26), e o custo conferido em 5.1.01.

NÃO faz parte da suíte padrão — `tests/conftest.py` (`collect_ignore`) exclui este arquivo da
coleta recursiva. **Não é por ser caro** (medido: ~13s, 3 rodadas seguidas, nada perto do custo
que justificaria isolar por tempo) — é por DISPUTAR O MESMO BANCO: este arquivo sobe um
subprocesso que dá DROP SCHEMA CASCADE em `orizon_test`, o mesmo banco que `app_db`/
`db_pg_limpo` usam dentro do MESMO processo do pytest — rodar os dois na mesma sessão de
`pytest -q` corromperia o schema de algum teste no meio da suíte. Roda sozinho, antes de
implantar: `pytest tests/test_e2e_browser_conciliacao_final.py -v` (collect_ignore só vale pra
coleta recursiva, não quando o arquivo é passado explicitamente por caminho).

Duas regras (do teste manual do Marcelo no Chrome, 31/08):
1. Sobe o PRÓPRIO servidor a partir do código atual, num subprocesso — nunca reusa um servidor
   já no ar (foi um 404 de servidor velho que custou meia hora).
2. Navegador limpo, sem extensão nenhuma — o `browser`/`page` do pytest-playwright já sobe um
   Chromium ISOLADO, sem perfil e sem extensões, por padrão (nunca aponta pro Chrome real do
   sistema) — é isso que evita o problema que inviabilizou o caminho manual.

Escopo deliberadamente MENOR que "o ciclo inteiro clicado": Medição/Projeto executivo/Produção/
Montagem/Assistência/Vistoria/Aprovação final (entre o Contrato e a Conciliação Final — puro
"marcar como feito", sem forma própria nem risco de UI-cegueira, e nunca objeto de nenhum achado
desta auditoria) são marcadas concluídas direto no banco, não clicadas. Tudo que envolve
dinheiro/decisão (criar projeto, orçamento, ambiente, aprovar orçamento/gerar contrato, assinar,
dar veredito, concluir) é clicado de verdade na tela.
"""
import os
import socket
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REPO = os.path.join(os.path.dirname(__file__), "..")
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/orizon_test"

# XML Promob mínimo, com markup real (não "ruim" — ORDER 100.000 / BUDGET 140.000, 40%) — o
# ORDER vira o CFO (2.1.04.06 Custo de Fábrica), o BUDGET vira a receita/Val_Cont do ambiente.
XML_ONE_AMBIENTE = '''<PROJECT DESCRIPTION="Cozinha E2E" DATE="01/01/2026"><CATEGORY DESCRIPTION="Cozinha"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="Modulados" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="140000" TOTAL="140000"><MARGINS><ORDER TOTAL="100000"/><BUDGET TOTAL="140000"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def _sessao_teste():
    """Sessão com bind PRÓPRIO em TEST_DB_URL — nunca `database.get_session()` direto num
    teste: o processo do pytest importa `database` com o DATABASE_URL do AMBIENTE DE QUEM RODA
    O TESTE (pode ser o banco de dev real, se a variável estiver exportada no shell — foi
    exatamente isso que aconteceu numa rodada de depuração deste arquivo, escrevendo CicloEtapa
    órfã no banco de dev local — limpo depois, mas não pode se repetir). Chamador fecha a
    sessão E chama `.dispose()` na engine (`sessao.bind.dispose()`)."""
    eng = create_engine(TEST_DB_URL)
    return sessionmaker(bind=eng)()


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor_e2e():
    """Reseta o schema do banco de TESTE (mesmo `orizon_test` da suíte — sem CREATEDB local, ver
    docs/db/IMPLANTAR.md; NUNCA rode isto ao mesmo tempo que `pytest -q` da suíte inteira, os dois
    disputam o mesmo schema) e sobe `python3 main.py` DE VERDADE, do código atual, num
    subprocesso — nunca um servidor já no ar."""
    porta = _porta_livre()
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "_e2e_bootstrap.py"),
                       TEST_DB_URL], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, "bootstrap do banco falhou:\n" + r.stdout + r.stderr

    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DB_URL
    env["ORIZON_PORT"] = str(porta)
    env["ORIZON_HOST"] = "127.0.0.1"
    env.pop("ORIZON_WA_TOKEN", None); env.pop("ORIZON_SMTP_PASS", None)   # hermeticidade (conftest.py)
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
                    saida = proc.stdout.read()
                    raise RuntimeError("servidor E2E morreu no boot:\n" + saida)
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
    """`page` do pytest-playwright já é um Chromium isolado (sem perfil, sem extensão) — só
    ajusta timeout padrão pra esta suíte (a página tem uploads/gravações reais)."""
    page.set_default_timeout(15000)
    return page


def _click_confirmar(page):
    """Popup genérico de confirmarPopup()/_popupOverlay — sem id fixo, botão [data-act="ok"]."""
    page.click('[data-act="ok"]')


def _dispensar_alteracoes_nao_salvas(page):
    """confirmarSalvarPopup() ("Alterações não salvas") aparece ao trocar de contexto na
    negociação (o plano à vista default já conta como alteração pendente) — Salvar, sem perder o
    plano populado por avistaRecalcular(). Aparece com um instante de atraso — espera de verdade,
    não só `.count()` na hora (senão corre a chance de checar antes do popup existir)."""
    try:
        page.wait_for_selector('[data-act="salvar"]', timeout=2000)
        page.click('[data-act="salvar"]')
    except Exception:
        pass


def test_fluxo_terminal_conciliacao_final_pela_fila(page, servidor_e2e):
    base = servidor_e2e
    nome_exibicao = "E2E Cozinha Playwright"   # o que foi digitado — usado pra achar na lista
    nome_projeto = nome_exibicao   # reatribuído pro nome_safe REAL após criar (abaixo)

    # ── 1. Login ─────────────────────────────────────────────────────────────────────────
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    # ── 2. Criar projeto ─────────────────────────────────────────────────────────────────
    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", nome_exibicao)
    page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
    # nome_safe real (sufixo _N se um diretório de projeto antigo com o mesmo nome sobrou em
    # PROJETOS_DIR de uma rodada anterior — nunca assumir que é o nome digitado).
    nome_projeto = page.evaluate("() => projetoAtivo.nome_safe")

    # ── 3. Briefing (gate da aprovação do orçamento) ────────────────────────────────────
    page.select_option("#bf-tipo-imovel", index=1)
    page.fill("#bf-budget", "150000")
    page.select_option("#bf-categoria", index=1)
    page.fill("#bf-data-entrega", "2027-06-01")
    page.select_option("#bf-flexibilidade", index=1)
    page.click('button:has-text("Salvar Briefing")')
    page.wait_for_selector("#modal-briefing", state="hidden")

    # ── 4. Orçamento + ambiente (upload de XML real) ────────────────────────────────────
    page.click("#btn-novo-orc")
    page.fill("#novo-orc-nome-input", "Orçamento 1")
    page.locator("#modal-novo-orc").get_by_role("button", name="Criar", exact=True).click()
    page.wait_for_selector("#modal-novo-orc", state="hidden")

    _dispensar_alteracoes_nao_salvas(page)
    page.click("#btn-novo-ambiente")
    xml_path = "/tmp/e2e_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    # auto-vincula ao orçamento ativo e fecha o modal sozinho — sem isso "Total do Contrato"
    # nunca sai de R$ 0,00.
    page.wait_for_selector("text=140.000,00", timeout=10000)

    # ── 5. Aprovar orçamento / gerar contrato (exercita a guarda do ACHADO-24) ──────────
    # Cada gate é opcional e depende do estado (cliente é o próprio signatário? contatos já
    # confirmados? loja completa?) — poll explícito em vez de wait_for único: mais de um popup
    # pode aparecer em sequência, e cada um só existe por uma janela curta.
    page.click("#btn-aprovar-orcamento")
    page.wait_for_selector("#modal-aprovacao-overlay")
    page.click('#modal-aprovacao-overlay button:has-text("Gerar Contrato")')
    deadline = time.time() + 20
    while time.time() < deadline:
        if page.locator("text=Contrato gerado").count():
            break
        clicado = False
        for sel in ('[data-act="ok"]', 'button:has-text("Confirmar contatos")',
                   'button:has-text("Gerar assim")'):
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                clicado = True
                break
        page.wait_for_timeout(300 if clicado else 400)
    page.wait_for_selector("text=Contrato gerado", timeout=10000)

    # ── 6. Assinar contrato (loja + cliente) ────────────────────────────────────────────
    def _dispensar_transferir():
        btn = page.locator('button:has-text("Sim, transferir")')
        if btn.count() and btn.first.is_visible():
            btn.first.click()
            page.wait_for_timeout(300)

    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    _dispensar_transferir()
    ciclo.locator(".ficha-tab", has_text="Contrato").first.click()
    page.wait_for_timeout(500)
    _dispensar_transferir()

    # Passo 2 (cronograma): sem data de entrega + previsão de medição, a assinatura recusa.
    page.fill("#ct-previsao-medicao", "2027-03-01")
    page.fill("#ct-data-entrega", "2027-06-01")
    page.click('button:has-text("Validar")')
    page.wait_for_timeout(500)

    with page.expect_popup():
        ciclo.get_by_role("link", name="Imprimir").first.click()
    assinatura = page.locator("#secao-assinatura-contrato")
    # _confirmarBoxInterna manda as duas partes marcadas numa chamada só.
    page.check("#conf-ct-loja")
    page.fill("#conf-ct-loja-nome", "Rep Loja E2E")
    page.fill("#conf-ct-loja-cpf", "111.444.777-35")
    page.check("#conf-ct-cliente")
    page.fill("#conf-ct-cliente-nome", "Cliente E2E")
    page.fill("#conf-ct-cliente-cpf", "111.444.777-35")
    assinatura.get_by_role("button", name="Confirmar", exact=True).click()
    # _confirmarBoxInterna manda loja+cliente juntas nesta chamada — vai direto pro estado
    # "ambas as partes confirmaram", sem passar por um "loja confirmada" intermediário.
    page.wait_for_selector("text=Contrato assinado", timeout=10000)

    # ── 7. Medição/Projeto executivo/Produção/Montagem/Assistência/Vistoria/Aprovação final
    #      (puro "marcar feito", nunca objeto de achado desta auditoria): atalho direto no
    #      banco — mod_ciclo.ETAPAS_PRINCIPAIS antes de CONCILIACAO_FINAL, exceto as já feitas
    #      de verdade pela tela (Cadastro/Criação/Briefing/Orçamento/Contrato).
    import mod_ciclo
    import database
    db = _sessao_teste()
    try:
        i_contrato = mod_ciclo.ETAPAS_PRINCIPAIS.index(mod_ciclo.CONTRATO)
        i_final = mod_ciclo.ETAPAS_PRINCIPAIS.index(mod_ciclo.CONCILIACAO_FINAL)
        for cod in mod_ciclo.ETAPAS_PRINCIPAIS[i_contrato + 1:i_final]:
            et = db.query(database.CicloEtapa).filter_by(
                projeto_nome=nome_projeto, etapa_codigo=cod).first()
            if et is None:
                et = database.CicloEtapa(projeto_nome=nome_projeto, etapa_codigo=cod)
                db.add(et)
            et.status = "concluido"
        db.commit()
    finally:
        db.bind.dispose()
        db.close()

    # ── 8. Fila de Provisões — dar o veredito PELA TELA (não pela API) ──────────────────
    page.click('text=Financeiro')
    page.click('text=Fila de Provisões')
    linha = page.locator("tr", has_text=nome_projeto)
    linha.wait_for()
    linha.get_by_role("button", name="Encerrada · valor menor").click()
    page.fill("#_filaprov-valor", "100000")
    page.get_by_role("button", name="Confirmar", exact=True).last.click()
    page.wait_for_selector("text=Veredito registrado")

    # ── 9. Conciliação Final — conclui pela tela normal (corpo {} de sempre) ────────────
    page.click("text=Projetos")
    page.fill("#proj-search", nome_exibicao)
    page.locator(".proj-row", has_text=nome_exibicao).get_by_role("button", name="Abrir").click()
    page.click("#btn-abrir-ciclo")
    ciclo.wait_for(state="visible", timeout=10000)
    _dispensar_transferir()
    ciclo.locator(".ficha-tab", has_text="Conciliação Final").first.click()
    page.wait_for_timeout(500)
    page.click('button:has-text("Concluir Conciliação Final")')
    _click_confirmar(page)
    page.wait_for_selector("text=Números finais conciliados")

    # ── 10. Verificação — custo em 5.1.01 (Postgres, fonte de verdade) ──────────────────
    import mod_contabil as mc
    db = _sessao_teste()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": 1, "rede_id": None})
        despesa_5101 = mc.total_lancado(db, ot, oid, "5.1.01", "debito", nome_projeto)
        status = db.get(database.Projeto, nome_projeto).status
    finally:
        db.bind.dispose()
        db.close()
    assert status == "concluido", status
    assert abs(despesa_5101 - 100000.0) < 0.5, despesa_5101
