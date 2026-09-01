"""ACHADO-32 (docs/db/ACHADOS_CONTABEIS.md) — item 1 de docs/db/TAREFA_CONCILIACAO_UI.md.

`resolver-saldo-provisao` (main.py:10279) recusa com 409 qualquer conta fora de
`mod_contabil._PROV_FORA_DO_VEREDITO` desde o F2-3, mas `_reconProvTabelaHtml` (static/index.html)
continuava desenhando Efetivar/Resolver em toda linha, sem saber da regra — as seis provisões
abertas na tela do Marcelo eram todas "veredito nomeado" e nenhuma podia ser resolvida ali.

O aceite: `mod_contabil.reconciliacao()` expõe `exige_veredito` por linha, derivado da MESMA
constante que o endpoint usa — não uma cópia. Controle negativo (sugerido pelo próprio
TAREFA_CONCILIACAO_UI.md): mover um código para dentro de `_PROV_FORA_DO_VEREDITO` e o teste da
linha "veredito nomeado" tem que falhar — prova que a flag rastreia a constante de verdade, não
um valor fixo na tela nem no teste."""
import mod_contabil as mc


def test_reconciliacao_expoe_exige_veredito_derivado_da_constante(app_db, seed):
    """Aceite principal: código de veredito nomeado (Comissão de Vendedor) vem com
    exige_veredito=True; código de rota genérica (Impostos) vem com False e o destino nomeado."""
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        rec = mc.reconciliacao(db, ot, oid)
        por_codigo = {p["codigo"]: p for p in rec["provisoes"]}

        comissao = por_codigo["2.1.04.10"]   # Comissão de Vendedor — veredito nomeado
        assert comissao["exige_veredito"] is True

        impostos = por_codigo["2.1.04.13"]   # Impostos — rota genérica (ACHADO-01)
        assert impostos["exige_veredito"] is False
        assert impostos["resolucao_tipo"] == "destino_variancia"
        assert impostos["resolucao_destino_nome"] and "4.3.01" in impostos["resolucao_destino_nome"]

        custo_fin = por_codigo["2.1.04.19"]  # Custo Financeiro — rota genérica, sem destino mapeado
        assert custo_fin["exige_veredito"] is False
        assert custo_fin["resolucao_tipo"] is None
    finally:
        db.close()


def test_controle_negativo_exige_veredito_segue_a_constante_nao_um_valor_fixo(app_db, seed, monkeypatch):
    """Controle negativo explícito do TAREFA_CONCILIACAO_UI.md: move "2.1.04.10" pra dentro de
    _PROV_FORA_DO_VEREDITO — se a flag fosse hardcoded (na tela OU no teste), nada mudaria aqui.
    Sendo derivada da constante de verdade, exige_veredito tem que virar False."""
    monkeypatch.setattr(mc, "_PROV_FORA_DO_VEREDITO",
                        mc._PROV_FORA_DO_VEREDITO | {"2.1.04.10"})
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        rec = mc.reconciliacao(db, ot, oid)
        comissao = next(p for p in rec["provisoes"] if p["codigo"] == "2.1.04.10")
        assert comissao["exige_veredito"] is False, (
            "com o código movido pra _PROV_FORA_DO_VEREDITO, exige_veredito tinha que acompanhar")
    finally:
        db.close()
