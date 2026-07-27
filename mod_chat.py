# -*- coding: utf-8 -*-
"""mod_chat.py — Chat do Orizon, Fatia 1 (Fundação).

Spec: docs/superpowers/specs/_geral/2026-07-25-chat-projeto-porta-externa-whatsapp-email-design.md
(decisões de produto 1-10 FECHADAS lá — não reabrir aqui).

Nesta fatia: Conversa por projeto (âncora flexível) + mensagem interna, cronológica.
CANAIS espelha o modelo consolidado da spec desde já, mas só 'interno' circula — os
externos (comercial/financeiro/logistica/suporte_tecnico/sac) entram nas fatias 6-7,
e natureza/transferência/bloqueador/privada nas fatias 2-4.
"""
import json
import os

from database import (Conversa, ConversaParticipante, ConversaMensagem, ContatoConfirmacao,
                      Usuario, Cliente, Parceiro, Funcionario, Funcao, CicloDocumento)

# ── Modo privado (Fatia 4, decisão 8) ────────────────────────────────────────
MASCARA_PRIVADA = "🔒 Mensagem privada — visível apenas à gerência"
_MASCARA_CHAVE_TROCADA = ("🔒 Mensagem privada — não foi possível decifrar "
                          "(a chave do ambiente mudou?)")


def _fernet():
    """Fernet da chave ORIZON_CHAT_ENC_KEY do ambiente, ou None quando não configurada.
    NUNCA gere chave descartável aqui: mensagem cifrada com chave de processo fica
    ilegível PARA SEMPRE no próximo restart — sem chave, o modo privado é RECUSADO com
    erro claro (requisito de deploy: a variável precisa existir nos 3 ambientes ANTES
    de habilitar o modo privado neles)."""
    chave = (os.environ.get("ORIZON_CHAT_ENC_KEY") or "").strip()
    if not chave:
        return None
    from cryptography.fernet import Fernet
    return Fernet(chave.encode("ascii"))

CANAIS = ("interno", "comercial", "financeiro", "logistica", "suporte_tecnico", "sac")
_CANAIS_FATIA_1 = ("interno",)

# ── Central de Comunicação (spec 2026-07-27, Fatia 1) ─────────────────────────
TIPOS_CONVERSA = ("projeto", "direct", "grupo", "publico")

# Segmento derivado da FUNÇÃO do autor (rótulo automático, não seleção). Casa palavra-chave
# no nome da função → segmento. Sem função ou sem match → None.
_SEGMENTO_POR_PALAVRA = (
    ("financ", "financeiro"),
    ("comerc", "comercial"), ("vend", "comercial"), ("consult", "comercial"), ("projet", "comercial"),
    ("logist", "logistica"), ("montag", "logistica"), ("montador", "logistica"), ("entreg", "logistica"),
    ("tecnic", "suporte_tecnico"), ("suporte", "suporte_tecnico"), ("assist", "suporte_tecnico"),
)


def canal_segmento_do_usuario(db, loja_id, usuario_id):
    """Segmento (comercial/financeiro/logistica/...) a partir da Função do usuário. None se não
    houver função ou nenhuma palavra-chave casar."""
    u = db.get(Usuario, usuario_id) if usuario_id else None
    if not u or not getattr(u, "funcao_id", None):
        return None
    fn = db.get(Funcao, u.funcao_id)
    nome = (fn.nome if fn and fn.nome else "").lower()
    for chave, seg in _SEGMENTO_POR_PALAVRA:
        if chave in nome:
            return seg
    return None

# Fatia 2: interação não muda nada; transferência oficializa a troca de responsabilidade
# (grava no v12 — quem escreve em CicloEtapa é o ENDPOINT, com as validações de vínculo).
NATUREZAS = ("interacao", "transferencia")

# ── Confirmação de contatos na fase de contrato (decisão 13, mini-frente 2026-07-25) ──────
MODOS_CONFIRMACAO = ("confirmado", "sem_whatsapp")


