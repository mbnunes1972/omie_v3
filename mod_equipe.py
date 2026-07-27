"""mod_equipe.py — **Equipe do Projeto**: roster de papéis → responsáveis, para a secretária IA
informar o cliente a cada definição. Dois tipos de papel:
  - **AUTOMÁTICO** (derivado, não gravado): *Consultor* = quem criou o projeto (`criado_por`);
    *Gerente Comercial*/*SAC*/*Supervisor de Montagem* = funcionário(s) da loja com a função homônima.
  - **SELETOR** (escolhido e gravado em `projetos_meta.equipe_json`): *Medidor*, *Finalizador* e
    *Equipe de Montagem* (esta aceita VÁRIOS) — escolhidos entre funcionários e terceiros da loja.
Puro exceto pela sessão db. Fonte única: automáticos nunca são copiados; só as escolhas persistem.
"""
import json

from database import Projeto, Funcionario, Terceiro, Funcao, Usuario, CicloEtapa

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


# ═══ FONTE ÚNICA: equipe derivada das FUNÇÕES do ciclo ════════════════════════════════════════
# Spec conversa-projeto-no-orizon-chat (2026-07-27): a origem dos integrantes é a FUNÇÃO responsável
# de cada etapa (CicloEtapa.funcao_responsavel_id, do Cronograma Padrão da loja). O funcionário é
# DERIVADO: 1 candidato ativo → automático; >1 → LACUNA (ação gerencial no fechamento); 0 → sem
# responsável. Funcionário já fixado na etapa (responsavel_funcionario_id) é respeitado. Montagem
# mantém o refinamento por AMBIENTE no Mapa de Atribuições (decisão do lojista). O CRIADOR entra
# sempre. O roster de 7 papéis acima passará a DERIVAR desta fonte numa fatia seguinte (convergência).

def usuario_do_funcionario(db, funcionario_id):
    """Ponte Funcionário→Usuário: Funcionario.usuario_id; fallback Usuario.funcionario_id."""
    if not funcionario_id:
        return None
    f = db.get(Funcionario, funcionario_id)
    if f is not None and getattr(f, "usuario_id", None):
        return f.usuario_id
    u = db.query(Usuario).filter_by(funcionario_id=funcionario_id).first()
    return u.id if u else None


def candidatos_da_funcao(db, loja_id, funcao_id):
    """Candidatos ATIVOS de uma função na loja: FUNCIONÁRIOS ∪ TERCEIROS (ambos têm funcao_id —
    montadores/medidores/PE costumam ser terceiros). Cada candidato: {tipo, id, nome, usuario_id}.
    Terceiro é EXTERNO (sem usuario_id — participa por WhatsApp dirigido, como cliente/arquiteto)."""
    if not funcao_id:
        return []
    fs = (db.query(Funcionario)
            .filter(Funcionario.loja_id == loja_id, Funcionario.funcao_id == funcao_id)
            .filter((Funcionario.status == "ativo") | (Funcionario.status.is_(None)))
            .order_by(Funcionario.id.asc()).all())
    ts = (db.query(Terceiro)
            .filter(Terceiro.loja_id == loja_id, Terceiro.funcao_id == funcao_id)
            .order_by(Terceiro.id.asc()).all())
    out = [{"tipo": "funcionario", "id": f.id, "nome": f.nome,
            "usuario_id": usuario_do_funcionario(db, f.id)} for f in fs]
    out += [{"tipo": "terceiro", "id": t.id, "nome": t.nome, "usuario_id": None} for t in ts]
    return out


def responsavel_da_etapa(db, loja_id, etapa):
    """Responsável ÚNICO resolvido da etapa: DEFINIDO (responsavel_funcionario_id) ou AUTOMÁTICO
    (exatamente 1 candidato). Retorna {resolvido, tipo?, id?, motivo, candidatos?}. motivo ∈
    definido | auto | lacuna (>1) | sem_candidato (0)."""
    if etapa.responsavel_funcionario_id:
        return {"resolvido": True, "tipo": "funcionario",
                "id": etapa.responsavel_funcionario_id, "motivo": "definido"}
    cand = candidatos_da_funcao(db, loja_id, etapa.funcao_responsavel_id)
    if len(cand) == 1:
        return {"resolvido": True, "tipo": cand[0]["tipo"], "id": cand[0]["id"], "motivo": "auto"}
    return {"resolvido": False, "motivo": "lacuna" if len(cand) > 1 else "sem_candidato",
            "candidatos": cand}


