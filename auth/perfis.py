# -*- coding: utf-8 -*-
"""perfis.py — Fonte única dos perfis de usuário e suas permissões.

Ao adicionar/alterar um perfil, atualize TAMBÉM docs/USUARIOS.md.
"""

# Perfil = NÍVEL DE ACESSO (Regras_Funcoes_Perfis_Atribuicoes rev2 §2): 4 perfis de LOJA definidos por
# acesso a módulo/painel (acesso_*), + os 2 de plataforma/rede. Os CARGOS (Diretor, Medidor, …) saíram
# daqui e viraram Função (tabela Funcao). Capacidades operacionais mapeadas de forma grosseira p/ não
# quebrar os gates vigentes; a precisão fina por Função é frente posterior.
PERFIS = {
    "master": {"rotulo": "Master", "desconto_max": 50.0,
        "acesso_operacional": True, "acesso_financeiro": True, "acesso_fiscal": True,
        "acesso_admin": True, "acesso_config": True,
        "ver_parametros": True, "autorizar": True, "aprovar_financeiro": True,
        "aprovar_medicao_reprovada": True, "gerir_usuarios": True, "gerir_perfis": True,
        "editar_dados_loja": True, "gerir_documentos": True,
        "executar_pe": True, "revisar_pe": True, "registrar_medicao": True,
        "ver_todas_conversas": True,     # Orizon Chat Fatia 2 (Gerente/Diretor veem tudo + admin)
        # Painel Estratégico (2026-08-09): exclusivo do Master por ora — "acesso precisará ser
        # revisto no futuro" (decisão do usuário), por isso é uma CAPACIDADE normal (editável por
        # loja via Perfis de Usuário), não um `if nivel == "master"` espalhado pelo código.
        "acesso_estrategico": True},
    "gerencial": {"rotulo": "Gerente", "desconto_max": 20.0,   # rótulo padronizado 2026-07-22 (slug não muda)
        "acesso_operacional": True, "acesso_financeiro": True, "acesso_fiscal": True,
        "acesso_admin": False, "acesso_config": False,
        "ver_parametros": True, "autorizar": True, "aprovar_financeiro": True,
        "aprovar_medicao_reprovada": True, "gerir_usuarios": False, "gerir_perfis": False,
        "editar_dados_loja": False, "gerir_documentos": False,
        "executar_pe": True, "revisar_pe": True, "registrar_medicao": True,
        "ver_todas_conversas": True},    # Orizon Chat Fatia 2 (Gerente/Diretor veem tudo + admin)
    "operador": {"rotulo": "Operador", "desconto_max": 10.0,
        # 2026-07-24 (decisão do usuário): operador também SEM Fiscal (era True)
        "acesso_operacional": True, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": False, "acesso_config": False,
        "ver_parametros": False, "autorizar": False, "aprovar_financeiro": False,
        "aprovar_medicao_reprovada": False, "gerir_usuarios": False, "gerir_perfis": False,
        "editar_dados_loja": False, "gerir_documentos": False,
        "executar_pe": True, "revisar_pe": False, "registrar_medicao": True,
        "ver_todas_conversas": False},
    # ── Plataforma/Rede (fora dos perfis de loja; NÃO entram na tabela perfil_acesso) ──
    "super_admin": {"rotulo": "Administrador da Plataforma", "desconto_max": 0.0,
        "acesso_operacional": True, "acesso_financeiro": True, "acesso_fiscal": True,
        "acesso_admin": True, "acesso_config": True,
        "gerir_usuarios": True, "gerir_perfis": True, "editar_dados_loja": True,
        "gerir_redes": True, "gerir_lojas": True},
    "admin_rede": {"rotulo": "Gestor de Rede", "desconto_max": 0.0,   # rótulo 2026-07-24 (slug imutável)
        "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": True, "acesso_config": True,
        "gerir_usuarios": True, "gerir_perfis": False, "editar_dados_loja": True,
        "gerir_redes": False, "gerir_lojas": True},
}

# Compat: slugs antigos ainda referenciados por dados residuais resolvem para a base equivalente.
_ALIAS_BASE = {"diretoria": "master", "consultor": "operador", "suporte": "operador"}

