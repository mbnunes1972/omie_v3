"""docs/db/TAREFA_FASE0.md, Passo 4 do ROTEIRO — os três aceites de causa do ACHADO-19/ACHADO-20.

NÃO CONSERTA NADA. Reusa os estados já construídos e medidos em
tests/test_negociacao_breakdown_excecoes.py (Medição 1) e tests/test_fail_soft_medicao2.py
(Medição 2) — cada um deles já provou o comportamento ATUAL; estes três provam o comportamento
QUE FALTA, agnóstico a como o conserto for implementado."""
import json

import pytest


def _breakdown_levanta(app_db, orc_id):
    import main
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, orc_id)
        try:
            main._negociacao_breakdown(orc, db)
            return False, None
        except Exception as e:
            return True, e
    finally:
        db.close()


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# ── 1. parametros_json malformado não derruba _negociacao_breakdown ─────────────────────────
@pytest.mark.xfail(strict=True, reason="ACHADO-19 (docs/db/ACEITE.md): parametros_json "
                    "malformado deveria cair no default com falha nomeada, como o "
                    "config_financeira_json vizinho (main.py, linhas logo acima de "
                    "_negociacao_breakdown) já faz. Hoje json.loads(proj.parametros_json) não "
                    "tem try/except — levanta JSONDecodeError (confirmado em "
                    "test_negociacao_breakdown_excecoes.py::test_parametros_json_malformado_levanta).")
def test_parametros_json_malformado_cai_no_default(app_db, seed):
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    projeto_id = orc.projeto_id
    proj = db.query(app_db.Projeto).filter_by(nome_safe=projeto_id).first()
    proj.parametros_json = "{isto nao é json"
    db.commit(); db.close()

    try:
        levantou, exc = _breakdown_levanta(app_db, oid)
        assert not levantou, (
            "parametros_json malformado NÃO deveria levantar — deveria cair no default, como "
            "o config_financeira_json vizinho já faz: %r" % (exc,))
    finally:
        db = app_db.get_session()
        proj = db.query(app_db.Projeto).filter_by(nome_safe=projeto_id).first()
        proj.parametros_json = None
        db.commit(); db.close()


# ── 2. complemento auto-referente: recusado com erro nomeado, não RecursionError ─────────────
@pytest.mark.xfail(strict=True, reason="ACHADO-20 (docs/db/ACEITE.md): complemento_pe=1 no MESMO "
                    "orçamento que já é o Contrato.orcamento_id do projeto (auto-referência) "
                    "deveria ser RECUSADO com um erro nomeado — hoje é RecursionError opaco "
                    "(confirmado em test_negociacao_breakdown_excecoes.py::"
                    "test_complemento_pe_no_proprio_orcamento_do_contrato_recursao_infinita).")
def test_complemento_auto_referente_recusado_com_erro_nomeado(app_db, seed):
    oid = seed["orcamento_l1_id"]   # é o mesmo Orcamento de seed["contrato_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.complemento_pe = 1
    db.commit(); db.close()

    try:
        levantou, exc = _breakdown_levanta(app_db, oid)
        assert levantou and not isinstance(exc, RecursionError), (
            "complemento auto-referente deveria levantar um erro NOMEADO (ex.: ValueError "
            "citando a auto-referência), nunca RecursionError opaco — hoje: %r" % (exc,))
    finally:
        db = app_db.get_session()
        db.get(app_db.Orcamento, oid).complemento_pe = 0
        db.commit(); db.close()


# ── 3. /parametros não devolve sombra quando o recálculo do laço falhou ──────────────────────
@pytest.mark.xfail(strict=True, reason="ACHADO-19 (docs/db/ACEITE.md): /parametros NÃO deveria "
                    "devolver `sombra` quando algum _recalcular_orcamento do laço falhou — igual "
                    "ao que /margens já faz (sombra: None no except). Hoje main.py:10893 chama "
                    "_negociacao_breakdown incondicionalmente fora do try/except do laço, e a "
                    "tela mostra um número que o banco não tem (medido em "
                    "test_fail_soft_medicao2.py::test_parametros_fail_soft, ACHADOS_CONTABEIS.md "
                    "Medição 3 do TESTE_NEGOCIACAO_VALOR_TOTAL.md).")
def test_parametros_nao_devolve_sombra_com_recalculo_falho(app_db, seed, http_client_factory, monkeypatch):
    import main
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                             nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                             budget_total=90000.0, order_total=40000.0)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/%s/parametros" % seed["projeto_l1"], {"carga_trib": 8.0})
    assert st == 200 and body["ok"], body   # 1ª chamada real, sem falha — estabelece um "antes"

    def _explode(orc, db):
        raise RuntimeError("falha forçada — aceite ACHADO-19")
    monkeypatch.setattr(main, "_recalcular_orcamento", _explode)

    st, body = c.post("/api/projetos/%s/parametros" % seed["projeto_l1"],
                      {"comissao_arq_ativa": True, "comissao_arq_pct": 15.0})
    assert st == 200 and body["ok"], body
    assert body.get("sombra") is None, (
        "/parametros NÃO deveria devolver sombra com o recálculo falho — hoje devolve um "
        "breakdown recalculado ao vivo, mostrando um número que o banco não tem: %r"
        % body.get("sombra"))
