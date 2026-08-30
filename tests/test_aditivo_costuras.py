"""docs/db/TAREFA_ADITIVO.md — Costuras 4 e 2. MEDIÇÃO, NÃO CONSERTO.

Costura 4 (reproduzida com números, ANTES de qualquer conclusão): uma revisão de PE recebida
DEPOIS de um aditivo assinado cobra a MESMA diferença de novo, a partir da linha de base do
CONTRATO original — porque `_complemento_diferencas`/`_pe_fator_contexto` sempre comparam contra
`Contrato.orcamento_id`, nunca contra "contrato + aditivos já assinados", E `/pe/complemento/
orcamento` reaproveita (get-or-create) o MESMO `Orcamento` de complemento que o aditivo já
assinado referencia, sobrescrevendo seu `valor_total` — e um novo `Aditivo` (mesmo
`orcamento_complemento_id`, `ref` diferente por ser outro `aditivo.id`) constitui uma nova
`registro_venda_contrato` pelo total CHEIO da nova diferença, não pelo incremento.

Costura 2 (teste de regressão, escrito ANTES de qualquer conserto): confirma que
`faturar_segmento` decide o que falta faturar pelo SALDO ATUAL da conta 2.1.06 (não por um total
anterior armazenado) — então, mesmo que uma futura soma da Costura 1 faça
`_valores_segmentados_do_projeto` devolver contrato+aditivo, uma reemissão de NF-e para o mesmo
segmento NÃO fatura de novo o que já foi drenado da conta. Este teste tem que continuar verde
depois de qualquer implementação da soma da Costura 1."""
import json

import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _setup(app_db, seed, qual="l1"):
    """Mesmo setup de tests/test_complemento_pe_e2e.py::_setup: contrato assinado, 1 ambiente de
    80k com comissão de arquiteto 10% repassada (VAVA contratado = 80.000/0,9 = 88.888,89).
    Idempotente: `seed`/`app_db` são module-scoped e mais de um teste deste arquivo chama
    `_setup` sobre o MESMO `oid` — sem essa guarda, cada chamada extra duplicava o ambiente
    "Cozinha" no mesmo orçamento, dobrando o VAVO (achado ao rodar o arquivo inteiro junto).
    `qual` ("l1"/"l2") escolhe QUAL projeto do seed usar — a Costura 4 assina aditivos de
    verdade no projeto, então a Costura 2 usa o OUTRO projeto (l2) pra não herdar esse estado
    (achado ao rodar o arquivo inteiro junto, depois do ACHADO-21 passar a ler aditivos
    assinados na mesma conta/ambiente)."""
    oid = seed["orcamento_l%s_id" % qual[1]]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    proj = db.query(app_db.Projeto).filter_by(nome_safe=nome).first()
    proj.parametros_json = json.dumps({"incluir_custos": True, "comissao_arq_ativa": True,
                                       "comissao_arq_pct": 10.0, "carga_trib": 0.0,
                                       "pct_mercadoria": 100.0, "pct_servico": 0.0})
    ja = (db.query(app_db.PoolAmbiente).filter_by(projeto_id=nome, nome="Cozinha").first())
    if ja is not None:
        pa = ja
    else:
        pa = app_db.PoolAmbiente(nome="Cozinha", nome_exibicao="Cozinha", xml_path="fake/coz.xml",
                                 ambientes_json="{}", projeto_id=nome,
                                 budget_total=80000.0, order_total=30000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    pa.renegociar_pe = 1
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    if not db.query(app_db.ContratoAssinatura).filter_by(contrato_id=ct.id, parte="loja").first():
        db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="Loja",
                                         cpf="000.000.000-00", hash_sha256="x"))
    db.commit()
    pid = pa.id
    db.close()
    import main as _main, os
    pdir = os.path.join(_main.PROJETOS_DIR, nome)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "projeto.json"), "w", encoding="utf-8") as f:
        json.dump({"nome_projeto": nome}, f)
    return nome, pid, oid


