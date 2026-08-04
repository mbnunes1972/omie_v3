# -*- coding: utf-8 -*-
"""chat/triagem.py — resolução humana da FILA DE TRIAGEM (spec
_geral/2026-07-31-triagem-pipeline-entrada-design.md). A persistência da fila acontece em
externo.processar_entrada (idempotente por wamid); aqui vivem a listagem (tenancy por loja)
e as 3 saídas: vincular · criar (lead novo) · descartar (registro, não delete)."""
import json
from datetime import datetime

from database import EnvioExterno, Cliente, Usuario, TriagemEntrada

from .externo import _canal_do_thread, registrar_envio  # noqa: F401  (canal do fio externo)


def serializar_triagem(e):
    return {"id": e.id, "meio": e.meio, "remetente": e.remetente, "texto": e.texto,
            "status": e.status,
            "candidatos": (json.loads(e.candidatos_json) if e.candidatos_json else []),
            "segmento_sugerido": e.segmento_sugerido,
            "conversa_id": e.conversa_id,
            "criado_em": e.criado_em.isoformat() if e.criado_em else None}


def triagem_listar(db, loja_id, status="pendente"):
    """Entradas da fila da LOJA (tenancy), mais antigas primeiro (ordem de chegada)."""
    q = db.query(TriagemEntrada).filter_by(loja_id=loja_id)
    if status:
        q = q.filter(TriagemEntrada.status == status)
    return [serializar_triagem(e) for e in q.order_by(TriagemEntrada.id.asc()).all()]


def _triagem_marcar(db, entrada, status, usuario_id, conversa_id=None):
    entrada.status = status
    entrada.resolvido_por_id = usuario_id
    entrada.resolvido_em = datetime.utcnow()
    entrada.conversa_id = conversa_id
    db.flush()


def _triagem_postar_na_conversa(db, entrada, conversa, usuario_id):
    """Entrega a mensagem original na conversa (autor NULL = externa) + EnvioExterno de entrada
    com o wamid (mantém idempotência e janela) + EVENTO inline do vínculo (decisão 5)."""
    from . import core as _mc
    canal = _canal_do_thread(db, conversa.id, entrada.meio, entrada.remetente)
    msg = _mc.enviar_mensagem(db, conversa, None, entrada.texto or "(sem texto)", canal=canal,
                              _permitir_externo=True)
    db.add(EnvioExterno(mensagem_id=msg.id, meio=entrada.meio, direcao="entrada", canal=canal,
                        destino=entrada.remetente, status="recebido",
                        id_externo=entrada.id_externo, id_externo_ref=entrada.id_externo_ref))
    u = db.get(Usuario, usuario_id) if usuario_id else None
    corpo_ev = "Contato %s vinculado por %s via triagem" % (
        entrada.remetente, (u.nome if u else "—"))
    _mc.enviar_mensagem(db, conversa, usuario_id, corpo_ev, evento="triagem_vinculo")
    db.flush()
    return msg


def _aplicar_segmento(db, conversa, entrada, segmento):
    """r3: o segmento escolhido na resolução (ou o indicado pela triagem automática —
    `segmento_sugerido`) vira o segmento MANUAL da conversa. Sem nenhum dos dois, fica sem
    segmento — a gerência trata depois pelo seletor do thread."""
    from . import core as _mc
    seg = (segmento or "").strip() or entrada.segmento_sugerido
    if seg:
        _mc.definir_segmento(db, conversa, seg)


def triagem_resolver_vincular(db, entrada, conversa, usuario_id, segmento=None):
    """Vincula a entrada a uma conversa EXISTENTE (candidata ou escolhida). Não commita."""
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    if conversa is None or conversa.loja_id != entrada.loja_id:
        raise ValueError("Conversa inexistente nesta loja.")
    msg = _triagem_postar_na_conversa(db, entrada, conversa, usuario_id)
    _aplicar_segmento(db, conversa, entrada, segmento)
    _triagem_marcar(db, entrada, "resolvido", usuario_id, conversa_id=conversa.id)
    return msg


