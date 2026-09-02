# -*- coding: utf-8 -*-
"""docs/db/TAREFA_PERCURSO_0209.md, C3 — "Duas portas para o mesmo destino" (ROTEIRO.md, regra de
02/09), aplicada ao próprio caso que a originou: "Aprovação Financeira" e "Solicitação de
Medição" apareciam DENTRO do bloco do Contrato (achado do usuário 2026-08-17,
`_renderBotoesPosAssinaturaContrato`) E como sub-aba do fichário (N3, 2026-08-26,
`_FICHA_MAE_EXPLICITA`) — duas portas pro mesmo destino.

Medição antes do conserto (pedida pelo Marcelo): "Solicitação de Medição" tinha DUAS
implementações reais, não só duas portas de UI — a sub-aba "9" renderizava um upload simples de
arquivo (`_renderCardSolicitacaoMedicao`/`enviarSolicitacaoMedicao`, POST .../medicao/solicitacao
sem corpo de documento) enquanto o botão dentro do Contrato abria o fluxo de documento
gerado+assinado (`_renderSecaoSolicitacaoMedicao`, .../medicao/solicitacao/gerar+assinar). Grep
em tests/ (antes deste conserto): ZERO testes cobrindo o upload simples; 12 testes cobrindo
gerar+assinar+clicksign (tests/test_solicitacao_medicao_e2e.py) — e o próprio
`_registrar_assinatura_solicitacao_medicao` já documentava a superação. Upload simples = porta
morta.

Decisão do Marcelo: as duas etapas ficam só como sub-aba do fichário, ao lado da Visão Geral. O
conserto: (1) apagar os botões duplicados de dentro do bloco do Contrato; (2) mover o fluxo que
sobrevive (documento gerado+assinado) pra dentro da própria sub-aba "9", carregado por
`_fichaEfeitos` na seleção — mesmo padrão já usado por `carregarDadosContrato()` pra "7"; (3)
apagar o upload simples (frontend E o endpoint morto em main.py)."""
import os
import re

REPO = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO, "static", "index.html")
MAIN_PY = os.path.join(REPO, "main.py")


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def test_botoes_duplicados_desapareceram_do_bloco_do_contrato():
    html = _ler(INDEX_HTML)
    for morto in ("_renderBotoesPosAssinaturaContrato", "_toggleSolicitacaoMedicaoInline"):
        assert morto not in html, "porta duplicada dentro do Contrato ainda existe: %s" % morto


def test_upload_simples_de_solicitacao_de_medicao_foi_removido():
    html = _ler(INDEX_HTML)
    for morto in ("enviarSolicitacaoMedicao()", "med-solic-file"):
        assert morto not in html, "upload simples (porta morta) ainda referenciado: %s" % morto
    # o endpoint que ele chamava (upload sem documento) também precisa estar fora do backend —
    # a linha era única a este handler (destino do arquivo bruto, sem PDF gerado).
    main = _ler(MAIN_PY)
    assert 'os.path.join(_projeto_path(nome_safe), "medicao", "solicitacao_"' not in main, (
        "handler do upload simples (porta morta) ainda presente em main.py")


def test_ficha_9_carrega_o_fluxo_sobrevivente_ao_selecionar_a_aba():
    html = _ler(INDEX_HTML)
    m = re.search(r"function _fichaEfeitos\(codigo\)\s*\{(.*?)\n\}", html, re.S)
    assert m, "_fichaEfeitos não encontrada"
    corpo = m.group(1)
    assert "carregarSolicitacaoMedicao()" in corpo, (
        "seleção da ficha '9' precisa carregar o fluxo de documento+assinatura, "
        "mesmo padrão de carregarDadosContrato() pra '7'")

    m2 = re.search(r"function _renderCardSolicitacaoMedicao\(dados, bloqueada\)\s*\{(.*?)\n\}",
                   html, re.S)
    assert m2, "_renderCardSolicitacaoMedicao não encontrada"
    assert "med-solic-inline" in m2.group(1), (
        "a sub-aba '9' precisa hospedar o container do fluxo sobrevivente")