_DEFAULT = {"rotulo": "—", "desconto_max": 0.0, "ver_parametros": False,
            "autorizar": False, "gerir_usuarios": False, "gerir_perfis": False,
            "aprovar_financeiro": False,
            "registrar_medicao": False, "aprovar_medicao_reprovada": False,
            "gerir_redes": False, "gerir_lojas": False, "editar_dados_loja": False,
            "gerir_documentos": False,
            "executar_pe": False, "revisar_pe": False,
            "ver_todas_conversas": False, "acesso_estrategico": False,
            "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
            "acesso_admin": False, "acesso_config": False}

# Acesso a MÓDULO/PAINEL (matriz rev2 §2) — mapeia id de módulo → capacidade acesso_* do perfil.
_MODULOS_OPERACIONAIS = frozenset({"captacao", "cadastro", "comercial",
                                   "estoque", "expedicao", "montagem", "assistencias"})
_MODULO_ACESSO = {"financeiro": "acesso_financeiro", "folha": "acesso_financeiro",
                  "fiscal": "acesso_fiscal"}


def acessa_modulo(slug, modulo_id):
    """True se o perfil `slug` pode abrir o módulo de domínio `modulo_id` (matriz §2).
    Registro DB (perfil_acesso) manda quando existir; núcleo/desconhecido nunca é bloqueado."""
    if slug == "super_admin":
        return True
    info = _reg().get(slug)
    if info is not None:
        try:
            import modulos as _mod
            if modulo_id not in _mod.DOMINIOS:   # núcleo/desconhecido
                return True
        except Exception:
            pass
        return modulo_id in info["modulos"]
    if modulo_id in _MODULO_ACESSO:
        return pode(slug, _MODULO_ACESSO[modulo_id])
    if modulo_id in _MODULOS_OPERACIONAIS:
        return pode(slug, "acesso_operacional")
    return True   # módulos de núcleo / desconhecidos não são bloqueados por esta matriz


def acessa_painel(slug, painel):
    """True se o perfil abre o painel 'admin' (page-07) ou 'config' (page-09)."""
    if slug == "super_admin":
        return True
    info = _reg().get(slug)
    if info is not None:
        return painel in info["modulos"]
    return pode(slug, "acesso_admin" if painel == "admin" else "acesso_config")


def existe(slug):
    return slug in PERFIS or slug in _reg()


def slugs():
    return list(PERFIS.keys())


# Perfis (acesso) atribuíveis a um login de LOJA — exclui os de plataforma/rede. Fonte única do
# "acesso" oferecido no cadastro de Funcionário (Regras_Funcoes_Perfis_Atribuicoes §8, frente irmã).
_NAO_LOJA = frozenset({"super_admin", "admin_rede"})


def slugs_loja():
    return [s for s in PERFIS if s not in _NAO_LOJA]


def opcoes_loja():
    return [{"slug": s, "rotulo": PERFIS[s]["rotulo"]} for s in slugs_loja()]


def rotulo(slug):
    info = _reg().get(slug)
    if info:
        return info["nome"]
    return PERFIS.get(_base(slug), _DEFAULT)["rotulo"]


def _base(slug):
    """Resolve o slug para a BASE de capacidades finas (master/gerencial/operador/plataforma).
    Consulta primeiro o registro DB (perfil_acesso); sem registro, cai no PERFIS hardcoded."""
    info = _reg().get(slug)
    if info:
        return info["base"]
    if slug in PERFIS:
        return slug
    return _ALIAS_BASE.get(slug, slug)


def base(slug):
    """Base (master/gerencial/operador/plataforma) de um slug de perfil — pública."""
    return _base(slug)


def pode(slug, capacidade):
    """Override do perfil (capacidades_json) manda; senão cai na base PERFIS[base].
    super_admin é irrestrito (god-mode): sempre True."""
    if slug == "super_admin":
        return True
    info = _reg().get(slug)
    if info and capacidade in info["caps"]:
        return bool(info["caps"][capacidade])
    return bool(PERFIS.get(_base(slug), _DEFAULT).get(capacidade, False))


