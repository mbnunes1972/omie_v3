# -*- coding: utf-8 -*-
"""mod_simulador_autorizacao.py — Autorização por loja (LGPD) do Simulador de Modelo de Negócios
(Sessão 185/187, RF-02..RF-04, D5). O Simulador acessa dados sigilosos da loja (folha, salários,
margens, dívida): sem autorização ATIVA, a loja fica bloqueada no seletor e as rotas de dados
devolvem 403 com motivo.

Fluxo REMOTO (rev2, Sessão 187 — achado do usuário sobre a rev1: pedir a senha do Master DENTRO
da tela do solicitante só funcionava com os dois juntos, presencial):
1. `solicitar` — o super_admin pede acesso a uma loja. Sem senha nenhuma; cria `status='pendente'`.
2. `aprovar` — o Master vê o pedido na PRÓPRIA sessão (não a do solicitante) e reautentica a
   PRÓPRIA senha (padrão step-up de auto-confirmação — igual ao resto do app pede "confirme sua
   senha" pra ações sensíveis). Não há troca de credencial de terceiro em lugar nenhum: os dois
   lados só usam a própria conta, na própria sessão, o que dá pra acontecer remoto/assíncrono.
3. `revogar` — o Master revoga a qualquer momento, efeito imediato.

Trilha própria do Simulador (`simulador_log_acessos`), fora de `LogAcessoDelegado` (RF-04 pede log
fora do operacional). Nada aqui é motor de cálculo — é I/O puro (CRUD + auditoria)."""
from datetime import datetime

from database import SimuladorAutorizacao, SimuladorLogAcesso, Usuario


def status_lojas(db, lojas):
    """[{'loja_id','nome','status'}] pro seletor do Simulador (RF-02). `status` ∈
    'ativa'|'pendente'|'nenhuma'."""
    ids = [l.id for l in lojas]
    por_loja = {}
    if ids:
        for a in (db.query(SimuladorAutorizacao)
                  .filter(SimuladorAutorizacao.loja_id.in_(ids),
                          SimuladorAutorizacao.status.in_(("ativa", "pendente"))).all()):
            por_loja[a.loja_id] = a.status   # no máx. 1 ativa/pendente por loja (invariante)
    return [{"loja_id": l.id, "nome": l.nome, "status": por_loja.get(l.id, "nenhuma"),
             "autorizado": por_loja.get(l.id) == "ativa"} for l in lojas]


def autorizacao_ativa(db, loja_id):
    return db.query(SimuladorAutorizacao).filter_by(loja_id=loja_id, status="ativa").first()


def autorizacao_pendente(db, loja_id):
    return db.query(SimuladorAutorizacao).filter_by(loja_id=loja_id, status="pendente").first()


def registrar_log(db, evento, usuario_id, loja_id, ip=None, contexto=None):
    db.add(SimuladorLogAcesso(evento=evento, usuario_id=usuario_id, loja_id=loja_id,
                              ip=ip, contexto=contexto))


def solicitar(db, loja_id, solicitante_id, ip=None):
    """super_admin pede acesso a `loja_id` — sem senha, sem exigir presença do Master (RF-03,
    fluxo remoto). Idempotente: loja já `ativa`/`pendente` não duplica linha. Retorna
    (ok, autorizacao, erro|None)."""
    existente = (db.query(SimuladorAutorizacao)
                 .filter(SimuladorAutorizacao.loja_id == loja_id,
                         SimuladorAutorizacao.status.in_(("ativa", "pendente"))).first())
    if existente:
        return True, existente, None
    autorizacao = SimuladorAutorizacao(
        loja_id=loja_id, status="pendente", solicitado_por_usuario_id=solicitante_id,
        solicitado_em=datetime.utcnow(), beneficiario="orizon_assessoria",
        escopo="simulacao_leitura")
    db.add(autorizacao)
    db.flush()
    registrar_log(db, "solicitacao", solicitante_id, loja_id, ip)
    return True, autorizacao, None


def aprovar(db, master_usuario_dict, senha, base_legal, ip=None):
    """O Master aprova o pedido pendente da PRÓPRIA loja, reautenticando a PRÓPRIA senha (não a
    de terceiro). Retorna (ok, autorizacao|None, erro|None)."""
    if master_usuario_dict.get("nivel") != "master" or not master_usuario_dict.get("loja_id"):
        return False, None, "Só o Master da loja pode aprovar."
    loja_id = master_usuario_dict["loja_id"]
    master = db.get(Usuario, master_usuario_dict.get("id"))
    if not master or not master.ativo or not master.check_senha(senha or ""):
        return False, None, "Senha inválida."
    pendente = autorizacao_pendente(db, loja_id)
    if pendente is None:
        return False, None, "Não há solicitação pendente para esta loja."
    pendente.status = "ativa"
    pendente.concedido_por_usuario_id = master.id
    pendente.concedido_em = datetime.utcnow()
    pendente.base_legal = base_legal
    pendente.ip = ip
    registrar_log(db, "concessao", master.id, loja_id, ip,
                 contexto="solicitante=%s" % pendente.solicitado_por_usuario_id)
    return True, pendente, None


def revogar(db, master_usuario_dict, ip=None):
    """O próprio Master revoga a autorização (ativa OU um pedido ainda pendente) da sua loja —
    efeito imediato (RF-03). `master_usuario_dict` = dict de sessão (tem 'nivel'/'loja_id'/'id').
    Retorna (ok, erro|None)."""
    if master_usuario_dict.get("nivel") != "master" or not master_usuario_dict.get("loja_id"):
        return False, "Só o Master da loja pode revogar."
    loja_id = master_usuario_dict["loja_id"]
    atual = (db.query(SimuladorAutorizacao)
             .filter(SimuladorAutorizacao.loja_id == loja_id,
                     SimuladorAutorizacao.status.in_(("ativa", "pendente"))).first())
    if atual is None:
        return False, "Não há autorização ativa nem pedido pendente para revogar."
    atual.status = "revogada"
    atual.revogado_em = datetime.utcnow()
    registrar_log(db, "revogacao", master_usuario_dict.get("id"), loja_id, ip)
    return True, None
