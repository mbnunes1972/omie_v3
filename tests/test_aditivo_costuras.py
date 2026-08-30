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


def _setup(app_db, seed):
    """Mesmo setup de tests/test_complemento_pe_e2e.py::_setup: contrato assinado, 1 ambiente de
    80k com comissão de arquiteto 10% repassada (VAVA contratado = 80.000/0,9 = 88.888,89)."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    proj = db.query(app_db.Projeto).filter_by(nome_safe=nome).first()
    proj.parametros_json = json.dumps({"incluir_custos": True, "comissao_arq_ativa": True,
                                       "comissao_arq_pct": 10.0, "carga_trib": 0.0,
                                       "pct_mercadoria": 100.0, "pct_servico": 0.0})
    pa = app_db.PoolAmbiente(nome="Cozinha", nome_exibicao="Cozinha", xml_path="fake/coz.xml",
                             ambientes_json="{}", projeto_id=nome,
                             budget_total=80000.0, order_total=30000.0)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    pa.renegociar_pe = 1
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
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


def _criar_modelo_aditivo(app_db, seed):
    import mod_documentos
    db = app_db.get_session()
    mv = mod_documentos.criar_versao(db, seed["loja1_id"], "termo_aditivo",
                                     "# TERMO ADITIVO [NUM_ADITIVO]\n1. [AMBIENTES_COMPLEMENTO]\n"
                                     "2. Complemento: [VALOR_COMPLEMENTO].\n", "t.md", None)
    mod_documentos.ativar(db, mv.id)
    db.close()


def _assinar_aditivo_completo(c, nome):
    for parte, quem in (("loja", "Rep Loja"), ("cliente", "Cliente L1")):
        st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                          {"parte": parte, "nome": quem, "cpf": "111.444.777-35"})
        assert st == 200, body
    assert body["status"] == "assinado"
    return body


def _saldo_2106_credor(app_db, seed, nome):
    import mod_contabil
    db = app_db.get_session()
    ator = {"loja_id": seed["loja1_id"], "rede_id": None}
    ot, oid = mod_contabil.resolver_owner(db, ator)
    v = mod_contabil.total_lancado(db, ot, oid, "2.1.06", "credito", projeto_id=nome)
    db.close()
    return round(v, 2)


@pytest.mark.xfail(strict=True, reason="ACHADO-21/Costura 4 (medido 29/08): revisão de PE após "
                    "aditivo assinado duplica a cobrança — vira verde sozinho no dia da correção.")
def test_costura4_revisao_apos_aditivo_assinado_duplica_cobranca(app_db, seed, http_client_factory):
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    _criar_modelo_aditivo(app_db, seed)

    # ── revisão 1: venda=84.000 → diferença = 84.000/0,9 − 88.888,89 = 4.444,44 ──────────────
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    aj_id = body["orcamento"]["id"]
    assert abs(body["orcamento"]["valor_total"] - 4444.44) < 0.05, body["orcamento"]["valor_total"]

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    aditivo1_id = body["aditivo"]["id"]

    antes = _saldo_2106_credor(app_db, seed, nome)
    _assinar_aditivo_completo(c, nome)
    depois_ad1 = _saldo_2106_credor(app_db, seed, nome)
    assert abs((depois_ad1 - antes) - 4444.44) < 0.05, (
        "1º aditivo deveria creditar 2.1.06 em 4.444,44 — %r" % (depois_ad1 - antes))

    # ── revisão 2 do MESMO ambiente, DEPOIS do aditivo assinado: venda=90.000 → nova diferença
    #    (contra a MESMA base do contrato) = 90.000/0,9 − 88.888,89 = 11.111,11 ─────────────────
    _upsert_compl(app_db, nome, pid, venda=90000.0, cfo=34000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    assert body["orcamento"]["id"] == aj_id, (
        "get-or-create tem que reaproveitar o MESMO Orcamento que o 1º aditivo já assinou — "
        "se criou um novo, a premissa da Costura 4 mudou")
    assert abs(body["orcamento"]["valor_total"] - 11111.11) < 0.05, body["orcamento"]["valor_total"]

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"novo": True})
    assert st == 200 and body["ok"], body
    aditivo2_id = body["aditivo"]["id"]
    assert aditivo2_id != aditivo1_id

    _assinar_aditivo_completo(c, nome)
    depois_ad2 = _saldo_2106_credor(app_db, seed, nome)

    # Comportamento CORRETO seria: 2.1.06 total creditado por aditivos = 11.111,11 (a diferença
    # final, que já supera e substitui a da revisão 1) — nunca 4.444,44 + 11.111,11 = 15.555,55.
    total_creditado_aditivos = depois_ad2 - antes
    assert abs(total_creditado_aditivos - 11111.11) < 0.05, (
        "duplo-lançamento confirmado com números: 2.1.06 recebeu %.2f pelos dois aditivos juntos "
        "(4.444,44 do 1º + 11.111,11 do 2º = 15.555,55), quando a diferença final real é só "
        "11.111,11 — a diferença do 1º aditivo (4.444,44) foi cobrada duas vezes."
        % total_creditado_aditivos)


@pytest.mark.xfail(strict=True, reason="ACHADO-13/Costura 2 (medido 29/08): CONFIRMADA a regressão "
                    "que a própria tarefa previu. faturar_segmento faz o split usa/resto (2.1.06 x "
                    "1.1.02) pelo saldo ATUAL da conta — mas usa+resto SEMPRE soma o `valor` "
                    "recebido inteiro em 4.1.01/4.2.01 (a conta de RECEITA), sem nenhuma noção de "
                    "'quanto desta receita já foi reconhecido antes'. Reemitir para o mesmo "
                    "segmento do mesmo projeto sempre credita 4.1.01 pelo valor cheio de novo — "
                    "hoje (sem a soma da Costura 1) isso já duplicaria SE alguém emitisse 2 NF-e's "
                    "pro mesmo segmento (é o mesmo mecanismo do ACHADO-13); com a soma da Costura 1 "
                    "implementada SEM mexer em faturar_segmento, a 2ª NF-e pós-aditivo dobra o "
                    "Val_Cont original. NÃO implementar a soma da Costura 1 sem resolver isto "
                    "junto — a regra que a própria tarefa pede.")
def test_costura2_reemissao_nao_duplica_o_ja_faturado(app_db, seed, http_client_factory, monkeypatch):
    """Simula o que a Costura 1 faria (somar aditivo ao Val_Cont segmentado) via monkeypatch em
    `_valores_segmentados_do_projeto` — SEM implementar a soma de verdade (fora do escopo desta
    tarefa). MEDIDO: `faturar_segmento` NÃO é delta-aware para a RECEITA — o split usa/resto só
    decide qual conta de contrapartida (2.1.06 x 1.1.02) absorve o débito; o crédito a 4.1.01
    sempre soma usa+resto = o `valor` passado inteiro, de novo, a cada chamada. Escrito ANTES de
    qualquer conserto, pra travar a regressão que a soma da Costura 1 introduziria sozinha."""
    import main
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")

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
    ator = {"loja_id": seed["loja1_id"], "rede_id": None}
    db = app_db.get_session()
    ot, owner_id = mod_contabil.resolver_owner(db, ator)
    saldo_2106_pre = mod_contabil.saldo_adiantamento_projeto(db, ot, owner_id, nome)
    db.close()
    assert abs(saldo_2106_pre - val_cont_original) < 0.05, (
        "fechamento da venda original deveria creditar 2.1.06 pelo Val_Cont cheio — %r"
        % saldo_2106_pre)

    # 1ª "NF-e" (mercadoria) pelo Val_Cont original — chama o wiring real de faturamento.
    main._fin_faturamento_segmentado_seguro(seed["loja1_id"], nome, "mercadoria", "NFE-teste-1")
    faturado_1 = mod_contabil.total_lancado(app_db.get_session(), ot, owner_id, "4.1.01",
                                            "credito", projeto_id=nome)
    assert abs(faturado_1 - val_cont_original) < 0.05, faturado_1
    saldo_2106_pos_nfe1 = mod_contabil.saldo_adiantamento_projeto(app_db.get_session(), ot, owner_id, nome)
    assert saldo_2106_pos_nfe1 < 0.01, (
        "2.1.06 deveria estar drenado a zero pela 1ª NF-e — %r" % saldo_2106_pos_nfe1)

    # Aditivo assinado depois da 1ª NF-e: soma R$ 4.444,44 a mais, via o MESMO wiring
    # (_fin_provisoes_venda_seguro credita 2.1.06 de novo pelo valor do aditivo).
    _criar_modelo_aditivo(app_db, seed)
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
    main._fin_faturamento_segmentado_seguro(seed["loja1_id"], nome, "mercadoria", "NFE-teste-2")

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
