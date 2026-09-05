"""docs/db/TAREFA_AUDITORIA_CONTABIL.md — Parte 3: partida dobrada, por função.

`lancar()` (mod_contabil.py:1089) grava conta_debito/conta_credito/valor num único
`Lancamento` — soma(débitos) == soma(créditos) é garantido PELO SCHEMA em qualquer
lançamento individual (um valor só, split nos dois lados). O teste que teria valor real
não é "o par de UMA chamada bate" (impossível não bater) — é que funções com MAIS DE UMA
perna (o "mesmo evento, dois lançamentos" que várias funções contábeis fazem) usem o
MESMO valor nas duas pernas quando a regra de negócio diz que devem ser iguais, em vez de
uma perna divergir silenciosamente da outra (a "classe de lançamento pela metade" que a
tarefa pede pra cobrir). Por isso este arquivo tem duas partes:

1. Um sweep pelos 89 eventos de EVENTOS, validando que cada um resolve pro par de conta
   certo com o valor certo (pega erro de digitação no código da conta, não só a aritmética).
2. Um teste dedicado por função que grava MAIS de uma perna, conferindo que as pernas que
   deveriam ser iguais são iguais — e, onde a assimetria é uma decisão documentada (ver
   ACHADO-05, reclassificar_provisao), o teste prova a assimetria em vez de escondê-la.
"""
import mod_contabil as mc


def _lan_por_ref(db, ot, oid, ref):
    l = db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=oid, ref=ref).first()
    assert l is not None, "nenhum lançamento com ref=%r" % ref
    return l


def _cod(db, ot, oid, conta_id):
    return db.get(mc.Conta, conta_id).codigo