def contatos_do_projeto(db, cliente_id=None, parceiro_id=None):
    """Contatos de comunicação dos participantes externos, SEMPRE lidos do cadastro no
    momento da leitura (decisão 12). Cliente e Parceiro têm campo `whatsapp` próprio no
    cadastro (constatado em 2026-07-25 — a nota da S119 de que Cliente não tinha estava
    ERRADA); o telefone entra só como fallback quando o WhatsApp está vazio."""
    contatos = []
    if cliente_id:
        c = db.get(Cliente, cliente_id)
        if c is not None:
            contatos.append({"papel": "cliente", "nome": c.nome,
                             "whatsapp": (c.whatsapp or c.telefone or "").strip(),
                             "email": (c.email or "").strip()})
    if parceiro_id:
        p = db.get(Parceiro, parceiro_id)
        if p is not None:
            contatos.append({"papel": "arquiteto", "nome": p.nome,
                             "whatsapp": (p.whatsapp or p.telefone or "").strip(),
                             "email": (p.email or "").strip()})
    return contatos


def confirmacao_vigente(db, loja_id, projeto_nome):
    """A confirmação mais recente do projeto (append-only), ou None."""
    return (db.query(ContatoConfirmacao)
              .filter_by(loja_id=loja_id, projeto_nome=projeto_nome)
              .order_by(ContatoConfirmacao.id.desc())
              .first())


def registrar_confirmacao(db, loja_id, projeto_nome, usuario_id, modo, contatos):
    if modo not in MODOS_CONFIRMACAO:
        raise ValueError("modo inválido: %r (aceitos: %s)" % (modo, ", ".join(MODOS_CONFIRMACAO)))
    reg = ContatoConfirmacao(loja_id=loja_id, projeto_nome=projeto_nome, modo=modo,
                             contatos_json=json.dumps(contatos or [], ensure_ascii=False),
                             confirmado_por_id=usuario_id)
    db.add(reg)
    db.flush()
    return reg


def serializar_confirmacao(reg, confirmado_por_nome=None):
    if reg is None:
        return None
    return {"modo": reg.modo,
            "confirmado_por_id": reg.confirmado_por_id,
            "confirmado_por_nome": confirmado_por_nome or "—",
            "confirmado_em": reg.confirmado_em.isoformat() if reg.confirmado_em else None}


def get_or_create_conversa_projeto(db, loja_id, projeto_nome, cliente_id=None):
    """Conversa ÚNICA do projeto na loja (get-or-create; a primeira criada é a canônica).
    `cliente_id` só é gravado na criação — vínculo de nascença, não sincronização."""
    c = (db.query(Conversa)
           .filter_by(loja_id=loja_id, projeto_nome=projeto_nome)
           .order_by(Conversa.id.asc())
           .first())
    if c is None:
        c = Conversa(loja_id=loja_id, projeto_nome=projeto_nome, cliente_id=cliente_id)
        db.add(c)
        db.flush()
    return c


def enviar_mensagem(db, conversa, autor_usuario_id, corpo, canal="interno",
                    natureza="interacao", etapa_codigo=None,
                    transferido_para_funcionario_id=None, documento_ref_id=None,
                    bloqueador=False, privada=False, _permitir_externo=False,
                    canal_segmento=None):
    """Grava uma mensagem na conversa. Levanta ValueError com mensagem de usuário.
    Canal externo segue recusado (fatias 6-7). Fatia 2: `transferencia` exige destinatário;
    campos de transferência em `interacao` são recusados (não silenciosamente ignorados —
    quem mandou achando que transferiu precisa saber que não transferiu). `bloqueador` nesta
    fatia SÓ grava o flag — o gate real em pode_avancar() é a Fatia 3."""
    corpo = (corpo or "").strip()
    if not corpo:
        raise ValueError("Escreva a mensagem antes de enviar.")
    if canal not in CANAIS:
        raise ValueError("canal inválido: %r (aceitos: %s)" % (canal, ", ".join(CANAIS)))
    # Canal externo só entra pelo caminho de envio externo (mod_chat_externo, Fatias 6-7),
    # que passa _permitir_externo=True e cria o EnvioExterno junto. O chat interno segue
    # restrito a 'interno' — evita mensagem em canal externo sem porta de saída registrada.
    if canal not in _CANAIS_FATIA_1 and not _permitir_externo:
        raise ValueError("Canal externo só pelo envio externo (WhatsApp/e-mail).")
    if natureza not in NATUREZAS:
        raise ValueError("natureza inválida: %r (aceitas: %s)" % (natureza, ", ".join(NATUREZAS)))
    if natureza == "transferencia":
        if not transferido_para_funcionario_id:
            raise ValueError("Escolha quem recebe a transferência.")
    else:
        if transferido_para_funcionario_id or etapa_codigo or documento_ref_id or bloqueador:
            raise ValueError("Campos de transferência só valem em natureza=transferencia.")
    corpo_cifrado = None
    if privada:
        f = _fernet()
        if f is None:
            raise ValueError("Modo privado indisponível — chave de criptografia não "
                             "configurada neste ambiente.")
        corpo_cifrado = f.encrypt(corpo.encode("utf-8")).decode("ascii")
        corpo = ""    # o claro NUNCA persiste junto do cifrado (decisão 8)
    m = ConversaMensagem(conversa_id=conversa.id, autor_usuario_id=autor_usuario_id,
                         corpo=corpo, canal=canal, natureza=natureza,
                         etapa_codigo=etapa_codigo,
                         transferido_para_funcionario_id=transferido_para_funcionario_id,
                         documento_ref_id=documento_ref_id,
                         bloqueador=1 if bloqueador else 0,
                         privada=1 if privada else 0,
                         corpo_cifrado=corpo_cifrado,
                         canal_segmento=canal_segmento)
    db.add(m)
    db.flush()
    return m


