# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-41 (escrito 02/09, depois do B6).

A Fila desenhava os quatro botões de veredito em toda linha, mesmo sabendo (via
`resolver_veredito_provisao`) que dois deles seriam recusados dependendo do sinal do saldo —
"Efetivada" numa linha em SOBRA, ou "Encerrada · valor menor"/"Não se aplica" numa linha em
FALTA, sempre voltam com erro. A lista de vereditos válidos passa a vir do BACKEND
(`mod_contabil.vereditos_validos_para_saldo`), DERIVADA das mesmas checagens que
`resolver_veredito_provisao` usa pra recusar — nunca uma cópia da regra no JavaScript. A tela
desenha só os botões que o backend aceitaria."""
import mod_contabil as mc

from tests.test_aceite_achado16 import _projeto_pronto_para_etapa_21


def _constituir_montagem(app_db, seed, nome, valor=1000.0):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"montagem": valor}, ref_base="pf:" + nome)
    db.commit()
    db.close()
    return ot, oid


def _login(f, who="dir_l1"):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_linha_em_sobra_nao_oferece_efetivada(http_client_factory, seed, app_db):
    nome = "ACHADO41_sobra"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_montagem(app_db, seed, nome, valor=1000.0)
    db = app_db.get_session()
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.02", 400.0, ref="achado41:sobra:efetiva")
    db.commit(); db.close()

    c = _login(http_client_factory)
    st, body = c.get("/api/financeiro/fila-provisoes")
    assert st == 200 and body["ok"], body
    linha = next(r for r in body["fila"] if r["projeto_id"] == nome and r["codigo"] == "2.1.04.02")
    assert linha["saldo_aberto"] == 600.0, "SOBRA de 600 — confirma o cenário"
    assert set(linha["vereditos_validos"]) == {"encerrada_valor_menor", "nao_se_aplica", "ainda_vai_chegar"}
    assert "efetivada" not in linha["vereditos_validos"]

    # o backend continua recusando por trás — o campo é DERIVADO, não redundante por acaso
    try:
        mc.resolver_veredito_provisao(db, ot, oid, nome, "2.1.04.02", "efetivada", ref="achado41:sobra:tenta")
        assert False, "deveria recusar"
    except ValueError:
        pass


def test_linha_em_falta_nao_oferece_encerrada_nem_nao_se_aplica(http_client_factory, seed, app_db):
    nome = "ACHADO41_falta"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    ot, oid = _constituir_montagem(app_db, seed, nome, valor=1000.0)
    db = app_db.get_session()
    # efetiva MAIS do que o provisionado, via duas efetivações confirmadas (B1) — FALTA de 200.
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.02", 1000.0, ref="achado41:falta:efetiva1")
    mc.efetivar_provisao(db, ot, oid, nome, "2.1.04.02", 200.0, ref="achado41:falta:efetiva2")
    db.commit(); db.close()

    c = _login(http_client_factory)
    st, body = c.get("/api/financeiro/fila-provisoes")
    assert st == 200 and body["ok"], body
    linha = next(r for r in body["fila"] if r["projeto_id"] == nome and r["codigo"] == "2.1.04.02")
    assert linha["saldo_aberto"] == -200.0, "FALTA de 200 — confirma o cenário"
    assert set(linha["vereditos_validos"]) == {"efetivada", "ainda_vai_chegar"}
    assert "encerrada_valor_menor" not in linha["vereditos_validos"]
    assert "nao_se_aplica" not in linha["vereditos_validos"]
