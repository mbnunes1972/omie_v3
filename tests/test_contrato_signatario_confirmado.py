"""Frente 3 (achado do usuário 2026-08-17): o signatário confirmado na aprovação do orçamento
(override do modal ou o Cliente cadastrado) sobrevive em Contrato.cliente_nome_confirmado/
cpf_confirmado, e é exposto em GET .../contrato como `assinatura_defaults` — pré-preenche a
confirmação de assinatura manual (interna) em vez de nascer em branco."""
import json as _json
from tests.test_fluxo_completo_e2e import _setup_cenario


def _gerar_contrato(c, nome, oid, extra=None):
    body = {
        "orcamento_id": oid,
        "endereco_instalacao": "Av. Paulista, 1000 - São Paulo/SP",
        "pagamento_json": _json.dumps({"tipo": "avista", "total_cliente": 90000.0,
                                       "parcelas": [{"num": 1, "valor": 90000.0}]}),
        "confirmar_loja_incompleta": True,
    }
    if extra:
        body.update(extra)
    return c.post("/api/projetos/%s/contrato" % nome, body)


def test_sem_override_confirma_dados_do_cliente_cadastrado(app_db, seed, http_client_factory):
    _setup_cenario(app_db, seed)
    nome = seed["projeto_l1"]
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/projetos/%s/contatos-comunicacao/confirmar" % nome, {"modo": "sem_whatsapp"})

    st, b = _gerar_contrato(c, nome, seed["orcamento_l1_id"])
    assert st == 200 and b["ok"], b

    db = app_db.get_session()
    cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
    ct = db.get(app_db.Contrato, b["contrato_id"])
    assert ct.cliente_nome_confirmado == cli.nome
    assert ct.cliente_cpf_confirmado == (cli.cpf or "")
    db.close()

    st2, d2 = c.get("/api/projetos/%s/contrato" % nome)
    assert st2 == 200 and d2["ok"]
    defs = d2["contrato"]["assinatura_defaults"]
    assert defs["nome_cliente"] == cli.nome
    assert defs["cpf_cliente"] == (cli.cpf or "")
    assert defs["nome_loja"]   # veio do usuário logado (dir_l1)
    assert defs["cpf_loja"] == ""   # sistema não guarda CPF de quem assina pela loja


def test_com_override_confirma_dados_do_override_nao_do_cadastro(app_db, seed, http_client_factory):
    _setup_cenario(app_db, seed)
    nome = seed["projeto_l1"]
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/projetos/%s/contatos-comunicacao/confirmar" % nome, {"modo": "sem_whatsapp"})

    override = {
        "nome": "Procurador Fulano de Tal", "cpf": "22233344455",
        "email": "procurador@exemplo.com", "telefone": "(11) 98888-0000",
        "cep": "01310-100", "logradouro": "Av. Paulista", "numero": "1000",
        "bairro": "Bela Vista", "cidade": "São Paulo", "estado": "SP",
    }
    st, b = _gerar_contrato(c, nome, seed["orcamento_l1_id"], extra={"signatario_override": override})
    assert st == 200 and b["ok"], b

    db = app_db.get_session()
    cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
    ct = db.get(app_db.Contrato, b["contrato_id"])
    assert ct.cliente_nome_confirmado == "Procurador Fulano de Tal"
    assert ct.cliente_cpf_confirmado == "22233344455"
    assert ct.cliente_nome_confirmado != cli.nome
    db.close()

    st2, d2 = c.get("/api/projetos/%s/contrato" % nome)
    defs = d2["contrato"]["assinatura_defaults"]
    assert defs["nome_cliente"] == "Procurador Fulano de Tal"
    assert defs["cpf_cliente"] == "22233344455"
