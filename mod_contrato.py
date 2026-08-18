"""
mod_contrato.py — Geração de contrato E proposta via template HTML/Markdown,
renderizado em PDF com WeasyPrint.

Contrato: capa (contrato.html) + corpo (cláusulas em Markdown). Proposta: a mesma
capa, sem quebra, + corpo opcional do modelo da loja. O corpo dos dois sai de
mod_documentos.resolver_modelo() quando a loja tem modelo próprio; senão, do
contrato_template/contrato.md global.

O motor de marcadores em .docx (_substituir_marcadores/_subst_paragrafo) e a
conversão .docx→PDF (_converter_pdf) foram REMOVIDOS em 2026-07-15 junto com
mod_proposta.py: produção não os usava desde a migração da capa para WeasyPrint.

_libreoffice_cmd/LibreOfficeIndisponivel FICARAM e não são legado — são a base da
IMPORTAÇÃO de modelo (mod_documentos_import.normalizar).
"""

import os
import json
import platform
import hashlib
import threading
from datetime import datetime

_THIS_DIR            = os.path.dirname(os.path.abspath(__file__))
CONTRATOS_DIR        = os.path.join(_THIS_DIR, "CONTRATOS")
CONTRATO_TEMPLATE_DIR = os.path.join(_THIS_DIR, "contrato_template")

# WeasyPrint não garante thread-safety pra chamadas concorrentes (cache de fontes/Cairo
# compartilhado no processo) — servidor virou multi-thread (2026-08-08) e dois PDFs (contrato,
# proposta, export de chat) podem ser pedidos ao mesmo tempo por usuários diferentes. Serializa
# só a chamada write_pdf em si (rápida o bastante pra não virar gargalo real).
PDF_LOCK = threading.Lock()

_TRACO = "--------"  # preenche slots de parcela inexistentes


# ── Utilitários ───────────────────────────────────────────────────────────────


def gerar_num_contrato(existing_nums, loja_codigo: str, data=None, prefixo=None) -> str:
    """Próximo número no formato '<PREFIXO><AAAAMMDD><SEQ:05d>': a sigla da loja (3 letras) — ou um
    `prefixo` dado (ex.: 'PV' na proposta comercial) — seguida da data (ano-mês-dia) e de 5 dígitos
    sequenciais. A sequência é CONTÍNUA por prefixo (maior existente + 1).

    `existing_nums`: iterável com os números já existentes do MESMO prefixo (num_contrato/num_proposta).
    `loja_codigo`: código (3 letras) da loja — vem da tabela `lojas` (F3). Ignorado se `prefixo` vier.
    """
    data = data or datetime.now()
    pref = (prefixo if prefixo is not None else (loja_codigo or "")).strip().upper()
    maxseq = 0
    for n in (existing_nums or []):
        if not n or not n.startswith(pref):
            continue
        resto = n[len(pref):]
        if len(resto) >= 13 and resto[:8].isdigit() and resto[-5:].isdigit():
            maxseq = max(maxseq, int(resto[-5:]))
    return f"{pref}{data:%Y%m%d}{maxseq + 1:05d}"


def gerar_num_proposta(existing_nums, data=None) -> str:
    """Número da proposta comercial: prefixo fixo 'PV' + data + 5 dígitos sequenciais.
    Mesmo formato do contrato (gerar_num_contrato), mas com 'PV' no lugar da sigla da loja."""
    return gerar_num_contrato(existing_nums, "", data=data, prefixo="PV")


def calcular_hash_assinatura(nome: str, cpf: str, contrato_id: int, timestamp: str) -> str:
    dados = f"{nome}|{cpf}|{contrato_id}|{timestamp}"
    return hashlib.sha256(dados.encode("utf-8")).hexdigest()


