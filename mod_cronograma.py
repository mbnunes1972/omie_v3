"""mod_cronograma.py — Cronograma do Ciclo (Modulos_Orizon_v11).

Na assinatura do contrato (D0 = ambas as partes assinaram — mesmo gatilho que constitui as
Provisões, Financeiro §6.4), constitui a data prevista de conclusão de cada etapa a partir do
Cronograma de Projeto Padrão (Config): data_prevista_conclusao = D0 + Σ(durações até a etapa,
inclusive). prazo_dias é a DURAÇÃO da etapa (dias corridos), não um offset absoluto desde D0.

data_conclusao (= CicloEtapa.concluido_em) nasce vazia — preenche quando a etapa é de fato
concluída. Idempotente por (projeto, etapa): reexecutar recomputa a data prevista a partir de D0.
"""
from datetime import timedelta

from database import CicloEtapa, Projeto


def cronograma_padrao(cfg):
    """Normaliza a lista de fases do Cronograma Padrão da config: [{codigo, prazo_dias, funcao_id}].
    funcao_id (→ Tabela de Funções, Modulos_Orizon_v12) é a FUNÇÃO responsável pela fase; None se não
    definida."""
    itens = (cfg or {}).get("cronograma_padrao") or []
    out = []
    for it in itens:
        cod = str((it or {}).get("codigo") or "").strip()
        if not cod:
            continue
        try:
            prazo = int((it or {}).get("prazo_dias") or 0)
        except (TypeError, ValueError):
            prazo = 0
        try:
            fid = int((it or {}).get("funcao_id")) if (it or {}).get("funcao_id") else None
        except (TypeError, ValueError):
            fid = None
        out.append({"codigo": cod, "prazo_dias": max(0, prazo), "funcao_id": fid})
    return out


# Subfases do PE — offsets DEFAULT como frações da janela da etapa 11 (Agenda Fatia 2, spec
# 2026-08-03 §3): o cronograma padrão só data as etapas principais; sem isto os marcos de
# Planta de Pontos/Revisão/assinatura do PE não existem na Agenda. Só preenche subfase SEM
# data prevista (edição manual via modal de cronograma nunca é sobrescrita).
SUBFASES_PE_FRACOES = [("11a", 0.20), ("11b", 0.40), ("11c", 0.70), ("11d", 0.85), ("11e", 1.00)]


