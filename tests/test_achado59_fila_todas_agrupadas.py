# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-59, Passo 3 — DECIDIDO pelo Marcelo (05/09): "as
provisões devem aparecer sempre todas juntas." A Fila passava a listar SÓ as rubricas com saldo
em aberto — uma provisão resolvida (zerada) ou que nunca teve movimento algum simplesmente
sumia, ficando indistinguível de uma que ninguém olhou. Agora TODA rubrica elegível pra fila
aparece sempre, marcada com `grupo` ("em_aberto" ou "fechada_zerada"), migrando de grupo sozinha
conforme o saldo muda — e a contagem de cada grupo vem rotulada (`contagens` na resposta da
rota), pra não repetir o defeito do Passo 0(b) (número sem dizer do que é a contagem)."""
import mod_contabil as mc

from tests.test_aceite_achado16 import _projeto_pronto_para_etapa_21, _constituir_custo_fabrica_nunca_efetivado


def _login(f, who="dir_l1"):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_fila_lista_rubricas_nunca_tocadas_como_fechadas_zeradas(http_client_factory, seed, app_db):
    nome = "F25P3_todas_agrupadas"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=1000.0)

    c = _login(http_client_factory)
    st, body = c.get("/api/financeiro/fila-provisoes")
    assert st == 200 and body["ok"], body
    linhas = [r for r in body["fila"] if r["projeto_id"] == nome]

    # o universo elegível pra fila = todas as contas 2.1.04.% do plano, exceto as sem mecanismo
    # (_PROV_PAINEL_EXCLUI) e as de rota própria (_PROV_FORA_DO_VEREDITO, Impostos/Cust_Fin,
    # ACHADO-01) — 21 no plano, 4 excluídas, 17 sempre aparecem pra este projeto.
    excluir = mc._PROV_PAINEL_EXCLUI | mc._PROV_FORA_DO_VEREDITO
    assert len(linhas) == 21 - len(excluir), (
        "a fila tem que listar TODAS as rubricas elegíveis pro projeto, tocadas ou não — %r"
        % sorted(r["codigo"] for r in linhas))

    # a única rubrica com movimento fica em_aberto; as outras 16, nunca tocadas, aparecem
    # zeradas — visíveis, mas sem ação (não somem, não é a mesma coisa que "ninguém olhou").
    cfo = next(r for r in linhas if r["codigo"] == "2.1.04.06")
    assert cfo["grupo"] == "em_aberto" and cfo["saldo_aberto"] == 1000.0

    outras = [r for r in linhas if r["codigo"] != "2.1.04.06"]
    assert len(outras) == len(linhas) - 1
    assert all(r["grupo"] == "fechada_zerada" and abs(r["saldo_aberto"]) < 0.005 for r in outras), outras
    assert all(r["constituida_em"] is None for r in outras), (
        "rubrica nunca tocada não tem lançamento — constituida_em tem que ficar None")

    # a contagem rotulada bate com os dois grupos.
    assert body["contagens"]["em_aberto"] == 1
    assert body["contagens"]["fechadas_zeradas"] == len(outras)


def test_rubrica_migra_de_grupo_ao_ser_resolvida(http_client_factory, seed, app_db):
    """A mesma rubrica, no mesmo projeto: antes do veredito ela está em_aberto; depois, sem
    sumir da fila, ela migra sozinha pra fechada_zerada."""
    nome = "F25P3_migra_grupo"
    _projeto_pronto_para_etapa_21(app_db, seed, nome)
    _constituir_custo_fabrica_nunca_efetivado(app_db, seed, nome, valor=500.0)

    c = _login(http_client_factory)
    st, body = c.get("/api/financeiro/fila-provisoes")
    linha = next(r for r in body["fila"] if r["projeto_id"] == nome and r["codigo"] == "2.1.04.06")
    assert linha["grupo"] == "em_aberto"

    st, body = c.post("/api/financeiro/fila-provisoes/veredito",
                      {"projeto": nome, "conta": "2.1.04.06", "veredito": "receber"})
    assert st == 200 and body.get("ok"), body

    st, body = c.get("/api/financeiro/fila-provisoes")
    assert st == 200 and body["ok"], body
    linha2 = next((r for r in body["fila"] if r["projeto_id"] == nome and r["codigo"] == "2.1.04.06"), None)
    assert linha2 is not None, "não pode sumir — tem que migrar de grupo, não desaparecer"
    assert linha2["grupo"] == "fechada_zerada"
    assert abs(linha2["saldo_aberto"]) < 0.005
