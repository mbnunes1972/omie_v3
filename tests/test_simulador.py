"""mod_simulador — motor PURO do Simulador de Modelo de Negócios (Sessão 185). RN-01: faturamento
= Val_Liq. RN-02: markup exibido em % adicional (2,18× = 118%), imutável por efeito de outras
variáveis. Convenção de percentual: número-percent (2.5 = 2,5%), como mod_provisoes."""
import mod_simulador as sim


def _modelo_base():
    return {
        "vendedores": [
            {"nome": "Amanda", "atual": 118000.0, "meta": 110000.0, "ativo": True},
            {"nome": "Bruno", "atual": 96500.0, "meta": 110000.0, "ativo": True},
            {"nome": "Carla", "atual": 132400.0, "meta": 120000.0, "ativo": True},
        ],
        "medias_janela": {"mes": 112500.0, "d30": 109300.0, "tri": 108000.0, "sem": 104500.0, "ano": 101200.0},
        "variaveis": [
            {"chave": "fabrica", "nome": "Custo de Fábrica", "pct": 32.0},
            {"chave": "montagem", "nome": "Montagem", "pct": 4.0},
            {"chave": "brinde", "nome": "Brinde / Viagem", "pct": 0.0},
        ],
        "markups_medios": {
            "seco": {"mes": 2.18, "d30": 2.16, "tri": 2.12, "sem": 2.08, "ano": 2.05},
            "com_frete": {"mes": 2.02, "d30": 2.00, "tri": 1.97, "sem": 1.94, "ano": 1.91},
        },
        "folha": [
            {"nome": "Rogério", "cargo": "Diretor", "salario_fixo": 15000.0, "comissao_fixa": 0.0,
             "pro_labore": True, "comissionamento": "none", "ativo": True},
            {"nome": "Marina", "cargo": "Gerente", "salario_fixo": 9500.0, "comissao_fixa": 0.0,
             "pro_labore": False, "comissionamento": "faixa_loja", "ativo": True},
            {"nome": "Amanda", "cargo": "Consultora", "salario_fixo": 2200.0, "comissao_fixa": 0.0,
             "pro_labore": False, "comissionamento": "faixa_vendedor", "vendedor_idx": 0, "ativo": True},
            {"nome": "Bruno", "cargo": "Consultor", "salario_fixo": 2200.0, "comissao_fixa": 800.0,
             "pro_labore": False, "comissionamento": "faixa_vendedor", "vendedor_idx": 1, "ativo": True},
            {"nome": "Carla", "cargo": "Consultora", "salario_fixo": 2200.0, "comissao_fixa": 0.0,
             "pro_labore": False, "comissionamento": "faixa_vendedor", "vendedor_idx": 2, "ativo": True},
            {"nome": "Felipe", "cargo": "Projetista", "salario_fixo": 4800.0, "comissao_fixa": 0.0,
             "pro_labore": False, "comissionamento": "pct_fat", "pct_fixo": 1.0, "ativo": True},
            {"nome": "Sandra", "cargo": "Administrativo", "salario_fixo": 3600.0, "comissao_fixa": 0.0,
             "pro_labore": False, "comissionamento": "none", "ativo": True},
        ],
        "encargos_pct": 35.0,
        "faixas_consultor": [[0.8, 2.5, "até 80% da meta"], [1.0, 3.0, "80-100% da meta"],
                             [1.2, 3.5, "100-120% da meta"], [None, 4.0, "acima de 120%"]],
        "faixas_gerente": [[0.8, 0.5, "até 80% da meta da loja"], [1.0, 0.8, "80-100% da meta da loja"],
                           [None, 1.0, "acima de 100%"]],
        "custos_fixos": [{"nome": "Aluguel", "valor": 18500.0}, {"nome": "Água e esgoto", "valor": 0.0}],
        "amortizacoes": [{"nome": "Reforma do showroom", "valor": 120000.0, "prazo_meses": 24},
                         {"nome": "Mostruário novo", "valor": 84000.0, "prazo_meses": 12}],
        "juros": 3850.0, "impostos_pct": 8.5, "divida": 240000.0,
    }


