"""mod_fiscal.py — lógica fiscal pura (emitente-padrão de teste, validação, guarda de produção)
e a fiação com o emissor (focus_client_para_emitente). Config real vem do Emitente (banco)."""

REGIMES = {"simples", "simples_excesso", "normal", "mei"}
PAPEIS = {"central_produto", "loja_servico", "loja_produto_servico", "avulso"}
AMBIENTES = {"homologacao", "producao"}

_CNAE_PLACEHOLDER = "4330404"   # instalação/montagem de móveis (genérico — NÃO confirmado)
_CAMPOS_PADRAO = ["regime_tributario", "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf",
                  "cnae_servico", "aliquota_iss", "papel_cnpj"]


def emitente_padrao_teste():
    """Valores de teste p/ desbloquear a config do Emitente (Simples, CFOP 5102/6102,
    CNAE placeholder, ISS 5%)."""
    return {
        "razao_social": None, "inscricao_estadual": None, "inscricao_municipal": None,
        "regime_tributario": "simples", "csosn_padrao": "102", "csosn_contribuinte": "101",
        "cfop_dentro_uf": "5102", "cfop_fora_uf": "6102",
        "serie_nfe": None, "discrimina_impostos": 1, "cnae_servico": _CNAE_PLACEHOLDER,
        "cod_servico_municipio": None, "aliquota_iss": 5.0, "retencao_json": None,
        "municipio_ibge": None, "papel_cnpj": "loja_produto_servico",
        "placeholders": list(_CAMPOS_PADRAO),
    }


def validar_config(req):
    """(ok, erro) para os campos não-secretos do PUT de config."""
    cnpj = req.get("cnpj")
    if cnpj:
        from validacao_doc import valida_cnpj
        if not valida_cnpj(cnpj):
            return (False, "CNPJ do emitente inválido")
    reg = req.get("regime_tributario")
    if reg is not None and reg not in REGIMES:
        return (False, "regime_tributario inválido")
    papel = req.get("papel_cnpj")
    if papel is not None and papel not in PAPEIS:
        return (False, "papel_cnpj inválido")
    iss = req.get("aliquota_iss")
    if iss is not None:
        try:
            v = float(iss)
        except (TypeError, ValueError):
            return (False, "aliquota_iss inválida")
        if not (0 <= v <= 100):
            return (False, "aliquota_iss fora da faixa (0-100)")
    return (True, "")


def pode_ativar_producao(placeholders):
    """False se restar qualquer placeholder — bloqueia produção com dado de teste."""
    return not placeholders


def _vazio(v):
    return not (str(v).strip() if v is not None else "")


# Bloco fiscal item 4 (docs/db/TAREFA_BLOCO_FISCAL.md) — DECIDIDO do Marcelo: BARRAR. O ramo
# produto conferia só regime+UF; endereço do emitente inteiro passava e o destinatário não era
# conferido em lugar nenhum (a falta que custou o percurso de 01/09, erro de schema cMun/xLgr).
_CAMPOS_EMITENTE_IDENTIFICACAO = [
    ("cnpj", "CNPJ"), ("inscricao_estadual", "Inscrição Estadual"),
    ("regime_tributario", "regime tributário"), ("csosn_padrao", "CSOSN padrão"),
    ("csosn_contribuinte", "CSOSN contribuinte"), ("cfop_dentro_uf", "CFOP dentro da UF"),
    ("cfop_fora_uf", "CFOP fora da UF"), ("municipio_ibge", "código IBGE do município"),
    ("uf", "UF"),
]
_CAMPOS_EMITENTE_ENDERECO = [
    ("logradouro", "logradouro"), ("numero", "número"), ("bairro", "bairro"),
    ("cidade", "cidade"), ("uf", "UF"), ("cep", "CEP"),
]
_CAMPOS_DESTINATARIO_ENDERECO = [
    ("logradouro", "logradouro"), ("numero", "número"), ("bairro", "bairro"),
    ("cidade", "cidade"), ("estado", "estado"), ("cep", "CEP"),
]


def prontidao_emitente(emitente, tipo_doc):
    """Mensagem de erro se o Emitente NÃO está pronto para emitir `tipo_doc` ('produto'|'servico'),
    ou None se estiver pronto. Barra ANTES de chamar a Focus o que hoje geraria (a) nota autorizada
    porém ERRADA em silêncio — regime ≠ Simples usa PIS/COFINS/CSOSN do Simples; UF do emitente vazia
    cai em CFOP interestadual — ou (b) recusa com erro genérico por dado fiscal faltante.
    Descoberto na auditoria fiscal 2026-07-07 (achados A2/A3/A5)."""
    regime = (getattr(emitente, "regime_tributario", None) or "").strip().lower()
    if tipo_doc == "produto":
        # Gate duro, não afrouxado pelo item 4: sem Simples Nacional, nem chega a valer a pena
        # nomear os outros campos — e é por causa dele que CSOSN abaixo é sempre exigível (não
        # condicional ao regime).
        if regime != "simples":
            return ("Emissão de NF-e de produto hoje só é suportada para o Simples Nacional "
                    "(regime do emitente: %s). Ajuste o regime do emitente no painel Fiscal."
                    % (regime or "não informado"))
        faltando_id = [rotulo for campo, rotulo in _CAMPOS_EMITENTE_IDENTIFICACAO
                       if _vazio(getattr(emitente, campo, None))]
        ambiente = (getattr(emitente, "ambiente_ativo", None) or "homologacao")
        token_campo = "focus_token_homolog_enc" if ambiente == "homologacao" else "focus_token_prod_enc"
        if _vazio(getattr(emitente, token_campo, None)):
            faltando_id.append("token da Focus (ambiente %s)" % ambiente)
        faltando_end = [rotulo for campo, rotulo in _CAMPOS_EMITENTE_ENDERECO
                        if _vazio(getattr(emitente, campo, None))]
        if not faltando_id and not faltando_end:
            return None
        partes = []
        if faltando_id:  partes.append("identificação (" + ", ".join(faltando_id) + ")")
        if faltando_end: partes.append("endereço (" + ", ".join(faltando_end) + ")")
        return "Configure no painel Fiscal antes de emitir a NF-e — " + "; ".join(partes) + "."
    if tipo_doc == "servico":
        faltando = []
        if _vazio(getattr(emitente, "inscricao_municipal", None)):   faltando.append("Inscrição Municipal")
        if _vazio(getattr(emitente, "municipio_ibge", None)):        faltando.append("código IBGE do município")
        if _vazio(getattr(emitente, "cod_servico_municipio", None)): faltando.append("código de serviço do município")
        if getattr(emitente, "aliquota_iss", None) in (None, ""):    faltando.append("alíquota de ISS")
        if faltando:
            return "Configure no painel Fiscal antes de emitir a NFS-e: " + ", ".join(faltando) + "."
        return None
    return None


