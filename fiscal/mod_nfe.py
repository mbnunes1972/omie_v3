"""mod_nfe.py — parser + precificação do XML da NF-e da fábrica (Fase 1).
Puro: sem rede, sem banco. Produz a estrutura de preview consumida pelas fases seguintes."""
import re
import xml.etree.ElementTree as ET

MARKUP_TESTE_PADRAO = 30.0   # % — valor de teste do CLI; a origem real do markup é config (fases 2+)

_RE_CPROD = re.compile(r'^(.+?)\[([^\]]+)\]$')


def split_cprod(cprod):
    """'50079[2131748]' -> ('50079','2131748','sob_medida'); '80070' -> ('80070', None, 'padrao')."""
    m = _RE_CPROD.match(cprod or "")
    if m:
        return (m.group(1), m.group(2), "sob_medida")
    return (cprod or "", None, "padrao")


def parse_infadprod(texto):
    """'COR LARGURA ALTURA' -> {cor,largura,altura} SÓ quando os 2 últimos tokens são inteiros.
    Caso contrário None (o campo é não-confiável na prática). Nunca levanta."""
    if not texto:
        return None
    toks = texto.split()
    if len(toks) >= 3 and toks[-1].isdigit() and toks[-2].isdigit():
        return {"cor": " ".join(toks[:-2]), "largura": int(toks[-2]), "altura": int(toks[-1])}
    return None


def _strip_ns(xml_text):
    """Remove os atributos xmlns (default e prefixados) — a NF-e usa um único namespace
    default; sem ele os finds ficam simples (mesma tática usada ao inspecionar o XML real)."""
    return re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_text)


def _txt(el, path, default=None):
    if el is None:
        return default
    x = el.find(path)
    return x.text if (x is not None and x.text is not None) else default


def parse_nfe(xml):
    """XML (str|bytes) da NF-e da fábrica -> {'cabecalho': {...}, 'itens': [...]}.
    Namespace-aware (localiza infNFe sob nfeProc OU NFe puro). vIPI ausente -> 0.0.
    Levanta ValueError (não AttributeError/ParseError) pra XML mal formado ou sem <infNFe> —
    os dois endpoints de emissão (main.py) só tratam ValueError como 400; sem isso, um XML
    inválido/placeholder vazava exceção crua pro cliente como 500 (achado da Vera, 2026-08-09)."""
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8")
    try:
        root = ET.fromstring(_strip_ns(xml))
    except ET.ParseError as e:
        raise ValueError("XML da fábrica inválido: não é um XML bem formado (" + str(e) + ").")
    inf = root if root.tag == "infNFe" else root.find(".//infNFe")
    if inf is None:
        raise ValueError("XML da fábrica inválido: não encontrei o bloco <infNFe> da NF-e.")
    ide, emit, dest = inf.find("ide"), inf.find("emit"), inf.find("dest")
    cabecalho = {
        "nNF": _txt(ide, "nNF"), "serie": _txt(ide, "serie"),
        "dhEmi": _txt(ide, "dhEmi"), "natOp": _txt(ide, "natOp"),
        "emit": {"cnpj": _txt(emit, "CNPJ"), "nome": _txt(emit, "xNome"), "crt": _txt(emit, "CRT")},
        "dest": {"nome": _txt(dest, "xNome"), "doc": _txt(dest, "CNPJ") or _txt(dest, "CPF")},
        # ACHADO-51 (04/09): chave de acesso — o Id de <infNFe> ("NFe" + 44 dígitos). É o que
        # identifica a nota DE VERDADE (o mesmo documento chega com nomes de arquivo diferentes) —
        # nunca deduplicar por nome_original.
        "chave": inf.get("Id"),
    }
    itens = []
    for det in inf.findall("det"):
        prod, imp = det.find("prod"), det.find("imposto")
        vipi = imp.find(".//vIPI") if imp is not None else None
        infad = det.find("infAdProd")
        itens.append({
            "nItem": det.get("nItem"),
            "cProd": _txt(prod, "cProd"),
            "xProd": _txt(prod, "xProd"),
            "ncm": _txt(prod, "NCM"),
            "cfop": _txt(prod, "CFOP"),
            "uCom": _txt(prod, "uCom"),
            "qCom": float(_txt(prod, "qCom", "0") or 0),
            "vUnCom": float(_txt(prod, "vUnCom", "0") or 0),
            "vProd": float(_txt(prod, "vProd", "0") or 0),
            "vIPI": float(vipi.text) if (vipi is not None and vipi.text) else 0.0,
            "infAdProd": infad.text if infad is not None else None,
        })
    return {"cabecalho": cabecalho, "itens": itens}