# ── A. Vendas / faturamento (RN-01, RF-15, RF-16) ──────────────────────────────────────────
def test_atual_soma_valor_real_de_cada_vendedor():
    r = sim.simular(_modelo_base(), {"cenario": "atual", "janela": "mes"})
    assert r["vendas"]["faturamento"] == 118000.0 + 96500.0 + 132400.0
    nomes = {l["nome"]: l["valor"] for l in r["vendas"]["linhas"]}
    assert nomes["Amanda"] == 118000.0


def test_historico_cada_posto_inicia_igual_pela_media_da_janela():
    r = sim.simular(_modelo_base(), {"cenario": "historico", "janela": "tri"})
    for linha in r["vendas"]["linhas"]:
        assert linha["valor"] == 108000.0
    assert r["vendas"]["faturamento"] == 108000.0 * 3


def test_trava_redistribui_proporcionalmente_ao_desligar_vendedor():
    modelo = _modelo_base()
    ajustes = {"cenario": "atual", "janela": "mes", "trava": True,
              "vendedores_ativos": {"1": False}}   # desliga Bruno
    r = sim.simular(modelo, ajustes)
    total_pleno = 118000.0 + 96500.0 + 132400.0
    assert round(r["vendas"]["faturamento"], 2) == round(total_pleno, 2)   # travado: fat não muda
    linhas = {l["nome"]: l for l in r["vendas"]["linhas"]}
    assert linhas["Bruno"]["valor"] == 0.0 and linhas["Bruno"]["ativo"] is False
    assert linhas["Amanda"]["redistribuido"] is True
    assert linhas["Amanda"]["valor"] > 118000.0   # absorveu parte do volume do Bruno


def test_livre_faturamento_cai_ao_desligar_vendedor():
    modelo = _modelo_base()
    ajustes = {"cenario": "atual", "janela": "mes", "trava": False,
              "vendedores_ativos": {"1": False}}
    r = sim.simular(modelo, ajustes)
    assert r["vendas"]["faturamento"] == 118000.0 + 132400.0   # sem o Bruno, sem redistribuir
    linhas = {l["nome"]: l for l in r["vendas"]["linhas"]}
    assert linhas["Amanda"]["valor"] == 118000.0   # não absorveu nada


def test_trava_com_ativos_zerados_nao_estoura_divisao_por_zero():
    """Achado da Vera (auditoria e2e): se os vendedores que sobram ativos têm venda-base ZERO
    (ex.: consultor novo sem fechamento ainda) e o desligado carregava toda a venda, a
    redistribuição proporcional é 0/0 — não pode explodir; cai para divisão igual entre ativos."""
    modelo = _modelo_base()
    modelo["vendedores"].append({"nome": "Novo Consultor", "atual": 0.0, "meta": 100000.0, "ativo": True})
    ajustes = {"cenario": "atual", "janela": "mes", "trava": True,
              "vendedores_ativos": {"0": False, "1": False, "2": False}}   # só o "Novo Consultor" (idx 3) fica ativo
    r = sim.simular(modelo, ajustes)   # não pode levantar ZeroDivisionError
    total_pleno = 118000.0 + 96500.0 + 132400.0 + 0.0
    assert round(r["vendas"]["faturamento"], 2) == round(total_pleno, 2)
    novo = next(l for l in r["vendas"]["linhas"] if l["nome"] == "Novo Consultor")
    assert novo["valor"] == round(total_pleno, 2)   # único ativo → absorve tudo (divisão igual entre 1)
    assert novo["redistribuido"] is True


def test_loja_sem_vendedor_ativo_faturamento_zero_sem_erro():
    modelo = _modelo_base()
    ajustes = {"cenario": "atual", "vendedores_ativos": {"0": False, "1": False, "2": False}}
    r = sim.simular(modelo, ajustes)
    assert r["vendas"]["faturamento"] == 0.0
    assert r["snapshot"]["margem_contribuicao"]["pct"] is None   # denominador 0 → None, não erro


# ── B. Variáveis / markups (RF-17, RF-18, RN-02) ────────────────────────────────────────────
def test_variaveis_percentual_editado_recalcula_valor():
    modelo = _modelo_base()
    r = sim.simular(modelo, {"cenario": "atual", "variaveis_pct": {"fabrica": 30.0}})
    fat = r["vendas"]["faturamento"]
    fabrica = next(l for l in r["variaveis"]["linhas"] if l["chave"] == "fabrica")
    assert fabrica["pct"] == 30.0
    assert fabrica["valor"] == round(fat * 0.30, 2)


