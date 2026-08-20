import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_lista_projetos_traz_parceiro_nome(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # cria um parceiro e associa a um projeto do seed
    st, dp = c.post("/api/parceiros", {"nome": "Arq Teste", "tipo": "arquiteto", "cpf_cnpj": "111.444.777-35"})
    assert st == 200, dp
    pid = dp["parceiro"]["id"]
    proj = seed["projeto_l1"]
    st2, _ = c.post(f"/api/projetos/{proj}/parceiro", {"parceiro_id": pid})
    assert st2 == 200
    st3, d = c.get("/projetos")
    assert st3 == 200
    alvo = next(p for p in d["projetos"] if p["nome_safe"] == proj)
    assert alvo["parceiro_id"] == pid
    assert alvo["parceiro_nome"] == "Arq Teste"
    # projeto sem parceiro -> parceiro_nome None/ausente, sem quebrar
    outros = [p for p in d["projetos"] if p["nome_safe"] != proj]
    assert all(p.get("parceiro_nome") in (None, "") for p in outros if not p.get("parceiro_id"))


def test_lista_projetos_ultimo_orcamento_ignora_rascunho_zerado(http_client_factory, seed, app_db, projetos_dir):
    """Achado do usuário 2026-08-19: criar um "Novo Orçamento" para efeito comparativo (rascunho
    vazio, valor_total=0) fazia o box "Último Orçamento" da lista de projetos zerar, mesmo com o
    orçamento negociado/salvo intacto — a query pegava sempre o mais recente por
    updated_at/id, não o que realmente tem valor. Deve continuar mostrando o valor salvo até o
    rascunho novo também ser negociado."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    db = app_db.get_session()
    orc_salvo = db.query(app_db.Orcamento).filter_by(projeto_id=proj, ordem=1).first()
    orc_salvo.valor_total = 50000.0
    db.commit()
    # "Novo Orçamento" para comparação — rascunho vazio, sem ambientes, valor_total=0 (default)
    rascunho = app_db.Orcamento(projeto_id=proj, nome="Orçamento 2", ordem=2, loja_id=orc_salvo.loja_id)
    db.add(rascunho); db.commit()
    db.close()
    st, d = c.get("/projetos")
    assert st == 200
    alvo = next(p for p in d["projetos"] if p["nome_safe"] == proj)
    assert alvo["ultimo_orcamento_valor"] == 50000.0


def test_lista_projetos_traz_consultor(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    # marca o usuário logado como criador (consultor) do projeto
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    meta = db.query(app_db.Projeto).filter_by(nome_safe=proj).first()
    meta.criado_por_id = u.id
    db.commit()
    uid, unome = u.id, u.nome
    db.close()
    st, d = c.get("/projetos")
    assert st == 200
    alvo = next(p for p in d["projetos"] if p["nome_safe"] == proj)
    assert alvo["consultor_id"] == uid
    assert alvo["consultor_nome"] == unome
    # projeto sem criador -> consultor_nome None, sem quebrar
    outros = [p for p in d["projetos"] if p["nome_safe"] != proj]
    assert all(p.get("consultor_nome") is None for p in outros if not p.get("consultor_id"))
