"""Fase 1: config de remuneração por Função — salário fixo, comissão (por meta?), benefícios."""


def _funcoes(c):
    _, d = c.get("/api/funcoes")
    return d.get("itens") or []


def _fid(app_db):
    db = app_db.get_session()
    lid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    f = app_db.Funcao(loja_id=lid, nome="Montador X", status="ativo"); db.add(f); db.commit()
    fid = f.id; db.close(); return fid


def test_grava_remuneracao(http_client_factory, seed, app_db):
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.post(f"/api/funcoes/{fid}", {
        "salario_fixo": 2500.50,
        "comissao": {"por_meta": False, "base": "fabrica", "pct": 3.0},
        "beneficios": {"at": {"on": True, "valor": 200.0},
                       "va": {"on": True, "valor": 600.0},
                       "ps": {"on": False, "valor": 0.0}},
    })
    assert out.get("ok"), out
    fn = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn["salario_fixo"] == 2500.50
    assert fn["comissao"]["por_meta"] is False and fn["comissao"]["base"] == "fabrica" and fn["comissao"]["pct"] == 3.0
    assert fn["beneficios"]["at"]["on"] is True and fn["beneficios"]["at"]["valor"] == 200.0
    assert fn["beneficios"]["ps"]["on"] is False


def test_comissao_por_meta_e_base_invalida(http_client_factory, seed, app_db):
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post(f"/api/funcoes/{fid}", {"comissao": {"por_meta": True, "base": "xxx",
                                                "faixas": [{"venda_ate": 50000, "pct": 2.0}, {"venda_ate": None, "pct": 4.0}]}})
    fn = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn["comissao"]["por_meta"] is True
    assert fn["comissao"]["base"] == "liquido"          # base inválida -> default liquido
    assert len(fn["comissao"]["faixas"]) == 2


def test_consultor_vendas_usa_comissao_da_loja(seed, app_db):
    from seed import criar_funcoes_seed
    from database import Funcao, Session
    db = Session()
    lid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    criar_funcoes_seed(db, lid)   # idempotente
    cv = db.query(Funcao).filter_by(loja_id=lid, nome="Consultor de Vendas").first()
    assert cv is not None and bool(cv.usa_comissao_vendas) is True
    db.close()


def test_funcao_custom_liga_comissao_de_vendas_via_api(http_client_factory, seed, app_db):
    """🔴 achado da Vera (2026-08-08): funcao_aplicar nunca lia usa_comissao_vendas do
    payload — só o seed inicial (por nome exato "Consultor de Vendas") gravava isso.
    Função nova/custom não tinha como ligar a comissão por metas da loja."""
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.post(f"/api/funcoes/{fid}", {"usa_comissao_vendas": True})
    assert st == 200 and out["ok"], out
    fn = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn["usa_comissao_vendas"] is True
    # dá pra desligar de novo
    c.post(f"/api/funcoes/{fid}", {"usa_comissao_vendas": False})
    fn2 = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn2["usa_comissao_vendas"] is False
