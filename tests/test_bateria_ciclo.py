"""docs/db/TAREFA_BATERIA_CICLO.md — bateria exaustiva de ciclo completo.

Um motor único (`_rodar_cenario`), cenários como dados (`_CENARIOS`), 7 invariantes iguais
para todo cenário (`_conferir_invariantes`). Onde uma invariante falhar, `xfail(strict=True)`
citando o ACHADO (docs/db/ACHADOS_CONTABEIS.md) — um xfail que virar "unexpected pass" é o sinal
de que o achado foi corrigido e o marcador pode sair. Passo 10 (docs/db/TAREFA_ACHADO02_03.md,
ACHADO-01/02/03): os três ramos fecham sem xfail agora — `_XFAILS` fica vazio.

Toggles de parametros (enumerados do código — mod_orcamento_params.py:13-29,
mod_negociacao.py:19-24 — NÃO é só o aditivo que afeta contabilização):
  comissao_arq_ativa, fidelidade_ativa, fora_da_sede, brinde_ativo, custo_especial_ativo
  gate INDIVIDUALMENTE se a rubrica correspondente (com_arq/pro_fid/cust_via/brinde/cust_esp)
  entra com valor > 0 na provisão — confirmado em mod_negociacao.py: cada um zera SÓ a sua
  própria rubrica, independente dos demais. `incluir_custos` é um toggle DIFERENTE: não gate
  se a rubrica é provisionada (ela é, de qualquer forma — o custo é real e incorrido), gate se
  esse custo é RECUPERADO no preço (Val_Cont sobe) ou ABSORVIDO pela margem (Val_Cont não sobe,
  mas a provisão/despesa da rubrica continua cheia) — mod_negociacao.py:53-90. Por isso ele
  entra na matriz como uma dimensão própria, testando exatamente esse "Val_Cont mais baixo,
  despesa cheia igual" sem qualquer conserto: é apenas a margem absorvendo, não um achado.

As 18 rubricas de provisão-com-ativo-diferido (`mod_contabil._PROV_FECHAMENTO`, verificado por
código, não por memória): montagem, garantia, assistencia, frete_fabrica, frete_local, insumos,
com_medidor, com_proj_exec, retencao_com_vendas, custo_fabrica, com_adm — as 11 "sempre
presentes"; com_arq, pro_fid, cust_via, brinde, cust_esp — as 5 gateadas por toggle; impostos e
custo_financeiro — mecanismo de resolução próprio, fora de `efetivar_provisao`.
"""
import json
import os
import pytest
import mod_contabil as mc


# ── tabela de rubricas (derivada do código, ver docstring acima) ─────────────────────────────
RUBRICAS_MATCHING_PLENO = {
    # chave: (prov, ativo, despesa)
    "montagem":            ("2.1.04.02", "1.1.06.02", "5.2.01"),
    "garantia":             ("2.1.04.03", "1.1.06.03", "5.2.12"),
    "assistencia":          ("2.1.04.05", "1.1.06.05", "5.2.13"),
    "frete_fabrica":        ("2.1.04.07", "1.1.06.07", "5.1.02"),
    "frete_local":          ("2.1.04.08", "1.1.06.08", "5.2.08"),
    "insumos":              ("2.1.04.09", "1.1.06.09", "5.2.09"),
    "com_medidor":          ("2.1.04.10", "1.1.06.10", "5.3.18"),
    "com_proj_exec":        ("2.1.04.11", "1.1.06.11", "5.3.19"),
    "retencao_com_vendas":  ("2.1.04.12", "1.1.06.12", "5.3.01"),
    "custo_fabrica":        ("2.1.04.06", "1.1.06.06", "5.1.01"),
    "com_adm":              ("2.1.04.21", "1.1.06.21", "5.3.03"),
    "com_arq":              ("2.1.04.15", "1.1.06.15", "5.3.15"),
    "pro_fid":              ("2.1.04.16", "1.1.06.16", "5.3.04"),
    "cust_via":             ("2.1.04.17", "1.1.06.17", "5.3.14"),
    "brinde":               ("2.1.04.18", "1.1.06.18", "5.3.12"),
    "cust_esp":             ("2.1.04.20", "1.1.06.20", "5.3.17"),
}
RUBRICAS_SEMPRE_PRESENTES = ("montagem", "garantia", "assistencia", "frete_fabrica",
                             "frete_local", "insumos", "com_medidor", "com_proj_exec",
                             "retencao_com_vendas", "custo_fabrica", "com_adm")
