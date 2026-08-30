"""docs/db/TAREFA_FASE0.md (passo 4) + docs/db/TAREFA_ACHADO18.md (passo 9) — os aceites do
ACHADO-18.

Os aceites escritos no passo 4 construíam o estado que a medição (`tests/test_failsoft_nfe_
medicao.py`) disse ser mecanicamente inalcançável pelos caminhos normais (anexar ambiente pela
HTTP sempre recalcula valor_total na mesma requisição) — DIRETO NO BANCO — e afirmavam que o
estado existia ANTES de exercitar a rota, para que um setup que silenciosamente recalculasse não
fizesse o teste passar por engano. O passo 9 acrescentou a guarda explícita de valor_total > 0
em `/contrato`, `/emitir-nfe` e `/emitir-nfse` (main.py) — os dois `xfail(strict=True)` saíram
neste commit. A guarda de NF-e/NFS-e lê o TOTAL CONTRATADO (`valor_contratado_do_projeto` —
contrato + aditivos assinados, ACHADO-12), não só o valor_total do orçamento do contrato:
`test_emitir_nfe_passa_com_aditivo_assinado_positivo_mesmo_com_contrato_zerado` prova que um
contrato zerado com aditivo assinado positivo NÃO é recusado."""
import json
import os
import urllib.request
import urllib.error
import uuid as _uuid

import pytest

from fiscal import nfe_emissao
from integracoes.emissor_fiscal import resultado_de_focus


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _anexar_ambiente_direto_no_banco(app_db, seed, oid, projeto_id, budget=90000.0, order=40000.0):
    """Vincula um PoolAmbiente ao orçamento SEM passar por `POST /orcamentos/<id>/ambientes/<pid>`
    (esse endpoint sempre chama `_recalcular_orcamento` na mesma requisição — main.py:12278 — e
    persistiria valor_total>0, o que apagaria exatamente o estado que este teste precisa
    reproduzir). Só o vínculo, direto no banco."""
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id=projeto_id, nome="Cozinha", versao=1,
                             nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                             budget_total=budget, order_total=order)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id))
    db.commit()
    db.close()


def test_gerar_contrato_recusa_valor_total_zero(app_db, seed, http_client_factory):
    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    _anexar_ambiente_direto_no_banco(app_db, seed, oid, nome)

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    tem_ambiente = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).count() > 0
    valor_total_antes = orc.valor_total
    db.close()
    assert tem_ambiente, "pré-condição do teste: ambiente tem que estar vinculado"
    assert valor_total_antes in (None, 0, 0.0), (
        "pré-condição do teste: valor_total tem que estar nulo/zero ANTES de chamar a rota — "
        "se isto falhar, o setup recalculou por engano e o teste provaria a coisa errada: %r"
        % valor_total_antes)

    c = _login(http_client_factory, "dir_l1")
    c.post("/api/projetos/%s/contatos-comunicacao/confirmar" % nome, {"modo": "sem_whatsapp"})
    db = app_db.get_session()
    cli = db.get(app_db.Cliente, seed["cliente_l1_id"]) if "cliente_l1_id" in seed else None
    if cli is not None:
        cli.email = "cliente@exemplo.com"; cli.telefone = "(11) 99999-0000"
        cli.cep = "01310-100"; cli.logradouro = "Av. Paulista"; cli.numero = "1000"
        cli.bairro = "Bela Vista"; cli.cidade = "São Paulo"; cli.estado = "SP"
        cli.inst_mesmo_residencial = 1
        db.commit()
    db.close()

    st, body = c.post("/api/projetos/%s/contrato" % nome, {
        "orcamento_id": oid, "endereco_instalacao": "Av. Paulista, 1000",
        "pagamento_json": json.dumps({"tipo": "avista", "total_cliente": 0}),
        "confirmar_loja_incompleta": True,
    })
    assert not (st == 200 and body.get("ok")), (
        "geração de contrato deveria ser RECUSADA com valor_total nulo/zero — resposta hoje: "
        "st=%r body=%r" % (st, body))
    assert "valor" in (body.get("erro") or "").lower(), body


# ── ACHADO-18 · NF-e ─────────────────────────────────────────────────────────────────────────
class _FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH-A18",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    def baixar(self, caminho):
        return b"BYTES"


