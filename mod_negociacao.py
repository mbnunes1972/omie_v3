# -*- coding: utf-8 -*-
"""mod_negociacao.py — Motor de cálculo da negociação (PURO, sem I/O).

Cálculo por ambiente, agregado por orçamento. Siglas conforme
docs/superpowers/specs/2026-06-22-mecanismo-negociacao-design.md (§3/§4).

ACHADO-63 (06/09, DECIDIDO): o desconto anunciado ao cliente leva o Bruto ao Valor à Vista —
`Bruto × (1 − desconto) = à vista`, sempre, pra toda rubrica repassada. Viagem e brinde deixaram
de usar gross-up DIVISIVO (que inflava o Bruto e fazia o preço de tabela variar com o desconto);
custo especial passou a sofrer o desconto do orçamento em VAVO (senão a identidade quebrava).
Comissão de arquiteto e fidelidade continuam com gross-up divisivo (`vbva/fator_com`) — são
PERCENTUAIS, não dependem de `d`, já satisfazem a identidade sem mudança nenhuma.
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin=0.0, n_total_proj=None, vbvo_proj=None):
    """Ver docstring do plano/§4. `params` no formato parametros_json do projeto."""
    p = params or {}
    tog_cadi = bool(p.get("incluir_custos", False))      # master: repassa/absorve
    tog_carq = bool(p.get("comissao_arq_ativa", False))
    tog_fid  = bool(p.get("fidelidade_ativa", False))
    tog_cvia = bool(p.get("fora_da_sede", False))
    tog_bri  = bool(p.get("brinde_ativo", False))
    tog_cesp = bool(p.get("custo_especial_ativo", False))
    pct_arq  = _f(p.get("comissao_arq_pct")) / 100.0
    pct_fid  = _f(p.get("fidelidade_pct")) / 100.0
    cust_via = _f(p.get("custo_viagem"))
    bri      = _f(p.get("brinde"))
    cust_esp = _f(p.get("custo_especial")) if tog_cesp else 0.0
    pct_trib = _f(p.get("carga_trib")) / 100.0
    d_orc    = _f(desc_orc_pct) / 100.0

    ambs = [{"VBVA": _f(a.get("VBVA")), "CFA": _f(a.get("CFA")),
             "d_amb": _f(a.get("desc_amb_pct")) / 100.0} for a in (ambientes or [])]
    num_amb = len(ambs)
    if not num_amb:
        cust_esp = 0.0   # sem ambientes não há venda — custo especial só existe sobre uma venda (QA Vera)
    VBVO = sum(a["VBVA"] for a in ambs)
    CFO  = sum(a["CFA"] for a in ambs)

    out_ambs = []
    VBNO = VAVO = 0.0
    com_arq = pro_fid = 0.0
    total_via = total_bri = 0.0
    recup_via = recup_bri = 0.0
    for a in ambs:
        vbva, d_amb = a["VBVA"], a["d_amb"]
        fator_desc = (1 - d_orc) * (1 - d_amb)
        # parcelas de viagem (rateada) e brinde (igual/amb) deste ambiente
        den_via = vbvo_proj if vbvo_proj else VBVO          # projeto (proporcional) ou orçamento (fallback)
        den_bri = n_total_proj if n_total_proj else num_amb  # projeto (igual) ou orçamento (fallback)
        num_via = (cust_via * (vbva / den_via)) if (tog_cvia and den_via > 0) else 0.0
        num_bri = (bri / den_bri) if (tog_bri and den_bri) else 0.0
        if tog_cadi:
            fator_com = (1 - pct_arq if tog_carq else 1.0) * (1 - pct_fid if tog_fid else 1.0)
            termo_arqfid = (vbva / fator_com) if fator_com > 0 else vbva
            # ACHADO-63 (06/09, DECIDIDO): o desconto anunciado leva o Bruto ao à Vista —
            # viagem/brinde entram pelo valor de FACE (sem gross-up divisivo). O preço de
            # tabela não pode variar conforme o desconto; a loja recupera só (1−d) do custo,
            # contrapartida aceita e previsível (embutir o desconto médio é decisão de quem
            # digita o parâmetro).
            termo_via_bri = (num_via + num_bri)
            vbna = termo_arqfid + termo_via_bri
        else:
            vbna = vbva
        vava = vbna * fator_desc
        # comissão em cadeia, por ambiente: arq NÃO ganha sobre fid; e nem arq nem fid
        # ganham sobre viagem/brinde — a base exclui esses custos SEMPRE (repassados ou
        # absorvidos), conforme a fórmula `VAVA − viagem − brinde`. ACHADO-63: viagem/brinde
        # agora entram em VAVA já multiplicados por `fator_desc` (não mais blindados) — a base
        # excluída tem que refletir o mesmo valor, senão sobra/falta base de comissão.
        base_custos = (num_via + num_bri) * fator_desc
        pro_amb = (pct_fid * (vava - base_custos)) if tog_fid else 0.0
        com_amb = (pct_arq * (vava - pro_amb - base_custos)) if tog_carq else 0.0
        pro_fid += pro_amb
        com_arq += com_amb
        total_via += num_via
        total_bri += num_bri
        # ACHADO-63: o recuperado real de viagem/brinde é o custo JÁ multiplicado pelo fator de
        # desconto DESTE ambiente — com desconto por ambiente, a soma dos fatores por ambiente
        # não é igual ao total vezes o desconto global; a tela precisa deste número pronto,
        # não pode recalculá-lo (mesma razão de não recalcular nada em JS que o motor já sabe).
        recup_via += num_via * fator_desc
        recup_bri += num_bri * fator_desc
        VBNO += vbna
        VAVO += vava
        liq_amb = vava - com_amb - pro_amb - num_via - num_bri
        out_ambs.append({"VBVA": round(vbva, 2), "CFA": round(a["CFA"], 2),
                         "VBNA": round(vbna, 2), "VAVA": round(vava, 2),
                         "Com_Arq": round(com_amb, 2), "Pro_Fid": round(pro_amb, 2),
                         "Cust_Via": round(num_via, 2), "Bri": round(num_bri, 2),
                         "Val_Liq": round(liq_amb, 2)})

    # Custo Especial: linha do ORÇAMENTO, não rateada nos ambientes (sai ambiente, ele fica integral —
    # ≠ viagem/brinde, que se distribuem pelo pool do projeto). Repassado (tog_cadi), soma em VBNO
    # pelo valor cheio (o preço de tabela não varia com o desconto) e em VAVO pelo desconto DO
    # ORÇAMENTO (ACHADO-63 — não sofre desconto de ambiente, não é rateado em ambiente nenhum);
    # absorvido, só abate o líquido via cust_ad. Comissões arq/fid não o alcançam (loop por ambiente).
    if tog_cadi and cust_esp:
        VBNO += cust_esp
        # ACHADO-63: custo especial sofre o desconto DO ORÇAMENTO (não sofre desconto de
        # ambiente — não é rateado em ambiente nenhum). Antes entrava em VAVO pelo valor CHEIO
        # enquanto VBNO também recebia o valor cheio — a identidade VAVO == VBNO*(1−d) quebrava
        # exatamente em `cust_esp * d_orc`.
        VAVO += cust_esp * (1 - d_orc)
    cust_ad = (com_arq + pro_fid + (total_via if tog_cvia else 0.0)
               + (total_bri if tog_bri else 0.0) + cust_esp)
    val_liq = VAVO - cust_ad
    desc_tot = ((VBVO - val_liq) / VBVO) if VBVO > 0 else 0.0
    markup = (val_liq / CFO) if CFO > 0 else 0.0
    val_cont = VAVO + _f(cust_fin)
    prov_imp = pct_trib * val_cont

    return {
        "VBVO": round(VBVO, 2), "CFO": round(CFO, 2), "VBNO": round(VBNO, 2),
        "VAVO": round(VAVO, 2), "Num_Amb": num_amb,
        "Com_Arq": round(com_arq, 2), "Pro_Fid": round(pro_fid, 2),
        "Cust_Via": round(total_via if tog_cvia else 0.0, 2),
        "Bri": round(total_bri if tog_bri else 0.0, 2),
        "Cust_Esp": round(cust_esp, 2),
        "Cust_Ad": round(cust_ad, 2),
        "Val_Liq": round(val_liq, 2), "Desc_Tot": round(desc_tot, 4), "Markup": round(markup, 3),
        "Cust_Fin": round(_f(cust_fin), 2), "Val_Cont": round(val_cont, 2), "Prov_Imp": round(prov_imp, 2),
        # ACHADO-63: fonte única do recuperado real por rubrica — a tela não pode recalcular
        # (com desconto por ambiente, o recuperado é a soma dos fatores por ambiente, não o
        # valor vezes o desconto global).
        "Cust_Via_Recup": round(recup_via if tog_cvia else 0.0, 2),
        "Bri_Recup":      round(recup_bri if tog_bri else 0.0, 2),
        "Cust_Esp_Recup": round(cust_esp * (1 - d_orc), 2),
        "Desc_Efetivo":   round((1 - VAVO / VBNO), 6) if VBNO > 0 else 0.0,
        "ambientes": out_ambs,
    }
