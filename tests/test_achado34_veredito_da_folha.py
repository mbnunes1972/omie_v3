"""ACHADO-34 (docs/db/ACHADOS_CONTABEIS.md) — a folha zera a provisão de comissão de venda
(2.1.04.12) ANTES da Conciliação Final, e `conciliar_final` monta a exigência de veredito a partir
de quem ainda tem SALDO ABERTO. Resultado: a rubrica atravessava a exigência sem nunca passar por
ela, e o relatório de projetos encerrados por reversão ficava cego a esses projetos.

DECIDIDO 03/09 (Marcelo): a folha grava um `VeredictoProvisao` — não é reconhecida por escrito como
uma segunda forma de veredito. O rastro fica uniforme e o relatório volta a enxergar.

A propriedade central destes aceites: **o livro não muda**. A porta nova
(`mod_contabil.resolver_por_ato_nomeado`) chega no mesmo lugar que `resolver_saldo_provisao`
chegava sozinho; o que entra é a decisão escrita. Por isso os aceites 3 e 4 conferem conta a conta
contra os mesmos números que `tests/test_comissao.py` já travava antes desta mudança.
"""
import mod_folha
import mod_provisoes
import mod_contabil
import mod_comissao
from tests.test_comissao import _cria_venda_com_provisao

_PROV = "2.1.04.12"


def _paga_folha(db, app_db, projeto, provisao, ajuste=None, nome_funcao=None, decidido_por=True):
    """Cria venda com provisão constituída, gera/aprova/paga a folha. `ajuste` = (base, pct) do
    gerente no ato do pagamento, ou None pra pagar exatamente o provisionado."""
    loja, f, ot, oid = _cria_venda_com_provisao(db, app_db, projeto, provisao, valor_liquido=10000.0,
                                                nome_funcao=nome_funcao or ("Consultor " + projeto))
    cfg = mod_provisoes.config_financeira_default()
    mod_folha.gerar_folha(db, loja, "2026-07", cfg); db.commit()
    if ajuste is not None:
        item = db.query(app_db.ComissaoFolha).filter_by(ref_etapa="venda:%d:%s" % (f.id, projeto)).first()
        ok, err = mod_comissao.editar_item(db, item, base_ajustada=ajuste[0], pct_ajustado=ajuste[1])
        assert ok, err
        db.commit()
    reg = db.query(app_db.FolhaPagamento).filter_by(funcionario_id=f.id, competencia="2026-07").first()
    mod_folha.aprovar(db, reg); db.commit()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    ok, err = mod_folha.pagar(db, ot, oid, reg, decidido_por_id=(u.id if decidido_por else None))
    assert ok, err
    db.commit()
    return ot, oid, reg, u


def _vereditos(db, app_db, ot, oid, projeto):
    return (db.query(app_db.VeredictoProvisao)
              .filter_by(owner_tipo=ot, owner_id=oid, projeto_nome=projeto, codigo_provisao=_PROV)
              .all())


def test_aceite1_folha_paga_grava_veredito_nomeado(seed, app_db):
    """O aceite do achado: depois da folha paga existe veredito NOMEADO pra 2.1.04.12 — antes desta
    mudança não existia nenhum, e era isso que deixava a rubrica invisível ao fechamento."""
    db = app_db.get_session()
    ot, oid, reg, u = _paga_folha(db, app_db, "PVer1", 300.0)
    vs = _vereditos(db, app_db, ot, oid, "PVer1")
    assert len(vs) == 1, "a folha tem que deixar exatamente um veredito nomeado"
    v = vs[0]
    # F2-27: renomeados — 'absorver' (FALTA), 'receber' (SOBRA) ou 'encerrar' (bateu exato);
    # qual dos três sai depende de arredondamento do valor calculado da comissão contra o
    # provisionado (300.0) — o aceite é que SEMPRE existe um, nunca None/omisso.
    assert v.veredito in ("absorver", "receber", "encerrar")
    assert "folha:%d" % reg.id in (v.motivo or ""), "o motivo nomeia o ato que decidiu"
    assert reg.competencia in (v.motivo or ""), "e a competência da folha"
    assert v.decidido_por_id == u.id, "quem pagou a folha é quem decidiu"
    assert v.decidido_em is not None
    db.close()


