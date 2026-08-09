import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fiscal import mod_nfe as mn


def test_split_cprod_sob_medida():
    assert mn.split_cprod("50079[2131748]") == ("50079", "2131748", "sob_medida")
    assert mn.split_cprod("50057[2131751]") == ("50057", "2131751", "sob_medida")


def test_split_cprod_padrao():
    assert mn.split_cprod("80070") == ("80070", None, "padrao")
    assert mn.split_cprod("") == ("", None, "padrao")


def test_parse_infadprod_valido():
    assert mn.parse_infadprod("EBANO 622 600") == {"cor": "EBANO", "largura": 622, "altura": 600}
    assert mn.parse_infadprod("METROPOLITAN 2406 185") == {"cor": "METROPOLITAN", "largura": 2406, "altura": 185}


def test_parse_infadprod_nao_confiavel():
    # só-cor, cor+1-número, número-solto, vazio/None → None (não confiável)
    assert mn.parse_infadprod("MDF BP BRANCO") is None
    assert mn.parse_infadprod("FOSCO 2420") is None
    assert mn.parse_infadprod("970") is None
    assert mn.parse_infadprod("") is None
    assert mn.parse_infadprod(None) is None


import os as _os
_FIX = _os.path.join(_os.path.dirname(__file__), "fixtures", "nfe")

def _ler(nome):
    with open(_os.path.join(_FIX, nome), encoding="utf-8") as f:
        return f.read()


def test_parse_nfe_cabecalho():
    nfe = mn.parse_nfe(_ler("nfe_basica.xml"))
    cab = nfe["cabecalho"]
    assert cab["nNF"] == "170942" and cab["serie"] == "1"
    assert cab["emit"]["cnpj"] == "00000000000000" and cab["emit"]["crt"] == "3"
    assert cab["emit"]["nome"] == "FABRICA TESTE LTDA"
    assert cab["dest"]["nome"] == "LOJA TESTE LTDA" and cab["dest"]["doc"] == "11111111111111"


def test_parse_nfe_itens():
    itens = mn.parse_nfe(_ler("nfe_basica.xml"))["itens"]
    assert len(itens) == 3   # ainda NÃO consolidado
    i0 = itens[0]
    assert i0["cProd"] == "50079[2131748]" and i0["ncm"] == "94035000" and i0["cfop"] == "6101"
    assert i0["qCom"] == 1.0 and i0["vUnCom"] == 71.63 and i0["vProd"] == 71.63
    assert i0["vIPI"] == 3.58 and i0["infAdProd"] == "METROPOLITAN 2406 185"
    # item padrão sem infAdProd
    assert itens[2]["cProd"] == "80070" and itens[2]["infAdProd"] is None


def test_parse_nfe_aceita_bytes():
    itens = mn.parse_nfe(_ler("nfe_basica.xml").encode("utf-8"))["itens"]
    assert len(itens) == 3


def test_parse_nfe_sem_ipi_e_cpf_e_nfe_puro():
    nfe = mn.parse_nfe(_ler("nfe_sem_ipi.xml"))
    assert nfe["cabecalho"]["dest"]["doc"] == "00000000000"   # CPF
    it = nfe["itens"][0]
    assert it["vIPI"] == 0.0 and it["vProd"] == 50.0


# ── XML inválido/placeholder → ValueError tratado, não AttributeError/ParseError crus ──────────
# (achado da Vera, 2026-08-09: um XML placeholder na emissão de NF-e em homolog vazava
# "'NoneType' object has no attribute 'find'" como 500 pro cliente HTTP)
import pytest


def test_parse_nfe_xml_mal_formado_vira_value_error():
    with pytest.raises(ValueError, match="não é um XML bem formado"):
        mn.parse_nfe("isto não é xml <<<")


def test_parse_nfe_sem_infnfe_vira_value_error():
    with pytest.raises(ValueError, match="infNFe"):
        mn.parse_nfe("<algumaCoisa><x>1</x></algumaCoisa>")


