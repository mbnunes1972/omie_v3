"""clicksign_config.py — resolve a base URL da ClickSign por ambiente (sandbox/produção).
Mesmo papel de d4sign_config.py/focus_config.py: a config real é 100% por loja/rede no banco
(IntegracaoClickSign), sem fallback de arquivo local."""

_BASES = {
    "sandbox":  "https://sandbox.clicksign.com/api/v3",
    "producao": "https://app.clicksign.com/api/v3",
}


def base_url_de(ambiente: str) -> str:
    try:
        return _BASES[ambiente]
    except KeyError:
        raise ValueError("ambiente inválido: %r (use 'sandbox' ou 'producao')" % (ambiente,))
