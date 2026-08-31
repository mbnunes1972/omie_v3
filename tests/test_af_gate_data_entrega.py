"""Gate independente da sequência (bug de teste manual): a AF (etapa 8/11d) só FECHA quando a data de
entrega está DEFINIDA **e** o contrato está totalmente assinado. Cobre o furo em que um projeto assinado
ANTES do gate da assinatura (data_entrega) chegava à AF sem a data — a trava vivia só na assinatura."""
from datetime import datetime

from database import Projeto, Contrato, CicloEtapa


def _prep(app_db, nome, *, data_entrega, contrato_status, contrato_id):
    """Estado mínimo p/ tentar concluir a etapa 8: etapa 7 concluída (pode_avancar), contrato num
    status dado e data_entrega dada. Cada teste fixa o estado COMPLETO → independe da ordem."""
    db = app_db.get_session()
    try:
        db.get(Projeto, nome).data_entrega = data_entrega
        db.get(Contrato, contrato_id).status = contrato_status
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


def _patch_af(c, nome):
    return c.patch("/api/projetos/%s/ciclo/8" % nome,
                   {"status": "concluido", "login": "dir_l1", "senha": "senha123"})


def test_af_bloqueia_sem_data_entrega(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _prep(app_db, nome, data_entrega=None, contrato_status="assinado",
          contrato_id=seed["contrato_l1_id"])
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af(c, nome)
    assert st == 400, (st, d)
    assert "data de entrega" in (d.get("erro", "").lower()), d


def test_af_bloqueia_contrato_nao_assinado(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _prep(app_db, nome, data_entrega=datetime(2028, 1, 1), contrato_status="para_assinatura",
          contrato_id=seed["contrato_l1_id"])
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af(c, nome)
    assert st == 400, (st, d)
    assert "contrato" in (d.get("erro", "").lower()), d


def test_af_fecha_com_data_e_contrato_assinado(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _prep(app_db, nome, data_entrega=datetime(2028, 1, 1), contrato_status="assinado",
          contrato_id=seed["contrato_l1_id"])
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af(c, nome)
    assert st == 200 and d["ok"], (st, d)
    assert d["status"] == "concluido"


def test_assinatura_exige_previsao_medicao(app_db, seed, http_client_factory):
    from database import Projeto, Contrato, ContratoAssinatura
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    db.get(Projeto, nome).data_entrega = datetime(2028, 1, 1)
    db.get(Projeto, nome).previsao_medicao = None                 # falta a medição
    ct = db.get(Contrato, cid); ct.status = "assinado_loja"
    db.add(ContratoAssinatura(contrato_id=cid, parte="loja", nome="L", cpf="00000000000",
                              assinado_em=datetime.utcnow(), hash_sha256="x" * 64))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "11144477735"})
    assert st == 400 and "medição" in (d.get("erro", "").lower()), (st, d)


def _prep_assinatura_folga(app_db, seed, *, folga_autorizada):
    """Contrato com 1ª assinatura (loja) + datas com FOLGA NEGATIVA (entrega logo após a medição).
    folga_autorizada controla se a data foi registrada sob autorização gerencial."""
    from database import Projeto, Contrato, ContratoAssinatura
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    p = db.get(Projeto, nome)
    p.previsao_medicao = datetime(2028, 1, 1)
    p.data_entrega     = datetime(2028, 1, 10)   # 9 dias < ~50 do padrão → folga negativa
    p.folga_autorizada = folga_autorizada
    p.data_limite_contratual = None
    ct = db.get(Contrato, cid); ct.status = "assinado_loja"
    db.query(ContratoAssinatura).filter_by(contrato_id=cid).delete()   # isolamento: limpa assinaturas de testes anteriores
    db.add(ContratoAssinatura(contrato_id=cid, parte="loja", nome="L", cpf="00000000000",
                              assinado_em=datetime.utcnow(), hash_sha256="x" * 64))
    db.commit(); db.close()
    return nome


def test_assinatura_bloqueia_folga_negativa_nao_autorizada(app_db, seed, http_client_factory):
    nome = _prep_assinatura_folga(app_db, seed, folga_autorizada=0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "11144477735"})
    assert st == 400 and "folga" in (d.get("erro", "").lower()), (st, d)


def test_assinatura_permite_folga_negativa_autorizada(app_db, seed, http_client_factory):
    nome = _prep_assinatura_folga(app_db, seed, folga_autorizada=1)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "11144477735"})
    assert st == 200 and d.get("ok"), (st, d)


def test_assinatura_registra_data_limite_contratual(app_db, seed, http_client_factory):
    """Ao completar a assinatura (D0), o sistema registra a Data-limite do Contrato = D0 + prazo em dias úteis."""
    from database import Projeto
    nome = _prep_assinatura_folga(app_db, seed, folga_autorizada=1)   # datas válidas + loja já assinada
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "11144477735"})
    assert st == 200 and d.get("ok"), (st, d)
    db = app_db.get_session()
    p = db.get(Projeto, nome)
    assert p.data_limite_contratual is not None, "data-limite deve ser registrada na assinatura"
    assert p.data_limite_contratual.weekday() < 5, "data-limite cai em dia útil (seg-sex)"
    db.close()


def test_assinatura_primeira_exige_datas(app_db, seed, http_client_factory):
    """A trava vale desde a PRIMEIRA assinatura (loja), não só na que completa o contrato."""
    from database import Projeto, Contrato, ContratoAssinatura
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    p = db.get(Projeto, nome); p.data_entrega = None; p.previsao_medicao = None
    ct = db.get(Contrato, cid); ct.status = "para_assinatura"
    db.query(ContratoAssinatura).filter_by(contrato_id=cid).delete()   # sem assinaturas ainda
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": "00000000000"})
    assert st == 400 and "entrega" in (d.get("erro", "").lower()), (st, d)
