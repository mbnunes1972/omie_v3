# -*- coding: utf-8 -*-
"""Atendimentos UI — Fatia 1 (fundação de dados + envio por template).
Spec: docs/superpowers/specs/comunicacao/2026-08-04-orizon-chat-atendimentos-ui-design.md
Plan: docs/superpowers/plans/2026-08-04-atendimentos-chat-ui.md

Cobre: responsável atual (§7.1-A — transferir manual seta+ADICIONA participante; a transferência
automática de etapa atualiza o MESMO campo), urgência manual (§6.1), concluir/reabrir (§8, com
notificação interna à gerência por perfil), origem triagem×avulsa (§5), e o envio por template
`"type":"template"` (§11 — validação bloqueante de variável vazia, config-gated)."""
import io
import json
import urllib.request

import pytest

import mod_chat
import mod_chat_externo as mce
from chat import triagem as tri
from database import (Conversa, ConversaMensagem, ConversaParticipante, EnvioExterno,
                      TriagemEntrada)


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _uid(db, app_db, login):
    return db.query(app_db.Usuario).filter_by(login=login).first().id


# ── Responsável atual (§7.1-A) ─────────────────────────────────────────────────

def test_criador_comeca_responsavel(app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G resp", [], exige_dois=False)
        assert conv.responsavel_usuario_id == crid
    finally:
        db.close()


def test_conversa_de_projeto_nasce_com_criador_do_projeto(app_db, seed):
    """Achado da revisão visual 2026-08-04: get_or_create_conversa_projeto não passava
    responsável — o cabeçalho de uma conversa de projeto real (Homolog) nascia sem nome no
    canto direito, contrariando §7.1-A ('toda conversa tem sempre um responsável')."""
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        p = db.query(app_db.Projeto).filter_by(nome_safe=seed["projeto_l1"]).first()
        p.criado_por_id = crid
        db.commit()
        conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], seed["projeto_l1"])
        assert conv.responsavel_usuario_id == crid
        # idempotente: chamar de novo (conversa já existe) não sobrescreve uma transferência
        outro = _uid(db, app_db, "cons_l1")
        conv.responsavel_usuario_id = outro
        db.commit()
        conv2 = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], seed["projeto_l1"])
        assert conv2.id == conv.id and conv2.responsavel_usuario_id == outro
    finally:
        db.close()


