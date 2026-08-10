"""mod_simulador_dados — adapter Orizon do Simulador (Sessão 185, D3): monta o ModeloLoja a
partir das fontes reais (config financeira, folha, plano de contas). Compara o que o adapter
levanta com o que foi semeado direto no banco."""
import itertools
import json
from datetime import datetime, timedelta

import mod_contabil as mc
import mod_simulador_dados as msd

_SEQ = itertools.count(1)


def _mes_fechado_str():
    ref = datetime.utcnow()
    primeiro_atual = ref.replace(day=1)
    return (primeiro_atual - timedelta(days=1)).strftime("%Y-%m")


def _loja_com_dados(app_db, competencia=None):
    db = app_db.get_session()
    loja = app_db.Loja(nome="Loja Simulador Teste")   # sem `codigo` (unique) — chamada várias vezes por arquivo
    db.add(loja); db.flush()

    cfg = {
        "provisoes": {"frete_fab_pct": 10.0, "com_adm_pct": 2.0, "com_med_pct": 0.0,
                     "com_proj_exec_pct": 0.0, "frete_loc_pct": 0.0, "assist_pct": 0.0,
                     "ins_loc_pct": 0.0},
        "provisoes_contabeis": {"montagem_pct": 1.0, "garantia_pct": 0.5, "comissao_pct": 0.0},
        "comissao_vendas": {"meta_mensal": 50000.0,
                            "faixas_comissao": [{"venda_ate": None, "pct": 3.0}],
                            "limitador_desconto": {"ativo": False, "limites": []}},
        "defaults_negociacao": {"carga_trib_pct": 8.0, "comissao_arq_pct": 0.0, "fidelidade_pct": 0.0},
        "juros_mensal": 500.0,
        "amortizacoes": [{"nome": "Reforma Teste", "valor": 12000.0, "prazo_meses": 12}],
    }
    loja.config_financeira_json = json.dumps(cfg)
    db.flush()

    mc.seed_plano(db, "loja", loja.id)

    funcao = app_db.Funcao(loja_id=loja.id, nome="Consultor de Vendas", status="ativo",
                           salario_fixo=2000.0, usa_comissao_vendas=1)
    db.add(funcao); db.flush()

    usuario = app_db.Usuario(nome="Consultora Teste", login="sim_cons_teste_%d" % next(_SEQ),
                             nivel="operador", loja_id=loja.id, ativo=1)
    usuario.set_senha("senha123")
    db.add(usuario); db.flush()

    func = app_db.Funcionario(loja_id=loja.id, nome="Consultora Teste", funcao_id=funcao.id,
                              usuario_id=usuario.id, status="ativo")
    db.add(func); db.flush()

    comp = competencia or _mes_fechado_str()
    ano, mes = comp.split("-")
    status_at = datetime(int(ano), int(mes), 15)
    proj = app_db.Projeto(nome_safe="Proj_Sim_%s" % loja.id, status="fechado", status_at=status_at,
                          loja_id=loja.id, criado_por_id=usuario.id)
    db.add(proj); db.flush()
    orc = app_db.Orcamento(projeto_id=proj.nome_safe, nome="Orçamento 1", ordem=1, loja_id=loja.id,
                           valor_liquido=50000.0, val_liq=50000.0, cfo=20000.0, markup=2.5)
    db.add(orc); db.flush()

    db.commit()
    loja_id = loja.id
    db.close()
    return loja_id


def test_modelo_de_loja_vazia_nao_quebra(app_db, seed):
    db = app_db.get_session()
    loja = app_db.Loja(nome="Loja Vazia Sim", codigo="SVZ")
    db.add(loja); db.flush(); db.commit()
    modelo = msd.montar_modelo(db, loja)
    db.close()
    assert modelo["vendedores"] == []
    assert modelo["folha"] == []
    assert modelo["divida"] == 0.0
    assert len(modelo["variaveis"]) == 9   # 7 provisões + montagem/garantia (RF-17)