def _upsert_compl(app_db, nome, pid, venda, cfo=30000.0):
    db = app_db.get_session()
    reg = (db.query(app_db.ArquivoPE)
             .filter_by(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_compl").first())
    if reg is None:
        reg = app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pid, formato="xml_compl")
        db.add(reg)
    reg.valor_venda = venda
    reg.valor_atualizado = cfo
    db.commit(); db.close()


def _criar_modelo_aditivo(app_db, seed, loja_id=None):
    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, loja_id or seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()


def _assinar_aditivo_completo(c, nome, forma_pagamento=None):
    """ACHADO-21, 6-c: a assinatura que completa (2ª parte) exige forma_pagamento — sem
    default inventado (a tela recusa se não coletar). Passa à vista/entrada 0 por padrão do
    teste, só na 2ª chamada (a 1ª nunca completa sozinha)."""
    fp = forma_pagamento or json.dumps({"tipo": "avista", "total_cliente": 0})
    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        corpo = {"parte": parte, "nome": quem, "cpf": "111.444.777-35"}
        if parte == "cliente":
            corpo["forma_pagamento"] = fp
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar", corpo)
        assert st == 200, body
    assert body["status"] == "assinado"
    return body


def _saldo_2106_credor(app_db, seed, nome, loja_id=None):
    import mod_contabil
    db = app_db.get_session()
    ator = {"loja_id": loja_id or seed["loja1_id"], "rede_id": None}
    ot, oid = mod_contabil.resolver_owner(db, ator)
    mod_contabil.seed_plano(db, ot, oid)   # 1ª chamada pode acontecer antes de qualquer lançamento
    v = mod_contabil.total_lancado(db, ot, oid, "2.1.06", "credito", projeto_id=nome)
    db.close()
    return round(v, 2)


def test_costura4_revisao_apos_aditivo_assinado_nao_duplica_cobranca(app_db, seed, http_client_factory):
    """ACHADO-21 (docs/db/TAREFA_ACHADO21.md, passo 6 do ROTEIRO): CONSERTADO — as duas metades do
    6-b. (1) `POST /pe/complemento/orcamento` não reaproveita mais o orçamento de complemento que
    já tem aditivo assinado — a revisão seguinte cria um orçamento NOVO, e o valor pelo qual o
    cliente assinou o 1º aditivo continua legível, intocado, no orçamento dele. (2) A diferença do
    orçamento novo é calculada contra `valor_contratado_do_projeto` (contrato + aditivos já
    assinados), não contra o contrato sozinho — por isso a revisão 2 cobra só o INCREMENTO real,
    não a diferença cheia de novo."""
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _criar_modelo_aditivo(app_db, seed)

    # valor_contratado_do_projeto lê valor_total PERSISTIDO do contrato (não recomputa ao vivo) —
    # _setup não recalcula/persiste esse valor (o resto do arquivo trabalha via breakdown ao
    # vivo), então sem isto o contrato entraria com 0,0 na conferência final deste teste. Roda
    # também o wiring de fechamento da venda ORIGINAL (credita 2.1.06 pelos 88.888,89 do
    # contrato) — sem isso a conferência final só veria a parte dos aditivos, não o projeto
    # inteiro (contrato + aditivos, que é exatamente o que a aceite #3 do 6-b pede).
    import main as _main
    db = app_db.get_session()
    orc_ct_setup = db.get(app_db.Orcamento, oid)
    _main._recalcular_orcamento(orc_ct_setup, db)
    db.commit()
    _main._fin_provisoes_venda_seguro(orc_ct_setup, nome, "prov:venda-original-teste:" + nome)
    db.close()

    # ── revisão 1: venda=84.000 → diferença = 84.000/0,9 − 88.888,89 = 4.444,44 ──────────────
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj1_id = body["orcamento"]["id"]
    assert abs(body["orcamento"]["valor_total"] - 4444.44) < 0.05, body["orcamento"]["valor_total"]

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    aditivo1_id = body["aditivo"]["id"]

    antes = _saldo_2106_credor(app_db, seed, nome)
    _assinar_aditivo_completo(c, nome)
    depois_ad1 = _saldo_2106_credor(app_db, seed, nome)
    assert abs((depois_ad1 - antes) - 4444.44) < 0.05, (
        "1º aditivo deveria creditar 2.1.06 em 4.444,44 — %r" % (depois_ad1 - antes))

    # ── revisão 2 do MESMO ambiente, DEPOIS do aditivo assinado: venda=90.000 → à vista =
    #    90.000/0,9 = 100.000,00. Contra o CONTRATO sozinho (88.888,89) daria 11.111,11 de novo
    #    (o defeito). Contra valor_contratado_do_projeto (88.888,89 + 4.444,44 = 93.333,33), o
    #    incremento real é 100.000,00 − 93.333,33 = 6.666,67. ──────────────────────────────────
    _upsert_compl(app_db, nome, pid, venda=90000.0, cfo=34000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj2_id = body["orcamento"]["id"]
    assert aj2_id != aj1_id, (
        "6-b, metade 1: a revisão depois do aditivo assinado tem que criar um Orcamento NOVO, "
        "não reaproveitar o que o 1º aditivo já assinou")
    assert abs(body["orcamento"]["valor_total"] - 6666.67) < 0.05, (
        "6-b, metade 2: a diferença do orçamento novo tem que ser calculada contra "
        "valor_contratado_do_projeto (93.333,33), não contra o contrato sozinho (o que daria "
        "11.111,11 de novo) — valor obtido: %r" % body["orcamento"]["valor_total"])

    # o valor do aditivo #1 continua legível no orçamento dele — imutável (6-b, linha de desenho)
    db = app_db.get_session()
    valor_aj1_depois = db.get(app_db.Orcamento, aj1_id).valor_total
    db.close()
    assert abs(valor_aj1_depois - 4444.44) < 0.05, (
        "o valor pelo qual o cliente assinou o aditivo #1 não pode ter mudado — %r" % valor_aj1_depois)

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"novo": True})
    assert st == 200 and body["ok"], body
    aditivo2_id = body["aditivo"]["id"]
    assert aditivo2_id != aditivo1_id

    _assinar_aditivo_completo(c, nome)
    depois_ad2 = _saldo_2106_credor(app_db, seed, nome)

    total_creditado_aditivos = round(depois_ad2 - antes, 2)
    assert abs(total_creditado_aditivos - 11111.11) < 0.05, (
        "2.1.06 tem que fechar em 11.111,11 pelos dois aditivos juntos (4.444,44 + 6.666,67) — "
        "a diferença final real, sem duplicar o que o 1º aditivo já cobrou: %r"
        % total_creditado_aditivos)

    # aceite #3 do 6-b (docs/db/TAREFA_ACHADO21.md): a conferência do ACHADO-21 fecha — soma dos
    # créditos de 2.1.06 do projeto inteiro (contrato + os dois aditivos assinados) ==
    # valor_contratado_do_projeto. Antes do 6-b isto divergia (o 2º aditivo cobrava 11.111,11 de
    # novo em vez de 6.666,67, então a soma de 2.1.06 batia SÓ com a soma bruta das duas
    # cobranças, não com o que o projeto realmente vale).
    db = app_db.get_session()
    v_contratado = _main.valor_contratado_do_projeto(db, nome)
    db.close()
    assert abs(v_contratado - (88888.89 + 4444.44 + 6666.67)) < 0.05, v_contratado
    assert abs(depois_ad2 - v_contratado) < 0.05, (
        "soma dos créditos de 2.1.06 do projeto (%.2f) tem que bater com "
        "valor_contratado_do_projeto (%.2f)" % (depois_ad2, v_contratado))


