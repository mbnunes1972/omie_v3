# -*- coding: utf-8 -*-
"""F2-28 (docs/db/ROTEIRO.md) — percurso do Marcelo no beta4 (Teste_6), quatro frentes.

Passo 1a (medido): "Atual" no painel de Provisões lia `_negociacao_breakdown` (recomputa da
negociação salva, nunca do razão) — Custo de Fábrica e Outros Fornecedores agora leem o SALDO
VIVO da provisão (as duas contas que a reclassificação da AF efetivamente move).

Passo 2 (DECIDIDO): Custo de Fábrica vira READ-ONLY na AF — só "Outros Fornecedores" é digitado;
o sistema lança a contrapartida contra a fábrica sozinho (reclassificação automática, pelo
INCREMENTO do saldo de Outros Fornecedores).

Passo 4 (DECIDIDO): "Concluir Contrato" fecha a fase FINANCEIRA (`Contrato.
financeiro_concluido_em`, distinta de `status`) — confere consistência ANTES de fechar (docs/db/
PLANO_AJUSTES.md, princípio #5); a partir daí, reabrir a AF exige Diretor."""
import mod_contabil as mc
from tests.test_provisao_registro import _setup_venda


def _s(db, ot, oid, cod, projeto_id=None):
    if projeto_id is None:
        c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
        return mc.saldo_conta(db, ot, oid, c.id)
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    sentido = "devedor" if mc._natureza(c.grupo) == "devedora" else "credor"
    return round(mc._mov(db, ot, oid, cod, sentido, None, None, projeto_id=projeto_id), 2)


# ── Passo 4 — conferir_provisao_ativo_par ────────────────────────────────────────────────────
def test_conferir_provisao_ativo_par_tudo_pareado(app_db):
    db = app_db.get_session(); ot, oid = "loja", 9600; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"montagem": 500.0, "custo_fabrica": 1000.0},
                                       ref_base="pf:P")
    assert mc.conferir_provisao_ativo_par(db, ot, oid, "P") == {}
    db.close()


def test_conferir_provisao_ativo_par_acusa_divergencia(app_db):
    """Reclassificar SEM o ativo acompanhar (chamada direta e incompleta, simulando um lançamento
    pela metade) tem que acusar a divergência."""
    db = app_db.get_session(); ot, oid = "loja", 9601; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    # só a perna da provisão, sem a do ativo — o próprio cenário que a checagem existe pra pegar
    prov06 = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="2.1.04.06").first()
    prov14 = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="2.1.04.14").first()
    mc.lancar(db, ot, oid, conta_debito_id=prov06.id, conta_credito_id=prov14.id, valor=300.0,
             projeto_id="P", origem="teste_divergencia")
    div = mc.conferir_provisao_ativo_par(db, ot, oid, "P")
    assert "2.1.04.06" in div and "2.1.04.14" in div
    assert div["2.1.04.06"]["diferenca"] == -300.0   # provisão caiu, ativo não acompanhou
    assert div["2.1.04.14"]["diferenca"] == 300.0
    db.close()


# ── Passo 1a + 2 — Custo de Fábrica read-only, Outros Fornecedores migra automaticamente ────
def test_atual_le_saldo_vivo_nao_o_motor_de_negociacao(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    import mod_contabil as _mc
    db = app_db.get_session()
    try:
        ot, oid = _mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        _mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                            {"custo_fabrica": 1000.0}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()
    _, prov = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    # "Atual" reflete o saldo REAL da provisão (1000, constituído fora da negociação) — não o
    # motor (_negociacao_breakdown), que não sabe desse lançamento e devolveria outro número.
    assert prov["provisoes"]["atual"]["itens"]["custo_fabrica"] == 1000.0
    assert prov["provisoes"]["atual"]["itens"]["out_forn"] == 0.0


def test_editar_out_forn_migra_automaticamente_da_fabrica(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    import mod_contabil as _mc
    db = app_db.get_session()
    try:
        ot, oid = _mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        _mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                            {"custo_fabrica": 1000.0}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()
    itens = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
             "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0,
             "prov_imp": 0.0, "out_forn": 300.0, "custo_fabrica": 999999.0}
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": itens, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    db = app_db.get_session()
    try:
        ot, oid = _mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        # migrou 300 de Custo de Fábrica pra Outros Fornecedores — o valor absurdo digitado em
        # custo_fabrica (999999) foi IGNORADO (read-only de verdade, não só na tela).
        assert _s(db, ot, oid, "2.1.04.06", projeto_id=seed["projeto_l1"]) == 700.0
        assert _s(db, ot, oid, "2.1.04.14", projeto_id=seed["projeto_l1"]) == 300.0
        assert _s(db, ot, oid, "1.1.06.06", projeto_id=seed["projeto_l1"]) == 700.0
        assert _s(db, ot, oid, "1.1.06.14", projeto_id=seed["projeto_l1"]) == 300.0
    finally:
        db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        db.commit(); db.close()


def test_reduzir_out_forn_nao_reverte_a_migracao(http_client_factory, app_db, seed, projetos_dir):
    """Migração só numa direção (fábrica → outros), igual antes do F2-28: digitar um valor MENOR
    de out_forn não devolve nada pra fábrica."""
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    import mod_contabil as _mc
    db = app_db.get_session()
    try:
        ot, oid = _mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        _mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                            {"custo_fabrica": 1000.0}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()
    base = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
            "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0, "prov_imp": 0.0}
    c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
          {"decisao": "revisa", "itens": {**base, "out_forn": 300.0},
           "login": "dir_l1", "senha": "senha123"})
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": {**base, "out_forn": 100.0},
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    db = app_db.get_session()
    try:
        ot, oid = _mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        assert _s(db, ot, oid, "2.1.04.14", projeto_id=seed["projeto_l1"]) == 300.0   # não caiu
        assert _s(db, ot, oid, "2.1.04.06", projeto_id=seed["projeto_l1"]) == 700.0   # não voltou
    finally:
        db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
        db.commit(); db.close()


