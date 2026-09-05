# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-54 — a NF-e de produto rejeitada era um beco sem saída.

Causa 1 (numeração): `ref` era constante por fabrica_doc_id ("NFE-<projeto>-<doc.id>") — uma
retentativa depois de rejeição chegava à Focus/SEFAZ pedindo o MESMO número, e a SEFAZ recusa por
"Duplicidade de NF-e com diferença na Chave de Acesso" (print do Marcelo, projeto Teste 2, série
001, números 19/20). Conserto: `ref` por TENTATIVA, mesma regra já usada na NFS-e — só autorizado/
processando trava; erro (rejeitada) ou cancelado libera um `ref` novo.

Causa 2 (tela): `_renderCardEmissaoNfe` (static/index.html) travava a linha assim que existia
QUALQUER emissão, mesmo em `erro` — só Consultar (e Cancelar se autorizado), nunca uma saída. Regra
do Marcelo: "caso a nota não seja carregada ela precisa sair da tela, não precisa ficar nenhum
registro de um documento que não foi processado." Conserto: só trava (Consultar/Cancelar) quando
autorizado/processando; em erro ou cancelado, a linha volta a oferecer nova tentativa e Remover."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
import urllib.request, urllib.error

from fiscal import nfe_emissao
from integracoes.emissor_fiscal import resultado_de_focus
from tests.test_nfe_etapa15_e2e import _reset15, _perfil, _login, _upload_xml, _fixture_xml, _post


class _FakeClientAutorizaSegunda:
    def baixar(self, caminho):
        return b"BYTES"
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        raise AssertionError("não deveria pollar — o Fake já devolve status final direto")


class _FakeEmissorRejeitaPrimeiraTentativa:
    """1ª chamada: rejeição da SEFAZ (duplicidade de numeração, o sintoma real do Marcelo).
    2ª chamada (ref novo): autorizada — prova que o retry chega à Focus com um `ref` diferente."""
    def __init__(self):
        self.client = _FakeClientAutorizaSegunda()
        self.refs_vistos = []

    def emitir_nfe_produto(self, nota):
        self.refs_vistos.append(nota["ref"])
        if len(self.refs_vistos) == 1:
            return resultado_de_focus({
                "ref": nota["ref"], "status": "erro_autorizacao",
                "mensagem_sefaz": "Rejeição: Duplicidade de NF-e com diferença na Chave de Acesso "
                                   "[chNFe:35141219152134000156550010000000201000000201]"
                                   "[nRec:351000086365534]"})
        return resultado_de_focus({
            "ref": nota["ref"], "status": "autorizado", "chave_nfe": "CH-NOVA",
            "numero": "20", "serie": "1",
            "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})


def test_retentativa_apos_rejeicao_usa_numeracao_nova(
        http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    fake = _FakeEmissorRejeitaPrimeiraTentativa()
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: fake)
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    doc_id = up["documento_id"]

    st1, b1 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                    {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st1 == 200 and b1["status"] == "erro", b1
    ref1 = b1["ref"]

    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                    {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st2 == 200 and b2["status"] == "autorizado", b2
    ref2 = b2["ref"]

    assert ref1 != ref2, "a retentativa tem que usar um ref NOVO, nunca o mesmo da rejeitada"
    assert fake.refs_vistos[0] != fake.refs_vistos[1], \
        "a Focus recebeu o mesmo ref nas duas chamadas — não forçaria numeração nova na SEFAZ"

    # o GET .../ciclo/15/nfe reflete a ÚLTIMA tentativa (autorizada), não a rejeitada — a busca
    # de emissão por fabrica_doc_id tem que ficar com a de maior id, não uma qualquer.
    st_get, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st_get == 200
    linha = next((x for x in g["fabrica_xmls"] if x["id"] == doc_id), None)
    assert linha is not None and linha["emissao"]["status"] == "autorizado", g

    db = app_db.get_session()
    regs = (db.query(app_db.DocumentoFiscal).filter_by(fabrica_doc_id=doc_id)
              .order_by(app_db.DocumentoFiscal.id.asc()).all())
    assert len(regs) == 2, "cada tentativa vira sua própria linha — histórico, não sobrescrita"
    assert regs[0].status == "erro" and regs[1].status == "autorizado"
    db.close()


def test_segunda_tentativa_nao_e_bloqueada_por_estar_travada(
        http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Controle-irmão: uma emissão AUTORIZADA continua travada (idempotente) — o destravamento
    da causa 1 é só pra erro/cancelado, não afrouxa o caso já resolvido."""
    class _FakeAutorizaDeCara:
        def __init__(self): self.client = _FakeClientAutorizaSegunda()
        def emitir_nfe_produto(self, nota):
            return resultado_de_focus({
                "ref": nota["ref"], "status": "autorizado", "chave_nfe": "CH-1",
                "numero": "1", "serie": "1",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})
    fake = _FakeAutorizaDeCara()
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: fake)
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    doc_id = up["documento_id"]

    st1, b1 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                    {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st1 == 200 and b1["status"] == "autorizado", b1
    ref1 = b1["ref"]

    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                    {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st2 == 200 and b2["status"] == "autorizado" and b2["ref"] == ref1, b2
