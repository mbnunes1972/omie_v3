import pytest
import sqlalchemy.exc
import mod_escopo


# ── F1.1: modelo + UniqueConstraint (ambiente concreto; projeto-inteiro NULL é upsert no app) ──
def test_atribuicao_unique_por_papel_ambiente(app_db, seed):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Cozinha", nome_exibicao="Cozinha",
                             xml_path="x.xml", ambientes_json="[]", budget_total=0.0)
    db.add(pa); db.flush()
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="Proj_L1",
                                     pool_ambiente_id=pa.id, papel="medicao")); db.commit()
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="Proj_L1",
                                     pool_ambiente_id=pa.id, papel="medicao"))
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.commit()
    db.rollback()
    # app_db é module-scoped: limpa o que criou p/ não vazar para os testes HTTP seguintes
    db.query(app_db.AtribuicaoAmbiente).filter_by(projeto_nome="Proj_L1").delete()
    db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").delete()
    db.commit(); db.close()


# ── F1.2: predicados puros de escopo ─────────────────────────────────────────────
def _ator(nivel, uid=1):
    return {"nivel": nivel, "id": uid}


class _Meta:
    def __init__(self, nome_safe, criado_por_id=None):
        self.nome_safe = nome_safe
        self.criado_por_id = criado_por_id


def test_gerencia_ve_tudo_admin_nada():
    m = _Meta("P", criado_por_id=999)
    for g in ("master", "gerencial", "master"):
        assert mod_escopo.pode_ver_projeto(_ator(g), m, set()) is True
    for a in ("super_admin", "admin_rede"):
        assert mod_escopo.pode_ver_projeto(_ator(a), m, set()) is False


def test_consultor_por_posse():
    meu = _Meta("P1", criado_por_id=7)
    outro = _Meta("P2", criado_por_id=8)
    assert mod_escopo.pode_ver_projeto(_ator("operador", 7), meu, set()) is True
    assert mod_escopo.pode_ver_projeto(_ator("operador", 7), outro, set()) is False
    # legado sem criador é visível
    assert mod_escopo.pode_ver_projeto(_ator("operador", 7), _Meta("P3", None), set()) is True


def test_operacional_so_atribuido():
    m = _Meta("P", criado_por_id=99)
    # medidor id=5 só vê o projeto se estiver no conjunto de atribuídos
    assert mod_escopo.pode_ver_projeto(_ator("medidor", 5), m, {5}) is True
    assert mod_escopo.pode_ver_projeto(_ator("medidor", 5), m, {6}) is False
    # conferente (fora do escopo por atribuição) vê tudo na loja (decisão Fase 1)
    assert mod_escopo.pode_ver_projeto(_ator("conferente", 5), m, set()) is True


def test_resolver_responsavel_ambiente_prevalece():
    atr = [
        {"papel": "medicao", "pool_ambiente_id": None, "funcionario_id": 10},   # projeto inteiro
        {"papel": "medicao", "pool_ambiente_id": 3, "funcionario_id": 20},      # específico do amb. 3
    ]
    assert mod_escopo.resolver_responsavel(atr, 3, "medicao")["funcionario_id"] == 20   # específico
    assert mod_escopo.resolver_responsavel(atr, 9, "medicao")["funcionario_id"] == 10   # cai no inteiro
    assert mod_escopo.resolver_responsavel(atr, 9, "montagem") is None                  # papel sem atrib.


def test_visao_do_papel():
    assert mod_escopo.visao_do_papel(_ator("medidor")) == "operacional"
    assert mod_escopo.visao_do_papel(_ator("operador")) == "comercial"
    assert mod_escopo.visao_do_papel(_ator("master")) == "comercial"
    assert mod_escopo.visao_do_papel(_ator("super_admin")) == "nenhuma"


# ── F1.3: CRUD do Mapa (HTTP) — função compatível, 1:1 substitui, auditoria, consultor barrado ──
def _mk_medidores(app_db, loja):
    db = app_db.get_session()
    fmed = app_db.Funcao(loja_id=loja, nome="Medidor")
    fmont = app_db.Funcao(loja_id=loja, nome="Montador")
    db.add_all([fmed, fmont]); db.flush()
    a = app_db.Funcionario(loja_id=loja, nome="Ana Medidora", funcao_id=fmed.id, status="ativo")
    b = app_db.Funcionario(loja_id=loja, nome="Bia Medidora", funcao_id=fmed.id, status="ativo")
    m = app_db.Funcionario(loja_id=loja, nome="Beto Montador", funcao_id=fmont.id, status="ativo")
    db.add_all([a, b, m]); db.commit()
    ids = (a.id, b.id, m.id); db.close()
    return ids


