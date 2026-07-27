"""mod_equipe.py — **Equipe do Projeto**: roster de papéis → responsáveis, para a secretária IA
informar o cliente a cada definição. Dois tipos de papel:
  - **AUTOMÁTICO** (derivado, não gravado): *Consultor* = quem criou o projeto (`criado_por`);
    *Gerente Comercial*/*SAC*/*Supervisor de Montagem* = funcionário(s) da loja com a função homônima.
  - **SELETOR** (escolhido e gravado em `projetos_meta.equipe_json`): *Medidor*, *Finalizador* e
    *Equipe de Montagem* (esta aceita VÁRIOS) — escolhidos entre funcionários e terceiros da loja.
Puro exceto pela sessão db. Fonte única: automáticos nunca são copiados; só as escolhas persistem.
"""
import json

from database import (Projeto, Funcionario, Terceiro, Funcao, Usuario, CicloEtapa,
                      AtribuicaoAmbiente)

FUNCAO_GERENTE = "Gerente de Vendas"          # rótulo do papel = "Gerente Comercial"
FUNCAO_SAC = "SAC"
FUNCAO_SUPERVISOR = "Supervisor de Montagem"
# Convergência do roster (2026-07-27): medidor/finalizador viram o responsável da ETAPA da função;
# montagem vira o Mapa de Atribuições (papel 'montagem', projeto inteiro).
FUNCAO_MEDIDOR = "Medidor"
FUNCAO_PROJETISTA = "Projetista Executivo"    # papel "Finalizador" = quem faz o PE

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


def _etapa_da_funcao_nome(db, projeto_nome, loja_id, funcao_nome):
    """A etapa do projeto cuja FUNÇÃO responsável tem esse nome (medição→Medidor, PE→Projetista)."""
    fids = [f.id for f in db.query(Funcao).filter(Funcao.nome == funcao_nome).all()
            if (not loja_id) or f.loja_id == loja_id or f.loja_id is None]
    if not fids:
        return None
    return (db.query(CicloEtapa)
              .filter(CicloEtapa.projeto_nome == projeto_nome,
                      CicloEtapa.funcao_responsavel_id.in_(fids))
              .order_by(CicloEtapa.etapa_codigo.asc()).first())


def _pessoa_de_resp(db, r):
    """A pessoa (funcionário/terceiro) de um responsavel_da_etapa resolvido, ou []."""
    if not r or not r.get("resolvido"):
        return []
    if r["tipo"] == "funcionario":
        f = db.get(Funcionario, r["id"]);  return [_pessoa_pub("funcionario", f)] if f else []
    t = db.get(Terceiro, r["id"]);          return [_pessoa_pub("terceiro", t)] if t else []


