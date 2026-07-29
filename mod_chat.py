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

from sqlalchemy import func

from database import (Conversa, ConversaParticipante, ConversaParticipanteExterno,
                      ConversaMensagem, MensagemAnexo, ContatoConfirmacao, Assunto, Usuario,
                      Cliente, Parceiro, Funcionario, Funcao, CicloDocumento, TemplateMensagem,
                      TriagemConfig, SegmentoConfig)

# ── Modo privado REMOVIDO (2026-07-27) ────────────────────────────────────────
# Não se criam novas mensagens privadas. Mensagens privadas LEGADAS (privada=1, texto cifrado em
# corpo_cifrado) já não são decifradas — exibem este marcador. As colunas privada/corpo_cifrado
# ficam no schema como legado (sem migração destrutiva).
MASCARA_PRIVADA = "🔒 (mensagem privada — recurso descontinuado)"

CANAIS = ("interno", "comercial", "financeiro", "logistica", "suporte_tecnico", "sac",
          "compras", "parceiros")
_CANAIS_FATIA_1 = ("interno",)

# Segmentos externos (Meta) — espelha mod_chat_externo.CANAIS_EXTERNOS (teste anti-drift na Fatia 1).
SEGMENTOS = ("comercial", "financeiro", "logistica", "suporte_tecnico", "sac", "compras", "parceiros")

# As 9 mensagens OBRIGATÓRIAS do sistema (spec §4.1) — fonte ÚNICA do checklist RF-16 (Fatia 5) e do
# mapeamento segmento→template do reengajamento (Fatia 4). Ordem = número do slot.
SLOTS_OBRIGATORIOS = (
    {"num": 1, "titulo": "Triagem / boas-vindas",              "momento": "Primeiro contato sem conversa ativa",        "categoria": "utility", "segmento": None},
    {"num": 2, "titulo": "Confirmação de vínculo a projeto",   "momento": "Cliente com projeto ativo entra em contato",  "categoria": "utility", "segmento": None},
    {"num": 3, "titulo": "Aviso de janela prestes a fechar",   "momento": "~90% do prazo de 24h sem resposta",           "categoria": "utility", "segmento": None},
    {"num": 4, "titulo": "Reengajamento — Comercial",          "momento": "Janela fechada, retomada de negociação",      "categoria": "utility", "segmento": "comercial"},
    {"num": 5, "titulo": "Reengajamento — Suporte Técnico",    "momento": "Janela fechada, retomada pós-venda",          "categoria": "utility", "segmento": "suporte_tecnico"},
    {"num": 6, "titulo": "Reengajamento/Cobrança — Financeiro","momento": "Janela fechada, aviso de pendência",          "categoria": "utility", "segmento": "financeiro"},
    {"num": 7, "titulo": "Reengajamento — Compras",            "momento": "Janela fechada, alinhamento com fornecedor",  "categoria": "utility", "segmento": "compras"},
    {"num": 8, "titulo": "Confirmação de agendamento — Logística","momento": "Entrega ou visita de montagem",             "categoria": "utility", "segmento": "logistica"},
    {"num": 9, "titulo": "Reengajamento — Parceiros",          "momento": "Janela fechada, aviso de comissão/indicação", "categoria": "utility", "segmento": "parceiros"},
)
_SLOTS_NUM = {s["num"] for s in SLOTS_OBRIGATORIOS}

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
                    bloqueador=False, _permitir_externo=False,
                    canal_segmento=None, permitir_vazio=False,
                    destinatario_usuario_id=None):
    """Grava uma mensagem na conversa. Levanta ValueError com mensagem de usuário.
    Canal externo segue recusado (fatias 6-7). Fatia 2: `transferencia` exige destinatário;
    campos de transferência em `interacao` são recusados (não silenciosamente ignorados —
    quem mandou achando que transferiu precisa saber que não transferiu). `bloqueador` nesta
    fatia SÓ grava o flag — o gate real em pode_avancar() é a Fatia 3."""
    corpo = (corpo or "").strip()
    if not corpo and not permitir_vazio:   # anexo-only (Fatia 5) passa permitir_vazio=True
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
    # Destinatário dirigido (F2): só vale se for PARTICIPANTE da conversa — senão vira "todos" (None).
    # (achado da Vera: sem isso, um id de outra loja/não-membro vazaria como "→ para <nome>").
    _dest = None
    if destinatario_usuario_id:
        try:
            _d = int(destinatario_usuario_id)
        except (TypeError, ValueError):
            _d = None
        if _d and eh_participante(db, conversa.id, _d):
            _dest = _d
    m = ConversaMensagem(conversa_id=conversa.id, autor_usuario_id=autor_usuario_id,
                         corpo=corpo, canal=canal, natureza=natureza,
                         etapa_codigo=etapa_codigo,
                         transferido_para_funcionario_id=transferido_para_funcionario_id,
                         documento_ref_id=documento_ref_id,
                         bloqueador=1 if bloqueador else 0,
                         canal_segmento=canal_segmento,
                         destinatario_usuario_id=_dest)
    db.add(m)
    db.flush()
    # RF-11 / §7 (carteira aditiva): a transferência de responsabilidade ADICIONA o novo responsável
    # como integrante do grupo — NUNCA remove ninguém. O Consultor original permanece.
    if natureza == "transferencia" and transferido_para_funcionario_id:
        _adicionar_responsavel_ao_grupo(db, conversa, transferido_para_funcionario_id)
    return m


def _usuario_do_funcionario(db, funcionario_id):
    """Usuario vinculado a um Funcionario (Funcionario.usuario_id ou o reverso). None se terceiro/sem
    conta — nesse caso não há ConversaParticipante a adicionar."""
    if not funcionario_id:
        return None
    f = db.get(Funcionario, funcionario_id)
    if f is not None and getattr(f, "usuario_id", None):
        return f.usuario_id
    u = db.query(Usuario).filter_by(funcionario_id=funcionario_id).first()
    return u.id if u else None