def test_transferir_seta_e_adiciona_participante(app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        alvo = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G tr", [], exige_dois=False)
        u = mod_chat.transferir_responsavel(db, conv, crid, alvo); db.flush()
        assert u.id == alvo and conv.responsavel_usuario_id == alvo
        ativos = {p.usuario_id for p in db.query(ConversaParticipante)
                  .filter_by(conversa_id=conv.id, removido=0).all()}
        assert alvo in ativos and crid in ativos            # aditivo: ninguém sai
        # idempotente: transferir de novo não duplica a participação
        mod_chat.transferir_responsavel(db, conv, crid, alvo); db.flush()
        assert db.query(ConversaParticipante).filter_by(
            conversa_id=conv.id, usuario_id=alvo).count() == 1
        # evento registrado na timeline
        evs = db.query(ConversaMensagem).filter_by(
            conversa_id=conv.id, evento="responsavel_transf").all()
        assert len(evs) == 2
    finally:
        db.close()


def test_transferir_recusa_usuario_de_outra_loja(app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        alheio = _uid(db, app_db, "dir_l2")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G x", [], exige_dois=False)
        with pytest.raises(ValueError):
            mod_chat.transferir_responsavel(db, conv, crid, alheio)
    finally:
        db.close()


def test_transferencia_de_etapa_atualiza_o_mesmo_campo(app_db, seed):
    """A transferência AUTOMÁTICA (natureza='transferencia') e o botão manual alimentam o
    MESMO responsavel_usuario_id — checagem C1 do plano."""
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
        func = app_db.Funcionario(nome="Medidor R", loja_id=seed["loja1_id"],
                                  usuario_id=u.id, status="ativo")
        db.add(func); db.flush()
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G etp", [], exige_dois=False)
        mod_chat.enviar_mensagem(db, conv, crid, "passa", natureza="transferencia",
                                 etapa_codigo="10", transferido_para_funcionario_id=func.id)
        assert conv.responsavel_usuario_id == u.id
    finally:
        db.close()


# ── Urgência manual (§6.1) ─────────────────────────────────────────────────────

def test_urgencia_liga_desliga_com_evento(app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G urg", [], exige_dois=False)
        assert mod_chat.definir_urgencia(db, conv, crid, True) is True
        assert conv.urgente == 1
        assert mod_chat.definir_urgencia(db, conv, crid, True) is True   # idempotente: sem 2º evento
        assert mod_chat.definir_urgencia(db, conv, crid, False) is False
        assert conv.urgente == 0
        evs = db.query(ConversaMensagem).filter_by(conversa_id=conv.id, evento="urgencia").all()
        assert len(evs) == 2                                             # ligou + desligou
    finally:
        db.close()


# ── Concluir / reabrir (§8) ────────────────────────────────────────────────────

def test_concluir_grava_quem_quando_obs_e_notifica_gerencia(app_db, seed):
    db = app_db.get_session()
    try:
        op = _uid(db, app_db, "cons_l1")            # operador conclui
        ger = _uid(db, app_db, "dir_l1")            # master da loja recebe a DM
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], op, "Lead — Zé", [], exige_dois=False)
        mod_chat.concluir_atendimento(db, conv, op, "cliente satisfeito"); db.commit()
        assert conv.status == "concluida" and conv.concluido_por_id == op
        assert conv.concluido_em is not None and conv.conclusao_obs == "cliente satisfeito"
        with pytest.raises(ValueError):             # concluir 2x → erro claro
            mod_chat.concluir_atendimento(db, conv, op)
        n = mod_chat.notificar_conclusao_gerencia(db, conv, op); db.commit()
        assert n >= 1
        dm = mod_chat.get_or_create_direct(db, seed["loja1_id"], op, ger)
        corpos = [m.corpo for m in db.query(ConversaMensagem)
                  .filter_by(conversa_id=dm.id).all()]
        assert any("Atendimento concluído" in c and "cliente satisfeito" in c for c in corpos)
    finally:
        db.close()


def test_nova_entrada_reabre_atendimento_concluido(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999990101"
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G reab", [], exige_dois=False)
        mod_chat.adicionar_externo(db, conv, "Cli R", telefone=tel, meio="whatsapp")
        # tráfego prévio: entrada roteável (o roteador acha a conversa pelo reply do envio)
        msg = mod_chat.enviar_mensagem(db, conv, crid, "olá", canal="comercial",
                                       _permitir_externo=True)
        env = EnvioExterno(mensagem_id=msg.id, meio="whatsapp", direcao="saida",
                           canal="comercial", destino=tel, status="enviado",
                           id_externo="wamid.reab.out")
        db.add(env); db.commit()
        mod_chat.concluir_atendimento(db, conv, crid); db.commit()
        assert conv.status == "concluida"
        r = mce.processar_entrada(db, "whatsapp", tel, "voltei!",
                                  id_externo_ref="wamid.reab.out", id_externo="wamid.reab.in")
        db.commit()
        assert r["status"] == "roteado" and r["conversa_id"] == conv.id
        db.refresh(conv)
        assert conv.status == "aberta"              # §8.5: reabriu sozinho
    finally:
        db.close()


# ── Origem triagem × avulsa (§5) + responsável na resolução ───────────────────

def test_resolucao_de_triagem_assume_e_marca_origem(app_db, seed, monkeypatch):
    """Resolução SEMPRE automática (2026-08-05, triagem_materializar): quem assume não é mais
    'quem resolveu' (não existe mais humano na fila) — é o SAC (Função 'SAC' da loja)."""
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    db = app_db.get_session()
    try:
        sac_uid = _uid(db, app_db, "cons_l1")
        fn = app_db.Funcao(loja_id=seed["loja1_id"], nome="SAC")
        db.add(fn); db.flush()
        func = app_db.Funcionario(nome="Pessoa do SAC", loja_id=seed["loja1_id"],
                                  funcao_id=fn.id, usuario_id=sac_uid, status="ativo")
        db.add(func); db.flush()
        ent = TriagemEntrada(loja_id=seed["loja1_id"], meio="whatsapp",
                             remetente="5512999990202", texto="oi")
        db.add(ent); db.flush()
        conv = tri.triagem_materializar(db, ent, tri.SEGMENTO_TRIAGEM); db.commit()
        assert conv.responsavel_usuario_id == sac_uid       # SAC ASSUME (2026-08-05)
        assert conv.origem_entrada == "triagem"             # tag de fallback correta (§5)
        assert conv.segmento == tri.SEGMENTO_TRIAGEM
        assert ent.status == "resolvido"
    finally:
        db.close()


# ── Envio por template (§11) ───────────────────────────────────────────────────

def test_render_template_valida_variavel_vazia():
    corpo = "Olá, {{1}}! Aqui é {{2}}."
    texto, params = mce._render_template(corpo, {1: "Ana", 2: "Bia"})
    assert texto == "Olá, Ana! Aqui é Bia." and params == ["Ana", "Bia"]
    with pytest.raises(ValueError) as ei:
        mce._render_template(corpo, {1: "Ana"})             # {{2}} vazio → bloqueia
    assert "{{2}}" in str(ei.value)
    with pytest.raises(ValueError):
        mce._render_template(corpo, {1: "Ana", 2: "   "})   # espaço não conta


def test_payload_template_correto(monkeypatch):
    capturado = {}

    def _fake_urlopen(req, timeout=15):
        capturado["payload"] = json.loads(req.data.decode("utf-8"))
        class _R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R(json.dumps({"messages": [{"id": "wamid.tpl.1"}]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setenv("ORIZON_WA_TOKEN", "tok")
    monkeypatch.setenv("ORIZON_WA_PHONE_ID", "123")

    class _Env:
        canal = "comercial"; destino = "+55 (12) 99999-0303"
    ok, wamid, erro = mce._enviar_whatsapp_template(_Env(), "apresentacao", "pt_BR",
                                                    ["Ana", "Patrícia"])
    assert ok and wamid == "wamid.tpl.1" and erro is None
    p = capturado["payload"]
    assert p["type"] == "template" and p["to"] == "5512999990303"
    assert p["template"]["name"] == "apresentacao"
    assert p["template"]["language"]["code"] == "pt_BR"
    pars = p["template"]["components"][0]["parameters"]
    assert [x["text"] for x in pars] == ["Ana", "Patrícia"]


def test_enviar_template_conversa_config_gated(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        crid = _uid(db, app_db, "dir_l1")
        t = mod_chat.criar_template(db, lid, {
            "nome_meta": "apres_ui", "segmento": "comercial", "categoria": "utility",
            "corpo": "Olá, {{1}}! Aqui é {{2}}.", "status": "aprovado",
            "variaveis": ["Nome do cliente", "Nome do atendente"]})
        conv = mod_chat.criar_grupo(db, lid, crid, "Lead — Tpl", [], exige_dois=False)
        mod_chat.adicionar_externo(db, conv, "Cli T", telefone="5512999990404",
                                   meio="whatsapp")
        msg, env = mce.enviar_template_conversa(db, conv, crid, t,
                                                {1: "Cli T", 2: "Ana"})
        db.commit()
        assert msg.corpo == "Olá, Cli T! Aqui é Ana."       # histórico legível (renderizado)
        assert env.status == "pendente_config"              # sem credencial: rede não tocada
        assert env.template_id == t.id
        # rascunho NÃO sai fora da janela
        t2 = mod_chat.criar_template(db, lid, {"nome_meta": "rascunho_ui",
                                               "corpo": "Oi {{1}}", "status": "rascunho"})
        with pytest.raises(ValueError):
            mce.enviar_template_conversa(db, conv, crid, t2, {1: "X"})
    finally:
        db.close()


def test_resolver_variaveis_conhecidas():
    vars_ = ["Nome do cliente", "Nome do atendente", "Nome da loja", "Data de vencimento"]
    out = mod_chat.resolver_variaveis_conhecidas(vars_, usuario_nome="Patrícia",
                                                 contato_nome="Fernanda", loja_nome="Dalmóbile")
    assert out == {1: "Fernanda", 2: "Patrícia", 3: "Dalmóbile"}   # a 4 fica p/ preencher


# ── Endpoints + tenancy ────────────────────────────────────────────────────────

def test_endpoints_transferir_urgente_concluir(http_client_factory, app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        alvo = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G ep", [], exige_dois=False)
        db.commit(); cid = conv.id
    finally:
        db.close()
    ger = _login(http_client_factory, "dir_l1")
    st, b = ger.post("/api/comunicacao/conversas/%d/transferir" % cid, {"usuario_id": alvo})
    assert st == 200 and b["responsavel"]["id"] == alvo
    st, b = ger.post("/api/comunicacao/conversas/%d/urgente" % cid, {"on": True})
    assert st == 200 and b["urgente"] is True
    st, b = ger.post("/api/comunicacao/conversas/%d/concluir" % cid,
                     {"observacao": "ok pelo endpoint"})
    assert st == 200 and b["status"] == "concluida"
    # inbox do destino expõe responsável/urgente/status (serialização nova)
    alvo_cli = _login(http_client_factory, "cons_l1")
    st, b = alvo_cli.get("/api/comunicacao/inbox")
    assert st == 200
    item = next(i for i in b["conversas"] if i["id"] == cid)
    assert item["responsavel"]["id"] == alvo and item["urgente"] is True
    assert item["status"] == "concluida"
    # tenancy: a loja 2 não alcança (404); não-participante sem gerência → 403
    outro = _login(http_client_factory, "dir_l2")
    assert outro.post("/api/comunicacao/conversas/%d/urgente" % cid, {"on": True})[0] == 404


def test_endpoint_nao_participante_operador_403(http_client_factory, app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G 403", [], exige_dois=False)
        db.commit(); cid = conv.id
    finally:
        db.close()
    op = _login(http_client_factory, "cons_l1")     # operador, NÃO participante
    assert op.post("/api/comunicacao/conversas/%d/urgente" % cid, {"on": True})[0] == 403


# ── Janela por telefone (§11 — antes de a conversa existir) ────────────────────

def test_janela_por_telefone_aberta_e_escopada_por_loja(app_db, seed):
    db = app_db.get_session()
    try:
        crid1 = _uid(db, app_db, "dir_l1")
        crid2 = _uid(db, app_db, "dir_l2")
        tel = "5512999990505"
        assert mce.janela_por_telefone(db, seed["loja1_id"], tel)["aberta"] is False
        conv1 = mod_chat.criar_grupo(db, seed["loja1_id"], crid1, "G jt1", [], exige_dois=False)
        msg = mod_chat.enviar_mensagem(db, conv1, None, "oi", canal="comercial",
                                       _permitir_externo=True)
        db.add(EnvioExterno(mensagem_id=msg.id, meio="whatsapp", direcao="entrada",
                            destino=tel, status="recebido")); db.commit()
        assert mce.janela_por_telefone(db, seed["loja1_id"], tel)["aberta"] is True
        # o MESMO telefone em outra loja não deve "ver" a janela alheia (isolamento)
        assert mce.janela_por_telefone(db, seed["loja2_id"], tel)["aberta"] is False
    finally:
        db.close()


# ── Iniciar Conversa por template (§11) ────────────────────────────────────────

def test_iniciar_conversa_com_template_cria_e_envia(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        crid = _uid(db, app_db, "dir_l1")
        t = mod_chat.criar_template(db, lid, {
            "nome_meta": "apres_ic", "segmento": "comercial", "categoria": "utility",
            "corpo": "Olá, {{1}}! Aqui é {{2}}.", "status": "aprovado",
            "variaveis": ["Nome do cliente", "Nome do atendente"]})
        conv = mod_chat.iniciar_conversa_externa(
            db, lid, crid, {"nome": "Fernanda IC", "telefone": "5512999990606"},
            template_id=t.id, valores={1: "Fernanda IC", 2: "Ana"})
        db.commit()
        assert conv.responsavel_usuario_id == crid and conv.origem_entrada == "avulsa"
        ext = db.query(app_db.ConversaParticipanteExterno).filter_by(conversa_id=conv.id).first()
        assert ext is not None and ext.telefone == "5512999990606"
        msg = (db.query(ConversaMensagem).filter_by(conversa_id=conv.id)
                 .order_by(ConversaMensagem.id.desc()).first())
        assert msg.corpo == "Olá, Fernanda IC! Aqui é Ana."
        env = db.query(EnvioExterno).filter_by(mensagem_id=msg.id).first()
        assert env.status == "pendente_config" and env.template_id == t.id
        # achado da Vera 2026-08-04: o segmento já aparece via _atendimento_meta (herdado do
        # canal da mensagem do template) ANTES de qualquer resposta do contato — é o que o
        # front usa pra decidir se mostra "Concluir atendimento" (não só janela.estado).
        segmento, janela = mod_chat._atendimento_meta(db, conv)
        assert segmento == "comercial" and janela["estado"] == "na"
    finally:
        db.close()


def test_iniciar_conversa_livre_exige_janela_aberta(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        crid = _uid(db, app_db, "dir_l1")
        with pytest.raises(ValueError):
            mod_chat.iniciar_conversa_externa(
                db, lid, crid, {"nome": "Sem Janela", "telefone": "5512999990707"},
                livre=True)
        # com janela aberta (entrada recente do mesmo telefone) já funciona
        tel = "5512999990808"
        conv0 = mod_chat.criar_grupo(db, lid, crid, "G lv", [], exige_dois=False)
        msg0 = mod_chat.enviar_mensagem(db, conv0, None, "oi", canal="comercial",
                                        _permitir_externo=True)
        db.add(EnvioExterno(mensagem_id=msg0.id, meio="whatsapp", direcao="entrada",
                            destino=tel, status="recebido")); db.commit()
        conv = mod_chat.iniciar_conversa_externa(
            db, lid, crid, {"nome": "Com Janela", "telefone": tel}, livre=True)
        db.commit()
        assert conv.id == conv0.id      # reaproveita a conversa já roteável (não duplica)
    finally:
        db.close()


def test_iniciar_conversa_bloqueia_variavel_vazia(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        crid = _uid(db, app_db, "dir_l1")
        t = mod_chat.criar_template(db, lid, {
            "nome_meta": "apres_ic2", "corpo": "Olá, {{1}}! Aqui é {{2}}.",
            "status": "aprovado", "variaveis": ["Nome do cliente", "Nome do atendente"]})
        with pytest.raises(ValueError) as ei:
            mod_chat.iniciar_conversa_externa(
                db, lid, crid, {"nome": "X", "telefone": "5512999990909"},
                template_id=t.id, valores={1: "X"})
        assert "{{2}}" in str(ei.value)
    finally:
        db.close()


# ── Exportar conversa (TXT/PDF) ─────────────────────────────────────────────────

def test_exportar_conversa_txt_conteudo(app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G exp", [], exige_dois=False)
        mod_chat.enviar_mensagem(db, conv, crid, "mensagem de teste export")
        db.commit()
        txt = mod_chat.exportar_conversa_txt(db, conv)
        assert "G exp" in txt and "mensagem de teste export" in txt
    finally:
        db.close()


def test_endpoint_exportar_e_janela(http_client_factory, app_db, seed):
    db = app_db.get_session()
    try:
        crid = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "G exp ep", [], exige_dois=False)
        mod_chat.enviar_mensagem(db, conv, crid, "olá exportação http")
        db.commit(); cid = conv.id
    finally:
        db.close()
    ger = _login(http_client_factory, "dir_l1")
    st, raw = ger.get("/api/comunicacao/conversas/%d/exportar?formato=txt" % cid)
    assert st == 200
    texto = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    assert "olá exportação http" in texto
    outro = _login(http_client_factory, "dir_l2")
    assert outro.get("/api/comunicacao/conversas/%d/exportar?formato=txt" % cid)[0] == 404
    st, b = ger.get("/api/comunicacao/janela?telefone=5512999990606")
    assert st == 200 and "aberta" in b


# ── Endpoint iniciar-conversa (tenancy + fluxo) ────────────────────────────────

def test_endpoint_iniciar_conversa(http_client_factory, app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    db = app_db.get_session()
    try:
        lid = seed["loja1_id"]
        t = mod_chat.criar_template(db, lid, {
            "nome_meta": "apres_ep", "corpo": "Oi, {{1}}!", "status": "aprovado",
            "variaveis": ["Nome do cliente"]})
        db.commit(); tid = t.id
    finally:
        db.close()
    ger = _login(http_client_factory, "dir_l1")
    st, b = ger.post("/api/comunicacao/iniciar-conversa", {
        "contato": {"nome": "Endpoint IC", "telefone": "5512999991010"},
        "template_id": tid, "valores": {"1": "Endpoint IC"}})
    assert st == 201, b
    assert b["conversa"]["id"]
    # sem template nem livre → bloqueia
    st, b = ger.post("/api/comunicacao/iniciar-conversa", {
        "contato": {"nome": "Sem nada", "telefone": "5512999991111"}})
    assert st == 400
