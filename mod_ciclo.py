"""
mod_ciclo.py — Ordem canônica das etapas do ciclo e regras de gating sequencial.

Fonte única da verdade (backend) para "qual é a etapa anterior" e se uma etapa
pode avançar. A ordem aqui (2=Criação do projeto, 3=Briefing) é a canônica nova;
o ETAPAS_CICLO do frontend é alinhado a ela na tarefa de frontend.
"""

# Etapas PRINCIPAIS, na ordem. Sub-etapas ("11a".."11e", "17a") NÃO entram aqui
# — elas são livres dentro do pai.
# "8" (Aprovação financeira I) e "9" (Solicitação de medição) SAÍRAM daqui (achado do
# usuário 2026-08-17): viraram gatilhos independentes dentro da etapa 7 (Contrato) — cada
# uma um botão no card do Contrato, liberada só pelo contrato assinado, sem depender uma da
# outra. Continuam existindo como CicloEtapa/código próprio (nada migra) — só não são mais
# principais. Ver PREDECESSOR_OVERRIDE logo abaixo pra como o gating delas (e do "10", que
# ainda depende especificamente de "9") é resolvido sem estarem na lista.
# "14"/"15"/"16" SAÍRAM daqui também (achado do usuário 2026-08-18): "Produção"(13),
# "Entrega no depósito→Recebimento do Pedido"(14), "Emissão da NFe do cliente"(15) e
# "Entrega no cliente"(16) viram visualmente UMA etapa só, "Logística e Expedição" — "13" é
# a representante em ETAPAS_PRINCIPAIS; 14/15/16 continuam com CicloEtapa/código próprio,
# concluindo em sequência real (ver PREDECESSOR_OVERRIDE/PROXIMA_OVERRIDE) — diferente do
# caso 8/9 (paralelos), aqui a cadeia 13→14→15→16→17 é sequencial de verdade, só deixou de
# aparecer como 4 abas separadas no fichário. Ver GRUPOS_ESPINHACO/etapa_concluida_agregada
# pra quem precisa saber se "o grupo inteiro" já terminou (não só a Produção).
ETAPAS_PRINCIPAIS = [
    "1", "2", "3", "4", "7", "10",
    "11", "12", "13", "17", "18", "19", "20",
    "21",   # FASE D2: Conciliação Final — fecha os números e encerra o projeto (status "Concluído")
]

ETAPA_NOME = {
    "1": "Cadastro do Cliente",
    "2": "Criação do projeto",
    "3": "Briefing",
    "4": "Orçamento",
    "7": "Contrato",
    "8": "Aprovação financeira I",
    "9": "Solicitação de medição",
    "10": "Medição",
    "11": "Projeto executivo",
    "12": "Conferência e Implantação do Pedido",
    "13": "Produção",
    "14": "Recebimento do Pedido",
    "15": "Emissão da NFe do cliente",
    "16": "Entrega no cliente",
    "17": "Montagem",
    "18": "Assistência pós Montagem",
    "19": "Vistoria final",
    "20": "Aprovação final",
    "21": "Conciliação Final",
}

# Status que contam como "etapa concluída" para fins de gating (espelha o
# conjunto de status conclusivos do handler PATCH /ciclo em main.py).
STATUS_CONCLUSIVOS = frozenset({
    "concluido", "aprovado", "assinado", "vigente",
    "implantado", "realizado", "entregue", "emitida",
})


# ── Projeto Executivo (etapa 11) — subfases enriquecidas ──────────────────────
SUBFASES_PE = {
    "11a": {"nome": "Planta de pontos de PE",       "tipo_doc": "pe_planta_pontos",
            "doc_label": "arquivo de medição",       "botao": "Encaminhar para PE",       "revisavel": False},
    "11b": {"nome": "Reunião de alinhamento",        "tipo_doc": "pe_relatorio_alinhamento",
            "doc_label": "relatório da reunião",     "botao": "Projeto Alinhado",         "revisavel": True},
    "11c": {"nome": "Revisão de PE",                 "tipo_doc": "pe_projeto_executivo",
            "doc_label": "Projeto Executivo",        "botao": "Concluído",                "revisavel": True},
    "11e": {"nome": "Aprovação do PE pelo cliente",  "tipo_doc": "pe_pe_assinado",
            "doc_label": "Projeto Executivo Assinado","botao": "Concluir Projeto Executivo","revisavel": False},
}

