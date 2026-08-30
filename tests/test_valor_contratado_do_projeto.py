"""docs/db/TAREFA_ACHADO21.md, 6-a — extração de `valor_contratado_do_projeto`.

Extração pura: nenhuma mudança de comportamento — a função existe e é testada aqui, mas ainda
não é chamada por nenhum caminho de produção (isso entra no 6-b/6-c). Responde "quanto já foi
CONTRATADO neste projeto" = Val_Cont do contrato + Val_Cont de cada aditivo TOTALMENTE assinado
(`status == "assinado"`) — rascunho, para_assinatura e assinatura parcial de uma parte só não
contam, e isso é medido explicitamente abaixo, não presumido."""
import json


def test_sem_contrato_retorna_zero(app_db, seed):
    db = app_db.get_session()
    import main
    assert main.valor_contratado_do_projeto(db, "Projeto_Sem_Contrato_Nenhum") == 0.0
    db.close()


def test_so_contrato_sem_aditivo(app_db, seed):
    import main
    _limpar_aditivos(app_db, seed["projeto_l1"])
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
    orc.valor_total = 88888.89
    db.commit()
    v = main.valor_contratado_do_projeto(db, seed["projeto_l1"])
    db.close()
    assert v == 88888.89


def _limpar_aditivos(app_db, nome):
    """`seed`/`app_db` são module-scoped — sem isto, os Aditivo criados por um teste
    sobreviveriam para o próximo teste deste arquivo que reusa `seed["projeto_l1"]`."""
    db = app_db.get_session()
    db.query(app_db.Aditivo).filter_by(projeto_nome=nome).delete()
    db.commit(); db.close()


def _criar_aditivo(app_db, nome, contrato_id, orc_valor, status, loja_id):
    db = app_db.get_session()
    orc_aj = app_db.Orcamento(projeto_id=nome, nome="Complemento PE teste", ordem=99,
                              desconto_pct=0.0, complemento_pe=1, loja_id=loja_id,
                              valor_total=orc_valor)
    db.add(orc_aj); db.flush()
    adt = app_db.Aditivo(projeto_nome=nome, contrato_id=contrato_id,
                         orcamento_complemento_id=orc_aj.id, loja_id=loja_id, status=status)
    db.add(adt); db.commit()
    aid = adt.id
    db.close()
    return aid


def test_aditivo_assinado_entra_na_soma(app_db, seed):
    import main
    _limpar_aditivos(app_db, seed["projeto_l1"])
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
    orc.valor_total = 88888.89
    ct = db.query(app_db.Contrato).filter_by(projeto_nome=seed["projeto_l1"]).first()
    ct_id = ct.id
    db.commit(); db.close()

    _criar_aditivo(app_db, seed["projeto_l1"], ct_id, 4444.44, "assinado", seed["loja1_id"])
    db2 = app_db.get_session()
    v = main.valor_contratado_do_projeto(db2, seed["projeto_l1"])
    db2.close()
    assert v == round(88888.89 + 4444.44, 2)


def test_aditivo_nao_assinado_nao_entra(app_db, seed):
    """rascunho, para_assinatura, e assinatura de UMA parte só (assinado_loja/assinado_cliente)
    NÃO contam — só `status == "assinado"` (as duas partes)."""
    import main
    _limpar_aditivos(app_db, seed["projeto_l1"])
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
    orc.valor_total = 88888.89
    ct = db.query(app_db.Contrato).filter_by(projeto_nome=seed["projeto_l1"]).first()
    ct_id = ct.id
    db.commit(); db.close()

    for status in ("rascunho", "para_assinatura", "assinado_loja", "assinado_cliente"):
        _criar_aditivo(app_db, seed["projeto_l1"], ct_id, 9999.99, status, seed["loja1_id"])

    db2 = app_db.get_session()
    v = main.valor_contratado_do_projeto(db2, seed["projeto_l1"])
    db2.close()
    assert v == 88888.89, (
        "nenhum aditivo não-totalmente-assinado deveria entrar na soma — %r" % v)


def test_multiplos_aditivos_assinados_somam_todos(app_db, seed):
    import main
    _limpar_aditivos(app_db, seed["projeto_l1"])
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
    orc.valor_total = 88888.89
    ct = db.query(app_db.Contrato).filter_by(projeto_nome=seed["projeto_l1"]).first()
    ct_id = ct.id
    db.commit(); db.close()

    _criar_aditivo(app_db, seed["projeto_l1"], ct_id, 4444.44, "assinado", seed["loja1_id"])
    _criar_aditivo(app_db, seed["projeto_l1"], ct_id, 6666.67, "assinado", seed["loja1_id"])

    db2 = app_db.get_session()
    v = main.valor_contratado_do_projeto(db2, seed["projeto_l1"])
    db2.close()
    assert v == round(88888.89 + 4444.44 + 6666.67, 2)
