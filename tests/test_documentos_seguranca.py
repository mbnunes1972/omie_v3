# -*- coding: utf-8 -*-
"""tests/test_documentos_seguranca.py — SSRF/LFI pelo corpo_md do modelo da loja.

O corpo do contrato deixou de vir só de contrato_template/contrato.md (conteúdo do
repositório, confiável) e passou a vir do modelo que a LOJA sobe — entrada de usuário.
markdown.markdown() PRESERVA HTML embutido, e o HTML ia cru para o WeasyPrint: um
<img src="http://..."> ou @import url(...) fazia o renderizador buscar a URL (SSRF, com
alcance a serviço interno), e url(file:///...) lia arquivo local (LFI). Explorável no
/preview sem ativar nada, e persistente depois de ativado — dispara a cada contrato real.

Duas camadas, testadas aqui de forma independente:
  1. _html_corpo escapa o corpo antes do Markdown  -> a tag nunca nasce.
  2. _url_fetcher_local restringe o WeasyPrint     -> mesmo que uma tag escape no
     futuro, não há busca fora de CONTRATO_TEMPLATE_DIR.

E o contraponto que impede a "correção" de virar regressão: o logo e o CSS do template
TÊM que continuar carregando (test_assets_legitimos_* / test_logo_continua_embutido).
"""
import sys, os, tempfile, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest

import mod_contrato


# ── Servidor de prova: registra qualquer requisição que o renderizador emitir ───

@pytest.fixture
def sonda():
    """(base_url, hits) — hits recebe o path de toda requisição que chegar."""
    hits = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"hi")

        def log_message(self, *a):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), H)
    porta = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % porta, hits
    httpd.shutdown()


def _ctx_com_corpo(corpo_md):
    ctx = mod_contrato.construir_contexto(
        {"nome": "Cliente", "cpf": "0", "inst_mesmo_residencial": True},
        {"nome": "Usuario"}, "", {"nome": "Loja"})
    ctx["_corpo_md_preview"] = corpo_md
    ctx["num_contrato"] = "TESTE"
    return ctx


# ── Camada 1: o corpo é escapado ───────────────────────────────────────────────

def test_html_do_corpo_vira_texto_literal():
    """<img>/<style>/<script> no modelo não podem virar tag no documento."""
    h = mod_contrato._html_corpo(
        '<img src="http://x/y">\n<script>alert(1)</script>\n<style>@import url("http://x/z")</style>\n')
    assert "<img" not in h and "<script" not in h and "<style" not in h
    assert "&lt;img" in h, "a tag tem que sobrar VISÍVEL como texto (o lojista vê que colou lixo)"


def test_markdown_legitimo_continua_funcionando():
    """Escapar não pode custar a formatação real de um contrato."""
    h = mod_contrato._html_corpo("# CLÁUSULA PRIMEIRA\n1.1. Texto **negrito** aqui.\n")
    assert "<h1>" in h and "CLÁUSULA PRIMEIRA" in h
    assert "<strong>negrito</strong>" in h


def test_linha_de_assinatura_sobrevive_ao_escape():
    """Runs de '_' são linha de preenchimento; o escape não pode comê-los."""
    h = mod_contrato._html_corpo("________________________\n[NOME_EMPRESA]\n")
    assert "________________________" in h


def test_template_global_nao_tem_html_embutido():
    """GUARDA da premissa que torna o escape seguro.

    Escapar o corpo só é seguro porque contrato.md (que passa pelo MESMO _html_corpo)
    é texto puro com marcadores. Se alguém embutir HTML nele um dia, o escape passaria a
    imprimir a tag literal no contrato de produção — em silêncio. Este teste quebra antes.
    """
    md = mod_contrato._carregar_md()
    assert "<" not in md, (
        "contrato_template/contrato.md ganhou HTML embutido. _html_corpo escapa o corpo "
        "(defesa contra SSRF/LFI do modelo da loja), então esse HTML sairia como texto "
        "literal no PDF. Tire o HTML do .md ou reveja a estratégia de escape."
    )


# ── Camada 2: o url_fetcher confina o WeasyPrint ───────────────────────────────

@pytest.mark.parametrize("asset", ["logo_dalmobile.png", "contrato.css"])
def test_assets_legitimos_do_template_carregam(asset):
    """O contraponto: fechar o furo não pode quebrar o contrato de produção."""
    url = Path(os.path.join(mod_contrato.CONTRATO_TEMPLATE_DIR, asset)).as_uri()
    resp = mod_contrato._url_fetcher_local(url)
    conteudo = resp.read()
    assert len(conteudo) == os.path.getsize(os.path.join(mod_contrato.CONTRATO_TEMPLATE_DIR, asset))
    assert len(conteudo) > 0


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:9/x",
    "https://evil.example/y",
    "file:///etc/passwd",
    "ftp://evil.example/z",
])
def test_url_fetcher_bloqueia_externo_e_lfi(url):
    with pytest.raises(ValueError):
        mod_contrato._url_fetcher_local(url)


