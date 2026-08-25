"""GET /projetos/<nome> expõe Projeto.status (achado do usuário 2026-08-25, Visão Geral do
Projeto): a Visão Geral usa isso pra saber quando mostrar o banner de "resumo definitivo" (projeto
concluído, pós Etapa 21/Conciliação Final)."""


def test_get_projeto_expoe_status(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    nome = seed["projeto_l1"]
    st, d = c.get(f"/projetos/{nome}")
    assert st == 200 and d["ok"] is True
    assert d["projeto"].get("status") not in (None, "concluido")   # ainda não concluído no seed

    db = app_db.get_session()
    db.query(app_db.Projeto).filter_by(nome_safe=nome).first().status = "concluido"
    db.commit(); db.close()

    st, d = c.get(f"/projetos/{nome}")
    assert st == 200 and d["projeto"]["status"] == "concluido"
