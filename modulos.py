"""modulos.py — manifesto declarativo dos módulos (ARQUITETURA-MODULOS.md tornado executável).
Puro (sem dependências do app). Fonte da verdade de: qual arquivo/tabela/rota pertence a qual módulo,
a camada (nucleo|dominio), as dependências permitidas e se o módulo é desligável por loja (topologia)."""

# camada: "nucleo" (transversal, sempre ligado) | "dominio" (ligável/desligável por cliente)
# depende_de: módulos que ESTE pode importar além do próprio núcleo (ratchet do teste de fronteira)
# arquivos/tabelas/rotas: prefixos que identificam o dono. rotas = prefixos de path (match por startswith).
MODULOS = {
    # ── NÚCLEO / PLATAFORMA ────────────────────────────────────────────────
    "auth":        {"camada": "nucleo", "depende_de": [],
                    # PACOTE (reorganização 2026-07-15) — ver o comentário em "fiscal".
                    "arquivos": ["auth"],
                    "tabelas": ["usuarios", "sessoes", "perfil_acesso"], "rotas": []},
    "tenancy":     {"camada": "nucleo", "depende_de": ["auth"],
                    "arquivos": ["mod_tenancy.py"],
                    "tabelas": ["redes", "lojas", "usuario_lojas", "parceiro_lojas"], "rotas": []},
    "escopo":      {"camada": "nucleo", "depende_de": ["auth"],
                    "arquivos": ["mod_escopo.py"],
                    "tabelas": ["atribuicoes_ambiente"], "rotas": []},
    "auditoria":   {"camada": "nucleo", "depende_de": [],
                    "arquivos": [],
                    "tabelas": ["log_autorizacoes", "log_acoes_gerenciais", "log_acesso_delegado"], "rotas": []},
    "ciclo":       {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["mod_ciclo.py", "mod_cronograma.py", "mod_calendario.py"],
                    "tabelas": ["ciclo_etapas", "ciclo_documentos", "ciclo_revisoes"], "rotas": []},
    "integracoes": {"camada": "nucleo", "depende_de": [],
                    # PACOTE (reorganização 2026-07-15) — ver o comentário em "fiscal".
                    "arquivos": ["integracoes"],
                    "tabelas": [], "rotas": []},
    "plataforma":  {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["database.py", "storage.py"],
                    "tabelas": [], "rotas": []},
    "chat":        {"camada": "nucleo", "depende_de": [],
                    # Chat do Orizon, Fatia 1 (spec _geral/2026-07-25): comunicação transversal
                    # entre etapas/equipes — núcleo por ora (sempre ligado); se um dia virar
                    # desligável por loja, promove a domínio.
                    # PACOTE desde 2026-07-31 (spec módulo destacável): o código vive em chat/
                    # (core/externo/triagem/ports); mod_chat.py e mod_chat_externo.py na raiz são
                    # SHIMS de compatibilidade que fazem o bootstrap das portas (chat_host.py =
                    # adaptadores do host; direção permitida host→chat, nunca o contrário —
                    # ratchet test_chat_pacote_nao_importa_host).
                    "arquivos": ["chat", "mod_chat.py", "mod_chat_externo.py", "chat_host.py"],
                    "tabelas": ["conversas", "conversa_mensagens",
                                "conversa_participantes", # Central de Comunicação (Fatia 1, 2026-07-27)
                                "conversa_participantes_externos", # Orizon Chat externo (2026-07-28)
                                "template_mensagem",      # Orizon Chat/Meta templates (RF-07, 2026-07-28)
                                "triagem_config",         # Orizon Chat/Meta triagem (RF-08, 2026-07-28)
                                "segmento_config",        # Orizon Chat/Meta segmentos (RF-02, 2026-07-28)
                                "numero_conectado",       # Orizon Chat/Meta número por loja (RF-01, 2026-07-28)
                                "assuntos",               # Orizon Chat (Fatia 2, 2026-07-27)
                                "mensagem_anexos",        # Orizon Chat anexos (Fatia 5, 2026-07-27)
                                "usuario_presenca",       # Orizon Chat ponte WhatsApp (Fatia 6, 2026-07-27)
                                "contato_confirmacoes",   # decisão 13 (mini-frente 2026-07-25)
                                "envios_externos",        # canais externos (Fatias 6-7, 2026-07-26)
                                "triagem_entradas"],      # fila de triagem humana (spec 2026-07-31)
                    "rotas": []},
    # ── DOMÍNIOS ───────────────────────────────────────────────────────────
    "captacao":    {"camada": "dominio", "depende_de": [], "rotulo": "Captação", "faixa": "vendas",
                    "arquivos": [], "tabelas": [], "rotas": []},
    "cadastro":    {"camada": "dominio", "depende_de": [], "rotulo": "Cadastro", "faixa": "vendas",
                    "arquivos": ["validacao_doc.py", "mod_cadastro.py"],
                    "tabelas": ["clientes", "parceiros", "funcionarios", "fornecedores", "terceiros", "funcoes"],
                    "rotas": ["/api/clientes", "/api/parceiros", "/api/funcionarios",
                              "/api/fornecedores", "/api/terceiros", "/api/funcoes"]},
    "comercial":   {"camada": "dominio", "depende_de": ["cadastro"], "rotulo": "Comercial", "faixa": "vendas",
                    "arquivos": ["mod_orcamento_params.py", "mod_margens.py", "mod_negociacao.py",
                                 "mod_contrato.py", "mod_marcadores.py",
                                 "mod_documentos_import.py", "mod_documentos.py", "mod_arvore.py",
                                 "_ler_aymore.py", "mod_fin",
                                 "mod_pe_comparacao.py", "mod_parcelas.py", "mod_retido.py",
                                 # Medição (etapas 9/10 do ciclo): o antigo módulo 'producao' (rótulo UI
                                 # "Projetos") foi retirado da navegação por ser tela-vazia e duplicar o
                                 # nome; seu código é dono aqui, pois Medição pertence ao ciclo comercial.
                                 "mod_medicao.py", "mod_qualidade_xml.py",
                                 "mod_comercial_dash.py",   # dashboard Comercial (view derivada)
                                 "mod_equipe.py"],           # Equipe do Projeto (roster papel→responsável)
                    "tabelas": ["projetos_meta", "briefings", "pool_ambientes", "orcamentos",
                                "orcamento_ambientes", "contratos", "contratos_assinaturas",
                                "aditivos", "aditivos_assinaturas",   # Termo Aditivo (Fatia 3 PE)
                                "aprovacoes_pe", "aprovacoes_pe_assinaturas",   # Aprovação do PE (Fatia 3)
                                "arquivo_pe", "parcela_projeto", "parcela_ambiente",
                                "sinal_retido", "retencao_obra", "medicoes",
                                "documento_modelos",
                                "documento_tipos"],   # tipos customizados ("Novo Documento", 2026-07-22)
                    "rotas": ["/api/orcamentos", "/api/contratos", "/api/medicoes", "/api/comercial",
                              "/api/documentos"]},
    "fiscal":      {"camada": "dominio", "depende_de": ["cadastro", "comercial"], "rotulo": "Fiscal", "faixa": "expedicao",
                    # PACOTE (piloto da reorganização, 2026-07-15) — mesmo padrão do mod_fin:
                    # entra pelo nome do diretório. O ratchet de arquitetura EXPANDE o dir
                    # nos .py de dentro (tests/test_arquitetura_modulos._arquivos_do_modulo),
                    # então empacotar não tira o módulo da verificação.
                    "arquivos": ["fiscal"],
                    "tabelas": ["emitente", "perfil_emissao", "documento_fiscal"],
                    "rotas": ["/api/projetos/", "/api/admin/lojas/", "/api/admin/redes/"]},
    "financeiro":  {"camada": "dominio", "depende_de": ["comercial"], "rotulo": "Financeiro", "faixa": "financeiro",
                    "arquivos": ["mod_provisoes.py", "mod_contabil.py", "mod_ajustes_fabrica.py",
                                 "mod_indicadores.py"],
                    "tabelas": ["provisao_registro", "conta", "lancamento", "periodo_contabil",
                                "acordo_fabrica", "ajuste_fabrica", "ajuste_fabrica_aplicacao",
                                "acordo_movimento", "contraparte_financeira"],
                    "rotas": ["/api/provisoes", "/api/financeiro/contas", "/api/financeiro/lancamentos",
                              "/api/financeiro/eventos", "/api/financeiro/dre", "/api/financeiro/projetos-dre",
                              "/api/financeiro/reconciliar", "/api/financeiro/periodos", "/api/financeiro/balanco",
                              "/api/financeiro/repasse-fabrica", "/api/financeiro/sugerir-conta",
                              "/api/financeiro/provisoes-venda", "/api/financeiro/dashboard",
                              "/api/admin/acordos-fabrica", "/api/admin/ajustes-fabrica",
                              "/api/financeiro/indicadores"]},
    # domínios NOVOS — fronteira só (stub, sem código/tabela hoje). Montagem e Assistências substituem
    # o antigo "posvenda" (que virou FAIXA, não módulo — Modulos_Orizon_v4).
    "estoque":     {"camada": "dominio", "depende_de": ["cadastro", "comercial"], "rotulo": "Estoque", "faixa": "expedicao",
                    "arquivos": [], "tabelas": [], "rotas": []},
    "expedicao":   {"camada": "dominio", "depende_de": ["comercial", "estoque", "fiscal"], "rotulo": "Expedição", "faixa": "expedicao",
                    "arquivos": ["mod_expedicao.py"],
                    "tabelas": ["ciclo_logistico", "ciclo_logistico_transicao"],
                    "rotas": ["/api/expedicao"]},
    "montagem":    {"camada": "dominio", "depende_de": ["comercial"], "rotulo": "Montagem", "faixa": "montagem",
                    "arquivos": [], "tabelas": [], "rotas": []},
    "folha":       {"camada": "dominio", "depende_de": ["cadastro", "comercial", "financeiro"], "rotulo": "Folha de Pagamento", "faixa": "financeiro",
                    "arquivos": ["mod_folha.py", "mod_comissao.py", "mod_adiantamento.py"],
                    "tabelas": ["folha_pagamento", "comissao_folha", "adiantamento_funcionario"],
                    "rotas": ["/api/folha", "/api/comissao", "/api/adiantamentos"]},
    "assistencias":{"camada": "dominio", "depende_de": ["comercial", "montagem", "financeiro"], "rotulo": "Assistências", "faixa": "montagem",
                    "arquivos": ["mod_assistencias.py"],
                    "tabelas": ["assistencia_caso"],
                    "rotas": ["/api/assistencias"]},
}

