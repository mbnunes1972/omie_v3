# -*- coding: utf-8 -*-
"""Buffer de triagem (spec _geral/2026-07-31-triagem-pipeline-entrada-design.md, revisão
2026-08-05: resolução SEMPRE automática — o painel humano de vincular/criar/descartar foi
removido).

Regra de ouro: mensagem nenhuma é descartada em silêncio — o que a automação não roteia
cai numa TriagemEntrada `pendente`, idempotente por `id_externo` (a Meta reentrega 5-6x).
Cobre os casos obrigatórios da seção 4 da spec + a materialização automática (segmento
reconhecido ou sweep de 2min → SEGMENTO_TRIAGEM, SAC como responsável inicial)."""
import json

import pytest


def _mk_func(db, app_db, loja_id, nome_funcao, nome_pessoa, com_login=None):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome=nome_funcao).first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome=nome_funcao)
        db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=nome_pessoa, funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    if com_login:
        u = app_db.Usuario(nome=nome_pessoa, login=com_login, nivel="operador",
                           loja_id=loja_id, ativo=1)
        u.set_senha("senha123")
        db.add(u); db.flush()
        f.usuario_id = u.id; db.flush()
    return f


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


@pytest.fixture(scope="module", autouse=True)
def numero_da_loja1(app_db, seed):
    """Fiel à produção: a loja operante tem NumeroConectado configurado — é ele que ancora a
    loja das entradas de número DESCONHECIDO (fallback do _loja_da_entrada)."""
    db = app_db.get_session()
    db.add(app_db.NumeroConectado(loja_id=seed["loja1_id"], numero="+55 12 90000-0000"))
    db.commit(); db.close()


def _conversa_com_saida(db, app_db, loja_id, projeto, cliente_id, numero):
    """Conversa de projeto com um EnvioExterno de SAÍDA para `numero` (habilita o roteamento)."""
    import mod_chat, mod_chat_externo as ext
    conv = mod_chat.get_or_create_conversa_projeto(db, loja_id, projeto); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "saida", canal="comercial", _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", cliente_id, numero)
    db.commit()
    return conv


# ── 1. primeiro contato nunca visto → fila persistida ────────────────────────

def test_primeiro_contato_persiste_na_fila(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    res = ext.processar_entrada(db, "whatsapp", remetente="(11) 97777-0001",
                                texto="olá, quero um orçamento", id_externo="wamid.NOVO1")
    db.commit()
    assert res["status"] == "triagem" and res.get("triagem_id")
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    assert ent is not None and ent.status == "pendente"
    assert ent.texto == "olá, quero um orçamento"
    assert ent.id_externo == "wamid.NOVO1"
    assert ent.loja_id == seed["loja1_id"]      # fallback: primeira loja
    db.close()


# ── 2. reentrega Meta do mesmo id_externo → não duplica (fila E mensagem) ────

def test_reentrega_nao_duplica_fila(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(11) 97777-0002",
                               texto="oi", id_externo="wamid.DUP")
    db.commit()
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(11) 97777-0002",
                               texto="oi", id_externo="wamid.DUP")
    db.commit()
    assert r1["status"] == r2["status"] == "triagem"
    assert r1["triagem_id"] == r2["triagem_id"]
    n = db.query(app_db.TriagemEntrada).filter_by(id_externo="wamid.DUP").count()
    assert n == 1
    db.close()


def test_reentrega_nao_duplica_mensagem_roteada(app_db, seed):
    import mod_chat_externo as ext
    from database import ConversaMensagem
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                               seed["cliente_l1_id"], "(12) 90000-1111")
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-1111",
                               texto="resposta", id_externo="wamid.RESP")
    db.commit()
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-1111",
                               texto="resposta", id_externo="wamid.RESP")
    db.commit()
    assert r1["status"] == r2["status"] == "roteado"
    assert r1["conversa_id"] == r2["conversa_id"] == conv.id
    n = (db.query(ConversaMensagem)
           .filter_by(conversa_id=conv.id, corpo="resposta").count())
    assert n == 1                                   # a reentrega não duplicou a mensagem
    db.close()


# ── 3. ambíguo (2+ conversas) → fila com os candidatos preservados ───────────

def test_ambiguo_preserva_candidatos(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    c1 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                             seed["cliente_l1_id"], "(12) 90000-3333")
    c2 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_Ambiguo",
                             seed["cliente_l1_id"], "(12) 90000-3333")
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-3333",
                                texto="sobre meu projeto", id_externo="wamid.AMB")
    db.commit()
    assert res["status"] == "triagem"
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    cand = set(json.loads(ent.candidatos_json))
    assert cand == {c1.id, c2.id}                   # a lista que o código calculou não se perde
    db.close()


# ── 4. reply citando envio antigo → roteia determinístico (não cai na fila) ──

