# -*- coding: utf-8 -*-
"""r4 da revisão UX (2026-07-31): segmento = CANAL DE ENTRADA da triagem — com RESPONSÁVEL,
'+ novo segmento' e apagar (custom) na tela Segmentos; conversa INTERNA não tem segmento."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_criar_segmento_custom_e_listar(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    c = mod_chat.criar_segmento(db, seed["loja1_id"], "Pós-Venda VIP")
    db.commit()
    assert c.segmento == "pos_venda_vip"            # slug sem acento, minúsculo
    cfg = mod_chat.segmentos_config_get(db, seed["loja1_id"])
    custom = [s for s in cfg if s["segmento"] == "pos_venda_vip"]
    assert custom and custom[0]["custom"] is True and custom[0]["rotulo"] == "Pós-Venda VIP"
    ativos = {s["segmento"] for s in mod_chat.segmentos_ativos(db, seed["loja1_id"])}
    assert "pos_venda_vip" in ativos and "comercial" in ativos
    with pytest.raises(ValueError, match="[Jj]á existe"):
        mod_chat.criar_segmento(db, seed["loja1_id"], "pos venda vip")
    db.rollback()
    # tenancy: o custom é DA LOJA — loja 2 não o valida nem o lista
    assert not any(s["segmento"] == "pos_venda_vip"
                   for s in mod_chat.segmentos_ativos(db, seed["loja2_id"]))
    db.close()


def test_conversa_interna_nao_tem_segmento(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    ua = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    ub = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    grupo = mod_chat.criar_grupo(db, seed["loja1_id"], ua.id, "Equipe Interna", [ua.id, ub.id])
    db.commit()
    with pytest.raises(ValueError, match="interna"):
        mod_chat.definir_segmento(db, grupo, "comercial")   # grupo interno: sem canal de entrada
    db.rollback()
    direct = mod_chat.get_or_create_direct(db, seed["loja1_id"], ua.id, ub.id)
    db.commit()
    with pytest.raises(ValueError, match="interna"):
        mod_chat.definir_segmento(db, direct, "comercial")
    db.rollback()
    db.close()


def test_segmento_custom_em_atendimento_e_apagar(app_db, seed):
    import mod_chat
    from database import Conversa
    db = app_db.get_session()
    mod_chat.criar_segmento(db, seed["loja1_id"], "Garantia"); db.commit()
    u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
    # conversa COM face externa (contato adicionado) aceita o segmento custom
    conv, _reg = mod_chat.adicionar_contato(
        db, seed["loja1_id"], u.id, "Cliente Garantia", telefone="(12) 97777-2001",
        motivo="Acionamento de garantia", segmento="garantia")
    db.commit()
    assert db.get(Conversa, conv.id).segmento == "garantia"
    # apagar o custom: conversas voltam a 'sem segmento' e ele some das listas
    mod_chat.apagar_segmento(db, seed["loja1_id"], "garantia"); db.commit()
    assert db.get(Conversa, conv.id).segmento is None
    assert not any(s["segmento"] == "garantia"
                   for s in mod_chat.segmentos_ativos(db, seed["loja1_id"]))
    # base não apaga — desativa
    with pytest.raises(ValueError, match="catálogo base"):
        mod_chat.apagar_segmento(db, seed["loja1_id"], "comercial")
    db.rollback()
    db.close()


def test_responsavel_do_segmento(app_db, seed):
    import mod_chat
    db = app_db.get_session()
    f = app_db.Funcionario(nome="Resp Comercial", loja_id=seed["loja1_id"], status="ativo")
    db.add(f); db.flush()
    itens = [{"segmento": "comercial", "ativo": True, "rotulo": "Comercial",
              "responsavel_funcionario_id": f.id}]
    cfg = mod_chat.segmentos_config_salvar(db, seed["loja1_id"], itens)
    db.commit()
    com = [s for s in cfg if s["segmento"] == "comercial"][0]
    assert com["responsavel_funcionario_id"] == f.id
    assert com["responsavel_nome"] == "Resp Comercial"
    # funcionário de OUTRA loja não cola como responsável (tenancy)
    f2 = app_db.Funcionario(nome="Intruso L2", loja_id=seed["loja2_id"], status="ativo")
    db.add(f2); db.flush()
    cfg = mod_chat.segmentos_config_salvar(db, seed["loja1_id"],
        [{"segmento": "comercial", "ativo": True, "responsavel_funcionario_id": f2.id}])
    db.commit()
    assert [s for s in cfg if s["segmento"] == "comercial"][0]["responsavel_funcionario_id"] is None
    db.close()


def test_endpoints_segmentos_ativos_e_crud(http_client_factory, app_db, seed):
    # lista leve: OPERADOR pode (os seletores da F7 usam)
    cop = _login(http_client_factory, "cons_l1")
    st, body = cop.get("/api/comunicacao/segmentos/ativos")
    assert st == 200 and body["ok"] and any(s["segmento"] == "comercial" for s in body["segmentos"])
    # criar/apagar: gerência
    st, _b = cop.post("/api/comunicacao/segmentos/criar", {"rotulo": "Não Posso"})
    assert st == 403
    c1 = _login(http_client_factory, "dir_l1")
    st, body = c1.post("/api/comunicacao/segmentos/criar", {"rotulo": "Eventos"})
    assert st == 200 and body["ok"]
    assert any(s["segmento"] == "eventos" and s["custom"] for s in body["segmentos"])
    st, body = c1.post("/api/comunicacao/segmentos/apagar", {"segmento": "eventos"})
    assert st == 200 and body["ok"]
    assert not any(s["segmento"] == "eventos" for s in body["segmentos"])
    st, _b = c1.post("/api/comunicacao/segmentos/apagar", {"segmento": "sac"})
    assert st == 400                                    # base não apaga