def prontidao_destinatario(cliente):
    """Mensagem de erro se o Cliente (destinatário da nota) NÃO tem endereço completo, ou None se
    estiver pronto. Função IRMÃ de `prontidao_emitente`, não a mesma — a assinatura é do emitente,
    e misturar o Cliente ali quebraria a fronteira do módulo (o chamador resolve os dois e compõe).
    `Cliente` não tem coluna `uf` — usa `estado`; `inst_uf` é do endereço de instalação, que a nota
    não usa."""
    faltando = [rotulo for campo, rotulo in _CAMPOS_DESTINATARIO_ENDERECO
                if _vazio(getattr(cliente, campo, None))]
    if faltando:
        return "Configure o endereço do cliente (destinatário da nota): " + ", ".join(faltando) + "."
    return None


def resolver_emitente(db, loja, tipo_doc):
    """Resolve qual Emitente assina `tipo_doc` para `loja`.
    Precedência: override da loja (PerfilEmissao owner="loja") → default da rede
    (owner="rede") → self (loja.emitente_id). ValueError se nada resolver."""
    from database import Emitente, PerfilEmissao

    def _busca(owner_tipo, owner_id):
        if owner_id is None:
            return None
        pe = (db.query(PerfilEmissao)
                .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo_doc=tipo_doc)
                .order_by(PerfilEmissao.id.desc())   # defensivo: a mais recente vence (A12)
                .first())
        return pe.emitente_id if pe else None

    emitente_id = _busca("loja", loja.id)
    if emitente_id is None and getattr(loja, "loja_mae_id", None):
        # PDV (loja com mãe, spec 2026-07-22): sem resolução própria, emite pela MÃE —
        # cadeia completa dela (override da mãe → default da rede → emitente próprio da mãe).
        from database import Loja
        mae = db.get(Loja, loja.loja_mae_id)
        if mae is not None:
            return resolver_emitente(db, mae, tipo_doc)
    if emitente_id is None:
        emitente_id = _busca("rede", loja.rede_id)
    if emitente_id is None:
        emitente_id = loja.emitente_id
    if emitente_id is None:
        raise ValueError(
            "Loja %s sem emitente para tipo_doc=%s (sem override, sem default de rede, "
            "sem emitente próprio)" % (loja.id, tipo_doc))
    emitente = db.get(Emitente, emitente_id)
    if emitente is None:
        raise ValueError("Emitente %s (resolvido p/ loja %s, tipo_doc=%s) não existe"
                         % (emitente_id, loja.id, tipo_doc))
    return emitente


def resolver_plano(db, projeto, tem_produto=True, tem_servico=False):
    """Plano de faturamento do projeto: lista de {tipo_doc, emitente} conforme o que
    o projeto tem (produto/serviço). Resolve o emitente de cada tipo via resolver_emitente."""
    from database import Loja
    loja = db.get(Loja, projeto.loja_id)
    if loja is None:
        raise ValueError("Projeto %s sem loja (loja_id=%s)"
                         % (getattr(projeto, "nome_safe", projeto), projeto.loja_id))
    plano = []
    if tem_produto:
        plano.append({"tipo_doc": "produto", "emitente": resolver_emitente(db, loja, "produto")})
    if tem_servico:
        plano.append({"tipo_doc": "servico", "emitente": resolver_emitente(db, loja, "servico")})
    return plano


def focus_client_para_emitente(db, emitente_id):
    """Monta um FocusClient a partir do Emitente: token do ambiente_ativo, decriptado,
    e base_url do ambiente. ValueError se não há emitente ou token para o ambiente."""
    from . import fiscal_cripto
    from integracoes import focus_config
    from integracoes.focus_client import FocusClient
    from database import Emitente
    em = db.get(Emitente, emitente_id)
    if not em:
        raise ValueError("Emitente %s inexistente" % (emitente_id,))
    amb = em.ambiente_ativo or "homologacao"
    enc = em.focus_token_homolog_enc if amb == "homologacao" else em.focus_token_prod_enc
    if not enc:
        raise ValueError("Emitente %s sem token Focus para o ambiente %s" % (emitente_id, amb))
    return FocusClient(token=fiscal_cripto.decrypt(enc), base_url=focus_config.base_url_de(amb))
