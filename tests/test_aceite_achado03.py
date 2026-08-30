"""docs/db/TAREFA_FASE0.md, Passo 2 do ROTEIRO — a prova do ACHADO-03.

NÃO CONSERTA NADA. `_fin_provisoes_venda_seguro` (main.py) decide o evento de constituição do
Custo Financeiro por uma comparação binária (`_ramo == "financeira"`), enquanto
`mod_contabil._RAMO_CFIN_EVENTO` — o dicionário canônico pra essa mesma decisão — trata
"financeira" e "loja_antecipacao" da MESMA forma. Reproduzido: `orc.ramo_financeiro =
"loja_antecipacao"` faz a comparação binária cair no ramo ERRADO (o de "loja",
`constituir_juros_direto`), divergindo do que o dicionário canônico diz para o mesmo ramo."""
import pytest


def _saldo(db, mc, ot, oid, codigo, nome):
    return round(mc._mov(db, ot, oid, codigo, "credor", None, None, projeto_id=nome), 2)


@pytest.mark.xfail(strict=True, reason="ACHADO-03 (docs/db/ACHADOS_CONTABEIS.md): "
                    "_fin_provisoes_venda_seguro usa `_ramo == 'financeira'` (main.py) — diverge "
                    "de mod_contabil._RAMO_CFIN_EVENTO, que trata 'loja_antecipacao' IGUAL a "
                    "'financeira'. Vira verde quando main.py passar a usar o dict canônico.")
def test_ramo_loja_antecipacao_diverge_do_dict_canonico(app_db, seed):
    import main, mod_contabil as mc

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
    assert _saldo(db, mc, ot, owner_id, "2.1.04.19", nome) == 0.0
    assert _saldo(db, mc, ot, owner_id, "2.1.07", nome) == 0.0

    main._fin_provisoes_venda_seguro(orc, nome, "cf-achado03:" + nome)
    db.close()

    db = app_db.get_session()
    saldo_prov_custo_financeiro = _saldo(db, mc, ot, owner_id, "2.1.04.19", nome)   # dict canônico manda aqui
    saldo_juros_ramo_loja = _saldo(db, mc, ot, owner_id, "2.1.07", nome)             # main.py hoje lança aqui
    db.close()
    print("ACHADO-03 — 2.1.04.19 (esperado 5000.0)=%.2f | 2.1.07 (esperado 0.0, hoje recebe)=%.2f"
          % (saldo_prov_custo_financeiro, saldo_juros_ramo_loja))

    assert saldo_prov_custo_financeiro == 5000.0, (
        "ramo 'loja_antecipacao' deveria constituir a Provisão de Custo Financeiro (2.1.04.19), "
        "como o dicionário canônico manda — hoje: %.2f (foi pra 2.1.07 em vez disso: %.2f)"
        % (saldo_prov_custo_financeiro, saldo_juros_ramo_loja))
    assert saldo_juros_ramo_loja == 0.0