def test_mapa_upsert_funcao_substitui_e_audita(http_client_factory, seed, projetos_dir, app_db):
    loja = None
    dbx = app_db.get_session()
    loja = dbx.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id; dbx.close()
    ana, bia, beto = _mk_medidores(app_db, loja)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # função incompatível (Montador em Medição) -> 400
    st, d = c.post("/api/projetos/Proj_L1/atribuicoes",
                   {"papel": "medicao", "pool_ambiente_id": None, "funcionario_id": beto})
    assert st == 400 and d.get("ok") is False, d
    # compatível -> 200, aparece
    st2, d2 = c.post("/api/projetos/Proj_L1/atribuicoes",
                     {"papel": "medicao", "pool_ambiente_id": None, "funcionario_id": ana})
    assert st2 == 200
    med = [a for a in d2["atribuicoes"] if a["papel"] == "medicao" and a["pool_ambiente_id"] is None]
    assert len(med) == 1 and med[0]["responsavel_nome"] == "Ana Medidora"
    # 1:1 — atribuir outro medidor no mesmo (papel, projeto-inteiro) SUBSTITUI (não duplica)
    st3, d3 = c.post("/api/projetos/Proj_L1/atribuicoes",
                     {"papel": "medicao", "pool_ambiente_id": None, "funcionario_id": bia})
    med = [a for a in d3["atribuicoes"] if a["papel"] == "medicao" and a["pool_ambiente_id"] is None]
    assert len(med) == 1 and med[0]["responsavel_nome"] == "Bia Medidora"
    # limpar (alvo vazio)
    st4, d4 = c.post("/api/projetos/Proj_L1/atribuicoes",
                     {"papel": "medicao", "pool_ambiente_id": None})
    assert st4 == 200 and not any(a["papel"] == "medicao" for a in d4["atribuicoes"])
    # auditoria registrada
    db = app_db.get_session()
    try:
        assert db.query(app_db.LogAcaoGerencial).filter_by(
            projeto_nome="Proj_L1", acao="atribuir_mapa").count() >= 3
    finally:
        db.close()


def test_mapa_montagem_aceita_varios_por_ambiente(http_client_factory, seed, projetos_dir, app_db):
    """2026-08-06 (pedido do usuário): só Montagem aceita mais de 1 executor por ambiente —
    PE/Medição/Assistência continuam 1:1. {alvos:[...]} substitui o CONJUNTO inteiro (mesmo
    padrão de mod_equipe._salvar_montagem, só que por ambiente em vez de projeto inteiro)."""
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fmont = app_db.Funcao(loja_id=loja, nome="Montador")
    db.add(fmont); db.flush()
    beto = app_db.Funcionario(loja_id=loja, nome="Beto Montador", funcao_id=fmont.id, status="ativo")
    caio = app_db.Funcionario(loja_id=loja, nome="Caio Montador", funcao_id=fmont.id, status="ativo")
    db.add_all([beto, caio]); db.flush()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Sala", nome_exibicao="Sala",
                             xml_path="x.xml", ambientes_json="[]", budget_total=0.0)
    db.add(pa); db.commit()
    beto_id, caio_id, amb_id = beto.id, caio.id, pa.id
    db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # 2 executores no MESMO ambiente/papel — aceita os dois
    st, d = c.post("/api/projetos/Proj_L1/atribuicoes",
                   {"papel": "montagem", "pool_ambiente_id": amb_id,
                    "alvos": [{"tipo": "funcionario", "id": beto_id},
                             {"tipo": "funcionario", "id": caio_id}]})
    assert st == 200, d
    mont = [a for a in d["atribuicoes"] if a["papel"] == "montagem" and a["pool_ambiente_id"] == amb_id]
    assert {a["responsavel_nome"] for a in mont} == {"Beto Montador", "Caio Montador"}
    # substitui o CONJUNTO inteiro (tira o Caio, fica só o Beto)
    st2, d2 = c.post("/api/projetos/Proj_L1/atribuicoes",
                     {"papel": "montagem", "pool_ambiente_id": amb_id,
                      "alvos": [{"tipo": "funcionario", "id": beto_id}]})
    assert st2 == 200
    mont2 = [a for a in d2["atribuicoes"] if a["papel"] == "montagem" and a["pool_ambiente_id"] == amb_id]
    assert len(mont2) == 1 and mont2[0]["responsavel_nome"] == "Beto Montador"
    # PE não aceita "alvos" (só Montagem) -> 400, sem gravar nada
    st3, d3 = c.post("/api/projetos/Proj_L1/atribuicoes",
                     {"papel": "projeto_executivo", "pool_ambiente_id": amb_id,
                      "alvos": [{"tipo": "funcionario", "id": beto_id}]})
    assert st3 == 400 and d3.get("ok") is False
    # limpa (app_db é module-scoped — não vazar pros testes seguintes)
    db = app_db.get_session()
    db.query(app_db.AtribuicaoAmbiente).filter_by(projeto_nome="Proj_L1").delete()
    db.query(app_db.PoolAmbiente).filter_by(projeto_id="Proj_L1").delete()
    db.commit(); db.close()