def _adicionar_responsavel_ao_grupo(db, conversa, funcionario_id):
    """Inclui (ou reativa) o responsável transferido como ConversaParticipante do grupo. Aditivo:
    não remove ninguém; idempotente (não duplica). Sem usuario vinculado → no-op."""
    uid = _usuario_do_funcionario(db, funcionario_id)
    if not uid:
        return None
    p = (db.query(ConversaParticipante)
           .filter_by(conversa_id=conversa.id, usuario_id=uid).first())
    if p is None:
        p = ConversaParticipante(conversa_id=conversa.id, usuario_id=uid,
                                 papel="membro", origem="auto", removido=0)
        db.add(p)
    elif p.removido:
        p.removido = 0   # transferido de volta → volta ao grupo
    db.flush()
    return uid


def _corpo_visivel(m):
    """Texto que sai na API. Modo privado removido: mensagem comum mostra o claro; mensagem
    privada LEGADA (privada=1) mostra o marcador de descontinuado (não decifra)."""
    return m.corpo if not m.privada else MASCARA_PRIVADA


def _serializar_anexo(a):
    return {"id": a.id, "tipo": a.tipo, "nome": a.nome, "mime": a.mime,
            "tamanho": a.tamanho, "url": "/api/comunicacao/anexos/%d" % a.id}


def anexos_por_mensagem(db, mensagem_ids):
    """Mapa {mensagem_id: [anexos serializados]} para um lote de mensagens."""
    if not mensagem_ids:
        return {}
    out = {}
    for a in (db.query(MensagemAnexo)
                .filter(MensagemAnexo.mensagem_id.in_(list(mensagem_ids)))
                .order_by(MensagemAnexo.id.asc()).all()):
        out.setdefault(a.mensagem_id, []).append(_serializar_anexo(a))
    return out


def tipo_anexo_por_mime(mime):
    return "imagem" if (mime or "").lower().startswith("image/") else "arquivo"


def criar_anexo(db, mensagem_id, nome, mime, tamanho, caminho):
    a = MensagemAnexo(mensagem_id=mensagem_id, tipo=tipo_anexo_por_mime(mime),
                      nome=nome, mime=mime, tamanho=tamanho, caminho=caminho)
    db.add(a); db.flush()
    return a


def serializar_mensagem(m, autor_nome=None, transferido_nome=None,
                        documento=None, anexos=None, destinatario_nome=None):
    """`documento`: CicloDocumento já resolvido pelo chamador (ou None) — a mensagem devolve
    nome/tipo prontos, não só o id cru (Fatia 5). `destinatario_nome`: alvo dirigido (F2)."""
    return {"id": m.id, "autor_usuario_id": m.autor_usuario_id,
            "autor_nome": autor_nome or "—",
            "destinatario_usuario_id": m.destinatario_usuario_id,
            "destinatario_nome": destinatario_nome or "",
            "corpo": _corpo_visivel(m), "canal": m.canal,
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
            "anexos": anexos or [],
            "criado_em": m.criado_em.isoformat() if m.criado_em else None}


def listar_mensagens(db, conversa_id):
    """Histórico cronológico ASC, com nomes de autor e destinatário resolvidos (outerjoin/
    batch: autor NULL — resposta externa — não derruba a listagem)."""
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
    ids_dest = {m.destinatario_usuario_id for m, _ in rows if m.destinatario_usuario_id}
    dest_nomes = ({u.id: u.nome for u in db.query(Usuario)
                   .filter(Usuario.id.in_(ids_dest)).all()} if ids_dest else {})
    anexos = anexos_por_mensagem(db, [m.id for m, _ in rows])
    return [serializar_mensagem(m, nome, nomes.get(m.transferido_para_funcionario_id),
                                documento=docs.get(m.documento_ref_id),
                                anexos=anexos.get(m.id),
                                destinatario_nome=dest_nomes.get(m.destinatario_usuario_id))
            for m, nome in rows]


# ── Conversas direct / grupo / inbox (Central de Comunicação, Fatia 1) ────────

def eh_participante(db, conversa_id, usuario_id):
    """True se o usuário participa da conversa (direct/grupo/projeto) e NÃO foi removido."""
    return (db.query(ConversaParticipante.id)
              .filter(ConversaParticipante.conversa_id == conversa_id,
                      ConversaParticipante.usuario_id == usuario_id,
                      ConversaParticipante.removido == 0)
              .first() is not None)


def _funcao_nome_do_usuario(db, usuario_id):
    """Função (cargo) do usuário via Funcionario→Funcao (`Usuario.funcionario_id` ou o vínculo
    reverso). None se não houver vínculo/função."""
    u = db.get(Usuario, usuario_id) if usuario_id else None
    fid = getattr(u, "funcionario_id", None) if u else None
    func = db.get(Funcionario, fid) if fid else None
    if func is None and usuario_id:
        func = db.query(Funcionario).filter_by(usuario_id=usuario_id).first()
    if func is None or not func.funcao_id:
        return None
    fu = db.get(Funcao, func.funcao_id)
    return fu.nome if fu else None


def listar_participantes(db, conversa):
    """Participantes ATIVOS (não removidos): INTERNOS (Usuario, com FUNÇÃO/origem/flag `gerencia`) +
    EXTERNOS (contato WhatsApp/e-mail, `externo: True`, DESTACADOS na UI)."""
    from auth import perfis
    rows = (db.query(ConversaParticipante, Usuario)
              .outerjoin(Usuario, ConversaParticipante.usuario_id == Usuario.id)
              .filter(ConversaParticipante.conversa_id == conversa.id,
                      ConversaParticipante.removido == 0)
              .order_by(Usuario.nome.asc()).all())
    out = []
    for p, u in rows:
        nivel = getattr(u, "nivel", None) if u else None
        eh_ger = bool(nivel and (perfis.pode(nivel, "autorizar") or perfis.pode(nivel, "aprovar_financeiro")))
        out.append({"usuario_id": p.usuario_id, "nome": (u.nome if u else "—"),
                    "origem": p.origem, "papel": p.papel, "externo": False,
                    "funcao_nome": _funcao_nome_do_usuario(db, p.usuario_id),
                    "gerencia": eh_ger})
    for e in listar_externos(db, conversa):
        out.append({"externo_id": e["id"], "nome": e["nome"], "origem": "externo",
                    "externo": True, "meio": e["meio"], "contato": e["telefone"] or e["email"],
                    "funcao_nome": "Externo", "gerencia": False})
    return out


