"""mod_cadastro.py — módulo Cadastro (Modulos_Orizon_v9, módulo 2): Funcionário, Fornecedor, Terceiro.

Fronteira obrigatória: Funcionário (RH) ≠ Usuário (conta de login, Admin/Núcleo). Ligados por
referência (Usuario.funcionario_id / Funcionario.usuario_id), NUNCA duplicando dado pessoal.
"""
import re
import secrets
import json as _json
from auth import perfis
import mod_escopo
from database import Funcionario, Fornecedor, Terceiro, Usuario, Funcao

_REMUN = ("fixa", "variavel", "fixa_variavel")
_REG_TRAB = ("presencial", "remoto", "misto")
_REG_CONTR = ("registrado", "terceirizacao")

# Sub-entidades reutilizáveis (Modulos_Orizon_v10): Endereço + Dados Bancários
ENDERECO_CAMPOS = ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")
BANCO_CAMPOS    = ("banco_nome", "banco_codigo", "agencia", "conta", "pix")


def _aplicar_campos(obj, req, campos):
    for c in campos:
        if c in req:
            setattr(obj, c, _s(req.get(c)))


def _serial_campos(obj, campos):
    return {c: (getattr(obj, c, None) or "") for c in campos}

REMUNERACAO_TIPOS = ("fixa", "fixa_variavel")
FORN_CATEGORIAS   = ("materia_prima", "transportadora", "servicos", "outro")
TERC_SERVICOS     = ("montador", "outros")
# "Perfil de Usuário" (nivel de acesso) do Funcionário: fonte única = perfis.py (aposenta o
# 3-tuplo hardcoded que tinha o órfão "gerente"). Regras_Funcoes_Perfis_Atribuicoes §8.


def _s(v):
    v = ("" if v is None else str(v)).strip()
    return v or None


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _load_json_lista(s):
    try:
        v = _json.loads(s or "null")
    except (TypeError, ValueError):
        return []
    return v if isinstance(v, list) else []


def funcao_e_comissionada(funcao):
    """ACHADO-47 — guarda do adicional de comissão: True só quando a função PRIMÁRIA já tem
    ALGUMA comissão configurada (motor de vendas da loja, OU comissao_json com pct>0/faixas
    preenchidas). O adicional soma sobre uma comissão que já existe — nunca cria uma do zero.
    Mora aqui (não em mod_folha) porque opera só em dados de Funcao/cadastro — "folha" depende
    de "cadastro" (modulos.py), nunca o contrário; mod_folha reexporta esta função."""
    if not funcao:
        return False
    if funcao.usa_comissao_vendas:
        return True
    if not funcao.comissao_json:
        return False
    try:
        com = _json.loads(funcao.comissao_json)
    except (ValueError, TypeError):
        return False
    if com.get("por_meta"):
        return bool(com.get("faixas"))
    return float(com.get("pct") or 0.0) > 0.0


def _digitos(s):
    return re.sub(r"\D", "", s or "")


# ── Funcionário ──────────────────────────────────────────────────────────────
def func_serialize(f, db=None):
    d = {"id": f.id, "nome": f.nome, "cpf": f.cpf or "", "telefone": f.telefone or "",
         "email": f.email or "", "cargo": f.cargo or "", "funcao_id": f.funcao_id,
         "remuneracao_tipo": f.remuneracao_tipo or "fixa",
         "remuneracao_fixa": f.remuneracao_fixa, "remuneracao_var": f.remuneracao_var,
         "status": f.status or "ativo", "usuario_id": f.usuario_id,
         # ACHADO-47 — bloco Adicional (acúmulo de papéis, DECIDIDO 02/09).
         "adicional_fixo": getattr(f, "adicional_fixo", None),
         "adicional_comissao_pct": getattr(f, "adicional_comissao_pct", None),
         "adicional_comissao_base": getattr(f, "adicional_comissao_base", None) or "val_liq_venda",
         "adicional_obs": getattr(f, "adicional_obs", None) or "",
         "funcao_comissionada": False,
         "acesso": {"tem_acesso": False, "email": f.email or "", "perfil": "operador"}}
    d.update(_serial_campos(f, ENDERECO_CAMPOS + BANCO_CAMPOS))
    if db is not None and f.funcao_id:
        fn = db.get(Funcao, f.funcao_id)
        d["funcao_nome"] = fn.nome if fn else ""
        # ACHADO-46: papéis da função (fonte preferida pro Mapa de Atribuições filtrar
        # candidatos — nome vira fallback só quando isto vem vazio).
        papeis_brutos = _load_json_lista(getattr(fn, "atribuicoes_json", None)) if fn else []
        d["funcao_papeis"] = [p for p in papeis_brutos if p in mod_escopo.PAPEIS]
        # a tela só oferece o campo de adicional de comissão quando isto é True (o servidor
        # recusa de qualquer forma — ver func_aplicar — mas decoração NÃO é o gate, é só UX).
        d["funcao_comissionada"] = funcao_e_comissionada(fn)
    if db is not None and f.usuario_id:
        u = db.get(Usuario, f.usuario_id)
        if u and u.ativo:
            d["acesso"] = {"tem_acesso": True, "email": u.email or u.login, "perfil": u.nivel}
    return d