def desconto_max(slug):
    return PERFIS.get(_base(slug), _DEFAULT)["desconto_max"]


# Permissões por CONTA do Gestor de Rede (2026-08-08, pedido do usuário — "Permissões" na
# criação/edição). admin_rede não tem loja_id pra pendurar num PerfilAcesso (é por LOJA,
# nullable=False) — por isso um mecanismo à parte, em Usuario.capacidades_override_json, em vez
# de forçar esse nível dentro do sistema de slug por loja. Master reusa o slug por loja que já
# existe (cada Master pode ganhar seu próprio slug em PerfilAcesso); super_admin nunca tem
# override (god-mode, ver `pode()`).
#
# gerir_redes fica de fora de propósito: é FALSE fixo pra admin_rede e é o que
# `mod_tenancy._eh_super_admin` usa pra distinguir os dois níveis — tornar overridável deixaria
# um Gestor de Rede se passar por super_admin em qualquer checagem que use essa função.
# gerir_lojas também fica de fora: é o que `_eh_admin_rede` usa pra reconhecer a identidade do
# nível — desligar por engano tiraria a conta de todo o tenancy de rede (nem loja, nem rede).
CAPACIDADES_OVERRIDAVEIS_REDE = (
    "gerir_usuarios", "gerir_perfis", "editar_dados_loja", "acesso_admin", "acesso_config")


def capacidades_efetivas_rede(usuario):
    """Capacidades de UM admin_rede específico: default do nível (PERFIS["admin_rede"]) com o
    override da conta por cima, só nas capacidades da allowlist. `usuario` = dict de sessão
    (tem "nivel" e "capacidades_override") ou o objeto Usuario (tem .nivel e
    .capacidades_override_json). Não faz sentido pra outro nível — devolve a base pura."""
    import json as _json
    nivel = usuario.get("nivel") if isinstance(usuario, dict) else usuario.nivel
    base_caps = {c: PERFIS.get("admin_rede", _DEFAULT).get(c, False) for c in CAPACIDADES_OVERRIDAVEIS_REDE}
    if nivel != "admin_rede":
        return base_caps
    if isinstance(usuario, dict):
        override = usuario.get("capacidades_override") or {}
    else:
        try:
            override = _json.loads(usuario.capacidades_override_json or "{}")
        except (TypeError, ValueError):
            override = {}
    base_caps.update({k: bool(v) for k, v in override.items() if k in CAPACIDADES_OVERRIDAVEIS_REDE})
    return base_caps


def pode_usuario(usuario, capacidade):
    """Como pode(), mas honra o override POR CONTA do admin_rede (capacidade fora da allowlist,
    ou nível ≠ admin_rede, cai direto em pode() — comportamento de sempre, sem mudança)."""
    nivel = usuario.get("nivel") if isinstance(usuario, dict) else usuario.nivel
    if nivel == "admin_rede" and capacidade in CAPACIDADES_OVERRIDAVEIS_REDE:
        return capacidades_efetivas_rede(usuario).get(capacidade, False)
    return pode(nivel, capacidade)


def acessa_painel_usuario(usuario, painel):
    """Como acessa_painel(), mas honra o override por conta do admin_rede (acesso_admin/config
    estão na allowlist de CAPACIDADES_OVERRIDAVEIS_REDE)."""
    nivel = usuario.get("nivel") if isinstance(usuario, dict) else usuario.nivel
    if nivel == "admin_rede":
        return pode_usuario(usuario, "acesso_admin" if painel == "admin" else "acesso_config")
    return acessa_painel(nivel, painel)


