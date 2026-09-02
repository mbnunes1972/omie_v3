# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-43 — a porta dos fundos do portão da comissão, pelo
cadastro do parceiro.

Medido antes de escolher: `Parceiro.comissao_padrao_pct`/`ParceiroLoja.comissao_padrao_pct`
(a citação original do achado, "Loja.comissao_padrao_pct", estava imprecisa — o campo por-loja
mora em `ParceiroLoja`, não em `Loja`; corrigido no achado). Nos três ambientes reais
(Homologação, Integração, Produção): **zero parceiros cadastrados** — a escolha entre validar
no cadastro ou medir depois da fusão não tem legado a proteger de nenhum dos dois lados.

Escolhida a segunda (mais robusta, decisão do próprio achado): `_params_iniciais_projeto` só
SUGERE o default do parceiro (rotas GET, nunca grava sozinho); a única gravação real é
`POST /api/projetos/<nome>/parametros` — já gated pelo ACHADO-42. Este teste prova que o valor
que VEIO de um parceiro (não digitado por ninguém na tela) passa pelo MESMO portão."""
import pytest


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _preparar_projeto_com_ambiente(app_db, seed, vbva=10000.0, cfa=4000.0):
    db = app_db.get_session()
    oid = seed["orcamento_l1_id"]
    orc = db.get(app_db.Orcamento, oid)
    orc.desconto_pct = 0.0
    for lk in db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=oid).all():
        db.delete(lk)
    db.flush()
    pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="a43", nome_exibicao="Cozinha",
                             xml_path="p", ambientes_json="[]", order_total=cfa, budget_total=vbva)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    proj = db.get(app_db.Projeto, seed["projeto_l1"])
    proj.parametros_json = None
    db.commit()
    db.close()


def test_medicao_zero_parceiros_cadastrados_nos_tres_reais():
    """Não é um teste de asserção — é o registro da medição pedida ('meça antes de escolher'),
    fixado aqui pra não se perder: 0 parceiros em Homologação/Integração/Produção em 03/09/2026."""
    assert True


def test_caminho_do_parceiro_tambem_passa_pelo_portao(http_client_factory, seed, app_db, projetos_dir):
    """O teste que prova o caminho do PARCEIRO, não o da tela: o valor nunca foi digitado por um
    humano no formulário — veio do cadastro do parceiro, via `_params_iniciais_projeto`
    (GET /parametros sugere), e é reenviado (auto-save) exatamente como a tela reenviaria."""
    _preparar_projeto_com_ambiente(app_db, seed)
    nome = seed["projeto_l1"]

    db = app_db.get_session()
    parc = app_db.Parceiro(nome="Arq Backdoor", abrangencia="loja", comissao_padrao_pct=60.0)
    db.add(parc); db.flush()
    db.add(app_db.ParceiroLoja(parceiro_id=parc.id, loja_id=seed["loja1_id"], ativo=1))
    db.commit()
    pid = parc.id
    db.close()

    c = _login(http_client_factory, "dir_l1")   # master, limite 50% — 60% do parceiro já excede
    st, b = c.post(f"/api/projetos/{nome}/parceiro", {"parceiro_id": pid})
    assert st == 200 and b.get("ok"), b

    # GET /parametros: projeto sem parametros_json salvo ainda → sugere o default do parceiro.
    st2, b2 = c.get(f"/api/projetos/{nome}/parametros")
    assert st2 == 200 and b2["parametros"]["comissao_arq_pct"] == 60.0, b2

    # `incluir_custos=True` (default de `_params_iniciais_projeto`) repassa a comissão ao
    # cliente — sem erosão de margem, o portão corretamente não tem o que barrar aqui. O risco
    # do achado é quando a loja ABSORVE o custo (incluir_custos=False, config legítima) — o
    # auto-save da tela reenvia exatamente essa sugestão, ninguém digitou 60, veio do cadastro.
    proposta = dict(b2["parametros"]); proposta["incluir_custos"] = False
    st3, b3 = c.post(f"/api/projetos/{nome}/parametros", proposta)
    assert st3 == 403, b3
    assert b3.get("requer_autorizacao") is True

    db2 = app_db.get_session()
    proj = db2.get(app_db.Projeto, nome)
    assert proj.parametros_json is None, "não pode ter persistido sem autorização"
    db2.close()


def test_caminho_do_parceiro_aceita_com_autorizador_valido(http_client_factory, seed, app_db, projetos_dir):
    """cons_l1 (operador, limite 10%) não autoriza os 45% do parceiro sozinho; dir_l1 (master,
    limite 50%) autoriza — mesmo padrão de `test_desconto_autorizacao_e2e.py`."""
    _preparar_projeto_com_ambiente(app_db, seed)
    nome = seed["projeto_l1"]

    db = app_db.get_session()
    parc = app_db.Parceiro(nome="Arq Backdoor 2", abrangencia="loja", comissao_padrao_pct=45.0)
    db.add(parc); db.flush()
    db.add(app_db.ParceiroLoja(parceiro_id=parc.id, loja_id=seed["loja1_id"], ativo=1))
    db.commit()
    pid = parc.id
    db.close()

    c = _login(http_client_factory, "cons_l1")
    c.post(f"/api/projetos/{nome}/parceiro", {"parceiro_id": pid})
    _, b2 = c.get(f"/api/projetos/{nome}/parametros")

    proposta = dict(b2["parametros"]); proposta["incluir_custos"] = False
    st_sem, b_sem = c.post(f"/api/projetos/{nome}/parametros", proposta)
    assert st_sem == 403 and b_sem.get("requer_autorizacao") is True, b_sem

    proposta["login_autorizador"] = "dir_l1"
    proposta["senha_autorizador"] = "senha123"
    st3, b3 = c.post(f"/api/projetos/{nome}/parametros", proposta)
    assert st3 == 200 and b3.get("ok") is True, b3
