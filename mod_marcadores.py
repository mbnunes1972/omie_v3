# -*- coding: utf-8 -*-
"""mod_marcadores.py — Catálogo dos [MARCADORES] aceitos nos modelos de documento.

Fonte única do que EXISTE. Quem calcula os VALORES é mod_contrato._montar_mapping();
tests/test_marcadores.py trava os dois juntos — se um ganhar chave que o outro não
tem, a suíte quebra. Ao acrescentar marcador, mexa nos DOIS.
"""

CATALOGO = {
    # ── documento ────────────────────────────────────────────────────────────
    "NUM_CONTRATO":       {"rotulo": "Número do contrato",      "escopo": "documento"},
    "DATA_CONTRATO":      {"rotulo": "Data do contrato",        "escopo": "documento"},
    "TEXTO_COMPLEMENTAR": {"rotulo": "Adendo (texto livre)",    "escopo": "documento"},
    "REDE_IDENTIFICADOR": {"rotulo": "Identificador da rede",   "escopo": "documento"},
    "DATA_PREVISTA_ENTREGA": {"rotulo": "Data prevista de entrega (expectativa)", "escopo": "documento"},
    "PREVISAO_MEDICAO":      {"rotulo": "Previsão de medição",                    "escopo": "documento"},
    "PRAZO_CONTRATUAL":      {"rotulo": "Prazo contratual (dias úteis)",          "escopo": "documento"},
    "VENDA_PROGRAMADA":      {"rotulo": "Venda programada (observação)",          "escopo": "documento"},

    # ── cliente ──────────────────────────────────────────────────────────────
    "NOME_CLIENTE":     {"rotulo": "Nome do cliente",           "escopo": "cliente"},
    # CPF e CPF_CLIENTE são o MESMO dado, e os DOIS estão vivos em partes
    # diferentes do documento: [CPF] na capa (mod_contrato._html_capa, linha 669)
    # e [CPF_CLIENTE] no corpo (contrato_template/contrato.md). Nenhum é alias de
    # ninguém — chamar qualquer um de secundário mandaria o lojista usar o
    # marcador errado para a parte que ele está editando. O corpo é o que se
    # importa aqui, então ESSENCIAIS reporta CPF_CLIENTE como o canônico.
    "CPF":              {"rotulo": "CPF do cliente (usado na capa)",  "escopo": "cliente"},
    "CPF_CLIENTE":      {"rotulo": "CPF do cliente (usado no corpo)", "escopo": "cliente"},
    "EMAIL":            {"rotulo": "E-mail do cliente",         "escopo": "cliente"},
    "TELEFONE":         {"rotulo": "Telefone do cliente",       "escopo": "cliente"},
    "RES_LOGRADOURO":   {"rotulo": "Residencial — logradouro",  "escopo": "cliente"},
    "RES_NUMERO":       {"rotulo": "Residencial — número",      "escopo": "cliente"},
    "RES_COMPLEMENTO":  {"rotulo": "Residencial — complemento", "escopo": "cliente"},
    "RES_BAIRRO":       {"rotulo": "Residencial — bairro",      "escopo": "cliente"},
    "RES_CIDADE":       {"rotulo": "Residencial — cidade",      "escopo": "cliente"},
    "RES_CEP":          {"rotulo": "Residencial — CEP",         "escopo": "cliente"},
    "RES_UF":           {"rotulo": "Residencial — UF",          "escopo": "cliente"},
    "INST_LOGRADOURO":  {"rotulo": "Instalação — logradouro",   "escopo": "cliente"},
    "INST_NUMERO":      {"rotulo": "Instalação — número",       "escopo": "cliente"},
    "INST_COMPLEMENTO": {"rotulo": "Instalação — complemento",  "escopo": "cliente"},
    "INST_BAIRRO":      {"rotulo": "Instalação — bairro",       "escopo": "cliente"},
    "INST_CIDADE":      {"rotulo": "Instalação — cidade",       "escopo": "cliente"},
    "INST_CEP":         {"rotulo": "Instalação — CEP",          "escopo": "cliente"},
    "INST_UF":          {"rotulo": "Instalação — UF",           "escopo": "cliente"},

    # ── loja (CONTRATADA) ────────────────────────────────────────────────────
    "NOME_EMPRESA":      {"rotulo": "Razão social da loja",     "escopo": "loja"},
    "CNPJ_EMPRESA":      {"rotulo": "CNPJ da loja",             "escopo": "loja"},
    "LOJA_LOGRADOURO":   {"rotulo": "Loja — logradouro",        "escopo": "loja"},
    "LOJA_NUMERO":       {"rotulo": "Loja — número",            "escopo": "loja"},
    "LOJA_COMPLEMENTO":  {"rotulo": "Loja — complemento",       "escopo": "loja"},
    "LOJA_BAIRRO":       {"rotulo": "Loja — bairro",            "escopo": "loja"},
    "LOJA_CIDADE":       {"rotulo": "Loja — cidade",            "escopo": "loja"},
    "LOJA_UF":           {"rotulo": "Loja — UF",                "escopo": "loja"},
    "LOJA_CEP":          {"rotulo": "Loja — CEP",               "escopo": "loja"},
    "LOJA_TELEFONE":     {"rotulo": "Loja — telefone",          "escopo": "loja"},
    "LOJA_EMAIL":        {"rotulo": "Loja — e-mail",            "escopo": "loja"},
    "CONSULTOR_NOME":     {"rotulo": "Consultor — nome",        "escopo": "loja"},
    "CONSULTOR_TELEFONE": {"rotulo": "Consultor — telefone",    "escopo": "loja"},
    # Testemunhas: cadastro da loja (lojas.testemunha1_nome/cpf, testemunha2_nome/cpf).
    # Há duas famílias de nome para o MESMO dado, porque _montar_mapping expõe as duas:
    #   - NOME_/CPF_TESTEMUNHA_N: em uso — contrato_template/contrato.md:105-110 depende delas.
    #   - TESTEMUNHA_N_NOME/_DOC e NOME_TESTEMUNHA2: sem consumidor em nenhum template hoje.
    # As segundas seguem catalogadas só porque o mapping as produz (o teste anti-drift exige
    # paridade). Se um dia forem podadas, tirar de _montar_mapping e daqui no mesmo commit.
    "TESTEMUNHA_1_NOME": {"rotulo": "Testemunha 1 — nome (alias de NOME_TESTEMUNHA_1)", "escopo": "loja"},
    "TESTEMUNHA_1_DOC":  {"rotulo": "Testemunha 1 — CPF (alias de CPF_TESTEMUNHA_1)",   "escopo": "loja"},
    "TESTEMUNHA_2_NOME": {"rotulo": "Testemunha 2 — nome (alias de NOME_TESTEMUNHA_2)", "escopo": "loja"},
    "TESTEMUNHA_2_DOC":  {"rotulo": "Testemunha 2 — CPF (alias de CPF_TESTEMUNHA_2)",   "escopo": "loja"},
    "NOME_TESTEMUNHA_1": {"rotulo": "Testemunha 1 — nome",      "escopo": "loja"},
    "CPF_TESTEMUNHA_1":  {"rotulo": "Testemunha 1 — CPF",       "escopo": "loja"},
    "NOME_TESTEMUNHA_2": {"rotulo": "Testemunha 2 — nome",      "escopo": "loja"},
    "CPF_TESTEMUNHA_2":  {"rotulo": "Testemunha 2 — CPF",       "escopo": "loja"},
    "NOME_TESTEMUNHA2":  {"rotulo": "Testemunha 2 — nome (alias de NOME_TESTEMUNHA_2, sem underscore)", "escopo": "loja"},

    # ── pagamento ────────────────────────────────────────────────────────────
    "VALOR_ENTRADA":  {"rotulo": "Valor da entrada",   "escopo": "pagamento"},
    "FORMA_ENTRADA":  {"rotulo": "Forma da entrada",   "escopo": "pagamento"},
    "DATA_ENTRADA":   {"rotulo": "Data da entrada",    "escopo": "pagamento"},
    "MODALIDADE":     {"rotulo": "Modalidade",         "escopo": "pagamento"},
    "NUM_PARCELAS":   {"rotulo": "Nº de parcelas",     "escopo": "pagamento"},
    "TIPO":           {"rotulo": "Tipo da parcela",    "escopo": "pagamento"},
    "TOTAL_CONTRATO": {"rotulo": "Valor total",        "escopo": "pagamento"},

    # ── Termo Aditivo (Fatia 3 da Revisão de PE, 2026-07-21) — COMPLEMENTO contratado ─────────
    # O PE aumentou valores → contrata-se o ADICIONAL dos ambientes marcados (o contrato original
    # permanece intocado; o aditivo documenta só a diferença).
    "NUM_ADITIVO":                {"rotulo": "Nº do termo aditivo",                          "escopo": "documento"},
    "NUM_CONTRATO_ORIGINAL":      {"rotulo": "Nº do contrato original",                      "escopo": "documento"},
    # Modelo jurídico completo (spec 2026-07-22): título ordinal, datas e os 5 blocos dos
    # modais sequenciais (texto editado pelo operador entra no marcador). DATA_CONTRATO_ORIGINAL
    # é NOVO de propósito — DATA_CONTRATO segue sendo "a data do documento corrente".
    "ORDINAL_ADITIVO":            {"rotulo": "Ordinal do aditivo (PRIMEIRO/SEGUNDO…)",       "escopo": "documento"},
    "DATA_ADITIVO":               {"rotulo": "Data do termo aditivo",                        "escopo": "documento"},
    "DATA_CONTRATO_ORIGINAL":     {"rotulo": "Data em que o contrato original foi firmado",  "escopo": "documento"},
    "ADITIVO_CONSIDERANDOS":      {"rotulo": "Considerandos (modal 1)",                      "escopo": "documento"},
    "ADITIVO_LISTA_INTEGRAL":     {"rotulo": "Lista integral de produtos (modal 2)",         "escopo": "documento"},
    "ADITIVO_INCLUSOES":          {"rotulo": "Inclusões — ou declaração negativa (modal 3)", "escopo": "documento"},
    "ADITIVO_EXCLUSOES":          {"rotulo": "Exclusões — ou declaração negativa (modal 4)", "escopo": "documento"},
    "ADITIVO_VALORES":            {"rotulo": "Valores e condições de pagamento (modal 5)",   "escopo": "documento"},
    "AMBIENTES_COMPLEMENTO":      {"rotulo": "Ambientes do complemento (original → novo)",   "escopo": "documento"},
    "VALOR_ORIGINAL_COMPLEMENTO": {"rotulo": "Soma original dos ambientes do complemento",   "escopo": "documento"},
    "VALOR_NOVO_COMPLEMENTO":     {"rotulo": "Soma nova dos ambientes do complemento",       "escopo": "documento"},
    "VALOR_COMPLEMENTO":          {"rotulo": "Valor do complemento (novo − original)",       "escopo": "documento"},

    # ── Aprovação do Projeto Executivo (correção Fatia 3, 2026-07-21) ────────────────────────
    "NUM_APROVACAO_PE":     {"rotulo": "Nº da aprovação do Projeto Executivo",       "escopo": "documento"},
    "AMBIENTES_APROVADOS":  {"rotulo": "Ambientes aprovados no Projeto Executivo",   "escopo": "documento"},

    # ── Termo de Responsabilidade e Solicitação de Medição (achado do usuário 2026-08-17) ────
    "AMBIENTES_MEDICAO":  {"rotulo": "Ambientes a serem medidos",  "escopo": "documento"},
}