def consolidar(itens):
    """Agrupa por cProd (na mesma NF-e), somando qCom/vProd/vIPI. Mantém os campos estáticos
    (xProd, ncm, cfop, uCom, vUnCom, infAdProd) da 1ª ocorrência. Preserva a ordem de aparição."""
    ordem, por_cod = [], {}
    for it in itens:
        cod = it["cProd"]
        if cod not in por_cod:
            por_cod[cod] = dict(it)
            ordem.append(cod)
        else:
            ac = por_cod[cod]
            ac["qCom"] += it["qCom"]
            ac["vProd"] += it["vProd"]
            ac["vIPI"] += it["vIPI"]
    return [por_cod[c] for c in ordem]


def precificar(itens_consolidados, markup_pct):
    """Custo unitário = (vProd + vIPI) / qCom; preco_venda_unit = round(custo * (1+pct/100), 2).
    Anexa base/id_peca/tipo (split_cprod) e cor/largura/altura (parse_infadprod)."""
    fator = 1 + (markup_pct / 100.0)
    out = []
    for it in itens_consolidados:
        base, id_peca, tipo = split_cprod(it["cProd"])
        q = it["qCom"] or 0
        custo = (it["vProd"] + it["vIPI"]) / q if q else 0.0
        dim = parse_infadprod(it.get("infAdProd"))
        out.append({
            "cProd": it["cProd"], "base": base, "id_peca": id_peca, "tipo": tipo,
            "xProd": it.get("xProd"), "ncm": it.get("ncm"), "cfop": it.get("cfop"), "uCom": it.get("uCom"),
            "qCom": it["qCom"], "vUnCom": it.get("vUnCom"), "vProd": it["vProd"], "vIPI": it["vIPI"],
            "custo_unit": round(custo, 2), "preco_venda_unit": round(custo * fator, 2),
            "cor": dim["cor"] if dim else None,
            "largura": dim["largura"] if dim else None,
            "altura": dim["altura"] if dim else None,
            "infAdProd": it.get("infAdProd"),
        })
    return out


def preview(xml, markup_pct):
    """Pipeline completo: parse -> consolida -> precifica. Estrutura de handoff + totais."""
    nfe = parse_nfe(xml)
    itens = nfe["itens"]
    consol = consolidar(itens)
    precificados = precificar(consol, markup_pct)
    return {
        "cabecalho": nfe["cabecalho"],
        "markup_pct": markup_pct,
        "itens": precificados,
        "totais": {
            "n_linhas": len(itens),
            "n_distintos": len(consol),
            "n_padrao": sum(1 for p in precificados if p["tipo"] == "padrao"),
            "n_sob_medida": sum(1 for p in precificados if p["tipo"] == "sob_medida"),
            "custo_total": round(sum(p["custo_unit"] * p["qCom"] for p in precificados), 2),
            "venda_total": round(sum(p["preco_venda_unit"] * p["qCom"] for p in precificados), 2),
        },
    }


_CAMPOS_OBRIGATORIOS = (
    ("ncm",  "NCM",      "sem NCM"),
    ("cfop", "CFOP",     "sem CFOP"),
    ("uCom", "unidade",  "sem unidade comercial"),
)


def problemas_de_upload(xml):
    """ACHADO-31 (docs/db/TAREFA_BLOCO_FISCAL.md item 2) — o XML da fábrica conferido NO UPLOAD,
    não dois passos depois na emissão. Hoje o upload aceita qualquer arquivo e quem recusa é
    `preview`, na etapa 15, com uma mensagem que não diz que o problema é o arquivo que alguém
    anexou lá atrás. O parser sempre esteve bom — faltava a validação estar no lugar certo.

    Mesmo formato de `integracoes.promob_grupos.consistencia_interna` (ACHADO-44): devolve
    `(ok, problemas)`, `problemas` é lista de strings e fica vazia quando `ok`. Quem chama é
    quem decide o que fazer com isso — aqui, o upload da etapa 15 recusa com 400.

    O que recusa, e por quê: XML mal formado ou sem `<infNFe>` (o `parse_nfe` já sabia dizer
    isso, ninguém escutava no momento certo); nota sem nenhum item, que parseia mas não tem o
    que emitir; e item sem NCM, CFOP, unidade ou com quantidade não positiva — os quatro que a
    SEFAZ cobra e cuja falta hoje só aparece como erro de schema na emissão. É a regra do item 4
    do mesmo bloco aplicada ao item: **erro de schema da SEFAZ é falha nossa de validação**.

    Medido antes de travar (03/09), nos 5 XML disponíveis — os 3 reais da fábrica (195, 89 e 13
    linhas) e as 2 fixtures sintéticas: **zero** itens sem NCM, sem CFOP, sem unidade ou com
    quantidade zerada. A trava não rejeitaria nenhum arquivo real conhecido."""
    try:
        nfe = parse_nfe(xml)
    except ValueError as e:
        return False, [str(e)]
    itens = nfe.get("itens") or []
    if not itens:
        return False, ["a nota não tem nenhum item (<det>) — não há o que emitir a partir dela"]
    faltas = {rotulo: [] for _campo, rotulo, _frase in _CAMPOS_OBRIGATORIOS}
    faltas["quantidade"] = []
    for it in itens:
        n = str(it.get("nItem") or "?")
        for campo, rotulo, _frase in _CAMPOS_OBRIGATORIOS:
            if not str(it.get(campo) or "").strip():
                faltas[rotulo].append(n)
        if not (it.get("qCom") or 0) > 0:
            faltas["quantidade"].append(n)
    frases = {r: f for _c, r, f in _CAMPOS_OBRIGATORIOS}
    frases["quantidade"] = "com quantidade zerada ou negativa"
    problemas = []
    for rotulo in ("NCM", "CFOP", "unidade", "quantidade"):
        ruins = faltas.get(rotulo) or []
        if ruins:
            amostra = ", ".join(ruins[:5]) + ("…" if len(ruins) > 5 else "")
            problemas.append("%d item(ns) %s (item %s)" % (len(ruins), frases[rotulo], amostra))
    return (not problemas), problemas