# ── Participantes EXTERNOS (contato WhatsApp/e-mail, sem Usuario) — Orizon Chat 2026-07-28 ──────

def listar_externos(db, conversa, incluir_removidos=False):
    q = db.query(ConversaParticipanteExterno).filter_by(conversa_id=conversa.id)
    if not incluir_removidos:
        q = q.filter(ConversaParticipanteExterno.removido == 0)
    return [{"id": e.id, "nome": e.nome, "telefone": e.telefone, "email": e.email, "meio": e.meio}
            for e in q.order_by(ConversaParticipanteExterno.nome.asc()).all()]


def adicionar_externo(db, conversa, nome, telefone=None, email=None, meio="whatsapp", criado_por_id=None):
    """Adiciona (ou reativa) um participante externo. `meio` = whatsapp exige telefone; email exige
    e-mail. Reativa um homônimo pelo mesmo contato (não duplica). Não commita. Retorna o registro."""
    nome = (nome or "").strip()
    telefone = (telefone or "").strip() or None
    email = (email or "").strip() or None
    if not nome:
        raise ValueError("Dê um nome ao contato externo.")
    if meio == "whatsapp" and not telefone:
        raise ValueError("Informe o telefone (WhatsApp) do contato externo.")
    if meio == "email" and not email:
        raise ValueError("Informe o e-mail do contato externo.")
    # dedup pelo contato do MEIO (não misturar com IS NULL do outro campo — casaria linhas erradas)
    if meio == "whatsapp":
        ja = db.query(ConversaParticipanteExterno).filter_by(
            conversa_id=conversa.id, meio="whatsapp", telefone=telefone).first()
    else:
        ja = db.query(ConversaParticipanteExterno).filter_by(
            conversa_id=conversa.id, meio="email", email=email).first()
    if ja is not None:
        ja.removido = 0; ja.nome = nome; db.flush(); return ja
    e = ConversaParticipanteExterno(conversa_id=conversa.id, nome=nome, telefone=telefone,
                                    email=email, meio=meio, criado_por_id=criado_por_id)
    db.add(e); db.flush()
    return e


def remover_externo(db, conversa, externo_id):
    e = (db.query(ConversaParticipanteExterno)
           .filter_by(id=int(externo_id), conversa_id=conversa.id).first())
    if e is None:
        return False
    e.removido = 1; db.flush()
    return True


# ── Biblioteca de templates da Meta (RF-07, Fatia 2) ────────────────────────────────────────────

def _serializar_template(t):
    return {"id": t.id, "segmento": t.segmento, "slot_obrigatorio": t.slot_obrigatorio,
            "nome_meta": t.nome_meta, "categoria": t.categoria, "idioma": t.idioma,
            "corpo": t.corpo, "variaveis": (json.loads(t.variaveis_json) if t.variaveis_json else []),
            "assinatura_var": t.assinatura_var, "status": t.status,
            "meta_template_id": t.meta_template_id, "ativo": bool(t.ativo)}


def listar_templates(db, loja_id, segmento=None, so_ativos=True):
    q = db.query(TemplateMensagem).filter_by(loja_id=loja_id)
    if so_ativos:
        q = q.filter(TemplateMensagem.ativo == 1)
    if segmento:
        q = q.filter(TemplateMensagem.segmento == segmento)
    return [_serializar_template(t) for t in
            q.order_by(TemplateMensagem.slot_obrigatorio.asc().nullslast(),
                       TemplateMensagem.id.asc()).all()]


def _valida_template(dados):
    seg = dados.get("segmento") or None
    if seg is not None and seg not in SEGMENTOS:
        raise ValueError("Segmento inválido.")
    slot = dados.get("slot_obrigatorio")
    if slot in ("", None):
        slot = None
    else:
        try:
            slot = int(slot)
        except (TypeError, ValueError):
            raise ValueError("Slot obrigatório inválido.")
        if slot not in _SLOTS_NUM:
            raise ValueError("Slot obrigatório fora de 1..9.")
    if not (dados.get("nome_meta") or "").strip():
        raise ValueError("Informe o nome do template na Meta.")
    cat = dados.get("categoria") or "utility"
    if cat not in ("utility", "marketing"):
        raise ValueError("Categoria inválida (utility|marketing).")
    st = dados.get("status") or "rascunho"
    if st not in ("rascunho", "em_analise", "aprovado", "rejeitado"):
        raise ValueError("Status inválido.")
    return seg, slot, cat, st


def _slot_livre(db, loja_id, slot, exceto_id=None):
    if slot is None:
        return True
    q = db.query(TemplateMensagem).filter_by(loja_id=loja_id, slot_obrigatorio=slot, ativo=1)
    if exceto_id is not None:
        q = q.filter(TemplateMensagem.id != exceto_id)
    return q.first() is None


def criar_template(db, loja_id, dados, criado_por_id=None):
    """Cria um template da loja. Um slot obrigatório (1..9) tem no máximo UM template ativo por loja."""
    seg, slot, cat, st = _valida_template(dados)
    if not _slot_livre(db, loja_id, slot):
        raise ValueError("Já existe um template ativo para este slot obrigatório.")
    t = TemplateMensagem(
        loja_id=loja_id, segmento=seg, slot_obrigatorio=slot, nome_meta=dados["nome_meta"].strip(),
        categoria=cat, idioma=(dados.get("idioma") or "pt_BR"), corpo=dados.get("corpo"),
        variaveis_json=(json.dumps(dados["variaveis"]) if dados.get("variaveis") else None),
        assinatura_var=dados.get("assinatura_var"), status=st,
        meta_template_id=dados.get("meta_template_id"), criado_por_id=criado_por_id)
    db.add(t); db.flush()
    return t


