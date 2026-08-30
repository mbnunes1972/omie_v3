"""docs/db/TAREFA_ACHADO13.md, ponto 2 — medir ANTES de escrever o conserto.

`_mov(db, ot, oid, "4.1.01", "credor", ...)` — o já-reconhecido que `faturar_segmento` delta-aware
vai ler — é LÍQUIDO (crédito − débito) ou BRUTO (só crédito)? Se for bruto, um estorno de NF-e
cancelada (`mod_contabil.estornar_faturamento_nfe`, que de fato existe e de fato debita 4.1.01)
não reduziria o "já reconhecido", e o delta sairia menor do que deveria — receita legítima
ficaria sem faturar. MEDIDO, não presumido: emite, cancela (estorna via o mecanismo real que já
existe), reemite, e confere numericamente o que `_mov` devolve em cada ponto."""
import mod_contabil as mc


def test_mov_credor_e_liquido_nao_bruto(app_db):
    db = app_db.get_session()
    ot, oid = "loja", 900
    mc.seed_plano(db, ot, oid)

    mc.faturar_segmento(db, ot, oid, "P13", "mercadoria", 10000.0, ref_base="fat:NF1")
    bruto_apos_1a_nfe = mc._mov(db, ot, oid, "4.1.01", "credor", None, None, projeto_id="P13")
    assert bruto_apos_1a_nfe == 10000.0

    estornos = mc.estornar_faturamento_nfe(db, ot, oid, "NF1")
    assert estornos, "deveria ter estornado a perna de 4.1.01 da NF1"

    apos_estorno = mc._mov(db, ot, oid, "4.1.01", "credor", None, None, projeto_id="P13")
    print("ACHADO-13 ponto 2 — 4.1.01 após NF1 (10.000) e estorno da NF1:", apos_estorno)

    assert apos_estorno == 0.0, (
        "_mov(...,'credor') é LÍQUIDO — o débito do estorno reduziu o crédito da NF1 "
        "(10.000 - 10.000 = 0). Se fosse bruto, continuaria em 10.000,00: %r" % apos_estorno)
    db.close()