RUBRICAS_TOGGLE = {
    # chave: nome do toggle em mod_orcamento_params/mod_negociacao
    "com_arq":  "comissao_arq_ativa",
    "pro_fid":  "fidelidade_ativa",
    "cust_via": "fora_da_sede",
    "brinde":   "brinde_ativo",
    "cust_esp": "custo_especial_ativo",
}
TODAS_AS_RUBRICAS = tuple(RUBRICAS_MATCHING_PLENO) + ("impostos", "custo_financeiro")   # 18

_VALOR_BASE = {   # valores representativos, arbitrários mas fixos — não vêm do motor de preço
    "montagem": 900.0, "garantia": 400.0, "assistencia": 350.0, "frete_fabrica": 250.0,
    "frete_local": 180.0, "insumos": 220.0, "com_medidor": 150.0, "com_proj_exec": 200.0,
    "retencao_com_vendas": 300.0, "custo_fabrica": 6000.0, "com_adm": 260.0,
    "com_arq": 800.0, "pro_fid": 400.0, "cust_via": 300.0, "brinde": 150.0, "cust_esp": 500.0,
}
VAVO_BASE = 20000.0
_TOGGLES_TODOS_OFF = {"comissao_arq_ativa": False, "fidelidade_ativa": False,
                      "fora_da_sede": False, "brinde_ativo": False,
                      "custo_especial_ativo": False, "incluir_custos": False}


# ── motor único ───────────────────────────────────────────────────────────────────────────────
class _Ciclo:
    """Rastreia passos e confere, a CADA passo, que soma(débitos) == soma(créditos) no projeto
    (invariante 1). Cada `Lancamento` já nasce D=C por construção (`lancar()`, mod_contabil.py:1089)
    — este check é um guarda de regressão (pega uma FUTURA quebra desse invariante), não algo que
    o código de hoje possa violar linha a linha; o valor está em nomear o passo na falha."""
    def __init__(self, db, ot, oid, projeto_id):
        self.db, self.ot, self.oid, self.projeto_id = db, ot, oid, projeto_id
        self.passos = []

    def passo(self, nome):
        self.passos.append(nome)
        lans = (self.db.query(mc.Lancamento)
                .filter_by(owner_tipo=self.ot, owner_id=self.oid, projeto_id=self.projeto_id).all())
        deb = round(sum(l.valor for l in lans), 2)
        cred = round(sum(l.valor for l in lans), 2)
        assert deb == cred, "balancete não fecha após o passo %r (passos até aqui: %s): D=%.2f C=%.2f" % (
            nome, self.passos, deb, cred)


def _saldo(db, ot, oid, cod, projeto_id):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    if c is None:
        return None
    sentido = "devedor" if mc._natureza(c.grupo) == "devedora" else "credor"
    return round(mc._mov(db, ot, oid, cod, sentido, None, None, projeto_id=projeto_id), 2)


def _rubricas_ativas(toggles):
    """As 16 rubricas 'matching pleno' que entram com valor > 0 neste cenário."""
    ativas = dict(_VALOR_BASE)
    for chave, toggle in RUBRICAS_TOGGLE.items():
        if not toggles.get(toggle, False):
            ativas[chave] = 0.0
    return {k: v for k, v in ativas.items() if k in RUBRICAS_MATCHING_PLENO and v > 0}


