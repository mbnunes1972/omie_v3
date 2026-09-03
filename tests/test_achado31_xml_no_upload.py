"""ACHADO-31 / TAREFA_BLOCO_FISCAL item 2 — o XML da fábrica só era validado na EMISSÃO, dois
passos depois do upload. Quem anexava um arquivo ruim recebia "ok"; a recusa aparecia na etapa
15, sem dizer que o problema era o arquivo carregado lá atrás.

O parser sempre esteve bom — `parse_nfe` já sabia recusar XML mal formado e XML sem `<infNFe>`
com mensagem clara. O que faltava era a validação estar no lugar certo. Aqui ela passa a rodar
NO UPLOAD, no mesmo desenho do ACHADO-44 (`consistencia_interna`): trava prospectiva, só na
porta de entrada, nunca retroativa — documento já carregado antes dela continua sendo conferido
na emissão, que segue parseando por conta própria.

Medido antes de travar (03/09): os 5 XML conhecidos — os 3 reais da fábrica (195, 89 e 13
linhas) e as 2 fixtures sintéticas — passam inteiros, com ZERO itens sem NCM, sem CFOP, sem
unidade ou com quantidade zerada. A trava não rejeitaria nenhum arquivo real conhecido.
"""
import sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fiscal import mod_nfe

from tests.test_nfe_etapa15_e2e import (_login, _upload_xml, _fixture_xml, _perfil, _reset15)

_DIR_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "nfe")

_SEM_INFNFE = b"<?xml version='1.0'?><qualquer><coisa/></qualquer>"
_SEM_ITENS = (b"<?xml version='1.0'?><nfeProc><NFe><infNFe><ide><nNF>1</nNF></ide>"
              b"<emit><xNome>F</xNome></emit><dest><xNome>C</xNome></dest></infNFe></NFe></nfeProc>")


def _com_item(extra_prod="", q="1.0"):
    return ("<?xml version='1.0'?><nfeProc><NFe><infNFe><ide><nNF>1</nNF></ide>"
            "<emit><xNome>F</xNome></emit><dest><xNome>C</xNome></dest>"
            "<det nItem='1'><prod><cProd>X</cProd><xProd>Item</xProd>"
            + extra_prod +
            "<qCom>" + q + "</qCom><vUnCom>10.00</vUnCom><vProd>10.00</vProd></prod></det>"
            "</infNFe></NFe></nfeProc>").encode()


_COMPLETO = "<NCM>94035000</NCM><CFOP>6101</CFOP><uCom>UN</uCom>"


# ── a medição, travada como teste ────────────────────────────────────────────
def test_medicao_todos_os_xml_conhecidos_passam():
    """A trava só vale se não recusar o que hoje é legítimo. As fixtures sintéticas estão no
    repositório; os 3 XML REAIS da fábrica não estão rastreados (decisão pendente do Marcelo),
    então são conferidos quando existem na bancada e ignorados quando não — sem transformar a
    ausência deles em falha de suíte em outra máquina."""
    conhecidos = sorted(glob.glob(os.path.join(_DIR_FIX, "*.xml")))
    assert conhecidos, "as fixtures sintéticas têm que estar no repositório"
    for caminho in conhecidos:
        with open(caminho, "rb") as f:
            ok, problemas = mod_nfe.problemas_de_upload(f.read())
        assert ok, "%s deveria passar, recusado por: %s" % (os.path.basename(caminho), problemas)


# ── o que a porta passa a recusar ────────────────────────────────────────────
def test_xml_mal_formado_e_recusado_nomeando_o_arquivo():
    ok, probs = mod_nfe.problemas_de_upload(b"isto nao e xml")
    assert not ok and any("bem formado" in p for p in probs), probs


def test_xml_sem_infnfe_e_recusado():
    ok, probs = mod_nfe.problemas_de_upload(_SEM_INFNFE)
    assert not ok and any("infNFe" in p for p in probs), probs


def test_nota_sem_item_nenhum_e_recusada():
    """Parseia, mas não há o que emitir — o caso que passava no upload e morria na emissão."""
    ok, probs = mod_nfe.problemas_de_upload(_SEM_ITENS)
    assert not ok and any("item" in p for p in probs), probs


def test_item_sem_ncm_cfop_ou_unidade_e_recusado_nomeando_o_item():
    """Os quatro campos que a SEFAZ cobra. A regra do item 4 do mesmo bloco, aplicada ao item:
    erro de schema da SEFAZ é falha NOSSA de validação — a nota não deve chegar lá para
    descobrir que o campo estava vazio."""
    ok, probs = mod_nfe.problemas_de_upload(_com_item(""))
    assert not ok
    juntos = "; ".join(probs)
    for esperado in ("NCM", "CFOP", "unidade"):
        assert esperado in juntos, (esperado, juntos)
    assert "item 1" in juntos, "a recusa nomeia qual item está furado: %s" % juntos


def test_item_com_quantidade_zerada_e_recusado():
    ok, probs = mod_nfe.problemas_de_upload(_com_item(_COMPLETO, q="0"))
    assert not ok and any("quantidade" in p for p in probs), probs


def test_item_completo_passa():
    ok, probs = mod_nfe.problemas_de_upload(_com_item(_COMPLETO))
    assert ok, probs


# ── o aceite do achado: a recusa acontece NO UPLOAD ──────────────────────────
def test_aceite_upload_recusa_o_xml_ruim_e_nao_grava_documento(http_client_factory, seed, app_db, projetos_dir):
    """O aceite: antes desta mudança o upload respondia 200 e gravava o documento; a recusa vinha
    dois passos depois, na emissão. Agora para na porta — e não deixa documento nenhum para trás."""
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _upload_xml(c, proj, b"nao sou um xml de nota fiscal")
    assert st == 400, (st, b)
    assert "recusado" in (b.get("erro") or ""), b
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 == 200
    assert not (g.get("fabrica_xmls") or []), "upload recusado não pode deixar documento gravado"


def test_aceite_upload_continua_aceitando_o_xml_legitimo(http_client_factory, seed, app_db, projetos_dir):
    """A outra metade: a trava não pode fechar a porta do arquivo bom."""
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _upload_xml(c, proj, _fixture_xml())
    assert st == 200 and b.get("documento_id"), b
