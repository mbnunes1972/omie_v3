"""docs/db/TESTE_NEGOCIACAO_VALOR_TOTAL.md, Medição 1 — `_negociacao_breakdown` levanta exceção
com que entrada?

MEDIÇÃO, NÃO CONSERTO. Para cada candidato de exceção listado na tarefa (e outros achados na
leitura), CONSTRÓI a entrada em banco (nunca via HTTP — objetivo aqui é a função, não o
endpoint) e afirma se `main._negociacao_breakdown` levanta ou não. Não presume pela leitura.

Cada teste documenta, no próprio nome e docstring, se a entrada testada é PRODUZÍVEL por um
usuário através dos endpoints reais (merge_parametros/merge_margens coagem tipo antes de
persistir) ou só alcançável por escrita direta no banco (bug de outro código, migração,
correção manual de suporte)."""
import json


def _breakdown_levanta(app_db, orc_id):
    """Roda _negociacao_breakdown numa sessão NOVA (como main.py sempre faz) e diz se levantou."""
    import main
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, orc_id)
        try:
            main._negociacao_breakdown(orc, db)
            return False, None
        except Exception as e:
            return True, e
    finally:
        db.close()


# ── candidato 1: parametros_json malformado ──────────────────────────────────────────────────
def test_parametros_json_malformado_levanta(app_db, seed):
    """`json.loads(proj.parametros_json)` (main.py:17258) NÃO tem try/except ao redor — CONFIRMADO
    que levanta com JSON malformado. MAS: os 3 pontos de escrita reais de parametros_json
    (main.py:1289, 10889, 17677) sempre usam `json.dumps` de um dict — nunca gravam string crua
    do usuário. Não produzível pelos endpoints modelados; só por escrita direta no banco (bug de
    outro código, migração, ou correção manual de suporte)."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    projeto_id = orc.projeto_id   # captura antes do commit expirar o atributo (detached)
    proj = db.query(app_db.Projeto).filter_by(nome_safe=projeto_id).first()
    proj.parametros_json = "{isto nao é json"
    db.commit(); db.close()

    try:
        levantou, exc = _breakdown_levanta(app_db, oid)
        assert levantou, "esperava json.loads malformado levantar — se não levantou, o candidato 1 caiu"
        assert isinstance(exc, json.JSONDecodeError)
    finally:
        # `seed`/`app_db` são module-scoped — sem isto, o parametros_json malformado
        # sobrevive pros outros testes deste arquivo, contaminando-os (achado ao rodar
        # este arquivo: os 8 testes seguintes "levantavam" só por causa deste resíduo).
        db = app_db.get_session()
        proj = db.query(app_db.Projeto).filter_by(nome_safe=projeto_id).first()
        proj.parametros_json = None
        db.commit(); db.close()


# ── candidato 2: forma_pagamento malformado ──────────────────────────────────────────────────
def test_forma_pagamento_json_malformado_nao_levanta(app_db, seed):
    """`json.loads(orc.forma_pagamento)` (main.py:17296-17301) está DENTRO de um try/except que
    cobre também o `float(...)` do total_cliente — guardado. A escrita real (`PATCH
    /orcamentos/<id>/valor`, main.py:15825) grava `json.dumps` de um dict também — mas este
    candidato testa robustez mesmo que não seja alcançável hoje."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.forma_pagamento = "{tambem nao é json"
    db.commit(); db.close()

    levantou, exc = _breakdown_levanta(app_db, oid)
    assert not levantou, "forma_pagamento malformado NÃO deveria levantar (guardado) — %r" % (exc,)


def test_forma_pagamento_total_cliente_nao_numerico_nao_levanta(app_db, seed):
    """total_cliente como string não numérica — mesmo try/except do candidato acima cobre o
    float() também. Não produzível pelo endpoint real (que sempre grava float), mas testa
    robustez da função para qualquer origem do dado."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.forma_pagamento = json.dumps({"tipo": "avista", "total_cliente": "abacate"})
    db.commit(); db.close()

    levantou, exc = _breakdown_levanta(app_db, oid)
    assert not levantou, "total_cliente não numérico NÃO deveria levantar (guardado) — %r" % (exc,)


# ── candidato 3: ambiente sem budget_total/order_total ───────────────────────────────────────
def test_ambiente_sem_budget_total_nao_levanta(app_db, seed):
    """PoolAmbiente.budget_total/order_total = None — main.py:17289-17290 usa `or 0.0`. Não
    produzível pelo upload real de XML (main.py:11727-11736 recusa XML sem item com preço
    visível — "nada para importar"), mas o campo do modelo permite NULL, então testo a função."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    pa = app_db.PoolAmbiente(projeto_id=orc.projeto_id, nome="SemValor", versao=1,
                             nome_exibicao="Sem Valor", xml_path="", ambientes_json="[]",
                             budget_total=None, order_total=None)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id))
    db.commit(); db.close()

    levantou, exc = _breakdown_levanta(app_db, oid)
    assert not levantou, "ambiente sem budget_total NÃO deveria levantar (guardado) — %r" % (exc,)


