# -*- coding: utf-8 -*-
"""Chat do Orizon — Fatia 2 (Responsabilidade + transferência), spec seção 6 (v12).

Contratos desta fatia: mensagem `natureza=transferencia` grava DIRETO em
`CicloEtapa.responsavel_funcionario_id` (o MESMO campo do override manual do v12 — nada de
estado paralelo); defaults automáticos por FAIXA estendem o `_ETAPA_PAPEL` (Vendas via
Briefing.consultor_id + ponte Usuário↔Funcionário; Financeiro/Logística via Função); SAC
resolve à parte por Função, sem etapa; e **bloqueador=True SÓ grava o flag** — o gate real
em `pode_avancar()` é a Fatia 3 (teste de regressão aqui prova que nada travou)."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _mk_func(db, app_db, loja_id, nome_funcao, nome_pessoa):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome=nome_funcao).first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome=nome_funcao)
        db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=nome_pessoa, funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    return f


def _mk_etapa(db, app_db, nome, codigo, status="pendente"):
    e = db.query(app_db.CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo=codigo).first()
    if e is None:
        e = app_db.CicloEtapa(projeto_nome=nome, etapa_codigo=codigo, status=status)
        db.add(e); db.flush()
    else:
        e.status = status
    return e


# ── transferência oficial escreve no v12 ─────────────────────────────────────

def test_transferencia_grava_no_v12_e_ciclo_reflete(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "8")
    f = _mk_func(db, app_db, seed["loja1_id"], "Gerente de Vendas", "Fulano Transferido")
    db.commit(); fid = f.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "passa a bola", "natureza": "transferencia",
                       "etapa_codigo": "8", "transferido_para_funcionario_id": fid,
                       "bloqueador": False})
    assert st == 201 and body["ok"], body
    m = body["mensagem"]
    assert m["natureza"] == "transferencia" and m["etapa_codigo"] == "8"
    assert m["transferido_para_funcionario_id"] == fid
    assert m["transferido_para_nome"] == "Fulano Transferido"

    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="8").first()
    assert et.responsavel_funcionario_id == fid          # v12: MESMO campo do override manual
    db.close()

    st, body = c.get("/api/projetos/Proj_L1/ciclo")
    e8 = next(e for e in body["ciclo"] if e["etapa_codigo"] == "8")
    assert e8["responsavel_efetivo_id"] == fid           # precedência 1: transferência vence
    assert e8["responsavel_efetivo_nome"] == "Fulano Transferido"


def test_transferencia_validacoes(http_client_factory, seed, app_db):
    db = app_db.get_session()
    f = _mk_func(db, app_db, seed["loja1_id"], "Conferente", "Pessoa L1")
    f2 = _mk_func(db, app_db, seed["loja2_id"], "Conferente", "Pessoa L2")
    db.commit(); fid, fid_l2 = f.id, f2.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    # transferência sem destinatário
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "transferencia"})
    assert st == 400, body
    # etapa que não existe no ciclo do projeto
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "transferencia", "etapa_codigo": "99",
                       "transferido_para_funcionario_id": fid})
    assert st == 400 and "não existe" in (body.get("erro") or ""), body
    # destinatário de OUTRA loja
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "transferencia",
                       "transferido_para_funcionario_id": fid_l2})
    assert st == 400, body
    # interação NÃO aceita campos de transferência
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "interacao",
                       "transferido_para_funcionario_id": fid})
    assert st == 400, body
    # natureza desconhecida
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "delegacao"})
    assert st == 400, body


def test_transferencia_sem_etapa_nao_toca_ciclo(http_client_factory, seed, app_db):
    """Transferência sem etapa_codigo é válida (ex.: assunto fora do ciclo) — registra a
    mensagem mas não escreve em CicloEtapa nenhum."""
    db = app_db.get_session()
    f = _mk_func(db, app_db, seed["loja1_id"], "Montador", "Sem Etapa")
    antes = {e.etapa_codigo: e.responsavel_funcionario_id
             for e in db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1").all()}
    db.commit(); fid = f.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "x", "natureza": "transferencia",
                       "transferido_para_funcionario_id": fid})
    assert st == 201, body
    db = app_db.get_session()
    depois = {e.etapa_codigo: e.responsavel_funcionario_id
              for e in db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1").all()}
    assert depois == antes
    db.close()


# ── bloqueador: SÓ flag nesta fatia (gate real = Fatia 3) ────────────────────

def test_bloqueador_grava_flag_e_nao_trava_pode_avancar(http_client_factory, seed, app_db):
    import mod_ciclo
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "2", status="concluido")
    _mk_etapa(db, app_db, "Proj_L1", "3", status="pendente")
    f = _mk_func(db, app_db, seed["loja1_id"], "Medidor", "Bloqueador Humano")
    db.commit(); fid = f.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/conversa/mensagens",
                      {"corpo": "trava tudo", "natureza": "transferencia", "etapa_codigo": "3",
                       "transferido_para_funcionario_id": fid, "bloqueador": True})
    assert st == 201 and body["mensagem"]["bloqueador"] is True, body
    assert body["mensagem"]["resolvido_em"] is None
    # REGRESSÃO (contrato da Fatia 2): pode_avancar NÃO conhece o bloqueador — comportamento
    # idêntico ao de antes, com e sem mensagem bloqueadora gravada.
    assert mod_ciclo.pode_avancar("3", {"2": "concluido"}) is True
    assert mod_ciclo.pode_avancar("3", {"2": "pendente"}) is False
    assert mod_ciclo.pode_avancar("11a", {}) is mod_ciclo.pode_avancar("11", {})


# ── defaults automáticos por faixa (extensão do _ETAPA_PAPEL) ────────────────

def test_default_vendas_via_consultor_com_ponte(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "4")   # etapa de VENDAS não tocada pelos outros testes
    f_cons = _mk_func(db, app_db, seed["loja1_id"], "Consultor de Vendas", "Consultor Pessoa")
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    u.funcionario_id = f_cons.id                       # ponte Usuário↔Funcionário
    from datetime import datetime as _dt
    db.add(app_db.Briefing(cliente_id=seed["cliente_l1_id"], projeto_nome="Proj_L1",
                           data_atendimento=_dt(2026, 1, 1), tipo_imovel="apartamento",
                           budget_declarado=1.0, categoria_proposta="completo",
                           data_entrega_desejada="2026-12-01", flexibilidade_prazo="sim",
                           consultor_id=u.id))
    db.commit(); fid = f_cons.id; uid = u.id; db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/projetos/Proj_L1/ciclo")
    e4 = next(e for e in body["ciclo"] if e["etapa_codigo"] == "4")
    assert e4["responsavel_efetivo_id"] == fid
    assert e4["responsavel_efetivo_nome"] == "Consultor Pessoa"

    # consultor SEM Funcionário vinculado → etapa fica sem default (não é erro)
    db = app_db.get_session()
    db.query(app_db.Usuario).filter_by(id=uid).first().funcionario_id = None
    db.commit(); db.close()
    st, body = c.get("/api/projetos/Proj_L1/ciclo")
    e4 = next(e for e in body["ciclo"] if e["etapa_codigo"] == "4")
    assert e4["responsavel_efetivo_id"] is None


def test_default_financeiro_logistica_por_funcao_e_precedencia(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L2", "8")
    _mk_etapa(db, app_db, "Proj_L2", "12")
    gf = _mk_func(db, app_db, seed["loja2_id"], "Gerente Administrativo/Financeiro", "Fin da Loja")
    al = _mk_func(db, app_db, seed["loja2_id"], "Assistente Logístico", "Log da Loja")
    outro = _mk_func(db, app_db, seed["loja2_id"], "Conferente", "Override Manual")
    db.commit(); gfid, alid, outro_id = gf.id, al.id, outro.id; db.close()

    c = _login(http_client_factory, "dir_l2")
    st, body = c.get("/api/projetos/Proj_L2/ciclo")
    por_cod = {e["etapa_codigo"]: e for e in body["ciclo"]}
    assert por_cod["8"]["responsavel_efetivo_id"] == gfid       # Função GAF → default etapa 8
    assert por_cod["12"]["responsavel_efetivo_id"] == alid      # Função Assist. Log. → etapa 12

    # precedência: responsavel_funcionario_id manual/transferido VENCE o default por função
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L2", etapa_codigo="8").first()
    et.responsavel_funcionario_id = outro_id
    db.commit(); db.close()
    st, body = c.get("/api/projetos/Proj_L2/ciclo")
    e8 = next(e for e in body["ciclo"] if e["etapa_codigo"] == "8")
    assert e8["responsavel_efetivo_id"] == outro_id


# ── SAC fora do v12 ──────────────────────────────────────────────────────────

def test_responsavel_sac_por_funcao(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    assert mod_chat.responsavel_sac(db, seed["loja1_id"]) is None   # sem Função SAC → None
    f = _mk_func(db, app_db, seed["loja1_id"], "SAC", "Pessoa do SAC")
    db.commit()
    assert mod_chat.responsavel_sac(db, seed["loja1_id"]) == f.id
    assert mod_chat.responsavel_sac(db, seed["loja2_id"]) is None   # escopado por loja
    db.close()
