"""
auth.py — Autenticação, sessões e autorização delegada
Omie_V3 | Dalmóbile
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from database import get_session, Usuario, Sessao, LogAutorizacao

# ── Configuração ──────────────────────────────────────────────────────────────
SESSION_DURATION_HOURS = 8
COOKIE_NAME            = "omie_session"

# ── Login ─────────────────────────────────────────────────────────────────────
def fazer_login(login: str, senha: str) -> dict:
    """
    Autentica um usuário e retorna token de sessão.
    Retorna: {"ok": True, "token": "...", "usuario": {...}} ou {"ok": False, "erro": "..."}
    """
    db = get_session()
    try:
        usuario = db.query(Usuario).filter_by(login=login, ativo=1).first()
        if not usuario or not usuario.check_senha(senha):
            return {"ok": False, "erro": "Usuário ou senha inválidos."}

        # Invalida sessões anteriores do mesmo usuário
        db.query(Sessao).filter_by(usuario_id=usuario.id, ativa=1).update({"ativa": 0})

        token     = secrets.token_hex(32)
        expira_em = datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)
        sessao    = Sessao(token=token, usuario_id=usuario.id, expira_em=expira_em)
        db.add(sessao)
        db.commit()

        return {
            "ok":      True,
            "token":   token,
            "usuario": _usuario_dict(usuario)
        }
    finally:
        db.close()


def fazer_logout(token: str):
    db = get_session()
    try:
        db.query(Sessao).filter_by(token=token).update({"ativa": 0})
        db.commit()
    finally:
        db.close()


# ── Validação de sessão ───────────────────────────────────────────────────────
def validar_sessao(token: str) -> dict | None:
    """
    Valida o token de sessão.
    Retorna dict do usuário ou None se inválido/expirado.
    """
    if not token:
        return None
    db = get_session()
    try:
        sessao = db.query(Sessao).filter_by(token=token, ativa=1).first()
        if not sessao:
            return None
        if sessao.expira_em < datetime.utcnow():
            sessao.ativa = 0
            db.commit()
            return None
        return _usuario_dict(sessao.usuario)
    finally:
        db.close()


def get_token_from_cookie(cookie_header: str) -> str:
    """Extrai o token do header Cookie."""
    if not cookie_header:
        return ""
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(COOKIE_NAME + "="):
            return part[len(COOKIE_NAME) + 1:]
    return ""


# ── Autorização delegada ──────────────────────────────────────────────────────
def verificar_desconto(token_solicitante: str, desconto_pct: float) -> dict:
    """
    Verifica se o usuário pode aplicar o desconto solicitado.
    Retorna: {"ok": True} ou {"ok": False, "limite": X, "requer_autorizacao": True}
    """
    usuario = validar_sessao(token_solicitante)
    if not usuario:
        return {"ok": False, "erro": "Sessão inválida."}

    if desconto_pct <= usuario["limite_desconto"]:
        return {"ok": True}

    return {
        "ok":                  False,
        "limite":              usuario["limite_desconto"],
        "requer_autorizacao":  True,
        "mensagem":            f"Seu limite de desconto é {usuario['limite_desconto']:.0f}%. "
                               f"Deseja solicitar autorização gerencial?"
    }


def autorizar_desconto(token_solicitante: str, login_autorizador: str,
                       senha_autorizador: str, desconto_pct: float,
                       contexto: dict = None) -> dict:
    """
    Tenta autorizar um desconto acima do limite do solicitante.
    O autorizador precisa ter limite >= desconto_pct.
    Registra no log independente do resultado.
    """
    solicitante = validar_sessao(token_solicitante)
    if not solicitante:
        return {"ok": False, "erro": "Sessão do solicitante inválida."}

    db = get_session()
    try:
        autorizador = db.query(Usuario).filter_by(login=login_autorizador, ativo=1).first()

        # Registra tentativa no log
        log = LogAutorizacao(
            solicitante_id   = solicitante["id"],
            autorizador_id   = autorizador.id if autorizador else None,
            desconto_solicit = desconto_pct,
            desconto_limite  = solicitante["limite_desconto"],
            autorizado       = 0,
            contexto         = json.dumps(contexto or {})
        )

        if not autorizador or not autorizador.check_senha(senha_autorizador):
            db.add(log)
            db.commit()
            return {"ok": False, "erro": "Usuário ou senha do autorizador inválidos."}

        if autorizador.limite_desconto < desconto_pct:
            db.add(log)
            db.commit()
            return {
                "ok":    False,
                "erro":  f"{autorizador.nome} ({autorizador.nivel}) também não tem "
                         f"permissão para autorizar {desconto_pct:.1f}%."
            }

        log.autorizado    = 1
        log.autorizador_id = autorizador.id
        db.add(log)
        db.commit()

        return {
            "ok":          True,
            "autorizador": _usuario_dict(autorizador),
            "mensagem":    f"Desconto de {desconto_pct:.1f}% autorizado por {autorizador.nome}."
        }
    finally:
        db.close()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _usuario_dict(u: Usuario) -> dict:
    return {
        "id":                u.id,
        "nome":              u.nome,
        "login":             u.login,
        "nivel":             u.nivel,
        "limite_desconto":   u.limite_desconto,
        "pode_ver_parametros": u.pode_ver_parametros,
    }