def test_url_fetcher_bloqueia_file_vizinho_ao_template():
    """LFI mais realista que /etc/passwd: arquivo do próprio projeto, fora do template."""
    vizinho = Path(os.path.join(mod_contrato.CONTRATO_TEMPLATE_DIR, "..", "database.py")).as_uri()
    with pytest.raises(ValueError):
        mod_contrato._url_fetcher_local(vizinho)


# ── Logo por loja (2026-08-20): segunda base confinada no mesmo fetcher ────────

def test_logo_da_loja_carrega_via_fetcher(monkeypatch, tmp_path):
    """A logo própria da loja fica FORA de CONTRATO_TEMPLATE_DIR — prova que a segunda
    base (LOGOS_LOJA_DIR) também é aceita, sem afrouxar a primeira."""
    monkeypatch.setattr(mod_contrato, "LOGOS_LOJA_DIR", str(tmp_path))
    pasta = tmp_path / "7"
    pasta.mkdir()
    arquivo = pasta / "abc123.png"
    arquivo.write_bytes(b"conteudo-fake-de-logo")
    url = Path(str(arquivo)).as_uri()
    resp = mod_contrato._url_fetcher_local(url)
    assert resp.read() == b"conteudo-fake-de-logo"


def test_url_fetcher_bloqueia_fora_de_ambas_bases(monkeypatch, tmp_path):
    """Continua bloqueando tudo que não seja CONTRATO_TEMPLATE_DIR nem LOGOS_LOJA_DIR —
    a segunda base não virou um buraco geral no confinamento."""
    monkeypatch.setattr(mod_contrato, "LOGOS_LOJA_DIR", str(tmp_path / "logos_loja"))
    fora = tmp_path / "fora.png"
    fora.write_bytes(b"x")
    with pytest.raises(ValueError):
        mod_contrato._url_fetcher_local(Path(str(fora)).as_uri())


# ── Integração: gerar o PDF de verdade não emite requisição ────────────────────

def test_corpo_malicioso_nao_gera_requisicao_ao_render(sonda):
    """O vetor que PASSAVA antes da correção (sonda recebia /img e /css)."""
    base, hits = sonda
    corpo = ('<img src="%s/img-vazou">\n\n'
             '<style>@import url("%s/css-vazou");</style>\n\n'
             '# CLAUSULA PRIMEIRA\n1.1. Texto.\n' % (base, base))
    out = tempfile.mkdtemp()
    mod_contrato.gerar_pdf_contrato("seg", _ctx_com_corpo(corpo), destino=out)
    assert hits == [], "o renderizador buscou URL externa a partir do modelo: %r" % hits


def test_proposta_tambem_confina_o_fetcher(sonda):
    """gerar_pdf_proposta é o outro caminho de render — não pode ficar de fora."""
    base, hits = sonda
    ctx = _ctx_com_corpo("# X\n1.1. y\n")
    ctx["_ambientes"] = [("Amb", 1.0)]
    # a capa não consome corpo_md; o que se prova aqui é que o fetcher está plugado:
    # um asset externo no HTML da proposta não pode ser buscado.
    ctx["consultor_nome"] = '<img src="%s/proposta-vazou">' % base
    destino = os.path.join(tempfile.mkdtemp(), "p.pdf")
    mod_contrato.gerar_pdf_proposta(ctx, destino)
    assert hits == [], "gerar_pdf_proposta buscou URL externa: %r" % hits


def test_logo_continua_embutido_no_pdf():
    """Prova que o fetcher restrito não matou o asset legítimo: o PDF com os assets do
    template é substancialmente maior que o mesmo PDF com tudo bloqueado."""
    from weasyprint import HTML
    html = mod_contrato._montar_html_contrato(_ctx_com_corpo("# C\n1.1. Texto.\n"))
    com = os.path.join(tempfile.mkdtemp(), "com.pdf")
    sem = os.path.join(tempfile.mkdtemp(), "sem.pdf")

    def bloqueia_tudo(url):
        raise ValueError("bloqueado")

    HTML(string=html, base_url=mod_contrato.CONTRATO_TEMPLATE_DIR,
         url_fetcher=mod_contrato._url_fetcher_local).write_pdf(com)
    HTML(string=html, base_url=mod_contrato.CONTRATO_TEMPLATE_DIR,
         url_fetcher=bloqueia_tudo).write_pdf(sem)
    logo = os.path.getsize(os.path.join(mod_contrato.CONTRATO_TEMPLATE_DIR, "logo_dalmobile.png"))
    assert os.path.getsize(com) > os.path.getsize(sem) + logo // 2, (
        "o PDF com o fetcher restrito não tem o logo/CSS embutido — a correção de "
        "segurança quebrou o contrato de produção"
    )