# Metadados legíveis das capacidades — dão nome/descrição aos slugs para a tela Admin › Perfis de
# Usuário FORMALIZAR o que perfis.py já governa. A fonte única de VERDADE continua sendo PERFIS; isto
# é só a camada de apresentação. Toda capacidade booleana usada em PERFIS deve ter entrada aqui.
CAPACIDADES = {
    "acesso_operacional":        {"rotulo": "Módulos operacionais",       "grupo": "Acesso",
        "descricao": "Abrir os módulos operacionais (Cadastro, Comercial, Projetos, Expedição…)."},
    "acesso_financeiro":         {"rotulo": "Financeiro / Folha",         "grupo": "Acesso",
        "descricao": "Abrir os módulos Financeiro e Folha de Pagamento."},
    "acesso_fiscal":             {"rotulo": "Fiscal",                     "grupo": "Acesso",
        "descricao": "Abrir o módulo Fiscal (NF-e/NFS-e)."},
    "acesso_admin":              {"rotulo": "Painel Admin",               "grupo": "Acesso",
        "descricao": "Abrir o painel de Administração (identidade e acesso)."},
    "acesso_config":             {"rotulo": "Painel Config",              "grupo": "Acesso",
        "descricao": "Abrir o painel de Config (parâmetros de negócio)."},
    "acesso_estrategico":        {"rotulo": "Painel Estratégico",         "grupo": "Acesso",
        "descricao": "Abrir o Painel Estratégico (indicadores consolidados do negócio)."},
    "ver_parametros":            {"rotulo": "Ver parâmetros",             "grupo": "Comercial",
        "descricao": "Ver o painel de apoio da negociação (margens/custos internos)."},
    "autorizar":                 {"rotulo": "Autorizar desconto",         "grupo": "Comercial",
        "descricao": "Autorizar desconto acima do limite e ações que exigem gerência."},
    "ver_todas_conversas":       {"rotulo": "Administrar o Orizon Chat",  "grupo": "Comercial",
        "descricao": "Ver TODAS as conversas da loja (direct/grupo) e o painel de administração com filtro por assunto/participante."},
    "aprovar_financeiro":        {"rotulo": "Aprovar financeiro",         "grupo": "Financeiro",
        "descricao": "Aprovar os gates financeiros e liberar impostos."},
    "gerir_usuarios":            {"rotulo": "Gerir usuários",             "grupo": "Administração",
        "descricao": "Criar/editar contas de usuário da loja."},
    "gerir_perfis":              {"rotulo": "Gerir perfis de acesso", "grupo": "Administração",
        "descricao": "Criar/editar perfis de acesso da loja (só Master)."},
    "registrar_medicao":         {"rotulo": "Registrar medição",          "grupo": "Execução",
        "descricao": "Lançar a medição in loco (Medidor)."},
    "aprovar_medicao_reprovada": {"rotulo": "Aprovar medição reprovada",  "grupo": "Execução",
        "descricao": "Liberar medição reprovada (decisão comercial)."},
    "editar_dados_loja":         {"rotulo": "Editar dados da loja",       "grupo": "Administração",
        "descricao": "Editar o cadastro/dados da loja e emitir NF-e."},
    "gerir_documentos":          {"rotulo": "Gerir modelos de documento", "grupo": "Administração",
        "descricao": "Importar e ativar os modelos de contrato/proposta da loja (altera as cláusulas dos documentos gerados)."},
    "executar_pe":               {"rotulo": "Executar PE",                "grupo": "Execução",
        "descricao": "Trabalhar nas subfases do Projeto Executivo."},
    "revisar_pe":                {"rotulo": "Revisar PE",                 "grupo": "Execução",
        "descricao": "Revisar/aprovar o Projeto Executivo."},
    "gerir_redes":               {"rotulo": "Gerir redes",                "grupo": "Plataforma",
        "descricao": "Criar/editar redes (plataforma)."},
    "gerir_lojas":               {"rotulo": "Gerir lojas",                "grupo": "Plataforma",
        "descricao": "Criar/editar lojas (rede/plataforma)."},
}


def matriz():
    """Perfis com capacidades resolvidas (derivado de PERFIS) — alimenta Admin › Perfis de Usuário.
    Read-only: reflete o que o código já faz, não configura nada."""
    caps = list(CAPACIDADES.keys())
    loja = set(slugs_loja())
    perfis_out = [{
        "slug": s, "rotulo": PERFIS[s]["rotulo"], "desconto_max": PERFIS[s].get("desconto_max", 0.0),
        "loja": s in loja, "capacidades": [c for c in caps if PERFIS[s].get(c)],
    } for s in slugs()]
    return {"perfis": perfis_out, "capacidades": CAPACIDADES}