def editar_template(db, loja_id, template_id, dados):
    """Atualiza um template da loja (patch dos campos válidos). Valida unicidade de slot. Retorna o
    registro ou None se não for da loja."""
    t = db.query(TemplateMensagem).filter_by(id=int(template_id), loja_id=loja_id).first()
    if t is None:
        return None
    base = {"segmento": t.segmento, "slot_obrigatorio": t.slot_obrigatorio, "nome_meta": t.nome_meta,
            "categoria": t.categoria, "status": t.status}
    base.update({k: v for k, v in dados.items() if v is not None or k in ("segmento", "slot_obrigatorio")})
    seg, slot, cat, st = _valida_template(base)
    if not _slot_livre(db, loja_id, slot, exceto_id=t.id):
        raise ValueError("Já existe um template ativo para este slot obrigatório.")
    t.segmento, t.slot_obrigatorio, t.categoria, t.status = seg, slot, cat, st
    t.nome_meta = base["nome_meta"].strip()
    for campo in ("idioma", "corpo", "meta_template_id", "assinatura_var"):
        if campo in dados:
            setattr(t, campo, dados[campo])
    if "variaveis" in dados:
        t.variaveis_json = json.dumps(dados["variaveis"]) if dados["variaveis"] else None
    db.flush()
    return t


def remover_template(db, loja_id, template_id):
    """Soft-delete (ativo=0) — libera o slot obrigatório. Retorna True se removeu."""
    t = db.query(TemplateMensagem).filter_by(id=int(template_id), loja_id=loja_id).first()
    if t is None:
        return False
    t.ativo = 0; db.flush()
    return True


# ── Configuração de triagem (RF-08, Fatia 6) ────────────────────────────────────────────────────

_TRIAGEM_ROTULOS = {
    "comercial":       "Comercial — vendas e orçamentos",
    "suporte_tecnico": "Suporte Técnico — assistência pós-venda",
    "financeiro":      "Financeiro — pagamentos e cobrança",
    "logistica":       "Logística — entrega e montagem",
    "parceiros":       "Parceiros — indicações e comissões",
    "sac":             "SAC / Ouvidoria — reclamações e atendimento institucional",
    "compras":         "Compras — fornecedores",
}
# Os 7 segmentos aparecem na config. No cliente: comercial/suporte/financeiro/logística/parceiros/SAC
# ativos; COMPRAS entra desativado (é só fornecedor, não é triagem de cliente). A loja pode ligar/desligar.
_TRIAGEM_ORDEM = ("comercial", "suporte_tecnico", "financeiro", "logistica", "parceiros", "sac", "compras")
_TRIAGEM_MSG_PADRAO = ("Olá! Em que podemos ajudar? Nossa equipe vai direcionar seu atendimento para o "
                       "setor certo.")


def _triagem_default():
    return {"formato": "lista", "mensagem_livre": _TRIAGEM_MSG_PADRAO,
            "itens": [{"segmento": s, "rotulo": _TRIAGEM_ROTULOS[s], "ativo": (s != "compras")}
                      for s in _TRIAGEM_ORDEM]}


def triagem_config_get(db, loja_id):
    c = db.query(TriagemConfig).filter_by(loja_id=loja_id).first()
    if c is None:
        return _triagem_default()
    itens = json.loads(c.itens_json) if c.itens_json else _triagem_default()["itens"]
    return {"formato": c.formato, "mensagem_livre": c.mensagem_livre or _TRIAGEM_MSG_PADRAO,
            "itens": itens}


def triagem_config_salvar(db, loja_id, dados):
    formato = dados.get("formato") if dados.get("formato") in ("lista", "livre") else "lista"
    itens = []
    for it in (dados.get("itens") or []):
        seg = it.get("segmento")
        if seg in SEGMENTOS:
            itens.append({"segmento": seg, "rotulo": (it.get("rotulo") or "").strip() or seg,
                          "ativo": bool(it.get("ativo"))})
    c = db.query(TriagemConfig).filter_by(loja_id=loja_id).first()
    if c is None:
        c = TriagemConfig(loja_id=loja_id); db.add(c)
    c.formato = formato
    c.mensagem_livre = (dados.get("mensagem_livre") or "").strip() or _TRIAGEM_MSG_PADRAO
    c.itens_json = json.dumps(itens) if itens else None
    db.flush()
    return triagem_config_get(db, loja_id)


# ── Configuração de segmentos (RF-02) ───────────────────────────────────────────────────────────

_SEGMENTO_ROTULOS = {"comercial": "Comercial", "suporte_tecnico": "Suporte Técnico",
                     "financeiro": "Financeiro", "logistica": "Logística", "parceiros": "Parceiros",
                     "compras": "Compras", "sac": "SAC"}
_SEGMENTO_ORDEM = ("comercial", "suporte_tecnico", "financeiro", "logistica", "parceiros", "compras", "sac")


def segmentos_config_get(db, loja_id):
    """Os 7 segmentos com o config da loja (ativo/rótulo/template padrão) + os templates de cada um
    (para o seletor). Sem linha salva → padrão (ativo, rótulo do catálogo)."""
    salvos = {c.segmento: c for c in db.query(SegmentoConfig).filter_by(loja_id=loja_id).all()}
    out = []
    for seg in _SEGMENTO_ORDEM:
        c = salvos.get(seg)
        out.append({"segmento": seg,
                    "rotulo": (c.rotulo if (c and c.rotulo) else _SEGMENTO_ROTULOS.get(seg, seg)),
                    "ativo": (bool(c.ativo) if c else True),
                    "template_padrao_id": (c.template_padrao_id if c else None),
                    "templates": listar_templates(db, loja_id, segmento=seg)})
    return out


