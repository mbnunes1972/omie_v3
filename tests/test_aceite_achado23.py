"""docs/db/TAREFA_ACHADO23.md, Passo 11 do ROTEIRO — os aceites do ACHADO-23.

O ACHADO-23 nasceu de uma medição, nunca teve teste — o único achado da Fase 1 que quase passou
despercebido no fechamento. Conserto: a assinatura completa SEMPRE (não trava a venda com o
cliente na frente); a segmentação Mercadoria × Serviço não-congelada vira condição da Aprovação
Financeira I (AF1, etapa "8") — que tenta congelar ali mesmo (reparo) e só recusa se o reparo
também falhar.

As falhas de congelamento são FORÇADAS POR INJEÇÃO (monkeypatch de
`main._congelar_segmentacao_no_projeto`), não descobertas por acaso — e cada aceite confere que a
falha é pelo motivo certo (a mensagem nomeia o projeto), não um erro de setup."""
from datetime import datetime

from database import Projeto, Contrato, ContratoAssinatura, CicloEtapa
import main


def _prep_af1(app_db, seed, nome, *, segmentacao_congelada):
    """Estado mínimo pra tentar concluir a etapa 8 (AF1): etapa 7 concluída, contrato assinado,
    data de entrega definida — os outros gates da AF1 (docs/db/TAREFA_ACHADO18... não, ver
    test_af_gate_data_entrega.py) já satisfeitos, então só a segmentação está em jogo.
    `segmentacao_congelada=False` simula a assinatura que NUNCA passou pelo congelamento (bypassa
    o fluxo HTTP de assinatura de propósito — é o estado que uma falha silenciosa deixaria)."""
    db = app_db.get_session()
    try:
        p = db.get(Projeto, nome)
        p.data_entrega = datetime(2028, 1, 1)
        if segmentacao_congelada:
            import json
            par = json.loads(p.parametros_json) if p.parametros_json else {}
            par["pct_mercadoria"] = 65.0; par["pct_servico"] = 35.0
            par["segmentacao_congelada"] = True
            p.parametros_json = json.dumps(par)
        else:
            p.parametros_json = None
        cid = seed["contrato_l1_id"]
        db.get(Contrato, cid).status = "assinado"
        e7 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="7").first()
        if not e7:
            e7 = CicloEtapa(projeto_nome=nome, etapa_codigo="7"); db.add(e7)
        e7.status = "concluido"
        e8 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="8").first()
        if e8:
            e8.status = "pendente"; e8.concluido_em = None
        db.commit()
    finally:
        db.close()


def _patch_af1(c, nome):
    return c.patch("/api/projetos/%s/ciclo/8" % nome,
                   {"status": "concluido", "login": "dir_l1", "senha": "senha123"})


def _segmentacao_congelada_no_banco(app_db, nome):
    import json
    db = app_db.get_session()
    p = db.get(Projeto, nome)
    par = json.loads(p.parametros_json) if p.parametros_json else {}
    db.close()
    return bool(par.get("segmentacao_congelada"))


# ── Aceite 1 — congelamento falhou → AF1 recusa, com a razão nomeada ────────────────────────────

def test_af1_recusa_quando_congelamento_falha_por_injecao(app_db, seed, http_client_factory, monkeypatch):
    nome = seed["projeto_l1"]
    _prep_af1(app_db, seed, nome, segmentacao_congelada=False)

    # força a falha por injeção — não espera encontrá-la sozinha.
    def _falha(db, loja_id, projeto_nome):
        raise RuntimeError("injeção do aceite — loja sem config financeira")
    monkeypatch.setattr(main, "_congelar_segmentacao_no_projeto", _falha)

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af1(c, nome)

    assert st == 400, (st, d)
    # falha pelo motivo certo: nomeia o projeto, não é erro de setup (data/contrato/senha).
    assert nome in d.get("erro", ""), d
    assert "segmenta" in d.get("erro", "").lower(), d
    db = app_db.get_session()
    e8 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="8").first()
    db.close()
    assert e8 is None or e8.status != "concluido", "AF1 não deveria ter concluído"


