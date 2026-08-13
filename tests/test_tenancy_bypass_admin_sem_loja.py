"""Achado da auditoria estática 2026-08-13: `lid = usuario.get("loja_id")` seguido de
`if x is None or (lid and x.loja_id != lid): 404` curto-circuita quando `lid` é None — o caso
NORMAL de admin_rede/super_admin (que não têm `loja_id` próprio, só `rede_id`/nenhum). A checagem
de tenant nunca rodava para esses dois perfis, em `/api/expedicao/cards/<id>` (+ mover/editar),
`/api/assistencias/casos/<id>/anexo/<id>` (download de arquivo), `/api/assistencias/casos/<id>/
realizar` (lançamento contábil na rede ERRADA) e `/api/folha/<id>/pagar` (idem). Fix: usar
`mod_tenancy.escopo_operacional` (mesmo padrão já usado no resto do arquivo) — sem loja ATIVA
selecionada, 403 em vez de bypass."""
import json


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_super_sem_loja_ativa_bloqueado_no_card_de_expedicao(http_client_factory, seed, app_db):
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    assert st in (200, 201), d
    cid = d["id"]

    c_super = _login(http_client_factory, "super")   # loja_id=None, rede_id=None — SEM X-Loja-Ativa
    st2, d2 = c_super.get("/api/expedicao/cards/%d" % cid)
    assert st2 == 403, d2   # antes do fix: 200 com os dados do card de outra loja


def test_super_com_loja_ativa_ve_so_a_propria(http_client_factory, seed, app_db):
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    cid = d["id"]

    c_super = _login(http_client_factory, "super")
    c_super.loja_ativa = seed["loja1_id"]
    st2, d2 = c_super.get("/api/expedicao/cards/%d" % cid)
    assert st2 == 200 and d2["ok"] is True, d2

    c_super.loja_ativa = seed["loja2_id"]
    st3, d3 = c_super.get("/api/expedicao/cards/%d" % cid)
    assert st3 == 404, d3   # card é da loja 1, não da loja ativa (2)


def test_admrede_sem_loja_ativa_bloqueado_no_card(http_client_factory, seed, app_db):
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    cid = d["id"]

    c_rede = _login(http_client_factory, "adm_rede")   # rede_id setado, loja_id=None, sem header
    st2, d2 = c_rede.get("/api/expedicao/cards/%d" % cid)
    assert st2 == 403, d2   # antes do fix: 200 (mesmo bug — lid=None também pra admin_rede)


def test_admrede_com_loja_ativa_da_propria_rede_ve_card(http_client_factory, seed, app_db):
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    cid = d["id"]

    # admin_rede não ganha acesso a toda loja da rede automaticamente — precisa de membership
    # explícito (usuario_lojas), como em produção. Sem isso, escopo_operacional bloqueia mesmo
    # com X-Loja-Ativa setado — comportamento correto (fail-safe), não parte do bug corrigido.
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="adm_rede").first()
    if not db.query(app_db.UsuarioLoja).filter_by(usuario_id=u.id, loja_id=seed["loja1_id"]).first():
        db.add(app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja1_id"]))
        db.commit()
    db.close()

    c_rede = _login(http_client_factory, "adm_rede")
    c_rede.loja_ativa = seed["loja1_id"]
    st2, d2 = c_rede.get("/api/expedicao/cards/%d" % cid)
    assert st2 == 200 and d2["ok"] is True, d2


def test_mover_card_bloqueado_sem_loja_ativa(http_client_factory, seed, app_db):
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    cid = d["id"]

    c_super = _login(http_client_factory, "super")
    st2, d2 = c_super.post("/api/expedicao/cards/%d/mover" % cid, {"novo_status": "producao"})
    assert st2 == 403, d2


def test_anexo_assistencia_download_bloqueado_sem_loja_ativa(http_client_factory, seed, app_db):
    """O achado mais grave: download de arquivo (conteúdo binário) de um caso de outra loja."""
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/assistencias/casos", {
        "projeto_nome": seed["projeto_l1"], "sub_tipo": "pos_conclusao", "motivo": "alteracao_projeto",
        "descricao": "teste", "valor": 100.0})
    assert st in (200, 201), d
    caso_id = d["id"]

    c_super = _login(http_client_factory, "super")
    # mesmo sem anexo existente, o gate de tenant tem que barrar ANTES de procurar o anexo
    st2, d2 = c_super.get("/api/assistencias/casos/%d/anexo/1" % caso_id)
    assert st2 == 403, d2


def test_realizar_caso_bloqueado_sem_loja_ativa(http_client_factory, seed, app_db):
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/assistencias/casos", {
        "projeto_nome": seed["projeto_l1"], "sub_tipo": "pos_conclusao", "motivo": "alteracao_projeto",
        "descricao": "teste", "valor": 100.0})
    caso_id = d["id"]

    c_super = _login(http_client_factory, "super")
    st2, d2 = c_super.post("/api/assistencias/casos/%d/realizar" % caso_id, {"valor": 100.0})
    assert st2 == 403, d2


def test_realizar_caso_lanca_nos_livros_da_loja_dona_nao_do_atacante(http_client_factory, seed, app_db):
    """Mesmo com loja ativa LEGÍTIMA, resolver_owner tem que usar a loja escopada — não o
    usuario cru — pra não lançar nos livros errados quando o ator é admin_rede/super_admin."""
    c1 = _login(http_client_factory, "dir_l1")
    st, d = c1.post("/api/assistencias/casos", {
        "projeto_nome": seed["projeto_l1"], "sub_tipo": "pos_conclusao", "motivo": "alteracao_projeto",
        "descricao": "teste", "valor": 100.0})
    caso_id = d["id"]

    c_super = _login(http_client_factory, "super")
    c_super.loja_ativa = seed["loja1_id"]
    st2, d2 = c_super.post("/api/assistencias/casos/%d/realizar" % caso_id, {"valor": 100.0})
    assert st2 == 200 and d2["ok"] is True, d2

    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    # motivo="alteracao_projeto" -> tipo_custo "paga" -> evento "venda_assistencia". Tem que
    # existir nos livros da LOJA 1 (dona do caso) — não em algum owner derivado da sessão do
    # "super" (que não tem loja_id/rede_id próprios, resolver_owner(db, usuario) cairia noutro
    # owner ou levantaria erro).
    lan = mc.lancamento_por_ref(db, ot, oid, "assist:%d" % caso_id)
    assert lan is not None and lan["valor"] == 100.0, lan
    db.close()


def test_folha_pagar_bloqueado_sem_loja_ativa(http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="FxTenancy", salario_fixo=1500.0, usa_comissao_vendas=0,
                       status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="TenancyTest", funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
                                parte_fixa=1500.0, total=1500.0, status="aprovada")
    db.add(reg); db.flush()
    fid = reg.id
    db.commit(); db.close()

    c_super = _login(http_client_factory, "super")
    st, d = c_super.post("/api/folha/%d/pagar" % fid, {})
    assert st == 403, d   # antes do fix: tentaria pagar (e lançar) sem checagem de tenant nenhuma
