"""docs/db/TAREFA_TESTE_ACHADO16.md, Passo 1 do ROTEIRO — a prova do ACHADO-16.

NÃO CONSERTA NADA. `resolver_saldo_provisao` (mod_contabil.py:2035) cancela o saldo de uma
provisão contra o ativo diferido espelho, sem tocar a DRE, presumindo que "sobra" = dinheiro
nunca gasto. Quando a efetivação é ZERO, a "sobra" é 100% da provisão — e o sistema não distingue
"não foi gasto" de "foi gasto e ninguém lançou". A Conciliação Final (etapa 21) hoje ACEITA
concluir o projeto nesse estado.

Teste 1: aceite, `xfail(strict=True)` — a conclusão TEM que ser recusada; hoje é aceita.
Teste 2: medição, verde hoje e depois — documenta o MECANISMO do defeito (saldo zerado, nada em
5.1.01), não a política de correção."""
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


@pytest.mark.xfail(strict=True, reason="ACHADO-16 (docs/db/ACEITE.md): a Conciliação Final tem "
                    "que RECUSAR concluir um projeto com provisão nunca efetivada — hoje ela "
                    "aceita e cancela o saldo em silêncio contra o ativo diferido, sem tocar a "
                    "DRE. Vira verde sozinho quando o passo 8 (vereditos) entrar; XPASS quebra "
                    "a suíte e obriga remover este marcador.")
def test_conciliacao_final_recusa_com_provisao_nunca_efetivada(app_db, seed, http_client_factory):
    nome = "ACHADO16_aceite"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    ger = _login(http_client_factory, "dir_l1")
    st, body = ger.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {})

    assert not (st == 200 and body.get("ok")), (
        "conclusão deveria ser RECUSADA com provisão de Custo de Fábrica 100%% não efetivada — "
        "resposta hoje: st=%r body=%r" % (st, body))


def test_mecanismo_hoje_cancela_saldo_sem_tocar_5101(app_db, seed, http_client_factory):
    """MEDIÇÃO, não política: registra a assinatura exata do defeito de hoje, pra ela não voltar
    por outro caminho depois do conserto do passo 8 mudar a POLÍTICA (aceitar/recusar). O que não
    pode voltar a mudar em silêncio é o MECANISMO aqui descrito enquanto ele for o vigente: saldo
    da provisão zerado e nenhum débito em 5.1.01 (despesa real de Custo de Fábrica) pra este
    projeto — exatamente o "cancela sem tocar a DRE" que o docstring de resolver_saldo_provisao
    descreve."""
    import mod_contabil as mc
    nome = "ACHADO16_medicao"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    ger = _login(http_client_factory, "dir_l1")
    st, body = ger.post("/api/projetos/%s/ciclo/21/conciliar" % nome, {})
    assert st == 200 and body.get("ok"), body   # comportamento ACEITO hoje — é o que este teste documenta

    db = app_db.get_session()
    c_prov = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="2.1.04.06").first()
    saldo_provisao = mc.saldo_conta(db, ot, oid, c_prov.id)
    debito_5101 = mc._mov(db, ot, oid, "5.1.01", "devedor", None, None, projeto_id=nome)
    db.close()

    assert abs(saldo_provisao) < 0.005, (
        "provisão de Custo de Fábrica deveria estar zerada após a Conciliação Final — %r"
        % saldo_provisao)
    assert abs(debito_5101) < 0.005, (
        "nenhum débito deveria ter chegado em 5.1.01 (despesa real) pra este projeto — o custo "
        "nunca foi reconhecido, só cancelado contra o ativo diferido: %r" % debito_5101)