# ── Registro DB-backed (Task 5): perfil_acesso governa módulo/painel + overrides de capacidade fina
# por LOJA. Cache em memória (_REG_BY_SLUG/_REG_BY_LOJA), invalidado por recarregar(). Plataforma
# (super_admin/admin_rede) e lojas sem registro caem no PERFIS hardcoded acima.
import json as _json

_REG_BY_SLUG = None   # {slug: {"base","nome","modulos":set,"caps":dict,"loja_id","sistema"}}
_REG_BY_LOJA = None   # {loja_id: {slug: <mesma info>}}


def _carregar_registro():
    """Carrega perfil_acesso do banco para os caches. Silencioso se a tabela ainda não existe.
    Monta em variáveis locais e só publica nos globais no final (2026-08-08, servidor
    multi-thread): publicar `{}` no início e povoar aos poucos deixava uma janela em que outra
    thread via os globais "já carregados" porém vazios — agora ou é o cache antigo completo, ou
    o novo completo, nunca um estado parcial."""
    novo_slug, novo_loja = {}, {}
    try:
        from database import Session, PerfilAcesso
        db = Session()
        try:
            for p in db.query(PerfilAcesso).all():
                info = {"base": p.base, "nome": p.nome, "sistema": bool(p.sistema),
                        "loja_id": p.loja_id, "modulos": set(_json.loads(p.modulos_json or "[]")),
                        "caps": _json.loads(p.capacidades_json or "{}")}
                novo_slug[p.slug] = info
                novo_loja.setdefault(p.loja_id, {})[p.slug] = info
        finally:
            db.close()
    except Exception:
        pass   # DB indisponível/tabela ausente → registro vazio, cai no fallback PERFIS
    global _REG_BY_SLUG, _REG_BY_LOJA
    _REG_BY_SLUG, _REG_BY_LOJA = novo_slug, novo_loja


def recarregar():
    global _REG_BY_SLUG, _REG_BY_LOJA
    _REG_BY_SLUG, _REG_BY_LOJA = None, None


def _reg():
    if _REG_BY_SLUG is None:
        _carregar_registro()
    return _REG_BY_SLUG


def slugs_da_loja(loja_id):
    if _REG_BY_LOJA is None:
        _carregar_registro()
    return list((_REG_BY_LOJA or {}).get(loja_id, {}).keys())


def opcoes_da_loja(loja_id):
    if _REG_BY_LOJA is None:
        _carregar_registro()
    reg = (_REG_BY_LOJA or {}).get(loja_id, {})
    return [{"slug": s, "rotulo": reg[s]["nome"]} for s in reg]


# Capacidades finas booleanas SELECIONÁVEIS no modal (exclui os acesso_* de módulo/painel e as de plataforma).
CAPS_SELECIONAVEIS = ["ver_parametros", "autorizar",
                      "aprovar_financeiro", "gerir_usuarios",
                      "gerir_perfis", "editar_dados_loja", "gerir_documentos",
                      "registrar_medicao", "aprovar_medicao_reprovada", "executar_pe", "revisar_pe"]


def capacidades_efetivas(slug):
    """Mapa {cap: bool} das caps selecionáveis, resolvido (override sobre a base)."""
    return {c: pode(slug, c) for c in CAPS_SELECIONAVEIS}


def matriz_loja(loja_id):
    """Perfis da loja com módulos + capacidades resolvidos — alimenta Admin › Perfis de Usuário (editável)."""
    if _REG_BY_LOJA is None:
        _carregar_registro()
    reg = (_REG_BY_LOJA or {}).get(loja_id, {})
    perfis_out = [{"slug": s, "nome": reg[s]["nome"], "base": reg[s]["base"],
                   "sistema": reg[s]["sistema"], "modulos": sorted(reg[s]["modulos"]),
                   "capacidades": capacidades_efetivas(s), "desconto_max": desconto_max(s)} for s in reg]
    return {"perfis": perfis_out, "capacidades": CAPACIDADES, "caps_selecionaveis": CAPS_SELECIONAVEIS}