# ── 1. sweep dos 89 eventos ──────────────────────────────────────────────────────────────────
def test_todos_os_eventos_lancam_no_par_de_conta_e_valor_declarados(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6300; mc.seed_plano(db, ot, oid)
    for evento, (cod_d, cod_c, _hist) in mc.EVENTOS.items():
        ref = "sweep:" + evento
        mc.registrar_evento(db, ot, oid, evento, 111.11, ref=ref)
        l = _lan_por_ref(db, ot, oid, ref)
        assert _cod(db, ot, oid, l.conta_debito_id) == cod_d, evento
        assert _cod(db, ot, oid, l.conta_credito_id) == cod_c, evento
        assert l.valor == 111.11, evento
    db.close()


# ── 2. funções com mais de uma perna ─────────────────────────────────────────────────────────
def test_efetivar_provisao_agora_e_perna_unica(app_db):
    """F2-27 (docs/db/MODELO_CONTABIL.md): até 05/09/2026 `efetivar_provisao` tinha DUAS pernas —
    despesa×ativo (via `reconhecer_despesa_efetivacao`) MAIS provisão×payable — testadas aqui com
    o MESMO valor. Desde o F2-27 a despesa nasce na emissão (`reconhecer_provisoes_segmento`),
    nunca mais na efetivação: `efetivar_provisao` ficou perna ÚNICA (provisão×payable/caixa). Não
    sobra uma segunda perna pra comparar valor — a garantia do schema (débito==crédito por
    lançamento) já cobre a única perna que resta."""
    db = app_db.get_session(); ot, oid = "loja", 6301; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_montagem", 500.0, ref="fv:P")
    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.02", 500.0, ref="ef:P", forma_pagamento="a_prazo")
    assert mc.lancamento_por_ref(db, ot, oid, "ef:P:d") is None   # perna de despesa não existe mais
    l_prov = _lan_por_ref(db, ot, oid, "ef:P")
    assert l_prov.valor == 500.0
    assert _cod(db, ot, oid, l_prov.conta_debito_id) == "2.1.04.02"
    assert _cod(db, ot, oid, l_prov.conta_credito_id) == "2.1.01"
    db.close()


def test_reclassificar_provisao_perna_ativo_capada_quando_nao_ha_saldo(app_db):
    """ACHADO-05: a perna da provisão sempre move o valor cheio; a perna espelho do ativo
    é CAPADA ao saldo em aberto do ativo de origem (mod_contabil.py:1893-1907) — se parte do
    ativo já foi baixada (NF-e parcial), as duas pernas divergem por construção. Prova as
    duas situações: sem baixa prévia (pernas iguais) e com baixa prévia (pernas diferentes,
    proporcionalmente ao que sobrou)."""
    db = app_db.get_session(); ot, oid = "loja", 6302; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_custo_fabrica", 1000.0, projeto_id="P", ref="fv:P")

    # sem baixa prévia: ativo tem os 1000 inteiros — reclassificar 300 move os dois lados iguais
    mc.reclassificar_provisao(db, ot, oid, "P", "2.1.04.06", "2.1.04.14", 300.0, ref="reclass:P:1")
    l_prov1 = _lan_por_ref(db, ot, oid, "reclass:P:1")
    l_ativo1 = _lan_por_ref(db, ot, oid, "reclass:P:1:ativo")
    assert l_prov1.valor == 300.0
    assert l_ativo1.valor == 300.0

    # baixa parcial do ativo restante (NF-e): sobra só 200 de ativo aberto (700 - 500)
    mc.registrar_evento(db, ot, oid, "reconhecimento_despesa_custo_fabrica", 500.0, projeto_id="P", ref="nfe:P")

    # reclassificar mais 700 da provisão: a perna da provisão move os 700 cheios; a do ativo
    # capa ao que sobrou aberto (700 originais - 300 já reclassificados - 500 baixados = -100,
    # ou seja, saldo de ativo já ficou negativo/zerado antes desta chamada — a perna do ativo
    # não deve mover nada além do que ainda está aberto)
    saldo_ativo_antes = round(mc._mov(db, ot, oid, "1.1.06.06", "devedor", None, None, projeto_id="P"), 2)
    mc.reclassificar_provisao(db, ot, oid, "P", "2.1.04.06", "2.1.04.14", 700.0, ref="reclass:P:2")
    l_prov2 = _lan_por_ref(db, ot, oid, "reclass:P:2")
    assert l_prov2.valor == 700.0   # provisão sempre move o valor cheio pedido
    ativo_mv_esperado = round(min(700.0, max(saldo_ativo_antes, 0.0)), 2)
    if ativo_mv_esperado > 0:
        l_ativo2 = _lan_por_ref(db, ot, oid, "reclass:P:2:ativo")
        assert l_ativo2.valor == ativo_mv_esperado
        assert l_ativo2.valor < l_prov2.valor   # a assimetria do ACHADO-05, provada
    else:
        assert mc.lancamento_por_ref(db, ot, oid, "reclass:P:2:ativo") is None   # não moveu nada — capado a zero
    db.close()


def test_efetivar_impostos_segmento_duas_pernas_com_o_mesmo_valor(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6303; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "fechamento_venda_impostos", 400.0, projeto_id="P", ref="fv:P")
    v = mc.efetivar_impostos_segmento(db, ot, oid, "P", 400.0, ref_base="fat:P")
    assert v == 400.0
    l_ded = _lan_por_ref(db, ot, oid, "fat:P:ded")
    l_obr = _lan_por_ref(db, ot, oid, "fat:P:obr")
    assert l_ded.valor == 400.0 and l_obr.valor == 400.0
    assert _cod(db, ot, oid, l_ded.conta_debito_id) == "4.3.01"
    assert _cod(db, ot, oid, l_ded.conta_credito_id) == "1.1.05"
    assert _cod(db, ot, oid, l_obr.conta_debito_id) == "2.1.04.13"
    assert _cod(db, ot, oid, l_obr.conta_credito_id) == "2.1.03"
    db.close()


def test_devolver_venda_pernas_proporcionais_a_fracao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6304; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 1000.0, projeto_id="P", ref="rv:P")
    mc.registrar_evento(db, ot, oid, "fechamento_venda_montagem", 200.0, projeto_id="P", ref="fv:P:m")
    mc.registrar_evento(db, ot, oid, "fechamento_venda_impostos", 100.0, projeto_id="P", ref="fv:P:i")
    out = mc.devolver_venda(db, ot, oid, "P", 0.5, ref_base="dev:P")
    assert out["2.1.06"] == 500.0        # metade da receita a realizar
    assert out["2.1.04.02"] == 100.0     # metade da provisão de montagem
    assert out["2.1.04.13"] == 50.0      # metade da provisão de impostos — mesmo loop genérico
    l_receita = _lan_por_ref(db, ot, oid, "dev:P:receita")
    assert l_receita.valor == 500.0
    assert _cod(db, ot, oid, l_receita.conta_debito_id) == "2.1.06"
    assert _cod(db, ot, oid, l_receita.conta_credito_id) == "1.1.02"
    db.close()