# Arquivos que NÃO são módulo (shell/compositor e utilitários). O teste de cobertura os ignora.
SHELL = {"main.py", "seed.py", "modulos.py"}

# mod_nfe é COMPARTILHADO (parser=produção, pricing=fiscal): lotado em 'fiscal' no manifesto, mas
# 'comercial' (dono da medição/qualidade de XML) também pode importá-lo.
COMPARTILHADOS = {"mod_nfe.py": ["fiscal", "comercial"]}

NUCLEO = frozenset(n for n, v in MODULOS.items() if v["camada"] == "nucleo")
DOMINIOS = frozenset(n for n, v in MODULOS.items() if v["camada"] == "dominio")


def desligavel(modulo):
    """True se o módulo pode ser desligado por loja (só domínios)."""
    return MODULOS.get(modulo, {}).get("camada") == "dominio"


def modulo_de_arquivo(arquivo):
    """Nome do módulo dono do arquivo (.py ou pacote), ou None se for shell/desconhecido.

    Aceita caminho DENTRO de pacote — 'fiscal/mod_nfe.py' → 'fiscal' —, porque o
    manifesto registra o pacote pelo diretório. Sem isso, todo arquivo empacotado
    ficava órfão: era o caso de `mod_fin/aymore.py` (→ None) desde que o mod_fin
    virou pacote, e passaria a ser o do fiscal/ na reorganização de 2026-07-15.
    """
    arquivo = arquivo.replace("\\", "/")
    base = arquivo[:-3] if arquivo.endswith(".py") else arquivo
    raiz_pacote = arquivo.split("/")[0] if "/" in arquivo else None
    for nome, v in MODULOS.items():
        for a in v["arquivos"]:
            if a == arquivo or a == base or (raiz_pacote and a == raiz_pacote):
                return nome
    return None