def segmentos_config_salvar(db, loja_id, itens):
    for it in (itens or []):
        seg = it.get("segmento")
        if seg not in SEGMENTOS:
            continue
        c = db.query(SegmentoConfig).filter_by(loja_id=loja_id, segmento=seg).first()
        if c is None:
            c = SegmentoConfig(loja_id=loja_id, segmento=seg); db.add(c)
        c.ativo = 1 if it.get("ativo", True) else 0
        c.rotulo = (it.get("rotulo") or "").strip() or None
        tpid = it.get("template_padrao_id")
        if tpid:                                            # valida: template da loja E do segmento
            t = db.query(TemplateMensagem).filter_by(id=int(tpid), loja_id=loja_id).first()
            c.template_padrao_id = t.id if (t and t.segmento == seg) else None
        else:
            c.template_padrao_id = None
    db.flush()
    return segmentos_config_get(db, loja_id)


def _email_do_usuario(db, usuario_id):
    """E-mail de um usuário: Usuario.email; fallback ao e-mail do Funcionário vinculado."""
    u = db.get(Usuario, usuario_id) if usuario_id else None
    if u is None:
        return None
    if (getattr(u, "email", None) or "").strip():
        return u.email.strip()
    fid = getattr(u, "funcionario_id", None)
    f = db.get(Funcionario, fid) if fid else db.query(Funcionario).filter_by(usuario_id=usuario_id).first()
    return f.email.strip() if (f and (f.email or "").strip()) else None


def oficializar_por_email(db, conversa, mensagem, autor_nome=None):
    """F3 (caixa de e-mail): ENCAMINHA a mensagem por e-mail a TODOS os integrantes — internos (pelo
    e-mail cadastrado) e externos. Serve para oficializar informação e encaminhar documentos. CONFIG-
    GATED (SMTP) via mod_chat_externo: sem credencial → 'pendente_config' (a rede não é tocada). Não
    commita. Retorna {total, enviados, pendentes}."""
    import mod_chat_externo
    dests, vistos = [], set()
    for p in db.query(ConversaParticipante).filter_by(conversa_id=conversa.id, removido=0).all():
        email = _email_do_usuario(db, p.usuario_id)
        if email and email.lower() not in vistos:
            vistos.add(email.lower()); dests.append({"id": p.usuario_id, "email": email})
    for e in db.query(ConversaParticipanteExterno).filter_by(conversa_id=conversa.id, removido=0).all():
        email = (e.email or "").strip()
        if email and email.lower() not in vistos:
            vistos.add(email.lower()); dests.append({"id": None, "email": email})
    corpo = "📢 Comunicação oficial — %s\n\n%s" % (
        autor_nome or "Orizon Chat", (mensagem.corpo or "").strip() or "(documento/anexo na conversa)")
    envs = mod_chat_externo.notificar_gerentes_email(db, mensagem, dests, corpo)
    return {"total": len(envs),
            "enviados": sum(1 for x in envs if x.status == "enviado"),
            "pendentes": sum(1 for x in envs if x.status == "pendente_config")}


def gerir_participante(db, conversa, usuario_id, acao):
    """Override manual do gerente: 'add' (entra/reativa como manual) | 'remove' (tombstone
    removido=1 — o sync não readiciona, mesmo sendo derivado). Não commita."""
    usuario_id = int(usuario_id)
    p = (db.query(ConversaParticipante)
           .filter_by(conversa_id=conversa.id, usuario_id=usuario_id).first())
    if acao == "add":
        if p is None:
            db.add(ConversaParticipante(conversa_id=conversa.id, usuario_id=usuario_id,
                                        papel="membro", origem="manual", removido=0))
        else:
            p.removido = 0
    elif acao == "remove":
        if p is None:
            db.add(ConversaParticipante(conversa_id=conversa.id, usuario_id=usuario_id,
                                        papel="membro", origem="auto", removido=1))
        else:
            p.removido = 1
    else:
        raise ValueError("Ação inválida (add|remove).")
    db.flush()


def _usuarios_gerencia_loja(db, loja_id):
    """Usuários ATIVOS da loja cujo perfil é GERÊNCIA (capacidade `autorizar` OU `aprovar_financeiro`
    = Diretor/Gerentes). Participam POR PADRÃO de toda conversa de projeto (decisão do lojista
    2026-07-27); podem se auto-excluir via override manual (`removido=1`), respeitado pelo sync."""
    from auth import perfis
    out = []
    for u in db.query(Usuario).filter_by(loja_id=loja_id, ativo=1).all():
        n = getattr(u, "nivel", None)
        if n and (perfis.pode(n, "autorizar") or perfis.pode(n, "aprovar_financeiro")):
            out.append(u.id)
    return out


def sincronizar_participantes_projeto(db, conversa, membros_usuarios):
    """Sincroniza os participantes de uma CONVERSA DE PROJETO com o conjunto DERIVADO = equipe
    (membros_usuarios) ∪ GERÊNCIA da loja (Diretor/Gerentes, sempre). Regra 'override vence':
    adição manual (origem='manual') fica; remoção manual de um auto (removido=1) é respeitada (não
    readiciona — inclusive a auto-exclusão de um gerente); auto que saiu do time é removido. Não
    commita. Retorna a lista atual de usuarios participantes."""
    D = {int(u) for u in (membros_usuarios or []) if u}
    D |= {int(u) for u in _usuarios_gerencia_loja(db, conversa.loja_id)}   # gerência por padrão
    rows = {p.usuario_id: p for p in db.query(ConversaParticipante)
            .filter_by(conversa_id=conversa.id).all()}
    for uid in D:
        p = rows.get(uid)
        if p is None:
            db.add(ConversaParticipante(conversa_id=conversa.id, usuario_id=uid,
                                        papel="membro", origem="auto", removido=0))
        # p existente (auto presente, auto-removido-manual, ou manual) → não mexe
    for uid, p in rows.items():
        if p.origem == "auto" and not p.removido and uid not in D:
            db.delete(p)                       # deixou o time → sai (manual/removidos ficam)
    db.flush()
    return [p.usuario_id for p in db.query(ConversaParticipante)
            .filter(ConversaParticipante.conversa_id == conversa.id,
                    ConversaParticipante.removido == 0).all()]


