# -*- coding: utf-8 -*-
"""Chat do Orizon — Fatia 3 (Bloqueador como GATE REAL), spec seção 3.

CÓDIGO SENSÍVEL: mexe em mod_ciclo.pode_avancar (fonte única do gating, produção). Contratos:
(1) chamada SEM o parâmetro novo é IDÊNTICA ao comportamento anterior; (2) bloqueador ativo
vence tudo — nem com a anterior concluída avança; (3) '*' = bloqueador sem etapa, trava o
ciclo INTEIRO; (4) sub-etapa herda o bloqueio da mãe; (5) resolver normal é EXCLUSIVO de quem
recebeu a transferência (ponte Usuário↔Funcionário); (6) válvula de emergência = capacidade
'autorizar' (master/gerencial) + motivo obrigatório + LogAcaoGerencial."""
import json

import mod_ciclo


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


def _transferir(app_db, nome, login, fid, etapa=None, bloqueador=True, corpo="bloqueia"):
    """Achado FATIA 7 (2026-08-05): "Transferência de responsabilidade"/Bloqueador saiu do
    endpoint HTTP do Chat (decisão do usuário — o Chat é só canal de comunicação; atribuir
    responsável por etapa tem porta própria em Etapas do Projeto). `mod_ciclo.pode_avancar`/
    `bloqueadores_ativos`/`enviar_mensagem(natureza="transferencia", bloqueador=...)` continuam
    existindo por baixo (é o que esta suíte cobre) — só não são mais alcançáveis via POST no
    chat. Monta o cenário chamando mod_chat.enviar_mensagem direto, bypassando o HTTP."""
    import mod_chat
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login=login).first()
        conv = mod_chat.get_or_create_conversa_projeto(db, u.loja_id, nome)
        msg = mod_chat.enviar_mensagem(db, conv, u.id, corpo, natureza="transferencia",
                                       etapa_codigo=etapa, transferido_para_funcionario_id=fid,
                                       bloqueador=bloqueador)
        db.commit()
        return msg.id
    finally:
        db.close()


# ── unidade: pode_avancar (backward-compat + bloqueador) ─────────────────────

def test_pode_avancar_sem_parametro_e_identico_ao_anterior():
    """Contrato de regressão EXPLÍCITO: sem bloqueadores_ativos (default None), nada muda."""
    assert mod_ciclo.pode_avancar("3", {"2": "concluido"}) is True
    assert mod_ciclo.pode_avancar("3", {"2": "pendente"}) is False
    assert mod_ciclo.pode_avancar("1", {}) is True
    assert mod_ciclo.pode_avancar("11a", {"10": "concluido"}) is \
        mod_ciclo.pode_avancar("11", {"10": "concluido"})
    # set vazio ≡ None (nenhum bloqueio)
    assert mod_ciclo.pode_avancar("3", {"2": "concluido"}, bloqueadores_ativos=set()) is True


def test_pode_avancar_bloqueador_vence_mesmo_com_anterior_concluida():
    assert mod_ciclo.pode_avancar("3", {"2": "concluido"}, bloqueadores_ativos={"3"}) is False
    # bloqueador em OUTRA etapa não afeta esta
    assert mod_ciclo.pode_avancar("3", {"2": "concluido"}, bloqueadores_ativos={"8"}) is True


def test_pode_avancar_bloqueador_global_trava_tudo():
    for cod in ("1", "3", "8", "12", "21"):
        assert mod_ciclo.pode_avancar(cod, {}, bloqueadores_ativos={"*"}) is False, cod


def test_pode_avancar_subetapa_herda_bloqueio_da_mae():
    # mãe "11" bloqueada → sub "11a" não avança (propagação na recursão)
    assert mod_ciclo.pode_avancar("11a", {"10": "concluido"},
                                  bloqueadores_ativos={"11"}) is False
    # sub-etapa bloqueada DIRETO também trava
    assert mod_ciclo.pode_avancar("11a", {"10": "concluido"},
                                  bloqueadores_ativos={"11a"}) is False


# ── e2e: PATCH do ciclo respeita o bloqueador ────────────────────────────────

def test_patch_ciclo_trava_por_bloqueador_de_etapa(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "2", status="concluido")
    _mk_etapa(db, app_db, "Proj_L1", "3", status="pendente")
    f = _mk_func(db, app_db, seed["loja1_id"], "Medidor", "Destino Bloq")
    db.commit(); fid = f.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    mid = _transferir(app_db, "Proj_L1", "dir_l1", fid, etapa="3")

    st, body = c.patch("/api/projetos/Proj_L1/ciclo/3", {"status": "em_andamento"})
    assert st == 400, body
    assert body.get("codigo") == "bloqueador_ativo"
    assert "Bloqueador ativo" in body["erro"]           # mensagem DISTINTA da sequencial
    assert "Conclua a etapa anterior" not in body["erro"]
    return mid


def test_patch_ciclo_bloqueador_global_trava_qualquer_etapa(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L2", "1", status="pendente")
    f = _mk_func(db, app_db, seed["loja2_id"], "Medidor", "Destino Global")
    db.commit(); fid = f.id; db.close()
    c = _login(http_client_factory, "dir_l2")
    _transferir(app_db, "Proj_L2", "dir_l2", fid, etapa=None)          # SEM etapa → '*'
    st, body = c.patch("/api/projetos/Proj_L2/ciclo/1", {"status": "em_andamento"})
    assert st == 400 and body.get("codigo") == "bloqueador_ativo", body


def test_erro_sequencial_continua_o_de_sempre(http_client_factory, seed, app_db):
    """Sem bloqueador nenhum, a trava sequencial mantém a mensagem antiga — as duas causas
    não podem se confundir na tela."""
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "8", status="pendente")
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    # resolve qualquer bloqueador pendente do teste anterior não interfere: etapa 8 exige a 7
    st, body = c.patch("/api/projetos/Proj_L1/ciclo/8", {"status": "em_andamento"})
    assert st == 400, body
    if body.get("codigo") != "bloqueador_ativo":        # sem bloqueador global ativo no proj
        assert "Conclua a etapa anterior" in body["erro"]


