"""docs/db/TAREFA_CENTRO_CUSTO_2.md, item 2 — loja nova sem classificação (bug, bloqueava).

Antes de `aplicar_gabarito_completo` (mod_contabil.py), a árvore de centro de custo e o plano
de contas tinham seed-on-first-access, mas a classificação do grupo 5
(`conta.centro_custo_id`/`natureza_custo`) só era aplicada por `migrar_classificacao_grupo5_v1`,
chamada SÓ no boot do servidor — uma loja criada em runtime, cujo plano só nasce quando alguém
visita a tela, ficava com o grupo 5 inteiro em NULL até o próximo restart.

Este teste cria a loja pela API de verdade (`POST /api/admin/lojas`) — SEM visitar nenhuma tela
de Plano de Contas/Centro de Custo e SEM reiniciar o servidor de teste — e afirma que o grupo 5
já nasce com `centro_custo_id`/`natureza_custo` preenchidos.
"""
import mod_contabil as mc


def test_criar_loja_via_api_nasce_com_grupo5_classificado(http_client_factory, seed, app_db):
    c = http_client_factory()
    c.login("super", "senha123")

    st, d = c.post("/api/admin/lojas", {
        "nome": "Loja Gabarito Teste",
        "codigo": "GAB",
        "rede_id": seed["rede_id"],
    })
    assert st == 200 and d.get("ok"), d
    loja_id = d["loja"]["id"]

    db = app_db.get_session()
    try:
        contas_grupo5 = (db.query(mc.Conta)
                         .filter_by(owner_tipo="loja", owner_id=loja_id, grupo=5, tipo="analitica")
                         .all())
        assert contas_grupo5, (
            "loja nova sem NENHUMA conta do grupo 5 — o plano de contas nao foi semeado "
            "na criacao da loja."
        )

        esperadas = set(mc.CLASSIFICACAO_GRUPO5_V1)
        encontradas = {c.codigo for c in contas_grupo5}
        assert esperadas <= encontradas, (
            f"faltam codigos do grupo 5 que deveriam ter sido semeados: {esperadas - encontradas}"
        )

        sem_centro_custo = [c.codigo for c in contas_grupo5
                            if c.codigo in esperadas and c.centro_custo_id is None]
        sem_natureza = [c.codigo for c in contas_grupo5
                        if c.codigo in esperadas and c.natureza_custo is None]
        assert not sem_centro_custo, (
            f"contas do grupo 5 SEM centro_custo_id logo apos criar a loja: {sem_centro_custo}"
        )
        assert not sem_natureza, (
            f"contas do grupo 5 SEM natureza_custo logo apos criar a loja: {sem_natureza}"
        )

        # a arvore de centro de custo tambem nasce junto (16 nos do CENTRO_CUSTO_PADRAO)
        n_cc = db.query(mc.CentroCusto).filter_by(owner_tipo="loja", owner_id=loja_id).count()
        assert n_cc == len(mc.CENTRO_CUSTO_PADRAO)
    finally:
        db.close()
