# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-53 — abrir os parâmetros de um projeto com contrato
assinado disparava um POST /parametros (auto-save com debounce, ~250ms depois de popular os
campos do modal) que o servidor recusa (403, "Contrato assinado — alterações não permitidas") —
recusa CERTA, mas nunca deveria ter sido pedida: ninguém mexeu em nada, só abriu a tela.

Conserto (2 portões, `static/index.html`): `_mpPopulando` (true durante todo o preenchimento de
`abrirModalParams`) e `_mpModoLeitura` (espelha o `ro` de `_aplicarModoLeituraParams`) — enquanto
qualquer um dos dois estiver ligado, `agendarSalvarParametros` não agenda nada. `_renderCard*`
nunca populou disparando o handler de mudança de propósito; a garantia agora é no PONTO DE
CONSEQUÊNCIA (agendar o save), não em cada gatilho possível — mais robusto contra qualquer
caminho futuro que também populariza o modal."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
import urllib.request, urllib.error


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _post(c, path, body):
    req = urllib.request.Request(c.base + path, data=_json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie: req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def test_backend_alterar_passa_sem_contrato_assinado(http_client_factory, seed, app_db):
    """Controle-irmão: o gate é só para contrato assinado — projeto editável continua aceitando
    a mesma chamada (prova que nada no lado do servidor foi endurecido nesta rodada). Roda ANTES
    do teste seguinte de propósito — o seed/contrato é compartilhado no arquivo, e o teste
    seguinte marca o contrato como assinado (mutação que não se desfaz sozinha)."""
    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    st, body = _post(c, f"/api/projetos/{proj}/parametros", {"comissao_arq_pct": 7})
    assert st == 200 and body.get("ok") is True, body


def test_backend_alterar_continua_recusando_com_contrato_assinado(
        http_client_factory, seed, app_db):
    """Metade "alterar continua recusando" do aceite: o servidor é o gate real. O JS só deixa de
    pedir o que não precisava pedir — nunca deixou de recusar quando pedido de propósito."""
    db = app_db.get_session()
    ct = db.get(app_db.Contrato, seed["contrato_l1_id"])
    ct.status = "assinado_loja"
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    proj = seed["projeto_l1"]
    st, body = _post(c, f"/api/projetos/{proj}/parametros", {"comissao_arq_pct": 7})
    assert st == 403 and "Contrato assinado" in body.get("erro", ""), body
