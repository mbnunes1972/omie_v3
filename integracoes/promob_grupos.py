"""
promob_grupos.py — Fase 1: Leitura e classificação de XML Promob
Gera um arquivo JSON intermediário com os grupos de produtos por ambiente.
Uso: python promob_grupos.py arquivo1.xml [arquivo2.xml ...]
     python promob_grupos.py --pasta ./xmls
"""

import xml.etree.ElementTree as ET
import json
import sys
import os
import re
from collections import defaultdict
from datetime import datetime

# ── Grupos padronizados ──────────────────────────────────────────────────────
# Cada grupo é um produto fixo no Omie. NCMs a confirmar com contador.
GRUPOS = [
    {"id": "01", "nome": "MÓDULOS E GABINETES",                    "ncm": "94036000"},
    {"id": "02", "nome": "PORTAS E TAMPONAMENTOS",                 "ncm": "94036000"},
    {"id": "03", "nome": "PAINÉIS SOLTOS",                         "ncm": "94036000"},
    {"id": "04", "nome": "CHAPAS E FITAS",                         "ncm": "44119290"},
    {"id": "05", "nome": "ILUMINAÇÃO",                             "ncm": "94054090"},
    {"id": "06", "nome": "FERRAGENS - DOBRADIÇAS, CORREDIÇAS E PISTÕES", "ncm": "83024200"},
    {"id": "07", "nome": "FERRAGENS - ACESSÓRIOS INTERNOS",        "ncm": "83024200"},
    {"id": "08", "nome": "FERRAGENS - SISTEMAS FUNCIONAIS",        "ncm": "83024200"},
    {"id": "09", "nome": "PERFIS E ACABAMENTOS",                   "ncm": "76169000"},
    {"id": "10", "nome": "INDUSTRIALIZAÇÃO",                       "ncm": "99999900"},  # confirmar
    {"id": "11", "nome": "MATERIAIS DE PRODUÇÃO",                  "ncm": "35069100"},  # confirmar
    {"id": "12", "nome": "FIXAÇÃO",                                "ncm": "73181500"},
    {"id": "13", "nome": "COMPONENTES DE MONTAGEM",                "ncm": "83024200"},
    {"id": "14", "nome": "ACABAMENTO FINAL",                       "ncm": "39259090"},
    {"id": "15", "nome": "EMBALAGEM",                              "ncm": "39202000"},
    {"id": "16", "nome": "COMPLEMENTOS",                           "ncm": "94036000"},
]

# Mapa nome → id para referência rápida
GRUPO_IDS = {g["nome"]: g["id"] for g in GRUPOS}

