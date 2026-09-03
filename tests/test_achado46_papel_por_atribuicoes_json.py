# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-46 — a transferência de responsabilidade procura por
NOME de função (`mod_escopo.PAPEL_FUNCOES`), e o mecanismo certo (`Funcao.atribuicoes_json`) já
existia sem uso. Quem não tivesse uma função chamada EXATAMENTE "Projetista Executivo" não
existia para o papel `projeto_executivo` — em silêncio.

Conserto: `mod_escopo.funcao_compativel(papel, funcao_nome, papeis)` passa a checar `papeis`
(Funcao.atribuicoes_json parseada) PRIMEIRO; o nome vira fallback só quando a função não declara
papel nenhum. Aceite do achado: funcionário cuja função se chama "Projetista" (não "Projetista
Executivo") mas declara o papel `projeto_executivo` aparece na transferência (POST
/api/projetos/<nome>/atribuicoes aceita, 200 — não mais 400 "função incompatível")."""
import json

import mod_escopo


def _mk_funcionario(app_db, loja, nome_funcao, papeis, nome_pessoa):
    db = app_db.get_session()
    f = app_db.Funcao(loja_id=loja, nome=nome_funcao,
                      atribuicoes_json=json.dumps(papeis) if papeis else None)
    db.add(f); db.flush()
    p = app_db.Funcionario(loja_id=loja, nome=nome_pessoa, funcao_id=f.id, status="ativo")
    db.add(p); db.commit()
    fid, pid = f.id, p.id
    db.close()
    return fid, pid


def test_pure_funcao_compativel_papel_primeiro_nome_fallback():
    # papéis declarados: decide por eles, IGNORA o nome (mesmo com nome incompatível)
    assert mod_escopo.funcao_compativel("projeto_executivo", "Projetista", ["projeto_executivo"]) is True
    assert mod_escopo.funcao_compativel("projeto_executivo", "Projetista Executivo", ["medicao"]) is False
    # sem papéis (função não migrada): cai no nome, comportamento de sempre
    assert mod_escopo.funcao_compativel("projeto_executivo", "Projetista Executivo", None) is True
    assert mod_escopo.funcao_compativel("projeto_executivo", "Projetista", None) is False
    assert mod_escopo.funcao_compativel("projeto_executivo", "Projetista", []) is False


def test_funcionario_com_nome_custom_mas_papel_declarado_aparece_na_transferencia(
        http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    # "Projetista" (não "Projetista Executivo") — o nome exato que o achado descreve
    _fid, pid = _mk_funcionario(app_db, loja, "Projetista", ["projeto_executivo"], "Cíntia Projetista")

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/Proj_L1/atribuicoes",
                   {"papel": "projeto_executivo", "pool_ambiente_id": None, "funcionario_id": pid})
    assert st == 200 and d.get("ok") is True, d
    pe = [a for a in d["atribuicoes"] if a["papel"] == "projeto_executivo" and a["pool_ambiente_id"] is None]
    assert len(pe) == 1 and pe[0]["responsavel_nome"] == "Cíntia Projetista"

    # limpa (app_db é module-scoped)
    db2 = app_db.get_session()
    db2.query(app_db.AtribuicaoAmbiente).filter_by(projeto_nome="Proj_L1").delete()
    db2.commit(); db2.close()


def test_funcionario_com_nome_custom_e_sem_papel_declarado_continua_recusado(
        http_client_factory, seed, app_db):
    """Controle: nome custom SEM papel declarado continua caindo no fallback por nome (recusa) —
    a mudança não vira um "aceita geral", só estende a fonte de verdade."""
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    _fid, pid = _mk_funcionario(app_db, loja, "Projetista", None, "Duda Projetista")

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/Proj_L1/atribuicoes",
                   {"papel": "projeto_executivo", "pool_ambiente_id": None, "funcionario_id": pid})
    assert st == 400 and d.get("ok") is False, d
