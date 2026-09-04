"""mod_indicadores — snapshot de indicadores (PURO). Fórmulas clássicas com guardas de divisão
por zero (→ None; a tela mostra "—"). Bases: dicts do balanco()/dre() do mod_contabil."""
import mod_indicadores as mi


def test_liquidez_e_capital_de_giro():
    r = mi.liquidez(ativo_circ=150000.0, passivo_circ=100000.0, caixa=30000.0,
                    diferidos=80000.0)
    assert r["corrente"] == 1.5
    assert r["imediata"] == 0.3
    # ajustada: exclui ativos diferidos (1.1.05/1.1.06 não viram caixa) → (150k−80k)/100k
    assert r["ajustada"] == 0.7
    assert r["capital_giro"] == 50000.0


def test_liquidez_sem_passivo_eh_none():
    r = mi.liquidez(ativo_circ=1000.0, passivo_circ=0.0, caixa=100.0, diferidos=0.0)
    assert r["corrente"] is None and r["imediata"] is None and r["ajustada"] is None
    assert r["capital_giro"] == 1000.0


def test_margens():
    dre = {"receita_liquida": 200000.0, "lucro_bruto": 80000.0, "ebitda": 50000.0,
           "lucro_liquido": 30000.0}
    r = mi.margens(dre)
    assert r["bruta"] == 0.4 and r["ebitda"] == 0.25 and r["liquida"] == 0.15


def test_margens_receita_zero():
    r = mi.margens({"receita_liquida": 0.0, "lucro_bruto": 0.0, "ebitda": 0.0,
                    "lucro_liquido": 0.0})
    assert r["bruta"] is None and r["liquida"] is None


def test_prazos_e_giro():
    # PMR = receber/receita × dias; PMP = fornecedores/CMV × dias; giro = receita/receber
    r = mi.prazos_giro(receber=50000.0, fornecedores=30000.0,
                       receita_periodo=200000.0, cmv_periodo=90000.0, dias=90)
    assert r["pmr_dias"] == 22.5
    assert r["pmp_dias"] == 30.0
    assert r["giro_carteira"] == 4.0
    z = mi.prazos_giro(receber=0, fornecedores=0, receita_periodo=0, cmv_periodo=0, dias=90)
    assert z["pmr_dias"] is None and z["giro_carteira"] is None


def test_tendencia():
    assert mi.tendencia([100, 110, 121]) == {"dir": "alta", "pct": 10.0}
    assert mi.tendencia([100, 100, 90]) == {"dir": "queda", "pct": -10.0}
    assert mi.tendencia([100, 100, 100.4]) == {"dir": "estavel", "pct": 0.4}   # < ±1% = estável
    assert mi.tendencia([0, 0, 50]) == {"dir": "alta", "pct": None}            # base zero
    assert mi.tendencia([100]) == {"dir": "estavel", "pct": None}              # série curta
    assert mi.tendencia([]) == {"dir": "estavel", "pct": None}


def test_kpis_comerciais():
    r = mi.kpis_comerciais(status_counts={"quente": 3, "morno": 2, "frio": 1,
                                          "convertido": 4, "perdido": 2},
                           contratos_periodo=[100000.0, 150000.0])
    assert r["pipeline_ativo"] == 6                      # quente+morno+frio
    assert r["taxa_conversao"] == round(4 / 6, 4)        # convertidos / decididos
    assert r["ticket_medio"] == 125000.0
    assert r["vendas_periodo"] == 250000.0
    assert r["n_vendas_periodo"] == 2
    z = mi.kpis_comerciais(status_counts={}, contratos_periodo=[])
    assert z["taxa_conversao"] is None and z["ticket_medio"] is None


# ── Painel Estratégico (2026-08-09) — funções novas ──────────────────────────────────────────

def test_janela_periodo_mes():
    from datetime import date
    ini, fim, ini_ant, fim_ant = mi.janela_periodo("mes", date(2026, 8, 15))
    assert (ini, fim) == (date(2026, 8, 1), date(2026, 8, 31))
    assert (ini_ant, fim_ant) == (date(2026, 7, 1), date(2026, 7, 31))