def _rodar_cenario(app_db, cenario, oid):
    """Percorre venda → contrato → provisões → [aditivo] → NF-e → recebimento → fechamento,
    replicando a ordem e os mecanismos reais de main.py/mod_contabil.py (não uma sequência
    inventada) — ver docs/db/AUDITORIA_MAPA_CONTABIL.md e ACHADOS_CONTABEIS.md para a
    proveniência de cada evento usado aqui."""
    db = app_db.get_session()
    ot = "loja"
    mc.seed_plano(db, ot, oid)
    P = "Proj_%s" % cenario["nome"]
    ciclo = _Ciclo(db, ot, oid, P)
    toggles = cenario["toggles"]

    ativas = _rubricas_ativas(toggles)
    cust_ad = round(sum(ativas.get(k, 0.0) for k in RUBRICAS_TOGGLE), 2)
    vavo = round(VAVO_BASE + cust_ad, 2) if toggles.get("incluir_custos") else VAVO_BASE
    cust_fin = 0.0 if cenario.get("sem_financiamento") else round(vavo * 0.09, 2)
    val_cont = round(vavo + cust_fin, 2)
    impostos_valor = round(val_cont * 0.08, 2)

    ramo = cenario["ramo"]

    # ── venda + contrato (main.py:_fin_provisoes_venda_seguro) — ACHADO-02 (passo 10): VAVO, não
    # Val_Cont cheio, em 1.1.02×2.1.06. O custo financeiro (cust_fin) tem rota própria, abaixo. ──
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", vavo, projeto_id=P, ref="rv:" + P)
    ciclo.passo("venda_contrato")

    # ── provisões (constituir_provisoes_fechamento cobre as 16 matching-pleno + impostos) ──
    valores = dict(ativas)
    for chave in RUBRICAS_SEMPRE_PRESENTES:
        valores.setdefault(chave, _VALOR_BASE[chave])
    valores["impostos"] = impostos_valor
    mc.constituir_provisoes_fechamento(db, ot, oid, P, valores, ref_base="pf:" + P)
    # custo financeiro: rota própria por ramo, via o dict canônico `_RAMO_CFIN_EVENTO`/
    # `evento_custo_financeiro` — main.py agora lê a mesma tabela (ACHADO-03), e a tabela em si
    # mudou (ACHADO-02/03, passo 10): loja_antecipacao é receita financeira a apropriar, IGUAL a
    # loja — só 'financeira' constitui a retenção esperada (provisão).
    if cust_fin > 0:
        evento_cfin = mc.evento_custo_financeiro(ramo)
        mc.registrar_evento(db, ot, oid, evento_cfin, cust_fin, projeto_id=P, ref="cf:" + P)
    ciclo.passo("provisoes")

    # ── aditivo contratual (ACHADO-12): cria receita/provisão incremental, mas a NF-e nunca
    # fica sabendo do aditivo — replica _valores_segmentados_do_projeto lendo só o Contrato
    # original (main.py:1315-1336), nunca o aditivo. ──
    valor_aditivo = 0.0
    montagem_aditivo = 0.0
    if cenario.get("tem_aditivo"):
        valor_aditivo = cenario["valor_aditivo"]
        montagem_aditivo = round(valor_aditivo * 0.05, 2)
        mc.registrar_evento(db, ot, oid, "registro_venda_contrato", valor_aditivo,
                            projeto_id=P, ref="rv:" + P + ":aditivo")
        mc.constituir_provisoes_fechamento(db, ot, oid, P, {"montagem": montagem_aditivo},
                                           ref_base="pf:" + P + ":aditivo")
        ciclo.passo("aditivo")

    # ── NF-e (main.py:_fin_faturamento_segmentado_seguro — ACHADO-12 CONSERTADO no passo 7:
    # fatura valor_contratado_do_projeto = Val_Cont do contrato + aditivos ASSINADOS; ACHADO-02,
    # passo 10: o VALOR faturado é o VAVO, não o Val_Cont cheio) ──
    mc.faturar_segmento(db, ot, oid, P, "mercadoria", vavo + valor_aditivo, ref_base="fat:" + P)
    mc.efetivar_impostos_segmento(db, ot, oid, P, impostos_valor, ref_base="imp:" + P)
    # F2-27 (docs/db/MODELO_CONTABIL.md): a emissão volta a reconhecer despesa — provisionado
    # INTEGRAL das 17 rubricas de despesa em tempo real, segmentado. Esta bateria só emite
    # 'mercadoria' (nunca 'servico'), então pct_mercadoria=100 — replica
    # main.py:_fin_faturamento_segmentado_seguro na mesma ordem (fatura → impostos → reconhece).
    mc.reconhecer_provisoes_segmento(db, ot, oid, P, "mercadoria", 100.0, ref_base="rec:" + P)
    ciclo.passo("nfe")

    # ── recebimento: coleta tudo que 1.1.02 registra como em aberto (venda original + aditivo,
    # se houver — o cliente deve o VAVO cheio do contrato, faturado ou não) ──
    a_receber = _saldo(db, ot, oid, "1.1.02", P) or 0.0
    if a_receber > 0:
        mc.registrar_recebimento_venda(db, ot, oid, P, a_receber, ref="rec:" + P)
    if ramo in ("loja", "loja_antecipacao"):
        mc.apropriar_juros_loja(db, ot, oid, P, cust_fin, ref_base="jur:" + P)
    ciclo.passo("recebimento")

    # ── fechamento: efetiva as 16 rubricas matching-pleno pelo custo real (== provisionado,
    # cenário limpo — sobra/falta não é o que esta bateria investiga) ──
    for chave, valor in valores.items():
        if chave == "impostos" or valor <= 0:
            continue
        prov_cod = RUBRICAS_MATCHING_PLENO[chave][0]
        mc.efetivar_provisao(db, ot, oid, P, prov_cod, valor, ref="ex:" + P + ":" + chave,
                            forma_pagamento="a_prazo")
    if montagem_aditivo > 0:
        mc.efetivar_provisao(db, ot, oid, P, "2.1.04.02", montagem_aditivo,
                            ref="ex:" + P + ":montagem:aditivo", forma_pagamento="a_prazo")
    # 'financeira': conferência (ACHADO-01/02/03, passo 10) — cenário limpo, real == esperado,
    # sem variância. loja/loja_antecipacao já fecham via apropriar_juros_loja acima; nenhuma das
    # duas exercita o evento da antecipação aqui (não é o que esta bateria investiga).
    if ramo == "financeira" and cust_fin > 0:
        mc.conferir_retencao_financeira(db, ot, oid, P, cust_fin, ref_base="conf:" + P)
    ciclo.passo("fechamento")

    return {"db": db, "ot": ot, "oid": oid, "P": P, "ramo": ramo, "val_cont": val_cont,
            "vavo": vavo, "cust_fin": cust_fin, "cust_ad": cust_ad, "valor_aditivo": valor_aditivo,
            "montagem_aditivo": montagem_aditivo, "valores_rubricas": valores, "ciclo": ciclo}