def modulo_de_tabela(tabela):
    for nome, v in MODULOS.items():
        if tabela in v["tabelas"]:
            return nome
    return None


def modulo_do_path(path):
    """Módulo DESLIGÁVEL dono da rota (por prefixo), ou None. Só retorna domínios — rotas de núcleo
    (login, admin de tenancy) nunca são desligáveis. Prefixos mais específicos vencem (ordem por tamanho)."""
    candidatos = []
    for nome, v in MODULOS.items():
        if v["camada"] != "dominio":
            continue
        for pref in v["rotas"]:
            if path.startswith(pref):
                candidatos.append((len(pref), nome))
    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    return candidatos[0][1]


# Ordem estável dos domínios para a UI (DOMINIOS é frozenset, sem ordem). Sidebar plana usa esta ordem
# (achatada por faixa no hub_layout). Captação primeiro (entrada do funil); Montagem/Assistências ao fim.
DOMINIOS_ORDEM = ["captacao", "cadastro", "comercial", "fiscal",
                  "estoque", "expedicao", "montagem", "assistencias", "financeiro", "folha"]


def dominios_com_rotulo():
    """Lista ordenada dos domínios: [{'id','rotulo','depende_de'}]. Para o painel de módulos."""
    return [{"id": d, "rotulo": MODULOS[d].get("rotulo", d),
             "depende_de": list(MODULOS[d]["depende_de"])} for d in DOMINIOS_ORDEM]


