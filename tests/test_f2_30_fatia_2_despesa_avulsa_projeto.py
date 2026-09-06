# -*- coding: utf-8 -*-
"""F2-30 Fatia 2 (DECIDIDO 06/09): despesa avulsa ganha vínculo com projeto, e entra na margem.

Compra complementar descoberta na entrega, não prevista na venda, sem provisão nenhuma que
sirva (senão seria efetivação ou migração) — sai por `despesa_avulsa`, agora com `projeto_id`
opcional, na conta própria "5.3.22 Despesa Avulsa de Projeto". Fica em 5.3 (não em 5.2) de
propósito: a fórmula de `margem_projeto` só desconta 3 contas NOMEADAS do grupo 5.2 (Montagem/
Garantia/Assistência) mas o grupo 5.3 inteiro via `comissao` (que apesar do nome já soma
5.3.17 Custo Especial de Projeto do mesmo jeito) — é assim que a nova conta entra na margem
sem precisar de outro termo na fórmula.

NÃO CONFUNDIR com variância: avulsa nunca teve provisão; Conciliação (4.5.01/5.7.01) é resíduo
de uma que existiu. `despesa_avulsa` recusa essas duas contas explicitamente."""
import pytest

import mod_contabil as mc


def test_despesa_avulsa_sem_projeto_continua_default_none(app_db, seed):
    """Controle: o caso avulso-sem-projeto pré-existente (garantia/concessão) não muda de
    comportamento — projeto_id continua None quando não informado."""
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        lanc = mc.despesa_avulsa(db, ot, oid, "5.2.12", 200.0, "direto", ref="f230f2:sem_proj")
        db.commit()
        assert lanc["projeto_id"] is None
    finally:
        _limpar(app_db, seed, extra_natureza="5.2.12")


def test_despesa_avulsa_com_projeto_entra_na_margem_do_projeto(app_db, seed):
    antes = _margem(app_db, seed)
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        lanc = mc.despesa_avulsa(db, ot, oid, "5.3.22", 500.0, "direto", ref="f230f2:com_proj",
                                 projeto_id=seed["projeto_l1"],
                                 historico="Compra complementar não prevista na venda")
        db.commit()
        assert lanc["projeto_id"] == seed["projeto_l1"]
    finally:
        db.close()
    depois = _margem(app_db, seed)
    assert round(depois["comissao"] - antes["comissao"], 2) == 500.0
    assert round(antes["margem_contribuicao"] - depois["margem_contribuicao"], 2) == 500.0
    # margem_projetada = margem_contribuicao − não_reconhecido; a avulsa não está em
    # _PROV_DESPESA_POR_ATIVO, então não_reconhecido nem se move — a queda passa direto pra
    # projetada, sem catch-up nem duplicação (F2-30 Fatia 3: quem nunca vê a avulsa é o CÁLCULO
    # de não_reconhecido, não a margem projetada — que é só a realizada menos esse termo).
    assert round(antes["margem_projetada"] - depois["margem_projetada"], 2) == 500.0
    _limpar(app_db, seed, extra_natureza="5.3.22")


def test_despesa_avulsa_recusa_contas_de_conciliacao(app_db, seed):
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        with pytest.raises(ValueError):
            mc.despesa_avulsa(db, ot, oid, "4.5.01", 100.0, "direto", ref="f230f2:receita_conc",
                              projeto_id=seed["projeto_l1"])
        with pytest.raises(ValueError):
            mc.despesa_avulsa(db, ot, oid, "5.7.01", 100.0, "direto", ref="f230f2:despesa_conc",
                              projeto_id=seed["projeto_l1"])
        db.rollback()
    finally:
        db.close()


def _margem(app_db, seed):
    db = app_db.get_session()
    try:
        import mod_contabil as mc
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        return mc.margem_projeto(db, ot, oid, seed["projeto_l1"])
    finally:
        db.close()


def _limpar(app_db, seed, extra_natureza=None):
    """seed/app_db são module-scoped — sem isto, o próximo teste deste arquivo herdaria o
    lançamento (regra dos irmãos, F2-29 Fatia D). Filtra por ref (não por projeto_id — o
    controle sem-projeto grava projeto_id=None, que o filtro por projeto não pegaria)."""
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        db.query(mc.Lancamento).filter(mc.Lancamento.owner_tipo == ot,
                                       mc.Lancamento.owner_id == oid,
                                       mc.Lancamento.ref.like("f230f2:%")).delete(
                                           synchronize_session=False)
        db.commit()
    finally:
        db.close()
