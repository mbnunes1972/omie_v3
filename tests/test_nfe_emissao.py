import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from fiscal import nfe_emissao
from integracoes.emissor_fiscal import resultado_de_focus, StatusNota


class FakeClient:
    def __init__(self): self.baixados = []
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH123", "numero": "10", "serie": "1",
                "caminho_xml_nota_fiscal": "/nfe/xml.xml", "caminho_danfe": "/nfe/danfe.pdf"}
    def baixar(self, caminho):
        self.baixados.append(caminho)
        return b"BYTES:" + caminho.encode()


class FakeEmissor:
    def __init__(self, status="processando_autorizacao", erros=None):
        self.client = FakeClient(); self._status = status; self._erros = erros; self.emit_calls = 0
        self.nota_recebida = None
    def emitir_nfe_produto(self, nota):
        self.nota_recebida = nota
        self.emit_calls += 1
        d = {"ref": nota["ref"], "status": self._status}
        if self._erros: d["erros"] = self._erros
        return resultado_de_focus(d)
    def consultar_status(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CH",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})
    def cancelar(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


class FakeClientNfse:
    def __init__(self): self.baixados = []
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CHS1", "numero": "5", "serie": "1",
                "caminho_xml_nota_fiscal": "/nfse/xml.xml", "url": "/nfse/nota.pdf"}
    def baixar(self, caminho):
        self.baixados.append(caminho)
        return b"BYTES:" + caminho.encode()


class FakeEmissorNfse:
    """Emissor de NFS-e: espelha o de produto mas usa emitir_nfse_servico/consultar_status_nfse/cancelar_nfse."""
    def __init__(self, status="processando_autorizacao"):
        self.client = FakeClientNfse(); self._status = status; self.emit_calls = 0
        self.nota_recebida = None
    def emitir_nfse_servico(self, nota):
        self.nota_recebida = nota
        self.emit_calls += 1
        return resultado_de_focus({"ref": nota["ref"], "status": self._status})
    def consultar_status_nfse(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CHS",
                                   "caminho_xml_nota_fiscal": "/x.xml", "url": "/nota.pdf"})
    def cancelar_nfse(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


def _nota_nfse(ref):
    return {"ref": ref, "data_emissao": "D",
            "prestador": {"cnpj": "1", "inscricao_municipal": "IM", "codigo_municipio": "3549904",
                          "razao_social": "L"},
            "tomador": {"doc_tipo": "cpf", "doc": "2", "razao_social": "C", "logradouro": "a",
                        "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "servico": {"valor_servicos": 100.0, "aliquota": 2.0, "discriminacao": "Montagem",
                        "iss_retido": False, "item_lista_servico": "14.06",
                        "codigo_tributario_municipio": "3101"}}


def _nota(ref):
    return {"ref": ref, "natureza_operacao": "Venda", "data_emissao": "D",
            "emitente": {"doc_tipo": "cnpj", "doc": "1", "nome": "L", "regime": 1, "ie": "1",
                         "logradouro": "a", "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "destinatario": {"nome": "C", "doc_tipo": "cpf", "doc": "2", "logradouro": "a", "numero": "1",
                             "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "fiscal": {"csosn": "101", "cfop_dentro": "5102", "cfop_fora": "6102", "pis_cst": "49", "cofins_cst": "49"},
            "itens": [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN", "qCom": 1.0, "preco_venda_unit": 10.0}]}


def _reset(app_db, ref, proj):
    db = app_db.get_session()
    # xml_doc_id/danfe_doc_id/fabrica_doc_id são FK reais (ciclo_documentos.id) — antes de apagar
    # os ciclo_documentos da etapa 15, limpa qualquer documento_fiscal (de QUALQUER ref, não só o
    # desta chamada) que ainda aponte pra eles por QUALQUER uma das três colunas, senão o DELETE de
    # ciclo_documentos viola FK e aborta a transação (Postgres valida; SQLite não), deixando a
    # sessão pendurada (idle in transaction) e travando o próximo módulo.
    DF = app_db.DocumentoFiscal
    cdoc_ids = [r[0] for r in db.query(app_db.CicloDocumento.id)
                  .filter_by(projeto_nome=proj, etapa_codigo="15").all()]
    if cdoc_ids:
        (db.query(DF)
           .filter(DF.xml_doc_id.in_(cdoc_ids) | DF.danfe_doc_id.in_(cdoc_ids)
                   | DF.fabrica_doc_id.in_(cdoc_ids))
           .delete(synchronize_session=False))
    db.query(DF).filter_by(ref=ref).delete()
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    db.commit(); db.close()


def _perfil(app_db, loja_id, ambiente="homologacao"):
    """Garante o Emitente da loja (o do seed) com o ambiente pedido; devolve seu id.
    A emissão agora lê o Emitente (não o PerfilFiscal)."""
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id)
    em.ambiente_ativo = ambiente
    db.commit()
    eid = em.id
    db.close()
    return eid


def test_emitir_autoriza_guarda_docs(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-1", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-1"), emitente_id=eid, emissor=fake)
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CH123"
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-1").first()
    assert reg.status == "autorizado" and reg.xml_doc_id and reg.danfe_doc_id
    docs = db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").all()
    assert {d.tipo for d in docs} == {"nfe_loja_xml", "nfe_loja_danfe"}
    assert fake.client.baixados == ["/nfe/xml.xml", "/nfe/danfe.pdf"]
    db.close()


def test_emitir_idempotente(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-2", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emitente_id=eid, emissor=fake)
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emitente_id=eid, emissor=fake)
    assert fake.emit_calls == 1
    db.close()


def test_emitir_guarda_producao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-3", proj); eid = _perfil(app_db, lid, "producao")
    db = app_db.get_session()
    with pytest.raises(ValueError):
        nfe_emissao.emitir(db, lid, proj, _nota("R-3"), emitente_id=eid, emissor=FakeEmissor())
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-3"), emitente_id=eid,
                             permitir_producao=True, emissor=FakeEmissor())
    assert res.status == StatusNota.AUTORIZADO
    db.close()


def test_emitir_erro_autorizacao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-4", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor(status="erro_autorizacao", erros=[{"codigo": "215", "mensagem": "falha"}])
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-4"), emitente_id=eid, emissor=fake)
    assert res.status == StatusNota.ERRO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-4").first()
    assert reg.status == "erro" and reg.erros_json and not reg.xml_doc_id
    db.close()


def test_consultar_atualiza_registro(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-5", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="R-5", projeto_nome=proj, loja_id=lid, emitente_id=eid, status="processando"))
    db.commit()
    res = nfe_emissao.consultar(db, "R-5", emissor=FakeEmissor())
    assert res.status == StatusNota.AUTORIZADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-5").first()
    assert reg.status == "autorizado" and reg.xml_doc_id       # baixou docs ao autorizar
    db.close()


def test_cancelar_atualiza_registro(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-6", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="R-6", projeto_nome=proj, loja_id=lid, emitente_id=eid, status="autorizado"))
    db.commit()
    res = nfe_emissao.cancelar(db, "R-6", "cancelamento por erro de digitacao", emissor=FakeEmissor())
    assert res.status == StatusNota.CANCELADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-6").first()
    assert reg.status == "cancelado"
    db.close()


def test_cancelar_preserva_chave_numero_serie(app_db, seed, projetos_dir):
    """Achado Vera 2026-08-12: a resposta de CANCELAMENTO da Focus não devolve chave/numero/serie
    (só status+mensagem) — `_aplicar_resultado` sobrescrevia incondicionalmente com None, apagando
    a rastreabilidade de qual NF-e foi cancelada."""
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-6b", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="R-6b", projeto_nome=proj, loja_id=lid, emitente_id=eid,
                                  status="autorizado", chave_nfe="CH123", numero="10", serie="1"))
    db.commit()
    res = nfe_emissao.cancelar(db, "R-6b", "cancelamento por erro de digitacao", emissor=FakeEmissor())
    assert res.status == StatusNota.CANCELADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-6b").first()
    assert reg.status == "cancelado"
    assert reg.chave_nfe == "CH123" and reg.numero == "10" and reg.serie == "1"
    db.close()


def test_consultar_resolve_emissor_pelo_emitente_id(app_db, seed, projetos_dir, monkeypatch):
    # o switch reg.loja_id -> reg.emitente_id: consultar SEM emissor injetado resolve pelo emitente do documento
    # emitente_id é FK real (emitente.id) — usa o emitente da OUTRA loja (seed) em vez de um literal
    # fabricado (Postgres valida FK; SQLite não), provando que resolve pelo emitente do documento
    # e não pelo da loja (emitente_l1_id != emitente da loja2).
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]; outro_emitente_id = seed["emitente_l1_id"]
    _reset(app_db, "R-7", proj)
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="R-7", projeto_nome=proj, loja_id=lid,
                                  emitente_id=outro_emitente_id, status="processando"))
    db.commit()
    capturado = {}
    def _fake_emissor_para(_db, emitente_id):
        capturado["eid"] = emitente_id
        return FakeEmissor()
    monkeypatch.setattr(nfe_emissao, "_emissor_para", _fake_emissor_para)
    nfe_emissao.consultar(db, "R-7")
    assert capturado["eid"] == outro_emitente_id   # resolveu pelo emitente do documento, não pela loja
    db.close()