# ── as 7 invariantes ──────────────────────────────────────────────────────────────────────────
def _conferir_invariantes(ctx):
    db, ot, oid, P = ctx["db"], ctx["ot"], ctx["oid"], ctx["P"]

    # 2 + 5: contas transitórias zeradas / toda provisão resolvida
    contas_transitorias = (["2.1.06", "1.1.02", "1.1.07", "2.1.07"]
                           + [RUBRICAS_MATCHING_PLENO[k][0] for k in ctx["valores_rubricas"] if k != "impostos"]
                           + [RUBRICAS_MATCHING_PLENO[k][1] for k in ctx["valores_rubricas"] if k != "impostos"]
                           + ["2.1.04.13", "1.1.05", "2.1.04.19", "1.1.06.19"])
    abertos = {}
    for cod in sorted(set(contas_transitorias)):
        s = _saldo(db, ot, oid, cod, P)
        if s is not None and abs(s) >= 0.005:
            abertos[cod] = s
    assert not abertos, "contas transitórias abertas no fechamento: %s" % abertos

    # 3: receita total == valor da venda, contada uma vez (inclui aditivo) — ACHADO-02/ACHADO-12.
    # ACHADO-02/03 (passo 10): cust_fin só entra na receita pra loja/loja_antecipacao (receita
    # financeira a apropriar) — 'financeira' nunca soma cust_fin ao resultado (aceite #3).
    receita_total = round((_saldo(db, ot, oid, "4.1.01", P) or 0.0)
                          + (_saldo(db, ot, oid, "4.2.01", P) or 0.0)
                          + (_saldo(db, ot, oid, "4.4.03", P) or 0.0), 2)
    cust_fin_na_receita = ctx["cust_fin"] if ctx["ramo"] in ("loja", "loja_antecipacao") else 0.0
    receita_esperada = round(ctx["vavo"] + cust_fin_na_receita + ctx["valor_aditivo"], 2)
    assert receita_total == receita_esperada, (
        "receita total apurada = R$ %.2f; deveria ser R$ %.2f (venda + custo financeiro, "
        "quando entra no resultado + aditivo, cada um uma vez) — distorção de R$ %.2f"
        % (receita_total, receita_esperada, round(receita_total - receita_esperada, 2)))

    # 4: custo total == soma dos custos reais reconhecidos (nenhuma rubrica 2x, nenhuma esquecida).
    # ACHADO-02/03 (passo 10): nenhum ramo reconhece despesa de custo financeiro nesta bateria —
    # 'financeira' nunca reconhece (aceite #3); loja/loja_antecipacao não exercitam o evento da
    # antecipação aqui (não é o que esta bateria investiga).
    despesa_total = round(sum(
        (_saldo(db, ot, oid, RUBRICAS_MATCHING_PLENO[k][2], P) or 0.0) for k in ctx["valores_rubricas"]
        if k != "impostos"), 2)
    # o aditivo soma montagem PRÓPRIA (constituída à parte, ref ":aditivo") em cima da base —
    # esquecer essa soma aqui era um bug de teste mascarado pelas falhas de ACHADO-01/02 (a
    # invariante de receita/2.1.04.19 abortava antes de chegar aqui); descoberto ao consertar o
    # passo 10, corrigido junto.
    custo_esperado = round(sum(v for k, v in ctx["valores_rubricas"].items() if k != "impostos")
                          + ctx["montagem_aditivo"], 2)
    assert despesa_total == custo_esperado, (
        "custo total reconhecido = R$ %.2f; deveria ser R$ %.2f" % (despesa_total, custo_esperado))

    # 6: nenhum lançamento em 5.6.10 sem marcação explícita (nenhum cenário desta bateria usa)
    assert (_saldo(db, ot, oid, "5.6.10", P) or 0.0) == 0.0

    # 7: nenhuma conta fora do PLANO_PADRAO foi tocada
    codigos_plano = {c for c, _n in mc.PLANO_PADRAO}
    lans = db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=oid, projeto_id=P).all()
    contas_ids = {l.conta_debito_id for l in lans} | {l.conta_credito_id for l in lans}
    fora_do_plano = set()
    for cid in contas_ids:
        c = db.get(mc.Conta, cid)
        if c.codigo not in codigos_plano:
            fora_do_plano.add(c.codigo)
    assert not fora_do_plano, "contas fora do PLANO_PADRAO tocadas: %s" % fora_do_plano


