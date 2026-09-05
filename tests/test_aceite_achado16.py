"""docs/db/TAREFA_ACHADO16.md, Passo 8 do ROTEIRO — o conserto do ACHADO-16.

Até 2026-08-30, `resolver_saldo_provisao` (mod_contabil.py:2035) cancelava o saldo de uma
provisão contra o ativo diferido espelho, sem tocar a DRE, presumindo que "sobra" = dinheiro
nunca gasto. Quando a efetivação era ZERO, a "sobra" era 100% da provisão — e o sistema não
distinguia "não foi gasto" de "foi gasto e ninguém lançou". A Conciliação Final (etapa 21) aceitava
concluir o projeto nesse estado, em silêncio.

Teste 1: aceite — a conclusão SEM veredito é recusada (o `xfail(strict=True)` do passo 1 sai
neste commit: a conclusão passou a ser recusada de verdade, não é mais um bug pendente).
Teste 2 (reescrito 05/09, F2-27): a Conciliação Final não decide mais sozinha qual é o caso —
mas o que ela decide MUDOU de novo, com o modelo contábil. Até 05/09/2026 (F2-27), sem a
despesa ter nascido em lugar nenhum, o veredito precisava RECONHECER o custo real antes de
reverter o resíduo. Desde então a emissão da NF-e já reconhece o PROVISIONADO INTEGRAL antes da
Conciliação Final rodar — o veredito 'receber' só decide pra onde vai o resíduo entre o
reconhecido e o pago (Receita de Conciliação, nunca mais "reconhece de novo" um valor
diferente)."""
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


def test_veredito_receber_reverte_a_sobra_apos_a_emissao_ja_ter_reconhecido_o_integral(
        app_db, seed, http_client_factory):
    """F2-27 (docs/db/MODELO_CONTABIL.md) reescreveu o mecanismo que este teste prova: até
    05/09/2026, sem a despesa ter nascido em lugar nenhum, o veredito 'encerrada_valor_menor'
    tinha que RECONHECER o custo real (`valor_efetivado`) antes de reverter o resíduo — havia
    algo ainda por lançar. Agora não há mais: a emissão da NF-e já reconheceu o PROVISIONADO
    INTEGRAL (1000) em 5.1.01, antes mesmo da Conciliação Final rodar. O que resta pra decidir é
    só pra onde vai o resíduo entre o reconhecido (1000) e o que a fábrica de fato cobrou (700,
    pago via Efetivar) — 'receber' manda a sobra (300) pra Receita de Conciliação, nunca mais
    "reconhece de novo" um valor diferente do que a emissão já fixou."""
    import mod_contabil as mc
    nome = "ACHADO16_receber"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)
    db = app_db.get_session()
    mc.reconhecer_provisoes_segmento(db, ot, oid, nome, "mercadoria", 100.0, ref_base="rec:doc1")
    db.commit()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.06", 700.0, ref="ef:fabrica")   # a fábrica cobrou 700
    db.commit(); db.close()

    ger = _login(http_client_factory, "dir_l1")
    st, body = ger.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {
        "vereditos": {"2.1.04.06": {"veredito": "receber"}},
    })
    assert st == 200 and body.get("ok"), body
    assert body["vereditos"]["2.1.04.06"]["veredito"] == "receber"
    assert body["vereditos"]["2.1.04.06"]["valor_revertido"] == 300.0

    db = app_db.get_session()
    saldo_provisao = mc._mov(db, ot, oid, "2.1.04.06", "credor", None, None, projeto_id=nome)
    debito_5101 = mc._mov(db, ot, oid, "5.1.01", "devedor", None, None, projeto_id=nome)
    receita_conciliacao = mc._mov(db, ot, oid, "4.5.01", "credor", None, None, projeto_id=nome)
    db.close()

    # a despesa é o PROVISIONADO INTEGRAL (1000), fixado na emissão — o veredito não mexe nele
    assert abs(debito_5101 - 1000.0) < 0.005, (
        "5.1.01 deveria ter o provisionado integral (1000), reconhecido na emissão — %r" % debito_5101)
    # a sobra (300) vira Receita de Conciliação — em bloco próprio, nunca reabrindo 5.1.01
    assert abs(receita_conciliacao - 300.0) < 0.005, (
        "4.5.01 deveria ter a sobra (300) — %r" % receita_conciliacao)
    assert abs(saldo_provisao) < 0.005, (
        "provisão (deste projeto) deveria estar zerada após pagar 700 e reverter o resíduo "
        "de 300 — %r" % saldo_provisao)