# Nome de QUALQUER sub-etapa (não só as 4 "enriquecidas" de SUBFASES_PE acima) — espelha
# ETAPAS_CICLO do frontend (static/index.html) pros códigos "11d"/"17a", que não têm entrada em
# SUBFASES_PE (11d é gerida por outro handler; 17a não tem doc/botão associado). Achado da Vera
# (2026-08-26, E2E): a validação de `POST /ciclo/<cod>/pos-conclusao` só reconhecia códigos de
# ETAPA_NOME (etapas principais) — quando a "próxima etapa" calculada pelo frontend caía numa
# sub-etapa (ex.: "17a" logo depois da Montagem), o endpoint recusava com 400 mesmo sendo um
# alvo legítimo.
NOME_SUBETAPA = {cod: sf["nome"] for cod, sf in SUBFASES_PE.items()}
NOME_SUBETAPA["11d"] = "Aprovação financeira II"
NOME_SUBETAPA["17a"] = "Pendências de montagem"


def nome_etapa_qualquer(codigo):
    """Nome de exibição pra QUALQUER código válido — principal ou sub-etapa. Cai no código cru
    só se `codigo` não for reconhecido (não deveria acontecer com dado consistente)."""
    return ETAPA_NOME.get(codigo) or NOME_SUBETAPA.get(codigo) or codigo


def etapa_codigo_valido(codigo):
    """True se `codigo` é uma etapa OU sub-etapa reconhecida (principal ou não)."""
    return codigo in ETAPA_NOME or codigo in NOME_SUBETAPA

# Subfases que precisam estar concluídas antes de concluir o PE (11e).
# 11d é a aprovação financeira II (gerida por outro handler, sem entrada em
# SUBFASES_PE), mas exigida aqui como pré-requisito para concluir o PE.
PE_SUBFASES_OBRIGATORIAS = ["11a", "11b", "11c", "11d"]

# Subfase final do PE: concluí-la conclui a etapa-mãe 11.
PE_SUBFASE_FINAL = "11e"


def tipo_doc_de(codigo):
    """Retorna o tipo_doc da subfase de PE, ou None se o código não for uma subfase enriquecida."""
    sf = SUBFASES_PE.get(codigo)
    return sf["tipo_doc"] if sf else None


def guarda_conclusao(codigo, tipos_presentes, status_por_codigo, pe_ambientes=None,
                     aprovacao_pe=None):
    """(ok, erro). tipos_presentes: set de tipos de documento já carregados na subfase.
    status_por_codigo: {codigo: status} — usado no 11e para exigir 11a-11d concluídas.
    pe_ambientes: (total_pool, com_pe) — só a 11c usa (2026-07-21): o documento único da
    subfase saiu da UI e o carregamento é POR AMBIENTE na tabela de comparação; a 11c
    conclui quando todo ambiente do pool tem PE carregado. Documento único presente segue
    valendo (projetos legados). None → regra antiga do documento (chamador não informa).
    aprovacao_pe: bool — só a 11e usa (correção Fatia 3, 2026-07-21): o upload de "PE
    Assinado" foi substituído pela APROVAÇÃO DO PROJETO EXECUTIVO assinada no sistema
    (documento próprio, mecanismo do contrato/aditivo). Doc legado segue valendo.
    None → regra antiga do documento."""
    sf = SUBFASES_PE.get(codigo)
    if not sf:
        return (False, "Subfase de PE desconhecida.")
    doc_ok = sf["tipo_doc"] in tipos_presentes
    if codigo == "11c" and pe_ambientes is not None and not doc_ok:
        total, com_pe = pe_ambientes
        if total <= 0:
            return (False, "Projeto sem ambientes no pool — carregue o PE dos ambientes antes de concluir.")
        if com_pe < total:
            return (False, "Carregue o PE de todos os ambientes na comparação antes de "
                           f"'{sf['botao']}' ({com_pe}/{total} carregados).")
    elif codigo == PE_SUBFASE_FINAL and aprovacao_pe is not None and not doc_ok:
        if not aprovacao_pe:
            return (False, "Aprove o Projeto Executivo (assinatura da Aprovação) antes de "
                           f"'{sf['botao']}'.")
    elif not doc_ok:
        return (False, f"Carregue o documento ({sf['doc_label']}) antes de '{sf['botao']}'.")
    if codigo == PE_SUBFASE_FINAL:
        faltando = [c for c in PE_SUBFASES_OBRIGATORIAS
                    if status_por_codigo.get(c) not in STATUS_CONCLUSIVOS]
        if faltando:
            return (False, "Conclua as subfases anteriores do PE: " + ", ".join(faltando) + ".")
    return (True, "")