# ── resolução normal (só quem recebeu) e liberação do avanço ─────────────────

def test_resolver_so_quem_recebeu_e_libera_avanco(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L2", "2", status="concluido")
    _mk_etapa(db, app_db, "Proj_L2", "3", status="pendente")
    f = _mk_func(db, app_db, seed["loja2_id"], "Conferente", "Recebedor Oficial")
    # cons_l2 não existe no seed — vincula o PRÓPRIO dir_l2 a OUTRO funcionário para o 403
    outro = _mk_func(db, app_db, seed["loja2_id"], "Montador", "Nao Recebedor")
    db.commit(); fid, outro_id = f.id, outro.id; db.close()

    c = _login(http_client_factory, "dir_l2")
    mid = _transferir(app_db, "Proj_L2", "dir_l2", fid, etapa="3")

    # dir_l2 SEM vínculo com o destinatário → 403
    st, body = c.post(f"/api/projetos/Proj_L2/conversa/mensagens/{mid}/resolver", {})
    assert st == 403, body

    # vincula dir_l2 ao funcionário ERRADO → continua 403
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="dir_l2").first()
    u.funcionario_id = outro_id
    db.commit(); uid = u.id; db.close()
    st, body = c.post(f"/api/projetos/Proj_L2/conversa/mensagens/{mid}/resolver", {})
    assert st == 403, body

    # vincula ao destinatário CERTO → resolve
    db = app_db.get_session()
    db.query(app_db.Usuario).filter_by(id=uid).first().funcionario_id = fid
    db.commit(); db.close()
    st, body = c.post(f"/api/projetos/Proj_L2/conversa/mensagens/{mid}/resolver", {})
    assert st == 200 and body["ok"], body
    assert body["mensagem"]["resolvido_em"]

    # resolver de novo → 400 (já resolvida)
    st, body = c.post(f"/api/projetos/Proj_L2/conversa/mensagens/{mid}/resolver", {})
    assert st == 400, body

    # e o avanço LIBEROU (o bloqueador global do teste anterior era em Proj_L2... resolve-o)
    db = app_db.get_session()
    pend = (db.query(app_db.ConversaMensagem)
              .join(app_db.Conversa, app_db.ConversaMensagem.conversa_id == app_db.Conversa.id)
              .filter(app_db.Conversa.projeto_nome == "Proj_L2",
                      app_db.ConversaMensagem.bloqueador != 0,
                      app_db.ConversaMensagem.resolvido_em.is_(None)).all())
    from datetime import datetime as _dt
    for p in pend:
        p.resolvido_em = _dt.utcnow()                   # limpa resíduos de outros testes
    db.commit(); db.close()
    st, body = c.patch("/api/projetos/Proj_L2/ciclo/3", {"status": "em_andamento"})
    assert st == 200 and body["ok"], body


# ── válvula de emergência ────────────────────────────────────────────────────

def test_destravar_emergencia(http_client_factory, seed, app_db):
    db = app_db.get_session()
    _mk_etapa(db, app_db, "Proj_L1", "12", status="pendente")
    f = _mk_func(db, app_db, seed["loja1_id"], "Conferente", "Recebedor Emergencia")
    db.commit(); fid = f.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    mid = _transferir(app_db, "Proj_L1", "dir_l1", fid, etapa="12")

    # sem motivo → 400
    st, body = c.post(f"/api/projetos/Proj_L1/conversa/mensagens/{mid}/destravar-emergencia",
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 400, body

    # operador (sem 'autorizar') com credencial própria → 403
    c_op = _login(http_client_factory, "cons_l1")
    st, body = c_op.post(f"/api/projetos/Proj_L1/conversa/mensagens/{mid}/destravar-emergencia",
                         {"motivo": "tentativa indevida"})
    assert st == 403, body
    # credencial inválida → 403
    st, body = c_op.post(f"/api/projetos/Proj_L1/conversa/mensagens/{mid}/destravar-emergencia",
                         {"login": "dir_l1", "senha": "errada", "motivo": "x"})
    assert st == 403, body

    # master via sessão (sessão-primeiro, sem redigitar senha) → destrava e AUDITA,
    # mesmo NÃO sendo o destinatário da transferência (objetivo da válvula)
    st, body = c.post(f"/api/projetos/Proj_L1/conversa/mensagens/{mid}/destravar-emergencia",
                      {"motivo": "cliente aguardando entrega, destravado pela gerência"})
    assert st == 200 and body["ok"], body
    assert body["mensagem"]["resolvido_em"]

    db = app_db.get_session()
    log = (db.query(app_db.LogAcaoGerencial)
             .filter_by(acao="destravar_bloqueador", projeto_nome="Proj_L1")
             .order_by(app_db.LogAcaoGerencial.id.desc()).first())
    assert log is not None and log.etapa_alvo == "12"
    ctx = json.loads(log.contexto)
    assert ctx["mensagem_id"] == mid and "gerência" in ctx["motivo"]
    db.close()
