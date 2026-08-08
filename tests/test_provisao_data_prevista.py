"""Data prevista de efetivação por provisão (2026-08-07, pedido do usuário — mesma ideia dos
recebíveis, aplicada às provisões). Metadado só (ProvisaoDataPrevista) — não lança nada no razão.
GET /api/financeiro/reconciliacao-provisoes enxerta data_prevista/vencido por linha quando
?projeto= é passado (consolidado não tem UM projeto pra atribuir a data)."""
import mod_contabil as mc

# projeto_id aqui é só uma TAG de lançamento (não precisa existir como Projeto real — reconciliacao()
# filtra Lancamento.projeto_id como string) — cada teste usa uma tag própria porque o banco é
# module-scoped (compartilhado entre os testes do arquivo) e reconciliacao soma o razão inteiro
# daquela tag; reusar a mesma tag entre testes acumularia provisionado/efetivado de um teste no outro.


def _constituir(db, ot, oid, projeto_tag, valor=1000.0):
    mc.constituir_provisoes_fechamento(db, ot, oid, projeto_tag, {"frete_fabrica": valor},
                                       ref_base="pf:" + projeto_tag)


def _owner(app_db, seed):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    return db, ot, oid


def test_salvar_data_prevista_cria_e_atualiza(http_client_factory, seed, app_db):
    tag = "PDPTeste1"
    db, ot, oid = _owner(app_db, seed)
    _constituir(db, ot, oid, tag)
    db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/financeiro/provisao-data-prevista",
                   {"projeto": tag, "conta": "2.1.04.07", "data_prevista": "2027-03-10"})
    assert st == 200 and d["ok"] is True, d
    assert d["data_prevista"] == "2027-03-10"
    # atualiza (upsert, não duplica linha)
    st2, d2 = c.post("/api/financeiro/provisao-data-prevista",
                     {"projeto": tag, "conta": "2.1.04.07", "data_prevista": "2027-04-01"})
    assert st2 == 200 and d2["data_prevista"] == "2027-04-01"
    db2 = app_db.get_session()
    rows = db2.query(app_db.ProvisaoDataPrevista).filter_by(
        projeto_nome=tag, codigo_conta="2.1.04.07").all()
    assert len(rows) == 1 and rows[0].data_prevista.isoformat() == "2027-04-01"
    db2.close()


def test_salvar_data_prevista_rejeita_conta_nao_provisao(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/financeiro/provisao-data-prevista",
                   {"projeto": "PDPTeste2", "conta": "1.1.01", "data_prevista": "2027-01-01"})
    assert st == 400 and d["ok"] is False


def test_salvar_data_prevista_exige_projeto_e_data(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/financeiro/provisao-data-prevista", {"conta": "2.1.04.07", "data_prevista": "2027-01-01"})
    assert st == 400 and d["ok"] is False
    st2, d2 = c.post("/api/financeiro/provisao-data-prevista", {"projeto": "PDPTeste3", "conta": "2.1.04.07"})
    assert st2 == 400 and d2["ok"] is False


def test_reconciliacao_enxerta_data_e_vencido_quando_projeto_setado(http_client_factory, seed, app_db):
    tag = "PDPTeste4"
    db, ot, oid = _owner(app_db, seed)
    _constituir(db, ot, oid, tag, valor=2000.0)
    db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/provisao-data-prevista",
          {"projeto": tag, "conta": "2.1.04.07", "data_prevista": "2020-01-01"})   # passado
    st, d = c.get("/api/financeiro/reconciliacao-provisoes?projeto=" + tag)
    assert st == 200 and d["ok"] is True, d
    linha = next(p for p in d["reconciliacao"]["provisoes"] if p["codigo"] == "2.1.04.07")
    assert linha["data_prevista"] == "2020-01-01"
    assert linha["vencido"] is True   # data passada + saldo aberto > 0


def test_reconciliacao_sem_projeto_nao_tem_data(http_client_factory, seed, app_db):
    tag = "PDPTeste5"
    db, ot, oid = _owner(app_db, seed)
    _constituir(db, ot, oid, tag, valor=500.0)
    db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/provisao-data-prevista",
          {"projeto": tag, "conta": "2.1.04.07", "data_prevista": "2020-01-01"})
    st, d = c.get("/api/financeiro/reconciliacao-provisoes")   # consolidado, sem ?projeto=
    assert st == 200 and d["ok"] is True, d
    linhas = [p for p in d["reconciliacao"]["provisoes"] if p["codigo"] == "2.1.04.07"]
    assert linhas and all(p["data_prevista"] is None and p["vencido"] is False for p in linhas)


def test_vencido_falso_quando_saldo_ja_zerou(http_client_factory, seed, app_db):
    tag = "PDPTeste6"
    db, ot, oid = _owner(app_db, seed)
    _constituir(db, ot, oid, tag, valor=900.0)
    mc.efetivar_provisao(db, ot, oid, tag, "2.1.04.07", 900.0, ref="ef:" + tag)
    db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/provisao-data-prevista",
          {"projeto": tag, "conta": "2.1.04.07", "data_prevista": "2020-01-01"})
    st, d = c.get("/api/financeiro/reconciliacao-provisoes?projeto=" + tag)
    linha = next(p for p in d["reconciliacao"]["provisoes"] if p["codigo"] == "2.1.04.07")
    assert abs(linha["saldo_aberto"]) < 0.005
    assert linha["vencido"] is False   # já resolvido, data passada não importa mais
