"""docs/db/TESTE_NEGOCIACAO_VALOR_TOTAL.md, Medição 2 — o que fica no banco depois de cada
fail-soft (ACHADO-19, seis rotas).

MEDIÇÃO, NÃO CONSERTO. Para cada rota, força a falha de `_recalcular_orcamento` (monkeypatch —
Medição 1 não achou entrada real produzível por usuário que levante), chama a rota pelo cliente
HTTP de teste, e lê o banco depois. Compara COLUNA POR COLUNA (nunca por total)."""
import json

import pytest


COLUNAS = ("valor_total", "valor_liquido", "desconto_pct", "forma_pagamento", "negociacao_json",
          "vbvo", "cfo", "vbno", "vavo", "cust_ad", "com_arq_orc", "pro_fid_orc",
          "desc_tot_pct", "markup", "prov_imp", "cust_fin", "val_cont")


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _snapshot(app_db, oid):
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, oid)
        return {c: getattr(orc, c) for c in COLUNAS}
    finally:
        db.close()


def _diff(antes, depois):
    return {c: (antes[c], depois[c]) for c in COLUNAS if antes[c] != depois[c]}


def _forcar_falha(monkeypatch, mensagem="falha forçada — medição ACHADO-19"):
    import main
    def _explode(orc, db):
        raise RuntimeError(mensagem)
    monkeypatch.setattr(main, "_recalcular_orcamento", _explode)


