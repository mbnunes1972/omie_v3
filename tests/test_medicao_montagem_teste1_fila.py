# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0109.md, "Medição pedida, sem conserto".

O Marcelo relatou: "A Provisão de Montagem do projeto Teste 1 não resolveu na Fila", sem ter
anotado a mensagem. Reprodução pedida: efetivar PARCIALMENTE uma Montagem, tentar CADA veredito
na Fila, reportar a mensagem exata e qual veredito é recusado. SEM CONSERTO — é medição pura;
este teste documenta o comportamento atual, não corrige nada."""
import mod_contabil as mc

from tests.test_aceite_achado16 import _projeto_pronto_para_etapa_21


def _constituir_montagem(app_db, seed, nome, valor=1000.0):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"montagem": valor}, ref_base="pf:" + nome)
    db.commit()
    db.close()
    return ot, oid


def test_montagem_parcialmente_efetivada_recusa_o_veredito_efetivada(app_db, seed):
    """Reprodução: Montagem provisionada R$1000, efetivada R$400 (SOBRA de R$600 aberta) — exatamente
    o estado do projeto Teste 1 no percurso do Marcelo (Montagem do Teste 1 sempre parcial: as
    entregas de material chegam em levas, raramente batendo o provisionado exato)."""
    nome = "MedicaoMontagemTeste1"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_montagem(app_db, seed, nome, valor=1000.0)

    db = app_db.get_session()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.02", 400.0, ref="medicao:teste1:efetiva-parcial")
    db.commit()

    # "Efetivada" — recusado. Mensagem exata, pra quem bater nisto de novo saber ler de cara.
    try:
        mc.resolver_veredito_provisao(db, ot, oid, nome, "2.1.04.02", "efetivada",
                                      ref="medicao:teste1:veredito-efetivada")
        recusado = False
        mensagem = None
    except ValueError as e:
        recusado = True
        mensagem = str(e)
    db.close()

    assert recusado is True, "esperava recusa — se passou a aceitar, o comportamento mudou"
    assert mensagem == (
        "2.1.04.02 tem SOBRA de 600.00 (não FALTA) — 'efetivada' só vale quando o efetivado já "
        "supera o provisionado; escolha 'encerrada_valor_menor' ou 'nao_se_aplica'."
    ), "a mensagem exata mudou — reveja o que reportar (%r)" % mensagem


def test_montagem_parcialmente_efetivada_aceita_os_outros_tres_vereditos(app_db, seed):
    """Controle: os OUTROS três vereditos resolvem normalmente na mesma situação — confirma que o
    caso é ESPECÍFICO de 'Efetivada' com SOBRA aberta, não a Fila travada por inteiro."""
    nome = "MedicaoMontagemTeste1_b"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_montagem(app_db, seed, nome, valor=1000.0)

    db = app_db.get_session()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.02", 400.0, ref="medicao:b:efetiva-parcial")
    db.commit()

    v = mc.resolver_veredito_provisao(db, ot, oid, nome, "2.1.04.02", "ainda_vai_chegar",
                                      ref="medicao:b:veredito-ainda-vai-chegar")
    assert v.veredito == "ainda_vai_chegar"
    db.close()