def equipe(db, projeto_nome, loja_id):
    """Roster do projeto DERIVADO DA FONTE ÚNICA (convergência 2026-07-27):
    - gerente_comercial/sac/supervisor: informativos (funcionários da função — monitoramento);
    - consultor: criador do projeto;
    - medidor/finalizador: RESPONSÁVEL resolvido da etapa da função (Medidor / Projetista Executivo);
    - montagem: Mapa de Atribuições (papel 'montagem'). O `equipe_json` foi aposentado."""
    proj = db.get(Projeto, projeto_nome)
    consultor = None
    if proj and proj.criado_por_id:
        u = db.get(Usuario, proj.criado_por_id)
        if u:
            consultor = {"tipo": "usuario", "id": u.id, "nome": u.nome,
                         "telefone": u.telefone, "email": u.email}

    def resp_da_funcao(funcao_nome):
        et = _etapa_da_funcao_nome(db, projeto_nome, loja_id, funcao_nome)
        return _pessoa_de_resp(db, responsavel_da_etapa(db, loja_id, et)) if et is not None else []

    def montagem_pessoas():
        out = []
        for a in (db.query(AtribuicaoAmbiente)
                    .filter_by(projeto_nome=projeto_nome, papel="montagem").all()):
            if a.funcionario_id:
                f = db.get(Funcionario, a.funcionario_id)
                if f: out.append(_pessoa_pub("funcionario", f))
            elif a.terceiro_id:
                t = db.get(Terceiro, a.terceiro_id)
                if t: out.append(_pessoa_pub("terceiro", t))
        return out

    papeis = [
        {"papel": "gerente_comercial", "rotulo": "Gerente Comercial", "auto": True,
         "pessoas": _funcionarios_por_funcao(db, loja_id, FUNCAO_GERENTE)},
        {"papel": "consultor", "rotulo": "Consultor", "auto": True,
         "pessoas": [consultor] if consultor else []},
        {"papel": "sac", "rotulo": "SAC", "auto": True,
         "pessoas": _funcionarios_por_funcao(db, loja_id, FUNCAO_SAC)},
        {"papel": "medidor", "rotulo": "Medidor", "auto": False, "pessoas": resp_da_funcao(FUNCAO_MEDIDOR)},
        {"papel": "finalizador", "rotulo": "Finalizador", "auto": False,
         "pessoas": resp_da_funcao(FUNCAO_PROJETISTA)},
        {"papel": "supervisor_montagem", "rotulo": "Supervisor de Montagem", "auto": True,
         "pessoas": _funcionarios_por_funcao(db, loja_id, FUNCAO_SUPERVISOR)},
        {"papel": "montagem", "rotulo": "Equipe de Montagem", "auto": False, "multi": True,
         "pessoas": montagem_pessoas()},
    ]
    return {"papeis": papeis}


def _salvar_resp_etapa(db, projeto_nome, loja_id, funcao_nome, sel):
    """Grava o responsável (funcionário OU terceiro) da etapa da função. sel={tipo,id} ou None (limpa)."""
    et = _etapa_da_funcao_nome(db, projeto_nome, loja_id, funcao_nome)
    if et is None:
        return (False, "A etapa da função '%s' não existe no cronograma do projeto." % funcao_nome)
    et.responsavel_funcionario_id = None
    et.responsavel_terceiro_id = None
    if sel and sel.get("id"):
        if sel.get("tipo") == "terceiro":
            et.responsavel_terceiro_id = int(sel["id"])
        else:
            et.responsavel_funcionario_id = int(sel["id"])
    db.flush()
    return (True, "")


def _salvar_montagem(db, projeto_nome, loja_id, lista):
    """Substitui a Equipe de Montagem (projeto inteiro) no Mapa de Atribuições. lista=[{tipo,id}]."""
    if lista is not None and not isinstance(lista, list):
        return (False, "Equipe de Montagem espera uma lista.")
    (db.query(AtribuicaoAmbiente)
       .filter_by(projeto_nome=projeto_nome, papel="montagem", pool_ambiente_id=None).delete())
    for sel in (lista or []):
        if not sel or not sel.get("id"):
            continue
        a = AtribuicaoAmbiente(loja_id=loja_id, projeto_nome=projeto_nome,
                               papel="montagem", pool_ambiente_id=None)
        if sel.get("tipo") == "terceiro":
            a.terceiro_id = int(sel["id"])
        else:
            a.funcionario_id = int(sel["id"])
        db.add(a)
    db.flush()
    return (True, "")


def salvar(db, projeto_nome, papel, selecao, loja_id=None):
    """Grava a seleção de um papel SELETOR na FONTE ÚNICA (não mais no equipe_json):
    medidor/finalizador → responsável da etapa; montagem → Mapa de Atribuições. Não commita."""
    if papel == "medidor":
        return _salvar_resp_etapa(db, projeto_nome, loja_id, FUNCAO_MEDIDOR, selecao)
    if papel == "finalizador":
        return _salvar_resp_etapa(db, projeto_nome, loja_id, FUNCAO_PROJETISTA, selecao)
    if papel == "montagem":
        return _salvar_montagem(db, projeto_nome, loja_id, selecao)
    return (False, "Papel '%s' não é seletor (é automático/informativo)." % papel)