def _valor_bruto_item(it, vun=None):
    """Valor bruto do item como a nota fiscal calcula (mapa_fiscal.montar_payload):
    round(qCom · preco_venda_unit, 2)."""
    if vun is None:
        vun = it.get("preco_venda_unit") or 0
    return round((it.get("qCom") or 0) * vun, 2)


def rescalar_itens_para_total(itens, total_alvo):
    """FASE B2.3: reescala o preço unitário dos itens da NF-e para que Σ round(qCom·preco_venda_unit, 2)
    == `total_alvo` EXATO (a mesma soma que a nota usa). Aplica o fator = total_alvo / total_atual a
    cada item e faz o ÚLTIMO item com quantidade > 0 absorver o resíduo de arredondamento (fecha ao
    centavo). Se o total atual ou o alvo forem <= 0, devolve os itens inalterados. NÃO muta a lista
    original. Usado para alinhar a face da NF-e à parcela Mercadoria (pct_merc × Val_Cont)."""
    total_alvo = round(float(total_alvo or 0), 2)
    atual = round(sum(_valor_bruto_item(it) for it in itens), 2)
    if atual <= 0 or total_alvo <= 0:
        return [dict(it) for it in itens]
    fator = total_alvo / atual
    idx_ultimo = None
    for i, it in enumerate(itens):
        if (it.get("qCom") or 0) > 0:
            idx_ultimo = i
    out = [dict(it) for it in itens]
    acum = 0.0
    for i, it in enumerate(out):
        q = it.get("qCom") or 0
        if q > 0 and i != idx_ultimo:
            it["preco_venda_unit"] = round((it.get("preco_venda_unit") or 0) * fator, 6)
            acum = round(acum + _valor_bruto_item(it), 2)
    if idx_ultimo is not None:
        q = out[idx_ultimo].get("qCom") or 0
        resto = round(total_alvo - acum, 2)                     # o que falta p/ fechar no alvo
        out[idx_ultimo]["preco_venda_unit"] = round(resto / q, 6) if q else 0.0
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("uso: python3 mod_nfe.py <arquivo.xml> [markup_pct]")
        sys.exit(1)
    _pct = float(sys.argv[2]) if len(sys.argv) > 2 else MARKUP_TESTE_PADRAO
    with open(sys.argv[1], encoding="utf-8") as _f:
        _pv = preview(_f.read(), _pct)
    _cab = _pv["cabecalho"]
    print("NF-e %s serie %s | emit %s (CRT %s) | markup %.1f%%"
          % (_cab.get("nNF"), _cab.get("serie"), _cab["emit"].get("nome"), _cab["emit"].get("crt"), _pct))
    print("%-22s %-11s %7s %10s %10s  %s" % ("cProd", "tipo", "qtd", "custo_un", "venda_un", "xProd"))
    for _it in _pv["itens"]:
        print("%-22s %-11s %7.2f %10.2f %10.2f  %s"
              % (_it["cProd"], _it["tipo"], _it["qCom"], _it["custo_unit"],
                 _it["preco_venda_unit"], (_it["xProd"] or "")[:30]))
    _t = _pv["totais"]
    print("-" * 78)
    print("linhas=%d distintos=%d padrao=%d sob_medida=%d | custo_total=%.2f venda_total=%.2f"
          % (_t["n_linhas"], _t["n_distintos"], _t["n_padrao"], _t["n_sob_medida"],
             _t["custo_total"], _t["venda_total"]))
