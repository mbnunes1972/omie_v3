"""docs/db/TAREFA_FASE0.md, Passo 2 do ROTEIRO — a prova do ACHADO-03. Reescrito no passo 10
(docs/db/TAREFA_ACHADO02_03.md, ACHADO-02+03): a medição original (29/08) provou que main.py
divergia de `mod_contabil._RAMO_CFIN_EVENTO` para o ramo 'loja_antecipacao' — main.py mandava pro
mesmo evento de 'loja' (`constituir_juros_direto`), o dicionário mandava pro de 'financeira'
(`fechamento_venda_custo_financeiro`). A medição da decisão (30/08) mostrou que NENHUM dos dois
estava certo: 'loja_antecipacao' não é receita nem custo constituídos como provisão no
fechamento — é receita financeira a apropriar, IGUAL a 'loja' (o deságio do banco só existe
no evento da antecipação, separado). A tabela mudou para refletir isso; main.py agora lê a
tabela (não decide sozinho) — os dois concordam, e é exatamente o eventos que main.py já lançava
por coincidência antes."""
import mod_contabil as mc


def _saldo(db, ot, oid, codigo, nome):
    return round(mc._mov(db, ot, oid, codigo, "credor", None, None, projeto_id=nome), 2)


def test_ramo_loja_antecipacao_usa_o_mesmo_evento_do_dict_canonico(app_db, seed):
    import main

    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja1_id"]
    orc.valor_total = 5000.0          # sem ambiente nenhum: VAVO=0 no breakdown → Cust_Fin = 5000
    orc.ramo_financeiro = "loja_antecipacao"
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    # pré-condição, afirmada ANTES de exercitar: nada lançado ainda pra nenhum dos dois caminhos.
    assert _saldo(db, ot, owner_id, "2.1.04.19", nome) == 0.0
    assert _saldo(db, ot, owner_id, "2.1.07", nome) == 0.0

    main._fin_provisoes_venda_seguro(orc, nome, "cf-achado03:" + nome)
    db.close()

    db = app_db.get_session()
    saldo_prov_custo_financeiro = _saldo(db, ot, owner_id, "2.1.04.19", nome)
    saldo_juros_ramo_loja = _saldo(db, ot, owner_id, "2.1.07", nome)
    db.close()

    # main.py e o dicionário canônico (`mc.evento_custo_financeiro`) concordam agora: os dois
    # mandam 'loja_antecipacao' pra receita financeira a apropriar, não pra provisão.
    assert mc.evento_custo_financeiro("loja_antecipacao") == "constituir_juros_direto"
    assert saldo_juros_ramo_loja == 5000.0, (
        "ramo 'loja_antecipacao' deveria constituir receita financeira a apropriar (2.1.07), "
        "igual a 'loja' — hoje: %.2f (foi pra 2.1.04.19 em vez disso: %.2f)"
        % (saldo_juros_ramo_loja, saldo_prov_custo_financeiro))
    assert saldo_prov_custo_financeiro == 0.0