def test_reply_citado_roteia_mesmo_com_ambiguidade(app_db, seed):
    import mod_chat, mod_chat_externo as ext
    db = app_db.get_session()
    c1 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                             seed["cliente_l1_id"], "(12) 90000-4444")
    _c2 = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_Outro",
                              seed["cliente_l1_id"], "(12) 90000-4444")
    env = (db.query(app_db.EnvioExterno)
             .join(app_db.ConversaMensagem,
                   app_db.EnvioExterno.mensagem_id == app_db.ConversaMensagem.id)
             .filter(app_db.ConversaMensagem.conversa_id == c1.id).first())
    env.id_externo = "wamid.ANTIGA"; db.commit()
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-4444",
                                texto="sobre aquilo", id_externo="wamid.R1",
                                id_externo_ref="wamid.ANTIGA")
    db.commit()
    assert res["status"] == "roteado" and res["conversa_id"] == c1.id
    db.close()


# ── 5. fora da janela de 24h ainda roteia (janela restringe RESPOSTA, não entrada) ─

def test_fora_da_janela_ainda_roteia(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                               seed["cliente_l1_id"], "(12) 90000-5555")
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-5555",
                                texto="voltei depois de dias", id_externo="wamid.TARDE")
    db.commit()
    assert res["status"] == "roteado" and res["conversa_id"] == conv.id
    db.close()


# ── 6. funcionário que também é cliente: a ponte do funcionário VENCE ────────

def test_funcionario_vence_fluxo_de_cliente(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.whatsapp = "(12) 96666-0001"
    cli = db.get(app_db.Cliente, seed["cliente_l1_id"])
    cli.whatsapp = "(12) 96666-0001"                # mesmo número nos dois cadastros
    db.commit()
    res = ext.processar_entrada_usuario(db, "(12) 96666-0001", "oi da ponte")
    assert res is not None                          # ponte reconhece → cliente nem é tentado
    db.close()


# ── 7. projeto concluído não reabre sozinho → cai na fila com candidato ──────

def test_projeto_concluido_cai_na_fila(app_db, seed):
    import mod_chat_externo as ext
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_L1",
                               seed["cliente_l1_id"], "(12) 90000-7777")
    proj = db.query(app_db.Projeto).filter_by(nome_safe="Proj_L1").first()
    proj.status = "concluido"; db.commit()
    res = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-7777",
                                texto="tenho um problema no móvel", id_externo="wamid.POS")
    db.commit()
    assert res["status"] == "triagem"               # decisão humana, não reabertura silenciosa
    ent = db.get(app_db.TriagemEntrada, res["triagem_id"])
    assert conv.id in set(json.loads(ent.candidatos_json))
    proj.status = "quente"; db.commit()             # seed é module-scoped — restaura p/ os demais
    db.close()


# ── resolução automática (2026-08-05): materializa na hora, SAC como responsável ─────────

def test_segmento_reconhecido_materializa_com_sac_responsavel(app_db, seed):
    """Resposta reconhecida no menu → conversa nasce JÁ com esse segmento (não mais
    'segmento_sugerido' esperando humano); SAC (se configurado) vira responsável/criador."""
    import mod_chat_externo as ext
    from database import Conversa, ConversaMensagem
    db = app_db.get_session()
    sac = _mk_func(db, app_db, seed["loja1_id"], "SAC", "Pessoa do SAC", com_login="sac_l1")
    db.commit()
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(11) 95555-0001",
                               texto="quero móveis planejados", id_externo="wamid.LEAD1")
    db.commit()
    assert r1["status"] == "triagem" and r1["triagem_id"]
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(11) 95555-0001",
                               texto="1", id_externo="wamid.LEAD2")   # "1" = comercial
    db.commit()
    assert r2["status"] == "roteado" and r2["conversa_id"]
    ent = db.get(app_db.TriagemEntrada, r1["triagem_id"])
    assert ent.status == "resolvido" and ent.conversa_id == r2["conversa_id"]
    conv = db.get(Conversa, r2["conversa_id"])
    assert conv.segmento == "comercial"
    assert conv.responsavel_usuario_id == sac.usuario_id
    assert conv.origem_entrada == "triagem"
    cli = db.query(app_db.Cliente).filter_by(loja_id=seed["loja1_id"]).filter(
        app_db.Cliente.whatsapp.contains("955550001")).first()
    assert cli is not None                            # lead virou Cliente (decisão 12)
    ext_part = (db.query(app_db.ConversaParticipanteExterno)
                  .filter_by(conversa_id=conv.id).first())
    assert ext_part is not None                        # contato espelha por WhatsApp
    corpos = [m.corpo for m in db.query(ConversaMensagem)
              .filter_by(conversa_id=conv.id).order_by(ConversaMensagem.id).all()]
    assert "quero móveis planejados" in corpos          # texto original entrou na conversa
    # próxima mensagem do número roteia sozinha pra conversa já materializada
    r3 = ext.processar_entrada(db, "whatsapp", remetente="(11) 95555-0001",
                               texto="e o prazo?", id_externo="wamid.LEAD3")
    db.commit()
    assert r3["status"] == "roteado" and r3["conversa_id"] == conv.id
    db.close()


