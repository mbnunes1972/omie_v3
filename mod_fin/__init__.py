"""
mod_fin/__init__.py — interface pública do módulo financeiro

Uso:
    from mod_fin import calcular_aymore, calcular_cartao
    from mod_fin import carregar_faixas, carregar_tabela
"""
import os, json

_TABELAS_DIR = os.path.join(os.path.dirname(__file__), "..", "tabelas_financeiras")


def _carregar(codigo: str) -> dict:
    """Lê tabelas_financeiras/<codigo>.json. Mantido para compatibilidade."""
    path = os.path.join(_TABELAS_DIR, f"{codigo}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def carregar_tabela(codigo: str) -> dict:
    """Alias público de _carregar."""
    return _carregar(codigo)


def carregar_faixas(codigo: str) -> list:
    """
    Retorna lista de faixas [{parcelas, custo_pct, label}] normalizada.
    Usado para popular dropdowns de parcelas na interface.
    """
    from .base import pmt as _pmt
    tab = _carregar(codigo)
    if not tab:
        return []

    tipo = tab.get("tipo", "")

    if tipo == "avista":
        return [{"parcelas": 1, "custo_pct": 0.0, "label": "À Vista"}]

    if tipo == "financiamento_externo":
        if "faixas" in tab:   # cartao_credito
            return [{"parcelas": max(1, int(f["parcelas"])),
                     "custo_pct": float(f.get("taxa_retencao_pct", 0)),
                     "label": f.get("obs", f"{max(1,int(f['parcelas']))}x")}
                    for f in tab.get("faixas", [])]
        else:                  # aymore — retenção com carência padrão 30d
            result = []
            for t in tab.get("taxas_mensais", []):
                n    = int(t["parcelas"])
                taxa = float(t["taxa_mensal_pct"]) / 100
                if n > 0 and taxa > 0:
                    retencao = round((1 - (1.0 / n) / _pmt(taxa, n)) * 100, 4)
                else:
                    retencao = 0.0
                result.append({"parcelas": n, "custo_pct": retencao, "label": f"{n}x"})
            return result

    if tipo == "programado":
        return [{"parcelas": i, "custo_pct": 0.0, "label": f"{i}x"}
                for i in range(1, int(tab.get("parcelas_max", 12)) + 1)]

    if tipo == "flex":
        # custo_pct=0: o painel Total Flex gerencia o total direto
        p_min = int(tab.get("parcelas_min", 2))
        p_max = int(tab.get("parcelas_max", 12))
        return [{"parcelas": i, "custo_pct": 0.0, "label": f"{i}x"}
                for i in range(p_min, p_max + 1)]

    return []


def listar_modalidades() -> list:
    """Retorna lista de modalidades disponíveis para o dropdown da interface."""
    codigos = ['a_vista', 'aymore', 'cartao_credito', 'cartao_credito_x', 'venda_programada', 'total_flex']
    resultado = []
    for codigo in codigos:
        tab = _carregar(codigo)
        if tab:
            resultado.append({
                'codigo':    tab.get('codigo', codigo),
                'descricao': tab.get('descricao', codigo),
                'tipo':      tab.get('tipo', ''),
            })
        else:
            nomes = {
                'a_vista':          ('A Vista',          'avista'),
                'aymore':           ('Aymoré',            'financiamento_externo'),
                'cartao_credito':   ('Cartão de Crédito',   'financiamento_externo'),
                'cartao_credito_x': ('Cartão de Crédito X', 'financiamento_externo'),
                'venda_programada': ('Venda Programada',  'programado'),
                'total_flex':       ('Total Flex',        'flex'),
            }
            desc, tipo = nomes.get(codigo, (codigo, ''))
            resultado.append({'codigo': codigo, 'descricao': desc, 'tipo': tipo})
    return resultado

# Imports diretos das funções de cálculo
from .aymore           import calcular as calcular_aymore
from .cartao           import calcular as calcular_cartao
from .venda_programada import calcular as calcular_venda_programada
from .total_flex       import calcular as calcular_total_flex
from .total_flex       import inicializar as tf_inicializar
from .total_flex       import recalcular  as tf_recalcular