# ── Assunto (Orizon Chat, Fatia 2) ────────────────────────────────────────────
ASSUNTO_TIPOS = ("livre", "projeto", "custom")


def normalizar_assunto(db, loja_id, assunto_tipo, projeto_nome=None, assunto_id=None):
    """Valida e devolve (assunto_tipo, projeto_nome, assunto_id) prontos p/ gravar. 'livre' zera
    tudo; 'projeto' exige projeto_nome; 'custom' exige um Assunto ATIVO da loja."""
    at = (assunto_tipo or "livre").strip()
    if at not in ASSUNTO_TIPOS:
        raise ValueError("Assunto inválido.")
    if at == "projeto":
        if not projeto_nome:
            raise ValueError("Escolha o projeto do assunto.")
        return ("projeto", projeto_nome, None)
    if at == "custom":
        a = db.get(Assunto, int(assunto_id)) if assunto_id else None
        if a is None or a.loja_id != loja_id or not a.ativo:
            raise ValueError("Assunto inexistente nesta loja.")
        return ("custom", None, a.id)
    return ("livre", None, None)


def criar_assunto(db, loja_id, criado_por_id, nome):
    """Cria (ou reaproveita) um assunto custom por nome na loja."""
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Dê um nome ao assunto.")
    existente = (db.query(Assunto)
                   .filter(Assunto.loja_id == loja_id, Assunto.ativo == 1,
                           func.lower(Assunto.nome) == nome.lower())
                   .first())
    if existente is not None:
        return existente
    a = Assunto(loja_id=loja_id, nome=nome, criado_por_id=criado_por_id)
    db.add(a); db.flush()
    return a


def listar_assuntos(db, loja_id):
    """Assuntos custom ativos da loja (para o seletor 'Assunto')."""
    return [{"id": a.id, "nome": a.nome}
            for a in db.query(Assunto)
                       .filter(Assunto.loja_id == loja_id, Assunto.ativo == 1)
                       .order_by(Assunto.nome.asc()).all()]


def _assunto_do(db, c):
    """Rótulo/estrutura do assunto de uma conversa, para serialização."""
    at = c.assunto_tipo or ("projeto" if c.projeto_nome else "livre")
    if at == "projeto":
        return {"tipo": "projeto", "label": c.projeto_nome or "Projeto",
                "projeto_nome": c.projeto_nome, "assunto_id": None}
    if at == "custom" and c.assunto_id:
        a = db.get(Assunto, c.assunto_id)
        return {"tipo": "custom", "label": (a.nome if a else "Assunto"),
                "projeto_nome": None, "assunto_id": c.assunto_id}
    return {"tipo": "livre", "label": "Conversa Livre", "projeto_nome": None, "assunto_id": None}


def get_or_create_direct(db, loja_id, criado_por_id, outro_usuario_id,
                         assunto_tipo="livre", projeto_nome=None, assunto_id=None):
    """Conversa 1:1 canônica entre dois usuários da loja PARA UM ASSUNTO (idempotente pela dupla
    + assunto). Directs da mesma dupla com assuntos diferentes são threads distintas."""
    if not outro_usuario_id or int(outro_usuario_id) == int(criado_por_id):
        raise ValueError("Escolha outro usuário para a conversa direta.")
    outro_usuario_id = int(outro_usuario_id)
    at, pnome, aid = normalizar_assunto(db, loja_id, assunto_tipo, projeto_nome, assunto_id)
    minhas = {r[0] for r in db.query(ConversaParticipante.conversa_id)
              .filter_by(usuario_id=criado_por_id).all()}
    do_outro = {r[0] for r in db.query(ConversaParticipante.conversa_id)
                .filter_by(usuario_id=outro_usuario_id).all()}
    comuns = minhas & do_outro
    if comuns:
        c = (db.query(Conversa)
               .filter(Conversa.id.in_(comuns), Conversa.loja_id == loja_id,
                       Conversa.tipo == "direct", Conversa.assunto_tipo == at,
                       Conversa.projeto_nome == pnome, Conversa.assunto_id == aid)
               .order_by(Conversa.id.asc()).first())
        if c is not None:
            return c
    c = Conversa(loja_id=loja_id, tipo="direct", criado_por_id=criado_por_id,
                 assunto_tipo=at, projeto_nome=pnome, assunto_id=aid)
    db.add(c); db.flush()
    db.add_all([ConversaParticipante(conversa_id=c.id, usuario_id=criado_por_id),
                ConversaParticipante(conversa_id=c.id, usuario_id=outro_usuario_id)])
    db.flush()
    return c


def criar_grupo(db, loja_id, criado_por_id, titulo, participante_ids,
                assunto_tipo="livre", projeto_nome=None, assunto_id=None, exige_dois=True):
    """Cria uma conversa de grupo com título, assunto e N participantes (criador = admin). `exige_dois`
    pode ser False quando o grupo terá participantes EXTERNOS (criador + externo já basta)."""
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Dê um nome ao grupo.")
    at, pnome, aid = normalizar_assunto(db, loja_id, assunto_tipo, projeto_nome, assunto_id)
    ids = {int(x) for x in (participante_ids or []) if x} | {int(criado_por_id)}
    if exige_dois and len(ids) < 2:
        raise ValueError("Um grupo precisa de ao menos 2 participantes.")
    c = Conversa(loja_id=loja_id, tipo="grupo", titulo=titulo, criado_por_id=criado_por_id,
                 assunto_tipo=at, projeto_nome=pnome, assunto_id=aid)
    db.add(c); db.flush()
    for uid in ids:
        db.add(ConversaParticipante(conversa_id=c.id, usuario_id=uid,
                                    papel="admin" if uid == int(criado_por_id) else "membro"))
    db.flush()
    return c