def test_markup_pct_adicional_2_18_e_118_por_cento():
    assert sim._markup_pct_adicional(2.18) == 118
    assert sim._markup_pct_adicional(1.8) == 80


def test_markup_inicia_pela_media_do_periodo():
    r = sim.simular(_modelo_base(), {"cenario": "historico", "janela": "tri"})
    assert r["variaveis"]["markup_seco"]["multiplicador"] == 2.12
    assert r["variaveis"]["markup_seco"]["pct_adicional"] == 112


def test_markup_nao_muda_por_efeito_de_outra_variavel():
    """RF-18: editar uma provisão (variável) NÃO pode alterar o markup — só edição direta."""
    modelo = _modelo_base()
    r_base = sim.simular(modelo, {"cenario": "atual", "janela": "mes"})
    r_editado = sim.simular(modelo, {"cenario": "atual", "janela": "mes",
                                     "variaveis_pct": {"fabrica": 50.0}})
    assert r_base["variaveis"]["markup_seco"] == r_editado["variaveis"]["markup_seco"]


def test_markup_so_muda_por_edicao_direta():
    r = sim.simular(_modelo_base(), {"cenario": "atual", "janela": "mes", "markup_seco": 2.30})
    assert r["variaveis"]["markup_seco"]["multiplicador"] == 2.30
    assert r["variaveis"]["markup_seco"]["pct_adicional"] == 130
    # o outro markup, não editado, segue a média
    assert r["variaveis"]["markup_com_frete"]["multiplicador"] == 2.02


# ── C. Folha (RF-19, RF-19b, RF-20) ─────────────────────────────────────────────────────────
def test_encargos_35pct_sobre_salario_clt():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    sandra = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Sandra")
    assert sandra["encargos"] == round(3600.0 * 0.35, 2)


def test_pro_labore_nao_tem_encargos():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    rogerio = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Rogério")
    assert rogerio["pro_labore"] is True
    assert rogerio["encargos"] == 0.0


def test_comissao_fixa_nao_tem_encargos_e_soma_no_fixo():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    bruno = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Bruno")
    assert bruno["comissao_fixa"] == 800.0
    # encargos calculados só sobre o salário (2200), não sobre a comissão fixa
    assert bruno["encargos"] == round(2200.0 * 0.35, 2)


def test_sem_comissionamento_mostra_zero_e_flag():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    sandra = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Sandra")
    assert sandra["comissao"]["valor"] == 0.0
    assert sandra["comissao"]["sem_comissionamento"] is True


def test_comissao_faixa_vendedor_usa_atingimento_da_meta_do_proprio_vendedor():
    # Amanda: valor real 118000 / meta 110000 = 107,3% → faixa 100-120% (3.5%)
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    amanda = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Amanda")
    assert amanda["comissao"]["valor"] == round(118000.0 * 3.5 / 100.0, 2)


def test_comissao_pct_fat_e_percentual_fixo_do_faturamento_total():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    fat = r["vendas"]["faturamento"]
    felipe = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Felipe")
    assert felipe["comissao"]["valor"] == round(fat * 0.01, 2)


def test_comissao_faixa_loja_usa_atingimento_da_meta_da_loja():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    fat = r["vendas"]["faturamento"]
    meta_loja = 110000.0 + 110000.0 + 120000.0
    at = fat / meta_loja
    # at ~ 0.96 → faixa "até 80%"? checa qual faixa realmente bate (80-100%: 0.8%)
    marina = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Marina")
    esperado_pct = 0.5 if at < 0.8 else (0.8 if at < 1.0 else 1.0)
    assert marina["comissao"]["valor"] == round(fat * esperado_pct / 100.0, 2)


def test_desligar_vendedor_desliga_o_consultor_correspondente_na_folha():
    modelo = _modelo_base()
    r = sim.simular(modelo, {"cenario": "atual", "vendedores_ativos": {"1": False}})
    bruno = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Bruno")
    assert bruno["ativo"] is False
    assert bruno["comissao"]["valor"] == 0.0


def test_folha_pct_fixo_e_variavel_sao_fracao_do_faturamento():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    fat = r["vendas"]["faturamento"]
    assert r["folha"]["pct_fixo"] == sim._div(r["folha"]["fixo"], fat, nd=4)
    assert r["folha"]["pct_variavel"] == sim._div(r["folha"]["variavel"], fat, nd=4)