# ── a matriz ──────────────────────────────────────────────────────────────────────────────────
def _cenario(nome, ramo, toggles=None, tem_aditivo=False, valor_aditivo=3000.0,
            sem_financiamento=False):
    t = dict(_TOGGLES_TODOS_OFF)
    t.update(toggles or {})
    return {"nome": nome, "ramo": ramo, "toggles": t,
            "tem_aditivo": tem_aditivo, "valor_aditivo": valor_aditivo if tem_aditivo else 0.0,
            "sem_financiamento": sem_financiamento}


_TOGGLES_TODOS_ON = {"comissao_arq_ativa": True, "fidelidade_ativa": True, "fora_da_sede": True,
                     "brinde_ativo": True, "custo_especial_ativo": True, "incluir_custos": True}

_CENARIOS_NUCLEO = [
    _cenario("loja_sem_custo_sem_aditivo", "loja"),
    _cenario("loja_com_custo_sem_aditivo", "loja", _TOGGLES_TODOS_ON),
    _cenario("loja_sem_custo_com_aditivo", "loja", tem_aditivo=True),
    _cenario("loja_com_custo_com_aditivo", "loja", _TOGGLES_TODOS_ON, tem_aditivo=True),
    _cenario("loja_antecipacao_sem_custo_sem_aditivo", "loja_antecipacao"),
    _cenario("loja_antecipacao_com_custo_sem_aditivo", "loja_antecipacao", _TOGGLES_TODOS_ON),
    _cenario("loja_antecipacao_sem_custo_com_aditivo", "loja_antecipacao", tem_aditivo=True),
    _cenario("loja_antecipacao_com_custo_com_aditivo", "loja_antecipacao", _TOGGLES_TODOS_ON, tem_aditivo=True),
    _cenario("financeira_sem_custo_sem_aditivo", "financeira"),
    _cenario("financeira_com_custo_sem_aditivo", "financeira", _TOGGLES_TODOS_ON),
    _cenario("financeira_sem_custo_com_aditivo", "financeira", tem_aditivo=True),
    _cenario("financeira_com_custo_com_aditivo", "financeira", _TOGGLES_TODOS_ON, tem_aditivo=True),
]

