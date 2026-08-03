"""mod_escopo.py — Escopo de VISIBILIDADE (Regras_Funcoes_Perfis_Atribuicoes §6).

Predicados PUROS, sem I/O (espelha mod_tenancy): o main.py faz as queries, resolve o profissional
atribuído → usuario_id e aplica o WHERE; aqui só mora a REGRA. Três eixos separados:
Perfil (perfis.py) × Função (Funcao) × Escopo (posse + Mapa de Atribuições).

Isolamento por loja (F4) é aplicado ANTES, pelo tenancy — aqui é o escopo DENTRO da loja.
"""
from auth import perfis

# Papéis operacionais do Mapa de Atribuições (Regras §4).
PAPEIS = ("projeto_executivo", "medicao", "montagem", "assistencia")

# Papel ↔ Função(ões) compatível(is) (Regras §7). Nomes do catálogo padrão (seed FUNCOES_PADRAO); o
# alvo de uma atribuição precisa ter uma dessas funções. (Follow-up: campo `papel` na Tabela de Funções
# elimina o acoplamento por nome.)
PAPEL_FUNCOES = {
    "projeto_executivo": ("Projetista Executivo",),
    "medicao":           ("Medidor",),
    "montagem":          ("Montador", "Supervisor de Montagem"),
    "assistencia":       ("Montador", "Supervisor de Montagem"),
}


def funcao_compativel(papel, funcao_nome):
    """True se `funcao_nome` é uma função aceita para `papel`. Papel sem mapeamento aceita qualquer."""
    aceitas = PAPEL_FUNCOES.get(papel)
    return True if not aceitas else (funcao_nome in aceitas)

# Perfis que veem só o que criaram (posse do projeto). Regras §3. Dirigido pela BASE (perfis.py) para
# sobreviver à migração de nivel e escopar corretamente perfis customizados derivados de "operador".

# LEGADO (pré-Perfil-4): níveis aposentados na migração — mantidos por segurança, mas nenhuma
# conta real os tem desde a Sessão 61. O chaveamento VIVO é pela FUNÇÃO (re-chave 2026-08-03,
# achado 🔴1 da Vera: a visão operacional ficou dormente da migração até aqui).
_ESCOPO_ATRIBUICAO = frozenset({"projetista_executivo", "medidor", "supervisor_montagem"})

# Funções que executam papel operacional (união de PAPEL_FUNCOES) — fallback por NOME enquanto
# `Funcao.atribuicoes_json` (fonte preferida, ver funcao_operacional) não é preenchida na Config.
FUNCOES_OPERACIONAIS = frozenset(n for nomes in PAPEL_FUNCOES.values() for n in nomes)


def funcao_operacional(funcao_nome, papeis=None):
    """True se a Função executa papel operacional (PE/Medição/Montagem/Assistência).
    `papeis` = Funcao.atribuicoes_json parseada (fonte PREFERIDA quando preenchida — elimina o
    acoplamento por nome); sem ela, decide pelo catálogo de nomes (FUNCOES_OPERACIONAIS)."""
    if papeis:
        return any(p in PAPEIS for p in papeis)
    return bool(funcao_nome) and funcao_nome in FUNCOES_OPERACIONAIS


def _eh_admin(ator):
    return (ator or {}).get("nivel") in ("super_admin", "admin_rede")


def eh_gerencia(ator):
    """Gerência+ (vê tudo na loja) = diretor / gerente_vendas / gerente_adm_fin, derivado de perfis.py
    pelas capacidades (autorizar OU aprovar_financeiro). Fonte única: perfis.py."""
    n = (ator or {}).get("nivel")
    return bool(n) and (perfis.pode(n, "autorizar") or perfis.pode(n, "aprovar_financeiro"))


def escopo_por_posse(ator):
    return perfis.base((ator or {}).get("nivel")) == "operador"


def escopo_por_atribuicao(ator):
    """Operacional (escopado pelo Mapa; sem visão comercial) — re-chave 2026-08-03: decide pela
    FUNÇÃO do Funcionário vinculado ao usuário (`ator["funcao_nome"]`/`ator["funcao_papeis"]`,
    resolvidos por main._ator_dict), não mais pelo nivel (aposentado no Perfil-4). Gerência e
    admin NUNCA são escopados pelo Mapa, qualquer que seja a função cadastrada."""
    a = ator or {}
    if a.get("nivel") in _ESCOPO_ATRIBUICAO:      # legado — inofensivo, nenhuma conta real tem
        return True
    if _eh_admin(a) or eh_gerencia(a):
        return False
    return funcao_operacional(a.get("funcao_nome"), a.get("funcao_papeis"))


def pode_ver_projeto(ator, meta, usuario_ids_atribuidos):
    """`meta` = projetos_meta (tem criado_por_id). `usuario_ids_atribuidos` = conjunto de usuario_id
    com QUALQUER atribuição neste projeto (já resolvido pelo main.py). Escopo DENTRO da loja."""
    if meta is None:
        return False
    if _eh_admin(ator):
        return False                                    # admin não tem acesso operacional (§3)
    if eh_gerencia(ator):
        return True                                     # gerência+ vê tudo na loja
    if escopo_por_atribuicao(ator):
        return (ator or {}).get("id") in (usuario_ids_atribuidos or set())
    if escopo_por_posse(ator):
        cpid = getattr(meta, "criado_por_id", None)
        return cpid is None or cpid == (ator or {}).get("id")
    return True                                         # demais perfis de loja: tudo na loja


def pode_ver_ambiente(ator, pool_ambiente_id, atribuicoes_do_ator):
    """`atribuicoes_do_ator` = atribuições deste projeto que resolvem para o ator (dicts com
    pool_ambiente_id). True se alguma cobre este ambiente (específica) ou é projeto-inteiro (NULL)."""
    if _eh_admin(ator):
        return False
    if not escopo_por_atribuicao(ator):
        return True                     # gerência/posse/demais de loja: o filtro de projeto já basta
    for a in (atribuicoes_do_ator or []):
        if a.get("pool_ambiente_id") in (pool_ambiente_id, None):
            return True
    return False


def resolver_responsavel(atribuicoes, pool_ambiente_id, papel):
    """Dada a lista de atribuições de UM projeto, resolve o responsável de (ambiente, papel):
    específica do ambiente PREVALECE sobre projeto-inteiro (NULL); se nenhuma, None."""
    especifica = geral = None
    for a in (atribuicoes or []):
        if a.get("papel") != papel:
            continue
        if a.get("pool_ambiente_id") == pool_ambiente_id:
            especifica = a
        elif a.get("pool_ambiente_id") is None:
            geral = a
    return especifica or geral


def projetos_visiveis(ator, metas, usuario_ids_por_projeto):
    """Filtra `metas` pela visibilidade. `usuario_ids_por_projeto` = {projeto_nome: set(usuario_id)}."""
    mapa = usuario_ids_por_projeto or {}
    return [m for m in metas
            if pode_ver_projeto(ator, m, mapa.get(getattr(m, "nome_safe", None), set()))]


def visao_do_papel(ator):
    """'comercial' (vê valores) | 'operacional' (só execução, sem comercial) | 'nenhuma' (admin).
    Regras §3: operacional (PE/Medidor/Montagem) nunca vê negociação/valores/margem/comissão."""
    if _eh_admin(ator):
        return "nenhuma"
    if escopo_por_atribuicao(ator):
        return "operacional"
    return "comercial"