def test_consultar_ref_inexistente(app_db, seed, projetos_dir):
    db = app_db.get_session()
    with pytest.raises(ValueError):
        nfe_emissao.consultar(db, "NAO-EXISTE", emissor=FakeEmissor())
    db.close()


def test_emitir_grava_fabrica_doc_id(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F1", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    # fabrica_doc_id é FK real (ciclo_documentos.id) — cria a linha de verdade em vez de um
    # literal fabricado (Postgres valida FK; SQLite não).
    cdoc = app_db.CicloDocumento(projeto_nome=proj, etapa_codigo="15", tipo="doc_fabrica",
                                 arquivo_path="fabrica/doc.pdf", nome_original="doc.pdf")
    db.add(cdoc); db.flush()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F1"), emitente_id=eid, emissor=FakeEmissor(),
                       fabrica_doc_id=cdoc.id)
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-F1").first()
    assert reg.fabrica_doc_id == cdoc.id and reg.emitente_id == eid
    db.close()


def test_emitir_homologacao_forca_nome_dest_sefaz(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F2", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F2"), emitente_id=eid, emissor=fake)
    assert fake.nota_recebida["destinatario"]["nome"] == \
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    db.close()


def test_emitir_producao_nao_forca_nome_dest(app_db, seed, projetos_dir):
    # regra SEFAZ só vale em homologação: em produção o nome do destinatário é preservado
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F3", proj); eid = _perfil(app_db, lid, "producao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F3"), emitente_id=eid,
                       permitir_producao=True, emissor=fake)
    assert fake.nota_recebida["destinatario"]["nome"] == "C"
    db.close()


