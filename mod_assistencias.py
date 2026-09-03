"""mod_assistencias.py — módulo de domínio Assistências (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6).

Atendimento pós-execução com DUAS dimensões independentes por caso:
  - sub_tipo: Assistência Montagem × Assistência Pós-Conclusão
  - tipo_custo: Paga (cliente) · Loja · Fábrica — DERIVADO do motivo (tabela abaixo)

Realizar um caso dispara o lançamento contábil (motor v7 §6):
  Loja    -> realiza a Provisão de Assistência Técnica (execucao_assistencia)
  Fábrica -> realiza a Provisão de Garantia (execucao_reparo_garantia) + relatório "a cobrar da fábrica"
  Paga    -> gera venda ao cliente (venda_assistencia), sem tocar provisão
"""
import mod_contabil
import mod_escopo
from database import (AssistenciaCaso, AssistenciaExecutor, AssistenciaAnexo, PoolAmbiente,
                      Funcionario, Terceiro)

SUB_TIPOS = {"montagem": "Assistência Montagem", "pos_conclusao": "Assistência Pós-Conclusão"}

# Funções elegíveis pra executar uma assistência (2026-08-06): o critério real é "faz trabalho de
# montagem" — o MESMO critério do papel 'montagem' do Mapa de Atribuições. A Assistência tem
# agendamento próprio, desacoplado do papel 'assistencia' (removido de mod_escopo.PAPEIS em
# 2026-08-06) — mas o catálogo de NOMES em si não precisa ser uma cópia (ACHADO-46, "quinto
# irmão": duas listas com a mesma regra divergem no dia em que alguém edita uma). Importado, não
# copiado — e `funcao_elegivel_assistencia` reaproveita o mesmo papel-primeiro-nome-fallback do
# resto da rodada (ACHADO-46/47).
FUNCOES_ELEGIVEIS = mod_escopo.PAPEL_FUNCOES["montagem"]


def funcao_elegivel_assistencia(funcao_nome, papeis=None):
    """True se a função (por papel 'montagem' declarado, ou por nome como fallback) pode executar
    uma assistência. Mesma regra de `mod_escopo.funcao_compativel("montagem", ...)` — reaproveitada
    aqui, não copiada, embora 'assistencia' não seja mais papel do Mapa."""
    return mod_escopo.funcao_compativel("montagem", funcao_nome, papeis)

# motivo -> (rótulo, tipo_custo). Tabela do doc (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6).
MOTIVOS = {
    "alteracao_projeto":  ("Alteração de projeto solicitada pelo cliente", "paga"),
    "complemento":        ("Complemento", "paga"),
    "erro_projeto":       ("Erro de projeto", "loja"),
    "erro_montagem":      ("Erro de montagem", "loja"),
    "defeito_fabricacao": ("Defeito de fabricação", "fabrica"),
    "empenamento":        ("Empenamento / mau funcionamento", "fabrica"),
}
TIPO_CUSTO_LABEL = {"paga": "Paga (cliente)", "loja": "Loja", "fabrica": "Fábrica"}

# tipo_custo -> evento contábil (mod_contabil.EVENTOS)
EVENTO_POR_CUSTO = {
    "loja":    "execucao_assistencia",
    "fabrica": "execucao_reparo_garantia",
    "paga":    "venda_assistencia",
}


def tipo_custo_de(motivo):
    m = MOTIVOS.get(motivo)
    return m[1] if m else None


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def criar_caso(db, loja_id, projeto_nome, sub_tipo, motivo, descricao, valor, usuario_id, quando=None,
               pool_ambiente_id=None, data_inicio=None, data_fim=None, forma_pagamento="direto",
               classificacao_avulsa=None):
    """`forma_pagamento` ('direto'=Caixa na hora | 'a_prazo'=Fornecedores a Pagar, faturado) vale
    pra qualquer caso não-'paga'. `classificacao_avulsa` ('garantia'|'concessao') só faz sentido —
    e é EXIGIDA — pro caso AVULSO (sem projeto) e não cobrado: a provisão é uma média estatística
    por projeto, sem projeto não há o que debitar, então precisa saber se o custo é coberto
    ('garantia', despesa formal de sempre) ou uma cortesia fora da cobertura ('concessao',
    2026-08-07)."""
    tc = tipo_custo_de(motivo)
    if sub_tipo not in SUB_TIPOS:
        raise ValueError("sub_tipo inválido")
    if tc is None:
        raise ValueError("motivo inválido")
    if forma_pagamento not in ("direto", "a_prazo"):
        raise ValueError("forma_pagamento inválida")
    if (data_inicio and not data_fim) or (data_fim and not data_inicio):
        raise ValueError("Informe início e fim da janela, ou nenhum dos dois.")
    if data_inicio and data_fim and data_inicio > data_fim:
        raise ValueError("Data de início não pode ser depois da data de fim.")
    avulso_nao_cobrado = not projeto_nome and tc != "paga"
    if avulso_nao_cobrado and classificacao_avulsa not in ("garantia", "concessao"):
        raise ValueError("Caso avulso (sem projeto) e não cobrado exige classificação: "
                         "'garantia' (dentro da cobertura) ou 'concessao' (fora).")
    if not avulso_nao_cobrado:
        classificacao_avulsa = None   # só faz sentido nesse cenário — normaliza pra não confundir depois
    caso = AssistenciaCaso(loja_id=loja_id, projeto_nome=(projeto_nome or None), sub_tipo=sub_tipo,
                           motivo=motivo, tipo_custo=tc, descricao=(descricao or None),
                           valor=_num(valor), status="aberto", pool_ambiente_id=pool_ambiente_id,
                           data_inicio=data_inicio, data_fim=data_fim,
                           forma_pagamento=forma_pagamento, classificacao_avulsa=classificacao_avulsa,
                           # ACHADO-48 (02/09): fuso do dono do livro (o caso é sempre de UMA loja).
                           criado_em=quando or mod_contabil.agora_no_fuso(db, "loja", loja_id),
                           criado_por_id=usuario_id)
    db.add(caso)
    db.flush()
    return caso