def test_aceite2_sobra_vira_receber_e_o_relatorio_enxerga(seed, app_db):
    """O gerente zera a comissão: sobra a provisão inteira. Veredito de SOBRA ('receber', F2-27 —
    renomeado de 'encerrada_valor_menor'), e o projeto passa a aparecer no relatório de
    encerrados por reversão — a consequência exata que o achado registra como perdida ('nunca
    enxerga esses casos — não existe veredito nenhum pra listar')."""
    db = app_db.get_session()
    ot, oid, _reg, _u = _paga_folha(db, app_db, "PVer2", 300.0, ajuste=(0.0, 0.0))
    vs = _vereditos(db, app_db, ot, oid, "PVer2")
    assert len(vs) == 1
    assert vs[0].veredito == "receber"
    assert round(float(vs[0].valor_revertido or 0), 2) == 300.0
    rel = mod_contabil.relatorio_projetos_encerrados_por_reversao(db, ot, oid)
    linha = [p for p in rel if p["projeto_nome"] == "PVer2"]
    assert linha, "o relatório de reversões passa a enxergar o projeto encerrado pela folha"
    assert linha[0]["valor_revertido_total"] == 300.0
    db.close()


def test_aceite3_o_livro_nao_muda_na_sobra(seed, app_db):
    """Controle de que a porta nova não mexeu na contabilidade: provisão fechada, e a rota
    'sem DRE direta' preservada (nem 4.4.02 nem 5.6.10 tocadas — os destinos ANTIGOS,
    aposentados). F2-27: sem emissão simulada nesta rodada, a despesa (5.3.01) segue 0 — a
    sobra vai pra Receita de Conciliação (4.5.01), em bloco próprio."""
    db = app_db.get_session()
    ot, oid, _reg, _u = _paga_folha(db, app_db, "PVer3", 300.0, ajuste=(0.0, 0.0))
    assert mod_contabil._mov(db, ot, oid, "5.3.01", "devedor", None, None, projeto_id="PVer3") == 0.0
    assert mod_folha.saldo_provisao_venda(db, ot, oid, "PVer3") == 0.0
    for cod in ("4.4.02", "5.6.10"):
        assert mod_contabil._mov(db, ot, oid, cod, "devedor", None, None, projeto_id="PVer3") == 0.0
    assert mod_contabil._mov(db, ot, oid, "4.5.01", "credor", None, None, projeto_id="PVer3") == 300.0
    db.close()


def test_aceite4_falta_vira_absorver_e_a_despesa_fica_no_provisionado_integral(seed, app_db):
    """F2-27 (docs/db/MODELO_CONTABIL.md): ajuste pra cima (pago > provisionado) — o veredito é
    'absorver' (renomeado de 'efetivada' — o único que o sinal do saldo admite, ACHADO-41). A
    despesa formal (5.3.01) NÃO segue mais o valor pago — fica fixa no PROVISIONADO INTEGRAL
    (300, reconhecido na emissão); o excedente pago (200) vira Despesa de Conciliação (5.7.01),
    nunca uma segunda despesa em 5.3.01 (duplicaria)."""
    db = app_db.get_session()
    ot, oid, _reg, _u = _paga_folha(db, app_db, "PVer4", 300.0, ajuste=(10000.0, 5.0))
    # simula a emissão que reconhece o provisionado original (300) — pagamento nunca toca o
    # ativo, então a ordem entre pagar e emitir não muda o valor reconhecido (mesma prova do
    # exemplo de seis contas do MODELO_CONTABIL.md).
    mod_contabil.reconhecer_provisoes_segmento(db, ot, oid, "PVer4", "mercadoria", 100.0,
                                               ref_base="rec:PVer4")
    db.commit()
    vs = _vereditos(db, app_db, ot, oid, "PVer4")
    assert len(vs) == 1
    assert vs[0].veredito == "absorver"
    assert mod_contabil._mov(db, ot, oid, "5.3.01", "devedor", None, None, projeto_id="PVer4") == 300.0
    assert mod_contabil._mov(db, ot, oid, "5.7.01", "devedor", None, None, projeto_id="PVer4") == 200.0
    assert mod_folha.saldo_provisao_venda(db, ot, oid, "PVer4") == 0.0
    db.close()


def test_aceite5_idempotente_por_ref(seed, app_db):
    """Mesma `ref`, segunda chamada: devolve o veredito existente em vez de gravar um segundo —
    mesma família de idempotência do resto do módulo. Protege contra a folha reprocessada."""
    db = app_db.get_session()
    ot, oid, reg, u = _paga_folha(db, app_db, "PVer5", 300.0)
    ref = "folha:%d:venda:PVer5:ajuste" % reg.id
    v2 = mod_contabil.resolver_por_ato_nomeado(db, ot, oid, "PVer5", _PROV,
                                               origem="folha:%d competência %s" % (reg.id, reg.competencia),
                                               ref=ref, decidido_por_id=u.id)
    db.commit()
    vs = _vereditos(db, app_db, ot, oid, "PVer5")
    assert len(vs) == 1, "a segunda chamada com a mesma ref não pode criar um segundo veredito"
    assert v2.id == vs[0].id
    db.close()
