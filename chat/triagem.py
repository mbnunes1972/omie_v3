# -*- coding: utf-8 -*-
"""chat/triagem.py — resolução SEMPRE AUTOMÁTICA da triagem (revisão 2026-08-05, substitui a
fila humana da spec _geral/2026-07-31-triagem-pipeline-entrada-design.md: não existe mais
painel de vincular/criar/descartar). A persistência do buffer acontece em
externo.processar_entrada (idempotente por wamid); aqui vive a materialização: resposta
reconhecida no menu → conversa nasce com esse segmento; sem resposta em 2min
(varrer_triagem_vencida) → nasce com segmento='triagem' (selo próprio) e cai pro SAC
distribuir — SAC transfere pra quem deve atender, e a transferência resolve."""
import json
from datetime import datetime, timedelta

from database import EnvioExterno, Cliente, Conversa, Funcionario, TriagemEntrada

from .externo import (_canal_do_thread, _cliente_por_telefone, _cliente_por_email,
                      registrar_envio)  # noqa: F401  (canal do fio externo)

SEGMENTO_TRIAGEM = "triagem"   # selo próprio (não é um dos 7 de SEGMENTOS) — SAC distribui
MINUTOS_SWEEP = 2


def serializar_triagem(e):
    return {"id": e.id, "meio": e.meio, "remetente": e.remetente, "texto": e.texto,
            "status": e.status,
            "candidatos": (json.loads(e.candidatos_json) if e.candidatos_json else []),
            "segmento_sugerido": e.segmento_sugerido,
            "conversa_id": e.conversa_id,
            "criado_em": e.criado_em.isoformat() if e.criado_em else None}


def triagem_listar(db, loja_id, status="pendente"):
    """Entradas do buffer da LOJA (tenancy), mais antigas primeiro (ordem de chegada) — uso
    interno/depuração; não tem mais tela própria (a resolução é automática)."""
    q = db.query(TriagemEntrada).filter_by(loja_id=loja_id)
    if status:
        q = q.filter(TriagemEntrada.status == status)
    return [serializar_triagem(e) for e in q.order_by(TriagemEntrada.id.asc()).all()]


def _triagem_marcar(db, entrada, conversa_id):
    entrada.status = "resolvido"
    entrada.resolvido_em = datetime.utcnow()
    entrada.conversa_id = conversa_id
    db.flush()


def _triagem_postar_na_conversa(db, entrada, conversa):
    """Entrega a mensagem original na conversa (autor NULL = externa) + EnvioExterno de entrada
    com o wamid (mantém idempotência e janela). Não commita."""
    from . import core as _mc
    canal = _canal_do_thread(db, conversa.id, entrada.meio, entrada.remetente)
    msg = _mc.enviar_mensagem(db, conversa, None, entrada.texto or "(sem texto)", canal=canal,
                              _permitir_externo=True)
    db.add(EnvioExterno(mensagem_id=msg.id, meio=entrada.meio, direcao="entrada", canal=canal,
                        destino=entrada.remetente, status="recebido",
                        id_externo=entrada.id_externo, id_externo_ref=entrada.id_externo_ref))
    db.flush()
    return msg


def _sac_usuario_id(db, loja_id):
    """Usuário (conta de login) do Funcionário com Função 'SAC' da loja — responsável inicial
    de todo atendimento que sai da triagem automática (2026-08-05: SAC recebe e DISTRIBUI;
    quem recebe a transferência assume de verdade). None se ninguém tem essa Função na loja,
    ou tem mas sem conta de login — a conversa nasce sem responsável (só Oversight enxerga até
    alguém assumir manualmente), não trava a materialização."""
    from . import core as _mc
    fid = _mc.responsavel_sac(db, loja_id)
    if not fid:
        return None
    f = db.get(Funcionario, fid)
    return f.usuario_id if f else None