def test_modelo_traz_vendedor_com_venda_real_do_mes_fechado(app_db, seed):
    loja_id = _loja_com_dados(app_db)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    modelo = msd.montar_modelo(db, loja, cenario="atual", janela="mes")
    db.close()
    assert len(modelo["vendedores"]) == 1
    v = modelo["vendedores"][0]
    assert v["nome"] == "Consultora Teste"
    assert v["atual"] == 50000.0
    assert v["meta"] == 50000.0
    assert v["ativo"] is True


def test_modelo_folha_liga_o_colaborador_ao_indice_do_vendedor(app_db, seed):
    loja_id = _loja_com_dados(app_db)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    modelo = msd.montar_modelo(db, loja)
    db.close()
    colab = next(c for c in modelo["folha"] if c["nome"] == "Consultora Teste")
    assert colab["comissionamento"] == "faixa_vendedor"
    assert colab["vendedor_idx"] == 0
    assert colab["salario_fixo"] == 2000.0


def test_modelo_variaveis_refletem_config_financeira(app_db, seed):
    loja_id = _loja_com_dados(app_db)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    modelo = msd.montar_modelo(db, loja)
    db.close()
    por_chave = {v["chave"]: v["pct"] for v in modelo["variaveis"]}
    assert por_chave["frete_fab_pct"] == 10.0
    assert por_chave["com_adm_pct"] == 2.0
    assert por_chave["montagem_pct"] == 1.0
    assert por_chave["garantia_pct"] == 0.5


def test_modelo_amortizacoes_juros_impostos_da_config(app_db, seed):
    loja_id = _loja_com_dados(app_db)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    modelo = msd.montar_modelo(db, loja)
    db.close()
    assert modelo["juros"] == 500.0
    assert modelo["impostos_pct"] == 8.0
    assert modelo["amortizacoes"] == [{"nome": "Reforma Teste", "valor": 12000.0, "prazo_meses": 12}]


def test_modelo_custos_fixos_traz_o_plano_padrao_mesmo_sem_lancamento(app_db, seed):
    loja_id = _loja_com_dados(app_db)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    modelo = msd.montar_modelo(db, loja)
    db.close()
    assert len(modelo["custos_fixos"]) > 0
    assert all(c["valor"] == 0.0 for c in modelo["custos_fixos"])   # nenhum lançamento feito


def test_faixas_consultor_vem_da_comissao_vendas_da_loja(app_db, seed):
    loja_id = _loja_com_dados(app_db)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    modelo = msd.montar_modelo(db, loja)
    db.close()
    assert modelo["faixas_consultor"] == [[None, 3.0, None]]


# ── Endpoints (F3) ────────────────────────────────────────────────────────────────────────────
def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_endpoint_modelo_exige_acesso_simulador(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/simulador/modelo?loja_id=%d" % seed["loja1_id"])
    assert st == 403, body


def test_endpoint_modelo_exige_autorizacao_ativa_da_loja(http_client_factory, app_db, seed):
    from database import get_session, SimuladorAutorizacao
    loja_id = _loja_com_dados(app_db)   # loja nova — sem seed de autorização, sem passar pelo boot
    db = get_session()
    try:
        assert db.query(SimuladorAutorizacao).filter_by(loja_id=loja_id).first() is None
    finally:
        db.close()
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/simulador/modelo?loja_id=%d" % loja_id)
    assert st == 403 and "autoriza" in body["erro"].lower(), body


def test_endpoint_modelo_e_simular_fluxo_completo(http_client_factory, app_db, seed):
    from database import get_session
    loja_id = _loja_com_dados(app_db)
    db = get_session()
    try:
        from database import SimuladorAutorizacao
        db.add(SimuladorAutorizacao(loja_id=loja_id, status="ativa", beneficiario="orizon_assessoria",
                                    escopo="simulacao_leitura", base_legal="teste"))
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "super")
    st, body = c.get("/api/simulador/modelo?loja_id=%d&cenario=atual&janela=mes" % loja_id)
    assert st == 200 and body["ok"], body
    modelo = body["modelo"]
    assert len(modelo["vendedores"]) == 1

    st, body = c.post("/api/simulador/simular",
                      {"loja_id": loja_id, "modelo": modelo, "ajustes": {"cenario": "atual"}})
    assert st == 200 and body["ok"], body
    assert body["resultado"]["vendas"]["faturamento"] == 50000.0

    # travar e desligar o único vendedor: sem ativos, trava não redistribui nada — fat cai a 0
    st, body = c.post("/api/simulador/simular", {"loja_id": loja_id, "modelo": modelo,
        "ajustes": {"cenario": "atual", "trava": True, "vendedores_ativos": {"0": False}}})
    assert st == 200 and body["resultado"]["vendas"]["faturamento"] == 0.0