def triagem_resolver_criar(db, entrada, usuario_id, nome_cliente, segmento=None):
    """Lead NOVO por WhatsApp: cria o Cliente (contato no cadastro — decisão 12) + uma conversa
    de GRUPO com o resolvedor dentro e o contato como participante EXTERNO (as respostas da
    equipe espelham pelo transporte). A mensagem original entra na conversa. Não commita."""
    from . import core as _mc
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    nome_cliente = (nome_cliente or "").strip()
    if not nome_cliente:
        raise ValueError("Dê um nome ao novo cliente.")
    cli = Cliente(nome=nome_cliente, loja_id=entrada.loja_id,
                  whatsapp=(entrada.remetente if entrada.meio == "whatsapp" else None),
                  email=(entrada.remetente if entrada.meio == "email" else None))
    db.add(cli); db.flush()
    conv = _mc.criar_grupo(db, entrada.loja_id, usuario_id, "Lead — %s" % nome_cliente,
                           [usuario_id], exige_dois=False)
    _mc.adicionar_externo(db, conv, nome_cliente,
                          telefone=(entrada.remetente if entrada.meio == "whatsapp" else None),
                          email=(entrada.remetente if entrada.meio == "email" else None),
                          meio=entrada.meio, criado_por_id=usuario_id)
    _triagem_postar_na_conversa(db, entrada, conv, usuario_id)
    _aplicar_segmento(db, conv, entrada, segmento)
    _triagem_marcar(db, entrada, "resolvido", usuario_id, conversa_id=conv.id)
    return conv


def triagem_descartar(db, entrada, usuario_id):
    """Descarta (spam/engano) — é REGISTRO, não delete: a entrada fica auditável. Não commita."""
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    _triagem_marcar(db, entrada, "descartado", usuario_id)
    return entrada

# ── RF-08/09 — triagem AUTOMÁTICA (2026-08-04): pergunta ao contato + leitura da resposta ────
# O contato acabou de escrever → janela de 24h ABERTA → a pergunta sai como texto livre (sem
# template). A resolução continua HUMANA na fila; a resposta do cliente só preenche
# `segmento_sugerido` (o campo esperava esta frente desde a spec 2026-07-31).

_SEG_ROTULOS = {"comercial": "Comercial", "financeiro": "Financeiro", "logistica": "Logística",
                "suporte_tecnico": "Suporte Técnico", "sac": "SAC", "compras": "Compras",
                "parceiros": "Projeto Executivo"}   # chave legada `parceiros` (renomeado 2026-08-04)


def opcoes_pergunta(db, loja_id):
    """[{segmento, rotulo}] ATIVOS, na ordem da pergunta: TriagemConfig.itens_json quando
    configurada; senão SegmentoConfig ativos; senão o catálogo padrão (core.SEGMENTOS)."""
    from .core import SEGMENTOS
    from database import SegmentoConfig, TriagemConfig
    cfg = db.query(TriagemConfig).filter_by(loja_id=loja_id).first() if loja_id else None
    if cfg and cfg.itens_json:
        try:
            itens = [i for i in json.loads(cfg.itens_json) if i.get("ativo", True)]
            if itens:
                return [{"segmento": i["segmento"],
                         "rotulo": i.get("rotulo") or _SEG_ROTULOS.get(i["segmento"], i["segmento"])}
                        for i in itens]
        except (ValueError, KeyError, TypeError):
            pass
    rows = (db.query(SegmentoConfig).filter_by(loja_id=loja_id).all()) if loja_id else []
    cfg_por_seg = {r.segmento: r for r in rows}
    out = []
    for seg in SEGMENTOS:
        r = cfg_por_seg.get(seg)
        if r is not None and not r.ativo:
            continue
        out.append({"segmento": seg,
                    "rotulo": (r.rotulo if (r and r.rotulo) else _SEG_ROTULOS.get(seg, seg))})
    return out


