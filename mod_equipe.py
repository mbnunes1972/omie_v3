"""mod_equipe.py — **Equipe do Projeto**: roster de papéis → responsáveis, para a secretária IA
informar o cliente a cada definição. Dois tipos de papel:
  - **AUTOMÁTICO** (derivado, não gravado): *Consultor* = quem criou o projeto (`criado_por`);
    *Gerente Comercial*/*SAC*/*Supervisor de Montagem* = funcionário(s) da loja com a função homônima.
  - **SELETOR** (escolhido e gravado em `projetos_meta.equipe_json`): *Medidor*, *Finalizador* e
    *Equipe de Montagem* (esta aceita VÁRIOS) — escolhidos entre funcionários e terceiros da loja.
Puro exceto pela sessão db. Fonte única: automáticos nunca são copiados; só as escolhas persistem.
"""
import json

from database import Projeto, Funcionario, Terceiro, Funcao, Usuario

FUNCAO_GERENTE = "Gerente de Vendas"          # rótulo do papel = "Gerente Comercial"
FUNCAO_SAC = "SAC"
FUNCAO_SUPERVISOR = "Supervisor de Montagem"

_SELETORES = ("medidor", "finalizador", "montagem")   # papéis escolhidos (persistidos)
_MULTI = ("montagem",)                                  # aceitam vários responsáveis


def _pessoa_pub(tipo, obj):
    return {"tipo": tipo, "id": obj.id, "nome": obj.nome,
            "telefone": getattr(obj, "telefone", None), "email": getattr(obj, "email", None)}


def _funcionarios_por_funcao(db, loja_id, nome_funcao):
    """Funcionários da loja cuja função (por nome) é `nome_funcao` — a base dos papéis automáticos."""
    fq = db.query(Funcao).filter(Funcao.nome == nome_funcao)
    fids = [f.id for f in fq.all()
            if (not loja_id) or f.loja_id == loja_id or f.loja_id is None]
    if not fids:
        return []
    q = db.query(Funcionario).filter(Funcionario.funcao_id.in_(fids))
    if loja_id:
        q = q.filter(Funcionario.loja_id == loja_id)
    return [_pessoa_pub("funcionario", x) for x in q.all()]


def candidatos(db, loja_id):
    """Funcionários + terceiros da loja — as opções dos papéis seletores."""
    fq = db.query(Funcionario)
    tq = db.query(Terceiro)
    if loja_id:
        fq = fq.filter(Funcionario.loja_id == loja_id)
        tq = tq.filter(Terceiro.loja_id == loja_id)
    return {"funcionarios": [_pessoa_pub("funcionario", x) for x in fq.all()],
            "terceiros": [_pessoa_pub("terceiro", x) for x in tq.all()]}


# Funções elegíveis à Equipe de MONTAGEM (feedback do teste 2026-07-26): só quem executa a
# montagem — Montador e Ajudante de Montagem. O Supervisor de Montagem é papel PRÓPRIO
# (automático) na Equipe, então não entra nesta lista de execução.
FUNCOES_MONTAGEM = ("Montador", "Ajudante de Montagem")


def candidatos_montagem(db, loja_id):
    """Candidatos à Equipe de Montagem: FUNCIONÁRIOS só das funções de montagem
    (FUNCOES_MONTAGEM) + TODOS os terceiros da loja (mão de obra terceirizada de montagem).
    Antes ofertava todos os funcionários — o que o usuário apontou como errado."""
    fids = [f.id for f in db.query(Funcao)
              .filter(Funcao.nome.in_(FUNCOES_MONTAGEM))
            if (not loja_id) or f.loja_id == loja_id or f.loja_id is None]
    fq = db.query(Funcionario).filter(Funcionario.funcao_id.in_(fids)) if fids \
        else db.query(Funcionario).filter(Funcionario.id == None)   # noqa: E711 (set vazio)
    tq = db.query(Terceiro)
    if loja_id:
        fq = fq.filter(Funcionario.loja_id == loja_id)
        tq = tq.filter(Terceiro.loja_id == loja_id)
    return {"funcionarios": [_pessoa_pub("funcionario", x) for x in fq.all()],
            "terceiros": [_pessoa_pub("terceiro", x) for x in tq.all()]}


def _resolver_pessoa(db, sel):
    """sel = {'tipo':'funcionario'|'terceiro','id':N} → pessoa pública (ou None se sumiu)."""
    if not sel or "tipo" not in sel or "id" not in sel:
        return None
    Model = Funcionario if sel["tipo"] == "funcionario" else Terceiro
    obj = db.get(Model, sel["id"])
    return _pessoa_pub(sel["tipo"], obj) if obj else None


def _selecoes(proj):
    if proj and getattr(proj, "equipe_json", None):
        try:
            return json.loads(proj.equipe_json)
        except (ValueError, TypeError):
            return {}
    return {}


def equipe(db, projeto_nome, loja_id):
    """Roster completo do projeto: 7 papéis com suas pessoas resolvidas (automáticas derivadas +
    seletoras persistidas). Retorna {'papeis': [{papel, rotulo, auto, multi?, pessoas:[...]}]}."""
    proj = db.get(Projeto, projeto_nome)
    sel = _selecoes(proj)

    consultor = None
    if proj and proj.criado_por_id:
        u = db.get(Usuario, proj.criado_por_id)
        if u:
            consultor = {"tipo": "usuario", "id": u.id, "nome": u.nome,
                         "telefone": u.telefone, "email": u.email}

    def _um(papel):
        return [p for p in [_resolver_pessoa(db, sel.get(papel))] if p]

    def _varios(papel):
        return [p for p in (_resolver_pessoa(db, s) for s in (sel.get(papel) or [])) if p]

    papeis = [
        {"papel": "gerente_comercial", "rotulo": "Gerente Comercial", "auto": True,
         "pessoas": _funcionarios_por_funcao(db, loja_id, FUNCAO_GERENTE)},
        {"papel": "consultor", "rotulo": "Consultor", "auto": True,
         "pessoas": [consultor] if consultor else []},
        {"papel": "sac", "rotulo": "SAC", "auto": True,
         "pessoas": _funcionarios_por_funcao(db, loja_id, FUNCAO_SAC)},
        {"papel": "medidor", "rotulo": "Medidor", "auto": False, "pessoas": _um("medidor")},
        {"papel": "finalizador", "rotulo": "Finalizador", "auto": False, "pessoas": _um("finalizador")},
        {"papel": "supervisor_montagem", "rotulo": "Supervisor de Montagem", "auto": True,
         "pessoas": _funcionarios_por_funcao(db, loja_id, FUNCAO_SUPERVISOR)},
        {"papel": "montagem", "rotulo": "Equipe de Montagem", "auto": False, "multi": True,
         "pessoas": _varios("montagem")},
    ]
    return {"papeis": papeis}


def salvar(db, projeto_nome, papel, selecao):
    """Grava a seleção de um papel SELETOR. `selecao`: {tipo,id} (ou lista deles p/ 'montagem').
    Não commita — quem chama decide. Retorna (ok, erro)."""
    if papel not in _SELETORES:
        return (False, "Papel '%s' não é seletor (é automático)." % papel)
    if papel in _MULTI and not isinstance(selecao, list):
        return (False, "Equipe de Montagem espera uma lista de responsáveis.")
    proj = db.get(Projeto, projeto_nome)
    if not proj:
        return (False, "Projeto não encontrado.")
    sel = _selecoes(proj)
    sel[papel] = selecao
    proj.equipe_json = json.dumps(sel, ensure_ascii=False)
    return (True, "")
