# -*- coding: utf-8 -*-
"""Confirmação de contatos na fase de contrato (decisão 13 da spec de chat, antecipada como
mini-frente em 2026-07-25): no ato do contrato o operador VÊ os contatos de comunicação
(cliente e arquiteto, se houver) e escolhe explicitamente — 'confirmado' ou 'sem_whatsapp'
("seguir sem WhatsApp", aceito pelo usuário). Gate BLOQUEANTE-SUAVE no POST do contrato:
sem uma confirmação registrada, o contrato não é gerado (codigo 'contatos_nao_confirmados'
p/ o frontend abrir o modal); com QUALQUER um dos dois modos, passa. Contatos sempre lidos
do CADASTRO no momento da leitura (decisão 12)."""


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def test_get_contatos_lista_cliente_e_sem_confirmacao(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/projetos/Proj_L1/contatos-comunicacao")
    assert st == 200 and body["ok"], body
    papeis = {x["papel"]: x for x in body["contatos"]}
    assert "cliente" in papeis and papeis["cliente"]["nome"] == "Cliente L1"
    assert "whatsapp" in papeis["cliente"]           # campo presente mesmo vazio (UI avisa)
    assert body["confirmacao"] is None               # nunca confirmado


def test_confirmar_modos_e_registro_de_quem_quando(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/Proj_L1/contatos-comunicacao/confirmar", {"modo": "banana"})
    assert st == 400, body                            # modo inválido
    st, body = c.post("/api/projetos/Proj_L1/contatos-comunicacao/confirmar",
                      {"modo": "sem_whatsapp"})
    assert st == 200 and body["ok"], body
    st, body = c.get("/api/projetos/Proj_L1/contatos-comunicacao")
    conf = body["confirmacao"]
    assert conf["modo"] == "sem_whatsapp"
    assert conf["confirmado_por_nome"] == "Diretor L1" and conf["confirmado_em"]
    # nova confirmação substitui a vigente (histórico append-only, a mais recente vale)
    c.post("/api/projetos/Proj_L1/contatos-comunicacao/confirmar", {"modo": "confirmado"})
    st, body = c.get("/api/projetos/Proj_L1/contatos-comunicacao")
    assert body["confirmacao"]["modo"] == "confirmado"


def test_gate_no_post_do_contrato(http_client_factory, seed):
    """Sem confirmação → o POST do contrato devolve o codigo específico; depois de declarar
    'seguir sem WhatsApp', o gate abre (a geração segue adiante — qualquer erro posterior
    é de outra natureza, não deste gate)."""
    c = _login(http_client_factory, "dir_l2")         # Proj_L2 nunca confirmou
    st, body = c.post("/api/projetos/Proj_L2/contrato",
                      {"orcamento_id": seed["orcamento_l2_id"]})
    assert st == 400 and body.get("codigo") == "contatos_nao_confirmados", body
    st, body = c.post("/api/projetos/Proj_L2/contatos-comunicacao/confirmar",
                      {"modo": "sem_whatsapp"})
    assert st == 200, body
    st, body = c.post("/api/projetos/Proj_L2/contrato",
                      {"orcamento_id": seed["orcamento_l2_id"]})
    assert body.get("codigo") != "contatos_nao_confirmados", body


def test_tenancy_e_login(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    assert c.get("/api/projetos/Proj_L1/contatos-comunicacao")[0] == 404
    c2 = http_client_factory()
    assert c2.get("/api/projetos/Proj_L1/contatos-comunicacao")[0] == 401


def test_whatsapp_do_cliente_vem_do_campo_proprio(http_client_factory, seed, app_db):
    """O cadastro de Cliente TEM campo whatsapp (ponta a ponta) — o contato de comunicação
    usa ele; telefone é só fallback quando o WhatsApp está vazio."""
    db = app_db.get_session()
    c = db.get(app_db.Cliente, seed["cliente_l1_id"])
    c.telefone = "(12) 1111-1111"
    c.whatsapp = "(12) 99999-8888"
    db.commit(); db.close()
    cli = _login(http_client_factory, "dir_l1")
    st, body = cli.get("/api/projetos/Proj_L1/contatos-comunicacao")
    papeis = {x["papel"]: x for x in body["contatos"]}
    assert papeis["cliente"]["whatsapp"] == "(12) 99999-8888"   # campo próprio, não o telefone
    db = app_db.get_session()
    db.get(app_db.Cliente, seed["cliente_l1_id"]).whatsapp = None
    db.commit(); db.close()
    st, body = cli.get("/api/projetos/Proj_L1/contatos-comunicacao")
    papeis = {x["papel"]: x for x in body["contatos"]}
    assert papeis["cliente"]["whatsapp"] == "(12) 1111-1111"    # fallback: telefone