def _corpo_visivel(m, pode_ver_privada):
    """Texto que sai na API: claro para mensagem comum; para privada, decripta SÓ para quem
    tem a capacidade — os demais recebem a MÁSCARA fixa (nunca o cifrado bruto)."""
    if not m.privada:
        return m.corpo
    if not pode_ver_privada:
        return MASCARA_PRIVADA
    f = _fernet()
    if f is None or not m.corpo_cifrado:
        return _MASCARA_CHAVE_TROCADA
    try:
        return f.decrypt(m.corpo_cifrado.encode("ascii")).decode("utf-8")
    except Exception:
        return _MASCARA_CHAVE_TROCADA


def serializar_mensagem(m, autor_nome=None, transferido_nome=None,
                        pode_ver_privada=False, documento=None):
    """`documento`: CicloDocumento já resolvido pelo chamador (ou None) — a mensagem devolve
    nome/tipo prontos, não só o id cru (Fatia 5)."""
    return {"id": m.id, "autor_usuario_id": m.autor_usuario_id,
            "autor_nome": autor_nome or "—",
            "corpo": _corpo_visivel(m, pode_ver_privada), "canal": m.canal,
            "canal_segmento": m.canal_segmento,
            "natureza": m.natureza or "interacao",
            "etapa_codigo": m.etapa_codigo,
            "transferido_para_funcionario_id": m.transferido_para_funcionario_id,
            "transferido_para_nome": transferido_nome or "",
            "documento_ref_id": m.documento_ref_id,
            "documento_nome": documento.nome_original if documento is not None else "",
            "documento_tipo": documento.tipo if documento is not None else "",
            "bloqueador": bool(m.bloqueador),
            "resolvido_em": m.resolvido_em.isoformat() if m.resolvido_em else None,
            "privada": bool(m.privada),
            "criado_em": m.criado_em.isoformat() if m.criado_em else None}


def listar_mensagens(db, conversa_id, pode_ver_privada=False):
    """Histórico cronológico ASC, com nomes de autor e destinatário resolvidos (outerjoin/
    batch: autor NULL — resposta externa futura — não derruba a listagem). O chamador diz
    se o leitor pode decifrar privadas (perfis.pode fica no composition root, não aqui)."""
    rows = (db.query(ConversaMensagem, Usuario.nome)
              .outerjoin(Usuario, ConversaMensagem.autor_usuario_id == Usuario.id)
              .filter(ConversaMensagem.conversa_id == conversa_id)
              .order_by(ConversaMensagem.criado_em.asc(), ConversaMensagem.id.asc())
              .all())
    ids_transf = {m.transferido_para_funcionario_id for m, _ in rows
                  if m.transferido_para_funcionario_id}
    nomes = ({f.id: f.nome for f in db.query(Funcionario)
              .filter(Funcionario.id.in_(ids_transf)).all()} if ids_transf else {})
    ids_docs = {m.documento_ref_id for m, _ in rows if m.documento_ref_id}
    docs = ({d.id: d for d in db.query(CicloDocumento)
             .filter(CicloDocumento.id.in_(ids_docs)).all()} if ids_docs else {})
    return [serializar_mensagem(m, nome, nomes.get(m.transferido_para_funcionario_id),
                                pode_ver_privada=pode_ver_privada,
                                documento=docs.get(m.documento_ref_id))
            for m, nome in rows]


