# -*- coding: utf-8 -*-
"""Acoplamento do chat ao CICLO por eventos inline (spec
_geral/2026-07-31-chat-modulo-destacavel-portas-design.md, decisões 1-5).

Grupo de acompanhamento evolutivo na transição de fase (entrada/saída de membro vira faixa na
timeline), documento do ciclo registrado como evento, encaminhamento externo gated pela janela
de 24h, e o teste que TRAVA o roteamento pós-transição (rotear casa por número, não por
funcionário)."""
import pytest


def _numero_entrada(db, app_db, conv, numero, texto="oi", wamid=None):
    """Entrada externa recente na conversa (abre a janela de 24h)."""
    import mod_chat_externo as ext
    return ext.processar_entrada(db, "whatsapp", remetente=numero, texto=texto,
                                 id_externo=wamid)


def _conversa_com_saida(db, app_db, loja_id, projeto, cliente_id, numero):
    import mod_chat, mod_chat_externo as ext
    conv = mod_chat.get_or_create_conversa_projeto(db, loja_id, projeto); db.flush()
    m = mod_chat.enviar_mensagem(db, conv, None, "saida", canal="comercial", _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", cliente_id, numero)
    db.commit()
    return conv


# ── decisão 1: grupo evolutivo com eventos inline ────────────────────────────

def test_sincronizar_grupo_da_fase_gera_eventos(app_db, seed):
    import mod_chat
    from database import ConversaMensagem
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_Fase"); db.commit()
    cons = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    mod_chat.sincronizar_grupo_da_fase(db, conv, [cons.id], fase_nome="Montagem")
    db.commit()
    evs = (db.query(ConversaMensagem)
             .filter_by(conversa_id=conv.id, evento="membro_entrou").all())
    corpos = [e.corpo for e in evs]
    assert any("Consultor L1" in c for c in corpos)          # membro derivado entrou
    assert all("fase Montagem" in c for c in corpos)         # a fase entra na faixa
    # o consultor sai do time na fase seguinte → evento de saída (gerência fica)
    mod_chat.sincronizar_grupo_da_fase(db, conv, [], fase_nome="Entrega")
    db.commit()
    ev_saida = (db.query(ConversaMensagem)
                  .filter_by(conversa_id=conv.id, evento="membro_saiu").all())
    assert any("Consultor L1" in (e.corpo or "") and "fase Entrega" in (e.corpo or "")
               for e in ev_saida)
    db.close()


def test_sincronizar_grupo_respeita_override_manual(app_db, seed):
    import mod_chat
    from database import ConversaMensagem
    db = app_db.get_session()
    conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_Override"); db.commit()
    cons = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    mod_chat.sincronizar_grupo_da_fase(db, conv, [cons.id], fase_nome="Medição"); db.commit()
    mod_chat.gerir_participante(db, conv, cons.id, "remove"); db.commit()   # auto-exclusão manual
    antes = db.query(ConversaMensagem).filter_by(conversa_id=conv.id).count()
    mod_chat.sincronizar_grupo_da_fase(db, conv, [cons.id], fase_nome="Medição"); db.commit()
    ativos = {p.usuario_id for p in db.query(app_db.ConversaParticipante)
              .filter_by(conversa_id=conv.id, removido=0).all()}
    assert cons.id not in ativos                             # override vence: não readiciona
    depois = db.query(ConversaMensagem).filter_by(conversa_id=conv.id).count()
    assert depois == antes                                   # e não gera evento fantasma
    db.close()


# ── decisão 2: documento do ciclo vira evento na conversa ────────────────────

def test_registrar_documento_gera_evento_com_ref(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    doc = app_db.CicloDocumento(projeto_nome="Proj_L1", etapa_codigo="7", tipo="contrato_assinado",
                                arquivo_path="ciclo/7/x.pdf", nome_original="contrato.pdf")
    db.add(doc); db.flush()
    m = mod_chat.registrar_documento_na_conversa(db, seed["loja1_id"], "Proj_L1", doc)
    db.commit()
    assert m.evento == "documento_registrado" and m.documento_ref_id == doc.id
    assert "contrato.pdf" in m.corpo and "etapa 7" in m.corpo
    conv_id = m.conversa_id
    msgs = mod_chat.listar_mensagens(db, conv_id)
    alvo = [x for x in msgs if x["id"] == m.id][0]
    assert alvo["evento"] == "documento_registrado"
    assert alvo["documento_nome"] == "contrato.pdf"          # o nome resolve na serialização
    db.close()


# ── decisão 5: roteamento pós-transição + janela intocada ────────────────────

def test_roteamento_pos_transicao_mesma_conversa(app_db, seed):
    import mod_chat, mod_chat_externo as ext
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_Transicao",
                               seed["cliente_l1_id"], "(12) 98888-0001")
    r1 = _numero_entrada(db, app_db, conv, "(12) 98888-0001", "primeira", "wamid.T1")
    db.commit()
    assert r1["status"] == "roteado" and r1["conversa_id"] == conv.id
    j1 = ext.janela_da_conversa(db, conv)
    assert j1["aberta"]
    # fase muda, responsável muda: transferência oficial (aditiva) + passagem automática
    cons = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    f = app_db.Funcionario(nome="Func Transicao", loja_id=seed["loja1_id"],
                           usuario_id=cons.id, status="ativo")
    db.add(f); db.flush()
    mod_chat.mensagem_passagem_fase(db, conv, None, "Medição", "11", "Projeto Executivo", f.id)
    mod_chat.sincronizar_grupo_da_fase(db, conv, [cons.id], fase_nome="Projeto Executivo")
    db.commit()
    # o cliente escreve de novo → cai na MESMA conversa, apesar da troca de responsável
    r2 = _numero_entrada(db, app_db, conv, "(12) 98888-0001", "segunda", "wamid.T2")
    db.commit()
    assert r2["status"] == "roteado" and r2["conversa_id"] == conv.id
    # e a transição NÃO mexeu na janela: a última entrada é a do cliente (wamid.T2)
    j2 = ext.janela_da_conversa(db, conv)
    assert j2["aberta"] and j2["ultima_entrada"] >= j1["ultima_entrada"]
    db.close()


# ── decisão 3: encaminhamento de documento — janela + config-gating ──────────

def test_encaminhar_documento_gated_e_janela(app_db, seed, monkeypatch, tmp_path):
    import mod_chat, mod_chat_externo as ext
    from database import ConversaMensagem
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_DocEnc",
                               seed["cliente_l1_id"], "(12) 97777-0009")
    doc = app_db.CicloDocumento(projeto_nome="Proj_DocEnc", etapa_codigo="11a", tipo="pe_planta",
                                arquivo_path="ciclo/11a/planta.pdf", nome_original="planta.pdf")
    db.add(doc); db.commit()
    arq = tmp_path / "planta.pdf"; arq.write_bytes(b"%PDF-fake")
    # janela FECHADA (nenhuma entrada) → erro claro pedindo template
    with pytest.raises(ValueError, match="[Jj]anela"):
        ext.encaminhar_documento_externo(db, conv, doc, None, str(arq))
    db.rollback()
    # abre a janela (entrada do cliente) + contato externo na conversa
    _numero_entrada(db, app_db, conv, "(12) 97777-0009", "oi", "wamid.DOC1"); db.commit()
    mod_chat.adicionar_externo(db, conv, "Cliente Doc", telefone="(12) 97777-0009"); db.commit()
    msg, envios = ext.encaminhar_documento_externo(db, conv, doc, None, str(arq),
                                                   mime="application/pdf")
    db.commit()
    assert msg.evento == "documento_encaminhado" and msg.documento_ref_id == doc.id
    assert len(envios) == 1
    assert envios[0].status == "pendente_config"       # sem credencial a rede NÃO é tocada
    db.close()


def test_encaminhar_sem_externo_erro_claro(app_db, seed, monkeypatch, tmp_path):
    import mod_chat_externo as ext
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    db = app_db.get_session()
    conv = _conversa_com_saida(db, app_db, seed["loja1_id"], "Proj_SemExterno",
                               seed["cliente_l1_id"], "(12) 97777-0010")
    _numero_entrada(db, app_db, conv, "(12) 97777-0010", "oi", "wamid.DOC2"); db.commit()
    doc = app_db.CicloDocumento(projeto_nome="Proj_SemExterno", etapa_codigo="11a",
                                tipo="pe_planta", arquivo_path="x", nome_original="x.pdf")
    db.add(doc); db.flush()
    arq = tmp_path / "x.pdf"; arq.write_bytes(b"x")
    with pytest.raises(ValueError, match="contato externo"):
        ext.encaminhar_documento_externo(db, conv, doc, None, str(arq))
    db.close()
