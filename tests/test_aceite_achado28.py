"""ACHADO-28 (docs/db/ACHADOS_CONTABEIS.md) — CPF de assinatura sem validação de dígito.

`validacao_doc.erro_doc` passa a ser chamado dentro de `_registrar_assinatura_contrato`,
`_registrar_assinatura_aprovacao_pe` e `_registrar_assinatura_solicitacao_medicao` — por estar
DENTRO dessas três funções compartilhadas (não em cada chamador), a guarda cobre de graça os dois
gatilhos de cada uma: o endpoint síncrono de assinatura interna E o webhook/reconciliação
ClickSign (onde o CPF vem de fora, da própria ClickSign). Só dígito verificador — conferir contra
o cadastro é decisão do Marcelo, fica pro próximo ciclo (docs/db/LISTA_PARALELA.md).

Três aceites por caminho (contrato, aprovação do PE, solicitação de medição): CPF
estruturalmente inválido é recusado (400, mensagem nomeando a parte); CPF válido passa —
controle positivo, sem o qual uma guarda que recusasse SEMPRE passaria no primeiro aceite."""
from datetime import datetime

from database import Contrato, ContratoAssinatura, AprovacaoPE, SolicitacaoMedicao


CPF_INVALIDO = "111.111.111-11"      # dígito verificador não confere
CPF_VALIDO   = "111.444.777-35"      # CPF de teste válido, usado em toda a suíte


# ── Caminho 1 — Contrato ─────────────────────────────────────────────────────────────────────

def _prep_contrato(app_db, seed):
    """1ª assinatura (loja) já registrada + datas do cronograma válidas — pronto pra 2ª
    assinatura (cliente) via /api/projetos/<nome>/contrato/assinar."""
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    p = db.get(app_db.Projeto, nome)
    p.previsao_medicao = datetime(2028, 1, 1)
    p.data_entrega = datetime(2028, 1, 10)
    p.folga_autorizada = 1
    ct = db.get(Contrato, cid); ct.status = "assinado_loja"
    ct.assinatura_canal = "interno"
    db.query(ContratoAssinatura).filter_by(contrato_id=cid).delete()
    db.add(ContratoAssinatura(contrato_id=cid, parte="loja", nome="Loja", cpf=CPF_VALIDO,
                              assinado_em=datetime.utcnow(), hash_sha256="x" * 64))
    db.commit(); db.close()
    return nome


def test_contrato_recusa_cpf_invalido(app_db, seed, http_client_factory):
    nome = _prep_contrato(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_INVALIDO})
    assert st == 400, (st, d)
    assert "cpf" in d.get("erro", "").lower() and "cliente" in d.get("erro", "").lower(), d
    db = app_db.get_session()
    ct = db.get(Contrato, seed["contrato_l1_id"]); db.close()
    assert ct.status == "assinado_loja", "não pode ter avançado com CPF inválido"


def test_contrato_aceita_cpf_valido(app_db, seed, http_client_factory):
    """Controle positivo: sem ele, uma guarda que recusasse SEMPRE passaria no aceite acima."""
    nome = _prep_contrato(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_VALIDO})
    assert st == 200 and d.get("ok"), (st, d)
    assert d["status"] == "assinado"


# ── Caminho 2 — Aprovação do PE ──────────────────────────────────────────────────────────────

def _prep_aprovacao_pe(app_db, seed, tmp_path):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    pdf = tmp_path / "aprovacao_pe.pdf"
    pdf.write_bytes(b"%PDF-fake")
    ap = AprovacaoPE(projeto_nome=nome, contrato_id=seed["contrato_l1_id"],
                     status="para_assinatura", pdf_path=str(pdf), assinatura_canal="interno")
    db.add(ap); db.commit()
    db.close()
    return nome


def test_aprovacao_pe_recusa_cpf_invalido(app_db, seed, http_client_factory, tmp_path):
    nome = _prep_aprovacao_pe(app_db, seed, tmp_path)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/aprovacao-pe/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": CPF_INVALIDO})
    assert st == 400, (st, d)
    assert "cpf" in d.get("erro", "").lower() and "loja" in d.get("erro", "").lower(), d
    db = app_db.get_session()
    ap = db.query(AprovacaoPE).filter_by(projeto_nome=nome).order_by(AprovacaoPE.id.desc()).first()
    db.close()
    assert ap.status == "para_assinatura", "não pode ter avançado com CPF inválido"


def test_aprovacao_pe_aceita_cpf_valido(app_db, seed, http_client_factory, tmp_path):
    nome = _prep_aprovacao_pe(app_db, seed, tmp_path)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/aprovacao-pe/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": CPF_VALIDO})
    assert st == 200 and d.get("ok"), (st, d)
    assert d["status"] == "assinado_loja"


# ── Caminho 3 — Solicitação de Medição ───────────────────────────────────────────────────────

def _prep_solicitacao_medicao(app_db, seed, tmp_path):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    db.get(Contrato, seed["contrato_l1_id"]).status = "assinado"
    for sol in db.query(SolicitacaoMedicao).filter_by(projeto_nome=nome).all():
        for a in list(sol.assinaturas):
            db.delete(a)
        db.delete(sol)
    pdf = tmp_path / "solicitacao_medicao.pdf"
    pdf.write_bytes(b"%PDF-fake")
    sol = SolicitacaoMedicao(projeto_nome=nome, loja_id=seed["loja1_id"],
                             status="para_assinatura", pdf_path=str(pdf), assinatura_canal="interno")
    db.add(sol); db.commit()
    db.close()
    return nome


def test_solicitacao_medicao_recusa_cpf_invalido(app_db, seed, http_client_factory, tmp_path):
    nome = _prep_solicitacao_medicao(app_db, seed, tmp_path)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/medicao/solicitacao/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": CPF_INVALIDO})
    assert st == 400, (st, d)
    assert "cpf" in d.get("erro", "").lower() and "loja" in d.get("erro", "").lower(), d
    db = app_db.get_session()
    sol = (db.query(SolicitacaoMedicao).filter_by(projeto_nome=nome)
             .order_by(SolicitacaoMedicao.id.desc()).first())
    db.close()
    assert sol.status == "para_assinatura", "não pode ter avançado com CPF inválido"


def test_solicitacao_medicao_aceita_cpf_valido(app_db, seed, http_client_factory, tmp_path):
    nome = _prep_solicitacao_medicao(app_db, seed, tmp_path)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/medicao/solicitacao/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": CPF_VALIDO})
    assert st == 200 and d.get("ok"), (st, d)
    assert d["status"] == "assinado_loja"