def test_sem_sac_configurado_materializa_sem_responsavel(app_db, seed):
    """Loja sem ninguém na Função 'SAC' (loja 2 — a 1 ganha SAC no teste anterior, `seed` é
    module-scoped): a conversa nasce mesmo assim (sem travar), só sem responsável/criador —
    visível via Oversight até alguém assumir."""
    import mod_chat_externo as ext
    from database import Conversa
    db = app_db.get_session()
    # âncora a entrada na loja 2 por Cliente já cadastrado (mais específico que o fallback de
    # NumeroConectado/1ª loja — ver _loja_da_entrada) sem depender de haver só 1 NumeroConectado
    db.add(app_db.Cliente(nome="Cliente Loja 2 Novo", loja_id=seed["loja2_id"],
                          whatsapp="(31) 95555-0099"))
    db.commit()
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(31) 95555-0099",
                               texto="oi", id_externo="wamid.NOSAC1")
    db.commit()
    assert db.get(app_db.TriagemEntrada, r1["triagem_id"]).loja_id == seed["loja2_id"]
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(31) 95555-0099",
                               texto="1", id_externo="wamid.NOSAC2")
    db.commit()
    assert r2["status"] == "roteado"
    conv = db.get(Conversa, r2["conversa_id"])
    assert conv.segmento == "comercial"
    assert conv.responsavel_usuario_id is None and conv.criado_por_id is None
    db.close()


def test_sweep_materializa_com_segmento_triagem_apos_2min(app_db, seed):
    """Sem resposta reconhecida (ninguém respondeu, ou número ambíguo) → depois de 2min o
    sweep preguiçoso materializa com o selo 'triagem' (SAC distribui)."""
    import datetime as _dt
    import mod_chat_externo as ext
    from chat import triagem as tri
    from database import Conversa
    db = app_db.get_session()
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(11) 92222-0001",
                               texto="alô?", id_externo="wamid.SWEEP1")
    db.commit()
    ent = db.get(app_db.TriagemEntrada, r1["triagem_id"])
    ent.criado_em = _dt.datetime.utcnow() - _dt.timedelta(minutes=3)
    db.commit()
    # antes do sweep, ninguém carregou o inbox ainda: segue pendente
    ainda = db.get(app_db.TriagemEntrada, ent.id)
    assert ainda.status == "pendente"
    tri.varrer_triagem_vencida(db, seed["loja1_id"])
    db.commit()
    ent2 = db.get(app_db.TriagemEntrada, ent.id)
    assert ent2.status == "resolvido" and ent2.conversa_id is not None
    conv = db.get(Conversa, ent2.conversa_id)
    assert conv.segmento == tri.SEGMENTO_TRIAGEM
    db.close()


def test_sweep_ignora_entrada_recente(app_db, seed):
    import mod_chat_externo as ext
    from chat import triagem as tri
    db = app_db.get_session()
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(11) 92222-0002",
                               texto="alô?", id_externo="wamid.RECENTE1")
    db.commit()
    tri.varrer_triagem_vencida(db, seed["loja1_id"])
    db.commit()
    ent = db.get(app_db.TriagemEntrada, r1["triagem_id"])
    assert ent.status == "pendente"                     # ainda dentro dos 2min, não venceu
    db.close()


def test_nome_do_lead_prioriza_cadastro_sobre_meta(app_db, seed):
    """Nome do lead: Cliente já cadastrado com esse telefone > perfil do WhatsApp (Meta) >
    o próprio remetente, nessa ordem (pedido 2026-08-05)."""
    import mod_chat_externo as ext
    from database import Conversa
    db = app_db.get_session()
    cli = app_db.Cliente(nome="Fulano do Cadastro", loja_id=seed["loja1_id"],
                         whatsapp="(11) 91111-2222")
    db.add(cli); db.commit()
    r1 = ext.processar_entrada(db, "whatsapp", remetente="(11) 91111-2222",
                               texto="oi", id_externo="wamid.NOME1", nome="Nome da Meta")
    db.commit()
    r2 = ext.processar_entrada(db, "whatsapp", remetente="(11) 91111-2222",
                               texto="1", id_externo="wamid.NOME2")
    db.commit()
    conv = db.get(Conversa, r2["conversa_id"])
    assert "Fulano do Cadastro" in (conv.titulo or "")   # cadastro vence o perfil da Meta
    db.close()
