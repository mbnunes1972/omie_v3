import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fiscal import mod_fiscal as mf


def test_emitente_padrao_teste():
    p = mf.emitente_padrao_teste()
    assert p["regime_tributario"] == "simples" and p["csosn_padrao"] == "102"
    assert p["cfop_dentro_uf"] == "5102" and p["cfop_fora_uf"] == "6102"
    assert p["aliquota_iss"] == 5.0 and p["papel_cnpj"] == "loja_produto_servico"
    for chave in ("regime_tributario", "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf",
                  "cnae_servico", "aliquota_iss"):
        assert chave in p["placeholders"]


def test_validar_config_ok():
    ok, erro = mf.validar_config({"regime_tributario": "simples", "papel_cnpj": "avulso",
                                  "aliquota_iss": 5})
    assert ok is True and erro == ""


def test_validar_config_regime_invalido():
    ok, erro = mf.validar_config({"regime_tributario": "lucro_marciano"})
    assert ok is False and "regime" in erro


def test_validar_config_papel_invalido():
    ok, erro = mf.validar_config({"papel_cnpj": "imperador"})
    assert ok is False and "papel" in erro


def test_validar_config_iss_fora_faixa():
    ok, erro = mf.validar_config({"aliquota_iss": 150})
    assert ok is False and "iss" in erro.lower()
    ok2, _ = mf.validar_config({"aliquota_iss": "abc"})
    assert ok2 is False


def test_pode_ativar_producao():
    assert mf.pode_ativar_producao([]) is True
    assert mf.pode_ativar_producao(["regime_tributario"]) is False


# ── prontidao_emitente (US-42 / auditoria A2/A3/A5) ───────────────────────────
from types import SimpleNamespace


def _emit_pronto_produto(**kw):
    # Bloco fiscal item 4 (03/09, DECIDIDO: BARRAR) — prontidao_emitente passou a exigir a lista
    # inteira de identificação + endereço no ramo produto; este fixture nasce COMPLETO sob a
    # regra nova (era só regime+UF+IE antes do achado).
    base = dict(regime_tributario="simples", uf="SP", inscricao_estadual="123", cnpj="19152134000156",
                csosn_padrao="102", csosn_contribuinte="101", cfop_dentro_uf="5102", cfop_fora_uf="6102",
                municipio_ibge="3550308", ambiente_ativo="homologacao", focus_token_homolog_enc="tok",
                logradouro="Rua A", numero="1", bairro="Centro", cidade="Sao Paulo", cep="01000-000")
    base.update(kw); return SimpleNamespace(**base)


def _emit_pronto_servico(**kw):
    base = dict(regime_tributario="simples", inscricao_municipal="322176",
                municipio_ibge="3549904", cod_servico_municipio="14.13.03", aliquota_iss=5.0)
    base.update(kw); return SimpleNamespace(**base)


def test_prontidao_produto_ok():
    assert mf.prontidao_emitente(_emit_pronto_produto(), "produto") is None


def test_prontidao_produto_regime_nao_simples_barra():
    e = mf.prontidao_emitente(_emit_pronto_produto(regime_tributario="normal"), "produto")
    assert e and "Simples" in e


def test_prontidao_produto_uf_vazia_barra():
    for uf in (None, "", "  "):
        e = mf.prontidao_emitente(_emit_pronto_produto(uf=uf), "produto")
        assert e and "UF" in e


def test_prontidao_servico_ok():
    assert mf.prontidao_emitente(_emit_pronto_servico(), "servico") is None


def test_prontidao_servico_sem_im_barra():
    e = mf.prontidao_emitente(_emit_pronto_servico(inscricao_municipal=None), "servico")
    assert e and "Inscrição Municipal" in e


# ── Bloco fiscal item 4 (03/09, DECIDIDO: BARRAR) — extensão do ramo produto ──────────────────

def test_prontidao_produto_identificacao_incompleta_nomeia_campo_a_campo():
    e = mf.prontidao_emitente(_emit_pronto_produto(cnpj=None, csosn_padrao="", csosn_contribuinte=None), "produto")
    assert e and "identificação" in e
    assert "CNPJ" in e and "CSOSN padrão" in e and "CSOSN contribuinte" in e


def test_prontidao_produto_token_ambiente_ativo_faltando_barra():
    e = mf.prontidao_emitente(_emit_pronto_produto(focus_token_homolog_enc=None), "produto")
    assert e and "token" in e.lower() and "homologacao" in e
    e2 = mf.prontidao_emitente(_emit_pronto_produto(ambiente_ativo="producao", focus_token_prod_enc=None),
                               "produto")
    assert e2 and "producao" in e2


def test_prontidao_produto_endereco_incompleto_nomeia_campo_a_campo():
    e = mf.prontidao_emitente(_emit_pronto_produto(logradouro=None, cep=""), "produto")
    assert e and "endereço" in e
    assert "logradouro" in e and "CEP" in e


def test_prontidao_produto_csosn_exigivel_mesmo_com_tudo_mais_completo():
    # Regra do item 4: CSOSN não é condicional ao regime (o gate de regime já garante Simples) —
    # com tudo mais completo, faltar só o CSOSN ainda barra.
    e = mf.prontidao_emitente(_emit_pronto_produto(csosn_padrao=None), "produto")
    assert e and "CSOSN padrão" in e


# ── prontidao_destinatario (função IRMÃ, não mistura Cliente em prontidao_emitente) ───────────

def _cliente_pronto(**kw):
    base = dict(logradouro="Rua B", numero="2", bairro="Jardim", cidade="Sao Paulo",
                estado="SP", cep="02000-000")
    base.update(kw); return SimpleNamespace(**base)


def test_prontidao_destinatario_ok():
    assert mf.prontidao_destinatario(_cliente_pronto()) is None


def test_prontidao_destinatario_endereco_incompleto_nomeia_campo_a_campo():
    e = mf.prontidao_destinatario(_cliente_pronto(logradouro=None, estado="", cep=None))
    assert e and "logradouro" in e and "estado" in e and "CEP" in e
    # F2-23 (04/09): a recusa se explica sozinha — o que bloqueou, por quê, qual é a saída.
    assert "não pode ser emitida" in e
    assert "Complete o cadastro do cliente" in e


def test_prontidao_destinatario_nao_confere_uf_generico_de_instalacao():
    # Cliente não tem coluna uf — só 'estado'. Um objeto com 'inst_uf' preenchido mas sem
    # 'estado' continua incompleto (a nota nunca lê o endereço de instalação).
    cli = _cliente_pronto(estado=None)
    cli.inst_uf = "SP"
    e = mf.prontidao_destinatario(cli)
    assert e and "estado" in e


def test_prontidao_servico_sem_ibge_ou_cod_ou_iss_barra():
    assert mf.prontidao_emitente(_emit_pronto_servico(municipio_ibge=""), "servico")
    assert mf.prontidao_emitente(_emit_pronto_servico(cod_servico_municipio=None), "servico")
    assert mf.prontidao_emitente(_emit_pronto_servico(aliquota_iss=None), "servico")