# ── Análise do corpo importado (modelos de documento por loja) ─────────────────

import re as _re

# Reusa o regex do motor de substituição — se divergirem, a análise validaria
# um marcador que o renderizador não reconhece (ou o contrário).
from mod_contrato import _MARK_RE

# Sem estes, o documento sai quebrado: cliente sem nome, contrato sem data,
# fecho sem testemunha. O wizard avisa; não bloqueia (pode ser um modelo parcial).
#
# É lista de GRUPOS EQUIVALENTES, não de chaves: o CATALOGO mantém duas famílias
# de nome para o mesmo dado (CPF/CPF_CLIENTE, NOME_TESTEMUNHA_1/TESTEMUNHA_1_NOME)
# justamente para tolerar documentos de lojas com convenção própria. O grupo só é
# "ausente" se NENHUM membro aparecer; um documento que usa [CPF] não pode receber
# aviso de "CPF_CLIENTE ausente" com o dado presente e funcionando — aviso falso
# ensina o lojista a ignorar os avisos, e aí os verdadeiros também passam batido.
# O 1º de cada grupo é o CANÔNICO: é o único reportado em `ausentes` (a tela pede
# uma chave por grupo, não a família inteira).
#
# Os canônicos escolhidos são os que o template vivo usa (contrato_template/
# contrato.md) — é o que faz o aviso ser acionável. Nota: o rótulo do CATALOGO
# chama CPF_CLIENTE de "(alias)" e CPF de principal, mas o template usa
# [CPF_CLIENTE]; a rotulagem lá é que está invertida. Não mexi porque os testes
# anti-drift travam CATALOGO×_montar_mapping e isso é outra frente.
#
# TEXTO_COMPLEMENTAR está aqui por um achado da revisão do Task 2: é o ponto de
# injeção do adendo do ciclo (mod_contrato.py:744). mod_documentos_import só o
# insere se o texto tiver o marco de fecho do modelo ATUAL ("E assim, por estarem
# assim convencionados") — um contrato de outra loja, com redação própria, não
# tem. Sem este aviso, o adendo some do PDF em silêncio.
ESSENCIAIS = [
    ("NOME_CLIENTE",),
    ("CPF_CLIENTE", "CPF"),
    ("DATA_CONTRATO",),
    ("NOME_EMPRESA",),
    ("CNPJ_EMPRESA",),
    ("NOME_TESTEMUNHA_1", "TESTEMUNHA_1_NOME"),
    ("NOME_TESTEMUNHA_2", "TESTEMUNHA_2_NOME", "NOME_TESTEMUNHA2"),
    ("TEXTO_COMPLEMENTAR",),
]