# ═══ FONTE ÚNICA: equipe derivada das FUNÇÕES do ciclo ════════════════════════════════════════
# Spec conversa-projeto-no-orizon-chat (2026-07-27): a origem dos integrantes é a FUNÇÃO responsável
# de cada etapa (CicloEtapa.funcao_responsavel_id, do Cronograma Padrão da loja). O funcionário é
# DERIVADO: 1 candidato ativo → automático; >1 → LACUNA (ação gerencial no fechamento); 0 → sem
# responsável. Funcionário já fixado na etapa (responsavel_funcionario_id) é respeitado. Montagem
# mantém o refinamento por AMBIENTE no Mapa de Atribuições (decisão do lojista). O CRIADOR entra
# sempre. O roster de 7 papéis acima passará a DERIVAR desta fonte numa fatia seguinte (convergência).

# Etapas cujo responsável é POR AMBIENTE (Mapa de Atribuições) — fora da resolução por função
# única (montagem/assistência). Espelha main._ETAPAS_POR_AMBIENTE.
ETAPAS_POR_AMBIENTE = frozenset({"17", "18"})


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
    if getattr(etapa, "responsavel_terceiro_id", None):
        return {"resolvido": True, "tipo": "terceiro",
                "id": etapa.responsavel_terceiro_id, "motivo": "definido"}
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


def montagem_lacunas(db, loja_id, papel, atribuicoes, ambientes):
    """GATE DE EXECUÇÃO por AMBIENTE de montagem/assistência (etapas 17/18, responsável no Mapa de
    Atribuições, não por função única). Mesma regra do bloqueador invertido, mas por ambiente: só
    trava na LACUNA — há **>1 candidato** de montagem na loja E algum ambiente sem responsável no
    Mapa (nem específico nem projeto-inteiro). 0/1 candidato ⇒ sem_candidato/auto, NÃO trava
    (retrocompatível: projetos sem Mapa de montagem seguem como hoje). Puro sobre `atribuicoes`
    (dicts) e `ambientes` (ids). Retorna a lista de pool_ambiente_id em lacuna (vazia = liberado)."""
    import mod_escopo
    cm = candidatos_montagem(db, loja_id)
    if len(cm.get("funcionarios", [])) + len(cm.get("terceiros", [])) <= 1:
        return []
    return [amb for amb in (ambientes or [])
            if mod_escopo.resolver_responsavel(atribuicoes, amb, papel) is None]


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


def montar_equipe_no_fechamento(db, nome_safe, loja_id):
    """No FECHAMENTO do contrato (2ª assinatura → 'fechado'): PERSISTE os responsáveis AUTOMÁTICOS
    (função com 1 candidato FUNCIONÁRIO) em `CicloEtapa.responsavel_funcionario_id`; deixa as LACUNAS
    (>1 candidato) para ação gerencial. Etapas por ambiente (montagem/assistência) ficam de fora.
    Não commita. Retorna {definidos, lacunas, auto_usuarios} para as notificações."""
    definidos = []
    for et in db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all():
        if (et.responsavel_funcionario_id or getattr(et, "responsavel_terceiro_id", None)
                or str(et.etapa_codigo) in ETAPAS_POR_AMBIENTE):
            continue
        r = responsavel_da_etapa(db, loja_id, et)
        if r["resolvido"] and r["motivo"] == "auto":
            if r["tipo"] == "funcionario":
                et.responsavel_funcionario_id = r["id"]
            else:
                et.responsavel_terceiro_id = r["id"]
            definidos.append({"etapa_codigo": et.etapa_codigo,
                              "tipo": r["tipo"], "id": r["id"]})
    db.flush()
    eq = equipe_do_projeto(db, nome_safe, loja_id)
    return {"definidos": definidos, "lacunas": eq["lacunas"],
            "auto_usuarios": [m["usuario_id"] for m in eq["membros"] if m["usuario_id"]]}