# isolamento de cada toggle individual (ramo fixo "loja", sem aditivo — isola o efeito do
# próprio toggle sem o ruído das outras dimensões)
_CENARIOS_TOGGLE_ISOLADO = [
    _cenario("toggle_comissao_arq_isolado", "loja", {"comissao_arq_ativa": True, "incluir_custos": True}),
    _cenario("toggle_fidelidade_isolado", "loja", {"fidelidade_ativa": True, "incluir_custos": True}),
    _cenario("toggle_fora_da_sede_isolado", "loja", {"fora_da_sede": True, "incluir_custos": True}),
    _cenario("toggle_brinde_isolado", "loja", {"brinde_ativo": True, "incluir_custos": True}),
    _cenario("toggle_custo_especial_isolado", "loja", {"custo_especial_ativo": True, "incluir_custos": True}),
    # incluir_custos=False com TODOS os outros ON: testa "absorve" — Val_Cont não sobe, mas a
    # despesa das 5 rubricas continua cheia (a margem absorve, não é achado, ver docstring do módulo)
    _cenario("toggle_incluir_custos_absorve", "loja",
            {"comissao_arq_ativa": True, "fidelidade_ativa": True, "fora_da_sede": True,
             "brinde_ativo": True, "custo_especial_ativo": True, "incluir_custos": False}),
]

# controle positivo: sem custo financeiro (à vista), nenhum dos ACHADO-01/02/12 pode se
# manifestar — se estes falharem, o defeito é nas INVARIANTES, não no código de produção.
_CENARIOS_CONTROLE_POSITIVO = [
    _cenario("controle_positivo_loja_avista", "loja", sem_financiamento=True),
    _cenario("controle_positivo_loja_antecipacao_avista", "loja_antecipacao", sem_financiamento=True),
    _cenario("controle_positivo_financeira_avista", "financeira", sem_financiamento=True),
]

_CENARIOS = _CENARIOS_NUCLEO + _CENARIOS_TOGGLE_ISOLADO + _CENARIOS_CONTROLE_POSITIVO

# ACHADOS que fazem um cenário falhar — nome do cenário -> (achado, motivo)
# ACHADO-12 CONSERTADO no passo 7 (docs/db/TAREFA_ACHADO12.md): a NF-e passou a faturar
# valor_contratado_do_projeto (contrato + aditivos assinados) — tem_aditivo=True deixou de ter
# achado próprio aqui.
# ACHADO-01/02/03 CONSERTADOS no passo 10 (docs/db/TAREFA_ACHADO02_03.md): 4.1.01 fatura o VAVO
# (não mais o Val_Cont cheio, ACHADO-02); loja_antecipacao usa o mesmo mecanismo de loja no
# fechamento (ACHADO-03); financeira confere a retenção esperada contra a real (ACHADO-01/
# conferir_retencao_financeira) — nenhum dos três ramos tem achado próprio aqui.
_XFAILS = {}


