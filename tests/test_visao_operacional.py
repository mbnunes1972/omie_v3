"""Re-chave da VISÃO OPERACIONAL (2026-08-03, achado 🔴1 da Vera na Agenda).

Desde a migração Perfil-4 nenhuma conta tinha os níveis aposentados
(`medidor`/`projetista_executivo`/`supervisor_montagem`) — `escopo_por_atribuicao` nunca
disparava e a visão "operacional" (sem comercial) ficou DORMENTE. Agora o discriminador é a
FUNÇÃO do Funcionário vinculado à conta (`Funcao.atribuicoes_json` quando preenchida; senão o
catálogo de nomes PAPEL_FUNCOES), com guarda: gerência/admin nunca são escopados pelo Mapa."""
from database import AtribuicaoAmbiente, CicloEtapa, Funcao, Funcionario, Projeto, Usuario

import mod_escopo


# ── predicados puros ─────────────────────────────────────────────────────────────

def test_funcao_operacional_por_nome_e_por_papeis():
    assert mod_escopo.funcao_operacional("Medidor")
    assert mod_escopo.funcao_operacional("Projetista Executivo")
    assert mod_escopo.funcao_operacional("Montador")
    assert not mod_escopo.funcao_operacional("Consultor de Vendas")
    assert not mod_escopo.funcao_operacional(None)
    # atribuicoes_json preenchida é a fonte PREFERIDA (vence o nome)
    assert mod_escopo.funcao_operacional("Qualquer Nome", ["medicao"])
    assert not mod_escopo.funcao_operacional("Medidor", ["papel_inexistente"])


def test_escopo_por_atribuicao_via_funcao_com_guarda_de_gerencia():
    medidor = {"nivel": "operador", "funcao_nome": "Medidor", "funcao_papeis": None}
    assert mod_escopo.escopo_por_atribuicao(medidor)
    assert mod_escopo.visao_do_papel(medidor) == "operacional"
    consultor = {"nivel": "operador", "funcao_nome": "Consultor de Vendas"}
    assert not mod_escopo.escopo_por_atribuicao(consultor)
    assert mod_escopo.visao_do_papel(consultor) == "comercial"
    # gerência com função operacional cadastrada NÃO vira operacional
    diretor_montador = {"nivel": "master", "funcao_nome": "Montador"}
    assert not mod_escopo.escopo_por_atribuicao(diretor_montador)
    assert mod_escopo.visao_do_papel(diretor_montador) == "comercial"
    # legado (níveis aposentados) segue aceito — inofensivo
    assert mod_escopo.escopo_por_atribuicao({"nivel": "medidor"})


# ── ponta a ponta: conta real de medidor na Agenda e no bloqueio comercial ───────

def _criar_medidor(app_db, seed, login="med_l1"):
    """Usuário operador + Funcionário com Função 'Medidor' + atribuição no Proj_L1."""
    db = app_db.get_session()
    try:
        u = db.query(Usuario).filter_by(login=login).first()
        if not u:
            u = Usuario(nome="Medidor L1", login=login, nivel="operador",
                        loja_id=seed["loja1_id"], ativo=1)
            u.set_senha("senha123")
            db.add(u); db.flush()
        f = db.query(Funcao).filter_by(loja_id=seed["loja1_id"], nome="Medidor").first()
        if not f:
            f = Funcao(loja_id=seed["loja1_id"], nome="Medidor", status="ativo")
            db.add(f); db.flush()
        func = db.query(Funcionario).filter_by(usuario_id=u.id).first()
        if not func:
            func = Funcionario(loja_id=seed["loja1_id"], nome="Medidor L1",
                               funcao_id=f.id, usuario_id=u.id)
            db.add(func); db.flush()
        else:
            func.funcao_id = f.id
        atr = (db.query(AtribuicaoAmbiente)
                 .filter_by(projeto_nome=seed["projeto_l1"], funcionario_id=func.id).first())
        if not atr:
            db.add(AtribuicaoAmbiente(loja_id=seed["loja1_id"], projeto_nome=seed["projeto_l1"],
                                      pool_ambiente_id=None, papel="medicao",
                                      funcionario_id=func.id))
        db.commit()
        return u.id
    finally:
        db.close()


def _garantir_marco(app_db, seed):
    from datetime import datetime
    db = app_db.get_session()
    try:
        p = db.get(Projeto, seed["projeto_l1"])
        p.data_entrega = datetime(2026, 12, 1)
        e = db.query(CicloEtapa).filter_by(projeto_nome=seed["projeto_l1"],
                                           etapa_codigo="9").first()
        if not e:
            e = CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="9"); db.add(e)
        e.data_prevista_conclusao = datetime(2026, 9, 5)
        db.commit()
    finally:
        db.close()


def test_agenda_operacional_sem_valores_e_sem_cargas(app_db, seed, http_client_factory):
    _criar_medidor(app_db, seed)
    _garantir_marco(app_db, seed)
    c = http_client_factory(); c.login("med_l1", "senha123")
    st, d = c.get("/api/agenda?de=2026-01-01&ate=2027-12-31")
    assert st == 200 and d["ok"], (st, d)
    assert d["visao"] == "operacional"
    assert d["marcos"], "medidor atribuído ao projeto deve ver os marcos dele"
    assert all(m["projeto"] == seed["projeto_l1"] for m in d["marcos"])   # só o atribuído
    assert all(m["valor"] is None for m in d["marcos"])                   # SEM comercial
    assert d["cargas"] == [] and d["capacidade"] == [] and d["capacidade_cfg"] == {}


def test_operacional_bloqueado_no_comercial(app_db, seed, http_client_factory):
    _criar_medidor(app_db, seed)
    c = http_client_factory(); c.login("med_l1", "senha123")
    st, d = c.post("/api/orcamentos/%d/negociacao-preview" % seed["orcamento_l1_id"], {})
    assert st == 403, (st, d)                     # _bloqueio_comercial reativado


def test_consultor_sem_funcao_segue_comercial(app_db, seed, http_client_factory):
    c = http_client_factory(); c.login("cons_l1", "senha123")
    st, d = c.get("/api/agenda?de=2026-01-01&ate=2027-12-31")
    assert st == 200 and d["ok"]
    assert d["visao"] == "comercial"
