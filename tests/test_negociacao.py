# tests/test_negociacao.py
import mod_negociacao as mn

# LELEU oç1 — params do projeto, todos os toggles ON (spec §9)
PARAMS = {"incluir_custos": True, "comissao_arq_pct": 10.0, "comissao_arq_ativa": True,
          "fidelidade_pct": 2.0, "fidelidade_ativa": True, "fora_da_sede": True,
          "custo_viagem": 2000.0, "brinde": 500.0, "brinde_ativo": True, "carga_trib": 8.0}
AMBS = [{"VBVA": 22830.99, "CFA": 22830.99, "desc_amb_pct": 0.0},
        {"VBVA": 2650.50,  "CFA": 953.40,   "desc_amb_pct": 0.0}]

def _ap(a, b, tol=0.02): assert abs(a - b) <= tol, f"{a} != {b}"

def test_leleu_ancora():
    # comissão em cadeia (arq não ganha sobre fid; ambos excluem viagem/brinde) — Com_Arq/Pro_Fid/
    # Cust_Ad NÃO mudam com o ACHADO-63 (06/09): a base de comissão (num_via+num_bri)*fator_desc
    # sempre rastreou exatamente o que fica embutido em VAVA/VAVO pra essas duas rubricas (antes
    # E depois da correção — a álgebra cancela: delta_vava do termo via/bri == delta_base_custos),
    # então Com_Arq/Pro_Fid ficam idênticos ao valor de ANTES da correção (2265.02/462.25).
    # O que muda: viagem+brinde não inflam mais o Bruto nem são blindados do desconto — a loja
    # recupera só (1-d_orc) do custo. total_via=2000,00 (custo_viagem cheio, rateado e somado de
    # volta) + total_bri=500,00 (brinde cheio) = 2500,00; perda = 2500,00 × 20% = 500,00:
    #   VBNO cai (2500 × (1-0,80)/0,80) = 625,00 → 32015,58 - 625,00 = 31390,58
    #   VAVO/Val_Liq caem 2500 × 0,20 = 500,00 → 25612,46-500=25112,46 / 20385,19-500=19885,19
    r = mn.calcular_orcamento(AMBS, PARAMS, 20.0, cust_fin=1413.44)
    _ap(r["VBVO"], 25481.49); _ap(r["CFO"], 23784.39)
    _ap(r["VBNO"], 31390.58); _ap(r["VAVO"], 25112.46)
    _ap(r["Com_Arq"], 2265.02); _ap(r["Pro_Fid"], 462.25)
    _ap(r["Cust_Ad"], 5227.27); _ap(r["Val_Liq"], 19885.19)
    # Desc_Tot = (VBVO-Val_Liq)/VBVO = (25481.49-19885.19)/25481.49 = 21.96% (não mais 20,00% —
    # a "proteção total" da viagem/brinde acabou de propósito, ACHADO-63)
    _ap(r["Desc_Tot"] * 100, 21.96, tol=0.02); _ap(r["Markup"], 0.836, tol=0.002)
    _ap(r["Val_Cont"], r["VAVO"] + 1413.44); _ap(r["Prov_Imp"], 0.08 * r["Val_Cont"], tol=0.05)
    ag = r["ambientes"][0]
    # amb1: num_via1 = 2000*(22830.99/25481.49) = 1791,96664; num_bri1 = 500/2 = 250,00
    # sum1 = 2041,96664; delta_VBNA1 = -sum1*(0,20/0,80) = -510,49166 → 28437,93-510,49=27927,44
    # delta_VAVA1 = -sum1*0,20 = -408,39333 → 22750,35-408,39=22341,96
    _ap(ag["VBNA"], 27927.44); _ap(ag["VAVA"], 22341.96)

def test_perda_de_viagem_bri_e_exatamente_d_orc_vezes_custo():
    # ACHADO-63 (06/09): a "proteção total" de viagem/brinde ACABOU de propósito — o preço de
    # tabela não pode variar com o desconto, e a contrapartida (a loja recupera só (1-d) do
    # custo) é aceita e previsível. A perda tem que ser EXATAMENTE d_orc × (custo_viagem+brinde):
    # 20% × (2000,00+500,00) = 500,00 — nem mais, nem menos (senão sobra/falta base de comissão).
    r = mn.calcular_orcamento(AMBS, PARAMS, 20.0)
    _ap(r["Val_Liq"], r["VBVO"] * 0.80 - 500.0)
    _ap(r["Desc_Tot"] * 100, 21.96, tol=0.02)      # não mais == Desc_Orc (era a "proteção total")