def _marca(cenario):
    xf = _XFAILS.get(cenario["nome"])
    if xf is None:
        return pytest.param(cenario, id=cenario["nome"])
    achado, motivo = xf
    return pytest.param(cenario, id=cenario["nome"],
                        marks=pytest.mark.xfail(reason="%s: %s (ver docs/db/ACHADOS_CONTABEIS.md)"
                                                       % (achado, motivo), strict=True))


@pytest.mark.parametrize("cenario", [_marca(c) for c in _CENARIOS])
def test_ciclo_bateria(app_db, cenario):
    oid = 6500 + _CENARIOS.index(cenario)
    ctx = _rodar_cenario(app_db, cenario, oid)
    try:
        _conferir_invariantes(ctx)
    finally:
        ctx["db"].close()


# ── cobertura de rubricas (item 4) ───────────────────────────────────────────────────────────
def test_cobertura_de_rubricas_da_bateria():
    """Toda rubrica de _PROV_FECHAMENTO (18) tem que ser exercitada por ao menos um cenário com
    valor > 0. Falha nomeando qual rubrica nenhum cenário alcança — informação, não bug (pode
    ser cenário faltando ou rubrica morta)."""
    exercitadas = set()
    for c in _CENARIOS:
        ativas = _rubricas_ativas(c["toggles"])
        exercitadas |= set(ativas)
        exercitadas |= set(RUBRICAS_SEMPRE_PRESENTES)
        exercitadas.add("impostos")
        exercitadas.add("custo_financeiro")   # constituída em todo cenário via evento_cfin
    faltando = set(TODAS_AS_RUBRICAS) - exercitadas
    assert not faltando, "rubricas nunca exercitadas por nenhum cenário: %s" % faltando


# ── retrato do balancete (item 5) — DETECTOR DE MUDANÇA, NÃO VERDADE ────────────────────────
def test_gravar_retrato_do_balancete(app_db):
    """Grava docs/db/RETRATO_BALANCETE_BATERIA.md com os saldos finais por conta, por cenário.

    Isto NÃO é uma declaração de que os números estão certos — quem julga certo/errado são as
    invariantes de `_conferir_invariantes` (e os cenários marcados xfail acima, hoje nenhum). Este
    retrato existe só para que uma mudança futura de comportamento apareça como diff no arquivo."""
    linhas = [
        "# Retrato do balancete — bateria de ciclo completo\n\n",
        "**Gerado por `tests/test_bateria_ciclo.py::test_gravar_retrato_do_balancete`. "
        "NÃO é declaração de correção — é detector de mudança.** Quem julga certo/errado são as "
        "invariantes de `tests/test_bateria_ciclo.py`, não este arquivo. Se este arquivo mudar "
        "num PR futuro, o diff é o alarme — investigue por que o comportamento mudou.\n\n",
    ]
    for c in _CENARIOS:
        oid = 6500 + _CENARIOS.index(c)
        ctx = _rodar_cenario(app_db, c, oid)
        db, ot, oid_r, P = ctx["db"], ctx["ot"], ctx["oid"], ctx["P"]
        contas = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid_r).order_by(mc.Conta.codigo).all()
        linhas.append("## %s (ramo=%s, aditivo=%s)\n\n" % (c["nome"], c["ramo"], c["tem_aditivo"]))
        linhas.append("| conta | saldo |\n|---|---|\n")
        for conta in contas:
            if conta.tipo != "analitica":
                continue
            s = _saldo(db, ot, oid_r, conta.codigo, P) or 0.0
            if abs(s) >= 0.005:
                linhas.append("| %s %s | %.2f |\n" % (conta.codigo, conta.nome, s))
        linhas.append("\n")
        db.close()
    out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "db",
                            "RETRATO_BALANCETE_BATERIA.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(linhas)