# ── Conversas direct / grupo / inbox (Central de Comunicação, Fatia 1) ────────

def eh_participante(db, conversa_id, usuario_id):
    """True se o usuário participa da conversa (direct/grupo)."""
    return (db.query(ConversaParticipante.id)
              .filter_by(conversa_id=conversa_id, usuario_id=usuario_id)
              .first() is not None)


def get_or_create_direct(db, loja_id, criado_por_id, outro_usuario_id):
    """Conversa 1:1 canônica entre dois usuários da loja (idempotente pela dupla)."""
    if not outro_usuario_id or int(outro_usuario_id) == int(criado_por_id):
        raise ValueError("Escolha outro usuário para a conversa direta.")
    outro_usuario_id = int(outro_usuario_id)
    minhas = {r[0] for r in db.query(ConversaParticipante.conversa_id)
              .filter_by(usuario_id=criado_por_id).all()}
    do_outro = {r[0] for r in db.query(ConversaParticipante.conversa_id)
                .filter_by(usuario_id=outro_usuario_id).all()}
    comuns = minhas & do_outro
    if comuns:
        c = (db.query(Conversa)
               .filter(Conversa.id.in_(comuns), Conversa.loja_id == loja_id,
                       Conversa.tipo == "direct")
               .order_by(Conversa.id.asc()).first())
        if c is not None:
            return c
    c = Conversa(loja_id=loja_id, tipo="direct", criado_por_id=criado_por_id)
    db.add(c); db.flush()
    db.add_all([ConversaParticipante(conversa_id=c.id, usuario_id=criado_por_id),
                ConversaParticipante(conversa_id=c.id, usuario_id=outro_usuario_id)])
    db.flush()
    return c


def criar_grupo(db, loja_id, criado_por_id, titulo, participante_ids):
    """Cria uma conversa de grupo com título e N participantes (o criador entra como admin)."""
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Dê um nome ao grupo.")
    ids = {int(x) for x in (participante_ids or []) if x} | {int(criado_por_id)}
    if len(ids) < 2:
        raise ValueError("Um grupo precisa de ao menos 2 participantes.")
    c = Conversa(loja_id=loja_id, tipo="grupo", titulo=titulo, criado_por_id=criado_por_id)
    db.add(c); db.flush()
    for uid in ids:
        db.add(ConversaParticipante(conversa_id=c.id, usuario_id=uid,
                                    papel="admin" if uid == int(criado_por_id) else "membro"))
    db.flush()
    return c


def serializar_conversa(db, c, viewer_id, ultima=None, participantes=None):
    """Item da inbox: id/tipo/título de exibição + prévia da última mensagem. Para direct, o
    'titulo' de exibição é o nome do OUTRO participante (visto pelo `viewer_id`)."""
    titulo = c.titulo
    outro_id = None
    if c.tipo == "direct":
        parts = participantes if participantes is not None else [
            p.usuario_id for p in db.query(ConversaParticipante)
            .filter_by(conversa_id=c.id).all()]
        outros = [p for p in parts if p != viewer_id]
        outro_id = outros[0] if outros else None
        nome_outro = None
        if outro_id:
            u = db.get(Usuario, outro_id)
            nome_outro = u.nome if u else None
        titulo = nome_outro or "Conversa"
    if ultima is None:
        ultima = (db.query(ConversaMensagem)
                    .filter_by(conversa_id=c.id)
                    .order_by(ConversaMensagem.criado_em.desc(), ConversaMensagem.id.desc())
                    .first())
    previa = ""
    if ultima is not None:
        previa = MASCARA_PRIVADA if ultima.privada else (ultima.corpo or "")
    return {
        "id": c.id, "tipo": c.tipo, "titulo": titulo,
        "projeto_nome": c.projeto_nome, "outro_usuario_id": outro_id,
        "ultima_previa": previa[:120],
        "ultima_em": ultima.criado_em.isoformat() if (ultima and ultima.criado_em) else None,
        "criado_em": c.criado_em.isoformat() if c.criado_em else None,
    }