class _FakeEmissor:
    def __init__(self): self.client = _FakeClient()
    def emitir_nfe_produto(self, nota):
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})
    def consultar_status(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CH-A18",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})


def _fixture_xml():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml"), "rb") as f:
        return f.read()


def _perfil(app_db, loja_id):
    from fiscal import fiscal_cripto
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id) if loja.emitente_id else None
    if em is None:
        em = app_db.Emitente(cnpj="9100000000%02d" % loja_id, razao_social="LOJA X",
                             regime_tributario="simples", csosn_padrao="102",
                             cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                             cidade="Sao Paulo", logradouro="Rua A", numero="1",
                             bairro="Centro", cep="01000-000")
        db.add(em); db.flush()
        loja.emitente_id = em.id
    em.ambiente_ativo = "homologacao"
    em.focus_token_homolog_enc = fiscal_cripto.encrypt("tok-homolog")
    db.commit(); db.close()


def _upload_xml(c, proj, data):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--" + boundary + "\r\n").encode(),
             ('Content-Disposition: form-data; name="arquivo"; filename="fabrica.xml"\r\n').encode(),
             b"Content-Type: application/octet-stream\r\n\r\n", data, b"\r\n",
             ("--" + boundary + "--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/nfe-fabrica",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_emitir_nfe_recusa_valor_total_zero(app_db, seed, http_client_factory, monkeypatch, projetos_dir):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: _FakeEmissor())
    nome = seed["projeto_l2"]
    oid = seed["orcamento_l2_id"]
    _perfil(app_db, seed["loja2_id"])

    db = app_db.get_session()
    contrato = db.query(app_db.Contrato).filter_by(projeto_nome=nome).first()
    contrato_aponta_pro_orcamento = contrato is not None and contrato.orcamento_id == oid
    valor_total_antes = db.get(app_db.Orcamento, oid).valor_total
    db.close()
    assert contrato_aponta_pro_orcamento, "pré-condição do teste: Contrato tem que existir e apontar pro orçamento"
    assert valor_total_antes in (None, 0, 0.0), (
        "pré-condição do teste: valor_total tem que estar nulo/zero ANTES de emitir — %r"
        % valor_total_antes)

    c = _login(http_client_factory, "dir_l2")
    st_up, up = _upload_xml(c, nome, _fixture_xml())
    assert st_up == 200 and up.get("documento_id"), up

    st, body = _post(c, f"/api/projetos/{nome}/ciclo/15/emitir-nfe",
                     {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert not (st == 200 and body.get("ok") and body.get("status") == "autorizado"), (
        "emissão de NF-e deveria ser RECUSADA com Val_Cont nulo/zero — resposta hoje: "
        "st=%r body=%r" % (st, body))


def test_emitir_nfe_passa_com_aditivo_assinado_positivo_mesmo_com_contrato_zerado(
        app_db, seed, http_client_factory, monkeypatch, projetos_dir):
    """Detalhe que mudou desde a medição (docs/db/TAREFA_ACHADO18.md): a guarda lê o TOTAL
    CONTRATADO (contrato + aditivos assinados, `valor_contratado_do_projeto` — ACHADO-12), não só
    o valor_total do orçamento do contrato. Um contrato zerado com aditivo assinado positivo NÃO
    é recusado."""
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: _FakeEmissor())
    nome = seed["projeto_l2"]
    oid = seed["orcamento_l2_id"]
    _perfil(app_db, seed["loja2_id"])

    db = app_db.get_session()
    contrato = db.query(app_db.Contrato).filter_by(projeto_nome=nome).first()
    assert contrato is not None and contrato.orcamento_id == oid
    valor_total_antes = db.get(app_db.Orcamento, oid).valor_total
    assert valor_total_antes in (None, 0, 0.0), "pré-condição: orçamento do contrato zerado"

    orc_complemento = app_db.Orcamento(projeto_id=nome, nome="Complemento", valor_total=5000.0)
    db.add(orc_complemento); db.flush()
    db.add(app_db.Aditivo(projeto_nome=nome, contrato_id=contrato.id,
                          orcamento_complemento_id=orc_complemento.id, status="assinado"))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l2")
    st_up, up = _upload_xml(c, nome, _fixture_xml())
    assert st_up == 200 and up.get("documento_id"), up

    st, body = _post(c, f"/api/projetos/{nome}/ciclo/15/emitir-nfe",
                     {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and body.get("ok") and body.get("status") == "autorizado", (
        "emissão de NF-e NÃO deveria ser recusada — contrato zerado, mas aditivo assinado "
        "positivo cobre o total contratado: st=%r body=%r" % (st, body))


def _post(c, path, body):
    req = urllib.request.Request(c.base + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie:
        req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