def versao_atual(documentos, tipo):
    """documentos: lista de dicts com 'tipo' e 'enviado_em'. Última versão do tipo, ou None."""
    do_tipo = [d for d in documentos if d.get("tipo") == tipo]
    if not do_tipo:
        return None
    return max(do_tipo, key=lambda d: d["enviado_em"])


# ── Etapas operacionais (12/13/14) — ações e guardas de conclusão ─────────────
# Etapas principais pós-PE com ações próprias no frontend. Cycle-gated (sem
# capability dedicada): quem já pode avançar o ciclo executa. Só a 12 aceita
# upload (XMLs dos pedidos); 13/14 guardam texto em CicloEtapa.observacoes.
ETAPAS_OPERACIONAIS = {
    "12": {"nome": "Conferência e Implantação do Pedido", "exige": "xml",
           "tipo_doc": "implantacao_pedido_xml", "botao": "Encaminhar Pedidos à Fábrica"},
    "13": {"nome": "Produção",              "exige": "numeros",
           "botao": "Produção Concluída"},
    "14": {"nome": "Recebimento do Pedido", "exige": "relatorio",
           "botao": "Concluir Relatório de Entrega"},
}


def tipo_doc_operacional(codigo):
    """tipo_doc da etapa operacional que aceita upload (só a 12), ou None."""
    op = ETAPAS_OPERACIONAIS.get(codigo)
    return op.get("tipo_doc") if op else None


def _tem_linha_nao_vazia(texto):
    return any(linha.strip() for linha in (texto or "").splitlines())


def guarda_conclusao_operacional(codigo, tem_xml, numeros_txt, relatorio_txt):
    """(ok, erro) para concluir uma etapa operacional (12/13/14).
    tem_xml: bool (existe ao menos um XML na etapa 12).
    numeros_txt / relatorio_txt: texto de observacoes da etapa 13 / 14."""
    op = ETAPAS_OPERACIONAIS.get(codigo)
    if not op:
        return (False, "Etapa operacional desconhecida.")
    exige = op["exige"]
    if exige == "xml":
        if not tem_xml:
            return (False, "Carregue pelo menos um pedido (XML) antes de encaminhar à fábrica.")
    elif exige == "numeros":
        if not _tem_linha_nao_vazia(numeros_txt):
            return (False, "Informe os números dos pedidos antes de concluir a produção.")
    elif exige == "relatorio":
        if not _tem_linha_nao_vazia(relatorio_txt):
            return (False, "Preencha o Relatório de Entrega antes de concluí-lo.")
    else:
        raise ValueError(f"exige desconhecido em ETAPAS_OPERACIONAIS: {exige!r}")
    return (True, "")


# Etapas que exigem autorização financeira (login+senha de quem pode aprovar).
ETAPAS_APROVACAO_FINANCEIRA = frozenset({"8", "11d"})


def exige_aprovacao_financeira(codigo):
    return codigo in ETAPAS_APROVACAO_FINANCEIRA


# Faixas de titularidade do Ciclo (ARQUITETURA-MODULOS.md §Governança). Cada trecho de etapas pertence
# a uma faixa/equipe; as transições entre faixas são os gates de controle (8, 11d). Mapa explícito —
# antes a titularidade estava só implícita nas capabilities/constantes.
FAIXA_POR_ETAPA = {
    "1": "vendas", "2": "vendas", "3": "vendas", "4": "vendas", "7": "vendas",
    "8": "gate_financeiro_1",
    "9": "execucao_projeto", "10": "execucao_projeto",
    "11": "execucao_projeto", "11a": "execucao_projeto", "11b": "execucao_projeto",
    "11c": "execucao_projeto", "11e": "execucao_projeto",
    "11d": "gate_financeiro_2",
    "12": "expedicao", "13": "expedicao", "14": "expedicao", "15": "expedicao", "16": "expedicao",
    "17": "montagem", "18": "montagem", "19": "montagem", "20": "montagem",
    "21": "conciliacao_final",   # FASE D2: encerramento financeiro do projeto
}


def faixa_da_etapa(codigo):
    """Faixa de titularidade (dono operacional) da etapa, ou None se desconhecida.
    Faixas 'gate_*' são transições de controle (aprovação financeira). Ver Governança do Ciclo."""
    return FAIXA_POR_ETAPA.get(str(codigo))