def definir_equipe(db, caso, executores):
    """Substitui a equipe do caso (delete-all + insert-many — mesmo padrão do Montagem
    multi-executor). `executores` = [(tipo, id)], tipo em 'funcionario'|'terceiro'."""
    db.query(AssistenciaExecutor).filter_by(caso_id=caso.id).delete()
    for tipo, oid in executores:
        reg = AssistenciaExecutor(caso_id=caso.id)
        if tipo == "funcionario":
            reg.funcionario_id = oid
        else:
            reg.terceiro_id = oid
        db.add(reg)
    db.flush()


def equipe_do_caso(db, caso_id):
    """[{chave, nome}] da equipe atual do caso."""
    out = []
    for e in db.query(AssistenciaExecutor).filter_by(caso_id=caso_id).all():
        alvo = db.get(Funcionario, e.funcionario_id) if e.funcionario_id else db.get(Terceiro, e.terceiro_id)
        if alvo:
            chave = ("f:%d" % e.funcionario_id) if e.funcionario_id else ("t:%d" % e.terceiro_id)
            out.append({"chave": chave, "nome": alvo.nome})
    return out


def realizar_caso(db, owner_tipo, owner_id, caso, valor=None, quando=None):
    """Executa/conclui o caso: posta o lançamento conforme o tipo de custo e marca 'realizado'.
    Idempotente por ref ('assist:<id>'). Retorna (ok, erro).

    Três caminhos (2026-08-07, revisão do usuário — a provisão é uma média estatística POR PROJETO,
    então só faz sentido debitá-la quando existe projeto):
      - Paga (cliente): sempre venda ao cliente (`venda_assistencia`), nunca toca provisão.
      - Loja/Fábrica COM projeto: `mod_contabil.efetivar_provisao` (o MESMO motor da Reconciliação
        manual — antes o único caminho, achado da Vera: os dois duplicavam o mesmo evento real sem
        se falar) reconhece a despesa formal na competência real e baixa o passivo conforme
        `caso.forma_pagamento` ('direto'=Caixa, na hora; 'a_prazo'=Fornecedores a Pagar, faturado).
      - Loja/Fábrica AVULSO (sem projeto): `despesa_avulsa` lança direto, SEM provisão nenhuma —
        'garantia' (`classificacao_avulsa`, dentro da cobertura) usa a mesma conta formal de sempre
        (5.2.12/5.2.13); 'concessao' (fora da cobertura, cortesia) usa Concessão a Cliente (5.3.21)."""
    if caso.status == "realizado":
        return True, None
    nv = _num(valor)
    if nv is not None:
        caso.valor = nv
    if not caso.valor or caso.valor <= 0:
        return False, "Informe o valor do caso antes de realizar."
    ref = "assist:%d" % caso.id
    motivo = caso.motivo if caso.tipo_custo == "fabrica" else None   # §6.2: motivo carimba o reparo em garantia

    if caso.tipo_custo == "paga":
        mod_contabil.registrar_evento(db, owner_tipo, owner_id, "venda_assistencia", caso.valor,
                                      projeto_id=caso.projeto_nome, ref=ref, motivo=motivo)
    elif caso.projeto_nome:
        evento = EVENTO_POR_CUSTO[caso.tipo_custo]
        codigo_provisao = mod_contabil.EVENTOS[evento][0]   # débito do evento de execução = a provisão
        mod_contabil.efetivar_provisao(db, owner_tipo, owner_id, caso.projeto_nome, codigo_provisao,
                                       caso.valor, ref=ref, forma_pagamento=caso.forma_pagamento,
                                       origem=evento, motivo=motivo)
    else:
        if caso.classificacao_avulsa == "concessao":
            conta_despesa = "5.3.21"
        else:
            evento = EVENTO_POR_CUSTO[caso.tipo_custo]
            codigo_provisao = mod_contabil.EVENTOS[evento][0]
            ativo_cod = mod_contabil._ativo_diferido_de(codigo_provisao)
            conta_despesa = mod_contabil._PROV_DESPESA_POR_ATIVO[ativo_cod]
        mod_contabil.despesa_avulsa(db, owner_tipo, owner_id, conta_despesa, caso.valor,
                                    caso.forma_pagamento, ref=ref,
                                    historico="Assistência avulsa — %s" % (caso.descricao or caso.motivo))
    caso.status = "realizado"
    caso.ref_lancamento = ref
    caso.realizado_em = quando or mod_contabil.agora_no_fuso(db, owner_tipo, owner_id)   # ACHADO-48
    return True, None


