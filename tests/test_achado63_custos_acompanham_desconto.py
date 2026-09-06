# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-63 — motor da negociação (irmão do ACHADO-59, outra porta).

DECIDIDO (Marcelo, 06/09): o desconto anunciado ao cliente TEM que levar o Bruto ao Valor à
Vista — `Bruto × (1 − desconto) = à vista`, sempre, pra toda rubrica repassada. O preço de
tabela (Bruto) não pode variar conforme o desconto concedido. A contrapartida — a loja recupera
só (1−d) dos custos fixos — é aceita e previsível.

Todos os números abaixo são DERIVADOS À MÃO da fórmula (ver comentário de cada bloco), não
copiados de uma execução do motor — a aritmética está no comentário, verificável sem rodar nada."""
import mod_negociacao as mn


def _ap(a, b, tol=0.02):
    assert abs(a - b) <= tol, f"{a} != {b}"


# ── Rubrica isolada: viagem, brinde, custo especial — cada uma em 0% e 30% de desconto ──────────
# Cenário simétrico pras três: 1 ambiente, mercadoria (VBVA) = 10.000,00, custo = 1.000,00,
# sem arq/fid (fator_com=1, termo_arqfid=vbva). Com 1 ambiente só, a rubrica entra pelo valor
# CHEIO (viagem: den_via=VBVO=vbva, rateio vira 1:1; brinde: den_bri=num_amb=1; cust_esp: não
# rateia nunca).
#
# Fórmula (idêntica pras três, ACHADO-63):
#   Bruto = mercadoria + custo                              (NUNCA multiplicado por fator_desc)
#   à vista = Bruto × (1−d)                                 (identidade do cliente, sempre exata)
#   Val_Liq = à vista − custo (cust_ad é sempre o valor CHEIO, nunca descontado)
#           = Bruto×(1−d) − custo = (mercadoria+custo)×(1−d) − custo
#           = mercadoria×(1−d) + custo×(1−d) − custo = mercadoria×(1−d) − custo×d
# Em números (mercadoria=10.000, custo=1.000):
#   d=0%:  Bruto=11.000,00; à vista=11.000,00; Val_Liq=10.000,00 (= 10000×1 − 1000×0)
#   d=30%: Bruto=11.000,00 (IDÊNTICO — preço de tabela não varia); à vista=11.000×0,70=7.700,00;
#          Val_Liq=10.000×0,70 − 1.000×0,30 = 7.000,00 − 300,00 = 6.700,00

def test_viagem_isolada_bruto_fixo_e_identidade():
    amb = [{"VBVA": 10000.0, "CFA": 4000.0, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 1000.0}
    d0 = mn.calcular_orcamento(amb, p, 0.0)
    d30 = mn.calcular_orcamento(amb, p, 30.0)
    _ap(d0["VBNO"], 11000.0); _ap(d30["VBNO"], 11000.0)          # Bruto(30%) == Bruto(0%)
    _ap(d30["VAVO"], round(d30["VBNO"] * 0.70, 2))               # à vista == Bruto×(1−d), exato
    _ap(d0["Val_Liq"], 10000.0 * 1.0 - 1000.0 * 0.0)             # 10000.00
    _ap(d30["Val_Liq"], 10000.0 * 0.70 - 1000.0 * 0.30)          # 6700.00


def test_brinde_isolado_bruto_fixo_e_identidade():
    amb = [{"VBVA": 10000.0, "CFA": 4000.0, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "brinde_ativo": True, "brinde": 1000.0}
    d0 = mn.calcular_orcamento(amb, p, 0.0)
    d30 = mn.calcular_orcamento(amb, p, 30.0)
    _ap(d0["VBNO"], 11000.0); _ap(d30["VBNO"], 11000.0)
    _ap(d30["VAVO"], round(d30["VBNO"] * 0.70, 2))
    _ap(d0["Val_Liq"], 10000.0 * 1.0 - 1000.0 * 0.0)
    _ap(d30["Val_Liq"], 10000.0 * 0.70 - 1000.0 * 0.30)


def test_custo_especial_isolado_bruto_fixo_e_identidade():
    amb = [{"VBVA": 10000.0, "CFA": 4000.0, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "custo_especial_ativo": True, "custo_especial": 1000.0}
    d0 = mn.calcular_orcamento(amb, p, 0.0)
    d30 = mn.calcular_orcamento(amb, p, 30.0)
    _ap(d0["VBNO"], 11000.0); _ap(d30["VBNO"], 11000.0)
    _ap(d30["VAVO"], round(d30["VBNO"] * 0.70, 2))
    _ap(d0["Val_Liq"], 10000.0 * 1.0 - 1000.0 * 0.0)
    _ap(d30["Val_Liq"], 10000.0 * 0.70 - 1000.0 * 0.30)


# ── Combinado: viagem 1.500 + brinde 1.000 + cust_esp 800 + arq 5% + fid 2%, d=25%, 1 ambiente ──
# mercadoria (VBVA) = 20.000,00 (1 ambiente, sem rateio nenhum: viagem/brinde entram pelo valor
# cheio). fator_com = (1−0,05)×(1−0,02) = 0,931. fator_desc = 0,75.
#   termo_arqfid = 20000/0,931 = 21.482,277121... (gross-up do arq/fid, INTOCADO pela fatia)
#   termo_via_bri = 1500+1000 = 2.500,00 (ACHADO-63: sem gross-up, valor de face)
#   Bruto = 21.482,277121 + 2.500 + 800(cust_esp, cheio) = 24.782,277121
#   à vista = (21.482,277121+2.500)×0,75 + 800×0,75 = 24.782,277121×0,75 = 18.586,707841
#   → à vista − Bruto×0,75 == 0,00 (identidade — VBNO e VAVO carregam exatamente o mesmo cust_esp
#     escalado pelo mesmo fator_desc, por construção)
# Cenário B (SEM os 3 custos, MESMOS mercadoria/arq/fid): base de comissão (vava−base_custos) é
# IDÊNTICA à do cenário A — a subtração de `base_custos` sempre rastreia exatamente o que entrou
# em vava por viagem/brinde, então a comissão (arq+fid) não muda entre A e B. A única diferença
# em Val_Liq é exatamente −(via+bri+cust_esp)×d_orc = −(1500+1000+800)×0,25 = −825,00.
#   Val_Liq_B = 15.000,00 (mercadoria×0,75 líquido de arq/fid, redondo por construção da fração)
#   Val_Liq_A = 15.000,00 − 825,00 = 14.175,00

def test_combinado_identidade_e_perda_825():
    amb = [{"VBVA": 20000.0, "CFA": 8000.0, "desc_amb_pct": 0}]
    p_com = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 1500.0,
             "brinde_ativo": True, "brinde": 1000.0,
             "custo_especial_ativo": True, "custo_especial": 800.0,
             "comissao_arq_ativa": True, "comissao_arq_pct": 5.0,
             "fidelidade_ativa": True, "fidelidade_pct": 2.0}
    p_sem = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 5.0,
             "fidelidade_ativa": True, "fidelidade_pct": 2.0}
    d_com = mn.calcular_orcamento(amb, p_com, 25.0)
    d_sem = mn.calcular_orcamento(amb, p_sem, 25.0)
    _ap(d_com["VAVO"] - d_com["VBNO"] * 0.75, 0.0)     # à vista − Bruto×0,75 == 0,00
    _ap(d_com["VBNO"], 24782.28); _ap(d_com["VAVO"], 18586.71)
    _ap(d_sem["Val_Liq"], 15000.0)
    _ap(d_com["Val_Liq"], 14175.0)
    _ap(d_sem["Val_Liq"] - d_com["Val_Liq"], 825.0)    # = 3300 × 25%, exato


# ── Desconto individual por ambiente (25% global + 10% no amb2) ────────────────────────────────
# amb1 VBVA=12.000, d_amb=0%; amb2 VBVA=8.000, d_amb=10%; mesmas rubricas do combinado.
# fator_desc1=(1−0,25)=0,75; fator_desc2=(1−0,25)×(1−0,10)=0,675.
# Por ambiente a identidade é a mesma de sempre: VAVA == VBNA×(1−d_orc)×(1−d_amb), SEM depender
# de nenhuma rubrica repassada (elas entram em VBNA/VAVA já na proporção certa, por construção
# do laço). O agregado usa o Desc_Efetivo (novo — ACHADO-63): por definição,
# Desc_Efetivo = 1 − VAVO/VBNO, então VBNO×(1−Desc_Efetivo) == VAVO é tautológico — o que prova
# de verdade é que Desc_Efetivo (que pesa o desconto de CADA ambiente pelo seu próprio VBNA) É
# DIFERENTE de d_orc (25%) quando há desconto por ambiente — são dois números com propósitos
# diferentes por construção, não o mesmo número disfarçado.

def test_desconto_por_ambiente_identidade_e_desc_efetivo_diferente_de_d_orc():
    ambs = [{"VBVA": 12000.0, "CFA": 5000.0, "desc_amb_pct": 0.0},
            {"VBVA": 8000.0, "CFA": 3000.0, "desc_amb_pct": 10.0}]
    p = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 1500.0,
         "brinde_ativo": True, "brinde": 1000.0,
         "custo_especial_ativo": True, "custo_especial": 800.0,
         "comissao_arq_ativa": True, "comissao_arq_pct": 5.0,
         "fidelidade_ativa": True, "fidelidade_pct": 2.0}
    d = mn.calcular_orcamento(ambs, p, 25.0)
    a1, a2 = d["ambientes"]
    _ap(a1["VAVA"], round(a1["VBNA"] * 0.75, 2))          # amb1: d_amb=0% → fator 0,75
    _ap(a2["VAVA"], round(a2["VBNA"] * 0.675, 2))         # amb2: fator (0,75)×(0,90)=0,675
    _ap(d["VAVO"], round(d["VBNO"] * (1 - d["Desc_Efetivo"]), 2))   # tautológico, guarda coerência
    assert abs(d["Desc_Efetivo"] - 0.25) > 0.01, (
        "Desc_Efetivo tem que DIVERGIR de d_orc quando há desconto por ambiente — "
        "são números diferentes por construção, não o mesmo disfarçado")


# ── Controle: comissão de arquiteto sozinha, a 0% e 30% — prova que a fatia NÃO tocou as ─────────
# rubricas percentuais (gross-up divisivo `vbva/fator_com`, independente de `d_orc`).
# mercadoria=10.000, pct_arq=10%, sem fid/via/bri/cesp: fator_com=0,90.
#   Bruto = 10000/0,90 = 11.111,111... — IGUAL em 0% e 30% (nunca dependeu de d_orc)
#   d=0%:  Val_Liq = 11.111,111×1,00 − 0,10×11.111,111 = 10.000,00
#   d=30%: Val_Liq = 11.111,111×0,70 − 0,10×(11.111,111×0,70) = 7.777,777×0,90 = 7.000,00

def test_controle_comissao_arquiteto_sozinha_bruto_invariante():
    amb = [{"VBVA": 10000.0, "CFA": 4000.0, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0}
    d0 = mn.calcular_orcamento(amb, p, 0.0)
    d30 = mn.calcular_orcamento(amb, p, 30.0)
    _ap(d0["VBNO"], 11111.11); _ap(d30["VBNO"], 11111.11)   # Bruto nunca dependeu de d_orc
    _ap(d0["Val_Liq"], 10000.0)
    _ap(d30["Val_Liq"], 7000.0)