def _parse_codigo(codigo):
    """'11a' -> (11, 'a'); '2' -> (2, ''). Para ordenação e agrupamento por pai."""
    num, suf = "", ""
    for ch in str(codigo):
        if ch.isdigit() and not suf:
            num += ch
        else:
            suf += ch
    return (int(num) if num else 0, suf)


def is_principal(codigo):
    return codigo in ETAPAS_PRINCIPAIS


def etapa_pai(codigo):
    """Etapa principal de uma sub-etapa ('11a' -> '11', '17a' -> '17').
    Retorna None se o código já for principal ou não tiver pai principal."""
    num, suf = _parse_codigo(codigo)
    if not suf:                      # já é principal (sem sufixo)
        return None
    pai = str(num)
    return pai if pai in ETAPAS_PRINCIPAIS else None


# Predecessor explícito pra código que não segue mais a posição em ETAPAS_PRINCIPAIS (achado
# do usuário 2026-08-17, ver comentário acima de ETAPAS_PRINCIPAIS): "8" e "9" dependem
# diretamente de "7" (em paralelo entre si, não uma da outra); "10" continua dependendo
# especificamente de "9" (não bastaria só o contrato assinado — a medição precisa da
# solicitação assinada primeiro), mesmo "9" não sendo mais o predecessor posicional de "10"
# em ETAPAS_PRINCIPAIS (que agora vai direto de "7" pra "10").
# "14"→"13", "15"→"14", "16"→"15" (achado 2026-08-18): preservam a dependência sequencial
# REAL dentro do grupo "Logística e Expedição" — sem elas, "14" (que já é gatilhada de
# verdade pelo PATCH genérico + ETAPAS_OPERACIONAIS) perderia o gate. "17"→"16" é necessária
# porque, tirando 14/15/16 de ETAPAS_PRINCIPAIS, o predecessor POSICIONAL de "17" passaria a
# ser "13" direto — pulando o resto do grupo.
PREDECESSOR_OVERRIDE = {
    "8": "7", "9": "7", "10": "9",
    "14": "13", "15": "14", "16": "15", "17": "16",
}

# Espelho, na direção contrária, do PREDECESSOR_OVERRIDE acima — só pra 13→14→15→16→17
# (achado 2026-08-18): a "passagem automática de fase" no chat (etapa_seguinte, usada pelo
# PATCH genérico pra notificar quem é responsável pela PRÓXIMA etapa ao concluir qualquer
# uma) precisa continuar funcionando de verdade nessa cadeia — diferente de 8/9 (que viraram
# paralelas e perderam essa notificação de propósito), aqui é um handoff sequencial real
# entre equipes (produção → depósito → fiscal → expedição) que vale a pena manter.
PROXIMA_OVERRIDE = {"13": "14", "14": "15", "15": "16", "16": "17"}

# Grupos do espinhaço (achado do usuário 2026-08-18): "13" representa visualmente todo o
# grupo "Logística e Expedição" (Produção→Entrega no Cliente) — mas cada código continua
# com CicloEtapa própria, concluindo em separado. Quem varre ETAPAS_PRINCIPAIS achando "a
# etapa atual" (ou contando etapas concluídas) precisa saber que "13" só está de fato
# concluída quando TODO o grupo está — ver etapa_concluida_agregada.
GRUPOS_ESPINHACO = {"13": ["13", "14", "15", "16"]}

# Rótulo do GRUPO quando "13" é a etapa atual — espelha `_FICHA_GRUPO_NOME` do frontend
# (static/index.html). Achado da Vera (2026-08-26, E2E): a lista de Projetos e o diálogo de
# transferência de responsabilidade usavam ETAPA_NOME["13"] cru ("Produção") pra essa posição,
# divergindo do fichário do projeto (que mostra "Logística e Expedição") — mesma etapa, nomes
# diferentes em telas diferentes. Manter os dois dicionários em sincronia se o grupo mudar.
GRUPO_NOME = {"13": "Logística e Expedição"}


def codigos_relevantes_fase():
    """ETAPAS_PRINCIPAIS + os códigos "escondidos" dentro de grupos do espinhaço — pra quem
    monta um status_map por projeto (achar "a etapa atual") não perder o status real de
    "14"/"15"/"16", que não estão mais em ETAPAS_PRINCIPAIS."""
    extra = [c for grupo in GRUPOS_ESPINHACO.values() for c in grupo if c not in ETAPAS_PRINCIPAIS]
    return ETAPAS_PRINCIPAIS + extra