def test_comissao_exclui_custos_no_absorve():
    # absorve (Tog_Cadi false): a comissão NÃO incide sobre viagem/brinde — a base exclui esses
    # custos SEMPRE, mesmo absorvendo (`base_custos` roda incondicional, fora do if/else do
    # Tog_Cadi). ACHADO-63 (06/09): `base_custos` agora é (num_via+num_bri)*fator_desc, não mais
    # o valor cheio — em absorve, fator_desc=0,80 constante (d_amb=0 nos 2 ambientes), então
    # base_custos total = (2000+500)*0,80 = 2000,00 (não mais 2500,00).
    p = {"incluir_custos": False, "fidelidade_pct": 2.0, "fidelidade_ativa": True,
         "fora_da_sede": True, "custo_viagem": 2000.0, "brinde": 500.0, "brinde_ativo": True,
         "comissao_arq_ativa": False}
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    vavo = r["VBVO"] * 0.80                            # 20385.19 (absorve, só desconto — inalterado)
    pro_esperado = 0.02 * (vavo - (2000.0 + 500.0) * 0.80)   # 367.70384 — base agora é 2000,00 (era 2500,00)
    _ap(r["Pro_Fid"], pro_esperado)
    _ap(r["Val_Liq"], vavo - (pro_esperado + 2000 + 500))   # 17517.49 (cust_ad continua com o custo CHEIO)

def test_brinde_recupera_so_fator_desc_nao_mais_blindado():
    # ACHADO-63 (06/09): brinde repassado NÃO é mais blindado do desconto — a loja recupera só
    # (1-d_orc) do custo. vbna=vbva+brinde=1000+100=1100,00 (sem gross-up); vava=1100×0,80=880,00;
    # cust_ad=100,00 (custo cheio, sempre); Val_Liq=880,00-100,00=780,00 (perda de 20,00 = 100×20%).
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 0.0}]
    so_brinde = {"incluir_custos": True, "brinde": 100.0, "brinde_ativo": True}
    r = mn.calcular_orcamento(ambs, so_brinde, 20.0)
    _ap(r["Val_Liq"], 780.0)

def test_tog_cadi_off_absorve():
    # sem gross-up: VBNA = VBVA; custos ainda abatem o líquido
    p = {**PARAMS, "incluir_custos": False}
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    _ap(r["VBNO"], r["VBVO"])                      # VBNA = VBVA
    _ap(r["VAVO"], r["VBVO"] * 0.80)              # só o desconto
    assert r["Cust_Ad"] > 0                        # custos seguem abatendo

def test_toggle_individual_zera_componente():
    p = {**PARAMS, "brinde_ativo": False, "fora_da_sede": False}  # sem brinde nem viagem
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    # Cust_Ad = só Com_Arq + Pro_Fid, em cadeia: fid + arq·(1-fid) = 0.02 + 0.10·0.98 = 0.118
    _ap(r["Cust_Ad"], 0.118 * r["VAVO"], tol=0.05)

def test_desc_amb_por_ambiente():
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 50.0}]
    p = {"incluir_custos": False}
    r = mn.calcular_orcamento(ambs, p, 0.0)
    _ap(r["VAVO"], 500.0)                          # 1000 * (1-0.50)

def test_orcamento_vazio_nao_quebra():
    r = mn.calcular_orcamento([], {"incluir_custos": False}, 0.0)
    assert r["VBVO"] == 0 and r["Markup"] == 0 and r["Val_Liq"] == 0

def test_retorna_cust_via_e_bri():
    amb = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 300,
         "brinde_ativo": True, "brinde": 200}
    d = __import__("mod_negociacao").calcular_orcamento(amb, p, 0)
    assert d["Cust_Via"] == 300.0
    assert d["Bri"] == 200.0
    # cadeia fecha: VAVO − Com_Arq − Pro_Fid − Cust_Via − Bri == Val_Liq
    assert abs((d["VAVO"] - d["Com_Arq"] - d["Pro_Fid"] - d["Cust_Via"] - d["Bri"]) - d["Val_Liq"]) < 0.05