# ── candidato 4: complemento_pe sem contrato do projeto ──────────────────────────────────────
def test_complemento_pe_sem_contrato_nao_levanta(app_db, seed):
    """orc.complemento_pe=1 mas o projeto não tem NENHUM Contrato — `_complemento_diferencas`
    retorna (None, "erro"); main.py:17275 faz `for l in (linhas_c or [])` — guardado contra None.
    Orçamento NOVO, sem vínculo de contrato nenhum (ver candidato 4b abaixo para o caso do
    orçamento que JÁ É o do contrato do projeto — comportamento bem diferente)."""
    db = app_db.get_session()
    orc_novo = app_db.Orcamento(projeto_id=seed["projeto_l1"], nome="Complemento teste", ordem=9,
                                complemento_pe=1)
    db.add(orc_novo); db.commit()
    oid_novo = orc_novo.id
    db.close()

    levantou, exc = _breakdown_levanta(app_db, oid_novo)
    assert not levantou, "complemento_pe sem contrato NÃO deveria levantar (guardado) — %r" % (exc,)


def test_complemento_pe_no_proprio_orcamento_do_contrato_recursao_infinita(app_db, seed):
    """ACHADO DESTA MEDIÇÃO: `complemento_pe=1` setado no MESMO orçamento que é
    `Contrato.orcamento_id` do projeto (auto-referência) causa `RecursionError` — sem guarda de
    profundidade nenhuma. `_negociacao_breakdown` (orc, complemento_pe=1) → `_complemento_diferencas`
    → busca o Contrato do projeto → pega o MESMO orçamento (`ct.orcamento_id == orc.id`) →
    `_negociacao_breakdown(orc_ct, ...)` de novo → mesmo complemento_pe=1 → repete para sempre.

    Não confirmei um caminho de UI que produza esse estado (o endpoint real de criação de
    complemento sempre cria uma linha de Orcamento NOVA e separada — nunca marca
    complemento_pe=1 no orçamento que já é o do contrato) — mas nenhum código impede essa
    combinação de acontecer por outro caminho (correção manual, migração, bug futuro), e o
    resultado hoje é um RecursionError opaco, não um erro claro."""
    oid = seed["orcamento_l1_id"]   # este é o mesmo Orcamento de seed["contrato_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.complemento_pe = 1
    db.commit(); db.close()

    try:
        levantou, exc = _breakdown_levanta(app_db, oid)
        assert levantou and isinstance(exc, RecursionError), (
            "esperava RecursionError pela auto-referência — se isto mudou, o achado foi "
            "corrigido ou o desenho mudou: %r" % (exc,))
    finally:
        db = app_db.get_session()
        db.get(app_db.Orcamento, oid).complemento_pe = 0
        db.commit(); db.close()


