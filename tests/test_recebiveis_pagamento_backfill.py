"""Robustez do achado da Vera (item 3, 2026-08-08): `_materializar_recebiveis_venda_seguro` só
lia `Orcamento.forma_pagamento` direto do banco. Mas o PDF do contrato (gerado na MESMA
requisição) usa outra precedência: `pagamento_json_str or orcamento_dict.get("forma_pagamento")`
— o plano que veio no CORPO da requisição de geração do contrato tem prioridade. Se o orçamento
nunca tivesse `forma_pagamento` gravado (só chegou no corpo desta requisição), o PDF saía com o
plano certo e os recebíveis saíam ZERO, em silêncio: sem exceção, sem log, ninguém percebia
(reproduzido pela Vera em 5 projetos na rodada de 2026-08-08). Fix: usa a mesma precedência do
PDF, faz backfill do orçamento (só quando ainda vazio) e loga uma anomalia clara se, mesmo assim,
não sobrar nenhuma fonte de plano de pagamento para uma venda com valor > 0."""
import json
import logging
from types import SimpleNamespace
from datetime import datetime

import main


def _pag_json(tipo="avista", entrada_valor=0.0, entrada_data="", parcelas=None):
    return json.dumps({"tipo": tipo, "entrada_valor": entrada_valor, "entrada_data": entrada_data,
                       "parcelas": parcelas or []})


def _novo_orcamento(db_module, sufixo, valor_total, forma_pagamento=None):
    """Cria Cliente+Projeto+Orcamento mínimos na loja seed (db_pg_limpo já rodou init_db).
    `forma_pagamento=None` reproduz o cenário do bug: o campo nunca foi gravado no orçamento."""
    db = db_module.get_session()
    loja = db.query(db_module.Loja).order_by(db_module.Loja.id).first()
    cli = db_module.Cliente(nome="Cliente " + sufixo, cpf="529.982.247-25", loja_id=loja.id)
    db.add(cli); db.flush()
    proj_nome = "ProjBackfill_" + sufixo
    proj = db_module.Projeto(nome_safe=proj_nome, cliente_id=cli.id, status="quente", loja_id=loja.id)
    db.add(proj); db.flush()
    orc = db_module.Orcamento(projeto_id=proj_nome, nome="Orçamento 1", ordem=1, loja_id=loja.id,
                              valor_total=valor_total, forma_pagamento=forma_pagamento)
    db.add(orc); db.flush()
    orc_id, loja_id = orc.id, loja.id
    db.commit(); db.close()
    return orc_id, loja_id, proj_nome


def _recebiveis_do_orcamento(db_module, orc_id):
    db = db_module.get_session()
    linhas = db.query(db_module.Recebivel).filter_by(orcamento_id=orc_id).all()
    out = [(l.tipo, l.valor_previsto) for l in linhas]
    db.close()
    return out


def test_forma_pagamento_vazia_no_orcamento_mas_com_pagamento_json_da_requisicao_materializa(db_pg_limpo):
    """O cenário exato do achado: Orcamento.forma_pagamento nunca foi gravado, mas a própria
    requisição de geração do contrato trouxe o plano (pagamento_json_str). Antes do fix: 0
    recebíveis materializados, sem aviso nenhum. Agora: usa o plano da requisição."""
    orc_id, loja_id, proj_nome = _novo_orcamento(db_pg_limpo, "A", 10000.0, forma_pagamento=None)
    pag = _pag_json("avista", entrada_valor=3000.0, entrada_data="2026-08-01",
                    parcelas=[{"num": 1, "data": "2026-08-15", "valor": 7000.0, "forma": "pix"}])

    main._materializar_recebiveis_venda_seguro(
        SimpleNamespace(id=orc_id), proj_nome, loja_id, datetime(2026, 8, 1),
        "receb:test-A", pagamento_json_str=pag)

    linhas = _recebiveis_do_orcamento(db_pg_limpo, orc_id)
    assert sorted(linhas) == [("entrada", 3000.0), ("parcela", 7000.0)]