# ── Regras de classificação ──────────────────────────────────────────────────
# Retorna o NOME do grupo. Itens não classificados → COMPLEMENTOS.
def classificar(ref, desc, cat):
    r = ref.upper()
    d = desc.upper()

    # 01 — MÓDULOS E GABINETES
    if r.startswith(('BAL','BAS','ARM')):                           return "MÓDULOS E GABINETES"
    if r.startswith('PMO') and 'MONT' in d:                        return "MÓDULOS E GABINETES"
    if r.startswith('GAM'):                                         return "MÓDULOS E GABINETES"
    if any(kw in d for kw in ('BALCÃO','ARMÁRIO','GABINETE','BASE BAL','BASE ARM')):
        if not any(kw in d for kw in ('PARAFUSO','BUCHA','SUPORTE')):
            return "MÓDULOS E GABINETES"

    # 02 — PORTAS E TAMPONAMENTOS
    if r.startswith('FTE'):                                         return "PORTAS E TAMPONAMENTOS"
    if r.startswith('PAI3'):                                        return "PORTAS E TAMPONAMENTOS"
    if r in ('BOR004',):                                            return "PORTAS E TAMPONAMENTOS"
    if any(kw in d for kw in ('PORTA','FRENTE','TAMPON','BASCULANTE SUP','GIRO VERT','GIRO INF')):
        return "PORTAS E TAMPONAMENTOS"

    # 03 — PAINÉIS SOLTOS
    if r.startswith(('LIV','LVR')):                                 return "PAINÉIS SOLTOS"
    if r.startswith('PNL'):                                         return "PAINÉIS SOLTOS"
    if r.startswith('PAI0') or r == 'PAI003':                       return "PAINÉIS SOLTOS"
    if 'PAINEL LIVRE' in d or 'PAI LISO' in d or 'PAI HOR' in d:   return "PAINÉIS SOLTOS"

    # 04 — CHAPAS E FITAS
    if 'MP - CHAPA' in d or 'MP - FITA' in d:                      return "CHAPAS E FITAS"
    if 'MP - BORDA' in d or 'FITA BORDA' in d:                     return "CHAPAS E FITAS"
    if r in ('101933',):                                            return "CHAPAS E FITAS"  # fita borda alumínio
    if 'CHAPA EDIT' in d or 'CHAPA NORMAL' in d:                   return "CHAPAS E FITAS"

    # 05 — ILUMINAÇÃO
    if r.startswith('ILU'):                                         return "ILUMINAÇÃO"
    if r in ('207644',):                                            return "ILUMINAÇÃO"
    if r.startswith('CUEX') and 'LUMIN' in d:                      return "ILUMINAÇÃO"
    if any(kw in d for kw in ('LUMINÁRIA','LUMIN','DRIVE','LED','FONTE','PERFIL LED')):
        return "ILUMINAÇÃO"

    # 06 — FERRAGENS - DOBRADIÇAS, CORREDIÇAS E PISTÕES
    if r.startswith('DOB'):                                         return "FERRAGENS - DOBRADIÇAS, CORREDIÇAS E PISTÕES"
    if r.startswith('COR'):                                         return "FERRAGENS - DOBRADIÇAS, CORREDIÇAS E PISTÕES"
    if r.startswith('ACE'):                                         return "FERRAGENS - DOBRADIÇAS, CORREDIÇAS E PISTÕES"
    if any(kw in d for kw in ('DOBRADIÇA','CORREDIÇA','PISTÃO','PISTAO','AMORTECIMENTO')):
        return "FERRAGENS - DOBRADIÇAS, CORREDIÇAS E PISTÕES"

    # 07 — FERRAGENS - ACESSÓRIOS INTERNOS
    if r.startswith('ORG'):                                         return "FERRAGENS - ACESSÓRIOS INTERNOS"
    if r.startswith('PUX'):                                         return "FERRAGENS - ACESSÓRIOS INTERNOS"
    if r in ('200942', '200291', '110963'):                         return "FERRAGENS - ACESSÓRIOS INTERNOS"
    if r.startswith('PRF') and 'FLAT' in d:                        return "FERRAGENS - ACESSÓRIOS INTERNOS"
    if any(kw in d for kw in ('DIVISOR','LIXEIRA','ORGANIZADOR','PUXADOR','BARRA PUXADOR')):
        return "FERRAGENS - ACESSÓRIOS INTERNOS"

    # 08 — FERRAGENS - SISTEMAS FUNCIONAIS
    if r.startswith(('LAT','TRA','FUN','COS','FRE','PIL')):         return "FERRAGENS - SISTEMAS FUNCIONAIS"
    if r in ('207383',):                                            return "FERRAGENS - SISTEMAS FUNCIONAIS"  # suporte pensil
    if any(kw in d for kw in ('LATERAL GAV','TRAVESSA','FUNDO 6MM','COSTA GAV',
                               'CONTRA FRENTE','PILASTRA','PENSIL')):
        return "FERRAGENS - SISTEMAS FUNCIONAIS"

    # 09 — PERFIS E ACABAMENTOS
    if r.startswith('DEC'):                                         return "PERFIS E ACABAMENTOS"
    if r.startswith('PRF'):                                         return "PERFIS E ACABAMENTOS"
    if r in ('200308', '203412', '203413', '200295', '200296'):     return "PERFIS E ACABAMENTOS"
    if r.startswith('PAI') and ('ALUM' in d or 'STUCCO' in d):     return "PERFIS E ACABAMENTOS"
    if r.startswith(('COM114','PMO040')):                           return "PERFIS E ACABAMENTOS"
    if any(kw in d for kw in ('PERFIL','BARRA PERFIL','PONTEIRA','PROTETOR ALUM')):
        return "PERFIS E ACABAMENTOS"

    # 10 — INDUSTRIALIZAÇÃO
    if r.startswith('CUEX'):                                        return "INDUSTRIALIZAÇÃO"
    if any(kw in d for kw in ('CUSTO USINAGEM','CUSTO MONTAGEM','CUSTO APLICAÇÃO',
                               'CUSTO MONT','USINAGEM','INDUSTRIALIZ')):
        return "INDUSTRIALIZAÇÃO"

    # 11 — MATERIAIS DE PRODUÇÃO
    if any(kw in d for kw in ('COLA PUR','MASSA UV','FORMULA TINTA','TINTA',
                               'BISNAGA DE COLA','COLA ')):
        return "MATERIAIS DE PRODUÇÃO"
    if r in ('108731','108078','200057','206842','101378'):          return "MATERIAIS DE PRODUÇÃO"

    # 12 — FIXAÇÃO
    if any(kw in d for kw in ('PARAFUSO','MINIFIX','TAMBOR MINIFIX','PREGO',
                               'CAVILHA','STEELBLOCK','BUCHA')):
        return "FIXAÇÃO"
    if r in ('101382','101384','101390','101400','101391',
             '200313','200325','208818','100980','100981',
             '100982','100993','200270'):                            return "FIXAÇÃO"

    # 13 — COMPONENTES DE MONTAGEM
    if r.startswith(('SUP','SUPFL')):                               return "COMPONENTES DE MONTAGEM"
    if r in ('200000','206855','200321','200309'):                   return "COMPONENTES DE MONTAGEM"
    if any(kw in d for kw in ('SUPORTE FIXAÇÃO','SUPORTE DE FIXAÇÃO','FIXADOR DE ARM',
                               'ESQUADRETA','CANTONEIRA TRIANGULAR')):
        return "COMPONENTES DE MONTAGEM"

    # 14 — ACABAMENTO FINAL
    if any(kw in d for kw in ('TAPA FURO','BATENTE SILICONE','PLAQUETA','LOGOMARCA')):
        return "ACABAMENTO FINAL"
    if r in ('101310','205172','200111','101374','205832','205833','205834','ACA028'):
        return "ACABAMENTO FINAL"

    # 15 — EMBALAGEM
    if 'EMB -' in d or 'PLÁSTICO BOLHA' in d:                      return "EMBALAGEM"
    if 'CANTONEIRA PLÁSTICA' in d:                                  return "EMBALAGEM"
    if r.startswith(('101288','101289','101290','101292','103937',
                     '103938','104005','105350','106550','108583')): return "EMBALAGEM"

    # Tapetes de proteção — proteção de produto, similar a embalagem
    if 'TAPETE' in d and 'PROTEÇÃO' in d:                           return "EMBALAGEM"

    # 16 — COMPLEMENTOS (fallback)
    return "COMPLEMENTOS"


