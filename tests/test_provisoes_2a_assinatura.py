"""Timing correto das provisões (2026-08-12): nascem só na 2ª assinatura completa (loja+cliente),
nunca antes — testado via o endpoint real `POST /api/projetos/<nome>/contrato/assinar` (não a
função interna: mantém o teste válido independente de refatoração posterior do endpoint). Junto,
o snapshot imutável da negociação.

`seed` é module-scoped (compartilhado entre os testes deste arquivo) — cada teste que mexe em
assinaturas precisa limpar o estado anterior primeiro (mesmo padrão de isolamento já usado em
`test_af_gate_data_entrega.py::_prep_assinatura_folga`), senão a 2ª chamada vira reentrega
(idempotente, no-op) por causa da assinatura que sobrou do teste anterior.
"""
import json
from datetime import datetime

from database import Contrato, ContratoAssinatura, Projeto, ProvisaoRegistro


def _reset_contrato(app_db, seed):
    """Isolamento entre testes + datas exigidas pelo gate de assinatura (folga/medição)."""
    db = app_db.get_session()
    cid = seed["contrato_l1_id"]
    db.query(ContratoAssinatura).filter_by(contrato_id=cid).delete()
    ct = db.get(Contrato, cid)
    ct.status = "para_assinatura"
    ct.snapshot_negociacao_json = None
    db.query(ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
    p = db.get(Projeto, seed["projeto_l1"])
    p.previsao_medicao = datetime(2028, 1, 1)
    p.data_entrega = datetime(2028, 3, 1)   # folga positiva — sem gate de autorização no caminho
    db.commit()
    db.close()


def _assinar(c, nome, parte, nome_sig, cpf_sig):
    return c.post("/api/projetos/%s/contrato/assinar" % nome,
                  {"parte": parte, "nome": nome_sig, "cpf": cpf_sig})


def _sem_provisao_venda(app_db, orcamento_id):
    db = app_db.get_session()
    reg = db.query(ProvisaoRegistro).filter_by(orcamento_id=orcamento_id, versao="venda").first()
    db.close()
    return reg


def test_provisao_nao_existe_apos_1a_assinatura(app_db, seed, http_client_factory):
    _reset_contrato(app_db, seed)
    nome = seed["projeto_l1"]
    c = http_client_factory(); c.login("dir_l1", "senha123")

    st, d = _assinar(c, nome, "loja", "Loja", "11144477735")
    assert st == 200 and d.get("ok"), (st, d)

    assert _sem_provisao_venda(app_db, seed["orcamento_l1_id"]) is None, \
        "provisão não pode existir com só 1 assinatura"
    db = app_db.get_session()
    ct = db.get(Contrato, seed["contrato_l1_id"])
    assert ct.snapshot_negociacao_json is None
    db.close()


def test_provisao_nasce_na_2a_assinatura_completa(app_db, seed, http_client_factory):
    _reset_contrato(app_db, seed)
    nome = seed["projeto_l1"]
    c = http_client_factory(); c.login("dir_l1", "senha123")

    st1, d1 = _assinar(c, nome, "loja", "Loja", "11144477735")
    assert st1 == 200 and d1.get("ok"), (st1, d1)
    st2, d2 = _assinar(c, nome, "cliente", "Cliente", "11144477735")
    assert st2 == 200 and d2.get("ok"), (st2, d2)

    reg = _sem_provisao_venda(app_db, seed["orcamento_l1_id"])
    assert reg is not None, "provisão deve existir após a 2ª assinatura completa"

    db = app_db.get_session()
    ct = db.get(Contrato, seed["contrato_l1_id"])
    assert ct.snapshot_negociacao_json is not None, "snapshot imutável deve ser gravado na 2ª assinatura"
    snap = json.loads(ct.snapshot_negociacao_json)
    for campo in ("desconto_pct", "forma_pagamento", "negociacao_json", "valor_total",
                  "valor_liquido", "parametros_json"):
        assert campo in snap, "snapshot incompleto, falta %s" % campo
    db.close()


def test_reentrega_nao_duplica_provisao(app_db, seed, http_client_factory):
    """Reenviar a mesma assinatura (ex.: duplo clique / reentrega de webhook) é no-op — não
    duplica a constituição da provisão."""
    _reset_contrato(app_db, seed)
    nome = seed["projeto_l1"]
    c = http_client_factory(); c.login("dir_l1", "senha123")

    _assinar(c, nome, "loja", "Loja", "11144477735")
    _assinar(c, nome, "cliente", "Cliente", "11144477735")
    st3, d3 = _assinar(c, nome, "cliente", "Cliente", "11144477735")   # reentrega
    assert st3 == 400 and not d3.get("ok"), (st3, d3)   # endpoint recusa parte já assinada

    db = app_db.get_session()
    n = db.query(ProvisaoRegistro).filter_by(
        orcamento_id=seed["orcamento_l1_id"], versao="venda").count()
    db.close()
    assert n == 1, "reentrega não pode duplicar o registro de provisão"


def test_enviar_email_simples_chama_smtp(monkeypatch):
    from chat.externo import enviar_email_simples

    enviados = []

    class _FakeSMTP:
        def __init__(self, host, port, timeout=15):
            enviados.append({"host": host, "port": port})
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): enviados[-1]["login"] = u
        def send_message(self, msg):
            enviados[-1]["to"] = msg["To"]
            enviados[-1]["subject"] = msg["Subject"]

    monkeypatch.setenv("ORIZON_SMTP_HOST", "smtp.teste.local")
    monkeypatch.setenv("ORIZON_SMTP_PORT", "587")
    monkeypatch.setenv("ORIZON_SMTP_USER", "user@teste.local")
    monkeypatch.setenv("ORIZON_SMTP_PASS", "senha")
    monkeypatch.setenv("ORIZON_SMTP_FROM", "orizon@teste.local")
    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)

    enviar_email_simples("master@loja.com", "[Orizon] Teste", "corpo do e-mail")

    assert len(enviados) == 1
    assert enviados[0]["to"] == "master@loja.com"
    assert enviados[0]["subject"] == "[Orizon] Teste"


def test_enviar_email_simples_sem_config_levanta_erro(monkeypatch):
    from chat.externo import enviar_email_simples
    monkeypatch.delenv("ORIZON_SMTP_HOST", raising=False)
    try:
        enviar_email_simples("a@b.com", "assunto", "corpo")
        assert False, "deveria ter levantado RuntimeError sem ORIZON_SMTP_HOST"
    except RuntimeError:
        pass
