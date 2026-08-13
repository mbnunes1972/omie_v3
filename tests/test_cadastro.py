def test_funcionario_crud_e_isolamento(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "João RH", "cpf": "111.444.777-35",
                                         "cargo": "Supervisor", "remuneracao_tipo": "fixa",
                                         "remuneracao_fixa": 3000})
    assert st == 201, d
    fid = d["id"]
    _, lst = c.get("/api/funcionarios")
    assert any(x["id"] == fid and x["cargo"] == "Supervisor" for x in lst["itens"])
    # outra loja não enxerga
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    _, lst2 = c2.get("/api/funcionarios")
    assert all(x["id"] != fid for x in lst2["itens"])
    # inativar -> some do filtro por status=ativo
    st3, _ = c.post("/api/funcionarios/%d" % fid, {"status": "inativo"})
    assert st3 == 200
    _, lst3 = c.get("/api/funcionarios?status=ativo")
    assert all(x["id"] != fid for x in lst3["itens"])


def test_funcionario_acesso_cria_usuario_vinculado_sem_duplicar(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "Maria Acesso", "cpf": "111.444.777-35",
        "acesso": {"tem_acesso": True, "email": "maria@loja.com", "perfil": "operador"}})
    assert st == 201, d
    fid = d["id"]
    # fronteira: existe UM Usuário ligado por funcionario_id; o Funcionário aponta de volta
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(funcionario_id=fid).first()
        assert u is not None and u.login == "maria@loja.com" and u.nivel == "operador" and u.ativo == 1
        assert db.get(app_db.Funcionario, fid).usuario_id == u.id
    finally:
        db.close()
    # a conta entra com a senha inicial = dígitos do CPF
    c2 = http_client_factory()
    st2, d2 = c2.post("/api/auth/login", {"login": "maria@loja.com", "senha": "11144477735"})
    assert st2 == 200 and d2["ok"] is True
    # remover acesso -> desativa a conta (não apaga)
    st3, _ = c.post("/api/funcionarios/%d" % fid, {"acesso": {"tem_acesso": False}})
    assert st3 == 200
    db = app_db.get_session()
    try:
        assert db.query(app_db.Usuario).filter_by(funcionario_id=fid).first().ativo == 0
    finally:
        db.close()


def test_funcionario_sem_cpf_ganha_senha_aleatoria_nao_previsivel(http_client_factory, seed, app_db):
    """Achado de auditoria 2026-08-13: sem CPF, a senha inicial caía num fallback hardcoded
    ("orizon123") — qualquer um sabendo o e-mail de login sequestrava a conta antes do 1º acesso.
    Agora é um token aleatório (senha_provisoria=1 já força a troca no 1º login)."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "Sem CPF",
        "acesso": {"tem_acesso": True, "email": "semcpf@loja.com", "perfil": "operador"}})
    assert st == 201, d
    c2 = http_client_factory()
    st2, d2 = c2.post("/api/auth/login", {"login": "semcpf@loja.com", "senha": "orizon123"})
    assert st2 == 401 and d2.get("ok") is False, d2   # senha hardcoded antiga NÃO funciona mais
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login="semcpf@loja.com").first()
        assert u is not None and u.senha_provisoria == 1
    finally:
        db.close()


def test_acesso_email_duplicado_barrado(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/funcionarios", {"nome": "A", "cpf": "111.444.777-35",
        "acesso": {"tem_acesso": True, "email": "dup@loja.com", "perfil": "operador"}})
    st, d = c.post("/api/funcionarios", {"nome": "B", "cpf": "168.995.350-09",
        "acesso": {"tem_acesso": True, "email": "dup@loja.com", "perfil": "operador"}})
    assert st == 400 and "conta" in d["erro"].lower()


def test_fornecedor_crud_busca(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/fornecedores", {"nome": "Dal Mobile", "tipo_pessoa": "pj",
        "cnpj_cpf": "11.444.777/0001-61", "categoria": "materia_prima", "prazo_pagamento": 30})
    assert st == 201, d
    _, lst = c.get("/api/fornecedores?q=dal")
    it = next(x for x in lst["itens"] if x["nome"] == "Dal Mobile")
    assert it["categoria"] == "materia_prima" and it["prazo_pagamento"] == 30 and it["tipo_pessoa"] == "pj"
    assert "materia_prima" in lst["meta"]["fornecedor_categorias"]


def test_terceiro_crud(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/terceiros", {"nome": "Zé Montador", "cpf": "168.995.350-09",
        "tipo_servico": "montador", "pix": "ze@pix", "condicao": "mei"})
    assert st == 201, d
    _, lst = c.get("/api/terceiros?q=168")   # busca por documento
    it = next(x for x in lst["itens"] if x["id"] == d["id"])
    assert it["tipo_servico"] == "montador" and it["pix"] == "ze@pix" and it["condicao"] == "mei"


def test_funcoes_catalogo_e_referencia(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcoes", {"nome": "Montador"})
    assert st == 201, d
    fid = d["id"]
    _, lst = c.get("/api/funcoes")
    assert any(x["id"] == fid and x["nome"] == "Montador" for x in lst["itens"])
    # Funcionário referencia a função (não texto livre) e traz o nome resolvido
    st2, d2 = c.post("/api/funcionarios", {"nome": "Fulano", "funcao_id": fid})
    assert st2 == 201
    _, fl = c.get("/api/funcionarios")
    assert next(x for x in fl["itens"] if x["id"] == d2["id"])["funcao_nome"] == "Montador"


def test_endereco_e_dados_bancarios_persistem(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "Endç", "cep": "01001-000", "logradouro": "Praça da Sé",
        "numero": "10", "cidade": "São Paulo", "uf": "SP", "banco_nome": "Itaú", "banco_codigo": "341",
        "agencia": "1234", "conta": "56789-0", "pix": "endc@pix"})
    assert st == 201, d
    _, lst = c.get("/api/funcionarios")
    it = next(x for x in lst["itens"] if x["id"] == d["id"])
    assert it["logradouro"] == "Praça da Sé" and it["uf"] == "SP" and it["banco_codigo"] == "341" and it["pix"] == "endc@pix"