def test_cust_via_bri_zerados_quando_toggle_off():
    amb = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "fora_da_sede": False, "custo_viagem": 300,
         "brinde_ativo": False, "brinde": 200}
    d = __import__("mod_negociacao").calcular_orcamento(amb, p, 0)
    assert d["Cust_Via"] == 0.0 and d["Bri"] == 0.0


def test_distribuicao_3_de_7():
    """Projeto com 7 ambientes (pool), orçamento com 3 → brinde 3/7; viagem proporcional."""
    # orçamento = 3 ambientes (valores 10000, 10000, 10000); projeto = 7 ambientes
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0} for _ in range(3)]
    n_total_proj = 7
    vbvo_proj = 70000.0                      # 7 × 10000 (todos iguais p/ simplificar)
    p = {"incluir_custos": False, "fora_da_sede": True, "custo_viagem": 700,
         "brinde_ativo": True, "brinde": 700}
    d = mn.calcular_orcamento(ambs, p, 0, n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    # brinde recuperado = 3 × (700/7) = 300
    assert abs(d["Bri"] - 300.0) < 0.01
    # viagem recuperada = 700 × (30000/70000) = 300
    assert abs(d["Cust_Via"] - 300.0) < 0.01


def test_ambiente_expoe_waterfall_e_soma_bate():
    """Cada ambiente expõe Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq; a soma bate com os agregados."""
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0},
            {"VBVA": 20000, "CFA": 8000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10,
         "fidelidade_ativa": True, "fidelidade_pct": 5, "fora_da_sede": True,
         "custo_viagem": 600, "brinde_ativo": True, "brinde": 400}
    d = mn.calcular_orcamento(ambs, p, 5)
    aa = d["ambientes"]
    for a in aa:
        for k in ("Com_Arq", "Pro_Fid", "Cust_Via", "Bri", "Val_Liq"):
            assert k in a
        assert abs(a["Val_Liq"] - (a["VAVA"] - a["Com_Arq"] - a["Pro_Fid"]
                                   - a["Cust_Via"] - a["Bri"])) < 0.01
    assert abs(sum(a["Com_Arq"]  for a in aa) - d["Com_Arq"])  < 0.02
    assert abs(sum(a["Pro_Fid"]  for a in aa) - d["Pro_Fid"])  < 0.02
    assert abs(sum(a["Cust_Via"] for a in aa) - d["Cust_Via"]) < 0.02
    assert abs(sum(a["Bri"]      for a in aa) - d["Bri"])      < 0.02
    assert abs(sum(a["Val_Liq"]  for a in aa) - d["Val_Liq"])  < 0.02


def test_fallback_sem_contexto_inalterado():
    """Sem n_total_proj/vbvo_proj → comportamento atual (orçamento recebe o valor cheio)."""
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0} for _ in range(3)]
    p = {"incluir_custos": False, "fora_da_sede": True, "custo_viagem": 700,
         "brinde_ativo": True, "brinde": 700}
    d = mn.calcular_orcamento(ambs, p, 0)    # sem contexto
    assert abs(d["Bri"] - 700.0) < 0.01      # cheio
    assert abs(d["Cust_Via"] - 700.0) < 0.01 # cheio


# ── Custo Especial (linha do ORÇAMENTO, não rateada nos ambientes) ─────────────────────────────────
# Diferente de viagem (proporcional) e brinde (igual/amb), o Custo Especial NÃO se distribui:
# sai ambiente, ele fica integral. Por isso Σ Val_Liq dos ambientes ≠ Val_Liq do orçamento
# quando ativo — a diferença é exatamente a linha Cust_Esp.