def test_consolidar_soma_duplicados():
    itens = [
        {"cProd": "50079[2131748]", "xProd": "X", "ncm": "9403", "cfop": "6101", "uCom": "UN",
         "qCom": 1.0, "vUnCom": 71.63, "vProd": 71.63, "vIPI": 3.58, "infAdProd": "METROPOLITAN 2406 185"},
        {"cProd": "50079[2131748]", "xProd": "X", "ncm": "9403", "cfop": "6101", "uCom": "UN",
         "qCom": 1.0, "vUnCom": 71.63, "vProd": 71.63, "vIPI": 3.58, "infAdProd": "METROPOLITAN 2406 185"},
        {"cProd": "50057[2131751]", "xProd": "Y", "ncm": "9403", "cfop": "6101", "uCom": "UN",
         "qCom": 1.0, "vUnCom": 29.83, "vProd": 29.83, "vIPI": 1.49, "infAdProd": None},
    ]
    out = mn.consolidar(itens)
    assert len(out) == 2                       # duplicata somada; BASE igual mas [ID] diferente NÃO junta
    assert out[0]["cProd"] == "50079[2131748]" and out[0]["qCom"] == 2.0
    assert round(out[0]["vProd"], 2) == 143.26 and round(out[0]["vIPI"], 2) == 7.16
    assert out[1]["cProd"] == "50057[2131751]" and out[1]["qCom"] == 1.0


def test_precificar_custo_e_markup():
    consol = [{"cProd": "50079[2131748]", "xProd": "X", "ncm": "9403", "cfop": "6101", "uCom": "UN",
               "qCom": 2.0, "vUnCom": 71.63, "vProd": 143.26, "vIPI": 7.16, "infAdProd": "METROPOLITAN 2406 185"}]
    out = mn.precificar(consol, 30.0)
    p = out[0]
    assert p["tipo"] == "sob_medida" and p["base"] == "50079" and p["id_peca"] == "2131748"
    assert p["custo_unit"] == 75.21                      # (143.26+7.16)/2
    assert p["preco_venda_unit"] == 97.77                # round(75.21*1.30, 2)
    assert p["cor"] == "METROPOLITAN" and p["largura"] == 2406 and p["altura"] == 185


def test_precificar_sem_ipi_e_padrao():
    consol = [{"cProd": "80070", "xProd": "C", "ncm": "8302", "cfop": "6101", "uCom": "UN",
               "qCom": 1.0, "vUnCom": 50.0, "vProd": 50.0, "vIPI": 0.0, "infAdProd": None}]
    p = mn.precificar(consol, 30.0)[0]
    assert p["tipo"] == "padrao" and p["id_peca"] is None
    assert p["custo_unit"] == 50.0 and p["preco_venda_unit"] == 65.0
    assert p["cor"] is None and p["largura"] is None


def test_preview_end_to_end():
    pv = mn.preview(_ler("nfe_basica.xml"), 30.0)
    t = pv["totais"]
    assert t["n_linhas"] == 3 and t["n_distintos"] == 2
    assert t["n_padrao"] == 1 and t["n_sob_medida"] == 1
    assert t["custo_total"] == 171.42     # 75.21*2 + 10.50*2
    assert t["venda_total"] == 222.84     # 97.77*2 + 13.65*2
    assert pv["markup_pct"] == 30.0
    assert pv["cabecalho"]["nNF"] == "170942"
    # item consolidado sob-medida com dimensão parseada
    sob = [i for i in pv["itens"] if i["tipo"] == "sob_medida"][0]
    assert sob["qCom"] == 2.0 and sob["preco_venda_unit"] == 97.77 and sob["altura"] == 185


def test_preview_infadprod_ausente_nao_quebra():
    pv = mn.preview(_ler("nfe_basica.xml"), 10.0)
    padrao = [i for i in pv["itens"] if i["tipo"] == "padrao"][0]
    assert padrao["cor"] is None and padrao["largura"] is None   # sem infAdProd → dim None, sem erro
