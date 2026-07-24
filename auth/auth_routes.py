"""
auth_routes.py — Rotas de autenticação para integrar ao main.py
Orizon Manager | Dalmóbile

Como usar:
  1. No topo do main.py, adicione:
       from auth.auth_routes import handle_auth_get, handle_auth_post, get_usuario_sessao
  2. No do_GET, ANTES do bloco "if path == '/':", adicione:
       result = handle_auth_get(self, path)
       if result: return
  3. No do_POST, ANTES do bloco "if path == '/config':", adicione:
       result = handle_auth_post(self, path, body)
       if result: return
  4. No do_GET, troque o bloco "if path == '/':" por:
       if path == "/":
           usuario = get_usuario_sessao(self)
           if not usuario:
               self._redirect("/login")
               return
           body = _serve_html().encode()
           ...
"""

import json
import os
from .auth import (
    fazer_login, fazer_logout, validar_sessao,
    verificar_desconto, autorizar_desconto,
    get_token_from_cookie, COOKIE_NAME
)
from database import get_session, Usuario, Loja, Rede, membership_loja_ids, lojas_acessiveis_ids, LogAcessoDelegado
from . import perfis

# ── Caminho do login.html ─────────────────────────────────────────────────────
# DOIS dirname: este arquivo vive em auth/, e o static/ está na RAIZ do projeto.
# Com um só, apontava para auth/static/login.html — inexistente — e o
# `except FileNotFoundError` de _serve_login devolvia 404 em SILÊNCIO: a página de
# entrada sumia sem erro no log. Foi o que quebrou na mudança para pacote
# (2026-07-15). Mesmo padrão do mod_fin/base.py.
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGIN_HTML = os.path.join(_RAIZ, "static", "login.html")


def get_usuario_sessao(handler) -> dict | None:
    """Retorna o usuário da sessão atual ou None."""
    cookie = handler.headers.get("Cookie", "")
    token  = get_token_from_cookie(cookie)
    return validar_sessao(token)


