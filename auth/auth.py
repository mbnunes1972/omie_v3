"""
auth.py — Autenticação, sessões e autorização delegada
Orizon Manager | Dalmóbile
"""

import os
import json
import hashlib
import secrets
import threading
import time
from datetime import datetime, timedelta
from database import get_session, Usuario, Sessao, LogAutorizacao
from . import perfis

# ── Configuração ──────────────────────────────────────────────────────────────
SESSION_DURATION_HOURS = 8
# Renomeado de "omie_session" na faxina 2026-07-23 (Omie removido do produto).
# Efeito colateral consciente: sessões ativas caem UMA vez no deploy (re-login geral).
COOKIE_NAME            = "orizon_session"

# ── Rate limiting de login (achado de auditoria 2026-08-13) ───────────────────
# fazer_login não tinha nenhum contador/lockout — força bruta *online* sem barreira nenhuma,
# agravado pelo hash sem salt (achado à parte, migração maior, deferida) e pelo super_admin
# semeado com senha de bootstrap conhecida. Em memória (por processo — cada instância A/B/prod
# tem a sua, aceitável: reinício do processo já invalida sessões existentes, mesmo padrão já
# assumido pelo projeto); thread-safe (ThreadingHTTPServer). Chave = identificador normalizado
# (login OU e-mail em minúsculo), não IP — bloqueia a CONTA visada, que é o alvo real do ataque.
_LOGIN_TENTATIVAS = {}
_LOGIN_LOCK = threading.Lock()
_LOGIN_MAX_TENTATIVAS = 5
_LOGIN_JANELA_SEGUNDOS = 300     # 5 min: falhas fora dessa janela não contam mais
_LOGIN_MSG_BLOQUEIO = "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."


def _login_falhas_recentes(ident):
    agora = time.time()
    with _LOGIN_LOCK:
        hist = [t for t in _LOGIN_TENTATIVAS.get(ident, []) if agora - t < _LOGIN_JANELA_SEGUNDOS]
        _LOGIN_TENTATIVAS[ident] = hist
        return len(hist)


def _login_registrar_falha(ident):
    with _LOGIN_LOCK:
        _LOGIN_TENTATIVAS.setdefault(ident, []).append(time.time())


def _login_limpar_falhas(ident):
    with _LOGIN_LOCK:
        _LOGIN_TENTATIVAS.pop(ident, None)

# ── Login ─────────────────────────────────────────────────────────────────────
def fazer_login(login: str, senha: str) -> dict:
    """
    Autentica um usuário e retorna token de sessão. O identificador aceita **login OU e-mail**
    (a tela de entrada usa e-mail; contas antigas seguem entrando pelo login).
    Retorna: {"ok": True, "token": "...", "usuario": {...}} ou {"ok": False, "erro": "..."}
    """
    from sqlalchemy import or_, func
    ident = (login or "").strip()
    db = get_session()
    try:
        usuario = (db.query(Usuario)
                   .filter(Usuario.ativo == 1,
                           or_(Usuario.login == ident,
                               func.lower(Usuario.email) == ident.lower()))
                   .first())
        # Chave do lockout: ID do usuário RESOLVIDO quando a conta existe (login e e-mail da
        # MESMA conta caem no mesmo balde — não dobra o orçamento de tentativas alternando
        # entre os dois); string crua como fallback pra também limitar varredura de
        # identificadores inexistentes.
        chave = ("u:%d" % usuario.id) if usuario else ("s:%s" % ident.lower())
        if _login_falhas_recentes(chave) >= _LOGIN_MAX_TENTATIVAS:
            return {"ok": False, "erro": _LOGIN_MSG_BLOQUEIO}
        if not usuario or not usuario.check_senha(senha):
            _login_registrar_falha(chave)
            return {"ok": False, "erro": "Usuário ou senha inválidos."}
        _login_limpar_falhas(chave)

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
            "precisa_trocar_senha": bool(usuario.senha_provisoria),
            "usuario": _usuario_dict(usuario)
        }
    finally:
        db.close()


