# -*- coding: utf-8 -*-
"""mod_simulador_autorizacao.py — Autorização por loja (LGPD) do Simulador de Modelo de Negócios
(Sessão 185, RF-02..RF-04, D5). O Simulador acessa dados sigilosos da loja (folha, salários,
margens, dívida): sem autorização ATIVA, a loja fica bloqueada no seletor e as rotas de dados
devolvem 403 com motivo.

Concessão reautentica a SENHA do Master da loja alvo (mesmo padrão do step-up de
`POST /api/auth/step-up` — reautenticação por senha —, mas gravando na trilha PRÓPRIA do
Simulador, não em `LogAcessoDelegado`: RF-04 pede log fora do operacional). Revogação é do
Master, com efeito imediato. Nada aqui é motor de cálculo — é I/O puro (CRUD + auditoria)."""
from datetime import datetime

from database import SimuladorAutorizacao, SimuladorLogAcesso, Usuario


def status_lojas(db, lojas):
    """[{'loja_id','nome','autorizado'}] pro seletor do Simulador (RF-02)."""
    ids = [l.id for l in lojas]
    ativas = set()
    if ids:
        ativas = {a.loja_id for a in db.query(SimuladorAutorizacao)
                  .filter(SimuladorAutorizacao.loja_id.in_(ids),
                          SimuladorAutorizacao.status == "ativa").all()}
    return [{"loja_id": l.id, "nome": l.nome, "autorizado": l.id in ativas} for l in lojas]


def autorizacao_ativa(db, loja_id):
    return (db.query(SimuladorAutorizacao)
            .filter_by(loja_id=loja_id, status="ativa").first())


def registrar_log(db, evento, usuario_id, loja_id, ip=None, contexto=None):
    db.add(SimuladorLogAcesso(evento=evento, usuario_id=usuario_id, loja_id=loja_id,
                              ip=ip, contexto=contexto))


def conceder(db, loja_id, login_autorizador, senha_autorizador, solicitante_id, base_legal, ip=None):
    """Master da loja `loja_id` reautentica a senha e concede o acesso (RF-03) — a reautenticação
    é exigida SEMPRE, mesmo se a loja já estiver autorizada (idempotência não pula a validação).
    Idempotente: loja já autorizada não duplica linha (devolve a existente). Retorna
    (ok, autorizacao|None, erro|None)."""
    login = (login_autorizador or "").strip()
    autorizador = db.query(Usuario).filter_by(login=login).first()
    if not autorizador or not autorizador.ativo or not autorizador.check_senha(senha_autorizador or ""):
        return False, None, "Usuário ou senha inválidos."
    if autorizador.nivel != "master" or autorizador.loja_id != loja_id:
        return False, None, "%s não é Master desta loja." % autorizador.nome
    ativa = autorizacao_ativa(db, loja_id)
    if ativa:
        return True, ativa, None
    autorizacao = SimuladorAutorizacao(
        loja_id=loja_id, status="ativa", concedido_por_usuario_id=autorizador.id,
        beneficiario="orizon_assessoria", escopo="simulacao_leitura", base_legal=base_legal,
        concedido_em=datetime.utcnow(), ip=ip)
    db.add(autorizacao)
    db.flush()
    registrar_log(db, "concessao", solicitante_id, loja_id, ip,
                 contexto="autorizador=%d" % autorizador.id)
    return True, autorizacao, None


def revogar(db, master_usuario_dict, ip=None):
    """O próprio Master revoga a autorização da sua loja — efeito imediato (RF-03).
    `master_usuario_dict` = dict de sessão (tem 'nivel'/'loja_id'/'id'). Retorna (ok, erro|None)."""
    if master_usuario_dict.get("nivel") != "master" or not master_usuario_dict.get("loja_id"):
        return False, "Só o Master da loja pode revogar."
    loja_id = master_usuario_dict["loja_id"]
    atual = autorizacao_ativa(db, loja_id)
    if atual is None:
        return False, "Não há autorização ativa para revogar."
    atual.status = "revogada"
    atual.revogado_em = datetime.utcnow()
    registrar_log(db, "revogacao", master_usuario_dict.get("id"), loja_id, ip)
    return True, None