# ------------------------------------------------------------------------------------------------
# NFS-e de serviço: emitir ramifica por tipo_documento="servico" (caminho aditivo, produto intacto)
# ------------------------------------------------------------------------------------------------

def test_emitir_servico_autoriza_guarda_docs(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-1", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissorNfse()
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota_nfse("S-1"), tipo_documento="servico",
                             emitente_id=eid, emissor=fake)
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CHS1"
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="S-1").first()
    assert reg.tipo_documento == "servico" and reg.status == "autorizado"
    assert reg.xml_doc_id and reg.danfe_doc_id
    docs = db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").all()
    assert {d.tipo for d in docs} == {"nfse_loja_xml", "nfse_loja_pdf"}
    assert fake.client.baixados == ["/nfse/xml.xml", "/nfse/nota.pdf"]
    db.close()


def test_emitir_servico_nao_carimba_nome_dest(app_db, seed, projetos_dir):
    # a NFS-e não tem `destinatario`; o carimbo SEFAZ de homologação (regra do NF-e) não se aplica.
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-2", proj); eid = _perfil(app_db, lid, "homologacao")
    fake = FakeEmissorNfse()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota_nfse("S-2"), tipo_documento="servico",
                       emitente_id=eid, emissor=fake)
    assert "destinatario" not in fake.nota_recebida     # nota NFS-e intacta, sem carimbo
    db.close()


