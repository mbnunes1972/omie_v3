# -*- coding: utf-8 -*-
"""docs/db/TAREFA_ACHADO24.md, F2-1 — aceites do ACHADO-24.

`_materializar_recebiveis_venda_seguro` é compartilhada por dois chamadores: a assinatura que
completa o aditivo (passo 6-c) e a geração de contrato (main.py:13865/14040). Nenhum dos dois
valida que a `forma_pagamento`/`pagamento_json` recebida PRODUZ recebível — só que o campo está
presente (aditivo) ou nem isso (contrato). Um payload `{"tipo": "avista", "total_cliente": 0}`
(sem `parcelas` nem `entrada_valor`) é aceito nos dois; `mod_recebiveis.materializar` nunca lê
`total_cliente` e devolve zero linhas — a venda/aditivo fecha com receita constituída e nenhuma
cobrança, em silêncio (só um `logging.warning`).

Medição (F2-1): os DOIS caminhos estão expostos — não só o aditivo. O conserto adiciona a mesma
guarda nos dois chamadores: valor > 0 exige plano que produza ao menos um `Recebivel`."""
import json

from tests.test_aditivo_wizard_e2e import _setup, _upsert_compl, _login


def _limpar_estado_aditivo(app_db, seed):
    """Mesmo motivo do `test_aditivo_recebiveis_e_custo_financeiro.py`: `_setup`/`seed`/`app_db`
    são module-scoped e reusam o MESMO projeto entre os testes deste arquivo."""
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    for adt in db.query(app_db.Aditivo).filter_by(projeto_nome=nome).all():
        for a in list(adt.assinaturas):
            db.delete(a)
    db.query(app_db.Aditivo).filter_by(projeto_nome=nome).delete()
    db.query(app_db.Recebivel).filter_by(projeto_nome=nome).delete()
    for orc in db.query(app_db.Orcamento).filter_by(projeto_id=nome, complemento_pe=1).all():
        db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=orc.id).delete()
        db.delete(orc)
    db.commit(); db.close()


def _orcamento_com_valor(app_db, seed, budget=90000.0, order=40000.0):
    """Anexa um PoolAmbiente ao orçamento do contrato (`orcamento_l1_id`) e recalcula — precisa
    de valor_total > 0 de verdade pra testar a guarda (diferente do setup do ACHADO-18, que
    precisa do oposto: valor_total nulo)."""
    import main
    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id=nome, nome="Cozinha", nome_exibicao="Cozinha",
                             xml_path="fake/coz.xml", ambientes_json="{}",
                             budget_total=budget, order_total=order)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    orc = db.get(app_db.Orcamento, oid)
    main._recalcular_orcamento(orc, db)
    db.commit()
    valor_total = orc.valor_total
    db.close()
    return oid, valor_total


def _cliente_e_loja_completos(app_db, seed, c, nome):
    c.post(f"/api/projetos/{nome}/contatos-comunicacao/confirmar", {"modo": "sem_whatsapp"})
    db = app_db.get_session()
    cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
    cli.email = "cliente@exemplo.com"; cli.telefone = "(11) 99999-0000"
    cli.cep = "01310-100"; cli.logradouro = "Av. Paulista"; cli.numero = "1000"
    cli.bairro = "Bela Vista"; cli.cidade = "São Paulo"; cli.estado = "SP"
    cli.inst_mesmo_residencial = 1
    db.commit(); db.close()


# ── 1. Aditivo ───────────────────────────────────────────────────────────────────────────────

def test_aditivo_com_plano_vazio_e_recusado(app_db, seed, http_client_factory):
    _limpar_estado_aditivo(app_db, seed)
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body

    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "loja", "nome": "Rep Loja", "cpf": "111.444.777-35"})
    assert st == 200 and body["status"] == "assinado_loja", body

    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "cliente", "nome": "Cliente L1", "cpf": "222.333.444-05",
                       "forma_pagamento": json.dumps({"tipo": "avista", "total_cliente": 0})})
    assert not (st == 200 and body.get("ok")), (
        "assinatura do aditivo deveria ser RECUSADA com plano de pagamento vazio (presente, "
        "sem parcelas/entrada_valor) — resposta hoje: st=%r body=%r" % (st, body))


# ── 2. Geração de contrato ───────────────────────────────────────────────────────────────────

def test_contrato_com_plano_vazio_e_recusado(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    oid, valor_total = _orcamento_com_valor(app_db, seed)
    assert (valor_total or 0) > 0, "pré-condição: valor_total tem que ser > 0"

    c = _login(http_client_factory, "dir_l1")
    _cliente_e_loja_completos(app_db, seed, c, nome)

    st, body = c.post(f"/api/projetos/{nome}/contrato", {
        "orcamento_id": oid, "endereco_instalacao": "Av. Paulista, 1000",
        "pagamento_json": json.dumps({"tipo": "avista", "total_cliente": 0}),
        "confirmar_loja_incompleta": True,
    })
    assert not (st == 200 and body.get("ok")), (
        "geração de contrato deveria ser RECUSADA com plano de pagamento vazio (valor_total > "
        "0, zero recebível) — resposta hoje: st=%r body=%r" % (st, body))


# ── 3. Controle positivo — plano normal não sofre ruído ─────────────────────────────────────

def test_aditivo_com_plano_real_materializa_recebivel_e_passa(app_db, seed, http_client_factory):
    _limpar_estado_aditivo(app_db, seed)
    nome, pid, pid2 = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj_id = body["orcamento"]["id"]

    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body

    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = json.dumps(
                {"tipo": "avista", "parcelas": [{"valor": 4444.44}]})
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st == 200 and body.get("ok", True), body
    assert body["status"] == "assinado"

    db = app_db.get_session()
    recebiveis = db.query(app_db.Recebivel).filter_by(orcamento_id=aj_id).all()
    db.close()
    assert recebiveis, "plano real deveria materializar recebível(is) — guarda não pode barrar caso legítimo"


def test_contrato_com_plano_real_materializa_recebivel_e_passa(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    oid, valor_total = _orcamento_com_valor(app_db, seed)
    assert (valor_total or 0) > 0

    c = _login(http_client_factory, "dir_l1")
    _cliente_e_loja_completos(app_db, seed, c, nome)

    st, body = c.post(f"/api/projetos/{nome}/contrato", {
        "orcamento_id": oid, "endereco_instalacao": "Av. Paulista, 1000",
        "pagamento_json": json.dumps({"tipo": "avista",
                                      "parcelas": [{"num": 1, "valor": valor_total}]}),
        "confirmar_loja_incompleta": True,
    })
    assert st == 200 and body.get("ok"), (
        "plano real deveria ser aceito normalmente — guarda não pode barrar caso legítimo: %r"
        % body)

    db = app_db.get_session()
    recebiveis = db.query(app_db.Recebivel).filter_by(orcamento_id=oid).all()
    db.close()
    assert recebiveis, "plano real deveria materializar recebível(is)"