# ── Leitura de XML ───────────────────────────────────────────────────────────
def _totais_declarados(root):
    """ACHADO-44 (docs/db/ACHADOS_CONTABEIS.md): o próprio arquivo Promob declara, em
    `<TOTALPRICES><MARGINS><ORDER VALUE=".."/><BUDGET VALUE=".."/></MARGINS></TOTALPRICES>`
    (primeiro nó no documento — o grand-total do ambiente; os demais são subtotais por
    modelo/categoria, que somam para este), o custo (ORDER, = order_total) e a venda (BUDGET,
    = total) que a soma dos itens TEM que bater. Retorna (declarado_order, declarado_budget),
    None quando o arquivo não carrega essa seção (formato antigo)."""
    tp = root.find('.//TOTALPRICES')
    if tp is None:
        return None, None
    margins = tp.find('MARGINS')
    if margins is None:
        return None, None
    declarado_order = declarado_budget = None
    oe = margins.find('ORDER')
    if oe is not None:
        try: declarado_order = float(oe.get('VALUE', '0') or '0')
        except (TypeError, ValueError): pass
    be = margins.find('BUDGET')
    if be is not None:
        try: declarado_budget = float(be.get('VALUE', '0') or '0')
        except (TypeError, ValueError): pass
    return declarado_order, declarado_budget


def consistencia_interna(amb, tolerancia=0.05):
    """ACHADO-44 — o arquivo conferido CONTRA ELE MESMO, nada externo entra na conta: a soma dos
    `order_total`/`total` de todos os itens (já com os impostos/margens que cada item carrega,
    lidos do próprio arquivo) tem que bater com o que `TOTALPRICES` declara para o ambiente
    inteiro. Um `TOTAL` de item editado à mão (sem recalcular o grand-total) denuncia-se aqui —
    foi assim que o Δ custo do C1 (`docs/db/TAREFA_PERCURSO_0209.md`) atravessou o ciclo inteiro
    sem ninguém notar.

    `amb`: dict de `ler_xml_str`/`ler_xml` (precisa ter rodado com `_totais_declarados`, i.e.
    conter as chaves `declarado_order`/`declarado_budget`).

    Retorna `(ok, problemas)` — `problemas`: lista de strings, vazia quando `ok`. Arquivo sem
    `TOTALPRICES` (formato antigo) não tem o que conferir: sempre `ok`."""
    declarado_order = amb.get('declarado_order')
    declarado_budget = amb.get('declarado_budget')
    soma_order = round(sum(item.get('order_total', 0.0)
                           for grupo in amb.get('grupos', [])
                           for item in grupo.get('itens', [])), 2)
    soma_budget = round(amb.get('total', 0.0), 2)
    problemas = []
    if declarado_order is not None and abs(soma_order - declarado_order) > tolerancia:
        problemas.append(
            "custo de fábrica: soma dos itens R$ %.2f não bate com o total do arquivo R$ %.2f"
            % (soma_order, declarado_order))
    if declarado_budget is not None and abs(soma_budget - declarado_budget) > tolerancia:
        problemas.append(
            "venda: soma dos itens R$ %.2f não bate com o total do arquivo R$ %.2f"
            % (soma_budget, declarado_budget))
    return (not problemas), problemas


