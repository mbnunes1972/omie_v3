# -*- coding: utf-8 -*-
"""F2-27 (docs/db/MODELO_CONTABIL.md, Passo 3) — o ATO DE RECONHECIMENTO na emissão.

Até 07/08/2026 a despesa das 17 rubricas de despesa em tempo real só nascia na EFETIVAÇÃO
(pagamento real) — o custo caía na competência do pagamento, a receita na da NF-e, descasamento
estrutural numa venda cujo contrato antecede a entrega em meses. RAZÃO NOVA (05/09): a despesa
nasce na EMISSÃO, pelo PROVISIONADO INTEGRAL, segmentada entre mercadoria/serviço (mesma
convenção de `efetivar_impostos_segmento`) — `mod_contabil.reconhecer_provisoes_segmento`."""
import mod_contabil as mc


def _s(db, ot, oid, cod, proj=None):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    if proj is None:
        return mc.saldo_conta(db, ot, oid, c.id)
    return mc._mov(db, ot, oid, cod, "devedor" if cod.startswith(("1.", "5.")) else "credor",
                   None, None, projeto_id=proj)


def test_reconhece_so_a_fatia_do_segmento_e_a_soma_fecha_o_total(app_db):
    """CFO = 60.000, segmentação 70% mercadoria / 30% serviço: mercadoria emite primeiro,
    reconhece 42.000; serviço emite depois, reconhece os 18.000 restantes — soma = 60.000."""
    db = app_db.get_session(); ot, oid = "loja", 4001; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 60000.0}, ref_base="pf:P")

    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 70.0, ref_base="rec:doc1")
    assert _s(db, ot, oid, "5.1.01", "P") == 42000.0
    assert _s(db, ot, oid, "1.1.06.06", "P") == 18000.0   # ainda falta a fatia do serviço

    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "servico", 70.0, ref_base="rec:doc2")
    assert _s(db, ot, oid, "5.1.01", "P") == 60000.0       # soma fecha o total
    assert _s(db, ot, oid, "1.1.06.06", "P") == 0.0        # ativo zerado — os dois documentos emitiram
    assert _s(db, ot, oid, "2.1.04.06", "P") == 60000.0    # PROVISÃO sobrevive (só a despesa reconhece)
    db.close()


def test_ordem_dos_documentos_nao_importa(app_db):
    """O mesmo resultado saindo do serviço primeiro — a fatia não depende de qual documento
    emite antes; cada um reconhece só a SUA parte do total, sempre."""
    db = app_db.get_session(); ot, oid = "loja", 4002; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 60000.0}, ref_base="pf:P")

    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "servico", 70.0, ref_base="rec:doc1")
    assert _s(db, ot, oid, "5.1.01", "P") == 18000.0
    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 70.0, ref_base="rec:doc2")
    assert _s(db, ot, oid, "5.1.01", "P") == 60000.0
    assert _s(db, ot, oid, "1.1.06.06", "P") == 0.0
    db.close()


def test_pagamento_antes_da_emissao_nao_reduz_o_reconhecido(app_db):
    """O exemplo de seis contas do MODELO_CONTABIL.md, provado: CFO=60.000, paga 55.000ANTES da
    emissão (efetivar_provisao — só a perna de caixa agora) — a emissão ainda reconhece os
    60.000 CHEIOS, porque pagamento nunca toca o ativo."""
    db = app_db.get_session(); ot, oid = "loja", 4003; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 60000.0}, ref_base="pf:P")

    mc.efetivar_provisao(db, ot, oid, "P", "2.1.04.06", 55000.0, ref="pag:fabrica")
    # a perna de caixa não toca o ativo nem a despesa — só a provisão (passivo) e o fornecedor.
    assert _s(db, ot, oid, "1.1.06.06", "P") == 60000.0    # ativo intocado
    assert _s(db, ot, oid, "5.1.01", "P") == 0.0            # despesa ainda não reconhecida
    assert _s(db, ot, oid, "2.1.04.06", "P") == 5000.0      # provisão baixada pelo pagamento (60000-55000)

    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    assert _s(db, ot, oid, "5.1.01", "P") == 60000.0        # reconhece os 60.000 CHEIOS, não os 5.000 restantes
    assert _s(db, ot, oid, "1.1.06.06", "P") == 0.0
    db.close()


def test_reconhecimento_e_idempotente_por_documento(app_db):
    db = app_db.get_session(); ot, oid = "loja", 4004; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 10000.0}, ref_base="pf:P")

    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")   # reprocessamento
    assert _s(db, ot, oid, "5.1.01", "P") == 10000.0   # não duplicou
    db.close()


def test_reflete_todas_as_17_rubricas_de_uma_vez(app_db):
    """Não é só o CFO — as 17 rubricas de despesa em tempo real reconhecem juntas, na mesma
    chamada, cada uma pela sua fatia."""
    db = app_db.get_session(); ot, oid = "loja", 4005; mc.seed_plano(db, ot, oid)
    valores = {"montagem": 1000.0, "garantia": 200.0, "assistencia": 300.0, "custo_fabrica": 60000.0,
               "frete_fabrica": 400.0, "frete_local": 150.0, "insumos": 100.0, "com_medidor": 250.0,
               "com_proj_exec": 350.0, "retencao_com_vendas": 500.0, "outros_forn": 80.0,
               "com_arq": 60.0, "pro_fid": 40.0, "cust_via": 30.0, "brinde": 20.0,
               "cust_esp": 90.0, "com_adm": 70.0}
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", valores, ref_base="pf:P")

    out = mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    assert len(out) == 17, sorted(out)
    for cod in ("2.1.04.02", "2.1.04.03", "2.1.04.05", "2.1.04.06", "2.1.04.07", "2.1.04.08",
                "2.1.04.09", "2.1.04.10", "2.1.04.11", "2.1.04.12", "2.1.04.14", "2.1.04.15",
                "2.1.04.16", "2.1.04.17", "2.1.04.18", "2.1.04.20", "2.1.04.21"):
        assert cod in out, cod
    # Impostos e Custo Financeiro (rota própria) não entram
    assert "2.1.04.13" not in out and "2.1.04.19" not in out
    db.close()


def test_af_reduz_o_provisionado_e_o_reconhecimento_segue_o_valor_reduzido(app_db):
    """Uma redução via AF (ajustar_provisao_delta) É refletida no que se reconhece — é revisão
    genuína do provisionado, não pagamento. Diferente do payment, que nunca é."""
    db = app_db.get_session(); ot, oid = "loja", 4006; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 4000.0}, ref_base="pf:P")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_fabrica", 4000.0, 3000.0, ref="af:reduz")
    assert _s(db, ot, oid, "1.1.06.06", "P") == 3000.0

    mc.reconhecer_provisoes_segmento(db, ot, oid, "P", "mercadoria", 100.0, ref_base="rec:doc1")
    assert _s(db, ot, oid, "5.1.01", "P") == 3000.0   # reconhece o valor JÁ REVISADO, não o original
    db.close()
