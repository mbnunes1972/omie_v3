"""Cadastro completo de loja: cria loja + diretor (senha provisória) + módulos; PATCH edita/associa rede."""


def test_super_admin_cadastra_loja_completa(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.post("/api/admin/lojas", {
        "nome": "Loja Nova", "codigo": "LNV", "cnpj": "11.222.333/0001-81",
        "telefone": "1133330000", "email": "loja@nova.com", "responsavel": "Fulano",
        "logradouro": "Rua X", "numero": "10", "bairro": "Centro", "cidade": "Sao Paulo",
        "estado": "SP", "cep": "01000-000",
        "diretor": {"nome": "Diretor Novo", "login": "dir@nova.com"},
        "modulos": ["cadastro", "comercial", "fiscal"],
    })
    assert st in (200, 201) and out["ok"], out
    lid = out["loja"]["id"]
    db = app_db.get_session()
    lo = db.get(app_db.Loja, lid)
    diru = db.query(app_db.Usuario).filter_by(login="dir@nova.com").first()
    resp, est, mods = lo.responsavel, lo.estado, (lo.modulos_ativos or "")
    dn = (diru.nivel, diru.loja_id, diru.senha_provisoria) if diru else (None, None, None)
    db.close()
    assert resp == "Fulano" and est == "SP" and "comercial" in mods
    assert diru is not None and dn == ("master", lid, 1)


def test_loja_nova_ganha_tabela_de_funcoes(http_client_factory, seed, app_db):
    """2026-08-08 (achado da Vera): antes os 13 FUNCOES_PADRAO só nasciam no seed inicial do
    banco ou no backfill de boot — loja criada em runtime ficava sem cargo nenhum."""
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.post("/api/admin/lojas", {
        "nome": "Loja Sem Funcao Antes", "codigo": "LSF",
        "diretor": {"nome": "Diretor LSF", "login": "dir@lsf.com"},
    })
    assert st in (200, 201) and out["ok"], out
    lid = out["loja"]["id"]
    db = app_db.get_session()
    nomes = {f.nome for f in db.query(app_db.Funcao).filter_by(loja_id=lid).all()}
    db.close()
    assert len(nomes) == len(app_db.FUNCOES_PADRAO)
    assert "Consultor de Vendas" in nomes


def test_pdv_novo_ganha_tabela_de_funcoes(http_client_factory, seed, app_db):
    db = app_db.get_session()
    mae_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.post(f"/api/admin/lojas/{mae_id}/pdvs", {"nome": "PDV Sem Funcao Antes", "codigo": "PSF"})
    assert st in (200, 201) and out["ok"], out
    pdv_id = out["pdv"]["id"]
    db = app_db.get_session()
    n = db.query(app_db.Funcao).filter_by(loja_id=pdv_id).count()
    db.close()
    assert n == len(app_db.FUNCOES_PADRAO)


def test_patch_associa_rede_e_edita(http_client_factory, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    rede = db.query(app_db.Rede).first(); rid = rede.id if rede else None
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.patch(f"/api/admin/lojas/{l1}", {"rede_id": rid, "responsavel": "Novo Resp"})
    assert st == 200 and out["ok"], out
    db = app_db.get_session(); lo = db.get(app_db.Loja, l1); rr, rd = lo.responsavel, lo.rede_id; db.close()
    assert rr == "Novo Resp" and rd == rid