def venda_maior_que_cfo(budget_total, order_total, tolerancia=0.005):
    """ACHADO-45 (docs/db/TAREFA_PERCURSO_0209.md) — venda (`budget_total`) e custo de fábrica
    (`order_total`) vêm do MESMO XML, e ninguém as compara. Um ambiente vendido pelo custo ou
    abaixo dele nunca deveria existir — mas nada barrava. Medido em 02/09 antes de travar (Homo-
    logação, único ambiente com dados reais: 0/12 violavam hoje) — a trava é prospectiva, nunca
    retroativa.

    Retorna True quando a venda é estritamente maior que o CFO (dentro da tolerância de
    centavos) — ou seja, quando o ambiente PASSA. False significa recusar."""
    bt = round(float(budget_total or 0), 2)
    ot = round(float(order_total or 0), 2)
    return bt > ot + tolerancia


def _ler_xml_root(nome_arquivo, root):
    """Core parsing logic — receives ElementTree root directly."""
    projeto = root.get('DESCRIPTION', nome_arquivo)
    data_str = root.get('DATE', '')
    try:
        data = datetime.strptime(data_str, '%d/%m/%Y').strftime('%d/%m/%Y')
    except:
        data = datetime.today().strftime('%d/%m/%Y')
    declarado_order, declarado_budget = _totais_declarados(root)

    # Agrupa por ref (chapas/fitas podem ter múltiplos cortes com a mesma ref)
    refs = {}
    for cat_el in root.findall('.//CATEGORY'):
        items_el = cat_el.find('ITEMS')
        if items_el is None: continue
        for item in items_el.iter('ITEM'):
            if item.get('SHOWPRICE') != 'Y': continue
            ref  = item.get('REFERENCE','').strip()
            desc = item.get('DESCRIPTION','').strip()
            unit = item.get('UNIT','UN').strip()
            cat  = cat_el.get('DESCRIPTION','')
            if not ref: continue
            try: qty = float(item.get('QUANTITY','0'))
            except: qty = 0
            if qty <= 0: continue
            # Extrair todos os níveis de preço para referência futura
            price_table  = 0.0   # tabela fábrica (sem IPI)
            price_total  = 0.0   # tabela após ajustes iniciais
            order_total  = 0.0   # custo com frete (após descontos fábrica)
            budget_total = 0.0   # PREÇO DE VENDA AO CLIENTE ← valor usado

            pe = item.find('PRICE')
            if pe is not None:
                try: price_table = float(pe.get('TABLE','0') or '0')
                except: pass
                try: price_total = float(pe.get('TOTAL','0') or '0')
                except: pass
                margins = pe.find('MARGINS')
                if margins is not None:
                    oe = margins.find('ORDER')
                    if oe is not None:
                        try: order_total = float(oe.get('TOTAL','0') or '0')
                        except: pass
                    be = margins.find('BUDGET')
                    if be is not None:
                        try: budget_total = float(be.get('TOTAL','0') or '0')
                        except: pass

            # Usar BUDGET como valor de venda; fallback para PRICE/@TOTAL
            total = budget_total if budget_total > 0 else price_total
            if total <= 0: continue

            if ref not in refs:
                refs[ref] = {
                    'ref': ref, 'desc': desc, 'unit': unit, 'cat': cat,
                    'qty': 0.0, 'total': 0.0,
                    'price_table': 0.0, 'price_total': 0.0,
                    'order_total': 0.0, 'budget_total': 0.0,
                }
            refs[ref]['qty']          += qty
            refs[ref]['total']        += total
            refs[ref]['price_table']  += price_table
            refs[ref]['price_total']  += price_total
            refs[ref]['order_total']  += order_total
            refs[ref]['budget_total'] += budget_total

    # Classifica cada ref e acumula nos grupos
    grupos_vals  = defaultdict(float)
    grupos_itens = defaultdict(list)
    for r in refs.values():
        grp = classificar(r['ref'], r['desc'], r['cat'])
        grupos_vals[grp]   += r['total']
        grupos_itens[grp].append({
            'ref':          r['ref'],
            'desc':         r['desc'],
            'qty':          round(r['qty'], 4),
            'unit':         r['unit'],
            'total':        round(r['total'], 2),
            'price_table':  round(r.get('price_table',  0.0), 2),
            'price_total':  round(r.get('price_total',  0.0), 2),
            'order_total':  round(r.get('order_total',  0.0), 2),
            'budget_total': round(r.get('budget_total', 0.0), 2),
        })

    total_ambiente = sum(grupos_vals.values())

    # Monta resultado na ordem dos grupos definidos
    grupos_resultado = []
    for g in GRUPOS:
        subtotal = round(grupos_vals.get(g['nome'], 0.0), 2)
        itens    = sorted(grupos_itens.get(g['nome'], []), key=lambda x: -x['total'])
        if subtotal > 0:
            grupos_resultado.append({
                'grupo_id':   g['id'],
                'grupo_nome': g['nome'],
                'ncm':        g['ncm'],
                'subtotal':   subtotal,
                'itens':      itens,
            })

    return {
        'arquivo':   nome_arquivo,
        'projeto':   projeto,
        'data':      data,
        'total':     round(total_ambiente, 2),
        'grupos':    grupos_resultado,
        'declarado_order':  round(declarado_order, 2) if declarado_order is not None else None,
        'declarado_budget': round(declarado_budget, 2) if declarado_budget is not None else None,
    }