# Campos da loja que valem procurar cravados no texto → marcador correspondente.
#
# A ORDEM É FUNCIONAL, NÃO COSMÉTICA — NÃO REORDENE. Vai do literal mais
# específico/longo (CNPJ, razão social, logradouro) para o mais genérico/curto
# (bairro, cidade, CEP), porque aplicar_cravados faz replace SEQUENCIAL mutando
# o corpo: um literal curto trocado antes destrói a string exata de um literal
# longo que o contém, e o longo passa a ser pulado EM SILÊNCIO.
#
# Contraexemplo: loja com logradouro "Rua São José dos Campos" e cidade
# "São José dos Campos". Com cidade antes, o corpo vira "Rua [LOJA_CIDADE]" e o
# replace seguinte procura "Rua São José dos Campos" — que já não existe.
#
# Para analisar_corpo a ordem é indiferente (busca sobre o corpo imutável; cada
# campo procura seu próprio literal sem interferir nos outros) — ela só afeta a
# ordem de leitura da lista de achados na tela.
# test_ordem_de_cravaveis_esta_travada trava a lista inteira; o comportamental
# (test_aplicar_cravados_respeita_a_ordem_do_mais_especifico) prova o mecanismo.
_CRAVAVEIS = [
    ("cnpj",       "CNPJ_EMPRESA"),
    ("nome",       "NOME_EMPRESA"),
    ("logradouro", "LOJA_LOGRADOURO"),
    ("bairro",     "LOJA_BAIRRO"),
    ("cidade",     "LOJA_CIDADE"),
    ("cep",        "LOJA_CEP"),
]