def test_consultar_servico_usa_caminho_nfse(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-3", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="S-3", projeto_nome=proj, loja_id=lid, emitente_id=eid,
                                  tipo_documento="servico", status="processando"))
    db.commit()
    res = nfe_emissao.consultar(db, "S-3", emissor=FakeEmissorNfse())
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CHS"
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="S-3").first()
    assert reg.status == "autorizado" and reg.xml_doc_id
    db.close()


def test_cancelar_servico_usa_caminho_nfse(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "S-4", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="S-4", projeto_nome=proj, loja_id=lid, emitente_id=eid,
                                  tipo_documento="servico", status="autorizado"))
    db.commit()
    res = nfe_emissao.cancelar(db, "S-4", "cancelamento por erro de digitacao", emissor=FakeEmissorNfse())
    assert res.status == StatusNota.CANCELADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="S-4").first()
    assert reg.status == "cancelado"
    db.close()


class _FakeClientBaixaFalha(FakeClient):
    def baixar(self, caminho):
        raise RuntimeError("rede caiu ao baixar XML")


class _FakeEmissorBaixaFalha(FakeEmissor):
    def __init__(self):
        super().__init__(); self.client = _FakeClientBaixaFalha()


def test_emitir_autorizado_persiste_mesmo_se_baixa_falha(app_db, seed, projetos_dir):
    """Auditoria A9: se a baixa de XML/DANFE falhar, a nota JÁ autorizada não é desfeita;
    `consultar` rebaixa os documentos depois."""
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-A9", proj); eid = _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-A9"), emitente_id=eid, emissor=_FakeEmissorBaixaFalha())
    assert res.status == StatusNota.AUTORIZADO
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="R-A9").first()
    assert reg is not None and reg.status == "autorizado"        # a nota NÃO se perdeu
    assert reg.xml_doc_id is None and reg.danfe_doc_id is None    # a baixa falhou
    db.close()
    # consultar (com cliente que baixa OK) recupera os documentos
    db2 = app_db.get_session()
    nfe_emissao.consultar(db2, "R-A9", emissor=FakeEmissor())
    reg2 = db2.query(app_db.DocumentoFiscal).filter_by(ref="R-A9").first()
    assert reg2.xml_doc_id and reg2.danfe_doc_id
    db2.close()


def test_emitir_corrida_ref_idempotente(app_db, seed, projetos_dir):
    """Auditoria A13: se outro request gravar o mesmo ref durante a emissão, o 2º devolve o
    registro vencedor de forma idempotente (não 500 / não duplica)."""
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-RACE", proj); eid = _perfil(app_db, lid, "homologacao")

    class _RaceEmissor(FakeEmissor):
        def emitir_nfe_produto(self, nota):
            # simula um request concorrente que grava o mesmo ref primeiro
            db2 = app_db.get_session()
            db2.add(app_db.DocumentoFiscal(ref="R-RACE", projeto_nome=proj, loja_id=lid,
                                           etapa_codigo="15", tipo_documento="produto",
                                           emitente_id=eid, status="autorizado", chave_nfe="WIN"))
            db2.commit(); db2.close()
            return super().emitir_nfe_produto(nota)

    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-RACE"), emitente_id=eid, emissor=_RaceEmissor())
    assert res.status == StatusNota.AUTORIZADO and res.chave == "WIN"     # idempotente, devolve o vencedor
    n = db.query(app_db.DocumentoFiscal).filter_by(ref="R-RACE").count()
    assert n == 1                                                          # não duplicou
    db.close()