def test_cancelar_contrato_reversa_venda_e_juros_do_ramo_loja(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6305; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 1000.0, projeto_id="P", ref="rv:P")
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 80.0, projeto_id="P", ref="cj:P")
    out = mc.cancelar_contrato(db, ot, oid, "P", ref_base="canc:P")
    assert out["2.1.06"] == 1000.0
    assert out["1.1.07"] == 80.0
    l_juros = _lan_por_ref(db, ot, oid, "canc:P:juros")
    assert l_juros.valor == 80.0
    assert _cod(db, ot, oid, l_juros.conta_debito_id) == "2.1.07"
    assert _cod(db, ot, oid, l_juros.conta_credito_id) == "1.1.07"
    db.close()


def test_trocar_ramo_custo_financeiro_loja_para_financeira_mesmo_valor(app_db):
    db = app_db.get_session(); ot, oid = "loja", 6306; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="cj:P")
    ramo = mc.trocar_ramo_custo_financeiro(db, ot, oid, "P", "loja", "financeira", 300.0, ref_base="troca:P")
    assert ramo == "financeira"
    l_rev = _lan_por_ref(db, ot, oid, "troca:P:rev")
    l_new = _lan_por_ref(db, ot, oid, "troca:P:new")
    assert l_rev.valor == 300.0 and l_new.valor == 300.0
    assert _cod(db, ot, oid, l_rev.conta_debito_id) == "2.1.07"
    assert _cod(db, ot, oid, l_rev.conta_credito_id) == "1.1.07"
    assert _cod(db, ot, oid, l_new.conta_debito_id) == "1.1.06.19"
    assert _cod(db, ot, oid, l_new.conta_credito_id) == "2.1.04.19"
    db.close()


def test_rateio_ao_pdv_duas_pernas_espelhadas_mesmo_valor_e_ref(app_db):
    db = app_db.get_session()
    ot_mae, oid_mae = "loja", 6307
    ot_pdv, oid_pdv = "loja", 6308
    out = mc.rateio_ao_pdv(db, (ot_mae, oid_mae), (ot_pdv, oid_pdv), 250.0, "5.4.01",
                           historico="Aluguel compartilhado")
    ref = out["ref"]
    l_mae = _lan_por_ref(db, ot_mae, oid_mae, ref)
    l_pdv = _lan_por_ref(db, ot_pdv, oid_pdv, ref)
    assert l_mae.valor == 250.0 and l_pdv.valor == 250.0
    assert _cod(db, ot_mae, oid_mae, l_mae.conta_debito_id) == "1.1.09"
    assert _cod(db, ot_mae, oid_mae, l_mae.conta_credito_id) == "1.1.01"
    assert _cod(db, ot_pdv, oid_pdv, l_pdv.conta_debito_id) == "5.4.01"
    assert _cod(db, ot_pdv, oid_pdv, l_pdv.conta_credito_id) == "2.1.09"

    estorno = mc.estornar_rateio(db, ref)
    assert estorno["ja_estornado"] is False
    l_mae_e = _lan_por_ref(db, ot_mae, oid_mae, ref + ":estorno")
    l_pdv_e = _lan_por_ref(db, ot_pdv, oid_pdv, ref + ":estorno")
    assert l_mae_e.valor == 250.0 and l_pdv_e.valor == 250.0
    # estorno inverte D/C de cada perna original
    assert l_mae_e.conta_debito_id == l_mae.conta_credito_id
    assert l_mae_e.conta_credito_id == l_mae.conta_debito_id
    db.close()