# Campos cujo literal é essencialmente numérico: o documento pode pontuar
# diferente do cadastro ("19.152.134/0001-56" vs "19152134000156").
_NUMERICOS = ("cnpj", "cep")

# Abaixo disto, o valor casa por acidente (cidade "Sé", bairro "Boa").
_MIN_LITERAL = 4

# Contexto em volta de cada ocorrência, para a tela mostrar ao lojista.
_CTX_CHARS = 40
_MAX_TRECHOS = 3


def _so_digitos(s):
    return _re.sub(r"\D", "", s or "")


def _chaves_usadas(corpo_md):
    return [m.group(1).strip().upper().replace(" ", "_")
            for m in _MARK_RE.finditer(corpo_md or "")]


def _trecho(corpo, ini, fim):
    """Trecho do corpo em volta de [ini:fim), com a ocorrência demarcada.

    É o que permite ao lojista julgar a troca: 'Centro' casando em 'Centro
    Empresarial ABC' só é reconhecível vendo o texto em volta. Word-boundary não
    pegaria — 'Centro' ali É palavra inteira.
    """
    a, b = max(0, ini - _CTX_CHARS), min(len(corpo), fim + _CTX_CHARS)
    return "%s%s>>>%s<<<%s%s" % (
        "…" if a > 0 else "",
        corpo[a:ini].replace("\n", " "),
        corpo[ini:fim],
        corpo[fim:b].replace("\n", " "),
        "…" if b < len(corpo) else "",
    )


def _cravado(corpo, campo, marcador, valor, posicoes, so_digitos=False):
    item = {"marcador": marcador, "literal": valor, "campo": campo,
            "ocorrencias": len(posicoes),
            "trechos": [_trecho(corpo, a, b) for a, b in posicoes[:_MAX_TRECHOS]],
            "trechos_omitidos": max(0, len(posicoes) - _MAX_TRECHOS)}
    if so_digitos:
        item["so_digitos"] = True
    return item


def _posicoes_literal(corpo, valor):
    pos, i = [], corpo.find(valor)
    while i >= 0:
        pos.append((i, i + len(valor)))
        i = corpo.find(valor, i + len(valor))
    return pos