def test_custo_especial_repassado_soma_no_total_sem_ratear():
    # exemplo da demanda: cozinha 80k + sala 50k + banheiro 20k + custo especial 1.000 → 151.000
    ambs = [{"VBVA": 80000, "CFA": 30000, "desc_amb_pct": 0},
            {"VBVA": 50000, "CFA": 20000, "desc_amb_pct": 0},
            {"VBVA": 20000, "CFA": 8000,  "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "custo_especial": 1000.0, "custo_especial_ativo": True}
    d = mn.calcular_orcamento(ambs, p, 0)
    _ap(d["Cust_Esp"], 1000.0)
    _ap(d["VAVO"], 151000.0); _ap(d["Val_Cont"], 151000.0)
    # ambientes intocados (não rateia): preços por ambiente não mudam
    assert [a["VAVA"] for a in d["ambientes"]] == [80000.0, 50000.0, 20000.0]

def test_custo_especial_sobrevive_remocao_de_ambientes():
    # retirada da cozinha e do banheiro → total 51.000 (o custo especial fica INTEGRAL, mesmo com
    # contexto de projeto que ratearia viagem/brinde)
    ambs = [{"VBVA": 50000, "CFA": 20000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "custo_especial": 1000.0, "custo_especial_ativo": True}
    d = mn.calcular_orcamento(ambs, p, 0, n_total_proj=3, vbvo_proj=150000.0)
    _ap(d["Cust_Esp"], 1000.0)      # NÃO proporcional (≠ viagem/brinde)
    _ap(d["Val_Cont"], 51000.0)

def test_custo_especial_sofre_desconto_do_orcamento():
    # ACHADO-63 (06/09): custo especial sofre o desconto DO ORÇAMENTO em VAVO (não sofre
    # desconto de ambiente — não é rateado). VBNO continua com o valor CHEIO (preço de tabela
    # não varia); antes VAVO também recebia o valor cheio, quebrando a identidade VAVO==VBNO×(1-d)
    # em exatamente cust_esp×d_orc = 100×20% = 20,00 — corrigido.
    # VAVO = 1000×0,80 + 100×0,80 = 800+80 = 880,00; Val_Liq = 880,00-100,00(cust_ad cheio) = 780,00
    # Desc_Tot deixa de ser 20,00% "puro": (1000-780)/1000 = 22,00%
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "custo_especial": 100.0, "custo_especial_ativo": True}
    d = mn.calcular_orcamento(ambs, p, 20.0)
    _ap(d["VAVO"], 880.0)
    _ap(d["Val_Liq"], 780.0)
    _ap(d["Desc_Tot"] * 100, 22.00)

def test_custo_especial_absorvido():
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 0}]
    p = {"incluir_custos": False, "custo_especial": 100.0, "custo_especial_ativo": True}
    d = mn.calcular_orcamento(ambs, p, 0)
    _ap(d["VAVO"], 1000.0)           # preço ao cliente inalterado
    _ap(d["Cust_Esp"], 100.0)
    _ap(d["Val_Liq"], 900.0)         # loja absorve

def test_custo_especial_toggle_off_zera():
    p = {"incluir_custos": True, "custo_especial": 100.0, "custo_especial_ativo": False}
    d = mn.calcular_orcamento([{"VBVA": 1000, "CFA": 400, "desc_amb_pct": 0}], p, 0)
    assert d["Cust_Esp"] == 0.0
    _ap(d["VAVO"], 1000.0)

def test_comissoes_nao_incidem_sobre_custo_especial():
    # arq/fid não ganham sobre o custo especial (fica fora do waterfall dos ambientes)
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10.0,
         "fidelidade_ativa": True, "fidelidade_pct": 5.0,
         "custo_especial": 1000.0, "custo_especial_ativo": True}
    d  = mn.calcular_orcamento(ambs, p, 0)
    d0 = mn.calcular_orcamento(ambs, {**p, "custo_especial_ativo": False}, 0)
    _ap(d["Com_Arq"], d0["Com_Arq"]); _ap(d["Pro_Fid"], d0["Pro_Fid"])
    # cadeia fecha no nível do orçamento: VAVO − Com_Arq − Pro_Fid − Cust_Esp == Val_Liq
    _ap(d["VAVO"] - d["Com_Arq"] - d["Pro_Fid"] - d["Cust_Esp"], d["Val_Liq"], tol=0.05)

def test_custo_especial_orcamento_vazio_zera():
    # achado da Vera: sem ambientes não há venda — o custo especial não pode gerar Val_Cont>0
    # (repassado) nem líquido negativo (absorvido), como viagem/brinde já zeram.
    for inc in (True, False):
        d = mn.calcular_orcamento([], {"incluir_custos": inc,
                                       "custo_especial": 1000.0, "custo_especial_ativo": True}, 0)
        assert d["Cust_Esp"] == 0.0 and d["Val_Cont"] == 0.0 and d["Val_Liq"] == 0.0
