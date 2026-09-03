# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-46/47 — a tela de Funções passa a permitir marcar os
papéis do Mapa de Atribuições (`Funcao.atribuicoes_json`, campo morto até esta rodada). DECIDIDO
02/09: sem papel avulso no funcionário — os papéis vêm da função.

Backfill: as funções PADRÃO que já correspondem a um papel (Projetista Executivo, Medidor,
Montador, Supervisor de Montagem) nascem/ganham o papel automaticamente; só toca função com
atribuicoes_json vazio — nunca sobrescreve o que o cadastro já editou."""
import json

import database
import mod_cadastro
import mod_escopo


class _F:
    def __init__(self, nome="", atribuicoes_json=None):
        self.id = 1; self.loja_id = 1; self.nome = nome; self.status = "ativo"
        self.perfil_padrao = None; self.descricao = None
        self.atribuicoes_json = atribuicoes_json


def test_serialize_expoe_papeis_declarados():
    f = _F(nome="Projetista", atribuicoes_json=json.dumps(["projeto_executivo"]))
    d = mod_cadastro.funcao_serialize(f)
    assert d["papeis"] == ["projeto_executivo"]


def test_serialize_sem_atribuicoes_json_devolve_lista_vazia():
    f = _F(nome="SAC")
    d = mod_cadastro.funcao_serialize(f)
    assert d["papeis"] == []


def test_aplicar_grava_so_papeis_validos():
    f = _F()
    mod_cadastro.funcao_aplicar(None, f, {"nome": "Projetista",
                                          "papeis": ["projeto_executivo", "papel_inventado"]}, loja_id=1)
    assert json.loads(f.atribuicoes_json) == ["projeto_executivo"], (
        "papel fora de mod_escopo.PAPEIS nunca pode entrar")


def test_aplicar_lista_vazia_limpa_o_campo():
    f = _F(atribuicoes_json=json.dumps(["montagem"]))
    mod_cadastro.funcao_aplicar(None, f, {"papeis": []}, loja_id=1)
    assert f.atribuicoes_json is None


def test_backfill_papeis_funcoes_padrao_preenche_so_as_correspondentes(app_db, seed):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    proj = app_db.Funcao(loja_id=loja, nome="Projetista Executivo")
    med = app_db.Funcao(loja_id=loja, nome="Medidor")
    sac = app_db.Funcao(loja_id=loja, nome="SAC")   # não corresponde a papel nenhum
    ja_setado = app_db.Funcao(loja_id=loja, nome="Montador", atribuicoes_json=json.dumps(["projeto_executivo"]))
    db.add_all([proj, med, sac, ja_setado]); db.commit()
    ids = (proj.id, med.id, sac.id, ja_setado.id)
    db.close()

    db2 = app_db.get_session()
    n = database.backfill_papeis_funcoes_padrao(db2)
    assert n >= 2   # pelo menos Projetista Executivo e Medidor desta rodada

    proj2, med2, sac2, ja2 = [db2.get(app_db.Funcao, i) for i in ids]
    assert json.loads(proj2.atribuicoes_json) == ["projeto_executivo"]
    assert json.loads(med2.atribuicoes_json) == ["medicao"]
    assert sac2.atribuicoes_json is None, "SAC não corresponde a papel nenhum — não é tocado"
    assert json.loads(ja2.atribuicoes_json) == ["projeto_executivo"], (
        "função que o cadastro já editou (Montador com papel custom) NUNCA é sobrescrita")

    for i in ids:
        db2.delete(db2.get(app_db.Funcao, i))
    db2.commit(); db2.close()


def test_mod_assistencias_reaproveita_papel_montagem_do_mod_escopo():
    import mod_assistencias
    assert mod_assistencias.FUNCOES_ELEGIVEIS == mod_escopo.PAPEL_FUNCOES["montagem"]
    assert mod_assistencias.funcao_elegivel_assistencia("Projetista", ["montagem"]) is True
    assert mod_assistencias.funcao_elegivel_assistencia("Montador", None) is True
    assert mod_assistencias.funcao_elegivel_assistencia("Projetista", None) is False
