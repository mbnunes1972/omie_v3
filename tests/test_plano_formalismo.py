# -*- coding: utf-8 -*-
"""Formalismo pleno do plano (decisão do usuário, 2026-07-22, Sessão 109): a família 5.6
("constituição") é suprimida — a despesa de cada rubrica mora no grupo contábil FORMAL:
CMV (Frete de Fábrica 5.1.02), Custo de Serviço (Montagem 5.2.01, Frete Local 5.2.08,
Insumos Locais 5.2.09, Garantia 5.2.12, Assistência Técnica 5.2.13) e Despesas Comerciais
(Comissão de Medidor 5.3.18, Comissão de Projeto/Executivo 5.3.19, Retenção 5.3.20).
Da 5.6 sobra só o 5.6.10 Ajuste de Provisões. A migração RECODIFICA a mesma linha de conta
(id preservado → histórico junto) e faz merge quando o código formal está ocupado por
duplicata antiga com movimento. Condições do usuário: sem falta de lançamentos, sem perda
de gestão, sem erro de processamento, sem impropriedade contábil."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_contabil as mc

FORMAIS = {"5.1.02": "Frete de Fábrica", "5.2.01": "Montagem", "5.2.08": "Frete Local",
           "5.2.09": "Insumos Locais", "5.2.12": "Garantia", "5.2.13": "Assistência Técnica",
           "5.3.18": "Comissão de Medidor", "5.3.19": "Comissão de Projeto/Executivo"}
           # 5.3.20 "Retenção de Comissão de Vendas" removida (Centro de Custo/Natureza, 2026-08-08)
           # — o evento passou a debitar 5.3.01 Comissão de Vendedor


def test_seed_novo_formal(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 950)
    contas = {c.codigo: c for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=950).all()}
    db.close()
    for cod, nome in FORMAIS.items():
        assert contas[cod].nome == nome, cod
    assert "5.6.01" not in contas and "5.6.09" not in contas   # família suprimida
    assert contas["5.6"].nome == "Ajustes de Provisões"
    assert contas["5.6.10"].nome == "Ajuste de Provisões"      # único sobrevivente


def test_eventos_reconhecimento_nas_contas_formais(app_db):
    esperado = {"reconhecimento_despesa_montagem": "5.2.01",
                "reconhecimento_despesa_garantia": "5.2.12",
                "reconhecimento_despesa_assistencia": "5.2.13",
                "reconhecimento_despesa_frete_fabrica": "5.1.02",
                "reconhecimento_despesa_frete_local": "5.2.08",
                "reconhecimento_despesa_insumos": "5.2.09",
                "reconhecimento_despesa_com_medidor": "5.3.18",
                "reconhecimento_despesa_com_proj_exec": "5.3.19",
                "reconhecimento_despesa_retencao_com_vendas": "5.3.01",
                "reconhecimento_despesa_custo_fabrica": "5.1.01"}
    for ev, conta in esperado.items():
        assert mc.EVENTOS[ev][0] == conta, ev


def _base_geracao_s108(db, oid):
    """Simula uma base no estado da S108 (imediatamente anterior): família 5.6 com nome puro
    e SEM as contas formais novas (5.1.02 etc. tinham sido removidas)."""
    mc.seed_plano(db, "loja", oid)
    contas = {c.codigo: c for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=oid).all()}
    velhas = {"5.6.01": "Garantia", "5.6.02": "Montagem", "5.6.03": "Assistência Técnica",
              "5.6.04": "Frete de Fábrica", "5.6.05": "Frete Local", "5.6.06": "Insumos Locais",
              "5.6.07": "Comissão de Medidor", "5.6.08": "Comissão de Projeto/Executivo",
              "5.6.09": "Retenção de Comissão de Vendas"}
    for cod, c in list(contas.items()):
        if cod in FORMAIS:
            db.delete(c)                     # essas contas não existiam na S108
    db.flush()
    g56 = contas["5.6"]
    g56.nome = "Despesas de Provisões"
    for cod, nome in velhas.items():
        db.add(mc.Conta(owner_tipo="loja", owner_id=oid, codigo=cod, nome=nome, grupo=5,
                        tipo="analitica", natureza="devedora", pai_id=g56.id, ativa=1, ordem=990))
    db.commit()


def test_migracao_recodifica_preservando_historico(app_db):
    db = app_db.get_session()
    _base_geracao_s108(db, 951)
    # movimento REAL na 5.6.02 (reconhecimento de montagem) antes da migração
    c5602 = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=951, codigo="5.6.02").first()
    ativo = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=951, codigo="1.1.06.02").first()
    mc.lancar(db, "loja", 951, c5602.id, ativo.id, 500.0, projeto_id="P", historico="montagem NF-e")
    id_original = c5602.id
    out = mc.migrar_plano_formalismo(db)
    assert out["recodificadas"] >= 8   # 5.6.09 removida (Centro de Custo/Natureza, 2026-08-08)
    contas = {c.codigo: c for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=951).all()}
    assert "5.6.02" not in contas
    assert contas["5.2.01"].id == id_original          # MESMA linha — histórico preservado
    assert contas["5.2.01"].nome == "Montagem"
    pai = db.get(mc.Conta, contas["5.2.01"].pai_id)
    assert pai.codigo == "5.2"                          # reparentada no grupo formal
    assert contas["5.6"].nome == "Ajustes de Provisões"
    # o saldo veio junto: nada de lançamento perdido
    assert mc.saldo_conta(db, "loja", 951, contas["5.2.01"].id) != 0.0
    # idempotente
    out2 = mc.migrar_plano_formalismo(db)
    assert out2["recodificadas"] == 0 and out2["mescladas"] == 0
    db.close()


def test_migracao_merge_com_duplicata_com_movimento(app_db):
    """Base pré-S107: existia a duplicata 5.2.01 'Montagem' COM lançamento manual. Ela vira a
    conta formal e recebe também o histórico da 5.6.02 (a reclassificação da duplicação)."""
    db = app_db.get_session()
    _base_geracao_s108(db, 952)
    g52 = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=952, codigo="5.2").first()
    dupe = mc.Conta(owner_tipo="loja", owner_id=952, codigo="5.2.01", nome="Montagem", grupo=5,
                    tipo="analitica", natureza="devedora", pai_id=g52.id, ativa=1, ordem=991)
    db.add(dupe); db.flush()
    caixa = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=952, codigo="1.1.01").first()
    mc.lancar(db, "loja", 952, dupe.id, caixa.id, 100.0, historico="montagem manual (duplicada)")
    dupe.ativa = 0                       # estado que a S107/108 deixava: desativada com movimento
    db.commit()
    c5602 = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=952, codigo="5.6.02").first()
    ativo = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=952, codigo="1.1.06.02").first()
    mc.lancar(db, "loja", 952, c5602.id, ativo.id, 500.0, historico="montagem NF-e")
    out = mc.migrar_plano_formalismo(db)
    assert out["mescladas"] >= 1
    sobrev = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=952, codigo="5.2.01").all()
    assert len(sobrev) == 1 and sobrev[0].id == dupe.id and sobrev[0].ativa
    assert db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=952,
                                        codigo="5.6.02").first() is None
    # os DOIS lançamentos vivem na conta formal — 600 de débito no total
    assert abs(mc.saldo_conta(db, "loja", 952, dupe.id) - 600.0) < 0.01
    db.close()


def test_migracao_preserva_nome_customizado(app_db):
    db = app_db.get_session()
    _base_geracao_s108(db, 953)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=953, codigo="5.6.05").first()
    c.nome = "Frete Local da Minha Loja"
    db.commit()
    mc.migrar_plano_formalismo(db)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=953, codigo="5.2.08").first()
    assert c is not None and c.nome == "Frete Local da Minha Loja"   # recodifica, não renomeia
    db.close()


def test_dre_lucro_bruto_formal(app_db):
    """A razão da reforma: reconhecimento de montagem agora entra no CMV+CSP e o lucro
    bruto sai FORMAL (antes ficava na 5.6 e só descontava no EBITDA)."""
    db = app_db.get_session()
    ot, oid = "loja", 954
    mc.seed_plano(db, ot, oid)
    c = lambda cod: db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id
    mc.lancar(db, ot, oid, c("1.1.02"), c("4.1.01"), 1000.0, projeto_id="P")   # venda
    mc.lancar(db, ot, oid, c("5.2.01"), c("1.1.06.02"), 200.0, projeto_id="P")  # montagem reconhecida
    d = mc.dre(db, ot, oid)
    assert abs(d["cmv_csp"] - 200.0) < 0.01
    assert abs(d["lucro_bruto"] - 800.0) < 0.01        # formal: já líquido da montagem
    assert abs(d["constituicao_provisoes"]) < 0.01     # 5.6 = só ajustes (zero aqui)
    db.close()
