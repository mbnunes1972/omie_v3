# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-55 — a decisão do PE era reversível na TELA e
irreversível no LIVRO. Relato do Marcelo (05/09): escolheu "manter", depois "estornar" — o
estorno foi lançado; voltou pra "manter" e o lançamento NÃO foi corrigido. `ConciliacaoPeFase`
(o registro) é corrigido a cada redecisão (delete+reinsere); o crédito ao cliente
(`registrar_credito_cliente`, ref fixo `est:<projeto>:<pool>`) só sabia CRIAR, nunca reverter —
o razão ficava dizendo "estornado" pra sempre, mesmo com a decisão atual sendo "manter".

Medido antes de codar: (a) decidir "estornar" duas vezes NÃO duplicava o crédito — o `ref` fixo
tornava `registrar_evento` idempotente por si só (achado: não é um segundo defeito de dinheiro).
(b) o estado "cliente assinou a aprovação do PE" é consultável — `CicloEtapa(etapa_codigo="11e")
.status in mod_ciclo.STATUS_CONCLUSIVOS`. (c) medição real em Homologação: 1 caso hoje
(`Teste_4`/pool 16, sequência manter→estornar→manter→manter), com o crédito de R$ 64.043,46
ainda vivo no razão apesar da decisão atual ser "manter" — exatamente o defeito.

Conserto por LANÇAMENTO, nunca por apagamento (mesmo desenho do ACHADO-16/30/34): sair de
"estornar" gera uma REVERSÃO com rastro (`mod_contabil.reverter_credito_cliente_pe`, lançamento
invertido, ref '<original>:estorno', mesmo padrão do `estornar_rateio`); entrar em "estornar"
emite um crédito NOVO numerado por tentativa (`registrar_credito_cliente_pe`, nunca reaproveita
um ref já revertido). E a janela do (b) passa a ser recusada de propósito: redecidir depois de a
11e concluir vira 409, não mais um delete+reinsere silencioso."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.test_conciliacao_pe_e2e import _login, _setup, _carrega_pe


def test_sequencia_manter_estornar_manter_livro_termina_coerente(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=27000.0)   # custo caiu 3000 — manter/estornar válidos
    c = _login(http_client_factory)

    st1, b1 = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                     {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "manter"})
    assert st1 == 200 and b1["ok"], b1

    st2, b2 = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                     {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "estornar",
                      "valor_aprovado": 5000.0})
    assert st2 == 200 and b2["ok"], b2

    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid_c = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    assert mc.saldo_credito_cliente(db, ot, oid_c, nome) == 5000.0, "crédito lançado ao estornar"
    db.close()

    st3, b3 = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                     {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "manter"})
    assert st3 == 200 and b3["ok"], b3

    db = app_db.get_session()
    # o REGISTRO diz "manter"...
    reg = db.query(app_db.ConciliacaoPeFase).filter_by(
        projeto_nome=nome, pool_ambiente_id=pid).first()
    assert reg.tipo_decisao == "manter"
    # ...e o LIVRO agora concorda: o crédito foi revertido, saldo zerado (não apagado — os dois
    # lançamentos continuam existindo, o original E a reversão).
    assert mc.saldo_credito_cliente(db, ot, oid_c, nome) == 0.0, \
        "voltou pra 'manter' — o crédito tem que ter sido revertido, não deixado órfão"
    lans = (db.query(app_db.Lancamento).filter(app_db.Lancamento.ref.like("est:%s:%d:%%" % (nome, pid)))
              .order_by(app_db.Lancamento.id.asc()).all())
    assert len(lans) == 2, "crédito original + reversão — nunca um DELETE"
    assert lans[0].ref == "est:%s:%d:1" % (nome, pid)
    assert lans[1].ref == "est:%s:%d:1:estorno" % (nome, pid)
    db.close()


def test_reestornar_depois_de_reverter_emite_credito_novo_nao_reaproveita_ref(
        http_client_factory, seed, app_db):
    """Controle-irmão: voltar a 'estornar' depois de já ter revertido tem que criar um crédito
    NOVO (numerado), não devolver o antigo (já revertido) por idempotência de ref."""
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=27000.0)
    c = _login(http_client_factory)
    for tipo in ("estornar", "manter", "estornar"):
        body = {"login": "dir_l1", "senha": "senha123", "tipo_decisao": tipo}
        if tipo == "estornar":
            body["valor_aprovado"] = 5000.0
        st, b = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}", body)
        assert st == 200 and b["ok"], b

    import mod_contabil as mc
    db = app_db.get_session()
    ot, oid_c = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    assert mc.saldo_credito_cliente(db, ot, oid_c, nome) == 5000.0, \
        "o segundo 'estornar' tem que reativar o crédito"
    lans = (db.query(app_db.Lancamento).filter(app_db.Lancamento.ref.like("est:%s:%d:%%" % (nome, pid)))
              .order_by(app_db.Lancamento.id.asc()).all())
    assert len(lans) == 3, "crédito 1 + reversão 1 + crédito 2 — cada tentativa com seu ref"
    assert lans[2].ref == "est:%s:%d:2" % (nome, pid)
    db.close()


def test_redecidir_depois_da_assinatura_do_pe_e_recusado(http_client_factory, seed, app_db):
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=27000.0)
    c = _login(http_client_factory)

    st1, b1 = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                     {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "manter"})
    assert st1 == 200 and b1["ok"], b1

    # cliente assina a aprovação do PE (11e concluída) — a janela do Marcelo fecha aqui.
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo="11e", status="concluido"))
    db.commit(); db.close()

    st2, b2 = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                     {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "estornar",
                      "valor_aprovado": 5000.0})
    assert st2 == 409, b2
    assert "assinou" in b2["erro"].lower() or "aprovação" in b2["erro"].lower(), b2

    db = app_db.get_session()
    reg = db.query(app_db.ConciliacaoPeFase).filter_by(
        projeto_nome=nome, pool_ambiente_id=pid).first()
    assert reg.tipo_decisao == "manter", "recusado — a decisão anterior não pode ter mudado"
    db.close()


def test_primeira_decisao_e_livre_mesmo_apos_assinatura(http_client_factory, seed, app_db):
    """Controle: a janela protege REDECIDIR (mudar uma decisão existente). A primeira decisão
    pra um ambiente nunca visto ainda não é 'redecidir' — continua livre mesmo com a 11e
    concluída (não trava quem nunca decidiu nada)."""
    nome, pid, oid = _setup(app_db, seed, cfo_original=30000.0)
    _carrega_pe(app_db, nome, pid, cfo_pe=27000.0)
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=nome, etapa_codigo="11e", status="concluido"))
    db.commit(); db.close()
    c = _login(http_client_factory)

    st, b = c.post(f"/api/projetos/{nome}/pe/conciliacao/{pid}",
                  {"login": "dir_l1", "senha": "senha123", "tipo_decisao": "manter"})
    assert st == 200 and b["ok"], b
