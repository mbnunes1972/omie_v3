# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-50 — nota em PROCESSANDO é reportada como FALHA.

Simula a Focus devolvendo "processando_autorizacao" além do timeout de
`aguardar_processamento` (60s) — o `FakeEmissor`/`FakeClient` abaixo nunca sai desse status,
como se o polling tivesse esgotado as tentativas sem a SEFAZ resolver. Aceite: a resposta NÃO é
falha (`ok: True`, sem prefixo "Falha na emissão"), vem com mensagem dedicada dizendo que está
na fila, e o caminho de consulta (`GET .../ciclo/15/nfe`) já expõe a emissão pendente — o
"Consultar" que a tela desenha pra qualquer emissão registrada."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fiscal import nfe_emissao
from integracoes.emissor_fiscal import resultado_de_focus

from tests.test_nfe_etapa15_e2e import _reset15, _perfil, _login, _upload_xml, _fixture_xml, _post


class _FakeClientSempreProcessando:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        # Simula o timeout esgotado: o polling nunca sai de "processando_autorizacao".
        return {"ref": ref, "status": "processando_autorizacao"}
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "processando_autorizacao"}
    def baixar(self, caminho): return b"BYTES"


class _FakeEmissorSempreProcessando:
    def __init__(self): self.client = _FakeClientSempreProcessando()
    def emitir_nfe_produto(self, nota):
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})
    def emitir_nfse_servico(self, nota):
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})


def test_nfe_produto_pendente_nao_e_falha_e_oferece_consultar(
        http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: _FakeEmissorSempreProcessando())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    doc_id = up["documento_id"]
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st == 200 and b["ok"] is True, b
    assert b["status"] == "processando"
    assert "falha" not in (b.get("erro") or "").lower()
    assert b.get("mensagem") and "fila da SEFAZ" in b["mensagem"], b
    # o caminho de consulta: a emissão pendente já aparece pro GET que alimenta a tela — é o que
    # faz o botão "Consultar" ser desenhado (_renderCardEmissaoNfe só desenha pra emissão != None).
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 == 200
    linha = next((x for x in g["fabrica_xmls"] if x["id"] == doc_id), None)
    assert linha is not None and linha["emissao"] is not None, g
    assert linha["emissao"]["status"] == "processando"


def test_nfse_servico_pendente_nao_e_falha(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: _FakeEmissorSempreProcessando())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfse", {"valor_servico": 500})
    assert st == 200 and b["ok"] is True, b
    assert b["status"] == "processando"
    assert "falha" not in (b.get("erro") or "").lower()
    assert b.get("mensagem") and "fila da SEFAZ" in b["mensagem"], b