# ── Passo 4 — POST /contrato/concluir-financeiro + gate de revisão da AF ────────────────────
def _contrato_vigente(app_db, seed, nome, com_af1=True):
    db = app_db.get_session()
    orc = app_db.Orcamento(projeto_id=nome, nome="O", ordem=1, loja_id=seed["loja1_id"])
    db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"], status="vigente"))
    db.add(orc); db.flush()
    contrato = app_db.Contrato(projeto_nome=nome, orcamento_id=orc.id, status="vigente",
                              loja_id=seed["loja1_id"])
    db.add(contrato)
    if com_af1:
        db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo="8", status="concluido"))
    db.commit()
    contrato_id = contrato.id
    db.close()
    return contrato_id


def test_concluir_financeiro_recusa_af1_em_andamento(http_client_factory, app_db, seed):
    nome = "F228_af_aberta"
    _contrato_vigente(app_db, seed, nome, com_af1=False)
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo="8", status="pendente"))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.post("/api/projetos/%s/contrato/concluir-financeiro" % nome,
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 409 and body["ok"] is False, body
    assert any("Aprovação Financeira I" in f for f in body["faltas"])


def test_concluir_financeiro_recusa_provisao_ativo_divergente(http_client_factory, app_db, seed):
    nome = "F228_divergente"
    _contrato_vigente(app_db, seed, nome)
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"custo_fabrica": 1000.0}, ref_base="pf:" + nome)
    prov06 = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="2.1.04.06").first()
    prov14 = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="2.1.04.14").first()
    mc.lancar(db, ot, oid, conta_debito_id=prov06.id, conta_credito_id=prov14.id, valor=100.0,
             projeto_id=nome, origem="teste_divergencia")
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.post("/api/projetos/%s/contrato/concluir-financeiro" % nome,
                      {"login": "dir_l1", "senha": "senha123"})
    assert st == 409 and body["ok"] is False, body
    assert any("2.1.04.06" in f for f in body["faltas"])


def test_concluir_financeiro_sucesso_e_trava_revisao_da_af(http_client_factory, app_db, seed):
    nome = "F228_fecha"
    _contrato_vigente(app_db, seed, nome)
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.constituir_provisoes_fechamento(db, ot, oid, nome, {"custo_fabrica": 1000.0}, ref_base="pf:" + nome)
    orc_id = db.query(app_db.Orcamento).filter_by(projeto_id=nome).first().id
    # perfil custom: aprova financeiro, mas SEM "autorizar" (nem master nem gerencial servem —
    # os dois têm "autorizar":True por padrão; só assim o step-up de Diretor é testável de verdade).
    import json as _json
    from auth import perfis as _perfis
    db.add(app_db.PerfilAcesso(loja_id=seed["loja1_id"], slug="f228_sem_aut",
                              nome="Gerente sem autorizar", base="operador",
                              modulos_json=_json.dumps(["comercial", "financeiro"]),
                              capacidades_json=_json.dumps({"aprovar_financeiro": True}), sistema=0))
    u = app_db.Usuario(nome="Gerente F228", login="f228_gerente", nivel="f228_sem_aut",
                       loja_id=seed["loja1_id"], ativo=1)
    u.set_senha("senha123")
    db.add(u)
    db.commit(); db.close()
    _perfis.recarregar()
    assert _perfis.pode("f228_sem_aut", "aprovar_financeiro") is True
    assert _perfis.pode("f228_sem_aut", "autorizar") is False

    c = http_client_factory(); c.login("f228_gerente", "senha123")
    st, body = c.post("/api/projetos/%s/contrato/concluir-financeiro" % nome,
                      {"login": "f228_gerente", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    # idempotente — chamar de novo não falha nem regrava
    st2, body2 = c.post("/api/projetos/%s/contrato/concluir-financeiro" % nome,
                        {"login": "f228_gerente", "senha": "senha123"})
    assert st2 == 200 and body2.get("ja_concluido") is True

    # a partir daqui, reabrir a AF exige Diretor — o gerente (sem "autorizar") é recusado.
    db = app_db.get_session()
    db.add(app_db.ProvisaoRegistro(orcamento_id=orc_id, versao="venda",
                                   itens_json='{"custo_fabrica": 1000.0}', cfo=1000.0, val_liq=0.0,
                                   cust_var=1000.0, marg_cont=0.0, decisao=None, por_id=1))
    db.commit(); db.close()
    st3, body3 = c.post("/api/orcamentos/%d/provisoes/rev1" % orc_id,
                       {"decisao": "revisa", "itens": {"custo_fabrica": 1000.0},
                        "login": "f228_gerente", "senha": "senha123"})
    assert st3 == 403 and body3["ok"] is False, body3
    assert "Diretor" in body3["erro"]