def _nomes_participantes(db, conversa_id):
    rows = (db.query(Usuario.nome)
              .join(ConversaParticipante, ConversaParticipante.usuario_id == Usuario.id)
              .filter(ConversaParticipante.conversa_id == conversa_id)
              .order_by(Usuario.nome.asc()).all())
    return [r[0] for r in rows]


def listar_todas_conversas(db, loja_id, participante_id=None,
                           assunto_tipo=None, assunto_ref=None):
    """ADMIN (ver_todas_conversas): TODAS as conversas direct/grupo da loja, com filtro opcional
    por participante e por assunto. `assunto_ref` = projeto_nome (tipo projeto) ou id (custom)."""
    q = (db.query(Conversa)
           .filter(Conversa.loja_id == loja_id, Conversa.tipo.in_(("direct", "grupo"))))
    if assunto_tipo:
        q = q.filter(Conversa.assunto_tipo == assunto_tipo)
        if assunto_tipo == "projeto" and assunto_ref:
            q = q.filter(Conversa.projeto_nome == assunto_ref)
        if assunto_tipo == "custom" and assunto_ref:
            q = q.filter(Conversa.assunto_id == int(assunto_ref))
    if participante_id:
        ids = {r[0] for r in db.query(ConversaParticipante.conversa_id)
               .filter_by(usuario_id=int(participante_id)).all()}
        q = q.filter(Conversa.id.in_(ids or {-1}))
    convs = q.all()
    itens = []
    for c in convs:
        nomes = _nomes_participantes(db, c.id)
        ultima = (db.query(ConversaMensagem).filter_by(conversa_id=c.id)
                    .order_by(ConversaMensagem.criado_em.desc(), ConversaMensagem.id.desc()).first())
        itens.append({
            "id": c.id, "tipo": c.tipo,
            "titulo": c.titulo or (" ↔ ".join(nomes) if c.tipo == "direct" else "Conversa"),
            "participantes": nomes, "assunto": _assunto_do(db, c),
            "ultima_previa": (("" if ultima is None else
                               (MASCARA_PRIVADA if ultima.privada else (ultima.corpo or "")))[:120]),
            "ultima_em": ultima.criado_em.isoformat() if (ultima and ultima.criado_em) else None,
            "criado_em": c.criado_em.isoformat() if c.criado_em else None,
        })
    itens.sort(key=lambda x: (x["ultima_em"] or x["criado_em"] or ""), reverse=True)
    return itens


# ── Canais públicos: Mural + Fóruns (Fatia 4) ─────────────────────────────────
TIPOS_PUBLICOS = ("mural", "forum_loja", "forum_orizon")


def _rede_da_loja(db, loja_id):
    from database import Loja
    l = db.get(Loja, loja_id) if loja_id else None
    return l.rede_id if l else None


def get_or_create_mural(db, loja_id):
    """Mural de AVISOS da loja (Fatia 4): conversa única tipo='mural'. Todos leem; só gerência
    posta (regra em pode_escrever_conversa). get-or-create idempotente."""
    c = (db.query(Conversa)
           .filter_by(loja_id=loja_id, tipo="mural")
           .order_by(Conversa.id.asc()).first())
    if c is None:
        c = Conversa(loja_id=loja_id, tipo="mural", titulo="Mural da loja", assunto_tipo="livre")
        db.add(c); db.flush()
    return c


def criar_debate(db, escopo, loja_id, rede_id, criado_por_id, titulo,
                 assunto_tipo="livre", projeto_nome=None, assunto_id=None):
    """Cria um DEBATE (tópico) no Fórum da Loja (escopo='loja') ou no Fórum Orizon
    (escopo='orizon', cross-loja pela rede). Título obrigatório + assunto (reusa Assunto)."""
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Dê um título ao debate.")
    if escopo == "orizon":
        if not rede_id:
            raise ValueError("Sua loja não está associada a uma rede — sem Fórum Orizon.")
        # assunto custom/projeto é por loja; no fórum da rede só 'livre' (título organiza).
        c = Conversa(loja_id=loja_id, rede_id=rede_id, tipo="forum_orizon",
                     titulo=titulo, criado_por_id=criado_por_id, assunto_tipo="livre")
    else:
        at, pnome, aid = normalizar_assunto(db, loja_id, assunto_tipo, projeto_nome, assunto_id)
        c = Conversa(loja_id=loja_id, tipo="forum_loja", titulo=titulo,
                     criado_por_id=criado_por_id, assunto_tipo=at, projeto_nome=pnome, assunto_id=aid)
    db.add(c); db.flush()
    return c


def listar_debates(db, escopo, loja_id, rede_id, q=None, assunto_tipo=None, assunto_ref=None):
    """Debates de um fórum, mais recentes primeiro, com busca por título (q) e filtro de assunto.
    escopo='loja' → forum_loja da loja; 'orizon' → forum_orizon da rede."""
    if escopo == "orizon":
        if not rede_id:
            return []
        query = db.query(Conversa).filter(Conversa.rede_id == rede_id,
                                          Conversa.tipo == "forum_orizon")
    else:
        query = db.query(Conversa).filter(Conversa.loja_id == loja_id,
                                          Conversa.tipo == "forum_loja")
    if q:
        query = query.filter(Conversa.titulo.ilike("%" + q.strip() + "%"))
    if assunto_tipo:
        query = query.filter(Conversa.assunto_tipo == assunto_tipo)
        if assunto_tipo == "projeto" and assunto_ref:
            query = query.filter(Conversa.projeto_nome == assunto_ref)
        if assunto_tipo == "custom" and assunto_ref:
            query = query.filter(Conversa.assunto_id == int(assunto_ref))
    convs = query.all()
    itens = []
    for c in convs:
        ultima = (db.query(ConversaMensagem).filter_by(conversa_id=c.id)
                    .order_by(ConversaMensagem.criado_em.desc(), ConversaMensagem.id.desc()).first())
        n = (db.query(ConversaMensagem).filter_by(conversa_id=c.id).count())
        itens.append({
            "id": c.id, "tipo": c.tipo, "titulo": c.titulo or "Debate",
            "assunto": _assunto_do(db, c), "n_mensagens": n,
            "criado_por_nome": (db.get(Usuario, c.criado_por_id).nome
                                if c.criado_por_id and db.get(Usuario, c.criado_por_id) else None),
            "loja_nome": (_nome_loja(db, c.loja_id) if escopo == "orizon" else None),
            "ultima_em": ultima.criado_em.isoformat() if (ultima and ultima.criado_em) else None,
            "criado_em": c.criado_em.isoformat() if c.criado_em else None,
        })
    itens.sort(key=lambda x: (x["ultima_em"] or x["criado_em"] or ""), reverse=True)
    return itens