def func_aplicar(db, f, req, loja_id):
    if f.loja_id is None:
        f.loja_id = loja_id
    if _s(req.get("nome")):
        f.nome = _s(req.get("nome"))
    for campo in ("cpf", "telefone", "email", "cargo"):
        if campo in req:
            setattr(f, campo, _s(req.get(campo)))
    if "funcao_id" in req:
        f.funcao_id = _i(req.get("funcao_id"))
    _aplicar_campos(f, req, ENDERECO_CAMPOS + BANCO_CAMPOS)
    if "remuneracao_tipo" in req:
        f.remuneracao_tipo = (_s(req.get("remuneracao_tipo")) or "fixa")
    if "remuneracao_fixa" in req:
        f.remuneracao_fixa = _f(req.get("remuneracao_fixa"))
    if "remuneracao_var" in req:
        f.remuneracao_var = _f(req.get("remuneracao_var"))
    if "status" in req:
        f.status = (_s(req.get("status")) or "ativo")
    # ACHADO-47 (DECIDIDO 02/09) — Adicional (acúmulo de papéis): fixo é livre; comissão só
    # quando a função PRIMÁRIA já é comissionada — guarda NO SERVIDOR (achado de UAT de 10/08:
    # guarda só na tela é decoração). ValueError vira 400 automaticamente no chamador (main.py).
    if "adicional_fixo" in req:
        f.adicional_fixo = _f(req.get("adicional_fixo"))
    if "adicional_comissao_pct" in req:
        pct = _f(req.get("adicional_comissao_pct"))
        if pct:
            funcao_id = f.funcao_id if "funcao_id" not in req else _i(req.get("funcao_id"))
            funcao = db.get(Funcao, funcao_id) if (db is not None and funcao_id) else None
            if not funcao_e_comissionada(funcao):
                raise ValueError("Adicional de comissão só é permitido quando a função "
                                 "primária já é comissionada.")
        f.adicional_comissao_pct = pct
    if "adicional_comissao_base" in req:
        base = _s(req.get("adicional_comissao_base"))
        f.adicional_comissao_base = base if base == "val_liq_venda" else None
    if "adicional_obs" in req:
        f.adicional_obs = _s(req.get("adicional_obs"))


def func_sync_acesso(db, f, req):
    """Cria/atualiza/desativa a conta de login (Usuário) vinculada ao Funcionário — a fronteira.
    `req['acesso'] = {tem_acesso, email, perfil}`. Retorna (ok, erro)."""
    ac = req.get("acesso") or {}
    tem = bool(ac.get("tem_acesso"))
    if not tem:
        if f.usuario_id:
            u = db.get(Usuario, f.usuario_id)
            if u:
                u.ativo = 0                      # desativa (nunca apaga — preserva histórico/sessões)
        return True, None
    email = _s(ac.get("email")) or _s(f.email)
    funcao = db.get(Funcao, f.funcao_id) if f.funcao_id else None
    # perfil: o informado, senão o perfil_padrão da FUNÇÃO (Mapa de Funções), senão 'operador'
    perfil = _s(ac.get("perfil")) or (_s(getattr(funcao, "perfil_padrao", None))) or "operador"
    if not email:
        return False, "Informe o e-mail de acesso do funcionário."
    if perfil not in perfis.slugs_loja():
        return False, "Perfil de acesso inválido."
    # e-mail (login) não pode colidir com outro usuário
    conflito = (db.query(Usuario)
                .filter(Usuario.login == email, Usuario.id != (f.usuario_id or -1)).first())
    if conflito is not None:
        return False, "Já existe uma conta com este e-mail."
    if f.usuario_id:
        u = db.get(Usuario, f.usuario_id)
        if u:
            u.login = email; u.email = email; u.nivel = perfil; u.ativo = 1
            u.nome = f.nome; u.cpf = f.cpf; u.loja_id = f.loja_id
            u.funcao_id = f.funcao_id                 # conta herda a FUNÇÃO do funcionário
            return True, None
    # cria conta nova ligada — login = e-mail, senha provisória = dígitos do CPF (troca no 1º acesso)
    u = Usuario(nome=f.nome, login=email, email=email, cpf=f.cpf, nivel=perfil,
                loja_id=f.loja_id, ativo=1, funcionario_id=f.id, funcao_id=f.funcao_id)
    # senha provisória previsível (achado de auditoria 2026-08-13): "orizon123" hardcoded era
    # sequestrável por qualquer um que soubesse o e-mail de login. CPF ausente → token aleatório
    # (senha_provisoria=1 já força a troca no 1º acesso — o valor exato nunca precisa ser lido).
    u.set_senha(_digitos(f.cpf) or secrets.token_urlsafe(16))
    u.senha_provisoria = 1
    db.add(u); db.flush()
    f.usuario_id = u.id
    return True, None