def test_forma_pagamento_vazia_e_sem_pagamento_json_nao_materializa_e_loga_anomalia(db_pg_limpo, caplog):
    """Sem NENHUMA fonte de plano de pagamento (nem orçamento, nem requisição) e valor_total > 0:
    continua fail-soft (não levanta, não trava a geração do contrato — mesmo espírito de
    `_fin_provisoes_venda_seguro`), mas agora ISSO FICA VISÍVEL num warning, em vez de sumir."""
    orc_id, loja_id, proj_nome = _novo_orcamento(db_pg_limpo, "B", 8000.0, forma_pagamento=None)

    with caplog.at_level(logging.WARNING, logger="main"):
        main._materializar_recebiveis_venda_seguro(
            SimpleNamespace(id=orc_id), proj_nome, loja_id, datetime(2026, 8, 1),
            "receb:test-B", pagamento_json_str=None)

    assert _recebiveis_do_orcamento(db_pg_limpo, orc_id) == []
    avisos = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("receb:test-B" in m and "0 recebíveis" in m for m in avisos), avisos


def test_pagamento_json_da_requisicao_faz_backfill_no_orcamento(db_pg_limpo):
    """Corrige a causa raiz, não só o sintoma: se o orçamento estava com forma_pagamento vazio e
    veio um plano na requisição, o orçamento é atualizado — quem ler Orcamento.forma_pagamento
    depois (relatórios, reemissão de contrato) vê o dado certo, não mais vazio."""
    orc_id, loja_id, proj_nome = _novo_orcamento(db_pg_limpo, "C", 5000.0, forma_pagamento=None)
    pag = _pag_json("avista", entrada_valor=5000.0, entrada_data="2026-08-01")

    main._materializar_recebiveis_venda_seguro(
        SimpleNamespace(id=orc_id), proj_nome, loja_id, datetime(2026, 8, 1),
        "receb:test-C", pagamento_json_str=pag)

    db = db_pg_limpo.get_session()
    orc = db.get(db_pg_limpo.Orcamento, orc_id)
    assert orc.forma_pagamento == pag
    db.close()


def test_forma_pagamento_ja_gravada_no_orcamento_nunca_e_sobrescrita(db_pg_limpo):
    """Backfill só quando vazio: um orçamento que JÁ tem forma_pagamento (o caminho normal, sem
    bug) não pode ter esse valor trocado pelo que porventura vier (ou não vier) na requisição."""
    pag_original = _pag_json("avista", entrada_valor=1000.0, entrada_data="2026-08-01",
                             parcelas=[{"num": 1, "data": "2026-08-20", "valor": 4000.0}])
    orc_id, loja_id, proj_nome = _novo_orcamento(db_pg_limpo, "D", 5000.0,
                                                 forma_pagamento=pag_original)

    main._materializar_recebiveis_venda_seguro(
        SimpleNamespace(id=orc_id), proj_nome, loja_id, datetime(2026, 8, 1),
        "receb:test-D", pagamento_json_str=None)   # requisição não manda nada — não deve importar

    db = db_pg_limpo.get_session()
    orc = db.get(db_pg_limpo.Orcamento, orc_id)
    assert orc.forma_pagamento == pag_original
    db.close()
    assert sorted(_recebiveis_do_orcamento(db_pg_limpo, orc_id)) == [("entrada", 1000.0), ("parcela", 4000.0)]


def test_valor_total_zero_sem_plano_de_pagamento_nao_loga_anomalia(db_pg_limpo, caplog):
    """Venda de valor zero (ex.: projeto de teste/cortesia) sem plano de pagamento é legítima —
    não é a anomalia que o warning existe para sinalizar. Só valor_total>0 dispara o aviso."""
    orc_id, loja_id, proj_nome = _novo_orcamento(db_pg_limpo, "E", 0.0, forma_pagamento=None)

    with caplog.at_level(logging.WARNING, logger="main"):
        main._materializar_recebiveis_venda_seguro(
            SimpleNamespace(id=orc_id), proj_nome, loja_id, datetime(2026, 8, 1),
            "receb:test-E", pagamento_json_str=None)

    avisos = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert not any("receb:test-E" in m for m in avisos), avisos