# ── Aceite 2 — a AF1 congela e passa a aprovar (o caminho de reparo funciona) ───────────────────

def test_af1_congela_e_aprova_quando_congelamento_estava_pendente(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _prep_af1(app_db, seed, nome, segmentacao_congelada=False)
    assert not _segmentacao_congelada_no_banco(app_db, nome), "pré-condição: ainda não congelada"

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af1(c, nome)

    assert st == 200 and d.get("ok"), (st, d)
    assert d["status"] == "concluido"
    assert _segmentacao_congelada_no_banco(app_db, nome), (
        "AF1 deveria ter congelado a segmentação como reparo, ali mesmo")


# ── Aceite 3 — controle positivo: congelamento normal → AF1 aprova sem ruído ────────────────────

def test_af1_aprova_sem_ruido_quando_ja_congelada(app_db, seed, http_client_factory, monkeypatch):
    """Sem este controle positivo, uma AF1 que recusasse SEMPRE passaria nos outros dois aceites
    (o 1 quer recusa, o 2 só olha se o resultado final está congelado). Aqui a segmentação já
    chegou congelada (assinatura normal) — se `_congelar_segmentacao_no_projeto` for chamado de
    novo, o teste falha (não deveria precisar recongelar o que já está certo)."""
    nome = seed["projeto_l1"]
    _prep_af1(app_db, seed, nome, segmentacao_congelada=True)

    chamadas = []
    original = main._congelar_segmentacao_no_projeto
    def _rastreado(db, loja_id, projeto_nome):
        chamadas.append(projeto_nome)
        return original(db, loja_id, projeto_nome)
    monkeypatch.setattr(main, "_congelar_segmentacao_no_projeto", _rastreado)

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af1(c, nome)

    assert st == 200 and d.get("ok"), (st, d)
    assert d["status"] == "concluido"
    assert chamadas == [], "segmentação já estava congelada — não deveria tentar recongelar"


# ── Aceite 4 — a assinatura completa nos dois casos (não trava a venda) ─────────────────────────

def _prep_assinatura(app_db, seed):
    """Contrato com 1ª assinatura (loja) + datas válidas — pronto pra 2ª assinatura (cliente),
    que é o gatilho do congelamento (mesmo padrão de test_af_gate_data_entrega.py)."""
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    p = db.get(Projeto, nome)
    p.previsao_medicao = datetime(2028, 1, 1)
    p.data_entrega = datetime(2028, 1, 10)
    p.folga_autorizada = 1
    p.data_limite_contratual = None
    ct = db.get(Contrato, cid); ct.status = "assinado_loja"
    db.query(ContratoAssinatura).filter_by(contrato_id=cid).delete()
    db.add(ContratoAssinatura(contrato_id=cid, parte="loja", nome="L", cpf="00000000000",
                              assinado_em=datetime.utcnow(), hash_sha256="x" * 64))
    db.commit(); db.close()
    return nome


def test_assinatura_completa_mesmo_com_congelamento_falhando(app_db, seed, http_client_factory, monkeypatch):
    nome = _prep_assinatura(app_db, seed)

    def _falha(db, loja_id, projeto_nome):
        raise RuntimeError("injeção do aceite — congelamento indisponível")
    monkeypatch.setattr(main, "_congelar_segmentacao_no_projeto", _falha)

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "11111111111"})

    assert st == 200 and d.get("ok"), (
        "a assinatura não pode travar por causa do congelamento — %r" % (d,))
    db = app_db.get_session()
    ct = db.get(Contrato, seed["contrato_l1_id"])
    e7 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="7").first()
    db.close()
    assert ct.status == "assinado"
    assert e7 is not None and e7.status == "concluido"


def test_assinatura_completa_e_congela_no_caminho_normal(app_db, seed, http_client_factory):
    """Espelho do teste acima, sem injeção — confirma que o caminho normal da assinatura ainda
    congela de verdade (não regrediu ao consertar o ACHADO-23)."""
    nome = _prep_assinatura(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "11111111111"})
    assert st == 200 and d.get("ok"), d
    assert _segmentacao_congelada_no_banco(app_db, nome)