def test_endpoint_simular_reconfere_autorizacao_a_cada_chamada(http_client_factory, app_db, seed):
    """Achado da Vera: revogar (RF-03 'efeito imediato') precisa bloquear /simular também, não
    só /modelo — senão uma aba já aberta continua recalculando o dado sensível à vontade."""
    from database import get_session, SimuladorAutorizacao
    loja_id = _loja_com_dados(app_db)
    db = get_session()
    try:
        db.add(SimuladorAutorizacao(loja_id=loja_id, status="ativa", beneficiario="orizon_assessoria",
                                    escopo="simulacao_leitura", base_legal="teste"))
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "super")
    st, body = c.get("/api/simulador/modelo?loja_id=%d" % loja_id)
    modelo = body["modelo"]
    st, body = c.post("/api/simulador/simular", {"loja_id": loja_id, "modelo": modelo, "ajustes": {}})
    assert st == 200 and body["ok"], body

    db = get_session()
    try:
        ativa = db.query(SimuladorAutorizacao).filter_by(loja_id=loja_id, status="ativa").first()
        ativa.status = "revogada"
        db.commit()
    finally:
        db.close()

    # mesmo modelo já em cache no cliente — /simular tem que barrar mesmo sem tocar /modelo de novo
    st, body = c.post("/api/simulador/simular", {"loja_id": loja_id, "modelo": modelo, "ajustes": {}})
    assert st == 403, body


def test_endpoint_simular_recusa_modelo_ou_loja_id_invalidos(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.post("/api/simulador/simular", {"loja_id": seed["loja1_id"], "modelo": "nao-e-dict", "ajustes": {}})
    assert st == 400, body
    st, body = c.post("/api/simulador/simular", {"loja_id": "abc", "modelo": {}, "ajustes": {}})
    assert st == 400, body


def test_endpoint_simular_nao_grava_log_de_acesso(http_client_factory, app_db, seed):
    """RF-04 só pede log de ABERTURA/levantamento — /simular reusa dado já extraído, não some
    de novo pela loja (D1: motor puro, sem I/O)."""
    from database import get_session, SimuladorLogAcesso
    loja_id = _loja_com_dados(app_db)
    db = get_session()
    try:
        from database import SimuladorAutorizacao
        db.add(SimuladorAutorizacao(loja_id=loja_id, status="ativa", beneficiario="orizon_assessoria",
                                    escopo="simulacao_leitura", base_legal="teste"))
        db.commit()
        antes = db.query(SimuladorLogAcesso).filter_by(loja_id=loja_id).count()
    finally:
        db.close()

    c = _login(http_client_factory, "super")
    c.get("/api/simulador/modelo?loja_id=%d" % loja_id)
    db = get_session()
    try:
        depois_abertura = db.query(SimuladorLogAcesso).filter_by(loja_id=loja_id).count()
    finally:
        db.close()
    assert depois_abertura == antes + 1   # só a abertura

    c.post("/api/simulador/simular", {"loja_id": loja_id, "modelo": {}, "ajustes": {}})
    db = get_session()
    try:
        depois_simular = db.query(SimuladorLogAcesso).filter_by(loja_id=loja_id).count()
    finally:
        db.close()
    assert depois_simular == depois_abertura   # /simular não adiciona entrada