def test_salario_editavel_por_indice():
    modelo = _modelo_base()
    r = sim.simular(modelo, {"cenario": "atual", "folha_salarios": {"3": 3000.0}})   # índice 3 = Bruno
    bruno = next(c for c in r["folha"]["colaboradores"] if c["nome"] == "Bruno")
    assert bruno["salario_fixo"] == 3000.0


# ── D. Custos fixos + amortizações (RF-21, RF-23) ───────────────────────────────────────────
def test_custos_fixos_subtotal_pct_e_fracao_do_faturamento():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    fat = r["vendas"]["faturamento"]
    assert r["custos_fixos"]["subtotal_pct"] == sim._div(r["custos_fixos"]["subtotal"], fat, nd=4)


def test_todas_as_contas_aparecem_mesmo_zeradas():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    nomes = {c["nome"] for c in r["custos_fixos"]["contas"]}
    assert "Água e esgoto" in nomes
    zero = next(c for c in r["custos_fixos"]["contas"] if c["nome"] == "Água e esgoto")
    assert zero["valor"] == 0.0


def test_amortizacao_impacto_mensal_ponderado_pelo_prazo():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    itens = {a["nome"]: a for a in r["custos_fixos"]["amortizacoes"]}
    assert itens["Reforma do showroom"]["impacto_mensal"] == round(120000.0 / 24, 2)
    assert itens["Mostruário novo"]["impacto_mensal"] == round(84000.0 / 12, 2)
    esperado_total = round(120000.0 / 24 + 84000.0 / 12, 2)
    assert r["custos_fixos"]["impacto_mensal_total"] == esperado_total
    assert r["custos_fixos"]["total"] == round(18500.0 + 0.0 + esperado_total, 2)


# ── E. Juros / Impostos / Dívida (RF-24) ────────────────────────────────────────────────────
def test_impostos_aplicam_a_carga_fiscal_sobre_o_faturamento_simulado():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    fat = r["vendas"]["faturamento"]
    jid = r["juros_impostos_divida"]
    assert jid["impostos"] == round(fat * 0.085, 2)
    assert jid["impostos_pct_fat"] == sim._div(jid["impostos"], fat, nd=4)
    assert jid["juros_pct"] == sim._div(jid["juros"], fat, nd=4)


def test_divida_nao_entra_no_total_mensal():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    jid = r["juros_impostos_divida"]
    assert jid["divida"] == 240000.0
    assert jid["total_mensal"] == round(jid["juros"] + jid["impostos"], 2)


# ── F. Snapshot (RF-25) ──────────────────────────────────────────────────────────────────────
def test_snapshot_margem_contribuicao_e_lucro():
    r = sim.simular(_modelo_base(), {"cenario": "atual"})
    fat = r["vendas"]["faturamento"]
    mc_esperado = round(fat - r["variaveis"]["total_valor"] - r["folha"]["variavel"], 2)
    lucro_esperado = round(mc_esperado - r["folha"]["fixo"] - r["custos_fixos"]["total"]
                           - r["juros_impostos_divida"]["juros"] - r["juros_impostos_divida"]["impostos"], 2)
    assert r["snapshot"]["margem_contribuicao"]["valor"] == mc_esperado
    assert r["snapshot"]["margem_lucro_liquido"]["valor"] == lucro_esperado
    assert r["snapshot"]["margem_contribuicao"]["pct"] == sim._div(mc_esperado, fat, nd=4)


def test_snapshot_markups_espelham_grupo_b():
    r = sim.simular(_modelo_base(), {"cenario": "atual", "markup_seco": 2.5})
    assert r["snapshot"]["markup_seco"] == r["variaveis"]["markup_seco"]
    assert r["snapshot"]["markup_seco"]["multiplicador"] == 2.5


# ── Casos de borda transversais (RNF-02, RF-13) ─────────────────────────────────────────────
def test_media_historica_descarta_meses_zerados():
    assert sim.media_historica([10000.0, 0.0, 12000.0, 0.0]) == 11000.0


def test_media_historica_vazia_ou_toda_zerada_eh_none():
    assert sim.media_historica([]) is None
    assert sim.media_historica([0.0, 0.0]) is None


def test_simular_sem_modelo_nem_ajustes_nao_quebra():
    r = sim.simular(None, None)
    assert r["vendas"]["faturamento"] == 0.0
    assert r["snapshot"]["margem_contribuicao"]["pct"] is None