def etapa_executavel(db, loja_id, etapa):
    """GATE DE EXECUÇÃO (bloqueador invertido, decisão 2026-07-27): a etapa só pode ser EXECUTADA
    com responsável definido — definido OU automático de 1 candidato. Lacuna (>1) ou sem candidato
    → NÃO executável (trava SÓ esta etapa; o resto do fluxo segue; a definição pode vir até o pedido)."""
    return responsavel_da_etapa(db, loja_id, etapa)["resolvido"]


def equipe_do_projeto(db, nome_safe, loja_id):
    """Equipe do projeto derivada das FUNÇÕES responsáveis das etapas (fonte única).

    Retorna {membros, externos, membros_usuarios, lacunas, criador_usuario_id}:
      - membros: FUNCIONÁRIOS resolvidos [{tipo, funcionario_id, usuario_id, funcao_id, via}]
        (via='definido'|'auto'), deduplicados.
      - externos: TERCEIROS resolvidos [{tipo, terceiro_id, nome, telefone, funcao_id, via}] —
        participam por canal EXTERNO dirigido (não são usuários).
      - membros_usuarios: ids de USUÁRIO da equipe (funcionários resolvidos + criador).
      - lacunas: [{etapa_codigo, funcao_id, funcao_nome, candidatos:[{tipo,id,nome}]}] — funções com
        >1 candidato ainda sem responsável definido (ação gerencial; travam a execução da etapa).
      - criador_usuario_id: dono/consultor do projeto (sempre integrante interno).
    """
    etapas = (db.query(CicloEtapa).filter_by(projeto_nome=nome_safe)
                .order_by(CicloEtapa.etapa_codigo.asc()).all())
    membros, externos = {}, {}
    lacunas, lac_key, _fnome = [], set(), {}

    def nome_funcao(fid):
        if fid not in _fnome:
            f = db.get(Funcao, fid) if fid else None
            _fnome[fid] = f.nome if f else None
        return _fnome[fid]

    def add(tipo, id_, funcao_id, via):
        key = (tipo, id_)
        if not id_ or key in membros or key in externos:
            return
        if tipo == "funcionario":
            membros[key] = {"tipo": "funcionario", "funcionario_id": id_,
                            "usuario_id": usuario_do_funcionario(db, id_),
                            "funcao_id": funcao_id, "via": via}
        else:
            t = db.get(Terceiro, id_)
            externos[key] = {"tipo": "terceiro", "terceiro_id": id_,
                             "nome": t.nome if t else None,
                             "telefone": t.telefone if t else None,
                             "funcao_id": funcao_id, "via": via}

    for et in etapas:
        r = responsavel_da_etapa(db, loja_id, et)
        if r["resolvido"]:
            add(r["tipo"], r["id"], et.funcao_responsavel_id, r["motivo"])
        elif r["motivo"] == "lacuna":
            k = (et.etapa_codigo, et.funcao_responsavel_id)
            if k not in lac_key:
                lac_key.add(k)
                lacunas.append({"etapa_codigo": et.etapa_codigo,
                                "funcao_id": et.funcao_responsavel_id,
                                "funcao_nome": nome_funcao(et.funcao_responsavel_id),
                                "candidatos": r["candidatos"]})
        # sem_candidato → etapa sem responsável nem lacuna (falta cadastro)

    pm = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
    criador_uid = pm.criado_por_id if pm else None
    usuarios = {m["usuario_id"] for m in membros.values() if m["usuario_id"]}
    if criador_uid:
        usuarios.add(criador_uid)
    return {"membros": list(membros.values()),
            "externos": list(externos.values()),
            "membros_usuarios": sorted(usuarios),
            "lacunas": lacunas,
            "criador_usuario_id": criador_uid}
