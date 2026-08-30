"""docs/db/TAREFA_ACHADO12.md, ponto 3 — segmentação congelada. MEDIÇÃO, NÃO CONSERTO.

Não implementa o congelamento por aditivo — a decisão é do Marcelo. Mede e reporta:
1. É alcançável? Que caminhos mudam pct_mercadoria/pct_servico do projeto ou da loja depois do
   contrato assinado?
2. Efeito em número, num caso concreto.
3. `Aditivo.dados_json` já carrega a segmentação, ou precisaria carregar?"""
import json

from tests.test_aditivo_costuras import (
    _setup, _upsert_compl, _criar_modelo_aditivo, _assinar_aditivo_completo, _login,
)


def test_parametros_bloqueado_apos_contrato_assinado(app_db, seed, http_client_factory):
    """Caminho 1 (projeto): `/api/projetos/<n>/parametros` — incluindo pct_mercadoria/pct_servico
    — é bloqueado por `_contrato_assinado` assim que o contrato tem qualquer assinatura. NÃO
    alcançável por aqui."""
    nome, pid, oid = _setup(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{nome}/parametros",
                      {"pct_mercadoria": 50.0, "pct_servico": 50.0})
    assert st == 403 and not body["ok"], body
    assert "contrato assinado" in body["erro"].lower(), body


def test_segmentacao_frozen_protege_o_projeto_de_mudanca_na_loja(app_db, seed, http_client_factory):
    """Caminho 2 (loja): `PUT /api/lojas/<id>` muda `Loja.pct_mercadoria`/`pct_servico` SEM checar
    nenhum projeto — é um dado global da loja, não tem por que checar. Mas se o projeto já tem a
    segmentação CONGELADA em `Projeto.parametros_json` (via `_congelar_segmentacao_no_projeto`,
    disparado na 2ª assinatura do contrato — main.py:961), o override do projeto vence o default
    da loja (`mod_orcamento_params.segmentacao_efetiva`) — mudar a loja depois NÃO afeta este
    projeto. Medido com número concreto."""
    import main
    nome, pid, oid = _setup(app_db, seed)
    loja_id = seed["loja1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    main._recalcular_orcamento(orc, db)
    db.commit()
    val_cont = round(float(orc.valor_total or 0), 2)
    seg_congelada = main._congelar_segmentacao_no_projeto(db, loja_id, nome)
    db.commit()
    db.close()
    assert seg_congelada is not None
    assert abs(seg_congelada["pct_mercadoria"] - 100.0) < 0.01, seg_congelada   # herda o override do _setup

    # muda o default da LOJA depois do "congelamento" (equivalente a depois da assinatura)
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    loja.pct_mercadoria = 30.0
    loja.pct_servico = 70.0
    db.commit()
    vals = main._valores_segmentados_do_projeto(db, loja_id, nome)
    db.close()

    print("SEGMENTAÇÃO — congelada em 100%% mercadoria; loja mudou pra 30%%/70%% depois; "
          "vals['mercadoria']=%.2f de val_cont=%.2f" % (vals["mercadoria"], val_cont))
    assert abs(vals["mercadoria"] - val_cont) < 0.05, (
        "com o congelamento no lugar, a mudança na loja NÃO deveria afetar este projeto — %r"
        % vals)


def test_sem_congelamento_mudanca_na_loja_afeta_o_projeto_com_numero(app_db, seed, http_client_factory):
    """O congelamento (`_congelar_segmentacao_no_projeto`) roda dentro de um try/except FAIL-SOFT
    na assinatura do contrato (main.py:956-963: `except Exception as _eseg: ... print(...)`) — se
    falhar por qualquer motivo, o projeto segue vivendo do default da LOJA, ao vivo, para sempre.
    Mede o efeito: SEM a segmentação congelada (nenhuma chave pct_mercadoria/pct_servico no
    parametros_json do projeto — o estado real de um projeto legado, ou de uma falha silenciosa
    do congelamento), uma mudança na loja DEPOIS que o contrato já está assinado muda o valor
    faturado do próprio contrato (e, pelo mesmo motivo, do aditivo — mesma leitura em
    `_valores_segmentados_do_projeto`)."""
    import main
    nome, pid, oid = _setup(app_db, seed)
    loja_id = seed["loja1_id"]
    db = app_db.get_session()
    # `seed`/`app_db` são module-scoped — reset explícito pro default 65/35, senão herda a
    # mudança que o teste vizinho deste arquivo já fez na MESMA loja.
    loja0 = db.get(app_db.Loja, loja_id)
    loja0.pct_mercadoria = 65.0; loja0.pct_servico = 35.0
    orc = db.get(app_db.Orcamento, oid)
    main._recalcular_orcamento(orc, db)
    db.commit()
    val_cont = round(float(orc.valor_total or 0), 2)
    # remove a segmentação do parametros_json — simula "congelamento nunca aconteceu"
    proj = db.query(app_db.Projeto).filter_by(nome_safe=nome).first()
    params = json.loads(proj.parametros_json)
    params.pop("pct_mercadoria", None); params.pop("pct_servico", None)
    proj.parametros_json = json.dumps(params)
    db.commit()
    db.close()

    db = app_db.get_session()
    vals_antes = main._valores_segmentados_do_projeto(db, loja_id, nome)
    db.close()
    assert abs(vals_antes["mercadoria"] - val_cont * 0.65) < 0.05, vals_antes   # default 65/35

    # muda o default da loja DEPOIS de "assinado" — projeto sem congelamento reflete na hora
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    loja.pct_mercadoria = 20.0
    loja.pct_servico = 80.0
    db.commit()
    vals_depois = main._valores_segmentados_do_projeto(db, loja_id, nome)
    db.close()

    diferenca = round(vals_depois["mercadoria"] - vals_antes["mercadoria"], 2)
    print("SEGMENTAÇÃO SEM CONGELAMENTO — mercadoria antes (65%%)=%.2f, depois (20%%)=%.2f, "
          "diferença=%.2f sobre val_cont=%.2f" % (vals_antes["mercadoria"], vals_depois["mercadoria"],
                                                   diferenca, val_cont))
    assert abs(vals_depois["mercadoria"] - val_cont * 0.20) < 0.05, vals_depois
    assert abs(diferenca) > 0.01, "a mudança na loja tem que ter efeito mensurável sem o congelamento"