def triagem_materializar(db, entrada, segmento):
    """Resolução ÚNICA e sempre automática: cria o Cliente (se o telefone/e-mail não bate com
    nenhum já cadastrado — decisão 12, contato vira cadastro) + uma conversa de grupo com o
    SAC como responsável inicial + o contato como participante externo. `segmento` é o
    escolhido pelo cliente no menu (já validado em interpretar_resposta_triagem) OU
    SEGMENTO_TRIAGEM quando ninguém respondeu a tempo. Nome do lead: cadastro > perfil do
    WhatsApp (Meta) > o próprio remetente, nessa ordem (pedido 2026-08-05). Não commita."""
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    from . import core as _mc
    cli = (_cliente_por_telefone(db, entrada.remetente) if entrada.meio == "whatsapp"
           else _cliente_por_email(db, entrada.remetente))
    nome = (cli.nome if cli else None) or entrada.nome_whatsapp or entrada.remetente
    if cli is None:
        cli = Cliente(nome=nome, loja_id=entrada.loja_id,
                      whatsapp=(entrada.remetente if entrada.meio == "whatsapp" else None),
                      email=(entrada.remetente if entrada.meio == "email" else None))
        db.add(cli); db.flush()
    sac_uid = _sac_usuario_id(db, entrada.loja_id)
    if sac_uid:
        conv = _mc.criar_grupo(db, entrada.loja_id, sac_uid, "Lead — %s" % nome, [sac_uid],
                               exige_dois=False)
    else:
        conv = Conversa(loja_id=entrada.loja_id, tipo="grupo", titulo="Lead — %s" % nome)
        db.add(conv); db.flush()
    _mc.adicionar_externo(db, conv, nome,
                          telefone=(entrada.remetente if entrada.meio == "whatsapp" else None),
                          email=(entrada.remetente if entrada.meio == "email" else None),
                          meio=entrada.meio, criado_por_id=sac_uid)
    _triagem_postar_na_conversa(db, entrada, conv)
    conv.segmento = segmento
    conv.origem_entrada = "triagem"
    db.flush()
    _triagem_marcar(db, entrada, conv.id)
    return conv


def varrer_triagem_vencida(db, loja_id, minutos=MINUTOS_SWEEP):
    """Checagem PREGUIÇOSA (sem job em background — mesmo padrão da janela de 24h): entradas
    pendentes há mais de `minutos` sem segmento reconhecido materializam com
    SEGMENTO_TRIAGEM (cliente não respondeu / resposta não reconhecida / número ambíguo —
    qualquer caso sem resolução direta cai pro SAC distribuir). Chamada no GET do inbox, então
    "2 minutos" é best-effort (só vence quando alguém carrega a tela de novo), não um timer de
    verdade — aceito pelo pedido original. Não commita; o chamador decide. Best-effort: uma
    entrada problemática não derruba a leitura do inbox de todo mundo."""
    limite = datetime.utcnow() - timedelta(minutes=minutos)
    pendentes = (db.query(TriagemEntrada)
                   .filter(TriagemEntrada.loja_id == loja_id,
                           TriagemEntrada.status == "pendente",
                           TriagemEntrada.criado_em < limite).all())
    for ent in pendentes:
        try:
            triagem_materializar(db, ent, SEGMENTO_TRIAGEM)
        except Exception:
            pass


# ── RF-08/09 — triagem AUTOMÁTICA (2026-08-04): pergunta ao contato + leitura da resposta ────
# O contato acabou de escrever → janela de 24h ABERTA → a pergunta sai como texto livre (sem
# template). A resolução é sempre automática (2026-08-05, triagem_materializar acima): resposta
# reconhecida → materializa na hora com o segmento; sem resposta em 2min → SEGMENTO_TRIAGEM.

_SEG_ROTULOS = {"comercial": "Comercial", "financeiro": "Financeiro", "logistica": "Logística",
                "suporte_tecnico": "Suporte Técnico", "sac": "SAC", "compras": "Compras",
                "parceiros": "Projeto Executivo"}   # chave legada `parceiros` (renomeado 2026-08-04)


def opcoes_pergunta(db, loja_id):
    """[{segmento, rotulo}] ATIVOS, na ordem da pergunta: TriagemConfig.itens_json quando
    configurada; senão o DEFAULT de triagem (rótulos longos, ordem própria, Compras desligado —
    o mesmo que a tela de config mostra), respeitando desativações do SegmentoConfig (RF-02)."""
    from .core import _triagem_default
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
    for it in _triagem_default()["itens"]:
        if not it["ativo"]:
            continue
        r = cfg_por_seg.get(it["segmento"])
        if r is not None and not r.ativo:
            continue
        out.append({"segmento": it["segmento"],
                    "rotulo": (r.rotulo if (r and r.rotulo) else it["rotulo"])})
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

