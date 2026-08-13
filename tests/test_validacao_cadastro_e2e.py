import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def _cli(c, **extra):
    body = {"nome": "X", "email": "x@x.com", "telefone": "(12) 90000-0000"}; body.update(extra)
    return c.post("/api/clientes", body)

def test_cliente_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="111.444.777-00")
    assert st == 400 and "cpf" in d.get("erro","").lower()

def test_cliente_cpf_repetido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="111.111.111-11")
    assert st == 400

def test_cliente_cpf_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="390.533.447-05")
    assert st == 200 and d["ok"], d

def test_cliente_sem_cpf_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c)   # sem cpf -> permitido (opcional)
    assert st == 200 and d["ok"], d

def test_cliente_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, tipo_dest="contribuinte", cnpj="11.222.333/0001-00")
    assert st == 400 and "cnpj" in d.get("erro","").lower()

def test_cliente_editar_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="168.995.350-09"); cid = d["cliente"]["id"]
    st2, d2 = c.post(f"/api/clientes/{cid}/editar", {"cpf": "111.444.777-00"})
    assert st2 == 400


def test_cliente_cpf_duplicado_por_corrida_devolve_erro_limpo_nao_500(
        http_client_factory, seed, monkeypatch):
    """Achado de auditoria 2026-08-13 (achado baixo): o except genérico da criação de Cliente
    vazava a mensagem crua do Postgres numa corrida de CPF duplicado (a checagem em memória,
    `db.query(Cliente).filter_by(cpf=cpf).first()`, é TOCTOU). Simulado com uma query que nunca
    acha nada — o CPF já existe de verdade, o INSERT tem que estourar a constraint do banco, e o
    servidor tem que devolver erro de negócio limpo (não 500 com detalhe cru do Postgres)."""
    import main as _main
    from database import Cliente as _Cliente
    from sqlalchemy.orm import Query as _Query
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st0, d0 = _cli(c, cpf="529.982.247-25")
    assert st0 == 200 and d0["ok"], d0

    orig_first = _Query.first
    def _first_que_ignora_cliente(self):
        if self.column_descriptions and self.column_descriptions[0]["type"] is _Cliente:
            return None
        return orig_first(self)
    monkeypatch.setattr(_Query, "first", _first_que_ignora_cliente)

    st, body = _cli(c, cpf="529.982.247-25")
    assert body.get("ok") is False
    assert st == 409, body
    assert "cpf" in body.get("erro", "").lower()


# ── VD-Task 3: parceiro / usuário / rede / loja ──────────────────────────────

def test_parceiro_cpf_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/parceiros", {"nome": "P", "tipo": "arquiteto",
                                      "cpf_cnpj": "111.111.111-11"})
    assert st == 400, d

def test_parceiro_cpf_cnpj_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/parceiros", {"nome": "P", "tipo": "arquiteto",
                                      "cpf_cnpj": "111.444.777-35"})
    assert st == 200 and d.get("ok"), d

def test_parceiro_cnpj_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/parceiros", {"nome": "P PJ", "tipo": "arquiteto",
                                      "cpf_cnpj": "11.222.333/0001-81"})
    assert st == 200 and d.get("ok"), d

def test_parceiro_sem_doc_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/parceiros", {"nome": "P Sem Doc", "tipo": "arquiteto"})
    assert st == 200 and d.get("ok"), d

def test_parceiro_editar_cpf_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/parceiros", {"nome": "P Edit", "tipo": "arquiteto"})
    pid = d["parceiro"]["id"]
    st2, d2 = c.post(f"/api/parceiros/{pid}/editar", {"cpf_cnpj": "11.222.333/0001-00"})
    assert st2 == 400, d2


def test_usuario_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/admin/usuarios", {
        "nome": "U", "login": "u_cpf_bad", "senha": "s1", "nivel": "operador",
        "cpf": "111.111.111-11", "loja_id": seed["loja1_id"]})
    assert st == 400, d

def test_usuario_cpf_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/admin/usuarios", {
        "nome": "U", "login": "u_cpf_ok", "senha": "s1", "nivel": "operador",
        "cpf": "390.533.447-05", "loja_id": seed["loja1_id"]})
    assert st == 200 and d.get("ok"), d


def test_rede_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")
    st, d = c.post("/api/admin/redes", {"nome": "R Bad", "cnpj": "11.222.333/0001-00"})
    assert st == 400, d

def test_rede_cnpj_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")
    st, d = c.post("/api/admin/redes", {"nome": "R Ok", "cnpj": "11.222.333/0001-81"})
    assert st == 200 and d.get("ok"), d


def test_loja_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")
    st, d = c.post("/api/admin/lojas", {
        "nome": "L Bad", "codigo": "XBD", "rede_id": seed["rede_id"],
        "cnpj": "11.222.333/0001-00"})
    assert st == 400, d

def test_loja_cnpj_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")
    st, d = c.post("/api/admin/lojas", {
        "nome": "L Ok", "codigo": "XOK", "rede_id": seed["rede_id"],
        "cnpj": "11.222.333/0001-81"})
    assert st == 200 and d.get("ok"), d


# ── Achado de auditoria 2026-08-13: Funcionário/Fornecedor/Terceiro nunca validavam
#    dígito verificador de CPF/CNPJ (Cliente/Parceiro/Rede/Loja/Usuario/Emitente já validam) ──
def test_funcionario_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "X", "cpf": "111.444.777-00"})
    assert st == 400 and "cpf" in d.get("erro", "").lower()

def test_funcionario_cpf_valido_201(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "X", "cpf": "390.533.447-05"})
    assert st == 201, d

def test_funcionario_sem_cpf_201(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "X"})
    assert st == 201, d

def test_terceiro_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/terceiros", {"nome": "X", "cpf": "111.444.777-00"})
    assert st == 400 and "cpf" in d.get("erro", "").lower()

def test_fornecedor_cnpj_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/fornecedores", {"nome": "X", "cnpj_cpf": "11.222.333/0001-00"})
    assert st == 400 and "cpf" in d.get("erro", "").lower()

def test_fornecedor_cnpj_valido_201(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/fornecedores", {"nome": "X", "cnpj_cpf": "11.222.333/0001-81"})
    assert st == 201, d