# ── Fornecedor ───────────────────────────────────────────────────────────────
def forn_serialize(f, db=None):
    d = {"id": f.id, "tipo_pessoa": f.tipo_pessoa or "pj", "nome": f.nome,
         "cnpj_cpf": f.cnpj_cpf or "", "telefone": f.telefone or "", "email": f.email or "",
         "categoria": f.categoria or "", "prazo_pagamento": f.prazo_pagamento,
         "dados_bancarios": f.dados_bancarios or "", "status": f.status or "ativo"}
    d.update(_serial_campos(f, ENDERECO_CAMPOS + BANCO_CAMPOS))
    return d


def forn_aplicar(db, f, req, loja_id):
    if f.loja_id is None:
        f.loja_id = loja_id
    if _s(req.get("nome")):
        f.nome = _s(req.get("nome"))
    for campo in ("cnpj_cpf", "telefone", "email", "categoria", "dados_bancarios"):
        if campo in req:
            setattr(f, campo, _s(req.get(campo)))
    _aplicar_campos(f, req, ENDERECO_CAMPOS + BANCO_CAMPOS)
    if "tipo_pessoa" in req:
        f.tipo_pessoa = (_s(req.get("tipo_pessoa")) or "pj")
    if "prazo_pagamento" in req:
        f.prazo_pagamento = _i(req.get("prazo_pagamento"))
    if "status" in req:
        f.status = (_s(req.get("status")) or "ativo")


# ── Terceiro (sempre PF) ─────────────────────────────────────────────────────
def terc_serialize(t, db=None):
    d = {"id": t.id, "nome": t.nome, "cpf": t.cpf or "", "cnpj": t.cnpj or "", "telefone": t.telefone or "",
         "tipo_servico": t.tipo_servico or "", "funcao_id": t.funcao_id,
         "dados_bancarios": t.dados_bancarios or "", "condicao": t.condicao or "",
         "status": t.status or "ativo"}
    d.update(_serial_campos(t, ENDERECO_CAMPOS + BANCO_CAMPOS))
    if db is not None and t.funcao_id:
        fn = db.get(Funcao, t.funcao_id)
        d["funcao_nome"] = fn.nome if fn else ""
        papeis_brutos = _load_json_lista(getattr(fn, "atribuicoes_json", None)) if fn else []
        d["funcao_papeis"] = [p for p in papeis_brutos if p in mod_escopo.PAPEIS]
    return d


def terc_aplicar(db, t, req, loja_id):
    if t.loja_id is None:
        t.loja_id = loja_id
    if _s(req.get("nome")):
        t.nome = _s(req.get("nome"))
    for campo in ("cpf", "cnpj", "telefone", "dados_bancarios", "condicao", "tipo_servico"):
        if campo in req:
            setattr(t, campo, _s(req.get(campo)))
    if "funcao_id" in req:
        t.funcao_id = _i(req.get("funcao_id"))
    _aplicar_campos(t, req, ENDERECO_CAMPOS + BANCO_CAMPOS)
    if "status" in req:
        t.status = (_s(req.get("status")) or "ativo")


# ── Tabela de Funções (Config) ───────────────────────────────────────────────
def funcao_serialize(f, db=None):
    def _load(s):
        try: return _json.loads(s or "null")
        except Exception: return None
    com = _load(getattr(f, "comissao_json", None)) or {}
    ben = _load(getattr(f, "beneficios_json", None)) or {}
    papeis_brutos = _load(getattr(f, "atribuicoes_json", None)) or []
    papeis = [p for p in papeis_brutos if p in mod_escopo.PAPEIS] if isinstance(papeis_brutos, list) else []
    return {"id": f.id, "nome": f.nome, "status": f.status or "ativo",
            "perfil_padrao": getattr(f, "perfil_padrao", None),
            "descricao": getattr(f, "descricao", None),
            # ACHADO-46/47: papéis do Mapa de Atribuições que esta função executa — fonte
            # PREFERIDA (elimina o acoplamento por nome), preenchida aqui pela primeira vez.
            "papeis": papeis,
            "remuneracao_padrao": getattr(f, "remuneracao_padrao", None),
            "regime_trabalho": getattr(f, "regime_trabalho", None),
            "regime_contratacao": getattr(f, "regime_contratacao", None),
            "salario_fixo": getattr(f, "salario_fixo", None),
            "comissao_fixa": getattr(f, "comissao_fixa", None),
            "usa_comissao_vendas": bool(getattr(f, "usa_comissao_vendas", 0)),
            "comissao": {"por_meta": bool(com.get("por_meta")),
                         "base": com.get("base") if com.get("base") in ("liquido", "fabrica") else "liquido",
                         "pct": com.get("pct"), "faixas": com.get("faixas") or []},
            "beneficios": {k: {"on": bool((ben.get(k) or {}).get("on")),
                               "valor": float((ben.get(k) or {}).get("valor") or 0.0)} for k in ("at", "va", "ps")}}