def test_janela_periodo_mes_janeiro_vira_dezembro_ano_anterior():
    from datetime import date
    ini, fim, ini_ant, fim_ant = mi.janela_periodo("mes", date(2026, 1, 10))
    assert (ini, fim) == (date(2026, 1, 1), date(2026, 1, 31))
    assert (ini_ant, fim_ant) == (date(2025, 12, 1), date(2025, 12, 31))


def test_janela_periodo_trimestre():
    from datetime import date
    # 15/ago cai no Q3 (jul-set)
    ini, fim, ini_ant, fim_ant = mi.janela_periodo("trimestre", date(2026, 8, 15))
    assert (ini, fim) == (date(2026, 7, 1), date(2026, 9, 30))
    assert (ini_ant, fim_ant) == (date(2026, 4, 1), date(2026, 6, 30))


def test_janela_periodo_trimestre_primeiro_do_ano_vira_q4_ano_anterior():
    from datetime import date
    ini, fim, ini_ant, fim_ant = mi.janela_periodo("trimestre", date(2026, 2, 1))
    assert (ini, fim) == (date(2026, 1, 1), date(2026, 3, 31))
    assert (ini_ant, fim_ant) == (date(2025, 10, 1), date(2025, 12, 31))


def test_janela_periodo_ano():
    from datetime import date
    ini, fim, ini_ant, fim_ant = mi.janela_periodo("ano", date(2026, 8, 15))
    assert (ini, fim) == (date(2026, 1, 1), date(2026, 12, 31))
    assert (ini_ant, fim_ant) == (date(2025, 1, 1), date(2025, 12, 31))


def test_variacao_pct():
    # fração, não %-inteiro (mesma convenção do resto do módulo: "a tela formata em %")
    assert mi.variacao_pct(110, 100) == 0.1
    assert mi.variacao_pct(90, 100) == -0.1
    assert mi.variacao_pct(50, 0) is None


def test_variacao_pct_base_negativa_nao_inverte_o_sinal():
    # achado do usuário (Painel Estratégico, 2026-08-09): prejuízo encolhendo é MELHORA, não
    # pode virar % negativo/seta vermelha só porque a base do período anterior é negativa.
    assert mi.variacao_pct(-2660.41, -30000.0) > 0          # prejuízo encolheu → melhora (positivo)
    assert mi.variacao_pct(-30000.0, -2660.41) < 0          # prejuízo cresceu → piora (negativo)
    assert mi.variacao_pct(1000.0, -500.0) > 0              # saiu do prejuízo pro lucro → melhora
    assert mi.variacao_pct(-500.0, 1000.0) < 0              # saiu do lucro pro prejuízo → piora
    # quadrante clássico (base positiva) seguem batendo com a leitura intuitiva de sempre
    assert mi.variacao_pct(110, 100) == 0.1
    assert mi.variacao_pct(90, 100) == -0.1


def test_media():
    assert mi.media([1.5, 2.5, 3.5]) == 2.5
    assert mi.media([]) is None


def test_custo_fixo_stats():
    r = mi.custo_fixo_stats([10000.0, 10000.0, 12000.0])
    assert r["media"] == round(32000 / 3, 2)
    assert r["ultimo"] == 12000.0
    assert r["variacao_pct"] == 0.2                       # 12000 vs média dos 2 anteriores (10000)
    assert mi.custo_fixo_stats([])["media"] is None
    assert mi.custo_fixo_stats([500.0])["variacao_pct"] is None   # só 1 mês, sem "anteriores"


def test_ponto_equilibrio():
    assert mi.ponto_equilibrio(custo_fixo=50000.0, margem_contribuicao_pct=0.25) == 200000.0
    assert mi.ponto_equilibrio(custo_fixo=50000.0, margem_contribuicao_pct=0) is None
    assert mi.ponto_equilibrio(custo_fixo=50000.0, margem_contribuicao_pct=-0.1) is None


