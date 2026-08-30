"""docs/db/TAREFA_ACHADO16.md, Passo 8 do ROTEIRO — o conserto do ACHADO-16.

Até 2026-08-30, `resolver_saldo_provisao` (mod_contabil.py:2035) cancelava o saldo de uma
provisão contra o ativo diferido espelho, sem tocar a DRE, presumindo que "sobra" = dinheiro
nunca gasto. Quando a efetivação era ZERO, a "sobra" era 100% da provisão — e o sistema não
distinguia "não foi gasto" de "foi gasto e ninguém lançou". A Conciliação Final (etapa 21) aceitava
concluir o projeto nesse estado, em silêncio.

Teste 1: aceite — a conclusão SEM veredito é recusada (o `xfail(strict=True)` do passo 1 sai
neste commit: a conclusão passou a ser recusada de verdade, não é mais um bug pendente).
Teste 2 (reescrito): a Conciliação Final não decide mais sozinha qual é o caso — com o veredito
'encerrada_valor_menor' e um valor_efetivado real, ela reconhece o custo de verdade em 5.1.01 (a
"despesa que ocorreu e ninguém tinha lançado", o próprio exemplo do achado) e só reverte o que
sobra depois disso. O mecanismo antigo (zerar a provisão sem tocar 5.1.01 quando o efetivado é
menor que o saldo) não existe mais incondicionalmente — só quando é isso que o veredito diz."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _projeto_pronto_para_etapa_21(app_db, seed, nome):
    """Projeto raso (sem contrato/orçamento — a Conciliação Final não exige nenhum dos dois,
    só as etapas e a ausência de ambiente retido — mesmo padrão de
    tests/test_retido.py::test_endpoint_conciliar_barrado_por_etapas_pendentes), com etapa 20
    (Aprovação Final, única predecessora que `mod_ciclo.pode_avancar` checa) concluída."""
    db = app_db.get_session()
    db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"], status="fechado"))
    db.add(app_db.PoolAmbiente(projeto_id=nome, nome="A0", nome_exibicao="Amb 0",
                               xml_path="x", ambientes_json="[]"))
    db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo="20", status="concluido"))
    db.commit()
    db.close()


def _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0):
    """Constitui a provisão de Custo de Fábrica (2.1.04.06, ativo 1.1.06.06, despesa 5.1.01) e
    NUNCA efetiva — a assinatura exata do ACHADO-16: 100% da provisão é "sobra" porque ninguém
    lançou a efetivação, não porque o custo não ocorreu (o teste não pode e não tenta distinguir
    os dois — é isso que o achado diz que o sistema também não consegue)."""
    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"custo_fabrica": valor},
                                       ref_base="pf:" + nome)
    db.commit()
    db.close()
    return ot, oid


def test_conciliacao_final_recusa_com_provisao_nunca_efetivada(app_db, seed, http_client_factory):
    """ACHADO-16 (docs/db/ACEITE.md), item 1: a Conciliação Final RECUSA concluir um projeto com
    provisão em aberto sem veredito nomeado — não decide mais sozinha."""
    nome = "ACHADO16_aceite"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    ger = _login(http_client_factory, "dir_l1")
    st, body = ger.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {})

    assert not (st == 200 and body.get("ok")), (
        "conclusão deveria ser RECUSADA sem veredito para a provisão de Custo de Fábrica em "
        "aberto — resposta: st=%r body=%r" % (st, body))


def test_veredito_encerrada_valor_menor_reconhece_custo_real_antes_de_reverter(app_db, seed, http_client_factory):
    """Reescrita de test_mecanismo_hoje_cancela_saldo_sem_tocar_5101 (passo 1): aquele teste
    media o mecanismo antigo — provisão 100%% em aberto, nunca efetivada, cancelada sem tocar
    5.1.01. Esse mecanismo não existe mais incondicionalmente: sem veredito a conclusão é
    recusada (teste acima). Este teste prova o mecanismo NOVO no mesmo cenário motivador do
    achado — "foi gasto e ninguém lançou": a fábrica entregou por 700 de uma provisão de 1000, e
    é isso que o veredito 'encerrada_valor_menor' revela. As duas pernas são verificadas
    SEPARADAMENTE (não só o saldo final, que não distingue uma perna de duas)."""
    import mod_contabil as mc
    nome = "ACHADO16_encerrada_valor_menor"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    ger = _login(http_client_factory, "dir_l1")
    st, body = ger.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {
        "vereditos": {"2.1.04.06": {"veredito": "encerrada_valor_menor", "valor_efetivado": 700.0}},
    })
    assert st == 200 and body.get("ok"), body
    assert body["vereditos"]["2.1.04.06"]["veredito"] == "encerrada_valor_menor"
    assert body["vereditos"]["2.1.04.06"]["valor_efetivado"] == 700.0
    assert body["vereditos"]["2.1.04.06"]["valor_revertido"] == 300.0

    db = app_db.get_session()
    saldo_provisao = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=nome)
    debito_5101 = mc._mov(db, ot, oid, "5.1.01", "devedor", None, None, projeto_id=nome)
    db.close()

    # perna 1 — o custo real (o que a fábrica de fato entregou) chega na DRE
    assert abs(debito_5101 - 700.0) < 0.005, (
        "5.1.01 deveria ter o custo real reconhecido (700) — %r" % debito_5101)
    # perna 2 — só o resíduo genuíno (300, superprovisionado) reverte, e só depois da perna 1
    assert abs(saldo_provisao) < 0.005, (
        "provisão (deste projeto) deveria estar zerada após efetivar 700 e reverter o resíduo "
        "de 300 — %r" % saldo_provisao)