def handle_auth_get(handler, path: str) -> bool:
    """
    Trata rotas GET de autenticação.
    Retorna True se a rota foi tratada, False caso contrário.
    """
    if path == "/login":
        _serve_login(handler)
        return True

    if path == "/logout":
        cookie = handler.headers.get("Cookie", "")
        token  = get_token_from_cookie(cookie)
        if token:
            fazer_logout(token)
        handler.send_response(302)
        handler.send_header("Location", "/login")
        handler.send_header("Set-Cookie", f"{COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly")
        handler.end_headers()
        return True

    if path == "/api/auth/me":
        usuario = get_usuario_sessao(handler)
        if not usuario:
            _send_json(handler, {"ok": False, "erro": "Não autenticado."}, 401)
        else:
            db = get_session()
            try:
                ids = lojas_acessiveis_ids(db, usuario["id"],
                                            usuario.get("nivel"), usuario.get("loja_id"))
                if usuario.get("loja_id") and usuario["loja_id"] not in ids:
                    ids = ids + [usuario["loja_id"]]
                lojas_obj = db.query(Loja).filter(Loja.id.in_(ids)).all() if ids else []
                rede_ids = {l.rede_id for l in lojas_obj if l.rede_id}
                redes = ({r.id: r.nome for r in db.query(Rede).filter(Rede.id.in_(rede_ids)).all()}
                         if rede_ids else {})
                # rede_id/rede_nome por loja: o front decide se oferece abrangência 'rede'
                lojas = [{"id": l.id, "nome": l.nome, "codigo": l.codigo,
                          "rede_id": l.rede_id, "rede_nome": redes.get(l.rede_id, "")}
                         for l in lojas_obj]
                usuario["lojas"] = lojas
                # super_admin "entra" numa loja pelo header X-Loja-Ativa (não tem loja própria);
                # sem isso o hub ignorava os modulos_ativos da loja e mostrava tudo ligado.
                _raw_loja = (handler.headers.get("X-Loja-Ativa") or "").strip()
                _hdr_loja = int(_raw_loja) if _raw_loja.isdigit() else None
                if usuario.get("nivel") == "super_admin" and _hdr_loja is not None:
                    usuario["loja_ativa_id"] = _hdr_loja
                else:
                    usuario["loja_ativa_id"] = usuario.get("loja_id")
                # módulos ativos da loja ativa (topologia) — default tudo-ligado se sem loja/config
                import mod_tenancy, modulos as _mod
                from . import perfis as _perfis   # irmão do pacote: relativo (2026-07-15)
                _lid = usuario.get("loja_ativa_id") or usuario.get("loja_id")
                _loja_ativa = db.get(Loja, _lid) if _lid else None
                _ativos = (mod_tenancy.modulos_ativos_da_loja(_loja_ativa)
                           if _loja_ativa else set(_mod.DOMINIOS))
                # PDV (loja com mãe, spec 2026-07-22): os painéis Financeiro E Folha não
                # aparecem na UI do PDV — operados pela mãe (visão unificada). Folha acompanha
                # porque depende do financeiro na topologia (modulos.py; QA Vera 🟠). Só a TELA
                # some: modulo_ativo() segue True, então o wiring de lançamentos do razão continua.
                if _loja_ativa is not None and getattr(_loja_ativa, "loja_mae_id", None):
                    _ativos = _ativos - {"financeiro", "folha"}
                # Perfil-4 (rev2 §2): o hub reflete os módulos que o PERFIL acessa (matriz), além dos
                # ativos na loja. Painéis Admin/Config idem (flags p/ o front esconder a navegação).
                _niv = usuario.get("nivel")
                _acessiveis = set(m for m in _ativos if _perfis.acessa_modulo(_niv, m))
                usuario["modulos_ativos"] = sorted(_acessiveis)
                usuario["modulos_bloqueados"] = sorted(_ativos - _acessiveis)
                usuario["acessa_admin"] = _perfis.acessa_painel(_niv, "admin")
                usuario["acessa_config"] = _perfis.acessa_painel(_niv, "config")
                # Hub sobre TODOS os módulos ativos da loja, marcando os que o perfil não acessa
                # (front mostra bloqueado com cadeado → step-up por senha). rev3 §2.
                usuario["hub"] = [
                    {"faixa": g["faixa"], "rotulo": g["rotulo"],
                     "modulos": [{"id": m["id"], "rotulo": m["rotulo"],
                                  "bloqueado": m["id"] not in _acessiveis} for m in g["modulos"]]}
                    for g in _mod.hub_layout(sorted(_ativos))
                ]
            finally:
                db.close()
            _send_json(handler, {"ok": True, "usuario": usuario})
        return True

    return False