def anexos_do_caso(db, caso_id):
    """[{id, nome_original, enviado_em}] do caso, mais recente primeiro."""
    return [{"id": a.id, "nome_original": a.nome_original,
             "enviado_em": a.enviado_em.isoformat() if a.enviado_em else None}
            for a in db.query(AssistenciaAnexo).filter_by(caso_id=caso_id)
                        .order_by(AssistenciaAnexo.id.desc()).all()]


def serialize(db, caso):
    amb = db.get(PoolAmbiente, caso.pool_ambiente_id) if caso.pool_ambiente_id else None
    return {
        "id": caso.id, "projeto_nome": caso.projeto_nome or "",
        "pool_ambiente_id": caso.pool_ambiente_id,
        "ambiente_nome": (amb.nome_exibicao or amb.nome) if amb else "",
        "data_inicio": caso.data_inicio.isoformat() if caso.data_inicio else None,
        "data_fim": caso.data_fim.isoformat() if caso.data_fim else None,
        "equipe": equipe_do_caso(db, caso.id),
        "anexos": anexos_do_caso(db, caso.id),
        "sub_tipo": caso.sub_tipo, "sub_tipo_label": SUB_TIPOS.get(caso.sub_tipo, caso.sub_tipo),
        "motivo": caso.motivo, "motivo_label": (MOTIVOS.get(caso.motivo) or ["", ""])[0],
        "tipo_custo": caso.tipo_custo, "tipo_custo_label": TIPO_CUSTO_LABEL.get(caso.tipo_custo, caso.tipo_custo),
        "descricao": caso.descricao or "", "valor": caso.valor,
        "status": caso.status, "reembolsado_fabrica": bool(caso.reembolsado_fabrica),
        "forma_pagamento": caso.forma_pagamento, "classificacao_avulsa": caso.classificacao_avulsa,
    }


def listar(db, loja_id, tipo=None, apenas_abertos=False):
    q = db.query(AssistenciaCaso).filter_by(loja_id=loja_id)
    if tipo in ("paga", "loja", "fabrica"):
        q = q.filter(AssistenciaCaso.tipo_custo == tipo)
    if apenas_abertos:
        q = q.filter(AssistenciaCaso.status == "aberto")
    return [serialize(db, c) for c in q.order_by(AssistenciaCaso.id.desc()).all()]


def a_cobrar_fabrica(db, loja_id):
    """Relatório 'a cobrar da fábrica' (v7 §6.2): casos de tipo Fábrica ainda não reembolsados, com o
    custo real documentado. NÃO é Contas a Receber formal — controle p/ negociação com a fábrica."""
    casos = [c for c in db.query(AssistenciaCaso).filter_by(loja_id=loja_id, tipo_custo="fabrica").all()
             if not c.reembolsado_fabrica]
    return {"total": round(sum(c.valor or 0 for c in casos), 2), "qtd": len(casos),
            "itens": [serialize(db, c) for c in casos]}


FORMA_PAGAMENTO_LABEL = {"direto": "Direto (Caixa, pago na hora)", "a_prazo": "A prazo (Fornecedores a Pagar)"}
CLASSIFICACAO_AVULSA_LABEL = {"garantia": "Garantia (dentro da cobertura)", "concessao": "Concessão (fora da cobertura)"}


def meta():
    return {
        "sub_tipos": [{"id": k, "label": v} for k, v in SUB_TIPOS.items()],
        "motivos": [{"id": k, "label": v[0], "tipo_custo": v[1]} for k, v in MOTIVOS.items()],
        "tipo_custo_label": TIPO_CUSTO_LABEL,
        "forma_pagamento_label": FORMA_PAGAMENTO_LABEL,
        "classificacao_avulsa_label": CLASSIFICACAO_AVULSA_LABEL,
    }