# ── candidato 5: complemento_pe por fase, parcela_id sem decisões ────────────────────────────
def test_complemento_pe_fase_sem_decisoes_nao_levanta(app_db, seed):
    """orc.complemento_pe=1 + parcela_id setado, mas sem contrato (mesma guarda de
    `_pe_fator_contexto`, main.py:16780-16784) e sem nenhuma ConciliacaoPeFase — loop vazio,
    resumo com totais zerados. Orçamento novo, sem vínculo de contrato — mesmo cuidado do
    candidato 4 (auto-referência causaria RecursionError, não é o que este teste mede)."""
    db = app_db.get_session()
    parcela = app_db.ParcelaProjeto(projeto_nome=seed["projeto_l1"], ordem=1)
    db.add(parcela); db.flush()
    orc_novo = app_db.Orcamento(projeto_id=seed["projeto_l1"], nome="Complemento fase teste",
                                ordem=10, complemento_pe=1, parcela_id=parcela.id)
    db.add(orc_novo); db.commit()
    oid_novo = orc_novo.id
    db.close()

    levantou, exc = _breakdown_levanta(app_db, oid_novo)
    assert not levantou, "complemento por fase sem decisões NÃO deveria levantar (guardado) — %r" % (exc,)


# ── candidato 6: desconto_pct fora da faixa 0-100 ─────────────────────────────────────────────
def test_desconto_pct_maior_que_100_nao_levanta(app_db, seed):
    """orc.desconto_pct=150 (fora de 0-100): `fator_desc = (1-d_orc)*(1-d_amb)` fica NEGATIVO —
    resultado aritmeticamente sem sentido (VAVA negativo), mas NÃO levanta exceção nenhuma (não
    há guarda de RANGE, só de zero/negativo-como-denominador). Endpoints reais (`/margens`,
    `/descontos`) validam limite de desconto contra o perfil do usuário ANTES de persistir — um
    valor >100 exigiria autorização gerencial que provavelmente recusaria antes de chegar aqui;
    não confirmei se algum caminho aceita >100 sem checar."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.desconto_pct = 150.0
    db.commit(); db.close()

    levantou, exc = _breakdown_levanta(app_db, oid)
    assert not levantou, "desconto_pct=150 NÃO deveria levantar — %r" % (exc,)


# ── candidato 7: config_financeira_json malformado ───────────────────────────────────────────
def test_config_financeira_json_malformado_nao_levanta(app_db, seed):
    """`Loja.config_financeira_json` malformado — main.py:17250-17254 já tem try/except cobrindo
    exatamente isso (acompanhado de fallback pro default). Guardado."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    loja = db.get(app_db.Loja, orc.loja_id)
    loja.config_financeira_json = "{nao é json"
    db.commit(); db.close()

    levantou, exc = _breakdown_levanta(app_db, oid)
    assert not levantou, "config_financeira_json malformado NÃO deveria levantar (guardado) — %r" % (exc,)


# ── candidato 8: carga_trib — a hipótese da tarefa (divisão) não corresponde ao código ───────
def test_carga_trib_zero_nao_e_divisor(app_db, seed):
    """A tarefa lista "divisão por... carga tributária zerada" como candidato. Medido: NÃO existe
    tal divisão — mod_negociacao.py:30 usa `pct_trib = _f(carga_trib)/100.0` só como
    MULTIPLICADOR de `prov_imp = pct_trib * val_cont`. carga_trib=0 (ou None) não levanta e não
    é sequer um caminho de risco — a hipótese da tarefa não se confirma no código atual."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    proj = db.query(app_db.Projeto).filter_by(nome_safe=orc.projeto_id).first()
    proj.parametros_json = json.dumps({"incluir_custos": False, "carga_trib": 0.0})
    db.commit(); db.close()

    levantou, exc = _breakdown_levanta(app_db, oid)
    assert not levantou, "carga_trib=0 NÃO deveria levantar — %r" % (exc,)


def test_projeto_orfao_nao_levanta(app_db, seed):
    """orc.projeto_id aponta pra um Projeto que não existe (órfão) — main.py:17246-17259
    guarda com `if (proj and proj.parametros_json) else parametros_default_loja(cfg)`."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.projeto_id = "Projeto_Que_Nao_Existe_Xyz"
    db.commit(); db.close()

    levantou, exc = _breakdown_levanta(app_db, oid)
    assert not levantou, "projeto órfão NÃO deveria levantar (guardado) — %r" % (exc,)