def listar_inbox(db, loja_id, usuario_id):
    """Conversas direct/grupo de que o usuário participa, na loja, mais recentes primeiro."""
    conv_ids = [r[0] for r in db.query(ConversaParticipante.conversa_id)
                .filter_by(usuario_id=usuario_id).all()]
    if not conv_ids:
        return []
    convs = (db.query(Conversa)
               .filter(Conversa.id.in_(conv_ids), Conversa.loja_id == loja_id,
                       Conversa.tipo.in_(("direct", "grupo")))
               .all())
    itens = [serializar_conversa(db, c, usuario_id) for c in convs]
    itens.sort(key=lambda x: (x["ultima_em"] or x["criado_em"] or ""), reverse=True)
    return itens


# ── Resolução por Função (decisões 6/9 — Financeiro/Logística/SAC) ───────────

def funcionario_por_funcao(db, loja_id, nome_funcao):
    """Primeiro Funcionário ATIVO com a Função (por nome) na loja. Regra da spec: 1 pessoa
    por função no cenário atual; com mais de uma, vale a primeira (ambiguidade é assunto do
    cadastro, o sistema não quebra). None quando ninguém tem a função."""
    f = (db.query(Funcionario)
           .join(Funcao, Funcionario.funcao_id == Funcao.id)
           .filter(Funcionario.loja_id == loja_id, Funcao.nome == nome_funcao)
           .filter((Funcionario.status == "ativo") | (Funcionario.status.is_(None)))
           .order_by(Funcionario.id.asc())
           .first())
    return f.id if f else None


def responsavel_sac(db, loja_id):
    """SAC fica FORA do v12 (spec seção 6): conversa de SAC pode nem ter projeto, logo não há
    CicloEtapa para ancorar — resolve direto pela Função 'SAC' da loja da conversa."""
    return funcionario_por_funcao(db, loja_id, "SAC")


def mensagem_passagem_fase(db, conversa, autor_usuario_id, etapa_concluida_nome,
                           etapa_seguinte_cod, etapa_seguinte_nome,
                           transferido_para_funcionario_id):
    """Passagem oficial AUTOMÁTICA na transição de fase (decisão 17): mensagem de transferência
    documentando que a próxima etapa passa ao seu responsável. NÃO grava CicloEtapa (só
    registra — o default segue resolvendo sozinho). Exige um destinatário: se a próxima etapa
    não tem responsável resolvível, o chamador não chama isto (não há a quem passar)."""
    corpo = ("Passagem automática de fase: \"%s\" concluída. A etapa %s (%s) segue com o "
             "responsável indicado." % (etapa_concluida_nome, etapa_seguinte_cod,
                                        etapa_seguinte_nome))
    return enviar_mensagem(db, conversa, autor_usuario_id, corpo,
                           natureza="transferencia", etapa_codigo=etapa_seguinte_cod,
                           transferido_para_funcionario_id=transferido_para_funcionario_id)


# ── Bloqueador como gate real (Fatia 3, spec seção 3) ────────────────────────

def bloqueadores_ativos(db, projeto_nome):
    """Set de etapa_codigo com transferência BLOQUEADORA não resolvida no projeto — '*'
    representa bloqueador SEM etapa (trava o ciclo inteiro). É o que o PATCH do ciclo passa
    para mod_ciclo.pode_avancar()."""
    rows = (db.query(ConversaMensagem.etapa_codigo)
              .join(Conversa, ConversaMensagem.conversa_id == Conversa.id)
              .filter(Conversa.projeto_nome == projeto_nome,
                      ConversaMensagem.natureza == "transferencia",
                      ConversaMensagem.bloqueador != 0,
                      ConversaMensagem.resolvido_em.is_(None))
              .all())
    return {(cod or "*") for (cod,) in rows}
