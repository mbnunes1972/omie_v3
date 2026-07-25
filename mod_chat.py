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

from database import (Conversa, ConversaMensagem, ContatoConfirmacao, Usuario, Cliente,
                      Parceiro, Funcionario, Funcao)

CANAIS = ("interno", "comercial", "financeiro", "logistica", "suporte_tecnico", "sac")
_CANAIS_FATIA_1 = ("interno",)

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
                    bloqueador=False):
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
    if canal not in _CANAIS_FATIA_1:
        raise ValueError("Canal externo ainda não disponível — por ora a conversa é interna.")
    if natureza not in NATUREZAS:
        raise ValueError("natureza inválida: %r (aceitas: %s)" % (natureza, ", ".join(NATUREZAS)))
    if natureza == "transferencia":
        if not transferido_para_funcionario_id:
            raise ValueError("Escolha quem recebe a transferência.")
    else:
        if transferido_para_funcionario_id or etapa_codigo or documento_ref_id or bloqueador:
            raise ValueError("Campos de transferência só valem em natureza=transferencia.")
    m = ConversaMensagem(conversa_id=conversa.id, autor_usuario_id=autor_usuario_id,
                         corpo=corpo, canal=canal, natureza=natureza,
                         etapa_codigo=etapa_codigo,
                         transferido_para_funcionario_id=transferido_para_funcionario_id,
                         documento_ref_id=documento_ref_id,
                         bloqueador=1 if bloqueador else 0)
    db.add(m)
    db.flush()
    return m


def serializar_mensagem(m, autor_nome=None, transferido_nome=None):
    return {"id": m.id, "autor_usuario_id": m.autor_usuario_id,
            "autor_nome": autor_nome or "—", "corpo": m.corpo, "canal": m.canal,
            "natureza": m.natureza or "interacao",
            "etapa_codigo": m.etapa_codigo,
            "transferido_para_funcionario_id": m.transferido_para_funcionario_id,
            "transferido_para_nome": transferido_nome or "",
            "documento_ref_id": m.documento_ref_id,
            "bloqueador": bool(m.bloqueador),
            "resolvido_em": m.resolvido_em.isoformat() if m.resolvido_em else None,
            "criado_em": m.criado_em.isoformat() if m.criado_em else None}


def listar_mensagens(db, conversa_id):
    """Histórico cronológico ASC, com nomes de autor e destinatário resolvidos (outerjoin/
    batch: autor NULL — resposta externa futura — não derruba a listagem)."""
    rows = (db.query(ConversaMensagem, Usuario.nome)
              .outerjoin(Usuario, ConversaMensagem.autor_usuario_id == Usuario.id)
              .filter(ConversaMensagem.conversa_id == conversa_id)
              .order_by(ConversaMensagem.criado_em.asc(), ConversaMensagem.id.asc())
              .all())
    ids_transf = {m.transferido_para_funcionario_id for m, _ in rows
                  if m.transferido_para_funcionario_id}
    nomes = ({f.id: f.nome for f in db.query(Funcionario)
              .filter(Funcionario.id.in_(ids_transf)).all()} if ids_transf else {})
    return [serializar_mensagem(m, nome, nomes.get(m.transferido_para_funcionario_id))
            for m, nome in rows]


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
