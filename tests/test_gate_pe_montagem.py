# -*- coding: utf-8 -*-
"""Gate de execução de PE e Montagem/Assistência (fecha o pendente do Orizon Chat, 2026-07-27).

Bloqueador INVERTIDO por LACUNA (função com >1 candidato e ninguém escolhido):
- PE (etapa 11): o upload de documento/conclusão de subfase trava (409) enquanto a função do PE
  estiver em lacuna.
- Montagem/Assistência (17/18): responsável por AMBIENTE no Mapa — `montagem_lacunas` trava só
  quando há >1 candidato de montagem e algum ambiente sem responsável (0/1 candidato não trava)."""
import mod_equipe


def _funcao(app_db, loja_id, nome):
    db = app_db.get_session()
    try:
        f = app_db.Funcao(nome=nome, loja_id=loja_id); db.add(f); db.commit(); return f.id
    finally:
        db.close()


def _func(app_db, loja_id, funcao_id, nome):
    db = app_db.get_session()
    try:
        x = app_db.Funcionario(nome=nome, loja_id=loja_id, funcao_id=funcao_id, status="ativo")
        db.add(x); db.commit(); return x.id
    finally:
        db.close()


def _proj(app_db, loja_id, nome, n_amb=0):
    db = app_db.get_session()
    try:
        db.add(app_db.Projeto(nome_safe=nome, loja_id=loja_id, status="fechado"))
        ids = []
        for i in range(n_amb):
            pa = app_db.PoolAmbiente(projeto_id=nome, nome="A%d" % i, nome_exibicao="Amb %d" % i,
                                     xml_path="x", ambientes_json="[]")
            db.add(pa); db.flush(); ids.append(pa.id)
        db.commit(); return ids
    finally:
        db.close()


def _etapa(app_db, nome, codigo, funcao_id):
    db = app_db.get_session()
    try:
        db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo=codigo, funcao_responsavel_id=funcao_id))
        db.commit()
    finally:
        db.close()


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# ── Montagem/assistência: montagem_lacunas (por ambiente, via Mapa) ──────────────────────────

def test_montagem_sem_candidatos_nao_trava(app_db, seed):
    ids = _proj(app_db, seed["loja1_id"], "GM_a", n_amb=2)
    db = app_db.get_session()
    try:   # nenhum montador cadastrado → 0 candidatos → não trava (retrocompatível)
        assert mod_equipe.montagem_lacunas(db, seed["loja1_id"], "montagem", [], ids) == []
    finally:
        db.close()


def test_montagem_dois_candidatos_sem_mapa_trava(app_db, seed):
    ids = _proj(app_db, seed["loja1_id"], "GM_b", n_amb=2)
    fm = _funcao(app_db, seed["loja1_id"], "Montador")
    _func(app_db, seed["loja1_id"], fm, "Montador 1"); _func(app_db, seed["loja1_id"], fm, "Montador 2")
    db = app_db.get_session()
    try:   # >1 candidato e nenhum ambiente com responsável no Mapa → lacuna nos dois
        assert sorted(mod_equipe.montagem_lacunas(db, seed["loja1_id"], "montagem", [], ids)) == sorted(ids)
        # atribuição PROJETO-INTEIRO (pool_ambiente_id=None) cobre todos → sem lacuna
        atrib_geral = [{"papel": "montagem", "pool_ambiente_id": None, "funcionario_id": 1, "terceiro_id": None}]
        assert mod_equipe.montagem_lacunas(db, seed["loja1_id"], "montagem", atrib_geral, ids) == []
        # atribuição só do 1º ambiente → o 2º fica em lacuna
        atrib_1 = [{"papel": "montagem", "pool_ambiente_id": ids[0], "funcionario_id": 1, "terceiro_id": None}]
        assert mod_equipe.montagem_lacunas(db, seed["loja1_id"], "montagem", atrib_1, ids) == [ids[1]]
    finally:
        db.close()


# ── PE (etapa 11): gate no upload de documento de subfase ────────────────────────────────────

def test_pe_documento_barrado_por_lacuna(http_client_factory, app_db, seed):
    _proj(app_db, seed["loja1_id"], "GPE_a")
    fpe = _funcao(app_db, seed["loja1_id"], "Projetista Executivo")
    _func(app_db, seed["loja1_id"], fpe, "PE 1"); _func(app_db, seed["loja1_id"], fpe, "PE 2")   # 2 candidatos = lacuna
    _etapa(app_db, "GPE_a", "11", fpe)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post_multipart("/api/projetos/GPE_a/ciclo/11a/documento",
                             files={"arquivo": ("p.pdf", b"x")}, fields={})
    assert st == 409 and "responsável" in (b.get("erro") or "").lower()


def test_pe_documento_liberado_com_um_candidato(http_client_factory, app_db, seed):
    _proj(app_db, seed["loja1_id"], "GPE_b")
    fpe = _funcao(app_db, seed["loja1_id"], "Projetista Executivo")
    _func(app_db, seed["loja1_id"], fpe, "PE único")   # 1 candidato = auto → gate NÃO barra
    _etapa(app_db, "GPE_b", "11", fpe)
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post_multipart("/api/projetos/GPE_b/ciclo/11a/documento",
                             files={"arquivo": ("p.pdf", b"x")}, fields={})
    assert st != 409   # passou do gate (para em outra validação, não no bloqueador de responsável)