def ler_xml(caminho):
    tree = ET.parse(caminho)
    return _ler_xml_root(os.path.basename(caminho), tree.getroot())


def ler_xml_str(arq_nome, xml_string):
    """Like ler_xml but accepts filename + XML string instead of a file path."""
    root = ET.fromstring(xml_string)
    return _ler_xml_root(arq_nome, root)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    # Coleta arquivos XML da linha de comando ou pasta
    xmls = []
    args = sys.argv[1:]

    if '--pasta' in args:
        idx = args.index('--pasta')
        pasta = args[idx + 1]
        xmls = [os.path.join(pasta, f) for f in os.listdir(pasta) if f.lower().endswith('.xml')]
    else:
        xmls = [a for a in args if a.lower().endswith('.xml')]

    if not xmls:
        print("Uso: python promob_grupos.py arquivo.xml [arquivo2.xml ...]")
        print("     python promob_grupos.py --pasta ./xmls")
        sys.exit(1)

    print(f"\nProcessando {len(xmls)} arquivo(s)...\n")

    ambientes = []
    for caminho in sorted(xmls):
        try:
            amb = ler_xml(caminho)
            ambientes.append(amb)
            print(f"  ✓ {amb['arquivo']} — {amb['projeto']}")
            print(f"    {len(amb['grupos'])} grupos  |  R$ {amb['total']:,.2f}")
            for g in amb['grupos']:
                print(f"    {g['grupo_id']}. {g['grupo_nome']:<45} R$ {g['subtotal']:>10,.2f}  ({len(g['itens'])} refs)")
            print()
        except Exception as e:
            print(f"  ✗ {caminho}: {e}")

    # Total geral
    total_projeto = sum(a['total'] for a in ambientes)

    # Monta JSON de saída
    saida = {
        'versao':        '1.0',
        'gerado_em':     datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'total_projeto': round(total_projeto, 2),
        'ambientes':     ambientes,
        'grupos_ref':    GRUPOS,  # referência completa dos grupos com NCMs
    }

    # Nome do arquivo de saída baseado no primeiro projeto
    nome_base = re.sub(r'[^\w\s-]', '', ambientes[0]['projeto'])[:40].strip().replace(' ', '_')
    nome_saida = f"orcamento_{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    # DOIS dirname: grava na RAIZ, não dentro de integracoes/ (este arquivo mudou
    # de lugar em 2026-07-15 e o caminho relativo a __file__ seguiu junto).
    _raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_saida = os.path.join(_raiz, nome_saida)

    with open(caminho_saida, 'w', encoding='utf-8') as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print(f"{'─'*55}")
    print(f"  Total do projeto: R$ {total_projeto:,.2f}")
    print(f"  Arquivo gerado:   {nome_saida}")
    print()


if __name__ == '__main__':
    main()
