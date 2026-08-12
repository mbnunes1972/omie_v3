"""mod_clicksign.py — wiring da integração ClickSign: resolve credencial por loja/rede e monta
o cliente HTTP configurado. Espelha fiscal/mod_fiscal.py (resolver_emitente/
focus_client_para_emitente), mas mais simples — IntegracaoClickSign é 1 linha por loja OU por
rede (sem tabela de override tipo PerfilEmissao), já que aqui não existe "tipo de documento" a
distinguir na credencial. Diferente da D4Sign: não existe "cofre" pra resolver junto — cada envio
cria seu próprio envelope, então `client_de` devolve só o cliente."""

AMBIENTES = {"sandbox", "producao"}


def resolver_config(db, loja):
    """Config ClickSign pra `loja`: override da própria loja -> default da rede -> None
    (nenhum configurado = dormente, fluxo interno de assinatura continua como está)."""
    from database import IntegracaoClickSign
    cfg = db.query(IntegracaoClickSign).filter_by(loja_id=loja.id).first()
    if cfg is None and getattr(loja, "rede_id", None):
        cfg = (db.query(IntegracaoClickSign)
                 .filter_by(rede_id=loja.rede_id, loja_id=None).first())
    return cfg


def client_de(cfg):
    """Monta um ClickSignClient a partir da IntegracaoClickSign: access_token do ambiente_ativo,
    decriptado. ValueError se faltar token pro ambiente ativo."""
    from integracoes import cripto_segredos, clicksign_config
    from integracoes.clicksign_client import ClickSignClient
    amb = cfg.ambiente_ativo or "sandbox"
    token_enc = cfg.token_sandbox_enc if amb == "sandbox" else cfg.token_producao_enc
    if not token_enc:
        raise ValueError("Integração ClickSign (id=%s) sem access_token para o ambiente %s"
                         % (cfg.id, amb))
    return ClickSignClient(access_token=cripto_segredos.decrypt(token_enc),
                           base_url=clicksign_config.base_url_de(amb))
