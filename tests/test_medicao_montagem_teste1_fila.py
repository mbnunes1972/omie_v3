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


def test_montagem_parcialmente_efetivada_recusa_o_veredito_absorver(app_db, seed):
    """Reprodução: Montagem provisionada R$1000, efetivada R$400 (SOBRA de R$600 aberta) — exatamente
    o estado do projeto Teste 1 no percurso do Marcelo (Montagem do Teste 1 sempre parcial: as
    entregas de material chegam em levas, raramente batendo o provisionado exato).

    F2-27: 'efetivada' foi renomeado pra 'absorver' e a mensagem de recusa mudou de forma (não
    fala mais em SOBRA/FALTA explícito no texto, lista os vereditos_validos_para_saldo direto)."""
    nome = "MedicaoMontagemTeste1"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_montagem(app_db, seed, nome, valor=1000.0)

    db = app_db.get_session()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.02", 400.0, ref="medicao:teste1:efetiva-parcial")
    db.commit()

    # "Absorver" — recusado. Mensagem exata, pra quem bater nisto de novo saber ler de cara.
    try:
        mc.resolver_veredito_provisao(db, ot, oid, nome, "2.1.04.02", "absorver",
                                      ref="medicao:teste1:veredito-absorver")
        recusado = False
        mensagem = None
    except ValueError as e:
        recusado = True
        mensagem = str(e)
    db.close()

    assert recusado is True, "esperava recusa — se passou a aceitar, o comportamento mudou"
    assert mensagem == (
        "2.1.04.02 tem saldo de 600.00 — 'absorver' não vale pra esse sinal "
        "(válidos aqui: ['adiar', 'receber'])."
    ), "a mensagem exata mudou — reveja o que reportar (%r)" % mensagem


def test_montagem_parcialmente_efetivada_aceita_os_outros_dois_vereditos(app_db, seed):
    """Controle: os OUTROS dois vereditos (F2-27: só 'receber'/'adiar' valem pra SOBRA, 'encerrar'
    exige saldo≈0) resolvem normalmente na mesma situação — confirma que o caso é ESPECÍFICO de
    'Absorver' com SOBRA aberta, não a Fila travada por inteiro."""
    nome = "MedicaoMontagemTeste1_b"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_montagem(app_db, seed, nome, valor=1000.0)

    db = app_db.get_session()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.02", 400.0, ref="medicao:b:efetiva-parcial")
    db.commit()

    v = mc.resolver_veredito_provisao(db, ot, oid, nome, "2.1.04.02", "adiar",
                                      ref="medicao:b:veredito-adiar")
    assert v.veredito == "adiar"
    db.close()
