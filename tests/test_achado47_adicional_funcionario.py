# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-47 — bloco Adicional no cadastro do funcionário
(DECIDIDO 02/09): sem papel avulso — o acúmulo de papéis (ex.: a mesma pessoa faz Projeto
Executivo E Medição) se paga por Adicional, não por uma 2ª função.

- adicional_fixo: livre, soma na parte fixa da Folha.
- adicional_comissao_pct: só quando a função PRIMÁRIA já é comissionada (guarda NO SERVIDOR,
  `mod_folha.funcao_e_comissionada`) — soma sobre o % já existente e PROVISIONA JUNTO, no MESMO
  item/alimentador (`mod_comissao.preparar_comissao_etapa`), sem rubrica/alimentador/veredito
  novo. Base declarada: só 'val_liq_venda' suportada por ora.
- adicional_obs: um só campo, serve aos dois adicionais.
"""
import json
from datetime import datetime

import mod_cadastro
import mod_comissao
import mod_folha


def test_funcao_e_comissionada_pure():
    class _Fn:
        def __init__(self, usa=0, comissao_json=None):
            self.usa_comissao_vendas = usa; self.comissao_json = comissao_json
    assert mod_folha.funcao_e_comissionada(None) is False
    assert mod_folha.funcao_e_comissionada(_Fn(usa=1)) is True
    assert mod_folha.funcao_e_comissionada(_Fn(comissao_json=json.dumps({"por_meta": False, "pct": 3.0}))) is True
    assert mod_folha.funcao_e_comissionada(_Fn(comissao_json=json.dumps({"por_meta": False, "pct": 0}))) is False
    assert mod_folha.funcao_e_comissionada(_Fn(comissao_json=json.dumps({"por_meta": True, "faixas": []}))) is False
    assert mod_folha.funcao_e_comissionada(_Fn(comissao_json=json.dumps(
        {"por_meta": True, "faixas": [{"venda_ate": None, "pct": 2.0}]}))) is True
    assert mod_folha.funcao_e_comissionada(_Fn()) is False


def test_func_aplicar_recusa_adicional_comissao_sem_funcao_comissionada(app_db, seed):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="SAC", usa_comissao_vendas=0)   # não comissionada
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Zeca SAC", funcao_id=fn.id, status="ativo")
    db.add(f); db.commit()

    try:
        mod_cadastro.func_aplicar(db, f, {"adicional_comissao_pct": 5.0}, loja_id=loja)
        assert False, "deveria ter recusado"
    except ValueError as e:
        assert "comissionada" in str(e).lower()
    db.rollback()
    db.close()


def test_func_aplicar_aceita_adicional_comissao_com_funcao_comissionada(app_db, seed):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Projetista Executivo",
                      comissao_json=json.dumps({"por_meta": False, "pct": 3.0}))
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Ana PE", funcao_id=fn.id, status="ativo")
    db.add(f); db.commit()

    mod_cadastro.func_aplicar(db, f, {"adicional_comissao_pct": 2.0, "adicional_fixo": 300.0,
                                      "adicional_comissao_base": "val_liq_venda",
                                      "adicional_obs": "acumula Medição"}, loja_id=loja)
    db.commit()
    assert f.adicional_comissao_pct == 2.0
    assert f.adicional_fixo == 300.0
    assert f.adicional_comissao_base == "val_liq_venda"
    assert f.adicional_obs == "acumula Medição"
    db.close()


def test_func_aplicar_ignora_base_invalida():
    class _F:
        loja_id = 1; funcao_id = None
    f = _F()
    mod_cadastro.func_aplicar(None, f, {"adicional_comissao_base": "custo_fabrica"}, loja_id=1)
    assert f.adicional_comissao_base is None, "só val_liq_venda é suportada por ora"


def test_serialize_expoe_funcao_comissionada_e_adicional(app_db, seed):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Medidor", comissao_json=json.dumps({"por_meta": False, "pct": 3.0}))
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Bia Medidora", funcao_id=fn.id, status="ativo",
                           adicional_fixo=100.0, adicional_comissao_pct=1.5)
    db.add(f); db.commit()
    d = mod_cadastro.func_serialize(f, db)
    assert d["funcao_comissionada"] is True
    assert d["adicional_fixo"] == 100.0
    assert d["adicional_comissao_pct"] == 1.5
    assert d["adicional_comissao_base"] == "val_liq_venda"
    db.close()


def test_preparar_comissao_etapa_soma_adicional_no_mesmo_item(seed, app_db):
    """Aceite: o adicional soma sobre a comissão da função primária e provisiona JUNTO — mesmo
    item de ComissaoFolha, sem rubrica/alimentador novo."""
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    com = {"por_meta": False, "pct": 3.0}
    fn = app_db.Funcao(loja_id=loja, nome="Medidor", usa_comissao_vendas=0,
                       comissao_json=json.dumps(com), status="ativo")
    db.add(fn); db.flush()
    # 2% de adicional de comissão — função já comissionada (3%) — acumula Projeto Executivo
    f = app_db.Funcionario(loja_id=loja, nome="Med Acumulado", funcao_id=fn.id, status="ativo",
                           adicional_comissao_pct=2.0)
    db.add(f); db.flush()
    p = app_db.PoolAmbiente(projeto_id="PComisAdic", nome="a", nome_exibicao="Cozinha",
                            xml_path="x", ambientes_json="[]", order_total=999.0, budget_total=10000.0)
    db.add(p); db.flush()
    orc = app_db.Orcamento(projeto_id="PComisAdic", nome="O", ordem=1, loja_id=loja)
    db.add(orc); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=orc.id, pool_ambiente_id=p.id))
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PComisAdic", papel="medicao",
                                     funcionario_id=f.id, pool_ambiente_id=None))
    et = app_db.CicloEtapa(projeto_nome="PComisAdic", etapa_codigo="10", status="concluido",
                           concluido_em=datetime(2026, 7, 15), funcao_responsavel_id=fn.id,
                           responsavel_funcionario_id=f.id)
    db.add(et); db.commit()

    item = mod_comissao.preparar_comissao_etapa(db, loja, et); db.commit()
    assert item is not None
    assert item.pct == 5.0, "3% da função + 2% do adicional = 5%, mesmo item"
    assert item.valor == 500.0, "10000 (base) x 5% = 500 — mesmo alimentador, sem item extra"
    n = db.query(app_db.ComissaoFolha).filter_by(projeto_nome="PComisAdic", etapa_codigo="10").count()
    assert n == 1, "não cria item novo pro adicional — soma no MESMO item"
    db.close()


def test_calcular_folha_soma_adicional_fixo_na_parte_fixa(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Assistente", salario_fixo=2000.0)
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Ana Assist", funcao_id=fn.id, status="ativo",
                           adicional_fixo=250.0)
    db.add(f); db.commit()
    c = mod_folha.calcular_folha(db, loja, f, "2026-07", {})
    assert c["parte_fixa"] == 2250.0
    assert c["adicional_fixo"] == 250.0
    db.close()


def test_http_post_funcionarios_recusa_adicional_comissao_sem_funcao_comissionada(
        http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="SAC", usa_comissao_vendas=0)
    db.add(fn); db.commit()
    fid = fn.id
    db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "Zeca SAC", "funcao_id": fid,
                                        "adicional_comissao_pct": 5.0})
    assert st == 400 and d.get("ok") is False
    assert "comissionada" in d.get("erro", "").lower()


def test_http_post_funcionarios_aceita_adicional_com_funcao_comissionada(
        http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Projetista Executivo",
                       comissao_json=json.dumps({"por_meta": False, "pct": 3.0}))
    db.add(fn); db.commit()
    fid = fn.id
    db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/funcionarios", {"nome": "Ana PE", "funcao_id": fid,
                                        "adicional_fixo": 300.0, "adicional_comissao_pct": 2.0,
                                        "adicional_obs": "acumula Medição"})
    assert st == 201 and d.get("ok") is True, d
    item = d["item"]
    assert item["adicional_fixo"] == 300.0
    assert item["adicional_comissao_pct"] == 2.0
    assert item["adicional_obs"] == "acumula Medição"
    assert item["funcao_comissionada"] is True