def _nome_loja(db, loja_id):
    from database import Loja
    l = db.get(Loja, loja_id) if loja_id else None
    return l.nome if l else None


def pode_ler_conversa(db, c, loja_id, usuario_id, rede_id=None):
    """Leitura: mural/forum_loja = usuário da loja; forum_orizon = usuário de loja da MESMA rede;
    direct/grupo = participante."""
    if c is None:
        return False
    if c.tipo == "forum_orizon":
        return rede_id is not None and c.rede_id == rede_id
    if c.loja_id != loja_id:
        return False
    if c.tipo in ("mural", "forum_loja", "publico"):
        return True
    return eh_participante(db, c.id, usuario_id)


def pode_escrever_conversa(db, c, loja_id, usuario_id, rede_id=None, is_admin_chat=False):
    """Escrita: igual à leitura, EXCETO o mural (só gerência posta — is_admin_chat)."""
    if not pode_ler_conversa(db, c, loja_id, usuario_id, rede_id=rede_id):
        return False
    if c.tipo == "mural":
        return bool(is_admin_chat)
    return True


def _ultimo_id_mensagem(db, conversa_id):
    r = (db.query(ConversaMensagem.id).filter_by(conversa_id=conversa_id)
           .order_by(ConversaMensagem.id.desc()).first())
    return r[0] if r else 0


def marcar_lido(db, conversa, usuario_id):
    """Marca a conversa como lida até a última mensagem para o usuário. Para público (sem linha de
    participante) cria a linha SÓ para guardar o marcador de leitura — não muda a audiência."""
    ultimo = _ultimo_id_mensagem(db, conversa.id)
    p = (db.query(ConversaParticipante)
           .filter_by(conversa_id=conversa.id, usuario_id=usuario_id).first())
    if p is None:
        # em direct/grupo, não-participante (ex.: gerente em oversight) não vira participante;
        # nos canais públicos (mural/fórum) a linha é só marcador de leitura.
        if conversa.tipo in ("direct", "grupo", "projeto"):
            return
        p = ConversaParticipante(conversa_id=conversa.id, usuario_id=usuario_id,
                                 papel="membro", lido_ate_mensagem_id=ultimo)
        db.add(p)
    else:
        p.lido_ate_mensagem_id = ultimo
    db.flush()


def _conta_nao_lidas(db, conversa_id, usuario_id, lido_ate):
    """Mensagens acima do marcador de leitura que NÃO foram escritas pelo próprio usuário."""
    return (db.query(ConversaMensagem)
              .filter(ConversaMensagem.conversa_id == conversa_id,
                      ConversaMensagem.id > (lido_ate or 0),
                      (ConversaMensagem.autor_usuario_id != usuario_id)
                      | (ConversaMensagem.autor_usuario_id.is_(None)))
              .count())


def serializar_conversa(db, c, viewer_id, ultima=None, participantes=None, nao_lidas=0):
    """Item da inbox: id/tipo/título de exibição + prévia da última mensagem. Para direct, o
    'titulo' de exibição é o nome do OUTRO participante (visto pelo `viewer_id`)."""
    titulo = c.titulo
    outro_id = None
    if c.tipo in ("mural", "publico"):
        titulo = "📣 Mural da loja"
    if c.tipo == "projeto":
        titulo = "📁 " + ((c.projeto_nome or "Projeto").replace("_", " "))
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
        "assunto": _assunto_do(db, c),
        "nao_lidas": nao_lidas,
        "ultima_previa": previa[:120],
        "ultima_em": ultima.criado_em.isoformat() if (ultima and ultima.criado_em) else None,
        "criado_em": c.criado_em.isoformat() if c.criado_em else None,
    }


def listar_inbox(db, loja_id, usuario_id):
    """Inbox: o mural PÚBLICO da loja + conversas direct/grupo do usuário, mais recentes primeiro,
    cada uma com contagem de não-lidas. O público é sempre incluído (audiência = a loja)."""
    # marcador de leitura por conversa (linhas de participante do usuário, exceto removidos)
    lido = {p.conversa_id: (p.lido_ate_mensagem_id or 0)
            for p in db.query(ConversaParticipante)
            .filter(ConversaParticipante.usuario_id == usuario_id,
                    ConversaParticipante.removido == 0).all()}
    conv_ids = list(lido.keys())
    convs = (db.query(Conversa)
               .filter(Conversa.id.in_(conv_ids or [-1]), Conversa.loja_id == loja_id,
                       Conversa.tipo.in_(("direct", "grupo", "projeto"))).all()) if conv_ids else []
    mural = get_or_create_mural(db, loja_id)
    convs = [mural] + [c for c in convs if c.id != mural.id]
    itens = [serializar_conversa(db, c, usuario_id,
                                 nao_lidas=_conta_nao_lidas(db, c.id, usuario_id, lido.get(c.id, 0)))
             for c in convs]
    # mural sempre no topo; o resto por recência (desc)
    tops = [x for x in itens if x["tipo"] in ("mural", "publico")]
    resto = sorted([x for x in itens if x["tipo"] not in ("mural", "publico")],
                   key=lambda x: (x["ultima_em"] or x["criado_em"] or ""), reverse=True)
    return tops + resto


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