def test_endividamento():
    assert mi.endividamento(passivo_total=40000.0, ativo_total=100000.0) == 0.4
    assert mi.endividamento(passivo_total=40000.0, ativo_total=0.0) is None


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_endpoint_tenancy_e_venda_por_assinatura(http_client_factory, seed, app_db):
    # QA Vera 🔴/🟠: (1) contrato de loja FORA do owner (avulsa) não vaza; (2) venda conta
    # pela 1ª ASSINATURA (rascunho gerado não conta; assinatura conta no mês certo).
    # LP-17 (03/09, rescaldo do ACHADO-48/F2-14): a série "vendas" do endpoint bucketa por
    # ContratoAssinatura.assinado_em contra `mod_contabil.hoje_no_fuso` (fuso do dono do livro,
    # America/Sao_Paulo por padrão) — o default de coluna (`datetime.utcnow`) só concorda com
    # esse "hoje" por acidente de horário. A assinatura que decide o teste carimba explícito,
    # pela mesma fonte que o endpoint usa, não pelo default do modelo.
    import mod_contabil
    from datetime import datetime as _dt
    db = app_db.get_session()
    # loja AVULSA (owner próprio) com contrato assinado gordo — não pode aparecer p/ dir_l1
    lj = db.query(app_db.Loja).filter_by(codigo="AVX").first()
    if lj is None:
        lj = app_db.Loja(nome="Avulsa X", codigo="AVX")
        db.add(lj); db.flush()
    pav = app_db.Projeto(nome_safe="Proj_AVX", loja_id=lj.id, status="quente")
    db.add(pav)
    oav = app_db.Orcamento(projeto_id="Proj_AVX", nome="O1", ordem=1, loja_id=lj.id,
                           valor_total=999999.0)
    db.add(oav); db.flush()
    cav = app_db.Contrato(projeto_nome="Proj_AVX", orcamento_id=oav.id, loja_id=lj.id,
                          gerado_em=_dt.now())
    db.add(cav); db.flush()
    db.add(app_db.ContratoAssinatura(contrato_id=cav.id, parte="loja", nome="X",
                                     cpf="0", hash_sha256="x"))
    # na REDE do dir_l1: contrato do seed GERADO mas sem assinatura (rascunho — não conta)
    ct1 = (db.query(app_db.Contrato)
             .filter_by(projeto_nome=db.get(app_db.Orcamento,
                                            seed["orcamento_l1_id"]).projeto_id).first())
    ct1.gerado_em = _dt.now()
    o1 = db.get(app_db.Orcamento, ct1.orcamento_id)
    o1.valor_total = 100000.0
    db.commit()
    ct1_id = ct1.id
    db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/financeiro/indicadores?meses=3")
    ind = body["indicadores"]
    assert ind["comercial"]["n_vendas_periodo"] == 0     # rascunho não é venda; avulsa não vaza
    assert ind["comercial"]["vendas_periodo"] == 0.0

    # assina o contrato da rede → vira venda de 100.000 (e SÓ ela)
    db = app_db.get_session()
    agora = mod_contabil.agora_no_fuso(db, "loja", seed["loja1_id"])
    db.add(app_db.ContratoAssinatura(contrato_id=ct1_id, parte="loja", nome="L",
                                     cpf="0", hash_sha256="x", assinado_em=agora))
    db.commit(); db.close()
    st, body = c.get("/api/financeiro/indicadores?meses=3")
    ind = body["indicadores"]
    assert ind["comercial"]["n_vendas_periodo"] == 1
    assert ind["comercial"]["vendas_periodo"] == 100000.0   # sem os 999.999 da avulsa
    assert ind["series"]["vendas"][-1] == 100000.0


def test_endpoint_indicadores_e2e(http_client_factory, seed, app_db):
    # smoke E2E: shape completo + números coerentes com lançamentos reais
    import mod_contabil as mc
    from datetime import datetime
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "captacao_emprestimo", 50000.0, ref="i1",
                        data=datetime(2026, 7, 1))
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/financeiro/indicadores?meses=3")
    assert st == 200 and body["ok"], body
    ind = body["indicadores"]
    for chave in ("liquidez", "margens", "prazos", "comercial", "series", "tendencias"):
        assert chave in ind, chave
    assert ind["meses"] == 3
    assert len(ind["series"]["labels"]) == 3
    assert ind["caixa"] >= 50000.0                        # o empréstimo entrou no caixa
    assert ind["liquidez"]["capital_giro"] is not None
    assert ind["balanco_confere"] is True
    # clamp do parâmetro
    st, body = c.get("/api/financeiro/indicadores?meses=99")
    assert body["indicadores"]["meses"] == 24