def gerar_cronograma_projeto(db, projeto_nome, cfg, d0):
    """Para cada fase do Cronograma Padrão, cria/atualiza a etapa do projeto com
    data_prevista_conclusao = d0 + Σ(durações das etapas até esta, inclusive). prazo_dias é a DURAÇÃO
    da etapa (dias corridos). Não toca data de conclusão. Idempotente. Retorna as CicloEtapa afetadas.
    Subfases do PE ganham data default por fração da janela da 11 (SUBFASES_PE_FRACOES)."""
    afetadas = []
    acc = 0
    for fase in cronograma_padrao(cfg):
        acc += fase["prazo_dias"]
        prevista = d0 + timedelta(days=acc)
        reg = (db.query(CicloEtapa)
               .filter_by(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"]).first())
        if reg is None:
            reg = CicloEtapa(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"])
            db.add(reg)
        reg.data_prevista_conclusao = prevista
        # Herda a FUNÇÃO responsável do padrão (v12); não sobrescreve o funcionário já escolhido.
        reg.funcao_responsavel_id = fase.get("funcao_id")
        afetadas.append(reg)
        if fase["codigo"] == "11" and fase["prazo_dias"] > 0:
            inicio_11 = acc - fase["prazo_dias"]
            for cod_sf, frac in SUBFASES_PE_FRACOES:
                sf = (db.query(CicloEtapa)
                      .filter_by(projeto_nome=projeto_nome, etapa_codigo=cod_sf).first())
                if sf is None:
                    sf = CicloEtapa(projeto_nome=projeto_nome, etapa_codigo=cod_sf)
                    db.add(sf)
                if sf.data_prevista_conclusao is None:
                    sf.data_prevista_conclusao = d0 + timedelta(
                        days=inicio_11 + round(fase["prazo_dias"] * frac))
                    afetadas.append(sf)
    db.flush()
    return afetadas


# Etapas cuja data_prevista_conclusao deriva da entrega real (16), não do D0 — Montagem→Aprovação
# final, nessa ordem sequencial (mesma ordem em cronograma_padrao).
CODIGOS_POS_ENTREGA = ("17", "18", "19", "20")


def reancorar_pos_entrega(db, projeto_nome, cfg, nova_entrega):
    """Reancora Montagem/Assistência pós Montagem/Vistoria final/Aprovação final a partir da data de
    ENTREGA REAL (Projeto.data_entrega, editável na tela de Contrato) em vez do D0 da assinatura.

    Achado do usuário (2026-08-25): `gerar_cronograma_projeto` fixa a data prevista dessas 4 etapas
    UMA VEZ, no D0, a partir da entrega estimada de então — mas a entrega real é reavaliada depois
    (atraso de produção etc.) via Projeto.data_entrega, um campo independente. Nada resincronizava
    o restante: um projeto podia terminar com "Montagem" datada ANTES da "Entrega no cliente" real,
    uma inversão impossível no mundo real. Chamar isto sempre que Projeto.data_entrega muda evita a
    divergência. Nunca toca etapa já concluída (não reescreve histórico) — nesse caso preserva a
    data e continua acumulando as durações a partir dela mesma, e não da nova entrega, pra manter a
    cadeia coerente com o que já aconteceu de fato. Idempotente. Retorna as CicloEtapa afetadas
    (lista vazia se nada precisou mudar)."""
    import mod_ciclo
    durs = {e["codigo"]: e["prazo_dias"] for e in cronograma_padrao(cfg)}
    afetadas = []
    ancora = nova_entrega
    for cod in CODIGOS_POS_ENTREGA:
        reg = db.query(CicloEtapa).filter_by(projeto_nome=projeto_nome, etapa_codigo=cod).first()
        if reg is None:
            reg = CicloEtapa(projeto_nome=projeto_nome, etapa_codigo=cod)
            db.add(reg)
        if reg.status in mod_ciclo.STATUS_CONCLUSIVOS:
            if reg.data_prevista_conclusao:
                ancora = reg.data_prevista_conclusao   # já aconteceu — a cadeia segue dali, não da entrega
            continue
        ancora = ancora + timedelta(days=durs.get(cod, 0))
        if reg.data_prevista_conclusao != ancora:
            reg.data_prevista_conclusao = ancora
            afetadas.append(reg)
    if afetadas:
        db.flush()
    return afetadas


# ── Fase A — prazo por fase validado contra o cronograma do projeto ──────────────────────────────

def limite_etapa(db, projeto_nome, etapa_codigo):
    """Limite do cronograma (data_prevista_conclusao) da etapa do projeto; None se não houver."""
    reg = (db.query(CicloEtapa)
           .filter_by(projeto_nome=projeto_nome, etapa_codigo=str(etapa_codigo)).first())
    return reg.data_prevista_conclusao if reg else None


def prazo_excede_limite(limite, prazo):
    """True se `prazo` ultrapassa o `limite` do cronograma. Sem limite (None) ou sem prazo (None) →
    False (nada a exceder). Igualar o limite NÃO excede."""
    if limite is None or prazo is None:
        return False
    return prazo > limite


def backfill_subfases_pe(db):
    """Backfill ÚNICO (idempotente) dos offsets default das subfases do PE em cronogramas
    LEGADOS (gerados antes da Sessão 141): projeto com etapa 11 datada mas subfases sem data
    ganha as frações da janela 10→11 (achado 🟡3 da Vera: os MARCOS de PE ficavam invisíveis
    no Calendário enquanto a CARGA de PE aparecia cheia nas outras visões). Não sobrescreve
    data existente. Não commita. Retorna nº de subfases preenchidas."""
    com_11 = (db.query(CicloEtapa)
                .filter(CicloEtapa.etapa_codigo == "11",
                        CicloEtapa.data_prevista_conclusao.isnot(None)).all())
    n = 0
    for e11 in com_11:
        e10 = (db.query(CicloEtapa)
                 .filter_by(projeto_nome=e11.projeto_nome, etapa_codigo="10").first())
        ini = e10.data_prevista_conclusao if e10 else None
        if not ini or ini >= e11.data_prevista_conclusao:
            continue
        dur = (e11.data_prevista_conclusao - ini).days
        for cod_sf, frac in SUBFASES_PE_FRACOES:
            sf = (db.query(CicloEtapa)
                    .filter_by(projeto_nome=e11.projeto_nome, etapa_codigo=cod_sf).first())
            if sf is None:
                sf = CicloEtapa(projeto_nome=e11.projeto_nome, etapa_codigo=cod_sf)
                db.add(sf)
            if sf.data_prevista_conclusao is None:
                sf.data_prevista_conclusao = ini + timedelta(days=round(dur * frac))
                n += 1
    db.flush()
    return n


def tem_cronograma(db, projeto_nome):
    """True se o projeto já tem ao menos uma etapa com data prevista (cronograma gerado)."""
    return (db.query(CicloEtapa)
            .filter(CicloEtapa.projeto_nome == projeto_nome,
                    CicloEtapa.data_prevista_conclusao.isnot(None)).first() is not None)


def garantir_cronograma(db, projeto_nome, cfg, d0):
    """Todo projeto deve ter cronograma: se ainda não tem, gera do Cronograma Padrão (cfg) a partir do
    d0. NÃO sobrescreve um cronograma existente. Retorna True se gerou agora, False se já existia."""
    if tem_cronograma(db, projeto_nome):
        return False
    gerar_cronograma_projeto(db, projeto_nome, cfg, d0)
    return True


def cronogramas(etapas, inicio, entrega, codigo_entrega):
    """Dois cronogramas derivados do MESMO Cronograma Padrão (mesmos prazos, âncoras opostas) — puro.
    `etapas`: lista ORDENADA de (codigo, prazo_dias). `codigo_entrega` marca a etapa de ENTREGA ao cliente
    (âncora do regressivo; default = última). `inicio` = âncora do progressivo. Retorna
    [{codigo, progressivo, regressivo, folga_dias}]:
      - progressivo[i] = inicio + Σ prazos ATÉ i (inclusive) — o quanto ANTES a etapa pode terminar;
      - regressivo[i] = entrega recuada pelos prazos entre i e a entrega (o Prazo LIMITE); etapas DEPOIS
        da entrega avançam a partir dela;
      - folga_dias = (regressivo − progressivo).days (negativa = o prazo não cabe no padrão)."""
    prog = {}
    acc = inicio
    for cod, pz in etapas:
        acc = acc + timedelta(days=int(pz or 0))
        prog[cod] = acc
    idx = next((i for i, (c, _) in enumerate(etapas) if c == codigo_entrega), len(etapas) - 1)
    reg = {}
    for j, (cod, _) in enumerate(etapas):
        if j <= idx:
            dias = sum(int(p or 0) for _, p in etapas[j + 1:idx + 1])
            reg[cod] = entrega - timedelta(days=dias)
        else:
            dias = sum(int(p or 0) for _, p in etapas[idx + 1:j + 1])
            reg[cod] = entrega + timedelta(days=dias)
    return [{"codigo": cod, "progressivo": prog[cod], "regressivo": reg[cod],
             "folga_dias": (reg[cod] - prog[cod]).days} for cod, _ in etapas]


def cronograma_do_projeto(cfg, inicio, entrega, codigo_entrega="16"):
    """Dois cronogramas do projeto a partir do Cronograma Padrão (cfg) + âncoras (início, entrega).
    Extrai as etapas/prazos do padrão na ordem e delega a `cronogramas()`. `codigo_entrega` default = "16"
    (Entrega no cliente)."""
    etapas = [(f["codigo"], f["prazo_dias"]) for f in cronograma_padrao(cfg)]
    return cronogramas(etapas, inicio, entrega, codigo_entrega)


def cabe_no_cronograma(resultado):
    """True se NENHUMA etapa tem folga negativa — o prazo do cliente CABE no Cronograma Padrão. Se folga
    negativa em alguma etapa, o projeto precisa do cronograma PRÓPRIO (edição + senha de gerente/diretor)."""
    return all(e["folga_dias"] >= 0 for e in (resultado or []))


def folga_medicao_entrega(cfg, previsao_medicao, data_entrega, codigo_medicao="10", codigo_entrega="16"):
    """Folga do trecho MEDIÇÃO→ENTREGA em dias corridos: (data_entrega − previsao_medicao) menos a soma
    das DURAÇÕES das etapas APÓS a medição até a entrega (inclusive). Só as etapas sob controle da loja
    (PE, produção, entrega) contam; as anteriores à medição dependem da obra do cliente. Negativa = não
    cabe. Âncora da medição: prefere `codigo_medicao` ("10"); se ausente, "9"; se nenhum, a 1ª etapa.
    `codigo_entrega` default "16" (Entrega no cliente); se ausente, a última etapa. PRECONDIÇÃO: espera
    `cronograma_padrao` em ORDEM (medição antes da entrega), como a UI já ordena as etapas 8→20 (medição
    = 10, entrega = 16); se a medição vier em/depois da entrega (idx_medição >= idx_entrega), o range
    fica vazio → soma=0 → a folga sai SUPERESTIMADA silenciosamente. É violação de precondição da config,
    não um caso de uso a tratar aqui."""
    etapas = cronograma_padrao(cfg)
    cods = [e["codigo"] for e in etapas]
    if codigo_medicao in cods:
        idx_med = cods.index(codigo_medicao)
    elif "9" in cods:
        idx_med = cods.index("9")
    else:
        idx_med = 0
    idx_ent = cods.index(codigo_entrega) if codigo_entrega in cods else len(etapas) - 1
    soma = sum(int(etapas[i]["prazo_dias"]) for i in range(idx_med + 1, idx_ent + 1))
    return (data_entrega - previsao_medicao).days - soma


def somar_dias_uteis(data, n):
    """Avança `n` dias ÚTEIS (seg–sex; sem feriados) a partir de `data`. n=0 → a própria data.
    Único prazo do sistema em dias úteis (o prazo contratual, Fatia 3); o resto usa dias corridos."""
    d = data
    passos = 0
    while passos < n:
        d = d + timedelta(days=1)
        if d.weekday() < 5:   # 0=seg .. 4=sex (pula 5=sáb, 6=dom)
            passos += 1
    return d


def padrao_cabe_no_prazo_contratual(cfg, d0):
    """True se a ENTREGA pelo Cronograma Padrão (d0 + Σ durações CORRIDAS) cabe na data-limite contratual
    (d0 + prazo_contratual_dias_uteis, em dias ÚTEIS). Aviso de coerência, não bloqueio."""
    total = sum(f["prazo_dias"] for f in cronograma_padrao(cfg))
    entrega_padrao = d0 + timedelta(days=total)
    limite = somar_dias_uteis(d0, int((cfg or {}).get("prazo_contratual_dias_uteis") or 50))
    return entrega_padrao <= limite


def projeto_em_atraso(etapas, data_entrega, hoje, codigo_entrega="16"):
    """Sinal de atraso GERAL (Fatia 4, spec §6) — puro. `etapas`: [(codigo, data_prevista_conclusao,
    concluido_em)]; aberta = concluido_em nulo. Atrasado se QUALQUER etapa aberta tem previsão vencida
    (data_prevista_conclusao < hoje), OU se hoje > data_entrega com a etapa de entrega aberta — a "16"
    AUSENTE conta como aberta (não existir a etapa significa que a entrega não foi concluída)."""
    entrega_concluida = False
    for cod, prevista, concluida in etapas or []:
        if concluida is None:
            if prevista is not None and prevista < hoje:
                return True
        elif str(cod) == codigo_entrega:
            entrega_concluida = True
    if data_entrega is not None and hoje > data_entrega and not entrega_concluida:
        return True
    return False


def cronograma_projeto_view(db, projeto_nome, cfg, codigo_entrega="16"):
    """Dados das 3 datas do ciclo por etapa — **Planejada** (`CicloEtapa.data_prevista_conclusao`, do
    Cronograma Padrão gerado na assinatura), **Prazo Limite** (regressivo, âncora `Projeto.data_entrega`)
    e **Executada** (`concluido_em`). Folga = Limite − Planejada. Regressivo/folga só saem se `data_entrega`
    estiver definida. Datas em ISO (ou None). Retorna [{codigo, prazo_limite, planejado, executado,
    folga_dias}]."""
    p = db.get(Projeto, projeto_nome)
    entrega = getattr(p, "data_entrega", None) if p else None
    etapas = [(f["codigo"], f["prazo_dias"]) for f in cronograma_padrao(cfg)]
    # Prazo Limite = regressivo (depende só da entrega); reusa cronogramas() e usa só o regressivo.
    reg = ({x["codigo"]: x["regressivo"] for x in cronogramas(etapas, entrega, entrega, codigo_entrega)}
           if entrega else {})
    cetapas = {e.etapa_codigo: e for e in db.query(CicloEtapa).filter_by(projeto_nome=projeto_nome).all()}
    _iso = lambda d: d.isoformat() if d else None
    out = []
    for cod, _ in etapas:
        ce = cetapas.get(cod)
        planejada = getattr(ce, "data_prevista_conclusao", None) if ce else None
        limite = reg.get(cod)
        executada = getattr(ce, "concluido_em", None) if ce else None
        folga = (limite - planejada).days if (limite and planejada) else None
        out.append({"codigo": cod, "prazo_limite": _iso(limite), "planejado": _iso(planejada),
                    "executado": _iso(executada), "folga_dias": folga})
    return out