def test_costura2_reemissao_nao_duplica_o_ja_faturado(app_db, seed, http_client_factory, monkeypatch):
    """ACHADO-13 (docs/db/TAREFA_ACHADO13.md, passo 5 do ROTEIRO): CONSERTADO — `faturar_segmento`
    agora é delta-aware na receita (lê `_mov(..., "credor")` na própria conta de 4.1.01/4.2.01,
    líquido de estornos, e fatura só a diferença contra o `valor` recebido, que passou a
    significar "o total que deve estar reconhecido"). Simula o que a Costura 1 faria (somar
    aditivo ao Val_Cont segmentado) via monkeypatch em `_valores_segmentados_do_projeto` — SEM
    implementar a soma de verdade (fora do escopo desta tarefa, ver ACHADO-12/passo 7) — e
    confirma que a 2ª NF-e pós-aditivo fatura só o incremento, não o total somado de novo.

    Usa o projeto da LOJA 2 (`qual="l2"`), nunca tocado pela Costura 4 — que assina aditivos DE
    VERDADE no projeto da loja 1 (`seed`/`app_db` são module-scoped, e depois do ACHADO-21 a
    diferença de complemento passa a somar aditivos já assinados NA MESMA conta/ambiente;
    compartilhar o projeto faria este teste herdar o estado que a Costura 4 deixou)."""
    import main
    nome, pid, oid = _setup(app_db, seed, qual="l2")
    c = _login(http_client_factory, "dir_l2")
    loja_id = seed["loja2_id"]

    # oid já é o orçamento do CONTRATO ASSINADO — /margens está travado (403) por desenho
    # (test_complemento_pe_e2e.py:103-104). Recalcula direto, como o motor faria antes da
    # assinatura (a rota HTTP é a trava de negócio, não o mecanismo de cálculo em si), e roda o
    # MESMO wiring de fechamento da venda original (2ª assinatura) que credita 2.1.06 — sem isso
    # a conta nunca teria saldo nenhum pra este projeto testar drenagem.
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    main._recalcular_orcamento(orc, db)
    db.commit()
    val_cont_original = round(float(orc.valor_total or 0), 2)
    main._fin_provisoes_venda_seguro(orc, nome, "prov:venda-teste:" + nome)
    db.close()
    assert val_cont_original > 0

    import mod_contabil
    ator = {"loja_id": loja_id, "rede_id": None}
    db = app_db.get_session()
    ot, owner_id = mod_contabil.resolver_owner(db, ator)
    saldo_2106_pre = mod_contabil.saldo_adiantamento_projeto(db, ot, owner_id, nome)
    db.close()
    assert abs(saldo_2106_pre - val_cont_original) < 0.05, (
        "fechamento da venda original deveria creditar 2.1.06 pelo Val_Cont cheio — %r"
        % saldo_2106_pre)

    # 1ª "NF-e" (mercadoria) pelo Val_Cont original — chama o wiring real de faturamento.
    main._fin_faturamento_segmentado_seguro(loja_id, nome, "mercadoria", "NFE-teste-1")
    faturado_1 = mod_contabil.total_lancado(app_db.get_session(), ot, owner_id, "4.1.01",
                                            "credito", projeto_id=nome)
    assert abs(faturado_1 - val_cont_original) < 0.05, faturado_1
    saldo_2106_pos_nfe1 = mod_contabil.saldo_adiantamento_projeto(app_db.get_session(), ot, owner_id, nome)
    assert saldo_2106_pos_nfe1 < 0.01, (
        "2.1.06 deveria estar drenado a zero pela 1ª NF-e — %r" % saldo_2106_pos_nfe1)

    # Aditivo assinado depois da 1ª NF-e: soma R$ 4.444,44 a mais, via o MESMO wiring
    # (_fin_provisoes_venda_seguro credita 2.1.06 de novo pelo valor do aditivo).
    _criar_modelo_aditivo(app_db, seed, loja_id)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj_id = body["orcamento"]["id"]
    diferenca_aditivo = round(body["orcamento"]["valor_total"], 2)
    assert diferenca_aditivo > 0
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    _assinar_aditivo_completo(c, nome)

    # SIMULA a soma da Costura 1 (sem implementá-la): a partir de agora,
    # _valores_segmentados_do_projeto devolveria contrato + aditivo.
    val_cont_somado = round(val_cont_original + diferenca_aditivo, 2)
    _orig = main._valores_segmentados_do_projeto
    def _somado(db, loja_id, projeto_nome):
        v = _orig(db, loja_id, projeto_nome)
        if v is None:
            return None
        v = dict(v)
        v["mercadoria"] = val_cont_somado   # projeto 100% mercadoria no seed (sem segmentação)
        return v
    monkeypatch.setattr(main, "_valores_segmentados_do_projeto", _somado)

    # 2ª NF-e (mesma REF-base de documento diferente — outro número de nota).
    main._fin_faturamento_segmentado_seguro(loja_id, nome, "mercadoria", "NFE-teste-2")

    faturado_total = mod_contabil.total_lancado(app_db.get_session(), ot, owner_id, "4.1.01",
                                                "credito", projeto_id=nome)
    a_receber_total = mod_contabil.total_lancado(app_db.get_session(), ot, owner_id,
                                                 "1.1.02", "debito", projeto_id=nome)
    print("COSTURA 2 — faturado(4.1.01)=%.2f a_receber(1.1.02)=%.2f val_cont_somado=%.2f "
          "(original=%.2f + aditivo=%.2f)"
          % (faturado_total, a_receber_total, val_cont_somado, val_cont_original, diferenca_aditivo))

    # A pergunta da Costura 2: a 2ª emissão fatura o TOTAL somado de novo (dobrando o que já
    # tinha saído em 4.1.01 na 1ª NF-e) ou só a diferença que ainda não tinha sido drenada?
    assert abs(faturado_total - val_cont_somado) < 0.05, (
        "faturar_segmento NÃO deveria duplicar o valor original — total em 4.1.01 tem que ser "
        "igual ao Val_Cont somado (%.2f), não à soma das duas emissões brutas: %.2f"
        % (val_cont_somado, faturado_total))
