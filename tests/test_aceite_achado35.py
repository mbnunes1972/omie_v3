"""docs/db/TAREFA_PERCURSO_0109.md, item B1 — os aceites do ACHADO-35.

`efetivar_provisao` era idempotente por `ref = "ef:<projeto>:<conta>:<valor>:<hoje>"` — chave
desenhada em 07/08 CONTRA o duplo-clique, que passou a recusar (em silêncio, antes do item 3 do
ACHADO-32; com mensagem, depois dele) a SEGUNDA efetivação real do mesmo dia. Conserto: recusa
vira CONFIRMAÇÃO — "Já foram efetivados R$ X hoje. Confirmar mais R$ Y?" — e, confirmado, lança
com `ref` novo (sufixo sequencial), nunca colidindo com o de antes. Regra 3: o total "já
efetivado hoje" vem do RAZÃO (`mod_contabil.efetivado_no_dia`), nunca de uma soma lembrada pela
tela — por isso os aceites conferem a resposta do endpoint, não uma variável de teste."""
import pytest

from tests.test_aceite_achado16 import _projeto_pronto_para_etapa_21


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _constituir_montagem(app_db, seed, nome, valor=10000.0):
    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"montagem": valor}, ref_base="pf:" + nome)
    db.commit()
    db.close()
    return ot, oid


def test_segundo_efetivar_do_dia_mesmo_valor_pede_confirmacao_e_lanca_dois(app_db, seed, http_client_factory):
    """Aceite principal (o teste do TAREFA_PERCURSO_0109.md): efetivar 3.000, efetivar 3.000 de
    novo → aparece a confirmação; confirmando, o efetivado vai a 6.000 e há DOIS lançamentos."""
    nome = "ACHADO35_aceite1"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_montagem(app_db, seed, nome, valor=10000.0)
    c = _login(http_client_factory, "dir_l1")

    st1, d1 = c.post("/api/financeiro/efetivar-provisao",
                     {"projeto": nome, "conta": "2.1.04.02", "valor": 3000.0})
    assert st1 == 200 and d1["ok"] and d1["novo"] is True, d1

    # Regra 3: sem confirmar, recusa dizendo o total do RAZÃO — não lança nada.
    st2, d2 = c.post("/api/financeiro/efetivar-provisao",
                     {"projeto": nome, "conta": "2.1.04.02", "valor": 3000.0})
    assert st2 == 200 and d2["ok"] is False and d2["duplicado"] is True, d2
    assert d2["total_hoje"] == 3000.0, "o total tem que vir do razão, não de uma soma da tela"

    # Confirmado: lança de verdade, com ref próprio.
    st3, d3 = c.post("/api/financeiro/efetivar-provisao",
                     {"projeto": nome, "conta": "2.1.04.02", "valor": 3000.0, "confirmado": True})
    assert st3 == 200 and d3["ok"] and d3["novo"] is True, d3
    assert d3["total_hoje"] == 6000.0

    db = app_db.get_session()
    import mod_contabil as mc
    conta = mc._conta_por_codigo(db, *mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None}), "2.1.04.02")
    lancs = db.query(app_db.Lancamento).filter_by(conta_debito_id=conta.id, projeto_id=nome).all()
    db.close()
    assert len(lancs) == 2, "dois lançamentos distintos, um por efetivação real — não um só"
    assert len({l.ref for l in lancs}) == 2, (
        "refs têm que ser distintos — nunca colidir o segundo com o primeiro")


def test_segundo_efetivar_do_dia_valor_diferente_tambem_pede_confirmacao(app_db, seed, http_client_factory):
    """Pedido explícito do Marcelo ('poderia haver erro também'): vale pra valor IGUAL OU
    DIFERENTE — antes do conserto, um valor diferente passava direto (só a chave por valor+dia
    colidia), e essa era a prova de que a guarda protegia pouco."""
    nome = "ACHADO35_aceite2"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_montagem(app_db, seed, nome, valor=10000.0)
    c = _login(http_client_factory, "dir_l1")

    st1, d1 = c.post("/api/financeiro/efetivar-provisao",
                     {"projeto": nome, "conta": "2.1.04.02", "valor": 3000.0})
    assert st1 == 200 and d1["ok"], d1

    st2, d2 = c.post("/api/financeiro/efetivar-provisao",
                     {"projeto": nome, "conta": "2.1.04.02", "valor": 2000.0})
    assert st2 == 200 and d2["ok"] is False and d2["duplicado"] is True, (
        "valor diferente também exige confirmação — a guarda antiga só travava o par idêntico")
    assert d2["total_hoje"] == 3000.0

    st3, d3 = c.post("/api/financeiro/efetivar-provisao",
                     {"projeto": nome, "conta": "2.1.04.02", "valor": 2000.0, "confirmado": True})
    assert st3 == 200 and d3["ok"], d3
    assert d3["total_hoje"] == 5000.0