def funcao_aplicar(db, f, req, loja_id):
    if f.loja_id is None:
        f.loja_id = loja_id
    if _s(req.get("nome")):
        f.nome = _s(req.get("nome"))
    if "status" in req:
        f.status = (_s(req.get("status")) or "ativo")
    if "perfil_padrao" in req:
        f.perfil_padrao = _s(req.get("perfil_padrao")) or None
    if "descricao" in req:
        f.descricao = _s(req.get("descricao")) or None
    if "papeis" in req:
        # ACHADO-46/47: só os papéis válidos do Mapa de Atribuições entram — nunca um valor
        # arbitrário do request vira "papel" pro resto do sistema.
        brutos = req.get("papeis") or []
        papeis = [p for p in brutos if p in mod_escopo.PAPEIS] if isinstance(brutos, list) else []
        f.atribuicoes_json = _json.dumps(papeis) if papeis else None
    if "remuneracao_padrao" in req:
        v = _s(req.get("remuneracao_padrao")); f.remuneracao_padrao = v if v in _REMUN else None
    if "regime_trabalho" in req:
        v = _s(req.get("regime_trabalho")); f.regime_trabalho = v if v in _REG_TRAB else None
    if "regime_contratacao" in req:
        v = _s(req.get("regime_contratacao")); f.regime_contratacao = v if v in _REG_CONTR else None
    if "salario_fixo" in req:
        f.salario_fixo = _f(req.get("salario_fixo"))
    if "comissao_fixa" in req:
        f.comissao_fixa = _f(req.get("comissao_fixa"))
    if "usa_comissao_vendas" in req:
        # 2026-08-08 (achado da Vera): antes só o seed inicial gravava isto (por nome exato
        # "Consultor de Vendas") — função nova/custom nunca conseguia ligar a comissão de
        # vendas por metas da loja (o mesmo motor que o Consultor usa) via API.
        f.usa_comissao_vendas = 1 if req.get("usa_comissao_vendas") else 0
    if "comissao" in req:
        cm = req.get("comissao") or {}
        base = cm.get("base"); base = base if base in ("liquido", "fabrica") else "liquido"
        out = {"por_meta": bool(cm.get("por_meta")), "base": base}
        if out["por_meta"]:
            out["faixas"] = [{"venda_ate": _f(fx.get("venda_ate")), "pct": _f(fx.get("pct")) or 0.0}
                             for fx in (cm.get("faixas") or []) if isinstance(fx, dict)]
        else:
            out["pct"] = _f(cm.get("pct")) or 0.0
        f.comissao_json = _json.dumps(out)
    if "beneficios" in req:
        bn = req.get("beneficios") or {}
        f.beneficios_json = _json.dumps({k: {"on": bool((bn.get(k) or {}).get("on")),
                                             "valor": _f((bn.get(k) or {}).get("valor")) or 0.0} for k in ("at", "va", "ps")})


def listar_funcoes(db, loja_id, ativos_only=False):
    q = db.query(Funcao).filter_by(loja_id=loja_id)
    rows = q.order_by(Funcao.nome.asc()).all()
    if ativos_only:
        rows = [r for r in rows if (r.status or "ativo") == "ativo"]
    return [funcao_serialize(r) for r in rows]


# ── Listagem genérica (Lista/Tabela: filtro por status + busca nome/documento) ─
def listar(db, Model, serialize, loja_id, q=None, status=None):
    rows = db.query(Model).filter_by(loja_id=loja_id).order_by(Model.id.desc()).all()
    out = [serialize(r, db) for r in rows]
    if status in ("ativo", "inativo"):
        out = [x for x in out if x.get("status") == status]
    if q:
        ql = q.strip().lower()
        qd = _digitos(q)
        def match(x):
            doc = x.get("cpf") or x.get("cnpj_cpf") or ""
            return (ql and ql in (x.get("nome", "").lower())) or (qd and qd in _digitos(doc))
        out = [x for x in out if match(x)]
    return out


META = {
    "remuneracao_tipos": list(REMUNERACAO_TIPOS),
    "fornecedor_categorias": list(FORN_CATEGORIAS),
    "terceiro_servicos": list(TERC_SERVICOS),
    "perfis_acesso": perfis.opcoes_loja(),   # [{slug, rotulo}] derivado de perfis.py
}