def topologia_valida(ativos):
    """(True, "") se o conjunto `ativos` é coerente: todo módulo ativo tem seus depende_de (que são
    domínios) também ativos — senão (False, msg). Núcleo é sempre ativo (ignorado)."""
    ativos = set(ativos)
    for mod in ativos:
        for dep in MODULOS.get(mod, {}).get("depende_de", []):
            if dep in DOMINIOS and dep not in ativos:
                return (False, "Módulo '%s' depende de '%s', que precisa estar ativo." % (mod, dep))
    return (True, "")


# Faixas de titularidade para o hub de módulos (ordem de exibição). As 4 primeiras espelham
# mod_ciclo.FAIXA_POR_ETAPA (Governança do Ciclo); "financeiro" é transversal (dono dos gates 8/11d).
FAIXAS = [
    ("vendas",           "Vendas"),
    ("execucao_projeto", "Execução do Projeto"),
    ("expedicao",        "Logística / Expedição"),
    ("montagem",         "Pós-venda / Montagem"),
    ("financeiro",       "Financeiro"),
]


def hub_layout(ativos):
    """Layout do hub: domínios ATIVOS agrupados por faixa, na ordem de FAIXAS/DOMINIOS_ORDEM.
    Só inclui faixas com ≥1 domínio ativo. [{'faixa','rotulo','modulos':[{'id','rotulo'}]}]."""
    ativos = set(ativos)
    grupos = []
    for fid, frot in FAIXAS:
        mods = [{"id": d, "rotulo": MODULOS[d]["rotulo"]}
                for d in DOMINIOS_ORDEM
                if d in ativos and MODULOS[d].get("faixa") == fid]
        if mods:
            grupos.append({"faixa": fid, "rotulo": frot, "modulos": mods})
    return grupos