def _preparar_ambiente_e_valor(app_db, seed):
    """Ambiente com valor real + 1a chamada bem-sucedida (recálculo real, sem monkeypatch) —
    dá um "antes" com valor_total != 0/None, pra medir divergência de verdade (não só
    ausência)."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    ja = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).first()
    if not ja:
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                                 nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                                 budget_total=90000.0, order_total=40000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id))
        pa_id = pa.id
    else:
        pa_id = ja.pool_ambiente_id
    db.commit(); db.close()
    return oid, pa_id


# ── rota 1: /api/orcamentos/<id>/margens (main.py:10904) ─────────────────────────────────────
def test_margens_fail_soft(app_db, seed, http_client_factory, monkeypatch):
    oid, _pa = _preparar_ambiente_e_valor(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post("/api/orcamentos/%d/margens" % oid, {"desconto_pct": 0.0})
    assert st == 200 and b["ok"], b
    antes = _snapshot(app_db, oid)
    assert antes["valor_total"], "pré-condição: valor_total tem que existir antes do teste"

    _forcar_falha(monkeypatch)
    st, b = c.post("/api/orcamentos/%d/margens" % oid, {"desconto_pct": 25.0})
    depois = _snapshot(app_db, oid)

    assert st == 200 and b["ok"] is True, b
    assert b.get("sombra") is None and "erro" not in b or b.get("erro_sombra"), b
    diferencas = _diff(antes, depois)
    print("MARGENS diff:", diferencas, "resposta:", b)
    assert diferencas.get("desconto_pct") == (0.0, 25.0), (
        "esperava desconto_pct COMMITADO (25.0) mesmo com recálculo falho — %r" % diferencas)
    assert "valor_total" not in diferencas, (
        "valor_total NÃO deveria mudar (recálculo falhou) — se mudou, o fail-soft parou de "
        "deixar rastro: %r" % diferencas)


# ── rota 2: /api/orcamentos/<id>/descontos (main.py:15591) ───────────────────────────────────
def test_descontos_fail_soft(app_db, seed, http_client_factory, monkeypatch):
    oid, pa_id = _preparar_ambiente_e_valor(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.put("/api/orcamentos/%d/descontos" % oid, {"descontos": {str(pa_id): 0}})
    assert st == 200, b
    antes = _snapshot(app_db, oid)
    assert antes["valor_total"], "pré-condição: valor_total tem que existir antes do teste"

    _forcar_falha(monkeypatch)
    st, b = c.put("/api/orcamentos/%d/descontos" % oid, {"descontos": {str(pa_id): 20}})
    depois = _snapshot(app_db, oid)

    assert st == 200 and b["ok"] is True and b.get("erro_sombra"), b
    diferencas = _diff(antes, depois)
    print("DESCONTOS diff:", diferencas, "resposta:", b)
    db = app_db.get_session()
    link = db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid, pool_ambiente_id=pa_id).first()
    desc_amb_commitado = link.desconto_individual_pct
    db.close()
    assert desc_amb_commitado == 20, (
        "desconto_individual_pct do ambiente deveria estar COMMITADO (20) mesmo com "
        "recálculo falho — valor real: %r" % desc_amb_commitado)
    assert "valor_total" not in diferencas, (
        "valor_total NÃO deveria mudar (recálculo falhou) — %r" % diferencas)


# ── rota 3: /api/projetos/<nome>/parametros (main.py:10840) ──────────────────────────────────
def test_parametros_fail_soft(app_db, seed, http_client_factory, monkeypatch):
    oid, _pa = _preparar_ambiente_e_valor(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    antes = _snapshot(app_db, oid)
    assert antes["valor_total"], "pré-condição: valor_total tem que existir antes do teste"

    _forcar_falha(monkeypatch)
    st, b = c.post("/api/projetos/%s/parametros" % seed["projeto_l1"],
                   {"comissao_arq_ativa": True, "comissao_arq_pct": 15.0})
    depois = _snapshot(app_db, oid)

    assert st == 200 and b["ok"] is True, b
    diferencas = _diff(antes, depois)
    print("PARAMETROS diff:", diferencas, "resposta:", b)
    db = app_db.get_session()
    proj = db.query(app_db.Projeto).filter_by(nome_safe=seed["projeto_l1"]).first()
    params_commitados = json.loads(proj.parametros_json or "{}")
    db.close()
    assert params_commitados.get("comissao_arq_ativa") is True, (
        "parametros_json deveria estar COMMITADO (comissao_arq_ativa=True) mesmo com "
        "recálculo falho — valor real: %r" % params_commitados)
    assert "valor_total" not in diferencas, (
        "valor_total NÃO deveria mudar (recálculo falhou) — %r" % diferencas)


# ── rota 4: PATCH /orcamentos/<id>/valor (main.py:15825) ─────────────────────────────────────
def test_valor_patch_fail_soft(app_db, seed, http_client_factory, monkeypatch):
    oid, _pa = _preparar_ambiente_e_valor(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.patch("/orcamentos/%d/valor" % oid,
                    {"forma_pagamento": json.dumps({"tipo": "avista", "total_cliente": 0})})
    assert st == 200, b
    antes = _snapshot(app_db, oid)
    assert antes["valor_total"], "pré-condição: valor_total tem que existir antes do teste"

    novo_fp = json.dumps({"tipo": "avista", "total_cliente": 12345.0})
    _forcar_falha(monkeypatch)
    st, b = c.patch("/orcamentos/%d/valor" % oid, {"forma_pagamento": novo_fp})
    depois = _snapshot(app_db, oid)

    assert st == 200, b
    diferencas = _diff(antes, depois)
    print("VALOR (PATCH) diff:", diferencas, "resposta:", b)
    assert diferencas.get("forma_pagamento") == (antes["forma_pagamento"], novo_fp), (
        "forma_pagamento deveria estar COMMITADO (novo valor) mesmo com recálculo falho — %r"
        % diferencas)
    assert "valor_total" not in diferencas, (
        "valor_total NÃO deveria mudar (recálculo falhou) — %r" % diferencas)


# ── rota 5: POST /api/projetos/<nome>/pe/complemento/orcamento (main.py:7838-ish) ────────────
def test_complemento_pe_orcamento_fail_soft(app_db, seed, http_client_factory, monkeypatch):
    """Setup pesado: precisa de contrato assinado + ambiente marcado renegociar_pe + ArquivoPE
    de complemento carregado — mesmo padrão de tests/test_complemento_pe_e2e.py::_setup."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    nome = orc.projeto_id
    pa = app_db.PoolAmbiente(nome="Cozinha", nome_exibicao="Cozinha", xml_path="fake/coz.xml",
                             ambientes_json="{}", projeto_id=nome,
                             budget_total=80000.0, order_total=30000.0)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    pa.renegociar_pe = 1
    ct = (db.query(app_db.Contrato).filter_by(projeto_nome=nome)
            .order_by(app_db.Contrato.id.desc()).first())
    db.add(app_db.ContratoAssinatura(contrato_id=ct.id, parte="loja", nome="Loja",
                                     cpf="000.000.000-00", hash_sha256="x"))
    db.commit()
    pa_id = pa.id
    db.close()

    c = _login(http_client_factory, "dir_l1")
    # 1a chamada bem-sucedida (sem monkeypatch): cria o orçamento de complemento com valor real
    reg = app_db.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pa_id, formato="xml_compl",
                          valor_venda=84000.0, valor_atualizado=32000.0)
    db = app_db.get_session(); db.add(reg); db.commit(); db.close()
    st, b = c.post("/api/projetos/%s/pe/complemento/orcamento" % nome, {})
    assert st == 200 and b["ok"], b
    aj_id = b["orcamento"]["id"]
    antes = _snapshot(app_db, aj_id)
    assert antes["valor_total"], "pré-condição: valor_total do complemento tem que existir"

    # muda o XML de complemento (nova diferença) e refaz a chamada, agora com recálculo forçado a falhar
    db = app_db.get_session()
    reg2 = db.query(app_db.ArquivoPE).filter_by(projeto_nome=nome, pool_ambiente_id=pa_id,
                                                formato="xml_compl").first()
    reg2.valor_venda = 95000.0
    db.commit(); db.close()

    _forcar_falha(monkeypatch)
    st, b = c.post("/api/projetos/%s/pe/complemento/orcamento" % nome, {})
    depois = _snapshot(app_db, aj_id)

    assert st == 200 and b["ok"], b
    diferencas = _diff(antes, depois)
    print("COMPLEMENTO/ORCAMENTO diff:", diferencas, "resposta:", b)
    # ACHADO-19: aqui o commit vem DEPOIS do except (forma_pagamento/negociacao_json zerados
    # nesta rota) — o que muda mesmo com recálculo falho.
    assert diferencas.get("forma_pagamento") == (antes["forma_pagamento"], None) or antes["forma_pagamento"] is None, (
        "forma_pagamento deveria zerar (parte do wiring desta rota) mesmo com recálculo "
        "falho — %r" % diferencas)
    assert "valor_total" not in diferencas, (
        "valor_total NÃO deveria mudar (recálculo falhou) — se o novo XML (95000) tivesse "
        "sido processado, valor_total mudaria; ficou em %r" % (depois["valor_total"],))