def montar_pergunta_triagem(db, loja_id):
    """(texto, opcoes) da pergunta de triagem. Formato 'livre' usa a mensagem configurada
    (atendente roteia depois); 'lista' numera os segmentos ativos."""
    from database import TriagemConfig
    cfg = db.query(TriagemConfig).filter_by(loja_id=loja_id).first() if loja_id else None
    ops = opcoes_pergunta(db, loja_id)
    if cfg and cfg.formato == "livre" and (cfg.mensagem_livre or "").strip():
        return cfg.mensagem_livre.strip(), ops
    linhas = "\n".join("%d. %s" % (i + 1, o["rotulo"]) for i, o in enumerate(ops))
    texto = ("Olá! 👋 Recebemos sua mensagem. Para agilizar seu atendimento, responda com o "
             "NÚMERO do assunto:\n%s" % linhas)
    return texto, ops


def _normalizar_txt(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").strip().lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def interpretar_resposta_triagem(texto, opcoes):
    """Segmento escolhido pelo cliente, ou None: aceita o NÚMERO da lista ('2', '2.', '2 -')
    ou o NOME/rótulo (sem acento/caixa). Ambíguo/não reconhecido → None (fica pro humano)."""
    t = _normalizar_txt(texto)
    if not t or not opcoes:
        return None
    digitos = "".join(c for c in t if c.isdigit())
    if digitos and t.replace(".", "").replace("-", "").replace(")", "").strip() == digitos:
        n = int(digitos)
        if 1 <= n <= len(opcoes):
            return opcoes[n - 1]["segmento"]
        return None
    for o in opcoes:
        if t == _normalizar_txt(o["rotulo"]) or t == _normalizar_txt(o["segmento"]):
            return o["segmento"]
    return None


def _enviar_texto_triagem(db, entrada, corpo):
    """Envio externo de SISTEMA vinculado à entrada de triagem (sem conversa/mensagem ainda).
    Config-gated como todo envio: sem credencial nasce 'pendente_config'; erro fica gravado.
    Best-effort — NUNCA derruba o processamento do webhook. Não commita."""
    from database import EnvioExterno
    from . import externo as _ext
    env = EnvioExterno(mensagem_id=None, triagem_id=entrada.id, meio=entrada.meio,
                       direcao="saida", destinatario_tipo="cliente",
                       destino=entrada.remetente,
                       status=("enfileirado" if _ext.meio_configurado(entrada.meio)
                               else "pendente_config"))
    db.add(env); db.flush()
    if env.status == "enfileirado":
        ok, id_ext, erro = _ext.despachar(env, corpo)
        env.status = "enviado" if ok else "falhou"
        env.id_externo = id_ext
        env.erro = erro
    db.flush()
    return env


def enviar_pergunta_triagem(db, entrada):
    """RF-08: pergunta de triagem ao contato recém-chegado na fila."""
    corpo, _ops = montar_pergunta_triagem(db, entrada.loja_id)
    return _enviar_texto_triagem(db, entrada, corpo)


def registrar_resposta_triagem(db, entrada, texto):
    """RF-09 (lite): interpreta a resposta do contato que JÁ está na fila. Reconheceu →
    grava `segmento_sugerido` + confirma ao cliente; não reconheceu → anexa o texto à MESMA
    entrada (sem nova pergunta — evita loop de mensagens). Retorna o segmento ou None."""
    _texto = (texto or "").strip()
    if entrada.segmento_sugerido:                      # já escolhido antes: só anexa
        entrada.texto = ((entrada.texto or "") + "\n" + _texto).strip()
        db.flush()
        return entrada.segmento_sugerido
    ops = opcoes_pergunta(db, entrada.loja_id)
    seg = interpretar_resposta_triagem(_texto, ops)
    if seg:
        entrada.segmento_sugerido = seg
        rotulo = next((o["rotulo"] for o in ops if o["segmento"] == seg), seg)
        _enviar_texto_triagem(db, entrada,
                              "Perfeito! ✅ Encaminhei você para %s — em instantes alguém "
                              "da equipe continua o atendimento por aqui." % rotulo)
    else:
        entrada.texto = ((entrada.texto or "") + "\n" + _texto).strip()
    db.flush()
    return seg