def _posicoes_numerico(corpo, valor):
    """Acha o número no corpo tolerando pontuação diferente da do cadastro.

    Casa dígito a dígito com até 2 não-dígitos de folga entre eles (o bastante
    para ".", "/", "-", ", "). Substitui o teste antigo — `_so_digitos(valor) in
    _so_digitos(corpo)` —, que concatenava os dígitos do documento INTEIRO e
    podia casar uma sequência atravessando dois números não relacionados, sem
    posição nem contexto para o lojista conferir.

    Limitação residual: a folga de 2 chars ainda deixa casar "sala 19, 152134…"
    como se fosse um CNPJ único. Não dá para eliminar por sintaxe — por isso o
    achado vai para a tela COM trecho, para o lojista julgar, e nunca é
    substituído automaticamente (ver aplicar_cravados).
    """
    nus = _so_digitos(valor)
    if len(nus) < _MIN_LITERAL:
        return []
    rx = _re.compile(r"\D{0,2}".join(_re.escape(d) for d in nus))
    return [(m.start(), m.end()) for m in rx.finditer(corpo)]


def analisar_corpo(corpo_md, loja):
    """Analisa um corpo importado contra o catálogo e o cadastro da loja.

    Devolve:
      conhecidos_usados  marcadores do catálogo presentes no corpo
      desconhecidos      [FOO] sem verbete — seria impresso literal no PDF
      ausentes           canônica de cada grupo de ESSENCIAIS sem nenhum membro
                         presente no corpo
      cravados           dados da loja literais no texto, candidatos a marcador;
                         cada item traz `trechos` (contexto em volta, demarcado)
                         + `trechos_omitidos`, e `so_digitos` quando há ocorrência
                         que aplicar_cravados não vai trocar
      bloqueia_ativacao  True se há desconhecido
    """
    loja = loja or {}
    corpo = corpo_md or ""
    usadas = _chaves_usadas(corpo)
    conhecidos = [c for c in dict.fromkeys(usadas) if c in CATALOGO]
    desconhecidos = [c for c in dict.fromkeys(usadas) if c not in CATALOGO]
    ausentes = [grupo[0] for grupo in ESSENCIAIS
                if not any(chave in usadas for chave in grupo)]

    cravados = []
    for campo, marcador in _CRAVAVEIS:
        valor = (loja.get(campo) or "").strip()
        if len(valor) < _MIN_LITERAL:
            continue
        if campo in _NUMERICOS:
            pos = _posicoes_numerico(corpo, valor)
            if pos:
                # so_digitos = há ocorrência cujo texto difere do cadastro, logo
                # aplicar_cravados (replace exato) não a resolve: é caso manual.
                exatos = all(corpo[a:b] == valor for a, b in pos)
                cravados.append(_cravado(corpo, campo, marcador, valor, pos,
                                         so_digitos=not exatos))
            continue
        pos = _posicoes_literal(corpo, valor)
        if pos:
            cravados.append(_cravado(corpo, campo, marcador, valor, pos))
    return {"conhecidos_usados": conhecidos, "desconhecidos": desconhecidos,
            "ausentes": ausentes, "cravados": cravados,
            "bloqueia_ativacao": bool(desconhecidos)}


def aplicar_cravados(corpo_md, loja, marcadores_aprovados):
    """Troca pelo marcador só os literais que o lojista aprovou.

    Só troca correspondência EXATA de string (str.replace). Achado marcado
    `so_digitos` tem ao menos uma ocorrência escrita com pontuação diferente da
    do cadastro: essa não tem string exata para casar e SOBREVIVE à troca — a
    tela mostra o trecho e o lojista corrige à mão. Num achado misto as exatas
    são trocadas e as demais ficam (por isso o aviso importa: o documento sai
    meio parametrizado, meio cravado).

    Não reuso o regex flexível de _posicoes_numerico para substituir: ele tolera
    folga entre os dígitos e poderia casar outro número do texto. Detectar com
    ele é seguro (o achado vai à tela com trecho, e o lojista julga);
    substituir cegamente, num contrato assinado, não.
    """
    loja = loja or {}
    aprovados = set(marcadores_aprovados or [])
    out = corpo_md or ""
    for campo, marcador in _CRAVAVEIS:
        if marcador not in aprovados:
            continue
        valor = (loja.get(campo) or "").strip()
        if len(valor) < _MIN_LITERAL:
            continue
        out = out.replace(valor, "[%s]" % marcador)
    return out