def _formatar_valor(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Termo Aditivo — modelo jurídico completo (spec 2026-07-22) ────────────────

_ORDINAIS_ADITIVO = ("PRIMEIRO", "SEGUNDO", "TERCEIRO", "QUARTO", "QUINTO",
                     "SEXTO", "SÉTIMO", "OITAVO", "NONO", "DÉCIMO")


def ordinal_aditivo(n: int) -> str:
    """Título do termo aditivo: 1 → PRIMEIRO, 2 → SEGUNDO… Acima de 10 cai no
    numérico ('11º') — juridicamente válido e evita tabela infinita."""
    if 1 <= n <= len(_ORDINAIS_ADITIVO):
        return _ORDINAIS_ADITIVO[n - 1]
    return "%dº" % n


def corpo_modelo_aditivo_padrao() -> str:
    """contrato_template/termo_aditivo.md (modelo jurídico do advogado) — fonte do seed
    do modelo 'termo_aditivo' para loja sem modelo ativo. '' se o arquivo faltar."""
    try:
        with open(os.path.join(CONTRATO_TEMPLATE_DIR, "termo_aditivo.md"),
                  encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


# Os CONSIDERANDOS são o texto LITERAL do advogado (mod_aditivo.doc, 2022) — não
# reescrever; um por parágrafo para o operador apagar os que não se aplicam. Os demais
# textos são a redação da spec. A adaptação ao caso "sem inclusões/exclusões/alteração
# de valor" é pelo VALOR do marcador (frase negativa própria), não por condicional no
# template: o motor de substituição continua burro e a numeração 1.1/1.2/2 fica estável.
ADITIVO_CONSIDERANDOS_PADRAO = (
    "CONSIDERANDO QUE o CLIENTE solicitou alteração substancial na concepção original do "
    "Projeto Executivo, tal como definido nos itens 1.5.1; 2.3, alínea (b); 2.3.4 a 2.3.6 "
    "do CONTRATO;"
    "\n\n"
    "CONSIDERANDO QUE o CLIENTE solicitou alteração substancial dos produtos e serviços "
    "objeto do CONTRATO;"
    "\n\n"
    "CONSIDERANDO QUE a medição, tal como definida no item 2.3, alínea (a) do CONTRATO, "
    "constatou a necessidade de alteração substancial na concepção do Projeto Inicial, com "
    "impacto relevante no Projeto Executivo que pautará a produção dos bens adquiridos e os "
    "serviços que lhe são acessórios;"
)

_ADITIVO_TXT_LISTA = ("Com base na solicitação do CLIENTE, a lista de produtos e materiais "
                      "adquiridos passa a ser a seguinte, substituindo integralmente, para "
                      "todos os efeitos, o rol constante do CONTRATO e de seus anexos:")
_ADITIVO_TXT_INCLUSOES = ("Diante do rol constante do item 1, promove-se a inclusão dos "
                          "seguintes produtos e materiais, que não constavam do texto "
                          "original do CONTRATO:")
_ADITIVO_TXT_SEM_INCLUSOES = ("Registram as PARTES que o presente TERMO ADITIVO não promove "
                              "a inclusão de produtos ou materiais em relação ao rol "
                              "original do CONTRATO.")
_ADITIVO_TXT_EXCLUSOES = ("Diante do rol constante do item 1, promove-se a exclusão dos "
                          "seguintes produtos e materiais, que constavam do texto original "
                          "do CONTRATO:")
_ADITIVO_TXT_SEM_EXCLUSOES = ("Registram as PARTES que o presente TERMO ADITIVO não promove "
                              "a exclusão de produtos ou materiais em relação ao rol "
                              "original do CONTRATO.")
_ADITIVO_TXT_SEM_ALTERACAO_VALORES = (
    "As alterações promovidas nos itens precedentes não implicam modificação dos valores "
    "nem das condições de pagamento fixados no CONTRATO, que permanecem integralmente "
    "vigentes.")


def _linhas_ambientes_txt(pares):
    return "\n".join("- %s: %s" % (nome, _formatar_valor(v)) for nome, v in pares)


def montar_defaults_aditivo(lista_integral, inclusoes, exclusoes,
                            valor_original, valor_novo, diferenca, condicoes="") -> dict:
    """Textos-padrão dos 5 blocos dos modais sequenciais do Termo Aditivo.

    lista_integral: [(nome, valor)] de TODOS os ambientes vigentes pós-alteração,
    inclusive os não alterados; inclusoes/exclusoes: [(nome, valor)] detectados pela
    comparação (vazio → frase negativa automática); valores em R$ do CONTRATO inteiro
    (original → novo → diferença). O operador edita tudo no wizard antes de gerar."""
    if abs(diferenca) >= 0.005:
        valores = ("Diante das alterações promovidas nos itens precedentes, o valor total "
                   "do CONTRATO passa de %s para %s, resultando em diferença de %s, a ser "
                   "paga da seguinte forma: %s."
                   % (_formatar_valor(valor_original), _formatar_valor(valor_novo),
                      _formatar_valor(diferenca), condicoes or "[condições de pagamento]"))
    else:
        valores = _ADITIVO_TXT_SEM_ALTERACAO_VALORES
    return {
        "considerandos": ADITIVO_CONSIDERANDOS_PADRAO,
        "lista_integral": _ADITIVO_TXT_LISTA + "\n" + _linhas_ambientes_txt(lista_integral),
        "inclusoes": (_ADITIVO_TXT_INCLUSOES + "\n" + _linhas_ambientes_txt(inclusoes)
                      if inclusoes else _ADITIVO_TXT_SEM_INCLUSOES),
        "exclusoes": (_ADITIVO_TXT_EXCLUSOES + "\n" + _linhas_ambientes_txt(exclusoes)
                      if exclusoes else _ADITIVO_TXT_SEM_EXCLUSOES),
        "valores": valores,
    }


def _formatar_valor_str(v):
    """Aceita número ou string já formatada; devolve 'R$ x.xxx,xx' (ou '' se vazio)."""
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        return _formatar_valor(v)
    return str(v).strip()


def ambientes_valor_contrato(itens, vavo, val_cont):
    """Distribui Val_Cont pelos ambientes, proporcional ao VAVA.

    itens: lista [(nome, VAVA_float), ...] na ordem do orçamento.
    Retorna [(nome, valor_float), ...] com Σ valor == round(val_cont, 2);
    o resíduo de arredondamento é absorvido pelo último ambiente.
    vavo<=0 → devolve os próprios VAVA arredondados (sem divisão por zero).
    """
    if not itens:
        return []
    alvo = round(float(val_cont or 0.0), 2)
    if not vavo or vavo <= 0:
        return [(n, round(float(v or 0.0), 2)) for n, v in itens]
    fator = alvo / vavo
    out = [(n, round(float(v or 0.0) * fator, 2)) for n, v in itens]
    resid = round(alvo - sum(v for _, v in out), 2)
    if resid:
        n_ult, v_ult = out[-1]
        out[-1] = (n_ult, round(v_ult + resid, 2))
    return out


def _formatar_data_br(data: str) -> str:
    """Converte ISO 'YYYY-MM-DD' → 'DD/MM/AAAA'. Datas já em DD/MM são passadas direto."""
    if not data:
        return "—"
    data = data.strip()
    # Já está no formato brasileiro
    if len(data) == 10 and data[2] == "/" and data[5] == "/":
        return data
    if len(data) >= 10:
        try:
            return datetime.strptime(data[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass
    return data or "—"


def _cel_amb(rotulo, valor):
    """Retorna as duas <td>s de um ambiente (rótulo e valor)."""
    return (f'<td class="amb-rotulo">{rotulo}</td>'
            f'<td class="amb-valor">{valor}</td>')


def _html_ambientes_linhas(itens_valores):
    """<tr>s da tabela de ambientes: 2 por linha; sobra ímpar em traços."""
    from html import escape
    n = len(itens_valores)
    n_linhas = max(1, (n + 1) // 2)
    linhas = []
    for k in range(n_linhas):
        cels = []
        for slot in (0, 1):
            idx = 2 * k + slot
            if idx < n:
                nome, val = itens_valores[idx]
                cels.append(_cel_amb(escape(str(nome)), _formatar_valor(val)))
            else:
                cels.append(_cel_amb(_TRACO, _TRACO))
        linhas.append("<tr>" + "".join(cels) + "</tr>")
    return "\n".join(linhas)


def _html_parcelas_linhas(pag):
    """<tr>s da grade de parcelas: 3 por linha, só linhas usadas, tracos no resto."""
    tipo = pag.get("tipo", "")
    num = pag.get("num_parcelas_int", 0)
    valores = pag.get("valores", [""] * 24)
    datas = pag.get("datas", [""] * 24)
    n_linhas = (num + 2) // 3  # ceil(num/3)
    linhas = []
    for gi in range(n_linhas):
        cels = []
        for j in range(3):
            p = gi * 3 + j + 1  # 1-based
            if p <= num and valores[p - 1]:
                val = valores[p - 1]
                data = "" if tipo == "cartao" else (datas[p - 1] or _TRACO)
            else:
                val, data = _TRACO, _TRACO
            cels.append(f'<td class="pc-valor">{val}</td>'
                        f'<td class="pc-data">{data}</td>')
        linhas.append("<tr>" + "".join(cels) + "</tr>")
    return "\n".join(linhas)


# ── Motor de substituição de marcadores [MARCADOR] ────────────────────────────

import re as _re_mark
_MARK_RE = _re_mark.compile(r'\[+\s*([A-Za-z0-9_ ]+?)\s*\]')

# ── Nível de cláusula + Markdown→HTML ──────────────────────────────────────────

import re as _re2

_RE_NUM = _re2.compile(r'^\s*(\d+(?:\.\d+)*)\.\s')
_RE_ALINEA = _re2.compile(r'^\s*[a-z]\)\s')


def _nivel_clausula(texto):
    """Detecta o nível de uma cláusula pela numeração literal.

    2. → 1, 2.3. → 2, 2.3.1. → 3, a) → 4, caso contrário None.
    """
    m = _RE_NUM.match(texto or "")
    if m:
        return m.group(1).count(".") + 1
    if _RE_ALINEA.match(texto or ""):
        return 4
    return None


def _inline_md(texto):
    """Formatação inline do Markdown (negrito/itálico), sem parsing de bloco.

    Protege runs de '_' (linhas de preenchimento, ex.: '(nome) __________') para o
    Markdown não os tratar como ênfase e destruí-los."""
    import markdown
    t = (texto or "").replace("_", "\x00u\x00")
    html = markdown.markdown(t).replace("\x00u\x00", "_")
    m = _re2.match(r'^<p>(.*)</p>$', html, _re2.DOTALL)
    return m.group(1) if m else html


def _html_corpo(md_texto):
    """Corpo (cláusulas com números literais) em HTML, linha a linha.
    Linhas '1.'/'1.1.'/'a)' viram <p class="cl-N"> (NÃO <li> de lista ordenada);
    '#'/'##' viram <h1>/<h2>; o número literal é preservado como texto e o
    Markdown é aplicado só ao texto após o número (inline).

    O corpo é ESCAPADO antes de qualquer coisa. Um modelo de contrato é texto com
    [MARCADORES], não HTML: '**negrito**' e '# CLÁUSULA' seguem funcionando (Markdown
    é processado depois, sobre o texto já escapado), mas <img>/<style>/<script> viram
    texto literal visível — que é o comportamento certo, o lojista vê que colou lixo.

    POR QUE ISTO EXISTE: markdown.markdown() PRESERVA HTML embutido. Enquanto o corpo
    vinha só de contrato_template/contrato.md (conteúdo do repositório, confiável), não
    havia vetor. Desde que a loja passou a subir o próprio modelo, o corpo é entrada de
    usuário e ia cru para o WeasyPrint: um <img src="http://..."> ou @import url(...)
    fazia o renderizador buscar a URL (SSRF), e url(file:///...) lia arquivo local (LFI).
    Comprovado por execução — servidor de prova recebeu as requisições — e explorável
    tanto no /preview quanto, depois de ativado, em TODO contrato real gerado.
    Segunda camada, independente desta: _url_fetcher_local() em gerar_pdf_*.

    quote=False de propósito: o corpo vira conteúdo de elemento, nunca valor de
    atributo, e escapar aspas encheria um contrato de '&quot;' à toa.
    """
    from html import escape
    linhas = []
    for bruta in escape(md_texto or "", quote=False).splitlines():
        t = bruta.strip()
        if not t:
            continue
        mh = _re2.match(r'^(#{1,6})\s+(.*)$', t)
        if mh:
            lvl = len(mh.group(1))
            linhas.append(f"<h{lvl}>{_inline_md(mh.group(2))}</h{lvl}>")
            continue
        if t.startswith("E assim") and "firmam as PARTES" in t:
            # parágrafo de fecho: espaço acima via CSS
            linhas.append(f'<p class="fecho">{_inline_md(t)}</p>')
            continue
        if "[DATA_CONTRATO]" in t:
            # local/data do fecho (área de assinaturas): espaço acima via CSS
            linhas.append(f'<p class="data-fecho">{_inline_md(t)}</p>')
            continue
        if _re2.match(r'^_{5,}$', t):
            # linha de assinatura (traço para assinar): espaço acima via CSS
            linhas.append(f'<p class="assinatura">{t}</p>')
            continue
        if "[TEXTO_COMPLEMENTAR]" in t:
            # adendo (texto livre): ao final do contrato, após as assinaturas,
            # em itálico para destaque; a substituição do marcador vem depois.
            linhas.append(f'<p class="adendo">{t}</p>')
            continue
        alinea = _RE_ALINEA.match(t)
        nivel = _nivel_clausula(t)
        if alinea or nivel is not None:
            if alinea:                       # a), b)… -> alínea
                mnum, classe = alinea, "cl-alinea"
            else:                            # cláusula numérica (nível ≥3 usa cl-3)
                mnum, classe = _RE_NUM.match(t), f"cl-{min(nivel, 3)}"
            prefixo = t[:mnum.end()]         # ex.: "1.1. " ou "a) "
            resto = t[mnum.end():]
            linhas.append(f'<p class="{classe}">{prefixo}{_inline_md(resto)}</p>')
        else:
            linhas.append(f'<p>{_inline_md(t)}</p>')
    return "\n".join(linhas)


def _aplica_mark(texto, mapping):
    def repl(m):
        chave = m.group(1).strip().upper().replace(" ", "_")
        return mapping[chave] if chave in mapping else m.group(0)
    return _MARK_RE.sub(repl, texto)


def _substituir_marcadores_html(html, mapping):
    """Substitui [MARCADOR] (case-insensitive, tolera '[[') numa string HTML/texto.
    Chaves do mapping em MAIÚSCULAS sem colchetes. Marcador sem chave é mantido."""
    def repl(m):
        chave = m.group(1).strip().upper().replace(" ", "_")
        return mapping[chave] if chave in mapping else m.group(0)
    return _MARK_RE.sub(repl, html)


# ── Parser de pagamento ───────────────────────────────────────────────────────

_FORMA_LABELS = {
    "pix": "Pix",
    "ted": "TED",
    "transferencia": "TED",
    "boleto": "Boleto",
    "cheque": "Cheque",
    "dinheiro": "Dinheiro",
    "cartao_credito": "Cartão de Crédito",
    "cartao_debito": "Cartão de Débito",
    "debito_automatico": "Débito Automático",
}


def _forma_label(codigo: str) -> str:
    """Converte código de forma de pagamento em rótulo pt-BR. Idempotente:
    um rótulo já formatado (não encontrado no mapa) é devolvido como veio."""
    if not codigo:
        return ""
    return _FORMA_LABELS.get(str(codigo).strip().lower(), str(codigo).strip())


def _parse_pagamento(pag_json_str: str) -> dict:
    """
    Normaliza o JSON de pagamento capturado pelo frontend (_capturarPagamento).

    Formato de entrada (do frontend):
      { tipo, nome_forma, entrada_valor, entrada_data, entrada_forma,
        parcelas: [{seq, descricao, data, valor, forma}],
        texto (apenas cartão) }

    Retorna dict normalizado com campos prontos para preencher a capa.
    """
    try:
        pag = json.loads(pag_json_str) if pag_json_str else {}
    except Exception:
        pag = {}

    tipo         = (pag.get("tipo") or "").lower()
    nome_forma   = pag.get("nome_forma") or ""
    entrada_val  = float(pag.get("entrada_valor") or 0)
    entrada_data = _formatar_data_br(pag.get("entrada_data") or "")
    entrada_tipo = _forma_label(pag.get("entrada_forma") or pag.get("entrada_tipo") or "")
    parcelas     = pag.get("parcelas") or []
    num_parcelas = len(parcelas)

    if tipo == "cartao":
        forma_parcela = "Cartão de Crédito"
    elif parcelas:
        forma_parcela = _forma_label(parcelas[0].get("forma") or "")
    else:
        forma_parcela = ""

    # Grade p01..p24 — datas e valores diretamente das parcelas reais capturadas
    datas, valores = [], []
    for p in parcelas:
        if tipo == "cartao":
            datas.append("")   # cartão: parcelas não têm data na grade
        else:
            datas.append(_formatar_data_br(p.get("data") or ""))
        valores.append(_formatar_valor_str(p.get("valor")))
    datas   = (datas   + [""] * 24)[:24]
    valores = (valores + [""] * 24)[:24]

    if tipo == "cartao" and num_parcelas == 1:
        num_parcelas_disp = "à vista"
    elif num_parcelas:
        num_parcelas_disp = str(num_parcelas)
    else:
        num_parcelas_disp = "—"

    total_cliente = pag.get("total_cliente") or 0
    return {
        "tipo":             tipo,
        "nome_forma":       nome_forma,
        "entrada_valor":    _formatar_valor(entrada_val),
        "entrada_tipo":     entrada_tipo,
        "entrada_data":     entrada_data,
        "modalidade":       nome_forma,
        "num_parcelas":     num_parcelas_disp,
        "num_parcelas_int": num_parcelas,
        "data_primeira":    (datas[0] if datas and datas[0] else ""),
        "datas":            datas,          # lista de 24 strings (data ou "")
        "valores":          valores,        # lista de 24 strings (valor ou "")
        "valor_contrato":   _formatar_valor(total_cliente),
        "texto_cartao":     pag.get("texto_cartao") or "",
        "forma_parcela":    forma_parcela,
    }


# ── Guard de desatualização ───────────────────────────────────────────────────

def contrato_desatualizado(pagamento_snapshot_json, forma_pagamento_atual_json):
    """True se o pagamento mudou após a geração do contrato (modalidade 'tipo' ou 'total_cliente').
    Compara 'tipo' e 'total_cliente' (arredondado a 2 casas). Retorna False se não der pra comparar."""
    import json as _json
    def _p(x):
        if not x: return None
        try: return _json.loads(x) if isinstance(x, str) else x
        except Exception: return None
    a = _p(pagamento_snapshot_json); b = _p(forma_pagamento_atual_json)
    if not a or not b:
        return False
    if (a.get("tipo") or "") != (b.get("tipo") or ""):
        return True
    return round(float(a.get("total_cliente") or 0), 2) != round(float(b.get("total_cliente") or 0), 2)


# ── Validação de dados do cliente ─────────────────────────────────────────────

def validar_cliente_para_contrato(cliente: dict) -> list:
    """
    Retorna a lista de rótulos dos campos obrigatórios que estão vazios para
    gerar um contrato a partir do dict do cliente (formato _cliente_dict).

    Lista vazia → cliente está completo e pode gerar o contrato.

    Regra: identificação + endereço residencial são sempre obrigatórios.
    O endereço de instalação só é cobrado quando NÃO for o mesmo do residencial
    (inst_mesmo_residencial falso) — quando é o mesmo, o residencial é reutilizado.
    Complemento é opcional em ambos.

    Documento por tipo de destinatário (tipo_dest):
    - "contribuinte"/"isento" → exige CNPJ (CPF não substitui);
    - "nao_contribuinte" (default) → exige CPF.
    A Inscrição Estadual (IE) NÃO é exigida aqui — não bloqueia o contrato.
    """
    tipo_dest = (cliente.get("tipo_dest") or "nao_contribuinte").strip()
    doc_campo, doc_rotulo = (
        ("cnpj", "CNPJ") if tipo_dest in ("contribuinte", "isento")
        else ("cpf", "CPF")
    )
    obrigatorios = [
        ("nome",       "Nome"),
        (doc_campo,    doc_rotulo),
        ("email",      "E-mail"),
        ("telefone",   "Telefone"),
        ("logradouro", "Logradouro (residencial)"),
        ("numero",     "Número (residencial)"),
        ("bairro",     "Bairro (residencial)"),
        ("cidade",     "Cidade (residencial)"),
        ("cep",        "CEP (residencial)"),
        ("estado",     "Estado/UF (residencial)"),
    ]

    inst_mesmo = cliente.get("inst_mesmo_residencial", True)
    if not inst_mesmo:
        obrigatorios += [
            ("inst_logradouro", "Logradouro (instalação)"),
            ("inst_numero",     "Número (instalação)"),
            ("inst_bairro",     "Bairro (instalação)"),
            ("inst_cidade",     "Cidade (instalação)"),
            ("inst_cep",        "CEP (instalação)"),
            ("inst_uf",         "UF (instalação)"),
        ]

    faltando = []
    for campo, rotulo in obrigatorios:
        valor = cliente.get(campo)
        if not (valor and str(valor).strip()):
            faltando.append(rotulo)
    return faltando


# ── Validação de dados da loja ────────────────────────────────────────────────

_TEM_DIGITO = _re_mark.compile(r"\d")   # CPF real tem ao menos um dígito


def validar_loja_para_contrato(loja: dict) -> list:
    """Rótulos dos campos obrigatórios da loja que estão vazios para gerar o contrato.

    Lista vazia → loja completa. O CPF de testemunha sem nenhum dígito
    (placeholder 'xxx.xxx.xxx-xx') conta como faltando. `complemento` é opcional.
    """
    loja = loja or {}
    obrigatorios = [
        ("nome",             "Nome da empresa"),
        ("cnpj",             "CNPJ"),
        ("codigo",           "Código da loja"),
        ("telefone",         "Telefone"),
        ("email",            "E-mail"),
        ("cep",              "CEP"),
        ("logradouro",       "Logradouro"),
        ("numero",           "Número"),
        ("bairro",           "Bairro"),
        ("cidade",           "Cidade"),
        ("estado",           "Estado/UF"),
        ("testemunha1_nome", "Nome da Testemunha 1"),
        ("testemunha2_nome", "Nome da Testemunha 2"),
    ]
    faltando = []
    for campo, rotulo in obrigatorios:
        v = loja.get(campo)
        if not (v and str(v).strip()):
            faltando.append(rotulo)
    for campo, rotulo in [("testemunha1_cpf", "CPF da Testemunha 1"),
                          ("testemunha2_cpf", "CPF da Testemunha 2")]:
        v = (loja.get(campo) or "").strip()
        if not _TEM_DIGITO.search(v):
            faltando.append(rotulo)
    return faltando


# ── Preenchimento dinâmico do modelo ─────────────────────────────────────────

def _montar_mapping(ctx, pag):
    """Monta o dicionário {MARCADOR: valor} para _substituir_marcadores_html().

    Chaves em MAIÚSCULAS sem colchetes, casando com os marcadores do template
    HTML do contrato. A grade de parcelas e os ambientes são montados à parte
    (_html_parcelas_linhas/_html_ambientes_linhas); aqui só entram os campos de
    cabeçalho/identificação. Os dados da loja vêm de ctx['loja'] (F3).
    """
    loja = ctx.get("loja") or {}
    t1n = loja.get("testemunha1_nome", "") or ""
    t1c = loja.get("testemunha1_cpf", "") or ""
    t2n = loja.get("testemunha2_nome", "") or ""
    t2c = loja.get("testemunha2_cpf", "") or ""
    return {
        "NUM_CONTRATO":     str(ctx.get("num_contrato", "") or ""),
        "DATA_CONTRATO":    str(ctx.get("data_contrato", "") or ""),
        "NOME_CLIENTE":     ctx.get("cliente_nome", "") or "",
        "CPF":              ctx.get("cliente_cpf", "") or "",
        "EMAIL":            ctx.get("cliente_email", "") or "",
        "TELEFONE":         ctx.get("cliente_telefone", "") or "",
        "RES_LOGRADOURO":   ctx.get("res_logradouro", "") or "",
        "RES_NUMERO":       ctx.get("res_numero", "") or "",
        "RES_COMPLEMENTO":  ctx.get("res_complemento", "") or "",
        "RES_BAIRRO":       ctx.get("res_bairro", "") or "",
        "RES_CIDADE":       ctx.get("res_cidade", "") or "",
        "RES_CEP":          ctx.get("res_cep", "") or "",
        "RES_UF":           ctx.get("res_uf", "") or "",
        "INST_LOGRADOURO":  ctx.get("inst_logradouro", "") or "",
        "INST_NUMERO":      ctx.get("inst_numero", "") or "",
        "INST_COMPLEMENTO": ctx.get("inst_complemento", "") or "",
        "INST_BAIRRO":      ctx.get("inst_bairro", "") or "",
        "INST_CIDADE":      ctx.get("inst_cidade", "") or "",
        "INST_CEP":         ctx.get("inst_cep", "") or "",
        "INST_UF":          ctx.get("inst_uf", "") or "",
        "VALOR_ENTRADA":    pag.get("entrada_valor", "") or "",
        "FORMA_ENTRADA":    pag.get("entrada_tipo", "") or "",
        "DATA_ENTRADA":     pag.get("entrada_data", "") or "",
        "MODALIDADE":       pag.get("nome_forma", "") or "",
        "NUM_PARCELAS":     pag.get("num_parcelas", "") or "",
        "TIPO":             pag.get("forma_parcela", "") or "",
        "TOTAL_CONTRATO":   pag.get("valor_contrato", "") or "",
        "CONSULTOR_NOME":     ctx.get("consultor_nome", "") or "",
        "CONSULTOR_TELEFONE": ctx.get("consultor_tel", "") or "",
        # Identificador da rede sob o logo (parâmetro de config do contrato;
        # fallback p/ a cidade da loja enquanto o campo de config não é definido)
        "REDE_IDENTIFICADOR": ctx.get("rede_identificador", "") or loja.get("cidade", "") or "",
        "TESTEMUNHA_1_NOME": t1n,
        "TESTEMUNHA_1_DOC":  t1c,
        "TESTEMUNHA_2_NOME": t2n,
        "TESTEMUNHA_2_DOC":  t2c,
        "NOME_TESTEMUNHA_1": t1n,
        "NOME_TESTEMUNHA2":  t2n,
        "NOME_TESTEMUNHA_2": t2n,
        "NOME_EMPRESA":      loja.get("nome", "") or "",
        "CNPJ_EMPRESA":      loja.get("cnpj", "") or "",
        "LOJA_LOGRADOURO":   loja.get("logradouro", "") or "",
        "LOJA_NUMERO":       loja.get("numero", "") or "",
        "LOJA_COMPLEMENTO":  loja.get("complemento", "") or "",
        "LOJA_BAIRRO":       loja.get("bairro", "") or "",
        "LOJA_CIDADE":       loja.get("cidade", "") or "",
        "LOJA_UF":           loja.get("estado", "") or "",
        "LOJA_CEP":          loja.get("cep", "") or "",
        "LOJA_TELEFONE":     loja.get("telefone", "") or "",
        "LOJA_EMAIL":        loja.get("email", "") or "",
        "CPF_CLIENTE":       ctx.get("cliente_cpf", "") or "",
        "CPF_TESTEMUNHA_1":  t1c,
        "CPF_TESTEMUNHA_2":  t2c,
        "DATA_PREVISTA_ENTREGA": ctx.get("data_prevista_entrega", "") or "",
        "PREVISAO_MEDICAO":      ctx.get("previsao_medicao", "") or "",
        "PRAZO_CONTRATUAL":      ctx.get("prazo_contratual", "") or "",
        "VENDA_PROGRAMADA":      ctx.get("venda_programada_txt", "") or "",
        # Termo Aditivo (Fatia 3 PE): preenchidos via ctx["_aditivo"] pelo endpoint de geração;
        # no contrato/proposta saem vazios (padrão dos extras).
        "NUM_ADITIVO":            (ctx.get("_aditivo") or {}).get("num_aditivo", "") or "",
        "NUM_CONTRATO_ORIGINAL":  (ctx.get("_aditivo") or {}).get("num_contrato_original", "") or "",
        # Modelo jurídico completo do aditivo (spec 2026-07-22): ordinal do título, datas e os
        # 5 blocos dos modais sequenciais (texto final editado pelo operador, ou o default).
        # DATA_CONTRATO_ORIGINAL é marcador PRÓPRIO: DATA_CONTRATO segue sendo a do documento
        # corrente nos demais modelos — sobrecarregá-lo aqui quebraria contratos.
        "ORDINAL_ADITIVO":        (ctx.get("_aditivo") or {}).get("ordinal", "") or "",
        "DATA_ADITIVO":           (ctx.get("_aditivo") or {}).get("data_aditivo", "") or "",
        "DATA_CONTRATO_ORIGINAL": (ctx.get("_aditivo") or {}).get("data_contrato_original", "") or "",
        "ADITIVO_CONSIDERANDOS":  (ctx.get("_aditivo") or {}).get("considerandos", "") or "",
        "ADITIVO_LISTA_INTEGRAL": (ctx.get("_aditivo") or {}).get("lista_integral", "") or "",
        "ADITIVO_INCLUSOES":      (ctx.get("_aditivo") or {}).get("inclusoes", "") or "",
        "ADITIVO_EXCLUSOES":      (ctx.get("_aditivo") or {}).get("exclusoes", "") or "",
        "ADITIVO_VALORES":        (ctx.get("_aditivo") or {}).get("valores", "") or "",
        "AMBIENTES_COMPLEMENTO": (ctx.get("_aditivo") or {}).get("ambientes_txt", "") or "",
        "VALOR_ORIGINAL_COMPLEMENTO":  (ctx.get("_aditivo") or {}).get("valor_original", "") or "",
        "VALOR_NOVO_COMPLEMENTO":      (ctx.get("_aditivo") or {}).get("valor_novo", "") or "",
        "VALOR_COMPLEMENTO":       (ctx.get("_aditivo") or {}).get("diferenca", "") or "",
        # Aprovação do PE (correção Fatia 3): preenchidos via ctx["_aprovacao_pe"]
        "NUM_APROVACAO_PE":    (ctx.get("_aprovacao_pe") or {}).get("num_aprovacao", "") or "",
        "AMBIENTES_APROVADOS": (ctx.get("_aprovacao_pe") or {}).get("ambientes_txt", "") or "",
        # Solicitação de Medição (achado do usuário 2026-08-17): preenchido via
        # ctx["_solicitacao_medicao"] pelo endpoint de geração.
        "AMBIENTES_MEDICAO": (ctx.get("_solicitacao_medicao") or {}).get("ambientes_txt", "") or "",
    }


def _html_cabecalho():
    """Cabeçalho padrão dos documentos — logo + identificador da rede à esquerda, número e
    data à direita. Compartilhado entre a capa do contrato/proposta e os documentos de
    corpo-só (aditivo, aprovação do PE, customizados — spec 2026-07-22): um lugar só."""
    return """
<div id="cabecalho">
  <div class="cab-esq">
    <img class="logo" src="logo_dalmobile.png">
    <div class="cab-rede">[REDE_IDENTIFICADOR]</div>
  </div>
  <div class="cab-dir">[NUM_CONTRATO]<br>[DATA_CONTRATO]</div>
</div>
"""


def _html_capa(ctx):
    """Monta o HTML da capa (identificação, endereços, ambientes e pagamento).

    Consome _html_ambientes_linhas/_html_parcelas_linhas para as linhas dinâmicas
    e deixa os demais campos como [MARCADORES] a serem resolvidos por
    _substituir_marcadores_html() com o mapping de _montar_mapping().
    """
    amb = _html_ambientes_linhas(ctx.get("_ambientes") or [])
    parc = _html_parcelas_linhas(ctx.get("_pag") or {})
    return f"""
{_html_cabecalho()}

<div class="consultor">Consultor: [CONSULTOR_NOME] &nbsp;&nbsp;&nbsp; Telefone: [CONSULTOR_TELEFONE]</div>

<div class="secao">
  <div class="titulo">1. Identificação do Cliente</div>
  <table><tr>
    <td><span class="rotulo">Nome</span><span class="valor">[NOME_CLIENTE]</span></td>
    <td><span class="rotulo">CPF/CNPJ</span><span class="valor">[CPF]</span></td>
  </tr><tr>
    <td><span class="rotulo">E-mail</span><span class="valor">[EMAIL]</span></td>
    <td><span class="rotulo">Telefone</span><span class="valor">[TELEFONE]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">2. Endereço Residencial</div>
  <table><tr>
    <td colspan="3"><span class="rotulo">Logradouro</span><span class="valor">[RES_LOGRADOURO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Número</span><span class="valor">[RES_NUMERO]</span></td>
    <td><span class="rotulo">Complemento</span><span class="valor">[RES_COMPLEMENTO]</span></td>
    <td><span class="rotulo">Bairro</span><span class="valor">[RES_BAIRRO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Cidade</span><span class="valor">[RES_CIDADE]</span></td>
    <td><span class="rotulo">CEP</span><span class="valor">[RES_CEP]</span></td>
    <td><span class="rotulo">Estado/UF</span><span class="valor">[RES_UF]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">3. Endereço de Instalação</div>
  <table><tr>
    <td colspan="3"><span class="rotulo">Logradouro</span><span class="valor">[INST_LOGRADOURO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Número</span><span class="valor">[INST_NUMERO]</span></td>
    <td><span class="rotulo">Complemento</span><span class="valor">[INST_COMPLEMENTO]</span></td>
    <td><span class="rotulo">Bairro</span><span class="valor">[INST_BAIRRO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Cidade</span><span class="valor">[INST_CIDADE]</span></td>
    <td><span class="rotulo">CEP</span><span class="valor">[INST_CEP]</span></td>
    <td><span class="rotulo">Estado/UF</span><span class="valor">[INST_UF]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">4. Ambientes do Projeto</div>
  <table>
    {amb}
    <tr><td class="total-lbl" colspan="2">VALOR DO CONTRATO</td>
        <td class="total-val" colspan="2">[TOTAL_CONTRATO]</td></tr>
  </table>
</div>

<div class="secao">
  <div class="titulo">5. Forma de Pagamento</div>
  <table><tr>
    <td><span class="rotulo">Entrada</span><span class="valor">[VALOR_ENTRADA]</span></td>
    <td><span class="rotulo">Tipo</span><span class="valor">[FORMA_ENTRADA]</span></td>
    <td><span class="rotulo">Data</span><span class="valor">[DATA_ENTRADA]</span></td>
  </tr><tr>
    <td><span class="rotulo">Modalidade</span><span class="valor">[MODALIDADE]</span></td>
    <td><span class="rotulo">Parcelas</span><span class="valor">[NUM_PARCELAS]</span></td>
    <td><span class="rotulo">Valor do Contrato</span><span class="valor">[TOTAL_CONTRATO]</span></td>
  </tr></table>
  <table>{parc}</table>
</div>

<div class="quebra-capa"></div>
"""


def _carregar_md():
    """Lê contrato_template/contrato.md; retorna "" se o arquivo ainda não existir."""
    p = os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def _resolver_corpo_contrato(ctx):
    """Markdown das cláusulas deste contrato.

    Ordem: preview (tela de importação) > versão fixada no contrato (reproduz o
    assinado) > modelo ativo da loja > contrato_template/contrato.md global
    (contrato legado / loja sem modelo próprio). ctx['_db'] e
    ctx['_modelo_versao_id'] vêm do chamador; sem eles o comportamento é o de hoje.

    CUIDADO: quando o chamador PASSA a chave '_modelo_versao_id' (mesmo com valor
    None — é o caso do contrato legado, onde versao_para_contrato() decidiu de
    propósito "não fixar nada"), a resposta dele é FINAL. Cair aqui no modelo ativo
    da loja reabriria exatamente o buraco que esta frente existe para fechar:
    contrato legado que nunca teve versão teria a cláusula nova aplicada assim que a
    loja subisse um modelo — comprovado por execução (E2E real: um contrato legado
    da Loja 2, ao ganhar um modelo ativo DEPOIS de já gerado, vazava a cláusula nova
    até esta correção). O fallback pro "ativo da loja" só faz sentido quando o
    chamador nem tentou resolver (chave ausente) — hoje nenhum call site real faz
    isso; é reserva pra um futuro chamador que só queira "o vigente", sem fixar.
    """
    if ctx.get("_corpo_md_preview") is not None:
        return ctx["_corpo_md_preview"]
    db = ctx.get("_db")
    if db is None:
        return _carregar_md()
    import mod_documentos
    if "_modelo_versao_id" in ctx:
        versao_id = ctx["_modelo_versao_id"]
        if versao_id:
            corpo = mod_documentos.corpo_da_versao(db, versao_id)
            if corpo is not None:
                return corpo
        return _carregar_md()
    loja_id = (ctx.get("loja") or {}).get("id")
    if loja_id:
        return mod_documentos.resolver_modelo(db, loja_id, "contrato")
    return _carregar_md()


def _montar_html_contrato(ctx):
    """Monta o HTML final do contrato: capa + corpo, com [MARCADORES] substituídos."""
    from html import escape
    pag = ctx.get("_pag", {})
    mapping = _montar_mapping(ctx, pag)
    mapping["TEXTO_COMPLEMENTAR"] = ctx.get("adendo", "") or ""
    # escapa os VALORES dos marcadores (dados do cliente/loja/adendo) para HTML —
    # nomes/endereços/adendo (texto livre) não podem corromper o documento.
    # (o escape é aqui, no caminho HTML; _montar_mapping é compartilhado com a
    #  proposta, que ainda gera .docx e não deve receber texto escapado.)
    mapping = {k: escape(str(v)) for k, v in mapping.items()}
    if mapping["TEXTO_COMPLEMENTAR"]:
        mapping["TEXTO_COMPLEMENTAR"] = mapping["TEXTO_COMPLEMENTAR"].replace("\n", "<br>")
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"),
                 encoding="utf-8").read()
    capa = _html_capa(ctx)
    corpo = _html_corpo(_resolver_corpo_contrato(ctx))
    html = shell.replace("<!--CAPA-->", capa).replace("<!--CORPO-->", corpo)
    html = _substituir_marcadores_html(html, mapping)
    # sem adendo: remove o parágrafo vazio (evita traço/espaço solto no fim)
    if not mapping.get("TEXTO_COMPLEMENTAR"):
        html = html.replace('<p class="adendo"></p>', "")
    return html


def construir_contexto(cliente: dict, usuario: dict, forma_pagamento_json: str, loja: dict = None) -> dict:
    """Monta o dicionário completo para preencher o contrato.

    `loja`: dict com dados da loja (F3) — usado como fallback de telefone/email do
    consultor e injetado em ctx['loja'] para _montar_mapping(). Opcional; se None,
    os campos de empresa/testemunhas ficarão em branco no contrato.
    """
    loja = loja or {}
    inst_mesmo = cliente.get("inst_mesmo_residencial", True)
    if inst_mesmo:
        inst = {k: cliente.get(r, "") for k, r in [
            ("logradouro","logradouro"), ("numero","numero"),
            ("complemento","complemento"), ("bairro","bairro"),
            ("cidade","cidade"), ("cep","cep"), ("uf","estado"),
        ]}
    else:
        inst = {
            "logradouro":  cliente.get("inst_logradouro",  ""),
            "numero":      cliente.get("inst_numero",      ""),
            "complemento": cliente.get("inst_complemento", ""),
            "bairro":      cliente.get("inst_bairro",      ""),
            "cidade":      cliente.get("inst_cidade",      ""),
            "cep":         cliente.get("inst_cep",         ""),
            "uf":          cliente.get("inst_uf",          ""),
        }

    pag = _parse_pagamento(forma_pagamento_json)
    datas = pag["datas"]

    ctx = {
        "consultor_nome":  usuario.get("nome",     "") or "",
        "consultor_tel":   (usuario.get("telefone") or "").strip() or (loja.get("telefone") or ""),
        "consultor_email": (usuario.get("email")    or "").strip() or (loja.get("email")    or ""),
        "cliente_nome":    cliente.get("nome",     "") or "",
        "cliente_cpf":     cliente.get("cpf",      "") or "",
        "cliente_email":   cliente.get("email",    "") or "",
        "cliente_telefone":cliente.get("telefone", "") or "",
        "res_logradouro":  cliente.get("logradouro",  "") or "",
        "res_numero":      cliente.get("numero",      "") or "",
        "res_complemento": cliente.get("complemento", "") or "",
        "res_bairro":      cliente.get("bairro",      "") or "",
        "res_cidade":      cliente.get("cidade",      "") or "",
        "res_cep":         cliente.get("cep",         "") or "",
        "res_uf":          cliente.get("estado",      "") or "",
        "inst_logradouro":  inst["logradouro"],
        "inst_numero":      inst["numero"],
        "inst_complemento": inst["complemento"],
        "inst_bairro":      inst["bairro"],
        "inst_cidade":      inst["cidade"],
        "inst_cep":         inst["cep"],
        "inst_uf":          inst["uf"],
        # Pagamento — chaves planas para compatibilidade com templates antigos
        "pgto_entrada_valor":  pag["entrada_valor"],
        "pgto_entrada_tipo":   pag["entrada_tipo"],
        "pgto_entrada_data":   pag["entrada_data"],
        "pgto_modalidade":     pag["modalidade"],
        "pgto_num_parcelas":   pag["num_parcelas"],
        "pgto_data_primeira":  pag["data_primeira"],
        "data_contrato":       datetime.now().strftime("%d/%m/%Y"),
        "_pag":                pag,   # dict normalizado para gerar_pdf_contrato()
        "loja":                loja,
    }
    # Grade de datas p01..p24
    for i in range(24):
        ctx[f"p{i+1:02d}_data"] = datas[i]
    return ctx


def _url_fetcher_local(url):
    """url_fetcher do WeasyPrint restrito aos assets do template. Defesa em profundidade.

    O corpo do contrato hoje vem do modelo que a LOJA subiu (entrada de usuário). O
    escape em _html_corpo já impede HTML embutido de virar tag; este fetcher é a segunda
    camada: mesmo que algum caminho futuro deixe escapar um <img>/@import, o renderizador
    não busca nada fora de CONTRATO_TEMPLATE_DIR. Fecha SSRF (alcançar serviço interno) e
    LFI (url(file:///etc/passwd)) na origem, no único ponto por onde o WeasyPrint busca
    recurso.

    O template legítimo só referencia dois assets, ambos relativos e resolvidos contra
    base_url=CONTRATO_TEMPLATE_DIR: contrato.css (<link> em contrato.html) e
    logo_dalmobile.png (<img> montado em _html_capa). Os dois continuam carregando —
    tests/test_documentos_seguranca.py trava isso, senão a "correção" quebraria o
    contrato de produção para fechar o furo.

    Tudo que não for file:// sob o diretório do template é recusado: http(s):// (rede),
    file:// fora dali (disco), e esquemas exóticos. WeasyPrint trata a exceção como
    "asset indisponível", loga aviso e segue — o PDF sai, sem o recurso bloqueado.
    """
    from urllib.parse import urlparse, unquote
    from urllib.request import url2pathname
    from weasyprint.urls import default_url_fetcher

    partes = urlparse(url)
    if partes.scheme != "file":
        raise ValueError("recurso externo bloqueado no documento: %s" % url)
    try:
        alvo = os.path.realpath(url2pathname(unquote(partes.path)))
        base = os.path.realpath(CONTRATO_TEMPLATE_DIR)
        # commonpath levanta ValueError p/ drives diferentes (Windows) — é caso a recusar.
        dentro = os.path.commonpath([base, alvo]) == base
    except (ValueError, OSError):
        raise ValueError("recurso local bloqueado no documento: %s" % url)
    if not dentro:
        raise ValueError("recurso local fora do template bloqueado: %s" % url)
    return default_url_fetcher(url)


def gerar_pdf_contrato(contrato_id: int, ctx: dict, destino: str = None) -> str:
    """Renderiza o contrato (HTML -> PDF) via WeasyPrint. Retorna o caminho do PDF."""
    from weasyprint import HTML
    destino = destino or CONTRATOS_DIR
    os.makedirs(destino, exist_ok=True)
    html = _montar_html_contrato(ctx)
    pdf_path = os.path.join(destino, f"contrato_{contrato_id}.pdf")
    with PDF_LOCK:
        HTML(string=html, base_url=CONTRATO_TEMPLATE_DIR,
             url_fetcher=_url_fetcher_local).write_pdf(pdf_path)
    return pdf_path


def _resolver_corpo_proposta(ctx):
    """Markdown do corpo da proposta. Sem _db ou sem loja_id -> "" (capa-só,
    como sempre foi). A proposta não tem fallback pro template global: o
    contrato.md global é do CONTRATO; proposta sem modelo próprio não tem corpo."""
    db = ctx.get("_db")
    loja_id = (ctx.get("loja") or {}).get("id")
    if db is None or not loja_id:
        return ""
    import mod_documentos    # local: mod_documentos importa mod_contrato (ciclo)
    return mod_documentos.resolver_modelo(db, loja_id, "proposta")


def montar_html_proposta(ctx):
    """HTML da proposta comercial = PRIMEIRA PÁGINA do contrato (capa), seguida do
    corpo (cláusulas) do modelo 'proposta' ativo da loja, se houver. Sem modelo (ou
    sem ctx['_db']): capa-só, PDF de uma página, como sempre foi.
    O número no canto superior direito usa ctx['num_contrato'] (deve conter o num_proposta 'PV...')."""
    from html import escape
    mapping = {k: escape(str(v)) for k, v in _montar_mapping(ctx, ctx.get("_pag", {})).items()}
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"), encoding="utf-8").read()
    corpo_md = _resolver_corpo_proposta(ctx)
    capa = _html_capa(ctx)
    if not corpo_md:
        capa = capa.replace('<div class="quebra-capa"></div>', "")   # uma página só
    corpo = _html_corpo(corpo_md) if corpo_md else ""
    html = shell.replace("<!--CAPA-->", capa).replace("<!--CORPO-->", corpo)
    return _substituir_marcadores_html(html, mapping)


def gerar_pdf_proposta(ctx: dict, destino_pdf: str) -> str:
    """Renderiza a proposta comercial (capa do contrato) em PDF via WeasyPrint. Retorna o caminho."""
    from weasyprint import HTML
    _dir = os.path.dirname(destino_pdf)
    if _dir:
        os.makedirs(_dir, exist_ok=True)
    with PDF_LOCK:
        HTML(string=montar_html_proposta(ctx), base_url=CONTRATO_TEMPLATE_DIR,
             url_fetcher=_url_fetcher_local).write_pdf(destino_pdf)
    return destino_pdf


# ── Documentos de corpo-só (Fatia 3 PE): Termo Aditivo e Aprovação do PE ──────

def _montar_html_corpo_documento(ctx, corpo_md):
    """HTML de um documento SEM capa: só o corpo do modelo da loja no shell do contrato, com o
    mapping completo do CATALOGO (os marcadores específicos vêm de ctx['_aditivo'] /
    ctx['_aprovacao_pe'], preenchidos pelo endpoint de geração). TEXTO_COMPLEMENTAR não se
    aplica — removido se o modelo o trouxer."""
    from html import escape
    # \n → <br>: a substituição de marcadores acontece DEPOIS de o corpo virar <p> por linha
    # (_html_corpo), então um valor multi-linha (considerandos, listas do aditivo) colapsaria
    # numa linha só — o HTML ignora \n. O escape vem ANTES; o <br> é nosso, não do lojista.
    mapping = {k: escape(str(v)).replace("\n", "<br>")
               for k, v in _montar_mapping(ctx, ctx.get("_pag", {})).items()}
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"), encoding="utf-8").read()
    corpo = _html_corpo(corpo_md or "")
    # Cabeçalho aos moldes do contrato também nos corpo-só (spec 2026-07-22) — o número
    # vem de ctx['num_contrato'] (no aditivo, o nº TA) e a data de ctx['data_contrato'].
    html_doc = (shell.replace("<!--CAPA-->", _html_cabecalho())
                     .replace("<!--CORPO-->", corpo))
    html_doc = _substituir_marcadores_html(html_doc, mapping)
    return html_doc.replace("[TEXTO_COMPLEMENTAR]", "")


def _gerar_pdf_corpo_documento(html_doc: str, destino_pdf: str) -> str:
    """PDF via WeasyPrint com o MESMO confinamento de assets do contrato."""
    from weasyprint import HTML
    _dir = os.path.dirname(destino_pdf)
    if _dir:
        os.makedirs(_dir, exist_ok=True)
    with PDF_LOCK:
        HTML(string=html_doc, base_url=CONTRATO_TEMPLATE_DIR,
             url_fetcher=_url_fetcher_local).write_pdf(destino_pdf)
    return destino_pdf


def montar_html_aditivo(ctx):
    """Termo Aditivo: corpo do modelo 'termo_aditivo' (ctx['_corpo_md_aditivo'], versão CONGELADA)."""
    return _montar_html_corpo_documento(ctx, ctx.get("_corpo_md_aditivo"))


def gerar_pdf_documento_generico(ctx: dict, corpo_md: str, destino_pdf: str) -> str:
    """Documento customizado ("Novo Documento", spec 2026-07-22): corpo-só + cabeçalho,
    mesmo shell/confinamento dos demais."""
    return _gerar_pdf_corpo_documento(_montar_html_corpo_documento(ctx, corpo_md), destino_pdf)


def gerar_pdf_aditivo(ctx: dict, destino_pdf: str) -> str:
    return _gerar_pdf_corpo_documento(montar_html_aditivo(ctx), destino_pdf)


def montar_html_aprovacao_pe(ctx):
    """Aprovação do Projeto Executivo: corpo do modelo 'aprovacao_pe' (ctx['_corpo_md_aprovacao'],
    versão CONGELADA na 1ª geração), com [AMBIENTES_APROVADOS]/[NUM_APROVACAO_PE]."""
    return _montar_html_corpo_documento(ctx, ctx.get("_corpo_md_aprovacao"))


def gerar_pdf_aprovacao_pe(ctx: dict, destino_pdf: str) -> str:
    return _gerar_pdf_corpo_documento(montar_html_aprovacao_pe(ctx), destino_pdf)


def montar_html_solicitacao_medicao(ctx):
    """Termo de Responsabilidade e Solicitação de Medição (achado do usuário 2026-08-17):
    corpo do modelo 'solicitacao_medicao' (ctx['_corpo_md_solicitacao_medicao']), com
    [AMBIENTES_MEDICAO]/[PREVISAO_MEDICAO] (este já existia no catálogo geral)."""
    return _montar_html_corpo_documento(ctx, ctx.get("_corpo_md_solicitacao_medicao"))


def gerar_pdf_solicitacao_medicao(ctx: dict, destino_pdf: str) -> str:
    return _gerar_pdf_corpo_documento(montar_html_solicitacao_medicao(ctx), destino_pdf)


# ── LibreOffice ───────────────────────────────────────────────────────────────
#
# NÃO é legado, apesar de o nome sugerir: é a base da IMPORTAÇÃO de modelo de
# documento (mod_documentos_import.normalizar) — o único caminho que achata a
# numeração automática do Word em texto literal. Medido num .docx real:
# LibreOffice preserva 63 números de cláusula, python-docx preserva 3.
#
# ÚNICO consumidor hoje: mod_documentos_import. A conversão .docx→PDF
# (_converter_pdf) e o contrato_editar.py morreram na faxina de 2026-07-15.

class LibreOfficeIndisponivel(Exception):
    def __init__(self, docx_path: str):
        self.docx_path = docx_path
        super().__init__(
            "LibreOffice não encontrado no servidor.\n"
            "É necessário para importar modelo de documento (.docx/.odt/.doc/.rtf):\n"
            "só ele achata a numeração automática do Word em texto."
        )


def _libreoffice_cmd() -> str:
    if platform.system() == "Windows":
        for p in [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]:
            if os.path.exists(p):
                return p
    return "libreoffice"