def handle_auth_post(handler, path: str, body: bytes) -> bool:
    """
    Trata rotas POST de autenticação.
    Retorna True se a rota foi tratada, False caso contrário.
    """
    if path == "/api/auth/login":
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True

        resultado = fazer_login(dados.get("login", ""), dados.get("senha", ""))
        if resultado["ok"]:
            token = resultado["token"]
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header(
                "Set-Cookie",
                f"{COOKIE_NAME}={token}; Max-Age=28800; Path=/; HttpOnly"
            )
            resp = json.dumps(resultado).encode()
            handler.send_header("Content-Length", len(resp))
            handler.end_headers()
            handler.wfile.write(resp)
        else:
            _send_json(handler, resultado, 401)
        return True

    if path == "/api/auth/logout":
        cookie = handler.headers.get("Cookie", "")
        token  = get_token_from_cookie(cookie)
        if token:
            fazer_logout(token)
        _send_json(handler, {"ok": True})
        return True

    if path == "/api/auth/trocar-senha":
        usuario = get_usuario_sessao(handler)
        if not usuario:
            _send_json(handler, {"ok": False, "erro": "Não autenticado."}, 401)
            return True
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True
        from . import auth as _auth
        ok, erro = _auth.trocar_senha(usuario["id"], dados.get("nova_senha", ""))
        _send_json(handler, {"ok": True} if ok else {"ok": False, "erro": erro}, 200 if ok else 400)
        return True

    if path == "/api/auth/preferencias":
        usuario = get_usuario_sessao(handler)
        if not usuario:
            _send_json(handler, {"ok": False, "erro": "Não autenticado."}, 401)
            return True
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True
        tema = dados.get("tema")
        from . import auth as _auth
        if not _auth.set_tema(usuario["id"], tema):
            _send_json(handler, {"ok": False, "erro": "tema inválido."}, 400)
            return True
        _send_json(handler, {"ok": True, "tema": tema})
        return True

    if path == "/api/auth/verificar_desconto":
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True

        cookie  = handler.headers.get("Cookie", "")
        token   = get_token_from_cookie(cookie)
        desconto = float(dados.get("desconto_pct", 0))
        resultado = verificar_desconto(token, desconto)
        _send_json(handler, resultado)
        return True

    if path == "/api/auth/autorizar_desconto":
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True

        cookie   = handler.headers.get("Cookie", "")
        token    = get_token_from_cookie(cookie)
        resultado = autorizar_desconto(
            token_solicitante  = token,
            login_autorizador  = dados.get("login_autorizador", ""),
            senha_autorizador  = dados.get("senha_autorizador", ""),
            desconto_pct       = float(dados.get("desconto_pct", 0)),
            contexto           = dados.get("contexto", {})
        )
        _send_json(handler, resultado)
        return True

    if path == "/api/auth/liberar_impostos":
        try:
            req = json.loads(body) if body else {}
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True
        login = (req.get("login_autorizador") or "").strip()
        senha = req.get("senha_autorizador") or ""
        db = get_session()
        try:
            u = db.query(Usuario).filter_by(login=login).first()
            if not u or not u.ativo or not u.check_senha(senha):
                _send_json(handler, {"ok": False, "erro": "Usuário ou senha inválidos."}, 401)
                return True
            if not perfis.pode(u.nivel, "aprovar_financeiro"):
                _send_json(handler, {"ok": False, "erro": "Perfil sem permissão para liberar impostos."}, 403)
                return True
            _send_json(handler, {"ok": True, "autorizador": {"nome": u.nome}})
        finally:
            db.close()
        return True

    if path == "/api/auth/step-up":
        try:
            req = json.loads(body) if body else {}
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400); return True
        cookie = handler.headers.get("Cookie", "")
        token  = get_token_from_cookie(cookie)
        solicitante = validar_sessao(token)
        if not solicitante:
            _send_json(handler, {"ok": False, "erro": "Sessão inválida."}, 401); return True
        recurso = (req.get("recurso") or "").strip()
        login   = (req.get("login_autorizador") or "").strip()
        senha   = req.get("senha_autorizador") or ""
        db = get_session()
        try:
            u = db.query(Usuario).filter_by(login=login).first()
            if not u or not u.ativo or not u.check_senha(senha):
                _send_json(handler, {"ok": False, "erro": "Usuário ou senha inválidos."}, 401); return True
            tem = (perfis.acessa_painel(u.nivel, recurso) if recurso in ("admin", "config")
                   else perfis.acessa_modulo(u.nivel, recurso))
            if not tem:
                _send_json(handler, {"ok": False, "erro": f"{u.nome} não tem acesso a este recurso."}, 403); return True
            db.add(LogAcessoDelegado(solicitante_id=solicitante["id"], autorizador_id=u.id, recurso=recurso))
            db.commit()
            import main as _main
            _main._stepup_conceder(token, recurso)
            _send_json(handler, {"ok": True, "autorizador": {"nome": u.nome}})
        finally:
            db.close()
        return True

    return False


# ── Helpers internos ──────────────────────────────────────────────────────────
def _serve_login(handler):
    try:
        with open(_LOGIN_HTML, "rb") as f:
            body = f.read()
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", len(body))
        handler.end_headers()
        handler.wfile.write(body)
    except FileNotFoundError:
        handler.send_response(404)
        handler.end_headers()
        handler.wfile.write(b"login.html not found")


def _send_json(handler, data: dict, status: int = 200):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)
