"""docs/db/TESTE_FAILSOFT_NFE.md — ACHADO-18: a NF-e pode ser emitida sem `valor_total`?

MEDIÇÃO, NÃO CONSERTO. Resposta: NÃO é alcançável pela UI/API reais hoje — mas não por uma
validação explícita de `valor_total > 0` em nenhum ponto do caminho (contrato/NF-e só checam
"tem ambiente"). O que impede é um FATO MECÂNICO: o único caminho real pelo qual um ambiente
com valor passa a integrar um orçamento (`POST /orcamentos/<oid>/ambientes/<pid>`, e as
variações de sobrescrita/nova-versão de XML) já chama `_recalcular_orcamento` — que persiste
`valor_total` — na MESMA requisição, sem try/except ao redor (main.py:12278): se o recálculo
falhar, a requisição inteira falha e nada é anexado. Não existe caminho de duplicar/clonar
orçamento que copie o vínculo de ambiente sem recalcular (grep confirma).

Isso significa: a ordem das telas hoje IMPEDE o cenário do ACHADO-18, mas nenhum código
IMPEDE DELIBERADAMENTE um caminho futuro que anexe ambiente sem recalcular — um redesenho
reabriria o buraco em silêncio. Os dois testes abaixo são guarda de regressão para esse fato
mecânico específico, não uma correção do fail-soft."""
import json


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def test_anexar_ambiente_persiste_valor_total(app_db, seed, http_client_factory):
    """O único caminho real de dar valor a um orçamento (anexar ambiente já existente no pool)
    recalcula e persiste valor_total na mesma requisição — é ISSO que impede o ACHADO-18 hoje,
    não uma validação de valor_total>0."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    try:
        antes = db.get(app_db.Orcamento, oid).valor_total
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                                 nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                                 budget_total=90000.0, order_total=40000.0)
        db.add(pa); db.commit()
        pa_id = pa.id
    finally:
        db.close()
    assert not antes, "pré-condição do teste: orçamento novo nasce sem valor_total"

    c = _login(http_client_factory, "dir_l1")
    st, b = c.post("/orcamentos/%d/ambientes/%d" % (oid, pa_id), {})
    assert st == 200 and b["ok"], b

    db = app_db.get_session()
    try:
        depois = db.get(app_db.Orcamento, oid).valor_total
    finally:
        db.close()
    assert depois and depois > 0, (
        "anexar ambiente pelo caminho real deveria persistir valor_total>0 na mesma "
        "requisição — se isto falhar, o ACHADO-18 (NF-e sem valor_total, em silêncio) "
        "voltou a ser alcançável")


def test_gerar_contrato_recusa_orcamento_sem_ambiente(app_db, seed, http_client_factory):
    """A barreira que existe de fato hoje: `POST .../contrato` recusa um orçamento SEM
    ambiente (main.py:13729-13736) — mas note que essa checagem é "tem ambiente", não
    "valor_total > 0". Um orçamento com ambiente porém valor_total=0/None (ex.: XML de preço
    zero) NÃO é barrado por este gate especificamente — ver docstring do módulo.

    Usa o orçamento da LOJA 2 (`seed`), nunca tocado pelo outro teste deste arquivo — `seed` é
    module-scoped, então usar o mesmo orçamento do teste vizinho tornaria isto dependente de
    ordem (o outro teste anexa um ambiente ao da loja 1)."""
    oid = seed["orcamento_l2_id"]
    c = _login(http_client_factory, "dir_l2")
    db = app_db.get_session()
    try:
        cli = db.get(app_db.Cliente, seed["cliente_l2_id"])
        cli.email = "cliente@exemplo.com"; cli.telefone = "(11) 99999-0000"
        cli.cep = "01310-100"; cli.logradouro = "Av. Paulista"; cli.numero = "1000"
        cli.bairro = "Bela Vista"; cli.cidade = "São Paulo"; cli.estado = "SP"
        cli.inst_mesmo_residencial = 1
        db.commit()
    finally:
        db.close()
    c.post("/api/projetos/%s/contatos-comunicacao/confirmar" % seed["projeto_l2"],
           {"modo": "sem_whatsapp"})
    st, b = c.post("/api/projetos/%s/contrato" % seed["projeto_l2"], {
        "orcamento_id": oid, "endereco_instalacao": "Av. Paulista, 1000",
        "pagamento_json": json.dumps({"tipo": "avista", "total_cliente": 0}),
        "confirmar_loja_incompleta": True,
    })
    assert st == 400 and not b["ok"]
    assert "ambiente" in b["erro"].lower(), b