def trocar_senha(usuario_id: int, nova_senha: str):
    """Define nova senha e limpa a flag senha_provisoria. Retorna (ok, erro)."""
    nova = (nova_senha or "").strip()
    if len(nova) < 6:
        return False, "A senha deve ter ao menos 6 caracteres."
    db = get_session()
    try:
        u = db.get(Usuario, usuario_id)
        if not u:
            return False, "Usuário não encontrado."
        u.set_senha(nova)
        u.senha_provisoria = 0
        db.commit()
        return True, None
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
def _funcao_do_usuario(u):
    """(funcao_nome, papeis) da Função do Funcionário vinculado a esta conta, ou (None, None).
    Alimenta mod_escopo.escopo_por_atribuicao/visao_do_papel — re-chave da visão operacional
    (2026-08-03): o discriminador é a FUNÇÃO, não o nivel (aposentado no Perfil-4)."""
    import json as _json
    from sqlalchemy.orm import object_session
    from database import Funcao, Funcionario
    db = object_session(u)
    if db is None or not getattr(u, "id", None):
        return None, None
    f = (db.query(Funcao.nome, Funcao.atribuicoes_json)
           .join(Funcionario, Funcionario.funcao_id == Funcao.id)
           .filter(Funcionario.usuario_id == u.id).first())
    if not f:
        return None, None
    papeis = None
    if f[1]:
        try:
            papeis = _json.loads(f[1])
        except ValueError:
            papeis = None
    return f[0], papeis


def _usuario_dict(u: Usuario) -> dict:
    _funcao_nome, _funcao_papeis = _funcao_do_usuario(u)
    try:
        _override = json.loads(getattr(u, "capacidades_override_json", None) or "{}")
    except (TypeError, ValueError):
        _override = {}
    d = {
        "id":                u.id,
        "nome":              u.nome,
        "login":             u.login,
        "nivel":             u.nivel,
        "funcao_nome":       _funcao_nome,
        "funcao_papeis":     _funcao_papeis,
        "tema":              getattr(u, "tema", None) or "escuro",
        "loja_id":           u.loja_id,
        "rede_id":           u.rede_id,
        "limite_desconto":   u.limite_desconto,
        # capacidades_override (2026-08-08): override POR CONTA, só admin_rede — as funções
        # *_usuario abaixo o consultam; precisa estar no dict ANTES delas serem chamadas.
        "capacidades_override": _override,
        "pode_ver_parametros": perfis.pode(u.nivel, "ver_parametros"),
        "pode_gerir_documentos": perfis.pode(u.nivel, "gerir_documentos"),
        "rotulo":              perfis.rotulo(u.nivel),
        "pode_gerir_redes":    perfis.pode(u.nivel, "gerir_redes"),
        "pode_gerir_lojas":    perfis.pode(u.nivel, "gerir_lojas"),
        "pode_ver_estrategico": perfis.pode(u.nivel, "acesso_estrategico"),   # Painel Estratégico, 2026-08-09
        "pode_ver_simulador": perfis.pode(u.nivel, "acesso_simulador"),      # Simulador, Sessão 185 (só super_admin)
        # 2026-07-24: o frontend só pede senha gerencial quando o LOGADO não tem a permissão
        "pode_autorizar":           perfis.pode(u.nivel, "autorizar"),
        "pode_aprovar_financeiro":  perfis.pode(u.nivel, "aprovar_financeiro"),
        "pode_registrar_medicao":   perfis.pode(u.nivel, "registrar_medicao"),
        "pode_aprovar_medicao_reprovada": perfis.pode(u.nivel, "aprovar_medicao_reprovada"),
        "pode_executar_pe":         perfis.pode(u.nivel, "executar_pe"),
        "pode_revisar_pe":          perfis.pode(u.nivel, "revisar_pe"),
        "pode_ver_todas_conversas": perfis.pode(u.nivel, "ver_todas_conversas"),  # Orizon Chat F2
        "precisa_trocar_senha": bool(getattr(u, "senha_provisoria", 0)),
    }
    # Capacidades OVERRIDÁVEIS por conta pra admin_rede (2026-08-08) — usam pode_usuario(d, ...),
    # que lê d["capacidades_override"] acima; demais níveis caem em pode() sem mudança nenhuma.
    d["pode_gerir_usuarios"]    = perfis.pode_usuario(d, "gerir_usuarios")
    d["pode_gerir_perfis"]      = perfis.pode_usuario(d, "gerir_perfis")
    d["pode_editar_dados_loja"] = perfis.pode_usuario(d, "editar_dados_loja")
    return d


def set_tema(usuario_id: int, tema: str) -> bool:
    """Persiste a preferência de tema do usuário. False p/ tema inválido ou usuário inexistente."""
    if tema not in ("claro", "escuro"):
        return False
    db = get_session()
    try:
        u = db.get(Usuario, usuario_id)
        if not u:
            return False
        u.tema = tema
        db.commit()
        return True
    finally:
        db.close()