def test_mapa_so_gerencia_edita(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # consultor
    st, _ = c.post("/api/projetos/Proj_L1/atribuicoes",
                   {"papel": "medicao", "pool_ambiente_id": None, "funcionario_id": 1})
    assert st == 403
    st2, _ = c.get("/api/projetos/Proj_L1/atribuicoes")
    assert st2 == 403


# ── F1.4: enforcement — 404 fora de escopo (§9) ──────────────────────────────────
def test_escopo_consultor_nao_ve_projeto_de_outro(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    b = app_db.Usuario(nome="ConsB", login="consb@loja.com", nivel="operador", loja_id=l1, ativo=1)
    b.set_senha("x"); db.add(b); db.flush()
    db.query(app_db.Projeto).filter_by(nome_safe="Proj_L1").first().criado_por_id = b.id
    db.commit(); db.close()
    # Consultor A (cons_l1) NÃO abre o projeto criado por B (link direto → 404)
    ca = http_client_factory(); ca.login("cons_l1", "senha123")
    assert ca.get("/projetos/Proj_L1")[0] == 404
    # O criador (B) abre o próprio → 200
    cb = http_client_factory(); cb.login("consb@loja.com", "x")
    st, d = cb.get("/projetos/Proj_L1"); assert st == 200 and d.get("ok") is True
    # Gerência+ (diretor) vê tudo na loja → 200
    cg = http_client_factory(); cg.login("dir_l1", "senha123")
    assert cg.get("/projetos/Proj_L1")[0] == 200


def test_escopo_operacional_so_o_atribuido(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    f = app_db.Funcionario(loja_id=l1, nome="PE Paulo", status="ativo"); db.add(f); db.flush()
    u = app_db.Usuario(nome="PE Paulo", login="pe@loja.com", nivel="projetista_executivo",
                       loja_id=l1, ativo=1, funcionario_id=f.id)
    u.set_senha("x"); db.add(u); db.flush()
    f.usuario_id = u.id; db.commit(); fid = f.id; db.close()
    pe = http_client_factory(); pe.login("pe@loja.com", "x")
    # sem atribuição → operacional não vê → 404
    assert pe.get("/projetos/Proj_L1")[0] == 404
    # atribui o funcionário ao projeto (projeto inteiro) e agora vê → 200
    db = app_db.get_session()
    db.add(app_db.AtribuicaoAmbiente(loja_id=l1, projeto_nome="Proj_L1", pool_ambiente_id=None,
                                     papel="projeto_executivo", funcionario_id=fid))
    db.commit(); db.close()
    st, d = pe.get("/projetos/Proj_L1"); assert st == 200 and d.get("ok") is True


def test_escopo_isolamento_loja_intacto(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("cons_l1", "senha123")
    assert c.get("/projetos/Proj_L2")[0] == 404   # F4: outra loja


# ── F1.5: visão do papel (comercial bloqueado ao operacional) + Mapa = responsável default ──
def test_operacional_bloqueado_no_comercial(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    u = app_db.Usuario(nome="Med", login="med@loja.com", nivel="medidor", loja_id=l1, ativo=1)
    u.set_senha("x"); db.add(u); db.commit(); db.close()
    med = http_client_factory(); med.login("med@loja.com", "x")
    st, d = med.post("/api/orcamentos/1/negociacao-preview", {})
    assert st == 403 and "operacional" in (d.get("erro", "").lower())   # §9: Medidor não vê valores
    # consultor NÃO é barrado pelo gate comercial (passa; 404 pois o orçamento não existe)
    c = http_client_factory(); c.login("cons_l1", "senha123")
    assert c.post("/api/orcamentos/1/negociacao-preview", {})[0] != 403


def test_ciclo_responsavel_efetivo_vem_do_mapa(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fpe = app_db.Funcao(loja_id=l1, nome="Projetista Executivo"); db.add(fpe); db.flush()
    func = app_db.Funcionario(loja_id=l1, nome="Paulo PE", funcao_id=fpe.id, status="ativo")
    db.add(func); db.flush()
    db.add(app_db.CicloEtapa(projeto_nome="Proj_L1", etapa_codigo="11", status="pendente"))
    db.add(app_db.AtribuicaoAmbiente(loja_id=l1, projeto_nome="Proj_L1", pool_ambiente_id=None,
                                     papel="projeto_executivo", funcionario_id=func.id))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/projetos/Proj_L1/ciclo")
    assert st == 200
    e11 = next(x for x in d["ciclo"] if x["etapa_codigo"] == "11")
    assert e11["responsavel_efetivo_nome"] == "Paulo PE"   # Mapa é o default da fase
