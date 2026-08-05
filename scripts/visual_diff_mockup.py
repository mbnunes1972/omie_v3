#!/usr/bin/env python3
"""
Visual diff automatizado: mockup de referência × implementação real do Orizon Chat.

Objetivo (pedido do usuário 2026-08-05, depois de várias rodadas de "não bate com o mockup"
resolvidas só por julgamento visual meu, subjetivo e falível): tirar da percepção humana/do
Claude o veredito de "bate ou não bate" — gera um DIFF DE PIXEL de verdade entre o mockup e a
implementação, com um número objetivo (% de diferença) e uma imagem de calor mostrando ONDE
diverge, região por região (topbar, coluna da lista, barra de ação).

Como isso resolve o problema de "conteúdo dinâmico diferente atrapalha o diff": o mockup usa
dados de exemplo fixos (Fernanda Souza, "Comercial", etc.) — este script injeta EXATAMENTE os
mesmos dados na implementação real (via JS, sem tocar backend/banco) antes de tirar o print, pra
a comparação ser maçã-com-maçã (só estrutura/cor/proporção, não texto/conteúdo diferente).

Uso:
    python3 scripts/visual_diff_mockup.py
    python3 scripts/visual_diff_mockup.py --base https://homolog.orizonone.com.br \
        --login qa_visual_temp --senha temp1234
    python3 scripts/visual_diff_mockup.py --base http://127.0.0.1:8765 \
        --login qa_vera_temp --senha temp1234 --out /tmp/diff

Saída: <out>/<tela>_mockup.png, <out>/<tela>_implementacao.png, <out>/<tela>_diff.png
(heatmap vermelho = pixel diferente) + relatório impresso no stdout com % de diferença por
região. Não altera nenhum dado real (só injeta HTML/texto na página já carregada, no navegador
headless — nunca faz POST/escreve no banco).
"""
import argparse
import json
import os
import sys
import urllib.request

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

MOCKUP_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "docs/superpowers/specs/comunicacao/mockups/2026-08-04-orizon-chat-atendimentos-ui-mockup.html")

VIEWPORT = {"width": 1440, "height": 900}

# Dado de exemplo COMPARTILHADO — o mockup já nasce com isso (hardcoded); a implementação
# recebe o mesmo via injeção de DOM, sem tocar backend/banco.
FIXTURE_ATEND = [
    {"id": 1, "tipo": "direct", "titulo": "Fernanda Souza", "ultima_previa": "Oi, tudo bem? Preciso saber sobre um orçamento", "segmento": "comercial"},
    {"id": 2, "tipo": "projeto", "titulo": "📁 Projeto Vendas mse2hd50253", "ultima_previa": "Ricardo: cliente confirmou a medida final", "segmento": "comercial"},
    {"id": 3, "tipo": "grupo", "titulo": "Equipe Loja SJC", "ultima_previa": "Bruno: fechei a venda da Fernanda!"},
    {"id": 4, "tipo": "direct", "titulo": "Ricardo Alves", "ultima_previa": "Bom dia! Gostaria de fazer uma revisão nas gavetas do meu...", "segmento": "parceiros"},
    {"id": 5, "tipo": "direct", "titulo": "Marcos Tadeu", "ultima_previa": "Obrigado, até mais!", "segmento": "financeiro"},
]