def etapa_concluida_agregada(codigo, status_por_codigo):
    """True se `codigo` (ou, sendo cabeça de um grupo do espinhaço, TODO o grupo) está
    concluído. Sem isso, "13" apareceria concluído assim que só a Produção terminasse — quem
    varre ETAPAS_PRINCIPAIS achando "a próxima etapa não concluída" (listagem de projetos,
    árvore administrativa) pularia direto pra "17", ignorando 14/15/16 ainda pendentes."""
    grupo = GRUPOS_ESPINHACO.get(codigo, [codigo])
    return all(status_por_codigo.get(c) in STATUS_CONCLUSIVOS for c in grupo)


def etapa_anterior(codigo):
    """Código da etapa principal imediatamente anterior, ou None."""
    if codigo in PREDECESSOR_OVERRIDE:
        return PREDECESSOR_OVERRIDE[codigo]
    if codigo not in ETAPAS_PRINCIPAIS:
        return None
    i = ETAPAS_PRINCIPAIS.index(codigo)
    return ETAPAS_PRINCIPAIS[i - 1] if i > 0 else None


def etapa_seguinte(codigo):
    """Código da etapa principal imediatamente seguinte, ou None (última). Usada na passagem
    oficial automática do chat (decisão 17): concluir uma fase aponta para a próxima."""
    if codigo in PROXIMA_OVERRIDE:
        return PROXIMA_OVERRIDE[codigo]
    if codigo not in ETAPAS_PRINCIPAIS:
        return None
    i = ETAPAS_PRINCIPAIS.index(codigo)
    return ETAPAS_PRINCIPAIS[i + 1] if i + 1 < len(ETAPAS_PRINCIPAIS) else None


def ordenar_codigos(codigos):
    """Ordena códigos numericamente, com sub-etapas logo após o pai."""
    return sorted(codigos, key=_parse_codigo)


def chave_ordenacao(codigo):
    """Key para sorted() quando se ordena objetos por etapa_codigo."""
    return _parse_codigo(codigo)


def pode_avancar(codigo, status_por_codigo, bloqueadores_ativos=None):
    """
    True se a etapa pode sair de 'pendente' (iniciar/concluir).
    Sub-etapas herdam o gating da etapa-mãe (desbloqueiam junto com ela).
    Principais exigem a anterior concluída.
    status_por_codigo: dict {codigo: status}.

    bloqueadores_ativos (chat Fatia 3, spec seção 3 — OPCIONAL, default None mantém o
    comportamento de sempre): set de etapa_codigo com transferência BLOQUEADORA não
    resolvida; o valor especial "*" é bloqueador SEM etapa e trava o ciclo INTEIRO.
    Bloqueador vence tudo — False antes de qualquer outra checagem, mesmo com a etapa
    anterior concluída. Sub-etapa herda o bloqueio da mãe pela recursão de sempre.
    """
    if bloqueadores_ativos:
        if "*" in bloqueadores_ativos or codigo in bloqueadores_ativos:
            return False
    # PREDECESSOR_OVERRIDE (8/9/10) primeiro: essas exigem a etapa indicada CONCLUÍDA, igual
    # a uma principal comum — diferente da herança de subfase abaixo (11a etc.), que só exige
    # a etapa-mãe "alcançável", não necessariamente concluída.
    if codigo in PREDECESSOR_OVERRIDE:
        return status_por_codigo.get(PREDECESSOR_OVERRIDE[codigo]) in STATUS_CONCLUSIVOS
    if codigo not in ETAPAS_PRINCIPAIS:
        pai = etapa_pai(codigo)
        if pai is None:
            return True
        return pode_avancar(pai, status_por_codigo, bloqueadores_ativos)
    ant = etapa_anterior(codigo)
    if ant is None:
        return True
    return status_por_codigo.get(ant) in STATUS_CONCLUSIVOS


def codigos_a_resetar(codigo_alvo, codigos_existentes):
    """
    Reabertura em cascata: o próprio alvo + todos posteriores (principais e
    suas sub-etapas). Qualquer código cujo (num, sufixo) >= (num, sufixo) do alvo.
    """
    alvo = _parse_codigo(codigo_alvo)
    return [c for c in codigos_existentes if _parse_codigo(c) >= alvo]


def reabertura_bloqueada_por_contrato(codigos_a_resetar_lista, contrato_status):
    """True se a cascata desfaria a etapa 7 (Contrato) com contrato já firmado."""
    return "7" in set(codigos_a_resetar_lista) and contrato_status in ("assinado", "vigente")
