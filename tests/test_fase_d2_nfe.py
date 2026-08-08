"""FASE D2 · Fase 3 (redesenhada 2026-08-07) — reconhecer_despesa_efetivacao reconhece a despesa de
UMA rubrica NA COMPETÊNCIA REAL (na efetivação, não mais de uma vez estimada na NF-e — extinto o
antigo reconhecer_despesas_nfe/"matching pleno": as despesas de projeto de móveis planejados ocorrem
espalhadas ao longo do ciclo, muitas depois da própria NF-e, que só sai no fim, na entrega). Debita a
conta FORMAL da rubrica (formalismo S109: CMV 5.1.x, Custo de Serviço 5.2.x ou Despesas Comerciais
5.3.x) × baixa do ativo diferido 1.1.06.0X. A Provisão (2.1.04.0X) SOBREVIVE. Idempotente. Impostos e
Custo Financeiro NÃO entram (rota própria)."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


# rubrica -> (ativo diferido 1.1.06, provisão 2.1.04, despesa reconhecida na efetivação)
RUBRICAS = {
    "montagem":            ("1.1.06.02", "2.1.04.02", "5.2.01"),
    "garantia":            ("1.1.06.03", "2.1.04.03", "5.2.12"),
    "assistencia":         ("1.1.06.05", "2.1.04.05", "5.2.13"),
    "custo_fabrica":       ("1.1.06.06", "2.1.04.06", "5.1.01"),
    "frete_fabrica":       ("1.1.06.07", "2.1.04.07", "5.1.02"),
    "frete_local":         ("1.1.06.08", "2.1.04.08", "5.2.08"),
    "insumos":             ("1.1.06.09", "2.1.04.09", "5.2.09"),
    "com_medidor":         ("1.1.06.10", "2.1.04.10", "5.3.18"),
    "com_proj_exec":       ("1.1.06.11", "2.1.04.11", "5.3.19"),
    "retencao_com_vendas": ("1.1.06.12", "2.1.04.12", "5.3.01"),   # 5.3.20 removida (Centro de Custo/Natureza, 2026-08-08)
}
VALORES = {"montagem": 1000.0, "garantia": 200.0, "assistencia": 300.0, "custo_fabrica": 60000.0,
           "frete_fabrica": 400.0, "frete_local": 150.0, "insumos": 100.0, "com_medidor": 250.0,
           "com_proj_exec": 350.0, "retencao_com_vendas": 500.0}


def _contrato(db, ot, oid, proj):
    mc.constituir_provisoes_fechamento(db, ot, oid, proj, dict(VALORES, impostos=5000.0), ref_base="pf:" + proj)


def test_reconhece_despesa_de_cada_rubrica_na_efetivacao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 720; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    # antes de qualquer efetivação: nada de despesa no resultado (só a NF-e nunca fez isso mais)
    d0 = mc.dre(db, ot, oid)
    assert d0["cmv_csp"] == 0.0 and d0["constituicao_provisoes"] == 0.0
    for chave, (ativo, prov, desp) in RUBRICAS.items():
        lan = mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", prov, VALORES[chave], ref="ef:" + chave)
        assert lan is not None
        assert _s(db, ot, oid, desp) == VALORES[chave]                       # despesa reconhecida (conta formal)
        assert _s(db, ot, oid, ativo) == 0.0                                 # ativo diferido baixado
        assert _s(db, ot, oid, prov) == VALORES[chave]                       # PROVISÃO sobrevive (só a despesa reconhece)
    # 5.1.01 é o CMV da fábrica (pode somar outras origens; aqui só a fábrica)
    assert _s(db, ot, oid, "5.1.01") == 60000.0
    # DRE agora reflete os custos, cada um UMA vez — nos grupos FORMAIS (S109):
    d = mc.dre(db, ot, oid)
    assert d["cmv_csp"] == 62150.0                                           # 60000+400+1000+200+300+150+100
    assert d["despesas_comerciais"] == 1100.0                                # 250+350+500 (comissões)
    assert d["constituicao_provisoes"] == 0.0                                # 5.6 = só Ajustes de Provisões
    assert d["deducoes"] == 0.0                                              # impostos NÃO entram aqui
    assert _s(db, ot, oid, "1.1.05") == 5000.0 and _s(db, ot, oid, "2.1.04.13") == 5000.0
    db.close()


def test_reconhecimento_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 721; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 60000.0, ref="ef:custo_fabrica")
    mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.02", 1000.0, ref="ef:montagem")
    out2 = mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.06", 60000.0, ref="ef:custo_fabrica")
    assert out2 is not None                                                  # idempotente: não duplica
    assert _s(db, ot, oid, "5.1.01") == 60000.0
    assert _s(db, ot, oid, "5.2.01") == 1000.0
    db.close()


def test_custo_financeiro_e_impostos_sem_perna_de_despesa(app_db):
    """Impostos e Custo Financeiro têm rota própria — reconhecer_despesa_efetivacao é no-op pra eles
    (senão duplicaria com efetivar_impostos_segmento/reconhecer_custo_financeiro)."""
    db = app_db.get_session(); ot, oid = "loja", 722; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0, "impostos": 300.0},
                                       ref_base="pf:P")
    assert mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.19", 500.0, ref="ef:cf") is None
    assert mc.reconhecer_despesa_efetivacao(db, ot, oid, "P", "2.1.04.13", 300.0, ref="ef:imp") is None
    db.close()


def test_faturamento_cmv_foi_retirado():
    """O evento antigo faturamento_cmv (5.1.01 × 2.1.04.06) foi substituído pelo reconhecimento na
    efetivação (× 1.1.06.06)."""
    assert "faturamento_cmv" not in mc.EVENTOS
    assert mc.EVENTOS["reconhecimento_despesa_custo_fabrica"][:2] == ("5.1.01", "1.1.06.06")