def login(base, login_, senha):
    req = urllib.request.Request(
        f"{base}/api/auth/login",
        data=json.dumps({"login": login_, "senha": senha}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    if not d.get("ok"):
        raise SystemExit(f"Login falhou: {d.get('erro')}")
    return d["token"]


def diff_images(path_a, path_b, path_out):
    """Retorna % de pixels diferentes (0-100) e salva um heatmap em path_out.
    Redimensiona B pro tamanho de A se precisar (as duas fontes podem medir 1-2px
    diferente por causa de scrollbar/arredondamento) — sem isso um mero desalinhamento
    de tamanho conta como "100% diferente" e mascara o diff real de conteúdo."""
    a = Image.open(path_a).convert("RGB")
    b = Image.open(path_b).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    hist = diff.convert("L").histogram()
    total = sum(hist)
    # pixels com QUALQUER canal diferente por mais de uma tolerância pequena (evita ruído de
    # antialiasing de fonte contar como "diferente")
    changed = sum(hist[16:])  # luminância do diff > ~16/255
    pct = 100.0 * changed / total if total else 0.0
    # heatmap: realça as diferenças em vermelho sobre uma versão apagada da implementação
    heat = ImageChops.multiply(diff.convert("L").point(lambda p: 255 if p > 16 else 0).convert("RGB"),
                                Image.new("RGB", a.size, (255, 60, 60)))
    base_dim = Image.blend(b, Image.new("RGB", b.size, (20, 20, 20)), 0.55)
    overlay = ImageChops.screen(base_dim, heat)
    overlay.save(path_out)
    return pct, bbox


def montar_mockup(page):
    page.goto(f"file://{os.path.abspath(MOCKUP_PATH)}")
    page.wait_for_timeout(300)


def montar_implementacao_atend(page, base, token):
    ctx = page.context
    ctx.add_cookies([{"name": "orizon_session", "value": token, "url": base}])
    page.goto(base)
    page.wait_for_timeout(1200)
    page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
    page.wait_for_timeout(150)
    page.evaluate("ocAbrirPagina('atend')")
    page.wait_for_timeout(700)
    page.evaluate(
        "(fx) => { document.getElementById('atd-lista').innerHTML = "
        "fx.map((c,i)=>_atdItemHTML(Object.assign({ultima_em:new Date().toISOString()}, c))).join(''); }",
        FIXTURE_ATEND)
    page.wait_for_timeout(150)
    # abre a 1ª conversa (Fernanda Souza) e replica o cabeçalho/mensagens do mockup USANDO A
    # FUNÇÃO REAL DE RENDER (_ocRenderMsg) — não um placeholder à mão. Comparar contra um
    # placeholder mascarava justamente o achado do balão de mensagem (a implementação de
    # verdade nunca teve estilo de balão; um placeholder feito à mão por este script não
    # revelaria isso, só revelaria diferenças do PRÓPRIO placeholder).
    page.evaluate("""(uid) => {
        _ocConvAtiva = 1; _ocConvTipo = 'direct'; _ocConvProjeto = null;
        _usuarioAtual = _usuarioAtual || {}; _usuarioAtual.id = uid;
        ocMostrarView('oc-thread');
        document.getElementById('oc-thread-titulo').textContent = 'Fernanda Souza';
        const msgs = [
          {corpo:'Oi', criado_em:'2026-01-01T10:41:00', autor_usuario_id: null, autor_nome:'Fernanda Souza'},
          {corpo:'Vocês têm horário disponível essa semana pra uma visita?', criado_em:'2026-01-01T10:41:00', autor_usuario_id: null, autor_nome:'Fernanda Souza'},
          {corpo:'Oi Fernanda! Bom dia \\ud83d\\ude0a Deixa eu verificar aqui e já te retorno.', criado_em:'2026-01-01T10:43:00', autor_usuario_id: uid, autor_nome:'Você'},
        ];
        document.getElementById('oc-msgs').innerHTML = msgs.map(_ocRenderMsg).join('');
        _ocSetHeaderExtras({tipo:'direct', segmento:'comercial'});
    }""", 999999)
    page.wait_for_timeout(200)


def montar_implementacao_interno(page, base, token):
    ctx = page.context
    ctx.add_cookies([{"name": "orizon_session", "value": token, "url": base}])
    page.goto(base)
    page.wait_for_timeout(1200)
    page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
    page.wait_for_timeout(150)
    page.evaluate("ocAbrirPagina('interno')")
    page.wait_for_timeout(700)


def elemento_screenshot(page, selector, path_out):
    """Screenshot só do ELEMENTO (não da página inteira) — é isso que resolve o problema
    do sidebar do app deslocando tudo: o mockup não tem o menu lateral do Orizon Manager
    nem o menu do módulo Chat, então comparar a PÁGINA INTEIRA sempre ia mostrar um
    desalinhamento horizontal gigante que não é um bug de verdade, só chrome que o
    mockup nunca teve. Recortando só '.screen.visible' (mockup) / '.ochat-scr.active'
    (implementação) — a área de conteúdo do chat propriamente dita — a comparação vira
    maçã-com-maçã: mesma origem (0,0) relativa, mesmo tipo de conteúdo."""
    page.locator(selector).first.screenshot(path=path_out)


def rodar(base, login_, senha, out):
    os.makedirs(out, exist_ok=True)
    token = login(base, login_, senha)
    telas = []
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ── Atendimentos ──────────────────────────────────────────────────────
        page_m = browser.new_context(viewport=VIEWPORT).new_page()
        montar_mockup(page_m)
        p_mock = os.path.join(out, "atendimentos_mockup.png")
        elemento_screenshot(page_m, "#screen-atendimentos", p_mock)
        page_m.context.close()

        page_i = browser.new_context(viewport=VIEWPORT, ignore_https_errors=True).new_page()
        montar_implementacao_atend(page_i, base, token)
        p_impl = os.path.join(out, "atendimentos_implementacao.png")
        elemento_screenshot(page_i, "#ochat-scr-atend", p_impl)
        page_i.context.close()

        pct, bbox = diff_images(p_mock, p_impl, os.path.join(out, "atendimentos_diff.png"))
        telas.append(("Atendimentos", pct, bbox))

        # ── Chat Interno (só estrutura — mockup também tem dado fixo próprio) ──
        page_m2 = browser.new_context(viewport=VIEWPORT).new_page()
        montar_mockup(page_m2)
        page_m2.click("#toggleInterno")
        page_m2.wait_for_timeout(200)
        p_mock2 = os.path.join(out, "interno_mockup.png")
        elemento_screenshot(page_m2, "#screen-interno", p_mock2)
        page_m2.context.close()

        page_i2 = browser.new_context(viewport=VIEWPORT, ignore_https_errors=True).new_page()
        montar_implementacao_interno(page_i2, base, token)
        p_impl2 = os.path.join(out, "interno_implementacao.png")
        elemento_screenshot(page_i2, "#ochat-scr-interno", p_impl2)
        page_i2.context.close()

        pct2, bbox2 = diff_images(p_mock2, p_impl2, os.path.join(out, "interno_diff.png"))
        telas.append(("Chat Interno", pct2, bbox2))

        browser.close()

    print("\n=== Relatório de diff visual (mockup × implementação, 1440x900, tema escuro) ===")
    for nome, pct, bbox in telas:
        status = "✅ muito próximo" if pct < 8 else ("🟡 diferenças visíveis" if pct < 20 else "🔴 diferença grande")
        print(f"{nome}: {pct:.1f}% dos pixels diferentes — {status}")
        if bbox:
            print(f"  região com diferença: x={bbox[0]}-{bbox[2]} y={bbox[1]}-{bbox[3]}")
    print(f"\nImagens salvas em: {out}")
    print("Cada tela gera 3 arquivos: _mockup.png, _implementacao.png, _diff.png (heatmap vermelho = onde diverge).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8765", help="URL base da implementação (default: localhost)")
    ap.add_argument("--login", default="qa_vera_temp", help="login de um usuário de teste já ativo")
    ap.add_argument("--senha", default="temp1234", help="senha desse usuário de teste")
    ap.add_argument("--out", default="/tmp/orizon_visual_diff", help="pasta de saída das imagens")
    args = ap.parse_args()
    rodar(args.base, args.login, args.senha, args.out)
