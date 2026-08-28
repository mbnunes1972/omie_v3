"""docs/db/TAREFA_CENTRO_CUSTO_2.md, item 7 — varredura de órfãos.

`c1ab3f8007c4` grava gabarito incondicional pra rede,1/loja,1/loja,3, mesmo num ambiente onde
algum desses owners não existe de verdade (achado do ensaio do item 6: a Integração só tem
loja,1 — 320 linhas de `conta` e 32 de `centro_custo` ficariam órfãs, sem FK que as detecte,
já que owner é polimórfico). `mod_contabil.varrer_orfaos_gabarito` remove essas linhas, mas
NUNCA uma que tenha `lancamento` apontando pra ela (ou outra `conta`/`centro_custo` que
sobreviva referenciando-a via `pai_id`/`centro_custo_id`) — órfã com movimento é problema de
DADO, não de gabarito, apagar seria pior.

Os dois lados: owner sintético sem nenhum movimento desaparece inteiro; owner sintético com
UM lançamento tem só as contas/nós ligados a esse lançamento retidos (e reportados com
motivo) — o resto do gabarito órfão dele é removido normalmente.
"""
import mod_contabil as mc


def test_owner_orfao_sem_movimento_e_totalmente_removido(app_db):
    db = app_db.get_session()
    ot, oid = "loja", 9001
    mc.aplicar_gabarito_completo(db, ot, oid)
    assert db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).count() == len(mc.PLANO_PADRAO)
    assert db.query(mc.CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).count() == \
        len(mc.CENTRO_CUSTO_PADRAO)

    out = mc.varrer_orfaos_gabarito(db)

    assert out["removidos_conta"] == len(mc.PLANO_PADRAO)
    assert out["removidos_centro_custo"] == len(mc.CENTRO_CUSTO_PADRAO)
    assert out["retidos_conta"] == []
    assert out["retidos_centro_custo"] == []
    assert db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).count() == 0
    assert db.query(mc.CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).count() == 0
    db.close()


def test_owner_orfao_com_lancamento_tem_so_a_cadeia_ligada_retida_e_reportada(app_db):
    db = app_db.get_session()
    ot, oid = "loja", 9002
    mc.aplicar_gabarito_completo(db, ot, oid)
    contas = {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}
    caixa = contas["1.1.01"]           # Caixa/Bancos — analítica, grupo 1
    combustivel = contas["5.2.06"]     # Combustível — analítica, grupo 5, classificada em "1.4"
    mc.lancar(db, ot, oid, combustivel.id, caixa.id, 100.0, historico="orfao com movimento")

    out = mc.varrer_orfaos_gabarito(db)

    retidos_conta_ids = {r["id"] for r in out["retidos_conta"]}
    retidos_cc_ids = {r["id"] for r in out["retidos_centro_custo"]}

    # as duas contas do lancamento sobrevivem, com o motivo certo
    assert combustivel.id in retidos_conta_ids and caixa.id in retidos_conta_ids
    motivos = {r["id"]: r["motivo"] for r in out["retidos_conta"]}
    assert "lancamento" in motivos[combustivel.id]
    assert "lancamento" in motivos[caixa.id]

    # os ancestrais de cada uma (codigo = prefixo) sobrevivem por terem filho vivo, nao por
    # lancamento direto
    for codigo_pai in ("5.2", "5", "1.1", "1"):
        assert contas[codigo_pai].id in retidos_conta_ids, f"{codigo_pai} deveria ter sido retida"
        assert "filha" in motivos[contas[codigo_pai].id]

    # o centro de custo em que a combustivel foi classificada ("1.4") e o pai dele ("1")
    # tambem sobrevivem
    ccs = {c.nome: c for c in db.query(mc.CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).all()}
    cc_logistica = next(c for c in ccs.values() if c.id == combustivel.centro_custo_id)
    assert cc_logistica.id in retidos_cc_ids

    # o resto do gabarito orfao (sem ligacao nenhuma com o lancamento) foi removido de verdade
    assert out["removidos_conta"] > 0
    assert out["removidos_centro_custo"] > 0
    assert out["removidos_conta"] + len(retidos_conta_ids) == len(mc.PLANO_PADRAO)
    assert out["removidos_centro_custo"] + len(retidos_cc_ids) == len(mc.CENTRO_CUSTO_PADRAO)

    # confere no banco: as retidas realmente ainda existem
    assert db.get(mc.Conta, combustivel.id) is not None
    assert db.get(mc.Conta, caixa.id) is not None
    # e uma conta sem relacao nenhuma (folha, sem filho, sem lancamento) sumiu
    assert db.query(mc.Conta).filter_by(
        owner_tipo=ot, owner_id=oid, codigo="3.1").first() is None
    db.close()
