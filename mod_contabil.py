"""mod_contabil.py — motor contábil (domínio financeiro). Sub-projeto #1: Plano de Contas.
Fonte de verdade: Especificacao_Financeiro_Orizon_v2.docx §2/§2.1."""
import logging

from database import (get_session, Conta, CentroCusto, Loja, Rede, Lancamento, PeriodoContabil,
                      VeredictoProvisao)

_LOG = logging.getLogger(__name__)

# Plano-padrão (codigo, nome) — pai = prefixo; tipo/natureza derivados. Ordem = ordem contábil.
PLANO_PADRAO = [
    ("1", "ATIVO"),
    ("1.1", "Circulante"),
    ("1.1.01", "Caixa/Bancos"), ("1.1.02", "Contas a Receber (Clientes)"),
    ("1.1.03", "Estoques"), ("1.1.04", "Adiantamentos a Fornecedores"),
    ("1.1.05", "Impostos a Apropriar"),   # FASE B2.6: ativo diferido — imposto reservado no contrato,
                                          # baixado na emissão (dedução só ocorre no faturamento)
    # FASE D2: "Custos a Apropriar" — ativo diferido espelho de 1.1.05, generalizado às 10 rubricas.
    # No contrato: DR 1.1.06.0X × CR 2.1.04.0X (constitui a provisão sem tocar a DRE). Na NF-e: a despesa
    # (5.6.0X ou 5.1.01 p/ fábrica) debita contra a baixa deste ativo (matching pleno). Sobrevive só até a NF-e.
    ("1.1.06", "Custos a Apropriar"),
    ("1.1.06.02", "Montagem a Apropriar"), ("1.1.06.03", "Garantia a Apropriar"),
    ("1.1.06.05", "Assistência Técnica a Apropriar"), ("1.1.06.06", "Custo de Fábrica a Apropriar"),
    ("1.1.06.07", "Frete de Fábrica a Apropriar"), ("1.1.06.08", "Frete Local a Apropriar"),
    ("1.1.06.09", "Insumos Locais a Apropriar"), ("1.1.06.10", "Comissão de Medidor a Apropriar"),
    ("1.1.06.11", "Comissão de Projeto/Executivo a Apropriar"),
    ("1.1.06.12", "Retenção de Comissão de Vendas a Apropriar"),
    ("1.1.06.14", "Outros Fornecedores a Apropriar"),
    # FASE A (resultado da venda): custos adicionais como ativo diferido (espelho das demais rubricas)
    ("1.1.06.15", "Comissão de Arquiteto a Apropriar"), ("1.1.06.16", "Programa de Fidelidade a Apropriar"),
    ("1.1.06.17", "Custo de Viagem a Apropriar"), ("1.1.06.18", "Brinde a Apropriar"),
    ("1.1.06.19", "Custo Financeiro a Apropriar"),   # FASE B: ramo FINANCEIRA (Aymoré/Cartão) — despesa financeira diferida
    ("1.1.06.20", "Custo Especial a Apropriar"),   # Custo Especial (5º custo adicional — não rateado nos ambientes)
    ("1.1.06.21", "Comissão Administrativa a Apropriar"),   # 2026-08-12: com_adm passa a ser provisionada (era só visão)
    ("1.1.07", "Recebíveis de Parcelamentos"),   # FASE B: ramo LOJA (financiamento direto) — carrega SÓ os juros (VAVO fica no 1.1.02)
    # Ajustes Excepcionais de Fábrica (spec 2026-07-21): saldos de acordos no razão
    ("1.1.08", "Créditos com a Fábrica"),
    ("1.1.09", "Créditos com Empresas (conta corrente)"),
    # Não-recebimento (2026-08-07): recebível reclassificado da Contas a Receber "normal" quando o
    # cliente não paga na data prevista — CONTA-IRMÃ de 1.1.02, nunca filha (1.1.02 já é folha e
    # lança direto; virar sintética ao ganhar filho quebraria registro_venda_contrato/
    # recebimento_venda — ver seed_plano/lancar).
    ("1.1.10", "Recebíveis Duvidosos"),
    ("1.2", "Não Circulante"),
    ("1.2.1", "Imobilizado"),
    ("1.2.1.01", "Itens de Informática"), ("1.2.1.02", "Veículos"),
    ("1.2.1.03", "Obras/Reforma de Loja"), ("1.2.1.04", "Show Room"),
    ("1.2.2", "Intangível"),
    ("2", "PASSIVO"),
    ("2.1", "Circulante"),
    ("2.1.01", "Fornecedores a Pagar"), ("2.1.02", "Obrigações Trabalhistas"),
    ("2.1.03", "Obrigações Tributárias"),
    ("2.1.04", "Provisões"),
    ("2.1.04.01", "Provisão de Comissão"), ("2.1.04.02", "Provisão de Montagem"),
    ("2.1.04.03", "Provisão de Garantia"), ("2.1.04.04", "Provisão de Devolução"),
    ("2.1.04.05", "Provisão de Assistência Técnica"),
    # FASE A (infra contábil): Custo Fábrica + provisões das demais rubricas monitoradas
    ("2.1.04.06", "Provisão de Custo de Fábrica"),
    ("2.1.04.07", "Provisão de Frete de Fábrica"),
    ("2.1.04.08", "Provisão de Frete Local"),
    ("2.1.04.09", "Provisão de Insumos Locais"),
    ("2.1.04.10", "Provisão de Comissão de Medidor"),
    ("2.1.04.11", "Provisão de Comissão de Projeto/Executivo"),
    ("2.1.04.12", "Provisão de Retenção de Comissão de Vendas"),
    ("2.1.04.13", "Provisão de Impostos"),   # FASE B2.6: passivo reservado no contrato; efetivado (→ 2.1.03) na emissão
    ("2.1.04.14", "Provisão de Outros Fornecedores"),   # FASE D: recebe a reclassificação do Custo de Fábrica (substituição)
    # FASE A (resultado da venda): os 4 custos adicionais viram provisão (antes só deduzidos do Val_Liq)
    ("2.1.04.15", "Provisão de Comissão de Arquiteto"), ("2.1.04.16", "Provisão de Programa de Fidelidade"),
    ("2.1.04.17", "Provisão de Custo de Viagem"), ("2.1.04.18", "Provisão de Brinde"),
    ("2.1.04.19", "Provisão de Custo Financeiro"),   # FASE B: ramo FINANCEIRA — provisão da despesa financeira
    ("2.1.04.20", "Provisão de Custo Especial"),   # Custo Especial (5º custo adicional — não rateado nos ambientes)
    ("2.1.04.21", "Provisão de Comissão Administrativa"),   # 2026-08-12: previsão de comissionamento do staff
                                                            # da loja (diretores/gerentes) — mesmo mecanismo das
                                                            # demais (constituída no contrato, efetivada/resolvida
                                                            # via Reconciliação, despesa formal em 5.3.03).
    ("2.1.05", "Financiamento Parcelamento Loja a Pagar"),   # ACHADO-14: renomeado de "Total
    # Flex" — o produto virou "Parcelamento Loja" (mod_fin/__init__.py) mas o nome desta conta
    # nunca acompanhou. Rename em migration própria (R13/R14), não em lista no código.
    ("2.1.06", "Receita a Realizar"),   # FASE D2: recebe o Val_Cont cheio no contrato (era "Adiantamento de Clientes")
    ("2.1.07", "Receita Financeira a Apropriar"),   # FASE B: ramo LOJA — juros diferidos, realizados por parcela
    # Ajustes Excepcionais de Fábrica (spec 2026-07-21)
    ("2.1.08", "Acordos com a Fábrica a Amortizar"),
    ("2.1.09", "Débitos com Empresas (conta corrente)"),
    ("2.1.10", "Empréstimos Bancários"),   # Acordos Financeiros (2026-07-21): contraparte banco
    # Conciliação de PE/AF2 (spec 2026-08-14): crédito ao cliente por Estorno (diferença de Custo de
    # Fábrica devolvida) — FORA do grupo 2.1.04 (Provisões) de propósito, pra não ser varrida pela
    # Conciliação Final (conciliar_final itera só o prefixo "2.1.04."). Fica em aberto até baixa manual.
    ("2.1.11", "Créditos a Clientes"),
    ("2.2", "Não Circulante"),
    ("2.2.01", "Financiamentos de Longo Prazo (principal)"),
    ("3", "PATRIMÔNIO LÍQUIDO"),
    ("3.1", "Capital Social"), ("3.2", "Reservas"),
    ("3.3", "Lucros/Prejuízos Acumulados"), ("3.4", "Distribuição de Lucros"),
    ("3.5", "Ajustes de Exercícios Anteriores"),   # CPC 23: implantação de saldos de eventos passados (nunca DRE corrente)
    ("4", "RECEITAS"),
    ("4.1", "Vendas de Produtos"),
    ("4.1.01", "Receitas com Vendas"), ("4.1.02", "Receita com Vendas de Assistência"),
    ("4.2", "Serviços"),
    ("4.2.01", "Receita de Serviços"), ("4.2.02", "Prestação de Serviços para Terceiros"),
    ("4.3", "Deduções"),
    ("4.3.01", "Simples Nacional s/ Vendas"), ("4.3.02", "Devolução de Vendas"),
    ("4.4", "Outras Receitas Não Operacionais"),
    ("4.4.01", "Receita de Aluguéis"),
    ("4.4.02", "Reversão de Provisões"),
    ("4.4.03", "Receita Financeira"),   # FASE B: ramo LOJA — juros do financiamento direto (competência por parcela)
    ("4.4.04", "Ganhos com Acordos Financeiros"),   # opção B (2026-07-22): contrapartida-resultado de acrescer/abater
    ("4.4.05", "Ajuste de Retenção Financeira"),   # ACHADO-01/02/03 (passo 10, docs/db/TAREFA_ACHADO02_03.md):
    # variância entre a retenção esperada (2.1.04.19, ramo financeira) e a real, MESMA conta nos dois
    # sentidos (sobra credita, falta debita) — mesma regra e mesma justificativa dos impostos (4.3.01):
    # mandar sobra pra uma conta e falta pra outra infla receita em vez de corrigir.
    ("5", "DESPESAS / CUSTOS"),
    # Formalismo pleno (decisão do usuário, 2026-07-22, Sessão 109): a despesa de cada rubrica
    # tem UMA conta, e ela mora no grupo contábil FORMAL — frete sobre compra integra o custo
    # da mercadoria (CMV), execução/pós-venda é Custo de Serviço, comissões são Despesas
    # Comerciais. A família 5.6 ("constituição", herança pré-D2) foi suprimida: dava
    # granularidade desnecessária e duplicava conceitos. O reconhecimento na NF-e (matching
    # pleno) debita DIRETO nestas contas; lançamento avulso usa as mesmas.
    ("5.1", "CMV"),
    ("5.1.01", "CMV Fábrica"),
    ("5.1.02", "Frete de Fábrica"),
    ("5.2", "Custo de Serviço"),
    ("5.2.01", "Montagem"), ("5.2.02", "Comissão de Montagem"),
    ("5.2.03", "Viagens de Montagens"), ("5.2.04", "Salários Operacionais"),
    ("5.2.05", "Ajudante Eventual"), ("5.2.06", "Combustível"),
    ("5.2.07", "Pedágio"), ("5.2.08", "Frete Local"), ("5.2.09", "Insumos Locais"),
    ("5.2.10", "Manutenção de Veículos"),
    ("5.2.12", "Garantia"), ("5.2.13", "Assistência Técnica"),
    ("5.3", "Despesas Comerciais"),
    ("5.3.01", "Comissão de Vendedor"), ("5.3.02", "Comissão de Indicador"),
    ("5.3.03", "Comissão Administrativa"), ("5.3.04", "Pontos Programa de Relacionamento"),
    ("5.3.05", "Premiação de Vendedores"), ("5.3.06", "Salários de Vendas"),
    ("5.3.07", "Marketing/Campanhas de Divulgação"), ("5.3.08", "Salário Marketing"),
    ("5.3.09", "Site e Hospedagem"),
    ("5.3.11", "Uniformes"), ("5.3.12", "Brindes"), ("5.3.13", "Suprimento a Cliente"),
    ("5.3.14", "Viagens de Especificador"), ("5.3.15", "Comissão de Arquiteto"),   # FASE A: despesa da comissão de arquiteto (NF-e)
    ("5.3.16", "Benefícios a Funcionários (AT/VA/PS)"),   # Folha Fase 3: benefícios (conta provisória, a validar c/ contabilidade)
    ("5.3.17", "Custo Especial de Projeto"),   # despesa do Custo Especial (5º custo adicional, reconhecida na NF-e)
    # Formalismo (Sessão 109): comissões de execução saem da família 5.6 para Despesas Comerciais
    ("5.3.18", "Comissão de Medidor"),
    ("5.3.19", "Comissão de Projeto/Executivo"),
    # Assistência/Garantia avulsa fora da cobertura (2026-08-07): cortesia ao cliente, sem projeto
    # e sem provisão associada (é uma despesa nova, não uma execução do que já foi provisionado).
    ("5.3.21", "Concessão a Cliente"),
    ("5.4", "Despesas Administrativas"),
    ("5.4.01", "Aluguel"), ("5.4.02", "Energia Elétrica"), ("5.4.03", "Água"),
    ("5.4.04", "Telefonia Fixa/Móvel e Internet"), ("5.4.05", "Contabilidade"),
    ("5.4.06", "Assessoria Jurídica"), ("5.4.07", "Consultoria"),
    ("5.4.08", "Segurança e Seguros"), ("5.4.09", "Material de Limpeza/Expediente"),
    ("5.4.10", "Sistemas (ERP, CRM, assinatura digital)"), ("5.4.11", "Salários Administrativos"),
    ("5.4.12", "Pró-labore"), ("5.4.13", "Encargos sobre Folha"),
    ("5.4.14", "Vale-Transporte"), ("5.4.15", "Sindicato e Contribuições"), ("5.4.16", "Rescisões"),
    ("5.4.17", "IPVA/IPTU/Licenciamentos"),
    # Frente 4 (spec 2026-08-25, DECIDIDO): "5.4.18" perde "veículos" do nome — a 5.2.10
    # "Manutenção de Veículos" vira a ÚNICA conta de veículo do plano (sem mover histórico, sem
    # criar/remover conta; ver migrar_centro_custo_natureza_v2).
    ("5.4.18", "Manutenção (loja e informática)"),
    # Centro de Custo/Natureza (2026-08-08): 2 contas novas pedidas pra fechar a classificação
    ("5.4.19", "Licenças Promob e Sketchup"), ("5.4.20", "Outras Despesas"),
    ("5.5", "Despesas Financeiras"),
    ("5.5.01", "Tarifas Bancárias"), ("5.5.02", "Juros de Empréstimos"),
    ("5.5.03", "Custo de Antecipação de Recebíveis"),
    ("5.5.04", "Custo Financeiro sobre Vendas"),   # FASE B: deságio/taxa da financeira (Aymoré/Cartão)
    ("5.5.05", "Perdas com Acordos Financeiros"),   # opção B (2026-07-22): contrapartida-resultado de acrescer/abater
    # Família 5.6 SUPRIMIDA no formalismo (Sessão 109) — sobra só o Ajuste de Provisões,
    # destino genérico da FALTA (efetivado > provisionado) na reconciliação/Etapa 21.
    ("5.6", "Ajustes de Provisões"),
    # T3 (27/08/2026): renomeada de "Ajuste de Provisões" — a conta já existente no banco foi
    # renomeada na migration 0004; a semente estava desatualizada (owner novo nasceria com o nome
    # velho). O grupo "5.6" acima NÃO foi tocado (segue "Ajustes de Provisões" no banco também).
    ("5.6.10", "Ajustes de Reconciliação"),   # FASE D: destino da FALTA (efetivado > provisionado)
]

# ── Formalismo pleno (Sessão 109) — migração das bases existentes ────────────────────────────
# Cada conta de rubrica da família 5.6 vira a conta FORMAL correspondente. A MESMA linha é
# RECODIFICADA (id preservado → todo o histórico de lançamentos segue junto). Se o código
# formal já estiver ocupado: alvo sem movimento é apagado (recodifica por cima); alvo COM
# movimento (duplicata antiga de lançamento manual) recebe os lançamentos da 5.6 (merge —
# é exatamente a reclassificação da duplicação) e a linha 5.6 morre.
_FORMALISMO_5_6 = {
    "5.6.01": ("5.2.12", "5.2", "Garantia"),
    "5.6.02": ("5.2.01", "5.2", "Montagem"),
    "5.6.03": ("5.2.13", "5.2", "Assistência Técnica"),
    "5.6.04": ("5.1.02", "5.1", "Frete de Fábrica"),
    "5.6.05": ("5.2.08", "5.2", "Frete Local"),
    "5.6.06": ("5.2.09", "5.2", "Insumos Locais"),
    "5.6.07": ("5.3.18", "5.3", "Comissão de Medidor"),
    "5.6.08": ("5.3.19", "5.3", "Comissão de Projeto/Executivo"),
    # 5.6.09 removida (Centro de Custo/Natureza, 2026-08-08): apontava pra 5.3.20, que deixou de
    # existir (evento redirecionado pra 5.3.01 — ver migrar_centro_custo_natureza_v1).
}

# Todos os nomes que uma conta destas já teve em QUALQUER geração de seed (original
# "Constituição — …", S107 "… — Despesa Reconhecida", S108 nome puro, e os nomes das
# duplicatas antigas dos grupos 5.1/5.2). Renomeia só quem carrega um destes — nome
# customizado pelo usuário não é sobrescrito.
_NOMES_HISTORICOS = {
    "5.6.01": {"Constituição — Provisão de Garantia", "Garantia — Despesa Reconhecida", "Garantia"},
    "5.6.02": {"Constituição — Provisão de Montagem", "Montagem — Despesa Reconhecida", "Montagem"},
    "5.6.03": {"Constituição — Provisão de Assistência Técnica",
               "Assistência Técnica — Despesa Reconhecida", "Assistência Técnica"},
    "5.6.04": {"Constituição — Provisão de Frete de Fábrica",
               "Frete de Fábrica — Despesa Reconhecida", "Frete de Fábrica", "Frete Fábrica"},
    "5.6.05": {"Constituição — Provisão de Frete Local", "Frete Local — Despesa Reconhecida",
               "Frete Local"},
    "5.6.06": {"Constituição — Provisão de Insumos Locais", "Insumos Locais — Despesa Reconhecida",
               "Insumos Locais", "Insumos"},
    "5.6.07": {"Constituição — Provisão de Comissão de Medidor",
               "Comissão de Medidor — Despesa Reconhecida", "Comissão de Medidor"},
    "5.6.08": {"Constituição — Provisão de Comissão de Projeto/Executivo",
               "Comissão de Projeto/Executivo — Despesa Reconhecida", "Comissão de Projeto/Executivo"},
}

_NOMES_HISTORICOS_GRUPO_5_6 = ("Constituição de Provisões", "Despesas Reconhecidas de Provisões",
                               "Despesas de Provisões")


def _conta_tem_movimento(db, conta):
    return (db.query(Lancamento)
              .filter((Lancamento.conta_debito_id == conta.id) |
                      (Lancamento.conta_credito_id == conta.id))
              .first() is not None)


def migrar_plano_formalismo(db):
    """Formalismo pleno (decisão do usuário, 2026-07-22, Sessão 109) em TODOS os owners,
    idempotente — roda no start ANTES do backfill (senão o seed criaria as contas formais
    vazias e forçaria o caminho de merge à toa). Ver _FORMALISMO_5_6. Nenhum lançamento se
    perde: recodificação preserva o id da conta; merge reponta os lançamentos."""
    ordem_seed = {cod: i for i, (cod, _n) in enumerate(PLANO_PADRAO)}
    owners = db.query(Conta.owner_tipo, Conta.owner_id).distinct().all()
    recodificadas = mescladas = grupos = 0
    for ot, oid in owners:
        contas = {c.codigo: c for c in db.query(Conta)
                  .filter_by(owner_tipo=ot, owner_id=oid).all()}
        for cod56, (cod_novo, pai_cod, nome_novo) in _FORMALISMO_5_6.items():
            c = contas.get(cod56)
            if c is None:
                continue
            alvo = contas.pop(cod_novo, None)
            if alvo is not None:
                if not _conta_tem_movimento(db, alvo):
                    db.delete(alvo)
                    db.flush()
                else:
                    # duplicata antiga com movimento: ela VIRA a conta formal; o histórico
                    # da 5.6 é repontado pra ela (a reclassificação da duplicação manual)
                    db.query(Lancamento).filter(Lancamento.conta_debito_id == c.id)\
                        .update({"conta_debito_id": alvo.id}, synchronize_session=False)
                    db.query(Lancamento).filter(Lancamento.conta_credito_id == c.id)\
                        .update({"conta_credito_id": alvo.id}, synchronize_session=False)
                    db.delete(c)
                    del contas[cod56]
                    alvo.ativa = 1
                    if alvo.nome in _NOMES_HISTORICOS.get(cod56, set()):
                        alvo.nome = nome_novo
                    contas[cod_novo] = alvo
                    mescladas += 1
                    continue
            pai = contas.get(pai_cod)
            c.codigo = cod_novo
            if pai is not None:
                c.pai_id = pai.id
            if c.nome in _NOMES_HISTORICOS.get(cod56, set()):
                c.nome = nome_novo
            if cod_novo in ordem_seed:
                c.ordem = ordem_seed[cod_novo]
            del contas[cod56]
            contas[cod_novo] = c
            recodificadas += 1
        g = contas.get("5.6")
        if g is not None and g.nome in _NOMES_HISTORICOS_GRUPO_5_6:
            g.nome = "Ajustes de Provisões"
            grupos += 1
    db.commit()
    return {"recodificadas": recodificadas, "mescladas": mescladas, "grupos_renomeados": grupos}


# ── Centro de Custo + Natureza (decisão do usuário, 2026-08-08) ──────────────────────────────
# Passo 1 do pedido: ajustes pontuais no plano ANTES de classificar por Centro de Custo/Natureza.
# Renomeia só quem ainda carrega o nome antigo (nome customizado pelo usuário não é sobrescrito —
# mesmo cuidado de _NOMES_HISTORICOS).
_RENOMEIA_CENTRO_CUSTO_V1 = {
    "5.1.01": ("CMV Fábrica (Dal Mobile)", "CMV Fábrica"),
    "5.2.02": ("Comissão Executivo de Montagem", "Comissão de Montagem"),
    "5.2.03": ("Viagens de Pedido", "Viagens de Montagens"),
    "5.2.05": ("Ajudante Semanal", "Ajudante Eventual"),
    "5.2.06": ("Combustível de Depósito", "Combustível"),
    "5.3.04": ("Pontos Programa de Indicação", "Pontos Programa de Relacionamento"),
    "5.4.15": ("Sindicato", "Sindicato e Contribuições"),
}
_REMOVE_CENTRO_CUSTO_V1 = ("5.2.11", "5.3.10", "5.3.20")
_CRIAR_CENTRO_CUSTO_V1 = [("5.4.19", "Licenças Promob e Sketchup"), ("5.4.20", "Outras Despesas")]


def migrar_centro_custo_natureza_v1(db):
    """Centro de Custo/Natureza (decisão do usuário, 2026-08-08) em TODOS os owners, idempotente
    — roda no boot logo depois de migrar_plano_formalismo e ANTES de backfill_plano_todos_owners
    (senão o backfill recriaria 5.2.11/5.3.10/5.3.20, já tiradas de PLANO_PADRAO). Por owner:
    (1) renomeia contas cujo nome ainda é o padrão antigo; (2) reponta os lançamentos de 5.3.10
    "Combustível de Venda" pra 5.2.06 "Combustível" (única conta de combustível daqui pra frente);
    (3) remove 5.2.11/5.3.10/5.3.20 — apaga se puder (sem filho/lançamento, mesma regra de
    remover_conta), senão inativa; (4) cria as 2 contas novas que ainda faltarem."""
    ordem_seed = {cod: i for i, (cod, _n) in enumerate(PLANO_PADRAO)}
    owners = db.query(Conta.owner_tipo, Conta.owner_id).distinct().all()
    renomeadas = combustivel_unificado = removidas = inativadas = criadas = 0
    for ot, oid in owners:
        contas = {c.codigo: c for c in db.query(Conta)
                  .filter_by(owner_tipo=ot, owner_id=oid).all()}
        for cod, (nome_antigo, nome_novo) in _RENOMEIA_CENTRO_CUSTO_V1.items():
            c = contas.get(cod)
            if c is not None and c.nome == nome_antigo:
                c.nome = nome_novo
                renomeadas += 1
        origem = contas.get("5.3.10")
        destino = contas.get("5.2.06")
        if origem is not None and destino is not None:
            n1 = db.query(Lancamento).filter(Lancamento.conta_debito_id == origem.id)\
                   .update({"conta_debito_id": destino.id}, synchronize_session=False)
            n2 = db.query(Lancamento).filter(Lancamento.conta_credito_id == origem.id)\
                   .update({"conta_credito_id": destino.id}, synchronize_session=False)
            db.flush()
            if n1 or n2:
                combustivel_unificado += 1
        for cod in _REMOVE_CENTRO_CUSTO_V1:
            c = contas.get(cod)
            if c is None:
                continue
            if not _tem_filhos(db, c) and not _tem_lancamentos(db, c):
                db.delete(c)
                db.flush()
                removidas += 1
            else:
                c.ativa = 0
                inativadas += 1
            del contas[cod]
        for cod, nome in _CRIAR_CENTRO_CUSTO_V1:
            if cod in contas:
                continue
            pai = contas.get(_pai_codigo(cod))
            if pai is not None and pai.tipo == "analitica":
                pai.tipo = "sintetica"
            grupo = int(cod.split(".")[0])
            c = Conta(owner_tipo=ot, owner_id=oid, codigo=cod, nome=nome, grupo=grupo,
                      tipo="analitica", natureza=_natureza(grupo),
                      pai_id=pai.id if pai is not None else None,
                      ativa=1, ordem=ordem_seed.get(cod, 999))
            db.add(c)
            db.flush()
            contas[cod] = c
            criadas += 1
    db.commit()
    return {"renomeadas": renomeadas, "combustivel_unificado": combustivel_unificado,
            "removidas": removidas, "inativadas": inativadas, "criadas": criadas}


_RENOMEIA_CENTRO_CUSTO_V2 = {
    "5.4.18": ("Manutenção (loja, veículos, informática)", "Manutenção (loja e informática)"),
}


def migrar_centro_custo_natureza_v2(db):
    """Higiene do plano de contas (Frente 4, spec 2026-08-25, DECIDIDO): "5.4.18" perde
    "veículos" do nome — a 5.2.10 "Manutenção de Veículos" vira a ÚNICA conta de veículo do
    plano (veículo de montagem/entrega é Logística/Expedição; manutenção de loja e TI segue em
    Custos Distribuídos, sem mover). Resolve por TEXTO — sem mover histórico, sem criar/remover
    conta, sem migração de schema. Mesmo padrão idempotente de
    migrar_centro_custo_natureza_v1 (só toca quem AINDA tiver o nome antigo). Roda no boot, em
    TODOS os owners."""
    owners = db.query(Conta.owner_tipo, Conta.owner_id).distinct().all()
    renomeadas = 0
    for ot, oid in owners:
        contas = {c.codigo: c for c in db.query(Conta)
                  .filter_by(owner_tipo=ot, owner_id=oid).all()}
        for cod, (nome_antigo, nome_novo) in _RENOMEIA_CENTRO_CUSTO_V2.items():
            c = contas.get(cod)
            if c is not None and c.nome == nome_antigo:
                c.nome = nome_novo
                renomeadas += 1
    db.commit()
    return {"renomeadas": renomeadas}


def migrar_centro_custo_v2(db):
    """Ajuste do usuário na árvore de Centro de Custo (2026-08-08, revisão do dia): "Produtivo"
    vira "Operacional"; Instalações/Infraestrutura sai de Suporte (4.1) e entra em Operacional
    (1.5); Projetos/Design sai de Comercial (2.2) e entra em Pós-venda (3.2). Move os MESMOS nós
    (id preservado — se uma Conta já apontar pro centro_custo_id, o vínculo sobrevive intacto) —
    só recodifica/reparenta, não recria. Roda no boot, em TODOS os owners, ANTES do backfill
    (senão o backfill recriaria os nós na posição velha, já que ficariam "faltando" lá).
    Idempotente: a 2ª chamada não acha mais nada em "4.1"/"2.2" (já foram recodificados) e não
    faz nada."""
    owners = db.query(CentroCusto.owner_tipo, CentroCusto.owner_id).distinct().all()
    renomeados = movidos = 0
    for ot, oid in owners:
        ccs = {c.codigo: c for c in db.query(CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).all()}
        raiz1 = ccs.get("1")
        if raiz1 is not None and raiz1.nome == "Produtivo":
            raiz1.nome = "Operacional"
            renomeados += 1
        inst = ccs.get("4.1")
        if inst is not None and inst.nome == "Instalações/Infraestrutura" and raiz1 is not None:
            inst.codigo = "1.5"
            inst.pai_id = raiz1.id
            movidos += 1
        raiz3 = ccs.get("3")
        proj = ccs.get("2.2")
        if proj is not None and proj.nome == "Projetos/Design" and raiz3 is not None:
            proj.codigo = "3.2"
            proj.pai_id = raiz3.id
            movidos += 1
    db.commit()
    return {"renomeados": renomeados, "movidos": movidos}


def _pai_codigo(codigo):
    return codigo.rsplit(".", 1)[0] if "." in codigo else None


def _natureza(grupo):
    # Ativo(1)/Despesa(5) devedora; Passivo(2)/PL(3)/Receita(4) credora
    # T7 (27/08/2026): Conta.natureza (aqui) e Conta.natureza_custo (NATUREZA_CUSTO, mais abaixo)
    # são coisas SEM RELAÇÃO, apesar do nome parecido — natureza CONTÁBIL (credora|devedora, todo
    # grupo) vs. COMPORTAMENTO do custo (fixo|variavel|semivariavel, só grupo 5). O nome parecido
    # é herança; não renomear (~130 referências a natureza_custo, campo de API e de frontend).
    return "devedora" if grupo in (1, 5) else "credora"


_FUSO_PADRAO = "America/Sao_Paulo"


def _fuso_de_config_json(config_json_str):
    """Extrai `fuso_horario` de um `config_financeira_json` bruto (string), ou None. Puro,
    sem I/O — não distingue "campo ausente" de "JSON inválido", os dois viram None (o chamador
    decide o próximo degrau da cadeia)."""
    if not config_json_str:
        return None
    import json
    try:
        cfg = json.loads(config_json_str)
    except (TypeError, ValueError):
        return None
    fuso = (cfg or {}).get("fuso_horario") if isinstance(cfg, dict) else None
    return fuso or None


def resolver_fuso_owner(db, owner_tipo, owner_id):
    """ACHADO-48 (DECIDIDO 02/09) — fuso horário do DONO DO LIVRO, nunca o relógio da máquina.
    Cadeia: config da loja → config da rede (da loja, se houver) → America/Sao_Paulo. Owner
    "rede" pula direto pro degrau da rede (o livro já É da rede). `Rede` não tem
    `config_financeira_json` hoje (só `Loja` tem) — o degrau existe na cadeia, mas não tem o que
    ler ainda; cai no default. Nunca lê TZ do processo/sistema operacional — é exatamente essa
    mistura (date.today() local × datetime.utcnow()) que causou o ACHADO-48."""
    if owner_tipo == "loja":
        loja = db.get(Loja, owner_id)
        if loja is not None:
            fuso = _fuso_de_config_json(getattr(loja, "config_financeira_json", None))
            if fuso:
                return fuso
            if loja.rede_id:
                rede = db.get(Rede, loja.rede_id)
                fuso = _fuso_de_config_json(getattr(rede, "config_financeira_json", None)) if rede else None
                if fuso:
                    return fuso
    elif owner_tipo == "rede":
        rede = db.get(Rede, owner_id)
        fuso = _fuso_de_config_json(getattr(rede, "config_financeira_json", None)) if rede else None
        if fuso:
            return fuso
    return _FUSO_PADRAO


def agora_no_fuso(db, owner_tipo, owner_id):
    """'Agora' na hora de PAREDE do fuso do dono do livro (`resolver_fuso_owner`) — devolve
    NAIVE (sem tzinfo), pro mesmo tipo que `Lancamento.data`/`date.today()` sempre usaram. Fonte
    ÚNICA: o carimbo de `lancar()` e todo `date.today()`/`datetime.utcnow()` de regra de negócio
    saem daqui — nunca mais do relógio do processo."""
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    fuso = resolver_fuso_owner(db, owner_tipo, owner_id)
    try:
        tz = ZoneInfo(fuso)
    except Exception:
        tz = ZoneInfo(_FUSO_PADRAO)
    return _dt.now(tz).replace(tzinfo=None)


def hoje_no_fuso(db, owner_tipo, owner_id):
    """A data (sem hora) de hoje no fuso do dono do livro — mesma fonte de `agora_no_fuso`."""
    return agora_no_fuso(db, owner_tipo, owner_id).date()


def data_emissao_iso_no_fuso(db, owner_tipo, owner_id):
    """ACHADO-48 (02/09) — data-hora de emissão (NF-e/NFS-e) no formato que a SEFAZ exige
    (AAAA-MM-DDTHH:MM:SS±HH:MM), com o OFFSET calculado de verdade a partir do fuso do dono do
    livro — nunca "-03:00" fixo. Substitui o hack anterior (`datetime.utcnow() - timedelta(hours=3)`
    com sufixo hardcoded), que dependia do servidor rodar em UTC pra não fabricar um horário no
    futuro (achado do usuário 2026-08-08) — a mesma classe de bug do ACHADO-48, resolvida na
    fonte única, não mais com um ajuste manual por servidor."""
    from zoneinfo import ZoneInfo
    fuso = resolver_fuso_owner(db, owner_tipo, owner_id)
    try:
        tz = ZoneInfo(fuso)
    except Exception:
        tz = ZoneInfo(_FUSO_PADRAO)
    from datetime import datetime as _dt
    agora_tz = _dt.now(tz)
    return agora_tz.strftime("%Y-%m-%dT%H:%M:%S") + agora_tz.strftime("%z")[:3] + ":" + agora_tz.strftime("%z")[3:]


def resolver_owner(db, usuario):
    """`db` não é mais usado (a resolução virou pura, sem consultar `Loja`) — mantido na
    assinatura só pra não mexer nas ~26 chamadas existentes.

    (owner_tipo, owner_id) do usuário: SEMPRE a própria loja quando há `loja_id` — cada loja
    tem razão PRÓPRIO, mesmo pertencendo a uma rede (PDV também: owner ("loja", pdv.id), mesmo com
    rede herdada da mãe). `rede_id` sozinho (sem loja_id — ex.: admin_rede sem unidade ativa
    selecionada) resolve pro owner da REDE em si, um registro à parte, não um pote compartilhado
    entre as lojas dela.

    Corte 2026-08-10 (Sessão 188, decisão do usuário — "cada loja tem vida própria", sem dado real
    dependendo do comportamento antigo em nenhum ambiente, auditado antes do corte): ATÉ AQUI, loja
    de rede escrevia direto no razão COMPARTILHADO da rede (`("rede", loja.rede_id)`) — pensado
    pra netar transação intercompany entre lojas-irmãs sem precisar de conta corrente (Sessão 95).
    Na prática, isso misturava aluguel/dívida/tudo de todas as lojas da rede num livro só, sem
    jeito de segregar por loja depois (Lancamento não tem loja_id, só projeto_id — e nem todo
    lançamento tem projeto). Daqui pra frente, TODA loja (de rede ou não) sempre tem seu próprio
    owner; uma relação real entre duas lojas da mesma rede passa a seguir o MESMO tratamento
    intercompany que já existe pra loja×fábrica/empresa externa (`AcordoFabrica`/
    `ContraparteFinanceira`, conta corrente 1.1.09×2.1.09) — não um caso especial de "mesmo dono".
    HISTÓRICO já lançado sob `("rede", X)` antes do corte NÃO é reescrito (fato passado, congelado
    — mesmo princípio de não retroagir cláusula já assinada em `mod_documentos`); só afeta os
    ambientes de homolog/UAT que tinham essa história (nenhuma rede em produção tinha lançamento
    algum na data do corte — auditado antes de mudar)."""
    rid = usuario.get("rede_id")
    lid = usuario.get("loja_id")
    if lid:
        return ("loja", lid)
    if rid:
        return ("rede", rid)
    raise ValueError("usuário sem loja nem rede para resolver owner contábil")


def seed_plano(db, owner_tipo, owner_id):
    """Materializa/atualiza o plano-padrão do owner: cria as contas de PLANO_PADRAO que ainda
    faltam — **backfill idempotente** (planos já existentes ganham contas novas, ex.: as 3 provisões
    da v5). Retorna nº de contas criadas (0 se nada faltava)."""
    existentes = {c.codigo: c for c in db.query(Conta)
                  .filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    codigos = {c for c, _ in PLANO_PADRAO}
    id_por_codigo = {cod: c.id for cod, c in existentes.items()}
    criadas = 0
    for ordem, (codigo, nome) in enumerate(PLANO_PADRAO):
        if codigo in existentes:
            continue
        grupo = int(codigo.split(".")[0])
        tipo = "sintetica" if any(o.startswith(codigo + ".") for o in codigos) else "analitica"
        pai_cod = _pai_codigo(codigo)
        pai_exist = existentes.get(pai_cod)
        if pai_exist is not None and pai_exist.tipo == "analitica":
            pai_exist.tipo = "sintetica"          # pai que era folha vira agrupador ao ganhar filho
        c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo, nome=nome,
                  grupo=grupo, tipo=tipo, natureza=_natureza(grupo),
                  pai_id=id_por_codigo.get(pai_cod), ativa=1, ordem=ordem)
        db.add(c)
        db.flush()
        id_por_codigo[codigo] = c.id
        criadas += 1
    if criadas:
        db.commit()
    return criadas


def backfill_plano_todos_owners(db):
    """Backfill idempotente do plano de contas em TODOS os owners que já têm plano — garante que
    planos antigos ganhem as contas novas de PLANO_PADRAO (Adiantamento de Clientes, Provisão Custo
    Fábrica e demais provisões monitoradas — FASE A). Reusa seed_plano. Retorna nº total de contas criadas."""
    owners = db.query(Conta.owner_tipo, Conta.owner_id).distinct().all()
    return sum(seed_plano(db, ot, oid) for ot, oid in owners)


def _serial(c):
    return {"id": c.id, "codigo": c.codigo, "nome": c.nome, "grupo": c.grupo,
            "tipo": c.tipo, "natureza": c.natureza, "pai_id": c.pai_id, "ativa": bool(c.ativa),
            "centro_custo_id": c.centro_custo_id, "natureza_custo": c.natureza_custo}


def listar_contas(db, owner_tipo, owner_id, incluir_inativas=False):
    """Árvore (lista de raízes com 'filhos'), ordenada por 'ordem'/codigo. Seed-on-first-access —
    só a ÁRVORE (`seed_plano`). Classificação do grupo 5 é `aplicar_gabarito_completo`, chamada
    nos endpoints de TELA (main.py `/api/financeiro/contas` e `/centro-custo`), não aqui: esta
    função também é usada por relatórios de leitura pura (`relatorio_centro_custo` via
    `listar_centros_custo`), que não podem ter o efeito colateral de classificar conta sozinhos."""
    seed_plano(db, owner_tipo, owner_id)
    q = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    if not incluir_inativas:
        q = q.filter(Conta.ativa == 1)
    contas = q.order_by(Conta.ordem, Conta.codigo).all()
    nodes = {c.id: {**_serial(c), "filhos": []} for c in contas}
    raizes = []
    for c in contas:
        if c.pai_id and c.pai_id in nodes:
            nodes[c.pai_id]["filhos"].append(nodes[c.id])
        else:
            raizes.append(nodes[c.id])
    return raizes


# ── CRUD ────────────────────────────────────────────────────────────────────
def _get_own(db, owner_tipo, owner_id, conta_id):
    c = db.get(Conta, conta_id)
    if c is None:
        raise ValueError("conta inexistente")
    if c.owner_tipo != owner_tipo or c.owner_id != owner_id:
        raise PermissionError("conta de outro owner")
    return c


def _tem_filhos(db, conta):
    return db.query(Conta).filter_by(owner_tipo=conta.owner_tipo, owner_id=conta.owner_id,
                                     pai_id=conta.id).first() is not None


def _tem_lancamentos(db, conta):
    from sqlalchemy import or_
    return db.query(Lancamento).filter_by(owner_tipo=conta.owner_tipo, owner_id=conta.owner_id).filter(
        or_(Lancamento.conta_debito_id == conta.id,
            Lancamento.conta_credito_id == conta.id)).first() is not None


def _proximo_codigo(db, pai):
    filhos = db.query(Conta).filter_by(owner_tipo=pai.owner_tipo, owner_id=pai.owner_id,
                                       pai_id=pai.id).all()
    usados = set()
    for f in filhos:
        try:
            usados.add(int(f.codigo.rsplit(".", 1)[-1]))
        except ValueError:
            pass
    seq = 1
    while seq in usados:
        seq += 1
    return f"{pai.codigo}.{seq:02d}"


# Sentinela: distingue "campo ausente do request" de "None explícito" — mesmo padrão de
# mod_comissao._NAO_INFORMADO. Necessário pra Frente 3 (spec 2026-08-25): centro_custo_id/
# natureza_custo OMITIDOS não mexem em nada (ex.: só renomear); PASSADOS vazio/None numa conta do
# grupo 5 é tentativa de LIMPAR, que a obrigatoriedade (DECIDIDO) bloqueia.
_NAO_INFORMADO = object()


def criar_conta(db, owner_tipo, owner_id, pai_id, nome, centro_custo_id=None, natureza_custo=None,
                reclassificar_autorizado=False):
    """`centro_custo_id`/`natureza_custo`: obrigatórios quando o pai é do grupo 5 (Frente 3,
    DECIDIDO — toda conta do grupo 5 nasce classificada). `reclassificar_autorizado`: o CALLER
    (HTTP layer) já validou o perfil (Gerente Adm/Financeiro ou Diretor) — sem isso, criar conta
    no grupo 5 (que exige classificar) levanta PermissionError."""
    pai = _get_own(db, owner_tipo, owner_id, pai_id)
    if not (nome or "").strip():
        raise ValueError("nome obrigatório")
    if pai.tipo == "analitica":
        pai.tipo = "sintetica"                            # pai passa a agrupar
    cc_id, nat = None, None
    if pai.grupo == 5:
        if not reclassificar_autorizado:
            raise PermissionError("Criar conta em Despesas/Custos exige Gerente Adm/Financeiro ou Diretor.")
        if not centro_custo_id:
            raise ValueError("Centro de Custo é obrigatório para contas do grupo 5.")
        if not natureza_custo:
            raise ValueError("Natureza é obrigatória para contas do grupo 5.")
        cc = _get_own_cc(db, owner_tipo, owner_id, centro_custo_id)
        naturezas_validas = {slug for slug, _ in NATUREZA_CUSTO}
        if natureza_custo not in naturezas_validas:
            raise ValueError(f"natureza inválida: {natureza_custo}")
        cc_id, nat = cc.id, natureza_custo
    c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=_proximo_codigo(db, pai),
              nome=nome.strip(), grupo=pai.grupo, tipo="analitica", natureza=_natureza(pai.grupo),
              pai_id=pai.id, ativa=1, ordem=999, centro_custo_id=cc_id, natureza_custo=nat)
    db.add(c)
    db.commit()
    return _serial(c)


def editar_conta(db, owner_tipo, owner_id, conta_id, nome=None, ordem=None,
                 centro_custo_id=_NAO_INFORMADO, natureza_custo=_NAO_INFORMADO,
                 reclassificar_autorizado=False):
    """Botão Editar (Frente 3, spec 2026-08-25) — substitui Renomear, reune nome + Centro de
    Custo + Natureza numa transação só. `centro_custo_id`/`natureza_custo`:
    `_NAO_INFORMADO` (default) = não mexe (renomear/reordenar sozinho continua igual de sempre);
    qualquer OUTRO valor (inclusive `None`/vazio) = pedido de reclassificação, que:
    (a) exige `reclassificar_autorizado=True` (perfil Gerente Adm/Financeiro ou Diretor — checado
    pelo CALLER, esta função não conhece perfil de usuário); (b) numa conta do grupo 5, não aceita
    vazio — classificação é OBRIGATÓRIA (DECIDIDO); limpar continua só possível por
    `classificar_contas_lote`, ferramenta administrativa."""
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    if nome is not None:
        if not nome.strip():
            raise ValueError("nome obrigatório")
        c.nome = nome.strip()
    if ordem is not None:
        c.ordem = int(ordem)
    if centro_custo_id is not _NAO_INFORMADO or natureza_custo is not _NAO_INFORMADO:
        if not reclassificar_autorizado:
            raise PermissionError("Reclassificar Centro de Custo/Natureza exige Gerente Adm/Financeiro ou Diretor.")
        if c.grupo == 5:
            if not centro_custo_id:
                raise ValueError("Centro de Custo é obrigatório para contas do grupo 5.")
            if not natureza_custo:
                raise ValueError("Natureza é obrigatória para contas do grupo 5.")
        if centro_custo_id:
            cc = _get_own_cc(db, owner_tipo, owner_id, centro_custo_id)
            c.centro_custo_id = cc.id
        elif centro_custo_id is not _NAO_INFORMADO:
            c.centro_custo_id = None
        if natureza_custo:
            naturezas_validas = {slug for slug, _ in NATUREZA_CUSTO}
            if natureza_custo not in naturezas_validas:
                raise ValueError(f"natureza inválida: {natureza_custo}")
            c.natureza_custo = natureza_custo
        elif natureza_custo is not _NAO_INFORMADO:
            c.natureza_custo = None
    db.commit()
    return _serial(c)


def remover_conta(db, owner_tipo, owner_id, conta_id):
    """Folha sem lançamento -> apaga; senão inativa (regra do .docx). Apagar o ÚLTIMO filho de um
    pai promovido a sintética por criar_conta() reverte o pai a analítica de volta — senão ele fica
    preso sem poder receber lançamento (achado ao apagar contas de teste do Fluxo de Caixa: "1.1.01"
    ficou sintética e vazia, e contas_caixa() parou de devolver qualquer conta)."""
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    if not _tem_filhos(db, c) and not _tem_lancamentos(db, c):
        pai_id = c.pai_id
        db.delete(c)
        db.flush()
        if pai_id:
            pai = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, id=pai_id).first()
            if pai and pai.tipo == "sintetica" and not _tem_filhos(db, pai):
                pai.tipo = "analitica"
        db.commit()
        return {"acao": "apagada", "id": conta_id}
    c.ativa = 0
    db.commit()
    return {"acao": "inativada", "id": conta_id}


# ── Centro de Custo + Natureza (decisão do usuário, 2026-08-08) ──────────────────────────────
# "Quem gastou" — árvore própria por owner, só referenciada por Conta.centro_custo_id (sem
# lançamento próprio). Escopo do pedido: só as contas do grupo "5 DESPESAS/CUSTOS" são
# classificadas, mas a árvore em si não impõe essa restrição (validação fica no bulk-classify).
CENTRO_CUSTO_PADRAO = [
    ("1", "Operacional"),
    # "1.1 Produção própria" removida da semente (T3, 27/08/2026): a migration 0004 já a tirou
    # do banco (owner nenhum a tem hoje) — mantê-la aqui a traria de volta pro próximo owner novo.
    ("1.2", "Fábricas e Fornecedores"),
    ("1.3", "Montagem"), ("1.4", "Logística/Expedição"),
    ("1.5", "Instalações/Infraestrutura"),   # 2026-08-08: mudou de Suporte pra Operacional
    ("2", "Comercial"),
    ("2.1", "Vendas/Loja"), ("2.3", "Marketing"),   # 2.2 (Projetos/Design) mudou pra Pós-venda
    ("3", "Pós-venda"),
    ("3.1", "Assistência Técnica/Pós-venda"),
    ("3.2", "Projetos/Design"),   # 2026-08-08: mudou de Comercial pra Pós-venda
    ("4", "Suporte"),
    ("4.2", "Sistemas e TI"),
    ("4.3", "Administrativo-financeiro"), ("4.4", "Diretoria/Gestão"),
    ("4.5", "Custos Distribuídos"),
]

# Natureza do custo — lista fechada (3 itens), sem tabela própria: só um slug em Conta.natureza_custo.
# T7 (27/08/2026): não confundir com Conta.natureza (credora|devedora — ver _natureza(), acima
# no arquivo) — mesmo nome parecido, conceitos sem relação. Não renomear (regra permanente).
NATUREZA_CUSTO = [("fixo", "Fixo"), ("variavel", "Variável"), ("semivariavel", "Semivariável")]


def seed_centro_custo(db, owner_tipo, owner_id):
    """Materializa/atualiza a árvore-padrão do owner — backfill idempotente, mesmo padrão de
    seed_plano. Retorna nº de nós criados (0 se nada faltava)."""
    existentes = {c.codigo: c for c in db.query(CentroCusto)
                  .filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    id_por_codigo = {cod: c.id for cod, c in existentes.items()}
    criados = 0
    for ordem, (codigo, nome) in enumerate(CENTRO_CUSTO_PADRAO):
        if codigo in existentes:
            continue
        pai_cod = _pai_codigo(codigo)
        c = CentroCusto(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo, nome=nome,
                        pai_id=id_por_codigo.get(pai_cod), ativo=1, ordem=ordem)
        db.add(c)
        db.flush()
        id_por_codigo[codigo] = c.id
        criados += 1
    if criados:
        db.commit()
    return criados


def backfill_centro_custo_todos_owners(db):
    """Backfill idempotente da árvore de Centro de Custo em TODOS os owners que já têm Plano de
    Contas — reusa seed_centro_custo. Retorna nº total de nós criados."""
    owners = db.query(Conta.owner_tipo, Conta.owner_id).distinct().all()
    return sum(seed_centro_custo(db, ot, oid) for ot, oid in owners)


def _serial_cc(c):
    return {"id": c.id, "codigo": c.codigo, "nome": c.nome, "pai_id": c.pai_id, "ativo": bool(c.ativo),
            "protegido": c.codigo in CENTRO_CUSTO_PROTEGIDOS}


def listar_centros_custo(db, owner_tipo, owner_id, incluir_inativos=False):
    """Árvore (lista de raízes com 'filhos'), ordenada por 'ordem'/codigo. Seed-on-first-access —
    só a ÁRVORE (`seed_centro_custo`); mesma razão de `listar_contas` pra não chamar
    `aplicar_gabarito_completo` aqui (usada por `relatorio_centro_custo`, leitura pura)."""
    seed_centro_custo(db, owner_tipo, owner_id)
    q = db.query(CentroCusto).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    if not incluir_inativos:
        q = q.filter(CentroCusto.ativo == 1)
    itens = q.order_by(CentroCusto.ordem, CentroCusto.codigo).all()
    nodes = {c.id: {**_serial_cc(c), "filhos": []} for c in itens}
    raizes = []
    for c in itens:
        if c.pai_id and c.pai_id in nodes:
            nodes[c.pai_id]["filhos"].append(nodes[c.id])
        else:
            raizes.append(nodes[c.id])
    return raizes


def _get_own_cc(db, owner_tipo, owner_id, cc_id):
    c = db.get(CentroCusto, cc_id)
    if c is None:
        raise ValueError("centro de custo inexistente")
    if c.owner_tipo != owner_tipo or c.owner_id != owner_id:
        raise PermissionError("centro de custo de outro owner")
    return c


def _cc_tem_filhos(db, cc):
    return db.query(CentroCusto).filter_by(owner_tipo=cc.owner_tipo, owner_id=cc.owner_id,
                                           pai_id=cc.id).first() is not None


def _cc_tem_uso(db, cc):
    return db.query(Conta).filter_by(owner_tipo=cc.owner_tipo, owner_id=cc.owner_id,
                                     centro_custo_id=cc.id).first() is not None


def _proximo_codigo_cc(db, pai):
    filhos = db.query(CentroCusto).filter_by(owner_tipo=pai.owner_tipo, owner_id=pai.owner_id,
                                             pai_id=pai.id).all()
    usados = set()
    for f in filhos:
        try:
            usados.add(int(f.codigo.rsplit(".", 1)[-1]))
        except ValueError:
            pass
    seq = 1
    while seq in usados:
        seq += 1
    return f"{pai.codigo}.{seq}"


def criar_centro_custo(db, owner_tipo, owner_id, pai_id, nome):
    pai = _get_own_cc(db, owner_tipo, owner_id, pai_id)
    if not (nome or "").strip():
        raise ValueError("nome obrigatório")
    c = CentroCusto(owner_tipo=owner_tipo, owner_id=owner_id, codigo=_proximo_codigo_cc(db, pai),
                    nome=nome.strip(), pai_id=pai.id, ativo=1, ordem=999)
    db.add(c)
    db.commit()
    return _serial_cc(c)


def editar_centro_custo(db, owner_tipo, owner_id, cc_id, nome=None, ordem=None):
    c = _get_own_cc(db, owner_tipo, owner_id, cc_id)
    if nome is not None:
        if not nome.strip():
            raise ValueError("nome obrigatório")
        c.nome = nome.strip()
    if ordem is not None:
        c.ordem = int(ordem)
    db.commit()
    return _serial_cc(c)


def remover_centro_custo(db, owner_tipo, owner_id, cc_id):
    """Folha sem filho e sem conta apontando pra ele -> apaga; senão inativa (mesma regra de
    remover_conta — Centro de Custo não tem lançamento próprio, só é referenciado por Conta).
    T4: código em CENTRO_CUSTO_PROTEGIDOS nunca é apagado de verdade, mesmo childless/sem uso —
    só inativado. Protege a automação (migrar_classificacao_grupo5_v1) mesmo num owner novo, onde
    ainda não há conta nenhuma classificada apontando pro nó."""
    c = _get_own_cc(db, owner_tipo, owner_id, cc_id)
    protegido = c.codigo in CENTRO_CUSTO_PROTEGIDOS
    if not protegido and not _cc_tem_filhos(db, c) and not _cc_tem_uso(db, c):
        db.delete(c)
        db.commit()
        return {"acao": "apagado", "id": cc_id}
    c.ativo = 0
    db.commit()
    out = {"acao": "inativado", "id": cc_id}
    if protegido:
        out["protegido"] = True
    return out


def classificar_contas_lote(db, owner_tipo, owner_id, itens):
    """Aplica Centro de Custo + Natureza em lote nas contas do owner. `itens` =
    [{codigo, centro_custo_codigo, natureza_custo}] — os dois últimos aceitam None/"" pra
    LIMPAR a classificação da conta. Valida TUDO antes de gravar qualquer item (tudo ou nada —
    uma linha ruim no meio da lista não deixa a classificação pela metade). Endpoint pronto,
    mas só é chamado depois da aprovação do usuário (Centro de Custo/Natureza, 2026-08-08) —
    a revisão da proposta acontece fora do banco (Artifact), não aqui."""
    contas = {c.codigo: c for c in db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    ccs = {c.codigo: c for c in db.query(CentroCusto).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    naturezas_validas = {slug for slug, _ in NATUREZA_CUSTO}
    resolvidos = []
    for item in itens or []:
        cod = item.get("codigo")
        conta = contas.get(cod)
        if conta is None:
            raise ValueError(f"conta inexistente: {cod}")
        cc_cod = (item.get("centro_custo_codigo") or "").strip() or None
        cc = None
        if cc_cod is not None:
            cc = ccs.get(cc_cod)
            if cc is None:
                raise ValueError(f"centro de custo inexistente: {cc_cod} (conta {cod})")
        nat = (item.get("natureza_custo") or "").strip() or None
        if nat is not None and nat not in naturezas_validas:
            raise ValueError(f"natureza inválida: {nat} (conta {cod})")
        resolvidos.append((conta, cc, nat))
    for conta, cc, nat in resolvidos:
        conta.centro_custo_id = cc.id if cc else None
        conta.natureza_custo = nat
    db.commit()
    return {"classificadas": len(resolvidos)}


# código da conta -> (código do centro de custo, slug de natureza) — as 59 contas do grupo 5,
# proposta aprovada por Marcelo e Juliana (Artifact de 2026-08-08, ver DEV_LOG Sessão 177).
# Frente 1 (spec 2026-08-25, DECIDIDO): mapa atualizado com os valores FINAIS, incorporando as
# correções que as migrações migrar_classificacao_grupo5_v2/v3 faziam por VALOR (não por origem).
# Um owner novo (banco zerado) nasce direto com o valor certo, sem depender de nenhuma correção
# rodando depois. As duas correções que ainda faltavam aqui quando o mapa foi atualizado: 5.2.06
# Combustível → fixo (era o default antigo que v3 corrigia) e 5.5.05 Perdas com Acordos
# Financeiros → variável (decisão nova, Frente 4 #8 — nunca teve migração própria).
# T2 (27/08/2026, revisão do banco): v2/v3 saíram do boot em 2026-08-25 e já tinham cumprido o
# papel em todos os ambientes — as duas funções (e os testes que só exercitavam elas) foram
# apagadas nesta revisão junto da correção final da semente: 5.6.10 no PLANO_PADRAO ainda dizia
# "Ajuste de Provisões" (nome antigo — a conta já existente no banco tinha virado "Ajustes de
# Reconciliação" na 0004, mas um owner novo nasceria com o nome velho).
CLASSIFICACAO_GRUPO5_V1 = {
    "5.1.01": ("1.2", "variavel"), "5.1.02": ("1.4", "variavel"),
    "5.2.01": ("1.3", "variavel"), "5.2.02": ("1.3", "variavel"), "5.2.03": ("1.3", "variavel"),
    "5.2.04": ("1.4", "fixo"),     "5.2.05": ("1.3", "variavel"), "5.2.06": ("1.4", "fixo"),
    "5.2.07": ("1.4", "variavel"), "5.2.08": ("1.4", "variavel"), "5.2.09": ("1.3", "variavel"),
    "5.2.10": ("1.4", "fixo"),     "5.2.12": ("3.1", "variavel"), "5.2.13": ("3.1", "variavel"),
    "5.3.01": ("2.1", "variavel"), "5.3.02": ("2.1", "variavel"), "5.3.03": ("4.3", "variavel"),
    "5.3.04": ("2.3", "variavel"), "5.3.05": ("2.1", "variavel"), "5.3.06": ("2.1", "fixo"),
    "5.3.07": ("2.3", "fixo"),     "5.3.08": ("2.3", "fixo"),     "5.3.09": ("2.3", "fixo"),
    "5.3.11": ("2.3", "fixo"),     "5.3.12": ("2.3", "variavel"), "5.3.13": ("2.1", "variavel"),
    "5.3.14": ("2.3", "fixo"),     "5.3.15": ("2.1", "variavel"), "5.3.16": ("4.3", "fixo"),
    "5.3.17": ("3.2", "variavel"), "5.3.18": ("3.2", "variavel"), "5.3.19": ("3.2", "variavel"),
    "5.3.21": ("2.1", "variavel"), "5.4.01": ("1.5", "fixo"),     "5.4.02": ("1.5", "fixo"),
    "5.4.03": ("1.5", "fixo"),     "5.4.04": ("4.2", "fixo"),     "5.4.05": ("4.3", "fixo"),
    "5.4.06": ("4.3", "fixo"),     "5.4.07": ("4.3", "fixo"),     "5.4.08": ("1.5", "fixo"),
    "5.4.09": ("1.5", "fixo"),     "5.4.10": ("4.2", "fixo"),     "5.4.11": ("4.3", "fixo"),
    "5.4.12": ("4.4", "fixo"),     "5.4.13": ("4.3", "fixo"),     "5.4.14": ("4.3", "fixo"),
    "5.4.15": ("4.3", "fixo"),     "5.4.16": ("4.3", "fixo"),     "5.4.17": ("4.5", "fixo"),
    "5.4.18": ("4.5", "fixo"),     "5.4.19": ("4.2", "fixo"),     "5.4.20": ("4.5", "fixo"),
    "5.5.01": ("4.3", "fixo"),     "5.5.02": ("4.3", "fixo"),     "5.5.03": ("4.3", "variavel"),
    "5.5.04": ("4.3", "variavel"), "5.5.05": ("4.3", "variavel"), "5.6.10": ("4.5", "variavel"),
}

# T4 (27/08/2026, revisão do banco): códigos de Centro de Custo que a automação resolve por
# CÓDIGO (nunca por id — cada owner tem sua própria árvore, com ids diferentes para o mesmo
# código; ver R9 em CLAUDE.md). migrar_classificacao_grupo5_v1 procura estes códigos em TODO
# boot para classificar contas do grupo 5 ainda sem centro de custo — se um deles for apagado
# (ex.: "1.3 Montagem"), a próxima conta nova/reclassificação automática do grupo fica sem
# destino. remover_centro_custo nunca deixa um destes ser apagado de verdade (só inativado); o
# código (diferente do nome) também nunca é editável — editar_centro_custo não aceita esse campo.
CENTRO_CUSTO_PROTEGIDOS = frozenset(cc_cod for cc_cod, _nat in CLASSIFICACAO_GRUPO5_V1.values())


def migrar_classificacao_grupo5_v1(db):
    """Aplica CLASSIFICACAO_GRUPO5_V1 em TODOS os owners — idempotente, só preenche
    centro_custo_id/natureza_custo que ainda estiverem None; uma classificação manual feita
    depois (classificar_contas_lote ou edição direta) nunca é sobrescrita. Roda no boot DEPOIS
    de backfill_centro_custo_todos_owners (precisa da árvore de Centro de Custo já semeada, pra
    achar os códigos "1.2"/"1.3"/etc.)."""
    owners = db.query(Conta.owner_tipo, Conta.owner_id).distinct().all()
    cc_setado = nat_setado = 0
    for ot, oid in owners:
        contas = {c.codigo: c for c in db.query(Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}
        ccs = {c.codigo: c for c in db.query(CentroCusto).filter_by(owner_tipo=ot, owner_id=oid).all()}
        for cod, (cc_cod, nat) in CLASSIFICACAO_GRUPO5_V1.items():
            conta = contas.get(cod)
            if conta is None:
                continue
            if conta.centro_custo_id is None and cc_cod in ccs:
                conta.centro_custo_id = ccs[cc_cod].id
                cc_setado += 1
            if conta.natureza_custo is None:
                conta.natureza_custo = nat
                nat_setado += 1
    db.commit()
    return {"centro_custo_setado": cc_setado, "natureza_setado": nat_setado}


def aplicar_gabarito_completo(db, owner_tipo, owner_id):
    """Garante, num UNICO owner, a arvore de centro de custo (`seed_centro_custo`), o plano de
    contas (`seed_plano`) e a classificacao do grupo 5 (`CLASSIFICACAO_GRUPO5_V1`) — idempotente,
    so' preenche o que faltar (mesma regra de `migrar_classificacao_grupo5_v1`: nunca sobrescreve
    `centro_custo_id`/`natureza_custo` ja setado, seja pelo proprio gabarito seja por
    reclassificacao manual).

    docs/db/TAREFA_CENTRO_CUSTO_2.md item 2: antes desta funcao, a arvore e o plano tinham
    seed-on-first-access (`listar_centros_custo`/`listar_contas`), mas a classificacao só' era
    aplicada por `migrar_classificacao_grupo5_v1`, chamada SO no boot do servidor — uma loja
    criada em runtime, cujo plano so' nasce quando alguem visita a tela, ficava com o grupo 5
    inteiro em NULL ate' o proximo restart. Esta funcao roda os 3 passos juntos, chamada tanto na
    CRIACAO da loja (main.py, `/api/admin/lojas` e `.../pdvs` — loja nasce classificada, sem
    esperar tela nem reboot) quanto nos endpoints de TELA `/api/financeiro/contas` e
    `/api/financeiro/centro-custo` (rede de seguranca pros owners que ja existiam antes desta
    mudanca). Deliberadamente NAO dentro de `listar_centros_custo`/`listar_contas`: essas duas
    tambem alimentam leitura pura (`relatorio_centro_custo`), que nao pode ter o efeito colateral
    de classificar conta sozinha so' por ser chamada.

    Retorna contagem de linhas criadas/atualizadas (`centro_custo_criado`, `conta_criada`,
    `centro_custo_setado`, `natureza_setado`) — usada por scripts/aplicar_gabarito.py pra
    reportar o que fez; os outros 2 pontos de entrada (main.py, migration) ignoram o retorno."""
    centro_custo_criado = seed_centro_custo(db, owner_tipo, owner_id)
    conta_criada = seed_plano(db, owner_tipo, owner_id)
    contas = {c.codigo: c for c in db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    ccs = {c.codigo: c for c in db.query(CentroCusto).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    cc_setado = nat_setado = 0
    for cod, (cc_cod, nat) in CLASSIFICACAO_GRUPO5_V1.items():
        conta = contas.get(cod)
        if conta is None:
            continue
        if conta.centro_custo_id is None and cc_cod in ccs:
            conta.centro_custo_id = ccs[cc_cod].id
            cc_setado += 1
        if conta.natureza_custo is None:
            conta.natureza_custo = nat
            nat_setado += 1
    if cc_setado or nat_setado:
        db.commit()
    return {
        "centro_custo_criado": centro_custo_criado, "conta_criada": conta_criada,
        "centro_custo_setado": cc_setado, "natureza_setado": nat_setado,
    }


def varrer_orfaos_gabarito(db):
    """Remove `conta`/`centro_custo` cujo owner nao existe (mais) em `redes`/`lojas` —
    docs/db/TAREFA_CENTRO_CUSTO_2.md item 7. `c1ab3f8007c4` grava gabarito incondicional pra
    rede,1/loja,1/loja,3, mesmo num ambiente onde algum desses owners nao existe de verdade
    (ex.: Integracao, so' tem loja,1) — owner e' polimorfico, sem FK que acuse a orfandade
    sozinha. Rodar DEPOIS de `aplicar_gabarito_completo` em todo owner (scripts/
    aplicar_gabarito.py) e' o ponto do procedimento em que a verdade sobre os owners ja esta
    no banco (redes/lojas restauradas — passo 2 de RESTAURAR.md).

    So remove o que NAO tem referencia de `lancamento` nem de outra linha de `conta`/
    `centro_custo` que va sobreviver — orfa com movimento e' problema de DADO, nao de gabarito,
    apagar seria pior; fica RETIDA e reportada. Converge por remocao iterativa (peeling): um
    no so fica liberado depois que TODO filho que aponta pra ele (via `pai_id`, ou `conta.
    centro_custo_id`) ja foi removido — mesma logica que a FK (`RESTRICT`/sem `ondelete`)
    aplicaria linha a linha, só que decidida aqui, de uma vez, pra poder reportar o motivo.

    Retorna contagem (encontrados/removidos/retidos, por tabela) e a lista dos retidos com
    motivo — nunca lança exceção por conta/nó retido; isso e' o caminho normal, nao uma falha."""
    owners_validos = {("rede", r.id) for r in db.query(Rede).all()} | \
                     {("loja", l.id) for l in db.query(Loja).all()}

    contas = {r.id: r for r in db.query(Conta).all()}
    ccs = {r.id: r for r in db.query(CentroCusto).all()}

    orfaos_conta = {cid for cid, r in contas.items() if (r.owner_tipo, r.owner_id) not in owners_validos}
    orfaos_cc = {ccid for ccid, r in ccs.items() if (r.owner_tipo, r.owner_id) not in owners_validos}

    lanc_refs = set()
    for deb, cred in db.query(Lancamento.conta_debito_id, Lancamento.conta_credito_id).all():
        lanc_refs.add(deb)
        lanc_refs.add(cred)

    deletar_conta = set(orfaos_conta)
    deletar_cc = set(orfaos_cc)
    mudou = True
    while mudou:
        mudou = False
        for cid in list(deletar_conta):
            if cid in lanc_refs:
                deletar_conta.discard(cid)
                mudou = True
                continue
            if any(r.pai_id == cid for oid, r in contas.items() if oid not in deletar_conta):
                deletar_conta.discard(cid)
                mudou = True
        for ccid in list(deletar_cc):
            referenciada_por_conta = any(
                r.centro_custo_id == ccid for oid, r in contas.items() if oid not in deletar_conta)
            referenciada_por_filho = any(
                r.pai_id == ccid for oid, r in ccs.items() if oid not in deletar_cc)
            if referenciada_por_conta or referenciada_por_filho:
                deletar_cc.discard(ccid)
                mudou = True

    retidos_conta, retidos_cc = [], []
    for cid in sorted(orfaos_conta - deletar_conta):
        r = contas[cid]
        motivo = "referenciada por lancamento" if cid in lanc_refs else \
            "conta filha (pai_id) ainda existe"
        retidos_conta.append({"id": cid, "owner_tipo": r.owner_tipo, "owner_id": r.owner_id,
                               "codigo": r.codigo, "motivo": motivo})
    for ccid in sorted(orfaos_cc - deletar_cc):
        r = ccs[ccid]
        referenciada_por_conta = any(
            rr.centro_custo_id == ccid for oid, rr in contas.items() if oid not in deletar_conta)
        motivo = "conta classificada nela" if referenciada_por_conta else \
            "centro de custo filho ainda existe"
        retidos_cc.append({"id": ccid, "owner_tipo": r.owner_tipo, "owner_id": r.owner_id,
                            "nome": r.nome, "motivo": motivo})

    if deletar_conta:
        db.query(Conta).filter(Conta.id.in_(deletar_conta)).delete(synchronize_session=False)
    if deletar_cc:
        db.query(CentroCusto).filter(CentroCusto.id.in_(deletar_cc)).delete(synchronize_session=False)
    if deletar_conta or deletar_cc:
        db.commit()

    return {
        "encontrados_conta": len(orfaos_conta), "encontrados_centro_custo": len(orfaos_cc),
        "removidos_conta": len(deletar_conta), "removidos_centro_custo": len(deletar_cc),
        "retidos_conta": retidos_conta, "retidos_centro_custo": retidos_cc,
    }


def retrato_classificacao_grupo5(db, owner_tipo, owner_id):
    """Frente 0 (spec 2026-08-25, pré-requisito das demais): retrato do estado REAL do banco
    pras contas do grupo 5 — o que está gravado agora (não o que o mapa em código diz que
    DEVERIA estar), com uma coluna comparando contra `CLASSIFICACAO_GRUPO5_V1`. `diverge=True`
    não é necessariamente um erro — pode ser reclassificação manual legítima; é só o sinal pra
    revisão humana (Marcelo/Juliana) saber onde olhar. Contas fora do mapa (`sem_mapa=True`,
    ex.: alguma criada depois das 59 originais) não contam como divergentes — não há
    "esperado" pra comparar."""
    contas = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, grupo=5)
                .order_by(Conta.codigo).all())
    ccs_por_id = {c.id: c for c in db.query(CentroCusto)
                  .filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    itens = []
    for c in contas:
        cc_atual = ccs_por_id.get(c.centro_custo_id)
        esperado = CLASSIFICACAO_GRUPO5_V1.get(c.codigo)
        cc_esperado_cod, nat_esperada = esperado if esperado else (None, None)
        cc_atual_cod = cc_atual.codigo if cc_atual else None
        diverge = esperado is not None and (cc_atual_cod != cc_esperado_cod
                                            or c.natureza_custo != nat_esperada)
        itens.append({
            "codigo": c.codigo, "nome": c.nome, "ativa": bool(c.ativa),
            "centro_custo_atual_codigo": cc_atual_cod,
            "centro_custo_atual_nome": cc_atual.nome if cc_atual else None,
            "natureza_atual": c.natureza_custo,
            "centro_custo_esperado_codigo": cc_esperado_cod,
            "natureza_esperada": nat_esperada,
            "sem_mapa": esperado is None,
            "diverge": diverge,
        })
    return itens


# ── Livro de Lançamentos (sub-projeto #2) ────────────────────────────────────
def _lanc_serial(l):
    return {"id": l.id, "data": l.data.isoformat() if l.data else None, "valor": l.valor,
            "conta_debito_id": l.conta_debito_id, "conta_credito_id": l.conta_credito_id,
            "projeto_id": l.projeto_id, "origem": l.origem, "historico": l.historico, "ref": l.ref}


def lancar(db, owner_tipo, owner_id, conta_debito_id, conta_credito_id, valor,
           data=None, projeto_id=None, origem="manual", historico="", ref=None,
           motivo=None, ia_sugestao=None):
    """Registra um lançamento de partida dobrada. Débito e crédito devem ser contas
    ANALÍTICAS ativas do mesmo owner; valor > 0; contas distintas."""
    if valor is None or float(valor) <= 0:
        raise ValueError("valor deve ser > 0")
    if conta_debito_id == conta_credito_id:
        raise ValueError("débito e crédito não podem ser a mesma conta")
    cd = _get_own(db, owner_tipo, owner_id, conta_debito_id)
    cc = _get_own(db, owner_tipo, owner_id, conta_credito_id)
    for c in (cd, cc):
        if c.tipo != "analitica":
            raise ValueError("conta %s é sintética; só analítica recebe lançamento" % c.codigo)
        if not c.ativa:
            raise ValueError("conta %s está inativa" % c.codigo)
    # ACHADO-48 (DECIDIDO 02/09): a competência do lançamento é a hora de PAREDE do fuso do
    # dono do livro (`agora_no_fuso`), nunca `datetime.utcnow()` — era daqui que o defeito
    # nascia (venda às 21h30 em Brasília escriturada em UTC, um dia/mês adiante).
    lan = Lancamento(owner_tipo=owner_tipo, owner_id=owner_id,
                     data=data or agora_no_fuso(db, owner_tipo, owner_id),
                     conta_debito_id=conta_debito_id, conta_credito_id=conta_credito_id,
                     valor=round(float(valor), 2), projeto_id=projeto_id, origem=origem,
                     historico=historico or "", ref=ref, motivo=motivo, ia_sugestao=ia_sugestao)
    db.add(lan)
    db.commit()
    return _lanc_serial(lan)


def lancamento_por_ref(db, owner_tipo, owner_id, ref):
    """Idempotência do wiring: retorna o serial do lançamento com este `ref` (ou None)."""
    if not ref:
        return None
    l = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, ref=ref).first()
    return _lanc_serial(l) if l else None


def _filtra_periodo(q, ini, fim):
    if ini:
        q = q.filter(Lancamento.data >= ini)
    if fim:
        q = q.filter(Lancamento.data <= fim)
    return q


def saldo_conta(db, owner_tipo, owner_id, conta_id, ini=None, fim=None):
    """Saldo da conta na natureza dela (devedora: D−C; credora: C−D). Agregado no banco."""
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    deb, cred = _totais_conta(db, owner_tipo, owner_id, conta_id, ini, fim)
    return round(deb - cred if c.natureza == "devedora" else cred - deb, 2)


def razao(db, owner_tipo, owner_id, conta_id, ini=None, fim=None):
    """Extrato (razão) de uma conta: linhas D/C com saldo corrido na natureza da conta."""
    from sqlalchemy import or_
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).filter(
        or_(Lancamento.conta_debito_id == conta_id, Lancamento.conta_credito_id == conta_id))
    lans = _filtra_periodo(q, ini, fim).order_by(Lancamento.data, Lancamento.id).all()
    saldo = 0.0
    linhas = []
    for l in lans:
        deb = l.conta_debito_id == conta_id
        mov = l.valor if (deb == (c.natureza == "devedora")) else -l.valor
        saldo = round(saldo + mov, 2)
        linhas.append({"id": l.id, "data": l.data.isoformat() if l.data else None,
                       "dc": "D" if deb else "C", "valor": l.valor,
                       "contrapartida_id": l.conta_credito_id if deb else l.conta_debito_id,
                       "projeto_id": l.projeto_id, "historico": l.historico, "saldo": saldo})
    return {"conta_id": conta_id, "codigo": c.codigo, "nome": c.nome, "natureza": c.natureza,
            "linhas": linhas, "saldo_final": saldo}


CONTA_CAIXA_CODIGO = "1.1.01"   # raiz "Caixa/Bancos" — Fluxo de Caixa soma ela + filhos (2026-08-07)


def contas_caixa(db, owner_tipo, owner_id):
    """Contas ANALÍTICAS de caixa/banco: a raiz 1.1.01 (se ainda for folha — nunca foi
    desmembrada) + qualquer filho criado via 'Adicionar Conta' (ex.: Banco Itaú, Banco Inter).
    Mesmo padrão de _mov (prefixo + filhos), mas devolvendo as contas em vez do total."""
    seed_plano(db, owner_tipo, owner_id)
    raiz = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                                      codigo=CONTA_CAIXA_CODIGO).first())
    if raiz is None:
        return []
    todas = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()
    return [c for c in todas
            if c.tipo == "analitica" and (c.id == raiz.id or c.codigo.startswith(raiz.codigo + "."))]


def fluxo_caixa(db, owner_tipo, owner_id, conta_ids, ini, fim):
    """Fluxo de caixa dia a dia (2026-08-07): uma linha por dia de [ini,fim] (inclusive, mesmo
    sem movimento) com crédito/débito/saldo — soma de `conta_ids` (uma conta específica, ou
    TODAS as de contas_caixa() pro consolidado). Saldo inicial = saldo agregado das contas até a
    véspera de `ini`. Mesma convenção de sinal do razão: débito numa conta devedora (Caixa é
    Ativo) É dinheiro ENTRANDO; crédito é dinheiro SAINDO."""
    from datetime import timedelta, datetime as _dt, time as _time
    from sqlalchemy import or_
    if not conta_ids:
        return {"saldo_inicial": 0.0, "dias": [], "saldo_final": 0.0}
    contas = [_get_own(db, owner_tipo, owner_id, cid) for cid in conta_ids]
    saldo_ini = 0.0
    if ini:
        vespera = _dt.combine(ini - timedelta(days=1), _time.max)
        for c in contas:
            deb, cred = _totais_conta(db, owner_tipo, owner_id, c.id, None, vespera)
            saldo_ini += (deb - cred) if c.natureza == "devedora" else (cred - deb)
    fim_dt = _dt.combine(fim, _time.max) if fim else None
    ini_dt = _dt.combine(ini, _time.min) if ini else None
    q = (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
           .filter(or_(Lancamento.conta_debito_id.in_(conta_ids),
                       Lancamento.conta_credito_id.in_(conta_ids))))
    lans = _filtra_periodo(q, ini_dt, fim_dt).all()
    por_dia = {}
    for l in lans:
        dia = (l.data.date() if hasattr(l.data, "date") else l.data).isoformat()
        d = por_dia.setdefault(dia, {"credito": 0.0, "debito": 0.0})
        if l.conta_debito_id in conta_ids:
            d["debito"] += l.valor
        if l.conta_credito_id in conta_ids:
            d["credito"] += l.valor
    dias, saldo = [], round(saldo_ini, 2)
    cur = ini
    while cur and fim and cur <= fim:
        chave = cur.isoformat()
        mov = por_dia.get(chave, {"credito": 0.0, "debito": 0.0})
        cr, db_ = round(mov["credito"], 2), round(mov["debito"], 2)
        saldo = round(saldo + db_ - cr, 2)
        dias.append({"data": chave, "credito": cr, "debito": db_, "saldo": saldo})
        cur += timedelta(days=1)
    return {"saldo_inicial": round(saldo_ini, 2), "dias": dias, "saldo_final": saldo}


def listar_lancamentos(db, owner_tipo, owner_id, projeto_id=None, ini=None, fim=None, conta_id=None, limite=500):
    """`conta_id`: filtra lançamentos onde a conta aparece como débito OU crédito — "todos os
    lançamentos associados àquela conta" (2026-08-09, filtro da aba Lançamentos Contábeis)."""
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    if projeto_id:
        q = q.filter(Lancamento.projeto_id == projeto_id)
    if conta_id:
        from sqlalchemy import or_
        q = q.filter(or_(Lancamento.conta_debito_id == conta_id, Lancamento.conta_credito_id == conta_id))
    q = _filtra_periodo(q, ini, fim).order_by(Lancamento.data.desc(), Lancamento.id.desc())
    return [_lanc_serial(l) for l in q.limit(limite).all()]


def auditoria_contabil(db, owner_tipo, owner_id, projeto_id):
    """Relatório de Auditoria Contábil do PROJETO — VIEW derivada do razão (fonte única, nada novo
    persistido): todos os lançamentos do projeto em ordem CRONOLÓGICA, cada um com conta débito/crédito
    (código+nome), valor, origem e histórico. Inclui os estornos (devolução/cancelamento/ajuste de AF),
    que carregam origem própria. Retorna [{id, data, debito:{cod,nome}, credito:{cod,nome}, valor,
    origem, historico, ref}]."""
    cmap = {c.id: (c.codigo, c.nome) for c in
            db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    lans = (db.query(Lancamento)
            .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, projeto_id=projeto_id)
            .order_by(Lancamento.data, Lancamento.id).all())
    out = []
    for l in lans:
        dc = cmap.get(l.conta_debito_id, ("?", ""))
        cc = cmap.get(l.conta_credito_id, ("?", ""))
        out.append({"id": l.id, "data": l.data.isoformat() if l.data else None,
                    "debito": {"cod": dc[0], "nome": dc[1]}, "credito": {"cod": cc[0], "nome": cc[1]},
                    "valor": l.valor, "origem": l.origem, "historico": l.historico, "ref": l.ref})
    return out


# ── Motor evento → lançamento (sub-projeto #3) ───────────────────────────────
# As 5 regras do .docx §5. Contas resolvidas por CÓDIGO (estável: rename não muda o
# código; reparent/recodificar foi adiado no #1). (codigo_debito, codigo_credito, historico)
EVENTOS = {
    # FASE D2: constituição das 10 provisões no CONTRATO como ATIVO DIFERIDO (1.1.06.0X) × Provisão
    # (2.1.04.0X), SEM tocar a DRE. A despesa (5.6.0X, ou 5.1.01 p/ a fábrica) só é reconhecida na NF-e
    # (matching pleno). Espelha o padrão dos impostos (1.1.05 × 2.1.04.13). [antes: débito direto em 5.6.0X]
    "fechamento_venda_montagem":    ("1.1.06.02", "2.1.04.02", "Constituição — Provisão de Montagem (ativo diferido)"),
    "fechamento_venda_assistencia": ("1.1.06.05", "2.1.04.05", "Constituição — Provisão de Assistência Técnica (ativo diferido)"),
    "fechamento_venda_garantia":    ("1.1.06.03", "2.1.04.03", "Constituição — Provisão de Garantia (ativo diferido)"),
    "fechamento_venda_frete_fabrica":       ("1.1.06.07", "2.1.04.07", "Constituição — Provisão de Frete de Fábrica (ativo diferido)"),
    "fechamento_venda_frete_local":         ("1.1.06.08", "2.1.04.08", "Constituição — Provisão de Frete Local (ativo diferido)"),
    "fechamento_venda_insumos":             ("1.1.06.09", "2.1.04.09", "Constituição — Provisão de Insumos Locais (ativo diferido)"),
    "fechamento_venda_com_medidor":         ("1.1.06.10", "2.1.04.10", "Constituição — Provisão de Comissão de Medidor (ativo diferido)"),
    "fechamento_venda_com_proj_exec":       ("1.1.06.11", "2.1.04.11", "Constituição — Provisão de Comissão de Projeto/Executivo (ativo diferido)"),
    "fechamento_venda_retencao_com_vendas": ("1.1.06.12", "2.1.04.12", "Constituição — Provisão de Retenção de Comissão de Vendas (ativo diferido)"),
    "fechamento_venda_custo_fabrica":       ("1.1.06.06", "2.1.04.06", "Constituição — Provisão de Custo de Fábrica (ativo diferido)"),
    # FASE A (resultado da venda): custos adicionais constituídos como ativo diferido × provisão, sem tocar a DRE
    "fechamento_venda_com_arq":  ("1.1.06.15", "2.1.04.15", "Constituição — Provisão de Comissão de Arquiteto (ativo diferido)"),
    "fechamento_venda_pro_fid":  ("1.1.06.16", "2.1.04.16", "Constituição — Provisão de Programa de Fidelidade (ativo diferido)"),
    "fechamento_venda_cust_via": ("1.1.06.17", "2.1.04.17", "Constituição — Provisão de Custo de Viagem (ativo diferido)"),
    "fechamento_venda_brinde":   ("1.1.06.18", "2.1.04.18", "Constituição — Provisão de Brinde (ativo diferido)"),
    "fechamento_venda_cust_esp": ("1.1.06.20", "2.1.04.20", "Constituição — Provisão de Custo Especial (ativo diferido)"),
    # 2026-08-12: Comissão Administrativa (previsão de comissionamento do staff da loja — diretores/
    # gerentes) passa a ser provisionada como as demais, em vez de ficar só na visão gerencial da
    # negociação. Efetivada/resolvida pelo MESMO mecanismo genérico das outras (efetivar_provisao/
    # resolver_saldo_provisao na Reconciliação) — despesa formal em 5.3.03 (já existia no plano).
    "fechamento_venda_com_adm":  ("1.1.06.21", "2.1.04.21", "Constituição — Provisão de Comissão Administrativa (ativo diferido)"),
    # FASE B (resultado financeiro) — ramo FINANCEIRA: despesa financeira diferida (constituída no contrato)
    "fechamento_venda_custo_financeiro":     ("1.1.06.19", "2.1.04.19", "Constituição — Provisão de Custo Financeiro (ativo diferido)"),
    "reconhecimento_despesa_custo_financeiro": ("5.5.04", "1.1.06.19", "Reconhecimento da despesa financeira (baixa do ativo diferido)"),
    "reconhecimento_antecipacao":              ("5.5.03", "1.1.06.19", "Reconhecimento do custo de antecipação bancária (baixa do ativo diferido)"),
    # FASE B (resultado financeiro) — ramo LOJA (financiamento direto, capital próprio, SEM despesa):
    "constituir_juros_direto":       ("1.1.07", "2.1.07", "Financiamento direto — juros a apropriar (recebível × receita diferida)"),
    "receber_parcela_direto":        ("1.1.01", "1.1.07", "Financiamento direto — recebimento de parcela (baixa do recebível de juros)"),
    "apropriar_receita_financeira":  ("2.1.07", "4.4.03", "Financiamento direto — apropriação da receita financeira (competência)"),
    "reverter_juros_direto":         ("2.1.07", "1.1.07", "Estorno de juros a apropriar (troca de ramo do custo financeiro na AF)"),
    # FASE D2: matching pleno na NF-e — reconhece a DESPESA de cada rubrica (5.6.0X, ou 5.1.01 p/ a fábrica)
    # × baixa do ativo diferido (1.1.06.0X). A Provisão (2.1.04.0X) SOBREVIVE — é paga/reconciliada depois.
    # Formalismo (Sessão 109): o reconhecimento debita a conta FORMAL da rubrica —
    # Custo de Serviço (5.2.x), CMV (frete de fábrica) ou Despesas Comerciais (comissões).
    "reconhecimento_despesa_montagem":            ("5.2.01", "1.1.06.02", "Reconhecimento de despesa na NF-e — Montagem"),
    "reconhecimento_despesa_garantia":            ("5.2.12", "1.1.06.03", "Reconhecimento de despesa na NF-e — Garantia"),
    "reconhecimento_despesa_assistencia":         ("5.2.13", "1.1.06.05", "Reconhecimento de despesa na NF-e — Assistência Técnica"),
    "reconhecimento_despesa_frete_fabrica":       ("5.1.02", "1.1.06.07", "Reconhecimento de despesa na NF-e — Frete de Fábrica"),
    "reconhecimento_despesa_frete_local":         ("5.2.08", "1.1.06.08", "Reconhecimento de despesa na NF-e — Frete Local"),
    "reconhecimento_despesa_insumos":             ("5.2.09", "1.1.06.09", "Reconhecimento de despesa na NF-e — Insumos Locais"),
    "reconhecimento_despesa_com_medidor":         ("5.3.18", "1.1.06.10", "Reconhecimento de despesa na NF-e — Comissão de Medidor"),
    "reconhecimento_despesa_com_proj_exec":       ("5.3.19", "1.1.06.11", "Reconhecimento de despesa na NF-e — Comissão de Projeto/Executivo"),
    # 2026-08-08 (Centro de Custo/Natureza): 5.3.20 foi removida do plano — a retenção de
    # comissão de vendas é conceitualmente uma variação de comissão de vendedor, então passa a
    # debitar 5.3.01 (mesma conta usada por "comissao_venda"/folha_variavel).
    "reconhecimento_despesa_retencao_com_vendas": ("5.3.01", "1.1.06.12", "Reconhecimento de despesa na NF-e — Retenção de Comissão de Vendas"),
    "reconhecimento_despesa_custo_fabrica":       ("5.1.01", "1.1.06.06", "CMV Fábrica — reconhecimento na NF-e (baixa do ativo diferido)"),
    "reconhecimento_despesa_outros_fornecedores": ("5.1.01", "1.1.06.14", "CMV Outros Fornecedores — reconhecimento na NF-e (baixa do ativo diferido)"),
    # FASE A: matching dos custos adicionais na NF-e — despesa comercial × baixa do ativo diferido
    "reconhecimento_despesa_com_arq":  ("5.3.15", "1.1.06.15", "Reconhecimento de despesa na NF-e — Comissão de Arquiteto"),
    "reconhecimento_despesa_pro_fid":  ("5.3.04", "1.1.06.16", "Reconhecimento de despesa na NF-e — Programa de Fidelidade"),
    "reconhecimento_despesa_cust_via": ("5.3.14", "1.1.06.17", "Reconhecimento de despesa na NF-e — Custo de Viagem"),
    "reconhecimento_despesa_brinde":   ("5.3.12", "1.1.06.18", "Reconhecimento de despesa na NF-e — Brinde"),
    "reconhecimento_despesa_cust_esp": ("5.3.17", "1.1.06.20", "Reconhecimento de despesa na NF-e — Custo Especial"),
    "reconhecimento_despesa_com_adm":  ("5.3.03", "1.1.06.21", "Reconhecimento de despesa — Comissão Administrativa (efetivação)"),
    # Impostos = PROVISÃO (Tipo D). CONTRATO: passivo nasce SEM tocar a DRE — ativo diferido (1.1.05) ×
    # Provisão de Impostos (2.1.04.13). EMISSÃO (proporcional Merc/Serv): a dedução entra na DRE
    # (4.3.01 × baixa do ativo 1.1.05) e a obrigação fiscal real crystalliza (2.1.04.13 × 2.1.03).
    "fechamento_venda_impostos":            ("1.1.05", "2.1.04.13", "Provisão de Impostos — reserva no contrato (ativo diferido)"),
    "faturamento_impostos_deducao":         ("4.3.01", "1.1.05",    "Impostos — dedução da receita na emissão (baixa do ativo diferido)"),
    "faturamento_impostos_obrigacao":       ("2.1.04.13", "2.1.03", "Impostos — efetivação da obrigação fiscal na emissão"),
    # ACHADO-04 (docs/db/PLANO_AJUSTES.md): o evento "custo_financeiro" (5.5.03×2.1.05) nasceu
    # marcado [CONFIRMAR CONTADOR] e nunca foi confirmado nem chamado em produção — modelava o
    # Parcelamento Loja como financiamento de terceiro (passivo a pagar). Pela regra do deságio
    # (quem financia é a própria loja → receita financeira dela), removido em 2026-08-29. O
    # mecanismo certo é `_RAMO_CFIN_EVENTO`/`fechamento_venda_custo_financeiro`
    # (1.1.06.19×2.1.04.19, ramo financeira) e `constituir_juros_direto` (1.1.07×2.1.07, ramo
    # loja) — nenhum dos dois usa 2.1.05. A conta 2.1.05 fica no catálogo (PLANO_PADRAO): volta a
    # fazer sentido se o Parcelamento Loja/Total Flex algum dia for fundeado por terceiro.
    # Ciclo de caixa
    "faturamento":                  ("1.1.02", "4.1.01",    "Faturamento (NF-e emitida)"),
    "recebimento":                  ("1.1.01", "1.1.02",    "Recebimento do cliente"),
    # ACHADO-05 (docs/db/PLANO_AJUSTES.md): o evento "pagamento_comissao" (2.1.04.01×1.1.01) era
    # uma das 5 regras fundacionais do motor (.docx §5), mas nunca foi chamado em produção — só
    # por teste. Superado pelo caminho da Folha (mod_folha.pagar, comissão de venda via
    # 2.1.04.12/efetivar_provisao). Removido em 2026-08-29; medição confirmou que 2.1.04.12 não
    # acumula dois conceitos (é resolução única da provisão constituída na assinatura — ver
    # mod_folha.py:6-13). A conta 2.1.04.01 fica no catálogo (PLANO_PADRAO), pelo mesmo motivo do
    # 2.1.05 acima.
    # Execução — reverte a provisão respectiva: Provisão (2.1.04.x) × Caixa/Fornecedor
    "execucao_montagem":            ("2.1.04.02", "1.1.01",  "Execução da montagem (baixa da provisão)"),
    "execucao_assistencia":         ("2.1.04.05", "1.1.01",  "Execução de assistência técnica (baixa da provisão)"),
    "execucao_reparo_garantia":     ("2.1.04.03", "1.1.01",  "Execução de reparo em garantia (baixa da provisão)"),
    # Caso de Assistência — tipo de custo Paga: nova venda ao cliente, sem tocar provisão (v7 §6)
    "venda_assistencia":            ("1.1.02", "4.1.02",    "Venda de assistência (caso Paga — cobrança do cliente)"),
    # ── FASE B2: Adiantamento de Clientes + receita segmentada (Mercadoria/Serviço) + CMV=CFO ──
    # Recebimento ANTES do documento fiscal: dinheiro entra como PASSIVO (obrigação de entregar).
    # FASE D2: contrato registra a venda CHEIA (Val_Cont) em Receita a Realizar (passivo) contra Contas a
    # Receber (ativo); a NF-e depois debita 2.1.06 × 4.1.01/4.2.01 (fato gerador). Não toca a DRE.
    "registro_venda_contrato":      ("1.1.02", "2.1.06",    "Registro da venda no contrato — Receita a Realizar"),
    # Recebimento (entrada + parcelas Parcelamento Loja/Aymoré) abate Contas a Receber, não a Receita a Realizar.
    "recebimento_venda":            ("1.1.01", "1.1.02",    "Recebimento do cliente (abate Contas a Receber)"),
    # Não-recebimento (2026-08-07): o cliente não pagou na data prevista — duas contrapartidas.
    # Reclassificação (dúvida sobre o recebimento, SEM tocar a DRE — troca de ativo por ativo, não é
    # perda): move o saldo de Contas a Receber "normal" pra Recebíveis Duvidosos.
    # Nome curto de propósito: `origem` do Lancamento é VARCHAR(30) na base já em produção (o model
    # declara String(64), mas colunas de bases antigas nunca foram alteradas — achado ao vivo
    # 2026-08-07, StringDataRightTruncation). "reclassificar_recebivel_duvidoso" (32) estourava.
    "recebivel_duvidoso":              ("1.1.10", "1.1.02", "Reclassificação — recebível duvidoso"),
    # Se o dinheiro afinal chegar depois de já estar em Duvidosos, baixa de lá em vez de 1.1.02.
    "recebimento_venda_duvidoso":       ("1.1.01", "1.1.10", "Recebimento do cliente (baixa de Recebível Duvidoso)"),
    # Faturamento SEGMENTADO (B1): Mercadoria → 4.1.01 (NF-e) · Serviço → 4.2.01 (NFS-e). NUNCA lançar
    # estes 4 direto no wiring — sempre via faturar_segmento() (split adiantado/a-receber + idempotência).
    "faturamento_mercadoria_adiantado": ("2.1.06", "4.1.01", "Faturamento mercadoria (NF-e) — baixa de adiantamento"),
    "faturamento_mercadoria_a_receber": ("1.1.02", "4.1.01", "Faturamento mercadoria (NF-e) — a receber"),
    "faturamento_servico_adiantado":    ("2.1.06", "4.2.01", "Faturamento serviço (NFS-e) — baixa de adiantamento"),
    "faturamento_servico_a_receber":    ("1.1.02", "4.2.01", "Faturamento serviço (NFS-e) — a receber"),
    # FASE D2: o CMV da fábrica deixou de ser um evento próprio no faturamento (faturamento_cmv, retirado).
    # Agora o passivo 2.1.04.06 nasce no CONTRATO (fechamento_venda_custo_fabrica) e o CMV é reconhecido na
    # NF-e via matching pleno (reconhecimento_despesa_custo_fabrica: 5.1.01 × baixa do ativo 1.1.06.06).
    # Baixa do passivo com a fábrica ao pagar: passivo × ativo, não toca o resultado.
    "pagamento_fabrica":            ("2.1.04.06", "1.1.01", "Pagamento à fábrica (baixa da Provisão de Custo de Fábrica)"),
    # ── Ajustes Excepcionais de Fábrica (spec 2026-07-21) ─────────────────────────────────────
    # Implantação de saldos: eventos PASSADOS entram pelo PL (CPC 23), nunca pela DRE corrente.
    "implantacao_credito_fabrica":  ("1.1.08", "3.5",       "Implantação de crédito com a fábrica (ajuste de exercícios anteriores)"),
    "implantacao_divida_fabrica":   ("3.5", "2.1.08",       "Implantação de dívida com a fábrica (ajuste de exercícios anteriores)"),
    # Aplicações na venda (consumir_saldo — o custo econômico NÃO muda; ajustes de CUSTO usam
    # ajustar_provisao_delta). Desconto: paga-se menos à fábrica; crédito (ou conta corrente
    # intercompany, SÓ no razão da compradora) baixa. Acréscimo: o a-pagar sobe casando com a
    # NF-e; a dívida antiga baixa. DRE intocada nos três.
    "desconto_excepcional_fabrica":      ("2.1.04.06", "1.1.08", "Desconto excepcional — consumo de crédito com a fábrica"),
    "desconto_excepcional_intercompany": ("2.1.04.06", "2.1.09", "Desconto excepcional — crédito de loja irmã (conta corrente a pagar)"),
    "acrescimo_excepcional_fabrica":     ("2.1.08", "2.1.04.06", "Acréscimo excepcional — amortização de dívida com a fábrica"),
    # Acerto periódico consolidado: SÓ no razão da credora (venda de uma loja nunca lança na outra)
    # VESTIGIAL (revisão 2026-07-21): o fluxo de acerto foi eliminado; o par 1.1.09×1.1.08 vive
    # na TRANSFERÊNCIA manual entre acordos (endpoint /movimento). Mantido por histórico de refs.
    "acerto_acordo_intercompany":   ("1.1.09", "1.1.08",    "Acerto do acordo — consumo das lojas do grupo (consolidado por período)"),
    # Liquidação financeira da conta corrente: cada loja lança a SUA ponta
    "liquidacao_conta_corrente_devedora": ("2.1.09", "1.1.01", "Liquidação da conta corrente com lojas do grupo (pagamento)"),
    "liquidacao_conta_corrente_credora":  ("1.1.01", "1.1.09", "Liquidação da conta corrente com lojas do grupo (recebimento)"),
    # Encerramento com resíduo: baixa espelho da implantação (× 3.5)
    "baixa_credito_fabrica":        ("3.5", "1.1.08",       "Baixa de resíduo de crédito com a fábrica (encerramento do acordo)"),
    "baixa_divida_fabrica":         ("2.1.08", "3.5",       "Baixa de resíduo de dívida com a fábrica (encerramento do acordo)"),
    # ── Acordos Financeiros (revisão 2026-07-21): contrapartes empresa/banco + movimentos ────
    "implantacao_credito_empresa":  ("1.1.09", "3.5",       "Implantação de crédito com empresa (ajuste de exercícios anteriores)"),
    "implantacao_divida_empresa":   ("3.5", "2.1.09",       "Implantação de dívida com empresa (ajuste de exercícios anteriores)"),
    "implantacao_divida_banco":     ("3.5", "2.1.10",       "Implantação de saldo de empréstimo bancário pré-existente"),
    "captacao_emprestimo":          ("1.1.01", "2.1.10",    "Captação de empréstimo bancário (dinheiro entra no caixa)"),
    "desconto_excepcional_credito_empresa": ("2.1.04.06", "1.1.09", "Desconto excepcional — consumo de crédito com empresa"),
    "recebimento_credito_fabrica":  ("1.1.01", "1.1.08",    "Recebimento de crédito com a fábrica (em dinheiro)"),
    "pagamento_divida_fabrica_caixa": ("2.1.08", "1.1.01",  "Pagamento de dívida com a fábrica (em dinheiro)"),
    "pagamento_emprestimo":         ("2.1.10", "1.1.01",    "Pagamento de empréstimo bancário"),
    "atualizacao_divida_fabrica":   ("5.5.02", "2.1.08",    "Atualização (juros/encargos) da dívida com a fábrica"),
    "atualizacao_divida_empresa":   ("5.5.02", "2.1.09",    "Atualização (juros/encargos) da dívida com empresa"),
    "atualizacao_emprestimo":       ("5.5.02", "2.1.10",    "Atualização (juros/encargos) do empréstimo bancário"),
    # Revisão 2026-07-22: juros pagos DIRETO no ato do pagamento (nominal + juros separados)
    "pagamento_juros_acordo":       ("5.5.02", "1.1.01",    "Pagamento de juros/encargos de acordo financeiro"),
    # FASE D: pagamento da obrigação com fornecedor (baixa de Fornecedores a Pagar) — passivo × ativo
    "pagamento_fornecedor":         ("2.1.01", "1.1.01",   "Pagamento a fornecedor (baixa de Fornecedores a Pagar)"),
    # Folha de Pagamento (v10 §2.1): despesa nas contas 5.3 existentes × Caixa (sem conta nova)
    "folha_fixa":                   ("5.3.06", "1.1.01",    "Folha — parte fixa (Salários de Vendas)"),
    "folha_variavel":               ("5.3.01", "1.1.01",    "Folha — parte variável (Comissão de Vendedor)"),
    "folha_beneficios":             ("5.3.16", "1.1.01",    "Folha — benefícios (AT/VA/PS)"),
    # ── Conciliação de PE/AF2 — Estorno (Crédito a Clientes) — spec 2026-08-14 ───────────────
    # Lançamento A (imediato, no clique "Aprovar" o Estorno): nasce o passivo, reduz a receita
    # reconhecida. NUNCA se compensa automaticamente com o Complemento de Projeto (Cobrar).
    "estorno_credito_cliente":      ("4.3.02", "2.1.11",    "Estorno — crédito ao cliente por diferença de Custo de Fábrica (Devolução de Vendas)"),
    # Lançamento B (evento futuro, manual): baixa do crédito — abate o que o cliente ainda deve
    # (inclusive um Complemento de Projeto futuro) ou devolve em dinheiro.
    "baixa_credito_cliente_receber": ("2.1.11", "1.1.02",   "Baixa de Crédito a Clientes — abate Contas a Receber"),
    "baixa_credito_cliente_caixa":   ("2.1.11", "1.1.01",   "Baixa de Crédito a Clientes — devolvido em dinheiro"),
}


def _conta_por_codigo(db, owner_tipo, owner_id, codigo):
    c = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo).first()
    if c is None:
        raise ValueError("conta %s ausente no plano de contas do owner" % codigo)
    return c


def _conta_existe(db, owner_tipo, owner_id, codigo):
    return db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo).first() is not None


def registrar_evento(db, owner_tipo, owner_id, tipo_evento, valor, projeto_id=None, data=None,
                     historico="", ref=None, motivo=None):
    """Gera o lançamento de partida dobrada correspondente a um evento de negócio (.docx §5/§6).
    Carrega projeto_id (dimensão gerencial) e, p/ reparo em garantia, `motivo` (§6.2).
    Se `ref` já foi lançado, é **idempotente** (não duplica)."""
    if tipo_evento not in EVENTOS:
        raise ValueError("evento desconhecido: %s" % tipo_evento)
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja                          # idempotente: já lançado com este ref
    seed_plano(db, owner_tipo, owner_id)   # garante o plano-padrão
    cod_d, cod_c, hist_pad = EVENTOS[tipo_evento]
    cd = _conta_por_codigo(db, owner_tipo, owner_id, cod_d)
    cc = _conta_por_codigo(db, owner_tipo, owner_id, cod_c)
    return lancar(db, owner_tipo, owner_id, cd.id, cc.id, valor,
                  data=data, projeto_id=projeto_id, origem=tipo_evento,
                  historico=historico or hist_pad, ref=ref, motivo=motivo)


# ── FASE B2: faturamento segmentado com split contra o Adiantamento de Clientes ──────────────
def saldo_adiantamento_projeto(db, owner_tipo, owner_id, projeto_id):
    """Pool de Adiantamento de Clientes (2.1.06) EM ABERTO do projeto: crédito − débito dos
    lançamentos tagueados ao projeto. Nunca considerado abaixo de 0."""
    return max(_mov(db, owner_tipo, owner_id, "2.1.06", "credor", None, None, projeto_id=projeto_id), 0.0)


def faturar_segmento(db, owner_tipo, owner_id, projeto_id, segmento, valor, ref_base, data=None):
    """Fatura um segmento da receita (B1): 'mercadoria' → 4.1.01 (NF-e) | 'servico' → 4.2.01 (NFS-e).
    `valor` é o TOTAL que deve estar reconhecido para este projeto neste segmento — não um
    incremento. A função lê o que o livro já tem reconhecido (`_mov(..., "credor")` na própria
    conta de receita — LÍQUIDO de estornos, medido em tests/test_mov_credor_liquido_estorno.py:
    um estorno de NF-e cancelada debita a mesma conta e reduz esta leitura) e fatura só a
    DIFERENÇA (delta). Isso protege contra dois documentos fiscais faturando o mesmo segmento do
    mesmo projeto (ACHADO-13) — a idempotência por `ref` só protege o MESMO documento duas vezes.

    Delta < 0 (o total pedido é MENOR que o já reconhecido) é recusado: reduzir receita
    reconhecida é estorno, não refaturamento — não implementado aqui (correção passa pela rota de
    estorno, quando existir). Delta ~ 0 é no-op (nada novo a faturar).

    Faz o SPLIT do DELTA entre baixar o Adiantamento do projeto (2.1.06, até o saldo em aberto) e
    constituir Contas a Receber (1.1.02) pelo resto. Idempotente por documento (refs `ref_base:adiantado`
    e `ref_base:areceber`) e crash-safe: se a 1ª perna já existe, o split é RECUPERADO dela (não
    recalculado do pool, que já mudou). Invariantes: soma das pernas == delta; 2.1.06 do projeto ≥ 0."""
    if segmento not in ("mercadoria", "servico"):
        raise ValueError("segmento inválido: %s" % segmento)
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return []
    ev_adiantado = "faturamento_%s_adiantado" % segmento
    ev_areceber  = "faturamento_%s_a_receber" % segmento
    ref_a, ref_r = ref_base + ":adiantado", ref_base + ":areceber"
    ja_a = lancamento_por_ref(db, owner_tipo, owner_id, ref_a)
    ja_r = lancamento_por_ref(db, owner_tipo, owner_id, ref_r)
    if ja_r is not None:                       # a perna final já existe → tudo lançado
        return [l for l in (ja_a, ja_r) if l is not None]
    conta_receita = "4.1.01" if segmento == "mercadoria" else "4.2.01"
    ja_reconhecido = _mov(db, owner_tipo, owner_id, conta_receita, "credor", None, None,
                          projeto_id=projeto_id)
    delta = round(valor - ja_reconhecido, 2)
    if delta < -0.005:
        raise ValueError(
            "faturar_segmento: %s do projeto %s já tem R$ %.2f reconhecido em %s; R$ %.2f "
            "pedido reduziria a receita reconhecida — refaturamento não faz isso, correção é "
            "estorno (não implementado)." % (segmento, projeto_id, ja_reconhecido, conta_receita, valor))
    if delta <= 0.005:
        return []                              # já reconhecido integralmente — nada novo a faturar
    if ja_a is not None:
        usa = ja_a["valor"]                    # crash-recovery: split congelado na 1ª perna
    else:
        usa = round(min(saldo_adiantamento_projeto(db, owner_tipo, owner_id, projeto_id), delta), 2)
    resto = round(delta - usa, 2)
    out = []
    if usa > 0:                                # perna 1: saca do pool (registrar_evento re-checa o ref)
        out.append(registrar_evento(db, owner_tipo, owner_id, ev_adiantado, usa,
                                    projeto_id=projeto_id, data=data, ref=ref_a))
    if resto > 0:                              # perna 2: resto a receber
        out.append(registrar_evento(db, owner_tipo, owner_id, ev_areceber, resto,
                                    projeto_id=projeto_id, data=data, ref=ref_r))
    return out


# ── FASE B2.4: constituição de TODAS as provisões rastreadas no fechamento ────────────────────
# chave da rubrica -> evento de constituição. O VALOR de cada uma vem do motor (mod_provisoes), computado
# pelo composition root (main.py) — o razão só BOOKA, sem calcular (mantém o layering ledger×cálculo).
_PROV_FECHAMENTO = {
    "montagem":            "fechamento_venda_montagem",
    "garantia":            "fechamento_venda_garantia",
    "assistencia":         "fechamento_venda_assistencia",
    "frete_fabrica":       "fechamento_venda_frete_fabrica",
    "frete_local":         "fechamento_venda_frete_local",
    "insumos":             "fechamento_venda_insumos",
    "com_medidor":         "fechamento_venda_com_medidor",
    "com_proj_exec":       "fechamento_venda_com_proj_exec",
    "retencao_com_vendas": "fechamento_venda_retencao_com_vendas",
    "custo_fabrica":       "fechamento_venda_custo_fabrica",   # FASE D2: 10ª rubrica (era só no faturamento)
    "impostos":            "fechamento_venda_impostos",
    # FASE A (resultado da venda): os 4 custos adicionais
    "com_arq":             "fechamento_venda_com_arq",
    "pro_fid":             "fechamento_venda_pro_fid",
    "cust_via":            "fechamento_venda_cust_via",
    "brinde":              "fechamento_venda_brinde",
    "cust_esp":           "fechamento_venda_cust_esp",
    # FASE B — ramo FINANCEIRA (custo financeiro é rubrica provisionada; NÃO entra no matching
    # operacional da NF-e — tem reconhecimento próprio, como impostos)
    "custo_financeiro":    "fechamento_venda_custo_financeiro",
    # 2026-08-12: Comissão Administrativa (achado do usuário — antes só visão gerencial, sem lançamento)
    "com_adm":             "fechamento_venda_com_adm",
}


def constituir_provisoes_fechamento(db, owner_tipo, owner_id, projeto_id, valores, ref_base):
    """Constitui TODAS as 10 rubricas no fechamento da venda. `valores` = {chave_rubrica: R$} (do motor,
    computado pelo chamador). Cada uma: Ativo diferido (1.1.06.0X, ou 1.1.05 p/ impostos) × Provisão
    (2.1.04.0X) — **sem tocar a DRE** (FASE D2); a despesa vira resultado só na NF-e. Idempotente por ref
    (`ref_base:<chave>`). Valor <= 0 não lança. Custo de Fábrica (`custo_fabrica`) É constituído aqui.
    Retorna {chave: valor_lançado}."""
    out = {}
    for chave, valor in (valores or {}).items():
        evento = _PROV_FECHAMENTO.get(chave)
        if evento is None:
            continue
        v = round(float(valor or 0), 2)
        if v <= 0:
            continue
        registrar_evento(db, owner_tipo, owner_id, evento, v, projeto_id=projeto_id,
                         ref=ref_base + ":" + chave)
        out[chave] = v
    return out


_ORIGEM_AJUSTE_AF = "ajuste_provisao_af"


def ajustar_provisao_delta(db, owner_tipo, owner_id, projeto_id, rubrica, valor_anterior, valor_novo, ref, data=None):
    """#11 (Fatia 2) — ajuste (delta) de UMA provisão entre versões de Aprovação Financeira.

    Move SÓ entre o ativo diferido (1.1.06.0X, ou 1.1.05 p/ impostos) e a provisão (2.1.04.0X) —
    o par exato do evento de constituição da rubrica. **NUNCA toca a DRE** (o reconhecimento de
    despesa é a NF-e real, #12). `rubrica` usa o vocabulário de `_PROV_FECHAMENTO` (ex.: 'custo_fabrica').

      delta = round(valor_novo - valor_anterior, 2)
      - delta > 0 (aumento): constitui mais → DR ativo × CR provisão (mesma direção do fechamento).
      - delta < 0 (redução): reverte → DR provisão × CR ativo, **capado ao saldo do ativo em aberto**
        (não reverte além do que ainda não foi baixado na NF-e; o resto é absorvido na conciliação, #3).
      - delta == 0 (ou cap 0): no-op.

    Idempotente por `ref` (o chamador inclui o sufixo `:parcela_id`, #6). Origem própria
    (`ajuste_provisao_af`) p/ distinguir do fechamento original no razão (auditabilidade, #11).
    """
    evento = _PROV_FECHAMENTO.get(rubrica)
    if evento is None:
        raise ValueError("ajustar_provisao_delta: rubrica desconhecida: %s" % rubrica)
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja                              # idempotente
    delta = round(float(valor_novo or 0) - float(valor_anterior or 0), 2)
    if delta == 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    ativo_cod, prov_cod, _hist = EVENTOS[evento]
    ativo = _conta_por_codigo(db, owner_tipo, owner_id, ativo_cod)
    prov = _conta_por_codigo(db, owner_tipo, owner_id, prov_cod)
    if delta > 0:
        # aumento: constitui mais provisão × ativo diferido (mesma direção do fechamento_venda)
        return lancar(db, owner_tipo, owner_id, ativo.id, prov.id, delta, data=data, projeto_id=projeto_id,
                      origem=_ORIGEM_AJUSTE_AF,
                      historico="Ajuste de provisão (AF) — aumento (ativo diferido × provisão)", ref=ref)
    # redução: reverte, capado ao saldo do ativo em aberto (débito − crédito do ativo)
    saldo_ativo = round(total_lancado(db, owner_tipo, owner_id, ativo_cod, "debito", projeto_id)
                        - total_lancado(db, owner_tipo, owner_id, ativo_cod, "credito", projeto_id), 2)
    mv = round(min(-delta, max(saldo_ativo, 0.0)), 2)
    if mv <= 0:
        return None
    return lancar(db, owner_tipo, owner_id, prov.id, ativo.id, mv, data=data, projeto_id=projeto_id,
                  origem=_ORIGEM_AJUSTE_AF,
                  historico="Ajuste de provisão (AF) — redução (reversão do ativo diferido)", ref=ref)


# Fatia B (resultado financeiro) — ramo do custo financeiro → evento de constituição no contrato.
# #10/#11 (Fatia C) — mapa das chaves do painel de provisões (mod_provisoes._RUBRICAS) → rubrica contábil
# (_PROV_FECHAMENTO).
_AF_ITEM_RUBRICA = {
    "prov_mont": "montagem", "prov_gar": "garantia", "assist": "assistencia",
    "frete_fab": "frete_fabrica", "frete_loc": "frete_local", "ins_loc": "insumos",
    "com_med": "com_medidor", "com_proj_exec": "com_proj_exec",
    "com_venda": "retencao_com_vendas", "prov_imp": "impostos",
    # F0 (bug ①): custos adicionais — ajustáveis na AF (mesma chave em _PROV_FECHAMENTO).
    "com_arq": "com_arq", "pro_fid": "pro_fid", "cust_via": "cust_via", "brinde": "brinde",
    # com_adm (2026-08-12): mesma família dos custos adicionais — ajustável na AF.
    "com_adm": "com_adm",
    # out_forn (Outros Fornecedores) NÃO entra: só nasce por reclassificação (conferencia_pedido,
    # etapa 12), sem evento de fechamento próprio.
    # custo_financeiro NÃO entra: é LEITURA no painel (ajuste pelo box do ramo, rota própria).
}


def disparar_deltas_af(db, owner_tipo, owner_id, projeto_id, itens_alvo, ref_base, data=None):
    """#10/#11 — ao confirmar uma Aprovação Financeira, ajusta cada rubrica do **saldo ATUAL da provisão**
    para o valor-alvo da versão aprovada (itens_alvo, chaves do painel). Só ativo diferido × provisão,
    NUNCA DRE. Converge (idempotente por VALOR: re-aprovar o mesmo alvo → delta 0, mesmo com ref nova).
    Retorna {rubrica: delta_R$}."""
    out = {}
    for chave, rubrica in _AF_ITEM_RUBRICA.items():
        if chave not in (itens_alvo or {}) or rubrica not in _PROV_FECHAMENTO:
            continue
        alvo = round(float(itens_alvo.get(chave) or 0), 2)
        _ativo, prov_cod, _h = EVENTOS[_PROV_FECHAMENTO[rubrica]]
        atual = round(_mov(db, owner_tipo, owner_id, prov_cod, "credor", None, None, projeto_id=projeto_id), 2)
        if abs(alvo - atual) < 0.005:
            continue
        lan = ajustar_provisao_delta(db, owner_tipo, owner_id, projeto_id, rubrica, atual, alvo,
                                     ref=ref_base + ":" + rubrica, data=data)
        if lan is not None:
            out[rubrica] = round(alvo - atual, 2)
    return out


_RAMO_CFIN_EVENTO = {
    # ACHADO-02/03 (docs/db/TAREFA_ACHADO02_03.md, passo 10, tabela decidida em 30/08): quem NUNCA
    # teve o dinheiro (financeira/cartão retém a própria taxa antes de repassar) não tem receita
    # nem custo no fechamento — vira retenção esperada, posição de balanço (ver
    # _PROV_DESTINO_VARIANCIA). loja_antecipacao é receita financeira a apropriar, IGUAL a loja —
    # o deságio do banco só existe se/quando a antecipação de fato acontece, evento separado
    # (`reconhecer_custo_financeiro`). A tabela antiga mandava financeira E loja_antecipacao pro
    # MESMO evento de custo provisionado — nenhum dos dois estava certo.
    "financeira":       "fechamento_venda_custo_financeiro",  # retenção esperada (posição de balanço, nada no resultado)
    "loja_antecipacao": "constituir_juros_direto",             # receita financeira a apropriar — igual a 'loja'
    "loja":             "constituir_juros_direto",             # receita financeira a apropriar (capital próprio, sem despesa)
    # 'avista' → None (Cust_Fin = 0)
}


def evento_custo_financeiro(ramo):
    """Evento de constituição do custo financeiro por ramo (Fatia B). None p/ 'avista'/desconhecido."""
    return _RAMO_CFIN_EVENTO.get(ramo)


def trocar_ramo_custo_financeiro(db, owner_tipo, owner_id, projeto_id, ramo_atual, ramo_novo, valor, ref_base, data=None):
    """#B.2 — troca o ramo do custo financeiro DEPOIS do fechamento (box da AF). Reverte o que o
    fechamento lançou e constitui o ramo novo. Idempotente por `ref_base`.

    ACHADO-02/03 (passo 10): só 'financeira' constitui a provisão (retenção esperada) — loja e
    loja_antecipacao usam a MESMA receita financeira a apropriar (`_RAMO_CFIN_EVENTO`).
      - loja ↔ loja_antecipacao: **no-op** contábil (mesmo mecanismo — juros a apropriar).
      - loja/loja_antecipacao → financeira: estorna os juros a apropriar e constitui a provisão.
      - financeira → loja/loja_antecipacao: reverte a provisão e constitui os juros a apropriar.
    Retorna o ramo efetivo (ramo_novo).
    """
    _PROV = {"financeira"}
    if ramo_atual == ramo_novo:
        return ramo_novo
    de_prov, para_prov = ramo_atual in _PROV, ramo_novo in _PROV
    if de_prov == para_prov:
        return ramo_novo                       # ambos provisão, ou ambos loja/avista → sem mudança de razão
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return ramo_novo
    if para_prov:                              # loja → provisão
        registrar_evento(db, owner_tipo, owner_id, "reverter_juros_direto", valor,
                         projeto_id=projeto_id, ref=ref_base + ":rev")
        registrar_evento(db, owner_tipo, owner_id, "fechamento_venda_custo_financeiro", valor,
                         projeto_id=projeto_id, ref=ref_base + ":new")
    else:                                      # provisão → loja
        ajustar_provisao_delta(db, owner_tipo, owner_id, projeto_id, "custo_financeiro", valor, 0.0,
                               ref=ref_base + ":rev")
        registrar_evento(db, owner_tipo, owner_id, "constituir_juros_direto", valor,
                         projeto_id=projeto_id, ref=ref_base + ":new")
    return ramo_novo


_RAMO_CFIN_DESPESA = {
    "loja_antecipacao": "reconhecimento_antecipacao",              # 5.5.03 Custo de Antecipação de Recebíveis
    # ACHADO-02/03 (passo 10): 'financeira' NUNCA reconhece despesa — nada no resultado, a
    # retenção esperada é posição de balanço (ver conferir_retencao_financeira). O antigo
    # "financeira": "reconhecimento_despesa_custo_financeiro" (5.5.04) saiu daqui.
}


def reconhecer_custo_financeiro(db, owner_tipo, owner_id, projeto_id, ramo, valor, ref, data=None):
    """#B — reconhece o custo REAL da antecipação bancária (ramo loja_antecipacao) quando ela de fato
    acontece: o deságio que o banco retém é custo SEPARADO do cust_fin do fechamento (que virou
    receita financeira a apropriar, igual a 'loja' — ACHADO-02/03) — não é estimado antes, nasce
    aqui. Constitui o ativo diferido/provisão (1.1.06.19×2.1.04.19) PARA o valor real, na hora, e
    reconhece a despesa (5.5.03) contra o ativo no mesmo evento — sem cap, porque não há
    estimativa prévia para capar contra.

    Ramo 'loja' (próprio) / 'avista' não tem despesa → None. 'financeira' também não (nada no
    resultado — ver conferir_retencao_financeira, a rota própria da retenção esperada).
    Idempotente por ref."""
    evento = _RAMO_CFIN_DESPESA.get(ramo)
    if evento is None:
        return None
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    registrar_evento(db, owner_tipo, owner_id, "fechamento_venda_custo_financeiro", valor,
                     projeto_id=projeto_id, ref=ref + ":prov")
    return registrar_evento(db, owner_tipo, owner_id, evento, valor, projeto_id=projeto_id, ref=ref)


def conferir_retencao_financeira(db, owner_tipo, owner_id, projeto_id, valor_real, ref_base, data=None):
    """ACHADO-01/02/03 (passo 10) — a perna de liquidação da retenção esperada da financeira/cartão
    (2.1.04.19/1.1.06.19, constituída no fechamento, ramo 'financeira'). NUNCA reconhece despesa
    (aceite #3 — 'nada no resultado'): duas pernas independentes.

    (1) Cancela o par constituído inteiro (D:2.1.04.19 × C:1.1.06.19, pelo saldo constituído) —
    sem tocar DRE nem recebível: é só o encerramento da ESTIMATIVA, qualquer que seja o real.

    (2) A diferença entre a retenção esperada e a real (`saldo − valor_real`) ajusta o recebível
    (1.1.02) pela mesma diferença — é isto que faz "o líquido esperado = VAVO": se a financeira
    reteve MENOS que o esperado, sobra dinheiro pra loja receber (1.1.02 sobe); se reteve MAIS,
    falta (1.1.02 desce) — e o mesmo valor vai para 'Ajuste de Retenção Financeira' (4.4.05),
    MESMA conta nos dois sentidos (sobra credita, falta debita), a mesma regra e a mesma
    justificativa dos impostos (2.1.04.13 → 4.3.01).

    Idempotente por ref_base (cada perna por si)."""
    seed_plano(db, owner_tipo, owner_id)
    saldo = round(_mov(db, owner_tipo, owner_id, "2.1.04.19", "credor", None, None, projeto_id=projeto_id), 2)
    if saldo > 0.005:
        ja = lancamento_por_ref(db, owner_tipo, owner_id, ref_base + ":cancela")
        if ja is None:
            prov = _conta_por_codigo(db, owner_tipo, owner_id, "2.1.04.19")
            ativo = _conta_por_codigo(db, owner_tipo, owner_id, "1.1.06.19")
            lancar(db, owner_tipo, owner_id, prov.id, ativo.id, saldo, data=data, projeto_id=projeto_id,
                  origem=_ORIGEM_RESOL_SOBRA,
                  historico="Retenção confirmada — cancela ativo × provisão (sem impacto no resultado)",
                  ref=ref_base + ":cancela")
    diferenca = round(saldo - round(float(valor_real or 0), 2), 2)
    if abs(diferenca) < 0.005:
        return None
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref_base + ":var")
    if ja is not None:
        return ja
    rec = _conta_por_codigo(db, owner_tipo, owner_id, "1.1.02")
    destino = _conta_por_codigo(db, owner_tipo, owner_id, "4.4.05")
    if diferenca > 0:   # sobra: financeira reteve menos — sobra dinheiro pra loja receber
        return lancar(db, owner_tipo, owner_id, rec.id, destino.id, diferenca, data=data, projeto_id=projeto_id,
                      origem=_ORIGEM_RESOL_SOBRA, historico="Ajuste de retenção financeira (sobra)",
                      ref=ref_base + ":var")
    return lancar(db, owner_tipo, owner_id, destino.id, rec.id, -diferenca, data=data, projeto_id=projeto_id,
                 origem=_ORIGEM_RESOL_FALTA, historico="Ajuste de retenção financeira (falta)",
                 ref=ref_base + ":var")


def apropriar_juros_loja(db, owner_tipo, owner_id, projeto_id, valor, ref_base, data=None):
    """#B — ramo LOJA (financiamento direto, capital próprio): ao receber a parte de JUROS de uma parcela,
    baixa o recebível (caixa 1.1.01 × 1.1.07) e apropria a receita financeira por competência
    (2.1.07 × 4.4.03), CAPADO ao recebível de juros em aberto (1.1.07). Sem despesa (capital próprio).
    Idempotente por `ref_base`. Retorna o valor apropriado (ou None)."""
    saldo_rec = round(total_lancado(db, owner_tipo, owner_id, "1.1.07", "debito", projeto_id)
                      - total_lancado(db, owner_tipo, owner_id, "1.1.07", "credito", projeto_id), 2)
    mv = round(min(float(valor or 0), max(saldo_rec, 0.0)), 2)
    if mv <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    registrar_evento(db, owner_tipo, owner_id, "receber_parcela_direto", mv, projeto_id=projeto_id, ref=ref_base + ":rec")
    registrar_evento(db, owner_tipo, owner_id, "apropriar_receita_financeira", mv, projeto_id=projeto_id, ref=ref_base + ":ap")
    return mv


def conferencia_pedido(db, owner_tipo, owner_id, projeto_id, custo_fabrica_novo, valor_outros_forn,
                       ref_base, data=None, excluir_ajustes=0.0):
    """#13 — Conferência e Implantação do Pedido (etapa 12): DOIS lançamentos auditáveis, ambos
    ativo × provisão, NUNCA DRE:
      (a) ajusta o **Custo de Fábrica** do saldo ATUAL da provisão (2.1.04.06) para `custo_fabrica_novo`
          (valor do PE) — `ajustar_provisao_delta`, convergente;
      (b) reclassifica `valor_outros_forn` da fábrica para **Outros Fornecedores**
          (`reclassificar_provisao 2.1.04.06→2.1.04.14`, espelhando o ativo diferido).
    Idempotente por ref_base (use ref estável por projeto → conferência única). Retorna
    {custo_fabrica_delta?, outros_fornecedores?}."""
    out = {}
    _a, prov_cod, _h = EVENTOS[_PROV_FECHAMENTO["custo_fabrica"]]   # 2.1.04.06
    # `excluir_ajustes` (spec Ajustes Excepcionais 2026-07-21): efeito LÍQUIDO dos ajustes
    # excepcionais já aplicados neste projeto (acréscimos − descontos). Sem excluí-lo, re-rodar a
    # conferência miraria `custo_novo` sobre a provisão JÁ ajustada e reverteria os ajustes
    # (o delta zero da 1ª conferência não grava ref — não há marca de idempotência).
    atual = round(_mov(db, owner_tipo, owner_id, prov_cod, "credor", None, None, projeto_id=projeto_id)
                  - float(excluir_ajustes or 0), 2)
    novo = round(float(custo_fabrica_novo or 0), 2)
    lan_a = ajustar_provisao_delta(db, owner_tipo, owner_id, projeto_id, "custo_fabrica",
                                   atual, novo, ref=ref_base + ":pe", data=data)
    if lan_a is not None:
        out["custo_fabrica_delta"] = round(novo - atual, 2)
    v = round(float(valor_outros_forn or 0), 2)
    if v > 0:
        lan_b = reclassificar_provisao(db, owner_tipo, owner_id, projeto_id, "2.1.04.06", "2.1.04.14",
                                       v, ref=ref_base + ":outros", data=data)
        if lan_b is not None:
            out["outros_fornecedores"] = v
    return out


def total_lancado(db, owner_tipo, owner_id, codigo, lado, projeto_id=None,
                  origens=None, excluir_origens=None):
    """Soma BRUTA dos lançamentos de um lado ('debito'|'credito') de uma conta (opcionalmente por
    projeto). `origens` = só estas origens; `excluir_origens` = todas menos estas. Ex.: total constituído
    da Provisão de Impostos = total_lancado(..., '2.1.04.13', 'credito', projeto) — diferente do saldo,
    que já desconta as baixas."""
    conta = _conta_por_codigo(db, owner_tipo, owner_id, codigo)
    col = Lancamento.conta_debito_id if lado == "debito" else Lancamento.conta_credito_id
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).filter(col == conta.id)
    if projeto_id:
        q = q.filter(Lancamento.projeto_id == projeto_id)
    if origens is not None:
        q = q.filter(Lancamento.origem.in_(list(origens)))
    if excluir_origens is not None:
        q = q.filter(~Lancamento.origem.in_(list(excluir_origens)))
    return round(sum(l.valor for l in q.all()), 2)


def efetivado_no_dia(db, owner_tipo, owner_id, projeto_id, codigo_provisao, dia):
    """ACHADO-35 (docs/db/TAREFA_PERCURSO_0109.md, item B1) — regra 3: o total já efetivado
    NUM DIA vem do RAZÃO (débito na própria provisão, perna que `efetivar_provisao` sempre grava
    — a perna de despesa é outra conta), nunca de uma soma que a tela lembra em variável. Retorna
    (total, quantidade) — quantidade também numera a próxima efetivação confirmada do mesmo dia
    (ref ganha sufixo sequencial, nunca colide com a de antes)."""
    from datetime import datetime as _dt, time as _time
    conta = _conta_por_codigo(db, owner_tipo, owner_id, codigo_provisao)
    ini = _dt.combine(dia, _time.min)
    fim = _dt.combine(dia, _time.max)
    lancs = (db.query(Lancamento)
               .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, projeto_id=projeto_id)
               .filter(Lancamento.conta_debito_id == conta.id)
               .filter(Lancamento.data >= ini, Lancamento.data <= fim)
               .all())
    return round(sum(l.valor for l in lancs), 2), len(lancs)


def efetivar_impostos_segmento(db, owner_tipo, owner_id, projeto_id, valor, ref_base, data=None):
    """Efetiva (baixa) a Provisão de Impostos no faturamento, para a parcela `valor` (proporcional ao
    segmento Mercadoria/Serviço). Dois lançamentos idempotentes por ref: dedução na DRE
    (4.3.01 × baixa do ativo diferido 1.1.05) e obrigação fiscal real (2.1.04.13 × 2.1.03). O valor é
    limitado ao saldo em aberto da provisão (nunca negativa). Retorna o valor efetivado."""
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return 0.0
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref_base + ":ded")
    if ja is not None:
        return ja["valor"]                         # idempotente: já efetivado com este ref
    saldo = max(_mov(db, owner_tipo, owner_id, "2.1.04.13", "credor", None, None, projeto_id=projeto_id), 0.0)
    v = round(min(valor, saldo), 2)
    if v <= 0:
        return 0.0
    registrar_evento(db, owner_tipo, owner_id, "faturamento_impostos_deducao", v,
                     projeto_id=projeto_id, data=data, ref=ref_base + ":ded")
    registrar_evento(db, owner_tipo, owner_id, "faturamento_impostos_obrigacao", v,
                     projeto_id=projeto_id, data=data, ref=ref_base + ":obr")
    return v


_ORIGEM_ESTORNO_NFE_CANCELADA = "estorno_cancelamento_nfe"


def estornar_faturamento_nfe(db, owner_tipo, owner_id, ref_doc):
    """Reverte o faturamento (receita + impostos) de uma NF-e CANCELADA (achado Vera 2026-08-12:
    cancelar a NF-e não desfazia nada no razão — a receita ficava contabilizada para uma nota
    juridicamente inexistente). Mesmo padrão de `estornar_rateio`: lançamento invertido com ref
    '<original>:estorno', idempotente. Cobre os dois wirings automáticos disparados na emissão —
    `faturar_segmento` (refs 'fat:<ref_doc>:*') e `efetivar_impostos_segmento`
    (refs 'imp:<ref_doc>:*'). Retorna os estornos criados (lista, vazia se não havia nada a reverter
    ou já estava tudo estornado)."""
    from sqlalchemy import or_
    prefixos = ("fat:" + ref_doc + ":", "imp:" + ref_doc + ":")
    legs = (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
              .filter(or_(*[Lancamento.ref.like(p + "%") for p in prefixos]))
              .order_by(Lancamento.id.asc()).all())
    out = []
    for l in legs:
        if (l.ref or "").endswith(":estorno"):
            continue
        ref_estorno = l.ref + ":estorno"
        if lancamento_por_ref(db, owner_tipo, owner_id, ref_estorno) is not None:
            continue
        out.append(lancar(db, owner_tipo, owner_id, l.conta_credito_id, l.conta_debito_id, l.valor,
                          projeto_id=l.projeto_id, origem=_ORIGEM_ESTORNO_NFE_CANCELADA,
                          historico="Estorno (NF-e cancelada) — " + (l.historico or ""), ref=ref_estorno))
    return out


# ── FASE D: reconciliação (Provisionado × Efetivado × Saldo × Destino) + Contas a Pagar ───────
_ORIGEM_RESOL_SOBRA = "resolucao_provisao_sobra"
_ORIGEM_RESOL_FALTA = "resolucao_provisao_falta"
_ORIGEM_RECLASS     = "reclassificacao_provisao"

# 2026-08-07 (achado do usuário): despesa na COMPETÊNCIA REAL da efetivação, não mais estimada de
# uma vez na NF-e (extinto o antigo "matching pleno", reconhecer_despesas_nfe/_MATCHING_NFE — as
# despesas de projeto de móveis planejados ocorrem espalhadas ao longo do ciclo, muitas depois da
# própria NF-e, que só sai no fim, na entrega). Ativo diferido (crédito) -> despesa formal (débito),
# derivado de EVENTOS — cobre as 15 rubricas do antigo matching pleno + Outros Fornecedores
# automaticamente. Custo Financeiro fica de fora (rota própria: reconhecer_custo_financeiro, atrelada
# a um evento real de antecipação bancária, não à efetivação manual/automática de provisão).
_PROV_DESPESA_POR_ATIVO = {cred: deb for ev, (deb, cred, _h) in EVENTOS.items()
                          if ev.startswith("reconhecimento_despesa_") and ev != "reconhecimento_despesa_custo_financeiro"}

# docs/db/TAREFA_PROVISOES.md item 2 — RESOLVIDO PARA 'financeira' por rota PRÓPRIA (passo 10,
# ACHADO-01/02/03, 30/08): `conferir_retencao_financeira` é a perna de liquidação — cancela o
# par ativo×provisão constituído no fechamento e manda a diferença entre a retenção esperada e a
# real pra 'Ajuste de Retenção Financeira' (4.4.05) via um lançamento PRÓPRIO contra o recebível
# (1.1.02), não pelo mecanismo genérico de `resolver_saldo_provisao` — por isso 2.1.04.19
# continua de fora tanto daqui quanto de `_PROV_DESTINO_VARIANCIA`: uma chamada DIRETA e genérica
# a `resolver_saldo_provisao("2.1.04.19", ...)` (fora da rota própria) segue sem destino
# definido, de propósito — falha, não inventa uma rota alternativa que o razão não pediu.
_PROV_TEMPO_REAL_ROTA_PROPRIA = set()

# docs/db/TAREFA_PROVISOES.md item 3/4: destino EXPLÍCITO de variância por provisão, fora do
# padrão "tempo real" — sobra e falta vão pra MESMA conta, sinais opostos (achado do Marcelo:
# a rota antiga mandava sobra→4.4.02 e falta→5.6.10, inflando receita em vez de corrigir
# dedução — os dois lados da mesma variância acabavam em contas diferentes). Se um código
# aqui apontar pra "5.6.10", `resolver_saldo_provisao` alerta no momento da escrita (item 4) —
# 5.6.10 só entra aqui de propósito, nunca como default de quem não tem entrada nenhuma.
_PROV_DESTINO_VARIANCIA = {
    "2.1.04.13": "4.3.01",   # Impostos (P4): variância é dedução de receita, não custo nem receita nova
}

# F2-3 (docs/db/TAREFA_FILA_PROVISOES.md): as duas rubricas que `conciliar_final` e
# `resolver_veredito_provisao` excluem da regra de veredito, de propósito (ACHADO-01) — rota
# própria de liquidação, não o mecanismo genérico. Nome único usado nos dois lugares (antes eram
# dois literais `{"2.1.04.13", "2.1.04.19"}` independentes) e na guarda do endpoint
# `/api/financeiro/resolver-saldo-provisao`, que só continua aceitando estas duas depois do F2-3
# fechar a porta dos fundos para o resto. Nota: 2.1.04.19 (Custo Financeiro) já falhava sozinho
# nesta rota genérica ANTES do F2-3 (sem entrada em `_PROV_DESTINO_VARIANCIA` nem em
# `_PROV_TEMPO_REAL_ROTA_PROPRIA`, de propósito, ver comentário acima) — continua listado aqui
# só por simetria com `conciliar_final`, não porque a rota funcione para ele.
_PROV_FORA_DO_VEREDITO = {"2.1.04.13", "2.1.04.19"}


def reconhecer_despesa_efetivacao(db, owner_tipo, owner_id, projeto_id, codigo_provisao, valor, ref, data=None):
    """Perna de despesa de uma efetivação de provisão: débito na despesa FORMAL da rubrica (5.x) ×
    crédito no ativo diferido espelho (1.1.06.0X) — reconhece o custo na competência REAL, em vez de
    estimado de uma vez na NF-e. Usada tanto por `efetivar_provisao` (efetivação manual, Reconciliação)
    quanto pela execução automática de casos de Assistência/Garantia
    (mod_assistencias.realizar_caso) — mesma perna de despesa, qualquer que seja o lado do passivo
    (Fornecedores a Pagar ou Caixa direto). Sem rota (impostos, custo financeiro, ou qualquer código
    fora do mapa) → None, sem lançar nada. Idempotente por ref."""
    ativo_cod = _ativo_diferido_de(codigo_provisao)
    despesa_cod = _PROV_DESPESA_POR_ATIVO.get(ativo_cod)
    if not despesa_cod or not _conta_existe(db, owner_tipo, owner_id, ativo_cod):
        return None
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    cd = _conta_por_codigo(db, owner_tipo, owner_id, despesa_cod)
    cc = _conta_por_codigo(db, owner_tipo, owner_id, ativo_cod)
    return lancar(db, owner_tipo, owner_id, cd.id, cc.id, valor, data=data, projeto_id=projeto_id,
                  origem="efetivacao_provisao_despesa",
                  historico="Reconhecimento de despesa na efetivação (competência real)", ref=ref)


def reclassificar_provisao(db, owner_tipo, owner_id, projeto_id, cod_de, cod_para, valor, ref, data=None):
    """Reclassifica parte de uma provisão para OUTRA (passivo × passivo — NÃO toca o resultado). Ex.:
    substituição de custo — parte da Provisão de Custo de Fábrica (2.1.04.06) passa para a Provisão de
    Outros Fornecedores (2.1.04.14). Débito `cod_de` (reduz a provisionado de origem), crédito `cod_para`
    (aumenta a provisionado de destino). Idempotente por ref. Assim cada provisão reconcilia com o seu
    efetivado, e a soma dos saldos = a economia total."""
    if not (cod_de or "").startswith(GRUPO_PROVISOES + ".") or not (cod_para or "").startswith(GRUPO_PROVISOES + "."):
        raise ValueError("reclassificar_provisao: contas devem ser provisões (%s.x)" % GRUPO_PROVISOES)
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    cd = _conta_por_codigo(db, owner_tipo, owner_id, cod_de)
    cc = _conta_por_codigo(db, owner_tipo, owner_id, cod_para)
    lan = lancar(db, owner_tipo, owner_id, cd.id, cc.id, valor, data=data, projeto_id=projeto_id,
                 origem=_ORIGEM_RECLASS, historico="Reclassificação de provisão", ref=ref)
    # FASE D2: espelha o ativo diferido (1.1.06.XX → 1.1.06.YY) NA PROPORÇÃO ainda não baixada na NF-e —
    # senão a rubrica de destino não é reconhecida no matching. Move só até o saldo em aberto do ativo de
    # origem: reclass ANTES da NF-e (ativo cheio) espelha tudo; DEPOIS da NF-e (ativo já baixado) não move.
    ativo_de = "1.1.06." + cod_de.rsplit(".", 1)[-1]
    ativo_para = "1.1.06." + cod_para.rsplit(".", 1)[-1]
    if _conta_existe(db, owner_tipo, owner_id, ativo_de) and _conta_existe(db, owner_tipo, owner_id, ativo_para):
        saldo_ativo = round(total_lancado(db, owner_tipo, owner_id, ativo_de, "debito", projeto_id)
                            - total_lancado(db, owner_tipo, owner_id, ativo_de, "credito", projeto_id), 2)
        mv = round(min(valor, max(saldo_ativo, 0.0)), 2)
        if mv > 0:
            ad = _conta_por_codigo(db, owner_tipo, owner_id, ativo_para)
            ac = _conta_por_codigo(db, owner_tipo, owner_id, ativo_de)
            lancar(db, owner_tipo, owner_id, ad.id, ac.id, mv, data=data, projeto_id=projeto_id,
                   origem=_ORIGEM_RECLASS, historico="Reclassificação de custo a apropriar (espelho do ativo)",
                   ref=ref + ":ativo")
    return lan


def efetivar_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao, valor, ref, data=None,
                      forma_pagamento="a_prazo", origem="efetivacao_provisao", motivo=None):
    """Efetiva (reconhece) o custo REAL de uma provisão: dois lançamentos no mesmo evento —
    (1) `reconhecer_despesa_efetivacao` (ref+':d'): débito na despesa formal da rubrica × crédito no
    ativo diferido, reconhecendo o custo NA COMPETÊNCIA REAL (2026-08-07, achado do usuário — antes só
    isto aqui movia passivo, e a despesa nascia estimada de uma vez na NF-e); e (2, ref bruto, mantido
    p/ compat) Provisão (2.1.04.x) × Fornecedores a Pagar (2.1.01) se `forma_pagamento='a_prazo'`
    (padrão — faturado por terceiro, não baixa em caixa; o pagamento é o evento
    `pagamento_fornecedor`), ou × Caixa/Bancos (1.1.01) se `forma_pagamento='direto'` (pago na hora —
    usado pelo módulo Assistências quando a loja executa e paga sozinha, 2026-08-07). `origem`
    parametrizável (default `efetivacao_provisao`) pra quem chama precisar de uma tag própria (ex.:
    `mod_assistencias` usa `execucao_assistencia`/`execucao_reparo_garantia`, preservando o filtro do
    relatório "a cobrar da fábrica"); `motivo` só é relevante nesse caso (carimba o reparo em
    garantia). Cobre QUALQUER provisão do grupo — Impostos e Custo Financeiro não ganham a perna de
    despesa aqui (rota própria, sem entrada em `_PROV_DESPESA_POR_ATIVO`). Idempotente por ref (cada
    perna por si)."""
    if forma_pagamento not in ("a_prazo", "direto"):
        raise ValueError("efetivar_provisao: forma_pagamento inválida: %s" % forma_pagamento)
    if not (codigo_provisao or "").startswith(GRUPO_PROVISOES + "."):
        raise ValueError("efetivar_provisao: %s não é conta de provisão (%s.x)" % (codigo_provisao, GRUPO_PROVISOES))
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    reconhecer_despesa_efetivacao(db, owner_tipo, owner_id, projeto_id, codigo_provisao, valor,
                                  ref=ref + ":d", data=data)
    cd = _conta_por_codigo(db, owner_tipo, owner_id, codigo_provisao)
    cc_cod = "1.1.01" if forma_pagamento == "direto" else "2.1.01"
    cc = _conta_por_codigo(db, owner_tipo, owner_id, cc_cod)
    hist = ("Efetivação de provisão (custo real → Caixa/Bancos)" if forma_pagamento == "direto"
            else "Efetivação de provisão (custo real → Fornecedores a Pagar)")
    return lancar(db, owner_tipo, owner_id, cd.id, cc.id, valor, data=data, projeto_id=projeto_id,
                  origem=origem, historico=hist, ref=ref, motivo=motivo)


def despesa_avulsa(db, owner_tipo, owner_id, codigo_despesa, valor, forma_pagamento, ref, data=None,
                   historico=""):
    """Despesa direta, SEM provisão de projeto (2026-08-07 — Assistência/Garantia avulsa: a
    provisão é uma média estatística por projeto; sem projeto não há o que debitar). Débito na
    despesa formal (`codigo_despesa` — ex.: 5.2.12 Garantia, 5.2.13 Assistência Técnica, 5.3.21
    Concessão a Cliente) × crédito Caixa/Bancos ('direto') ou Fornecedores a Pagar ('a_prazo').
    Idempotente por ref."""
    if forma_pagamento not in ("direto", "a_prazo"):
        raise ValueError("despesa_avulsa: forma_pagamento inválida: %s" % forma_pagamento)
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    cd = _conta_por_codigo(db, owner_tipo, owner_id, codigo_despesa)
    cc_cod = "1.1.01" if forma_pagamento == "direto" else "2.1.01"
    cc = _conta_por_codigo(db, owner_tipo, owner_id, cc_cod)
    return lancar(db, owner_tipo, owner_id, cd.id, cc.id, valor, data=data,
                  origem="despesa_avulsa_assistencia", historico=historico, ref=ref)


def registrar_recebimento_venda(db, owner_tipo, owner_id, projeto_id, valor, ref, data=None, duvidoso=False):
    """Recebimento REAL do cliente (2026-08-07, achado da Vera — `recebimento_venda` existia só como
    chave morta em EVENTOS, nada disparava a baixa de Contas a Receber). Débito Caixa/Bancos (1.1.01) ×
    crédito Contas a Receber (1.1.02), CAPADO ao saldo em aberto de 1.1.02 do projeto — mesmo idiom de
    `reconhecer_custo_financeiro`/`apropriar_juros_loja`, protege o razão mesmo quando `valor` vem de um
    previsto só estimado (caso do Parcelamento Loja, antigo Total Flex, que mistura capital+juros na parcela). Não mexe na
    apropriação de juros do ramo loja (`apropriar_juros_loja`, conta 1.1.07 à parte) — só a perna de
    capital. `duvidoso=True` (2026-08-07, não-recebimento): o recebível já foi reclassificado pra
    Recebíveis Duvidosos (`reclassificar_recebivel_duvidoso`) — credita 1.1.10 em vez de 1.1.02
    (mesma capagem, contra o saldo em aberto de 1.1.10). Idempotente por ref."""
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    cod_origem = "1.1.10" if duvidoso else "1.1.02"
    evento = "recebimento_venda_duvidoso" if duvidoso else "recebimento_venda"
    saldo_aberto = round(total_lancado(db, owner_tipo, owner_id, cod_origem, "debito", projeto_id)
                         - total_lancado(db, owner_tipo, owner_id, cod_origem, "credito", projeto_id), 2)
    mv = round(min(valor, max(saldo_aberto, 0.0)), 2)
    if mv <= 0:
        return None
    return registrar_evento(db, owner_tipo, owner_id, evento, mv,
                            projeto_id=projeto_id, data=data, ref=ref)


def reclassificar_recebivel_duvidoso(db, owner_tipo, owner_id, projeto_id, valor, ref, data=None):
    """Não-recebimento (2026-08-07): o cliente não pagou na data prevista e o recebível vira
    DUVIDOSO — reclassifica ativo×ativo (débito 1.1.10 Recebíveis Duvidosos × crédito 1.1.02 Contas a
    Receber), sem tocar a DRE (não é perda, é só troca de bucket — mesmo idiom de
    `reclassificar_provisao`). CAPADO ao saldo em aberto de 1.1.02 do projeto. Idempotente por ref."""
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    valor = round(float(valor or 0), 2)
    if valor <= 0:
        return None
    seed_plano(db, owner_tipo, owner_id)
    saldo_aberto = round(total_lancado(db, owner_tipo, owner_id, "1.1.02", "debito", projeto_id)
                         - total_lancado(db, owner_tipo, owner_id, "1.1.02", "credito", projeto_id), 2)
    mv = round(min(valor, max(saldo_aberto, 0.0)), 2)
    if mv <= 0:
        return None
    return registrar_evento(db, owner_tipo, owner_id, "recebivel_duvidoso", mv,
                            projeto_id=projeto_id, data=data, ref=ref)


def resolver_saldo_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao, ref, data=None):
    """Fecha o saldo em aberto da provisão (de um projeto).

    Item 1 (docs/db/TAREFA_PROVISOES.md): só aceita conta de provisão LEGÍTIMA — grupo
    `GRUPO_PROVISOES` (2.1.04.x), exceto as em `_PROV_PAINEL_EXCLUI` (Comissão/Devolução, que
    não são set-aside de custo — ver comentário de `_PROV_PAINEL_EXCLUI`). Qualquer outro
    código é recusado com erro explícito, antes de tocar em qualquer lançamento.

    Pras rubricas com despesa em TEMPO REAL (`_PROV_DESPESA_POR_ATIVO` — as 15 do antigo
    matching pleno — e `_PROV_TEMPO_REAL_ROTA_PROPRIA`, item 2: Custo Financeiro, cuja despesa
    real já é reconhecida por `reconhecer_custo_financeiro`): CANCELA contra o ativo diferido
    espelho (1.1.06.0X / 1.1.05), SEM TOCAR A DRE em nenhuma direção (2026-08-07, achado do
    usuário) — SOBRA (provisionado > efetivado) é dinheiro nunca gasto, não vira "receita";
    FALTA (efetivado > provisionado) já teve a despesa real reconhecida a cada efetivação —
    só o residual mecânico entre ativo e provisão é zerado.

    Pras demais, com destino EXPLÍCITO em `_PROV_DESTINO_VARIANCIA` (item 3: Impostos → 4.3.01):
    SOBRA e FALTA vão pra MESMA conta, sinais opostos — nunca a variância inteira numa direção
    só e a outra ponta noutra conta (era o defeito da rota antiga: sobra em 4.4.02, falta em
    5.6.10). Se o destino for 5.6.10 (item 4 — só de propósito, nunca por falta de
    alternativa), alerta no log NO MOMENTO DA ESCRITA, aqui na própria função — não só o
    alerta de saldo que já existe na tela (`alertas_contas_escape`).

    Uma provisão que não tem NEM despesa em tempo real NEM destino explícito, mas chega aqui
    com saldo a resolver, é erro — nomeando a rubrica — em vez de cair em 5.6.10 por padrão
    (item 4: 5.6.10 deixou de ser destino implícito).

    Zera a provisão do projeto. Idempotente por ref."""
    if not (codigo_provisao or "").startswith(GRUPO_PROVISOES + ".") or codigo_provisao in _PROV_PAINEL_EXCLUI:
        raise ValueError(
            "resolver_saldo_provisao: %r não é conta de provisão legítima (grupo %s.x, exceto %s)"
            % (codigo_provisao, GRUPO_PROVISOES, sorted(_PROV_PAINEL_EXCLUI)))
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    seed_plano(db, owner_tipo, owner_id)
    saldo = round(_mov(db, owner_tipo, owner_id, codigo_provisao, "credor", None, None, projeto_id=projeto_id), 2)
    if abs(saldo) < 0.005:
        return None
    prov = _conta_por_codigo(db, owner_tipo, owner_id, codigo_provisao)
    ativo_cod = _ativo_diferido_de(codigo_provisao)
    despesa_em_tempo_real = (
        (_PROV_DESPESA_POR_ATIVO.get(ativo_cod) is not None or codigo_provisao in _PROV_TEMPO_REAL_ROTA_PROPRIA)
        and _conta_existe(db, owner_tipo, owner_id, ativo_cod))
    if despesa_em_tempo_real:
        ativo = _conta_por_codigo(db, owner_tipo, owner_id, ativo_cod)
        if saldo > 0:   # sobra: nunca efetivado — cancela sem DRE (débito provisão × crédito ativo)
            return lancar(db, owner_tipo, owner_id, prov.id, ativo.id, saldo, data=data, projeto_id=projeto_id,
                          origem=_ORIGEM_RESOL_SOBRA,
                          historico="Cancelamento de provisão não efetivada (nunca gasto — sem impacto no resultado)",
                          ref=ref)
        return lancar(db, owner_tipo, owner_id, ativo.id, prov.id, -saldo, data=data, projeto_id=projeto_id,
                      origem=_ORIGEM_RESOL_FALTA,
                      historico="Cancelamento de excedente já reconhecido na efetivação (sem novo impacto no resultado)",
                      ref=ref)

    destino_cod = _PROV_DESTINO_VARIANCIA.get(codigo_provisao)
    if destino_cod is None:
        raise ValueError(
            "resolver_saldo_provisao: %s tem saldo de %.2f mas nenhum destino de variância "
            "definido (nem _PROV_TEMPO_REAL_ROTA_PROPRIA, nem _PROV_DESTINO_VARIANCIA) — "
            "defina o destino antes de resolver; não roteia pra 5.6.10 por falta de alternativa"
            % (codigo_provisao, saldo))
    if destino_cod == "5.6.10":
        _LOG.warning(
            "resolver_saldo_provisao: %s,%s projeto=%s conta=%s saldo=%.2f — gravando em 5.6.10 "
            "(Ajustes de Reconciliação) DE PROPÓSITO. Confirme que é diferença sem origem "
            "identificável, não rota padrão de quem não tem destino.",
            owner_tipo, owner_id, projeto_id, codigo_provisao, saldo)
    destino = _conta_por_codigo(db, owner_tipo, owner_id, destino_cod)
    if saldo > 0:   # sobra: mesma conta do destino, crédito (reduz o que foi debitado antes)
        return lancar(db, owner_tipo, owner_id, prov.id, destino.id, saldo, data=data, projeto_id=projeto_id,
                      origem=_ORIGEM_RESOL_SOBRA,
                      historico="Ajuste de provisão (sobra → %s)" % destino_cod, ref=ref)
    return lancar(db, owner_tipo, owner_id, destino.id, prov.id, -saldo, data=data, projeto_id=projeto_id,
                  origem=_ORIGEM_RESOL_FALTA,
                  historico="Ajuste de provisão (falta → %s)" % destino_cod, ref=ref)


def reconciliacao(db, owner_tipo, owner_id, projeto_id=None, ini=None, fim=None):
    """Reconciliação de provisões (Provisionado × Efetivado × Saldo × Destino), data-driven sobre o grupo
    de provisões (exclui as de tratamento próprio). `projeto_id=None` → consolidado (todos os projetos);
    `projeto_id=X` → granular. Fonte única = razão: provisionado = créditos (constituição), efetivado =
    débitos (efetivação real), saldo = prov − efet; `resolvido` = o que já foi mandado ao resultado (as
    resoluções são excluídas de provisionado/efetivado p/ não contaminar)."""
    seed_plano(db, owner_tipo, owner_id)
    contas = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
              .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%")).order_by(Conta.codigo).all())
    tl = lambda cod, lado, **kw: total_lancado(db, owner_tipo, owner_id, cod, lado, projeto_id, **kw)
    provs = []
    for c in contas:
        if c.codigo in _PROV_PAINEL_EXCLUI:
            continue
        # provisionado = créditos (constituição + reclass-IN) − reclass-OUT; efetivado = débitos de custo
        # real (exclui resolução e reclassificação, que são passivo×passivo, não efetivação).
        provisionado = round(tl(c.codigo, "credito", excluir_origens={_ORIGEM_RESOL_FALTA})
                             - tl(c.codigo, "debito", origens={_ORIGEM_RECLASS}), 2)
        efetivado = tl(c.codigo, "debito", excluir_origens={_ORIGEM_RESOL_SOBRA, _ORIGEM_RECLASS})
        resolvido_sobra = tl(c.codigo, "debito", origens={_ORIGEM_RESOL_SOBRA})
        resolvido_falta = tl(c.codigo, "credito", origens={_ORIGEM_RESOL_FALTA})
        resolvido = round(resolvido_sobra + resolvido_falta, 2)
        saldo = round(provisionado - efetivado, 2)
        # saldo_aberto (líquido) = o que ainda falta resolver. `resolvido` é magnitude positiva nos dois
        # casos; sobra (saldo>0) e falta (saldo<0) reduzem o bruto em direções opostas → desconta na direção
        # do sinal do saldo. (Painel exibe este como "Saldo"; saldo/resolvido ficam p/ auditoria.)
        saldo_aberto = round(saldo - resolvido if saldo > 0 else (saldo + resolvido if saldo < 0 else 0.0), 2)
        # resolvido_liquido = mesma magnitude de `resolvido`, com sinal (positivo=sobra/receita,
        # negativo=falta/despesa) — só para exibição (cor/sinal na UI); `resolvido` acima permanece
        # magnitude p/ não quebrar saldo_aberto nem os testes que já dependem dele.
        resolvido_liquido = round(resolvido_sobra - resolvido_falta, 2)
        # ACHADO-32 (docs/db/TAREFA_CONCILIACAO_UI.md, item 1): a flag que decide se a linha pode
        # oferecer Efetivar/Resolver genérico sai daqui — a MESMA constante que
        # `/api/financeiro/resolver-saldo-provisao` usa pra recusar (main.py:10279). Duplicar a
        # lista de códigos no JavaScript recriaria o defeito (servidor e tela podendo divergir de
        # novo na próxima mudança de regra) — por isso a tela só LÊ este campo, nunca lista os
        # códigos ela mesma.
        exige_veredito = c.codigo not in _PROV_FORA_DO_VEREDITO
        # Só importa pro tooltip da rota genérica (as duas exceções); calculado pra toda linha por
        # uniformidade, sem custo — não é usado quando exige_veredito é True.
        resolucao_tipo = None
        resolucao_destino_nome = None
        if c.codigo in _PROV_DESTINO_VARIANCIA:
            resolucao_tipo = "destino_variancia"
            destino_cod = _PROV_DESTINO_VARIANCIA[c.codigo]
            destino_conta = _conta_por_codigo(db, owner_tipo, owner_id, destino_cod)
            resolucao_destino_nome = destino_conta.codigo + " " + destino_conta.nome
        elif _ativo_diferido_de(c.codigo) in _PROV_DESPESA_POR_ATIVO:
            resolucao_tipo = "tempo_real"
        provs.append({"codigo": c.codigo, "nome": c.nome, "tipo": _PROV_PAINEL_TIPO.get(c.codigo, "O"),
                      "provisionado": provisionado, "efetivado": efetivado,
                      "saldo": saldo, "resolvido": resolvido, "resolvido_liquido": resolvido_liquido,
                      "saldo_aberto": saldo_aberto, "exige_veredito": exige_veredito,
                      "resolucao_tipo": resolucao_tipo,
                      "resolucao_destino_nome": resolucao_destino_nome})
    t = lambda k: round(sum(p[k] for p in provs), 2)
    return {"projeto_id": projeto_id, "provisoes": provs,
            "totais": {"provisionado": t("provisionado"), "efetivado": t("efetivado"),
                       "saldo": t("saldo"), "resolvido": t("resolvido"),
                       "resolvido_liquido": t("resolvido_liquido"), "saldo_aberto": t("saldo_aberto")}}


def provisoes_em_aberto(db, owner_tipo, owner_id):
    """Fila de provisões (F2-3, docs/db/TAREFA_FILA_PROVISOES.md) — a PORTA DA FRENTE do
    veredito: toda provisão em aberto, por projeto, fora da Conciliação Final. Dona: a
    assistente administrativa da loja (decisão do Marcelo, 31/08) — quem tem o pedido e a nota
    da fábrica na mão pra responder "ainda há despesa a realizar?".

    Mesma exclusão de `conciliar_final`: `_PROV_PAINEL_EXCLUI` (sem mecanismo ativo) e
    `_PROV_FORA_DO_VEREDITO` (Impostos/Custo Financeiro, rota própria, ACHADO-01) nunca entram
    na fila — dar veredito nelas é recusado por `resolver_veredito_provisao`.

    `constituida_em` = data do lançamento mais antigo que tocou a rubrica NESTE projeto — só
    para "há quanto tempo está aberta" na tela; não entra em nenhum cálculo de saldo."""
    seed_plano(db, owner_tipo, owner_id)
    excluir = _PROV_PAINEL_EXCLUI | _PROV_FORA_DO_VEREDITO
    contas = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
              .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%")).all())
    conta_ids = {c.id: c for c in contas if c.codigo not in excluir}
    if not conta_ids:
        return []
    ids = list(conta_ids.keys())
    linhas = (db.query(Lancamento.projeto_id, Lancamento.conta_debito_id,
                       Lancamento.conta_credito_id, Lancamento.data)
                .filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
                .filter(Lancamento.projeto_id.isnot(None))
                .filter((Lancamento.conta_debito_id.in_(ids)) | (Lancamento.conta_credito_id.in_(ids)))
                .all())
    projetos_por_conta = {}   # conta_id -> {projeto_id, ...}
    constituida_em = {}       # (projeto_id, conta_id) -> data mais antiga
    for projeto_id, deb_id, cred_id, data in linhas:
        for cid in (deb_id, cred_id):
            if cid in conta_ids:
                projetos_por_conta.setdefault(cid, set()).add(projeto_id)
                chave = (projeto_id, cid)
                if chave not in constituida_em or data < constituida_em[chave]:
                    constituida_em[chave] = data

    projetos = sorted({p for ps in projetos_por_conta.values() for p in ps})
    fila = []
    for projeto_id in projetos:
        rec = reconciliacao(db, owner_tipo, owner_id, projeto_id=projeto_id)
        for p in rec["provisoes"]:
            if p["codigo"] in excluir or abs(p["saldo_aberto"]) < 0.005:
                continue
            cid = next((k for k, c in conta_ids.items() if c.codigo == p["codigo"]), None)
            fila.append({
                "projeto_id": projeto_id, "codigo": p["codigo"], "nome": p["nome"],
                "provisionado": p["provisionado"], "efetivado": p["efetivado"],
                "saldo_aberto": p["saldo_aberto"],
                # ACHADO-41: derivado, não uma cópia — mesma função que resolver_veredito_provisao
                # chama pra recusar.
                "vereditos_validos": vereditos_validos_para_saldo(p["saldo_aberto"]),
                "constituida_em": constituida_em.get((projeto_id, cid)),
            })
    fila.sort(key=lambda r: (r["constituida_em"] is None, r["constituida_em"]))
    return fila


_VEREDITOS_VALIDOS = {"efetivada", "encerrada_valor_menor", "nao_se_aplica", "ainda_vai_chegar"}


def vereditos_validos_para_saldo(saldo):
    """ACHADO-41 (docs/db/ACHADOS_CONTABEIS.md) — os MESMOS limites que `resolver_veredito_
    provisao` usa pra recusar, chamados por ela abaixo (não uma cópia paralela que possa
    divergir). A Fila de Provisões usa isto pra desenhar só os botões que o backend aceitaria —
    nunca os quatro sempre, com dois recusando na cara do operador conforme o sinal do saldo.

    `saldo` = provisionado − efetivado, líquido de resoluções anteriores (mesma convenção de
    `reconciliacao()['provisoes'][i]['saldo_aberto']` — testado idêntico a `_mov(...,'credor',...)`
    pro mesmo projeto/conta). 'ainda_vai_chegar' nunca é recusado. saldo ≤ 0,005 (FALTA ou zero):
    'efetivada'. saldo ≥ −0,005 (SOBRA ou zero): 'encerrada_valor_menor'/'nao_se_aplica'."""
    saldo = round(float(saldo or 0), 2)
    validos = ["ainda_vai_chegar"]
    if saldo <= 0.005:
        validos.append("efetivada")
    if saldo >= -0.005:
        validos.append("encerrada_valor_menor")
        validos.append("nao_se_aplica")
    return validos


def resolver_veredito_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao, veredito, ref,
                               valor_efetivado=None, motivo=None, decidido_por_id=None, data=None,
                               forma_pagamento="a_prazo"):
    """Resolve o saldo aberto de uma provisão por um VEREDITO NOMEADO (ACHADO-16, docs/db/
    TAREFA_ACHADO16.md, passo 8) — nunca mais o cancelamento silencioso que `resolver_saldo_
    provisao` fazia sozinho quando chamado direto pela Conciliação Final. Registra o veredito em
    `VeredictoProvisao` (quem decidiu, quando, com qual motivo) e aplica o efeito certo no livro:

    - **"efetivada"** — só para FALTA (saldo < 0, efetivado > provisionado): a despesa real já
      foi reconhecida A CADA EFETIVAÇÃO ao longo do projeto; só falta o residual MECÂNICO entre
      ativo e provisão, que `resolver_saldo_provisao` já cancela sem tocar a DRE (essa metade do
      desenho original continua certa — o achado era só a SOBRA nunca efetivada).
    - **"encerrada_valor_menor"** — só para SOBRA (saldo > 0): DUAS pernas, nesta ordem —
      (1) `efetivar_provisao(valor_efetivado)` reconhece o custo REAL (5.x × ativo diferido, e
      debita a própria provisão); (2) só então, se sobrar resíduo, `resolver_saldo_provisao`
      reverte o QUE FALTOU (a sobra genuína, sem tocar a DRE de novo). Reverter sem efetivar
      primeiro reproduziria o ACHADO-16 com outro nome.
    - **"nao_se_aplica"** — só para SOBRA: reverte o saldo INTEIRO como sobra (nenhuma despesa
      reconhecida — a rubrica nunca incidiu neste projeto). Exige `motivo` escrito; recusa sem
      ele.
    - **"ainda_vai_chegar"** — não resolve nada no livro. Ainda assim fica registrado (quem disse
      "ainda vai chegar" e quando) — é decisão, não silêncio. Quem chama (`conciliar_final`) é
      quem decide que isto barra o fechamento do projeto.

    Custo Financeiro (2.1.04.19) e Impostos (2.1.04.13) são RECUSADOS aqui — não seguem a regra
    de reversão (ACHADO-01: o deságio já foi retido na origem, não há despesa futura; aplicar a
    regra de custo neles reintroduz o erro que o ACHADO-01 registra). Idempotente por `ref`."""
    if not (codigo_provisao or "").startswith(GRUPO_PROVISOES + ".") or codigo_provisao in _PROV_PAINEL_EXCLUI:
        raise ValueError(
            "resolver_veredito_provisao: %r não é conta de provisão legítima (grupo %s.x, exceto %s)"
            % (codigo_provisao, GRUPO_PROVISOES, sorted(_PROV_PAINEL_EXCLUI)))
    if codigo_provisao in _PROV_FORA_DO_VEREDITO:
        raise ValueError(
            "resolver_veredito_provisao: %s não segue a regra de veredito/reversão (ACHADO-01) — "
            "impostos e custo financeiro têm rota própria, fora da Conciliação Final." % codigo_provisao)
    if veredito not in _VEREDITOS_VALIDOS:
        raise ValueError("veredito inválido: %r (válidos: %s)" % (veredito, sorted(_VEREDITOS_VALIDOS)))
    existente = (db.query(VeredictoProvisao)
                   .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, ref=ref).first())
    if existente is not None:
        return existente
    seed_plano(db, owner_tipo, owner_id)
    saldo = round(_mov(db, owner_tipo, owner_id, codigo_provisao, "credor", None, None, projeto_id=projeto_id), 2)

    valor_ef, valor_rev = None, None
    if veredito == "ainda_vai_chegar":
        pass   # não toca o livro — quem chama decide que isto barra o fechamento
    elif veredito == "efetivada":
        if veredito not in vereditos_validos_para_saldo(saldo):
            raise ValueError(
                "%s tem SOBRA de %.2f (não FALTA) — 'efetivada' só vale quando o efetivado já "
                "supera o provisionado; escolha 'encerrada_valor_menor' ou 'nao_se_aplica'."
                % (codigo_provisao, saldo))
        resolver_saldo_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao,
                               ref=ref + ":residual", data=data)
    elif veredito in ("encerrada_valor_menor", "nao_se_aplica"):
        if veredito not in vereditos_validos_para_saldo(saldo):
            raise ValueError(
                "%s está em FALTA (%.2f) — '%s' só vale para SOBRA (provisionado > efetivado); "
                "o veredito certo aqui é 'efetivada'." % (codigo_provisao, saldo, veredito))
        if veredito == "nao_se_aplica":
            if not (motivo or "").strip():
                raise ValueError("veredito 'nao_se_aplica' exige motivo escrito.")
            resolver_saldo_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao,
                                   ref=ref + ":reverte", data=data)
            valor_ef, valor_rev = 0.0, saldo
        else:
            # valor_efetivado == 0 é válido: cobre a rubrica que já foi efetivada mais cedo NO
            # PROJETO (fora desta chamada) e chega aqui só com o resíduo a reverter — não exige
            # reinventar um valor novo pra "confirmar" o que o livro já tem. `efetivar_provisao`
            # já no-opa sozinho pra valor<=0 (idempotência dela mesma), então não precisa de
            # guarda extra aqui além do teto do saldo aberto.
            valor_efetivado = round(float(valor_efetivado or 0), 2)
            if valor_efetivado < 0 or valor_efetivado > saldo + 0.005:
                raise ValueError(
                    "valor_efetivado precisa ser >= 0 e <= saldo aberto (%.2f) — recebido %r"
                    % (saldo, valor_efetivado))
            efetivar_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao, valor_efetivado,
                              ref=ref + ":efetiva", data=data, forma_pagamento=forma_pagamento)
            residual = round(saldo - valor_efetivado, 2)
            if residual > 0.005:
                resolver_saldo_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao,
                                       ref=ref + ":reverte", data=data)
            valor_ef, valor_rev = valor_efetivado, (residual if residual > 0.005 else 0.0)

    v = VeredictoProvisao(owner_tipo=owner_tipo, owner_id=owner_id, projeto_nome=projeto_id,
                         codigo_provisao=codigo_provisao, veredito=veredito,
                         valor_provisionado=saldo, valor_efetivado=valor_ef,
                         valor_revertido=valor_rev, motivo=motivo,
                         decidido_por_id=decidido_por_id, ref=ref)
    if data is not None:
        v.decidido_em = data
    db.add(v)
    db.flush()
    return v


def resolver_por_ato_nomeado(db, owner_tipo, owner_id, projeto_id, codigo_provisao, origem, ref,
                            decidido_por_id=None, data=None):
    """ACHADO-34 (docs/db/ACHADOS_CONTABEIS.md) — porta ÚNICA para resolver o saldo de uma provisão
    por um ATO NOMEADO que acontece FORA da Conciliação Final. Hoje o único chamador é o pagamento
    da folha (`mod_folha.pagar`, comissão de venda 2.1.04.12), que é o caso real medido em 01/09 —
    mas o achado registra que ele não é o único possível, e é por isso que esta função é genérica:
    o próximo mecanismo que zerar uma provisão antes do fechamento tem uma porta certa pra usar,
    em vez de chamar `resolver_saldo_provisao` direto e sumir do rastro.

    **O defeito que ela fecha.** `conciliar_final` monta a lista de rubricas que exigem veredito
    olhando quem AINDA TEM SALDO ABERTO naquele momento. Quem zera o saldo antes atravessa a
    exigência inteira sem nunca passar por ela, e o `relatorio_projetos_encerrados_por_reversao`
    fica cego a esses projetos — não existe `VeredictoProvisao` nenhum pra listar. Resolver o livro
    sem deixar decisão escrita é exatamente o silêncio que o ACHADO-16 tirou da Conciliação Final;
    aqui ele tinha voltado por uma porta lateral.

    **O efeito no livro é IDÊNTICO ao de `resolver_saldo_provisao` chamado sozinho** — é o mesmo
    caminho, alcançado pela porta que registra quem decidiu. O que muda é o rastro, não a
    contabilidade; é o que os aceites de `tests/test_achado34_veredito_da_folha.py` provam conta a
    conta. A DECISÃO do Marcelo (03/09) foi esta: a folha grava um veredito nomeado, em vez de ser
    reconhecida por escrito como uma segunda forma legítima de veredito.

    **O veredito sai do SINAL do saldo, derivado de `vereditos_validos_para_saldo`** — a mesma
    função que `resolver_veredito_provisao` usa pra recusar (ACHADO-41: nunca uma segunda cópia dos
    limites, que divergiria sozinha depois). FALTA ou zero → 'efetivada' (a despesa real já foi
    reconhecida na efetivação que precede esta chamada; sobra o residual mecânico). SOBRA →
    'encerrada_valor_menor' com `valor_efetivado=0`, que é o caso que o próprio
    `resolver_veredito_provisao` documenta: a rubrica já foi efetivada mais cedo NO PROJETO, fora
    desta chamada, e chega aqui só com o resíduo a reverter.

    `origem` descreve o ato que decidiu ("folha:123 competência 2026-07") e vai para o `motivo` do
    veredito — `VeredictoProvisao` não tem coluna `origem`, e criar uma custaria migration para
    guardar o que o campo escrito já guarda. Idempotente por `ref`, como toda a família."""
    saldo = round(_mov(db, owner_tipo, owner_id, codigo_provisao, "credor", None, None,
                       projeto_id=projeto_id), 2)
    if "efetivada" in vereditos_validos_para_saldo(saldo):
        veredito, valor_efetivado = "efetivada", None
    else:
        veredito, valor_efetivado = "encerrada_valor_menor", 0.0
    return resolver_veredito_provisao(db, owner_tipo, owner_id, projeto_id, codigo_provisao,
                                      veredito, ref, valor_efetivado=valor_efetivado,
                                      motivo=origem, decidido_por_id=decidido_por_id, data=data)


def conciliar_final(db, owner_tipo, owner_id, projeto_id, ref_base, vereditos, decidido_por_id=None, data=None):
    """FASE D2 — Conciliação Final (etapa 21). ACHADO-16 (docs/db/TAREFA_ACHADO16.md, passo 8):
    não fecha mais o projeto com provisão em aberto sem decisão — cada rubrica de custo do
    projeto (as 15 de matching pleno; Impostos e Custo Financeiro ficam de fora, rota própria)
    que tiver saldo aberto exige um veredito em `vereditos` ({codigo: {"veredito":,
    "valor_efetivado":, "motivo":, "forma_pagamento":}}).

    RECUSA (`ValueError`, tudo ou nada — nada é commitado, quem chama já faz rollback no
    `except`) em dois casos, ANTES de tocar qualquer lançamento:
    - falta veredito para alguma rubrica aberta;
    - alguma rubrica recebeu 'ainda_vai_chegar' — o projeto continua honestamente aberto.

    Idempotente por ref (`ref_base:<codigo>`). Retorna {codigo: {"veredito":, "valor_efetivado":,
    "valor_revertido":}} — descreve O QUE aconteceu, não só o saldo residual (a API não
    responde mais `{"resolvido": {...}}` sem dizer qual veredito foi dado, por quem)."""
    seed_plano(db, owner_tipo, owner_id)
    excluir = _PROV_PAINEL_EXCLUI | _PROV_FORA_DO_VEREDITO   # ACHADO-01 — rota própria, fora da regra de veredito
    contas = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
              .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%")).order_by(Conta.codigo).all())
    abertas = []
    for c in contas:
        if c.codigo in excluir:
            continue
        saldo = round(_mov(db, owner_tipo, owner_id, c.codigo, "credor", None, None, projeto_id=projeto_id), 2)
        if abs(saldo) >= 0.005:
            abertas.append(c.codigo)

    vereditos = vereditos or {}
    faltando = sorted(cod for cod in abertas if cod not in vereditos)
    if faltando:
        # F2-3 (docs/db/TAREFA_FILA_PROVISOES.md, Parte 3): a mensagem passou a dizer ONDE
        # resolver — a Conciliação Final não ganha campo de veredito nenhum, a Fila de
        # Provisões é a porta da frente (ACHADO-26).
        raise ValueError(
            "Conciliação Final recusada: falta veredito para %s — toda provisão em aberto "
            "precisa de um veredito nomeado antes do projeto fechar. Resolva na Fila de "
            "Provisões (Financeiro → Fila de Provisões) e tente novamente." % ", ".join(faltando))
    ainda_vai_chegar = sorted(cod for cod in abertas if vereditos[cod].get("veredito") == "ainda_vai_chegar")
    if ainda_vai_chegar:
        raise ValueError(
            "Conciliação Final recusada: %s ainda vai chegar — o projeto continua aberto até a "
            "despesa real ser lançada." % ", ".join(ainda_vai_chegar))

    out = {}
    for cod in abertas:
        info = vereditos[cod]
        v = resolver_veredito_provisao(
            db, owner_tipo, owner_id, projeto_id, cod, info["veredito"], ref=ref_base + ":" + cod,
            valor_efetivado=info.get("valor_efetivado"), motivo=info.get("motivo"),
            decidido_por_id=decidido_por_id, data=data,
            forma_pagamento=info.get("forma_pagamento") or "a_prazo")
        out[cod] = {"veredito": v.veredito, "valor_efetivado": v.valor_efetivado,
                   "valor_revertido": v.valor_revertido}
    return out


def relatorio_projetos_encerrados_por_reversao(db, owner_tipo, owner_id):
    """Controle contra o veredito virar formalidade (ACHADO-16, docs/db/TAREFA_ACHADO16.md, passo
    8): reversão de resíduo MELHORA a margem — um projeto que fecha com reversão grande é
    exatamente o que se quer olhar. Lista, por projeto, o total revertido ('encerrada_valor_menor'
    + 'nao_se_aplica') e os motivos ao lado, ordenado do MAIOR valor revertido pro menor."""
    linhas = (db.query(VeredictoProvisao)
                .filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
                .filter(VeredictoProvisao.veredito.in_(("encerrada_valor_menor", "nao_se_aplica")))
                .order_by(VeredictoProvisao.projeto_nome, VeredictoProvisao.id).all())
    por_projeto = {}
    for v in linhas:
        p = por_projeto.setdefault(v.projeto_nome, {"projeto_nome": v.projeto_nome,
                                                     "valor_revertido_total": 0.0, "rubricas": []})
        revertido = round(float(v.valor_revertido or 0), 2)
        p["valor_revertido_total"] = round(p["valor_revertido_total"] + revertido, 2)
        p["rubricas"].append({"codigo_provisao": v.codigo_provisao, "veredito": v.veredito,
                              "valor_efetivado": v.valor_efetivado, "valor_revertido": revertido,
                              "motivo": v.motivo, "decidido_por_id": v.decidido_por_id,
                              "decidido_em": v.decidido_em.strftime("%Y-%m-%d %H:%M") if v.decidido_em else None})
    out = sorted(por_projeto.values(), key=lambda p: p["valor_revertido_total"], reverse=True)
    return out


# ── Conciliação de PE/AF2 — Crédito a Clientes (Estorno) — spec 2026-08-14 ───────────────────
def registrar_credito_cliente(db, owner_tipo, owner_id, projeto_id, valor, ref, data=None, historico=None):
    """Lançamento A — imediato, no clique "Aprovar" o Estorno na AF2 (11d). DR 4.3.02 (Devolução
    de Vendas) × CR 2.1.11 (Créditos a Clientes) — fica em aberto até baixa manual
    (`baixar_credito_cliente`). Idempotente por `ref`. NUNCA se compensa automaticamente com o
    Complemento de Projeto (Cobrar) — mecanismos deliberadamente separados (decisão do usuário)."""
    if valor is None or float(valor) <= 0:
        raise ValueError("valor deve ser > 0")
    return registrar_evento(db, owner_tipo, owner_id, "estorno_credito_cliente", valor,
                            projeto_id=projeto_id, data=data, ref=ref, historico=historico)


def saldo_credito_cliente(db, owner_tipo, owner_id, projeto_id):
    """Saldo em aberto de Créditos a Clientes (2.1.11) do projeto — nunca abaixo de 0. Fora do
    grupo Provisões (2.1.04) de propósito: `conciliar_final` (etapa 21) não varre esta conta, o
    projeto pode fechar com saldo pendente aqui (evento futuro, sem prazo)."""
    saldo = round(total_lancado(db, owner_tipo, owner_id, "2.1.11", "credito", projeto_id)
                 - total_lancado(db, owner_tipo, owner_id, "2.1.11", "debito", projeto_id), 2)
    return max(saldo, 0.0)


def baixar_credito_cliente(db, owner_tipo, owner_id, projeto_id, valor, destino, ref, data=None):
    """Lançamento B — evento futuro e manual (o gerente adm/fin decide quando tratar). `destino`:
    'receber' (abate Contas a Receber — inclusive um Complemento de Projeto futuro, por
    tratamento manual e paralelo, nunca automático) ou 'caixa' (devolvido em dinheiro). Capado ao
    saldo em aberto do crédito do projeto. Idempotente por `ref`. Retorna None se não sobrar
    saldo pra baixar após o cap."""
    if destino not in ("receber", "caixa"):
        raise ValueError("destino deve ser 'receber' ou 'caixa'")
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    mv = round(min(float(valor or 0), saldo_credito_cliente(db, owner_tipo, owner_id, projeto_id)), 2)
    if mv <= 0:
        return None
    evento = "baixa_credito_cliente_receber" if destino == "receber" else "baixa_credito_cliente_caixa"
    return registrar_evento(db, owner_tipo, owner_id, evento, mv, projeto_id=projeto_id, data=data, ref=ref)


_ORIGEM_DEVOLUCAO = "devolucao"


def _ativo_diferido_de(prov_cod):
    """Ativo diferido correspondente a uma provisão: 2.1.04.13 (impostos) → 1.1.05; demais → 1.1.06.<sufixo>."""
    if prov_cod == "2.1.04.13":
        return "1.1.05"
    return "1.1.06." + prov_cod.rsplit(".", 1)[-1]


def devolver_venda(db, owner_tipo, owner_id, projeto_id, fracao, ref_base, data=None,
                   origem=_ORIGEM_DEVOLUCAO, rotulo="Devolução"):
    """#D — devolução (parcial/total) da venda: reverte PROPORCIONALMENTE a constituição DIFERIDA (antes da
    entrega/NF-e). `fracao` (0<f<=1) = parte devolvida (por ambiente/parcela — fração #5). Reverte:
      - Receita a Realizar: DR 2.1.06 × CR 1.1.02 (reduz receita diferida + recebível);
      - cada provisão do grupo com ativo diferido (operacionais + impostos 2.1.04.13/1.1.05 + custos
        adicionais + custo financeiro): DR provisão × CR ativo, por f × min(provisão, ativo em aberto).
    A despesa JÁ reconhecida na NF-e (móvel entregue — custo real incorrido) NÃO reverte (ativo já baixado
    → mv=0). Idempotente por ref_base. Retorna {conta: valor_revertido}.
    (Revenda de item entregue → estorno de receita reconhecida em 4.3.02 fica p/ extensão futura.)"""
    f = round(float(fracao or 0), 6)
    if f <= 0:
        return {}
    seed_plano(db, owner_tipo, owner_id)
    out = {}
    # 1) Receita a Realizar × Contas a Receber
    ref_r = ref_base + ":receita"
    if lancamento_por_ref(db, owner_tipo, owner_id, ref_r) is None:
        saldo_rar = round(_mov(db, owner_tipo, owner_id, "2.1.06", "credor", None, None, projeto_id=projeto_id), 2)
        mv = round(f * max(saldo_rar, 0.0), 2)
        if mv > 0:
            rar = _conta_por_codigo(db, owner_tipo, owner_id, "2.1.06")
            rec = _conta_por_codigo(db, owner_tipo, owner_id, "1.1.02")
            lancar(db, owner_tipo, owner_id, rar.id, rec.id, mv, data=data, projeto_id=projeto_id,
                   origem=origem, historico="%s — estorno de Receita a Realizar" % rotulo, ref=ref_r)
            out["2.1.06"] = mv
    # 2) provisões diferidas × ativos
    contas = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
              .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%")).order_by(Conta.codigo).all())
    for c in contas:
        ativo_cod = _ativo_diferido_de(c.codigo)
        if not _conta_existe(db, owner_tipo, owner_id, ativo_cod):
            continue
        ref_c = ref_base + ":" + c.codigo
        if lancamento_por_ref(db, owner_tipo, owner_id, ref_c) is not None:
            continue
        prov_saldo = round(_mov(db, owner_tipo, owner_id, c.codigo, "credor", None, None, projeto_id=projeto_id), 2)
        ativo_saldo = round(total_lancado(db, owner_tipo, owner_id, ativo_cod, "debito", projeto_id)
                            - total_lancado(db, owner_tipo, owner_id, ativo_cod, "credito", projeto_id), 2)
        mv = round(f * min(max(prov_saldo, 0.0), max(ativo_saldo, 0.0)), 2)
        if mv <= 0:
            continue
        prov = _conta_por_codigo(db, owner_tipo, owner_id, c.codigo)
        ativo = _conta_por_codigo(db, owner_tipo, owner_id, ativo_cod)
        lancar(db, owner_tipo, owner_id, prov.id, ativo.id, mv, data=data, projeto_id=projeto_id,
               origem=origem, historico="%s — estorno de provisão diferida (%s)" % (rotulo, c.codigo), ref=ref_c)
        out[c.codigo] = mv
    return out


_ORIGEM_CANCELAMENTO = "cancelamento_contrato"


def cancelar_contrato(db, owner_tipo, owner_id, projeto_id, ref_base, data=None):
    """Cancelamento de contrato (dentro do prazo, ANTES da NF-e): estorna TODA a constituição do contrato,
    deixando o razão como se ele não tivesse ocorrido. Reusa `devolver_venda(f=1.0)` (Receita a Realizar +
    provisões×ativos diferidos) com origem/rótulo próprios (distingue de devolução no razão) e adiciona o
    estorno dos juros a apropriar do ramo loja (`reverter_juros_direto`, 2.1.07 × 1.1.07). Idempotente por
    ref_base. **Bloqueio pós-NF-e** é do chamador (endpoint). O reembolso físico de valores já recebidos
    (1.1.02 fica CREDOR = a devolver) é tratado pela Tesouraria (módulo futuro). Retorna {conta: valor}."""
    out = devolver_venda(db, owner_tipo, owner_id, projeto_id, 1.0, ref_base=ref_base + ":estorno",
                         data=data, origem=_ORIGEM_CANCELAMENTO, rotulo="Cancelamento")
    ref_j = ref_base + ":juros"
    if lancamento_por_ref(db, owner_tipo, owner_id, ref_j) is None:
        saldo_juros = round(total_lancado(db, owner_tipo, owner_id, "1.1.07", "debito", projeto_id)
                            - total_lancado(db, owner_tipo, owner_id, "1.1.07", "credito", projeto_id), 2)
        if saldo_juros > 0:
            registrar_evento(db, owner_tipo, owner_id, "reverter_juros_direto", saldo_juros,
                             projeto_id=projeto_id, ref=ref_j)
            out["1.1.07"] = saldo_juros
    return out


def contas_a_pagar(db, owner_tipo, owner_id, projeto_id=None, ini=None, fim=None):
    """Contas a Pagar (MVP, FASE D): obrigações com fornecedores em aberto = saldo de Fornecedores a
    Pagar (2.1.01), escopado por projeto (None = consolidado). Derivado do razão — o sub-razão de títulos
    (fornecedor/vencimento) é fase futura."""
    total = _mov(db, owner_tipo, owner_id, "2.1.01", "credor", ini, fim, projeto_id=projeto_id)
    return {"projeto_id": projeto_id, "total_em_aberto": round(total, 2)}


def provisao_projetos(db, owner_tipo, owner_id, codigo, ini=None, fim=None):
    """Discrimina UMA conta de provisão por PROJETO: provisionado/efetivado/saldo + detalhe por ORIGEM
    (cada evento que tocou a conta, com débito/crédito e histórico). Alimenta o modal 'clicar na
    provisão' do painel de Provisões."""
    from sqlalchemy import or_
    conta = _conta_por_codigo(db, owner_tipo, owner_id, codigo)
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).filter(
        or_(Lancamento.conta_debito_id == conta.id, Lancamento.conta_credito_id == conta.id))
    projs = {}
    for l in _filtra_periodo(q, ini, fim).all():
        pid = l.projeto_id or "(sem projeto)"
        p = projs.setdefault(pid, {"projeto_id": pid, "por_origem": {}})
        o = p["por_origem"].setdefault(l.origem or "(manual)", {"debito": 0.0, "credito": 0.0, "historico": l.historico})
        if l.conta_debito_id == conta.id:
            o["debito"] = round(o["debito"] + l.valor, 2)
        else:
            o["credito"] = round(o["credito"] + l.valor, 2)
    out = []
    for pid, p in projs.items():
        # mesma regra da reconciliacao: provisionado = créditos (excl. resol_falta) − reclass-out;
        # efetivado = débitos de custo real (excl. resol_sobra e reclass).
        prov = round(sum(o["credito"] for org, o in p["por_origem"].items() if org != _ORIGEM_RESOL_FALTA)
                     - sum(o["debito"] for org, o in p["por_origem"].items() if org == _ORIGEM_RECLASS), 2)
        efet = round(sum(o["debito"] for org, o in p["por_origem"].items()
                         if org not in (_ORIGEM_RESOL_SOBRA, _ORIGEM_RECLASS)), 2)
        out.append({"projeto_id": pid, "provisionado": prov, "efetivado": efet,
                    "saldo": round(prov - efet, 2), "por_origem": p["por_origem"]})
    out.sort(key=lambda x: x["projeto_id"])
    return {"codigo": codigo, "nome": conta.nome,
            "totais": {"provisionado": round(sum(p["provisionado"] for p in out), 2),
                       "efetivado": round(sum(p["efetivado"] for p in out), 2),
                       "saldo": round(sum(p["saldo"] for p in out), 2)},
            "projetos": out}


# ── Provisões da venda: % configurável + auto-constituição no fechamento (v6 §6.4) ──
_PROV_VENDA = {   # chave -> (evento de constituição, código da conta de Provisão no Passivo)
    "montagem":    ("fechamento_venda_montagem",    "2.1.04.02"),
    "assistencia": ("fechamento_venda_assistencia", "2.1.04.05"),
    "garantia":    ("fechamento_venda_garantia",    "2.1.04.03"),
}

# ── Painel de Provisões (dashboard) — DATA-DRIVEN pelo Plano de Contas (Diagramacao_v4 §1.3) ──
# Regra: um card por conta ANALÍTICA do grupo de Provisões que existir no plano — NUNCA hardcodar
# os 3 nomes como componentes fixos. Criar uma provisão nova no Plano de Contas faz surgir um card
# automaticamente, sem tocar no painel. Duas contas do grupo ficam de fora por terem tratamento
# próprio (documentado abaixo), de modo que "hoje são 3" (Montagem/Assistência/Garantia) continua
# valendo — mas por exclusão explícita, não por lista fixa das 3.
GRUPO_PROVISOES = "2.1.04"
_PROV_PAINEL_EXCLUI = {
    # ACHADO-05: o evento pagamento_comissao (que baixava esta conta) foi removido em 2026-08-29
    # — nunca foi chamado em produção. A comissão de venda real usa 2.1.04.12 (mod_folha.py). A
    # conta 2.1.04.01 segue no catálogo mas sem mecanismo algum hoje — não é set-aside de custo.
    "2.1.04.01",
    "2.1.04.04",   # Devolução — sem evento/percentual de constituição hoje (saldo sempre 0)
}
# Descrição opcional por conta (enriquece o card; cai num texto genérico se a conta não estiver aqui):
_PROV_PAINEL_SUB = {
    "2.1.04.02": "Custo direto da venda · reverte na execução",
    "2.1.04.05": "Custo da loja · reverte no atendimento",
    "2.1.04.03": "Repasse à fábrica · controle de cobrança",
}
# FASE C: TIPO A/B/C/D de cada provisão (painel agrupado). Data-driven: conta nova no grupo sem tipo
# mapeado cai em "O" (Outros), aparecendo mesmo assim — sem tocar no painel.
_PROV_PAINEL_TIPO = {
    "2.1.04.10": "A", "2.1.04.11": "A", "2.1.04.12": "A", "2.1.04.21": "A",   # Comissões / Pessoas
    "2.1.04.02": "B", "2.1.04.03": "B", "2.1.04.05": "B",             # Custos futuros (serviços da venda)
    "2.1.04.06": "C", "2.1.04.07": "C", "2.1.04.08": "C", "2.1.04.09": "C", "2.1.04.14": "C",   # Aquisição / Fábrica
    "2.1.04.13": "D",                                                 # Fiscal
}
_PROV_TIPO_ROTULO = {"A": "Comissões / Pessoas", "B": "Custos futuros",
                     "C": "Aquisição / Fábrica", "D": "Fiscal", "O": "Outros"}
_PROV_TIPO_ORDEM = ("A", "B", "C", "D", "O")


def _cfg_f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def pcts_provisao_venda(cfg):
    """% das 3 provisões (v6 §6.4): montagem/garantia da config nova `provisoes_contabeis`;
    **assistência herda** `provisoes.assist_pct` da negociação (não recria o dado)."""
    cfg = cfg or {}
    pc = cfg.get("provisoes_contabeis", {}) or {}
    return {"montagem": _cfg_f(pc.get("montagem_pct")),
            "assistencia": _cfg_f((cfg.get("provisoes", {}) or {}).get("assist_pct")),
            "garantia": _cfg_f(pc.get("garantia_pct"))}


def constituir_provisoes_venda(db, owner_tipo, owner_id, projeto_id, vavo, cfg, ref_base):
    """Auto-constitui as 3 provisões no fechamento da venda (v6 §6.4): valor = % × VAVO (valor à vista —
    convenção canônica de base das provisões % sobre a venda, DEPOIS de extrair o Cust_Fin; NÃO Val_Cont,
    senão diverge da linha da modal/motor). Idempotente por `ref` (ref_base:<chave>). Só constitui % > 0."""
    pcts = pcts_provisao_venda(cfg)
    out = []
    for chave, (evento, _cod) in _PROV_VENDA.items():
        val = round(_cfg_f(vavo) * pcts[chave] / 100.0, 2)
        if val > 0:
            out.append(registrar_evento(db, owner_tipo, owner_id, evento, val,
                                        projeto_id=projeto_id, ref=ref_base + ":" + chave))
    return out


def contas_provisao_do_plano(db, owner_tipo, owner_id, ini=None, fim=None):
    """Contas ANALÍTICAS do grupo de Provisões (GRUPO_PROVISOES) presentes no plano, data-driven,
    cada uma com o saldo EM ABERTO. Exclui as de tratamento próprio (_PROV_PAINEL_EXCLUI). Fonte
    única do painel de Provisões (dashboard) e reusável (individualização por projeto, etc.).
    Assume o plano já semeado (o dashboard chama seed_plano antes)."""
    contas = (db.query(Conta)
              .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
              .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%"))
              .order_by(Conta.codigo).all())
    out = []
    for c in contas:
        if c.codigo in _PROV_PAINEL_EXCLUI:
            continue
        out.append({"codigo": c.codigo, "nome": c.nome,
                    "sub": _PROV_PAINEL_SUB.get(c.codigo, "Saldo provisionado em aberto"),
                    "tipo": _PROV_PAINEL_TIPO.get(c.codigo, "O"),
                    "saldo_em_aberto": saldo_conta(db, owner_tipo, owner_id, c.id, ini, fim)})
    return out


def _agrupar_provisoes_por_tipo(provs):
    """Agrupa a lista de provisões por TIPO (A/B/C/D/O), na ordem canônica, com subtotal por tipo.
    Data-driven: só cria os grupos que têm ao menos uma conta."""
    grupos = {}
    for p in provs:
        grupos.setdefault(p.get("tipo", "O"), []).append(p)
    return [{"tipo": t, "rotulo": _PROV_TIPO_ROTULO.get(t, "Outros"), "itens": grupos[t],
             "subtotal": round(sum(i["saldo_em_aberto"] for i in grupos[t]), 2)}
            for t in _PROV_TIPO_ORDEM if t in grupos]


def alertas_contas_escape(db, owner_tipo, owner_id):
    """T6 (27/08/2026, revisão do banco): sinal de acompanhamento das duas contas de "escape" do
    plano — "5.4.20 Outras Despesas" (balde do que ninguém sabe classificar) e "5.6.10 Ajustes de
    Reconciliação" (só diferença sem origem identificável, desde T5). Não é notificação PUSH —
    não existe canal pra isso hoje (sem e-mail/central de avisos); é computado sob demanda,
    incluído no dashboard financeiro. Escopo: mês corrente NO FUSO DO DONO DO LIVRO (ACHADO-48,
    02/09 — era UTC sempre, discordando do calendário de quem lê o dashboard), sempre —
    independe do período que o dashboard estiver mostrando.
    - 5.4.20: dispara se passar de 1% do custo fixo do mês (soma de débito de toda conta
      ANALÍTICA com natureza_custo='fixo'). Limiar frouxo de propósito (decisão do briefing) —
      apertar depois de ver o comportamento real.
    - 5.6.10: dispara com QUALQUER lançamento no mês — por definição (T5), toda entrada aqui é
      uma diferença sem origem identificável, não deveria ser hábito."""
    agora = agora_no_fuso(db, owner_tipo, owner_id)
    ini_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    alertas = []

    c5420 = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo="5.4.20").first()
    if c5420 is not None:
        valor_5420 = _somas_por_conta(db, owner_tipo, owner_id, [c5420.id], "debito", ini_mes, agora).get(c5420.id, 0.0)
        fixos_ids = [c.id for c in db.query(Conta).filter_by(
            owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica", natureza_custo="fixo").all()]
        custo_fixo_mes = round(sum(_somas_por_conta(db, owner_tipo, owner_id, fixos_ids, "debito",
                                                     ini_mes, agora).values()), 2)
        limite = round(custo_fixo_mes * 0.01, 2)
        if custo_fixo_mes > 0 and valor_5420 > limite:
            alertas.append({"codigo": "5.4.20", "nome": c5420.nome, "tipo": "limite_pct_custo_fixo",
                            "valor_mes": round(valor_5420, 2), "limite": limite,
                            "custo_fixo_mes": custo_fixo_mes,
                            "mensagem": "Outras Despesas passou de 1% do custo fixo do mês."})

    c5610 = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo="5.6.10").first()
    if c5610 is not None:
        valor_5610 = _somas_por_conta(db, owner_tipo, owner_id, [c5610.id], "debito", ini_mes, agora).get(c5610.id, 0.0)
        if valor_5610 > 0:
            alertas.append({"codigo": "5.6.10", "nome": c5610.nome, "tipo": "qualquer_lancamento",
                            "valor_mes": round(valor_5610, 2),
                            "mensagem": "Ajustes de Reconciliação recebeu lançamento este mês "
                                        "— diferença sem origem identificável."})
    return alertas


def dashboard_financeiro(db, owner_tipo, owner_id, ini=None, fim=None):
    """Dashboard do Financeiro (Padrao_Design_Orizon_v4 §5 / Diagramacao_v4 §1.3): um card por
    provisão que EXISTIR no Plano de Contas (grupo GRUPO_PROVISOES), data-driven (via
    contas_provisao_do_plano) — nunca lista fixa de 3. Mais o resumo do DRE e o indicador de
    cobertura de caixa (v6 §6.1: caixa vs provisões)."""
    seed_plano(db, owner_tipo, owner_id)
    provs = contas_provisao_do_plano(db, owner_tipo, owner_id, ini, fim)
    total_prov = round(sum(p["saldo_em_aberto"] for p in provs), 2)
    d = dre(db, owner_tipo, owner_id, ini, fim)
    caixa_c = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo="1.1.01").first()
    caixa = saldo_conta(db, owner_tipo, owner_id, caixa_c.id, None, fim) if caixa_c else 0.0
    indice = round(caixa / total_prov, 2) if total_prov > 0 else None
    return {
        "provisoes": provs,
        "provisoes_por_tipo": _agrupar_provisoes_por_tipo(provs),   # FASE C: agrupado A/B/C/D + subtotal
        "total_provisoes_abertas": total_prov,
        "dre_resumo": {"receita_liquida": d["receita_liquida"], "ebitda": d["ebitda"],
                       "lucro_liquido": d["lucro_liquido"]},
        "cobertura_caixa": {"caixa": caixa, "provisoes_abertas": total_prov, "indice": indice},
        "alertas": alertas_contas_escape(db, owner_tipo, owner_id),   # T6: sempre do mês corrente
    }




def _norm_tokens(s):
    import re as _re, unicodedata as _u
    s = _u.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return set(_re.findall(r"[a-z0-9]{3,}", s))   # tokens de 3+ chars (sem acento)


def sugerir_conta(db, owner_tipo, owner_id, texto):
    """IA de apoio à classificação (v5 §6.3) — HEURÍSTICA (sem LLM externo): sugere uma conta
    ANALÍTICA para `texto` por sobreposição de palavras com o nome da conta + histórico de
    lançamentos similares. **NUNCA lança** — só sugere; o funcionário confirma/troca."""
    import math
    from collections import Counter
    seed_plano(db, owner_tipo, owner_id)
    toks = _norm_tokens(texto)
    if not toks:
        return None
    contas = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                                       tipo="analitica", ativa=1).all()
    conta_toks = {c.id: _norm_tokens(c.nome) for c in contas}
    # IDF: token raro (ex.: 'aluguel') pesa mais que comum (ex.: 'loja', 'conta')
    df = Counter()
    for ts in conta_toks.values():
        for t in ts:
            df[t] += 1
    n = len(contas) or 1
    idf = lambda t: math.log((n + 1) / (df.get(t, 0) + 1)) + 1.0
    peso = lambda ts: sum(idf(t) for t in (toks & ts))
    scores = {}
    for cid, ts in conta_toks.items():
        w = peso(ts)
        if w:
            scores[cid] = scores.get(cid, 0) + w * 2.0           # nome da conta
    for l in (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
              .order_by(Lancamento.id.desc()).limit(300).all()):   # histórico recente
        w = peso(_norm_tokens(l.historico))
        if w:
            for cid in (l.conta_debito_id, l.conta_credito_id):
                scores[cid] = scores.get(cid, 0) + w             # histórico similar
    if not scores:
        return None
    best_id = max(scores, key=scores.get)
    c = db.get(Conta, best_id)
    return {"conta_id": c.id, "codigo": c.codigo, "nome": c.nome, "grupo": c.grupo,
            "score": scores[best_id],
            "motivo": "heurística: sobreposição com nome da conta + histórico similar"}


def total_a_cobrar_fabrica(db, owner_tipo, owner_id, ini=None, fim=None):
    """Repasse à Fábrica (§6.2): soma dos reparos em GARANTIA marcados 'defeito_fabrica' — o custo
    que deveria ser da Dal Mobile. Ferramenta de negociação; NÃO é Contas a Receber (só fase 2)."""
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                                       origem="execucao_reparo_garantia", motivo="defeito_fabrica")
    lans = _filtra_periodo(q, ini, fim).order_by(Lancamento.data.desc()).all()
    itens = [{"id": l.id, "data": l.data.isoformat() if l.data else None, "valor": l.valor,
              "projeto_id": l.projeto_id, "historico": l.historico} for l in lans]
    return {"total": round(sum(l.valor for l in lans), 2), "qtd": len(itens), "itens": itens}


# ── DRE societário (sub-projeto #4) ──────────────────────────────────────────
def _somas_por_conta(db, ot, oid, conta_ids, lado, ini, fim, projeto_id=None):
    """{conta_id: Σ valor} agregado NO BANCO para um lado ('debito'|'credito') — uma query
    por lado, em vez de 2 por conta (era o gargalo do painel de Indicadores no Postgres:
    milhares de round-trips por request; no SQLite in-process nunca doeu)."""
    if not conta_ids:
        return {}
    from sqlalchemy import func
    col = Lancamento.conta_debito_id if lado == "debito" else Lancamento.conta_credito_id
    q = (db.query(col, func.coalesce(func.sum(Lancamento.valor), 0.0))
           .filter(Lancamento.owner_tipo == ot, Lancamento.owner_id == oid)
           .filter(col.in_(conta_ids)))
    if projeto_id is not None:
        q = q.filter(Lancamento.projeto_id == projeto_id)
    q = _filtra_periodo(q, ini, fim)
    return dict(q.group_by(col).all())


def _totais_conta(db, ot, oid, conta_id, ini, fim, projeto_id=None):
    deb = _somas_por_conta(db, ot, oid, [conta_id], "debito", ini, fim, projeto_id=projeto_id)
    cred = _somas_por_conta(db, ot, oid, [conta_id], "credito", ini, fim, projeto_id=projeto_id)
    return deb.get(conta_id, 0.0), cred.get(conta_id, 0.0)


def _mov(db, ot, oid, prefixo, sentido, ini, fim, projeto_id=None):
    """Movimento das contas sob `prefixo`, no sentido pedido ('credor' = C−D p/ receitas;
    'devedor' = D−C p/ deduções/despesas). `projeto_id` filtra a dimensão gerencial.
    Considera TODAS as contas (não só analíticas): o seed_plano converte um pai em sintética
    quando ele ganha filho no backfill — lançamentos diretos anteriores à conversão sumiam da
    DRE/Balanço (fix 2026-07-22). Sem dupla contagem: as somas são por lançamento direto."""
    ids = [c.id for c in db.query(Conta).filter_by(owner_tipo=ot, owner_id=oid).all()
           if c.codigo == prefixo or c.codigo.startswith(prefixo + ".")]
    deb = sum(_somas_por_conta(db, ot, oid, ids, "debito", ini, fim, projeto_id=projeto_id).values())
    cred = sum(_somas_por_conta(db, ot, oid, ids, "credito", ini, fim, projeto_id=projeto_id).values())
    return round(cred - deb if sentido == "credor" else deb - cred, 2)


def _detalhe_grupo(db, ot, oid, prefixos, sentido, ini, fim):
    """Composição nível 3 de um ou mais prefixos, no sentido pedido. Alimenta o modo
    Analítico da DRE/Balanço (v5 §3.1) — Resumido usa só os totais de nível 2.

    Requisito 2026-07-22 (2ª revisão, supera o "sem movimento → fora" da 1ª): o analítico
    mostra TODAS as contas analíticas ATIVAS do grupo — sem movimento sai 0,00. O usuário
    quer enxergar o plano inteiro na DRE/Balanço analíticos (um lançamento "sumido" fica
    evidente ao lado das contas zeradas). Além delas, QUALQUER conta com lançamento no
    período aparece — inclusive sintética com lançamento direto (pai convertido pelo
    backfill) e inativa com histórico: movimento nunca some do demonstrativo."""
    if isinstance(prefixos, str):
        prefixos = [prefixos]
    contas = [c for c in db.query(Conta).filter_by(owner_tipo=ot, owner_id=oid).all()
              if any(c.codigo == p or c.codigo.startswith(p + ".") for p in prefixos)]
    ids = [c.id for c in contas]
    debs = _somas_por_conta(db, ot, oid, ids, "debito", ini, fim)
    creds = _somas_por_conta(db, ot, oid, ids, "credito", ini, fim)
    linhas = []
    for c in sorted(contas, key=lambda x: x.codigo):
        d, cr = debs.get(c.id, 0.0), creds.get(c.id, 0.0)
        teve_movimento = (d != 0 or cr != 0)
        sempre_listada = (c.tipo == "analitica" and bool(c.ativa))
        if not (sempre_listada or teve_movimento):
            continue
        val = round(cr - d if sentido == "credor" else d - cr, 2)
        linhas.append({"codigo": c.codigo, "nome": c.nome, "valor": val})
    return linhas


def meses_do_periodo(ini, fim):
    """[(mes_ini, mes_fim), ...] pra cada mês civil entre `ini` e `fim` (inclusive), um por mês
    inteiro (dia 1 00:00 até o último dia 23:59:59) — não corta pelo dia exato de `ini`/`fim`,
    só usa o ano/mês deles como os dois extremos. Alimenta a visão em colunas da DRE (achado do
    usuário 2026-08-15: a tela somava a história inteira sem mostrar o período)."""
    from datetime import datetime as _dt, time as _time
    import calendar
    out = []
    ano, mes = ini.year, ini.month
    ano_fim, mes_fim = fim.year, fim.month
    while (ano, mes) <= (ano_fim, mes_fim):
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        m_ini = _dt(ano, mes, 1)
        m_fim = _dt.combine(_dt(ano, mes, ultimo_dia).date(), _time.max)
        out.append((m_ini, m_fim))
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
    return out


def dre_serie_mensal(db, owner_tipo, owner_id, ini, fim, modo="real"):
    """Série mês a mês de `dre()`/`dre_simulada()` dentro de [ini, fim] — pra visão em colunas
    (achado do usuário 2026-08-15). Uma função só, sem round-trip por mês no frontend; reusa
    `dre()`/`dre_simulada()` tal como já testados, só orquestra por mês + o total do período
    inteiro. `owner_tipo == "consolidado"` fica de fora — resolvido pelo chamador HTTP (não tem
    `dre_consolidada` com `modo`, mesma limitação que o endpoint `/dre` já tem hoje)."""
    calc = ((lambda i, f: dre(db, owner_tipo, owner_id, i, f)) if modo == "real"
            else (lambda i, f: dre_simulada(db, owner_tipo, owner_id, modo, i, f)))
    meses = [calc(mi, mf) for mi, mf in meses_do_periodo(ini, fim)]
    total = calc(ini, fim)
    return {"meses": meses, "total": total}


def dre(db, owner_tipo, owner_id, ini=None, fim=None):
    """DRE societário (competência) a partir do livro (.docx §3). Deduções/despesas já com o sinal certo.
    Inclui `detalhe` (composição nível 3 por linha) p/ o toggle Analítico×Resumido (v5 §3.1)."""
    m = lambda pref, sen: _mov(db, owner_tipo, owner_id, pref, sen, ini, fim)
    det = lambda prefs, sen: _detalhe_grupo(db, owner_tipo, owner_id, prefs, sen, ini, fim)
    receita_bruta = round(m("4.1", "credor") + m("4.2", "credor"), 2)
    deducoes = m("4.3", "devedor")
    receita_liquida = round(receita_bruta - deducoes, 2)
    cmv_csp = round(m("5.1", "devedor") + m("5.2", "devedor"), 2)
    lucro_bruto = round(receita_liquida - cmv_csp, 2)
    desp_com = m("5.3", "devedor")
    desp_adm = m("5.4", "devedor")
    const_prov = m("5.6", "devedor")
    ebitda = round(lucro_bruto - desp_com - desp_adm - const_prov, 2)
    depreciacao = 0.0                                  # sem conta dedicada no seed
    ebit = round(ebitda - depreciacao, 2)
    resultado_financeiro = round(-m("5.5", "devedor"), 2)
    # FASE D: Outras Receitas (4.4) — inclui a Reversão de Provisões (4.4.02, sobra da reconciliação).
    # Sem isto a sobra ficava órfã da DRE (a falta, 5.6.10, já entra em constituicao_provisoes).
    outras_receitas = round(m("4.4", "credor"), 2)
    resultado_antes_impostos = round(ebit + resultado_financeiro + outras_receitas, 2)
    impostos = 0.0                                     # Simples/DAS já em Deduções (4.3)
    lucro_liquido = round(resultado_antes_impostos - impostos, 2)
    return {
        "periodo": {"ini": ini.isoformat() if ini else None, "fim": fim.isoformat() if fim else None},
        "receita_bruta": receita_bruta, "deducoes": deducoes, "receita_liquida": receita_liquida,
        "cmv_csp": cmv_csp, "lucro_bruto": lucro_bruto,
        "despesas_comerciais": desp_com, "despesas_administrativas": desp_adm,
        "constituicao_provisoes": const_prov, "ebitda": ebitda,
        "depreciacao": depreciacao, "ebit": ebit,
        "resultado_financeiro": resultado_financeiro, "outras_receitas": outras_receitas,
        "resultado_antes_impostos": resultado_antes_impostos,
        "impostos": impostos, "lucro_liquido": lucro_liquido,
        "obs": "Depreciação e Impostos = 0 (sem conta dedicada no seed; Simples/DAS já em Deduções). Refinar com contador.",
        "detalhe": {   # composição nível 3 por linha (modo Analítico)
            "receita_bruta": det(["4.1", "4.2"], "credor"),
            "deducoes": det("4.3", "devedor"),
            "cmv_csp": det(["5.1", "5.2"], "devedor"),
            "despesas_comerciais": det("5.3", "devedor"),
            "despesas_administrativas": det("5.4", "devedor"),
            "constituicao_provisoes": det("5.6", "devedor"),
            "resultado_financeiro": det("5.5", "devedor"),
            "outras_receitas": det("4.4", "credor"),
        },
    }


def relatorio_centro_custo(db, owner_tipo, owner_id, ini=None, fim=None):
    """Árvore de Centro de Custo com valor por conta (grupo 5, no período) e total consolidado
    por nó — a soma das contas classificadas direto nele + a soma recursiva dos filhos.
    `incluir_inativos=True` de propósito: um Centro de Custo inativado depois de já ter conta
    classificada nele não pode fazer o valor dela sumir do relatório sem aviso. Débito/crédito
    de TODAS as contas do grupo 5 vêm de uma tacada só via `_somas_por_conta` (não é N+1)."""
    arvore = listar_centros_custo(db, owner_tipo, owner_id, incluir_inativos=True)
    contas_g5 = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, grupo=5).all()
    ids = [c.id for c in contas_g5]
    debs = _somas_por_conta(db, owner_tipo, owner_id, ids, "debito", ini, fim)
    creds = _somas_por_conta(db, owner_tipo, owner_id, ids, "credito", ini, fim)
    por_cc = {}
    nao_classificado = []
    for c in contas_g5:
        v = round(debs.get(c.id, 0.0) - creds.get(c.id, 0.0), 2)   # despesa: sempre devedora
        if v == 0:
            continue
        item = {"id": c.id, "codigo": c.codigo, "nome": c.nome, "valor": v}
        if c.centro_custo_id:
            por_cc.setdefault(c.centro_custo_id, []).append(item)
        else:
            nao_classificado.append(item)

    def aumenta(node):
        contas = sorted(por_cc.get(node["id"], []), key=lambda x: x["codigo"])
        filhos = [aumenta(f) for f in node["filhos"]]
        total = round(sum(x["valor"] for x in contas) + sum(f["total"] for f in filhos), 2)
        return {**node, "filhos": filhos, "contas": contas, "total": total}

    nao_classificado.sort(key=lambda x: x["codigo"])
    return {
        "periodo": {"ini": ini.isoformat() if ini else None, "fim": fim.isoformat() if fim else None},
        "centros_custo": [aumenta(r) for r in arvore],
        "nao_classificado": {"contas": nao_classificado,
                              "total": round(sum(x["valor"] for x in nao_classificado), 2)},
    }


def relatorio_natureza(db, owner_tipo, owner_id, ini=None, fim=None):
    """Contas de despesa (grupo 5) agrupadas por Conta.natureza_custo, valor no período — só as
    com movimento (valor 0 fica de fora, não polui o relatório). `nao_classificado` pega quem
    ainda não tem natureza_custo definida, pra nada sumir em silêncio."""
    contas_g5 = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, grupo=5).all()
    ids = [c.id for c in contas_g5]
    debs = _somas_por_conta(db, owner_tipo, owner_id, ids, "debito", ini, fim)
    creds = _somas_por_conta(db, owner_tipo, owner_id, ids, "credito", ini, fim)
    baldes = {slug: [] for slug, _ in NATUREZA_CUSTO}
    baldes["nao_classificado"] = []
    for c in contas_g5:
        v = round(debs.get(c.id, 0.0) - creds.get(c.id, 0.0), 2)
        if v == 0:
            continue
        chave = c.natureza_custo if c.natureza_custo in baldes else "nao_classificado"
        baldes[chave].append({"id": c.id, "codigo": c.codigo, "nome": c.nome, "valor": v})
    out = {"periodo": {"ini": ini.isoformat() if ini else None, "fim": fim.isoformat() if fim else None}}
    for chave, itens in baldes.items():
        itens = sorted(itens, key=lambda x: x["codigo"])
        out[chave] = {"contas": itens, "total": round(sum(x["valor"] for x in itens), 2)}
    return out


# ── Sugestões de despesa do mês anterior (painel guiado de Lançamentos, 2026-08-09) ──────────
def _intervalo_mes_anterior(ref):
    """(ini, fim) do mês anterior a `ref`, dia cheio. replace(day=1) - 1 dia rola sozinho pra
    dezembro do ano anterior em janeiro, sem caso especial. ACHADO-48 (02/09): `ref` deixou de
    ter default aqui — o único chamador (`sugestoes_despesas_mes_anterior`) sempre passa
    `agora_no_fuso(db, owner_tipo, owner_id)`, nunca o relógio do processo."""
    from datetime import datetime as _dt, time as _time, timedelta
    primeiro_atual = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ultimo_dia_anterior = primeiro_atual - timedelta(days=1)
    ini = ultimo_dia_anterior.replace(day=1)
    fim = _dt.combine(ultimo_dia_anterior.date(), _time.max)
    return ini, fim


def _intervalo_mes_atual(ref):
    """(ini, fim) do mês em curso ATÉ `ref` — "já lançado" olha só o que já aconteceu. ACHADO-48
    (02/09): mesma nota de `_intervalo_mes_anterior` — sem default, `ref` vem sempre resolvido
    pelo fuso do dono do livro."""
    return ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0), ref


def _contrapartida_mais_recente(db, ot, oid, conta_ids, ini, fim):
    """{conta_debito_id: conta_credito_id do lançamento MAIS RECENTE na janela} — 1 query
    (ORDER BY data DESC, id DESC + setdefault na 1ª ocorrência), não N+1 por conta."""
    if not conta_ids:
        return {}
    q = (db.query(Lancamento.conta_debito_id, Lancamento.conta_credito_id)
           .filter(Lancamento.owner_tipo == ot, Lancamento.owner_id == oid)
           .filter(Lancamento.conta_debito_id.in_(conta_ids)))
    q = _filtra_periodo(q, ini, fim).order_by(Lancamento.data.desc(), Lancamento.id.desc())
    out = {}
    for deb_id, cred_id in q.all():
        out.setdefault(deb_id, cred_id)
    return out


def _contas_com_lancamento_debito(db, ot, oid, conta_ids, ini, fim):
    """Set de conta_ids com QUALQUER lançamento como DÉBITO na janela — 1 query (distinct)."""
    if not conta_ids:
        return set()
    q = (db.query(Lancamento.conta_debito_id)
           .filter(Lancamento.owner_tipo == ot, Lancamento.owner_id == oid)
           .filter(Lancamento.conta_debito_id.in_(conta_ids)))
    q = _filtra_periodo(q, ini, fim)
    return {row[0] for row in q.distinct().all()}


CONTAS_EXCLUIDAS_SUGESTAO_DESPESA = {"5.3.04"}   # Pontos Programa de Relacionamento (Fidelidade)
# ^ contas cujo lançamento é INTEIRAMENTE automático, pelo caminho da venda (parâmetros da
# negociação) — nunca sugerir repetição manual aqui, senão duplica o que o motor já lançou
# sozinho (achado do usuário 2026-08-15). Continuam lançáveis manualmente no formulário genérico
# "Lançar outra despesa" da mesma tela — cobre a exceção de o toggle da negociação ter ficado
# esquecido (aí não há lançamento automático nenhum pra duplicar).


def sugestoes_despesas_mes_anterior(db, owner_tipo, owner_id, ref=None):
    """Sugestões pro painel guiado de Lançamentos: toda conta analítica ATIVA do grupo 5 com
    movimento líquido POSITIVO (D−C > 0) no mês anterior a `ref`, EXCETO
    `CONTAS_EXCLUIDAS_SUGESTAO_DESPESA`. contrapartida_sugerida = outra ponta do lançamento mais
    recente dessa conta na mesma janela. ja_lancado_mes_atual = já tem lançamento como débito no
    mês em curso (a UI não insiste na sugestão). ACHADO-48 (02/09): sem `ref` explícito, "agora"
    é a hora de parede no fuso do dono do livro (`agora_no_fuso`), nunca `datetime.utcnow()`."""
    seed_plano(db, owner_tipo, owner_id)
    ref = ref or agora_no_fuso(db, owner_tipo, owner_id)
    ini_ant, fim_ant = _intervalo_mes_anterior(ref)
    ini_atu, fim_atu = _intervalo_mes_atual(ref)
    contas_g5 = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                 grupo=5, tipo="analitica", ativa=1)
                 .filter(~Conta.codigo.in_(CONTAS_EXCLUIDAS_SUGESTAO_DESPESA)).all())
    ids = [c.id for c in contas_g5]
    debs = _somas_por_conta(db, owner_tipo, owner_id, ids, "debito", ini_ant, fim_ant)
    creds = _somas_por_conta(db, owner_tipo, owner_id, ids, "credito", ini_ant, fim_ant)
    contrapartidas = _contrapartida_mais_recente(db, owner_tipo, owner_id, ids, ini_ant, fim_ant)
    ja_lancadas = _contas_com_lancamento_debito(db, owner_tipo, owner_id, ids, ini_atu, fim_atu)
    contra_ids = {cid for cid in contrapartidas.values() if cid}
    contra_map = ({c.id: c for c in db.query(Conta).filter(Conta.id.in_(contra_ids)).all()}
                  if contra_ids else {})
    out = []
    for c in sorted(contas_g5, key=lambda x: x.codigo):
        valor = round(debs.get(c.id, 0.0) - creds.get(c.id, 0.0), 2)
        if valor <= 0:
            continue
        contra_id = contrapartidas.get(c.id)
        contra = contra_map.get(contra_id)
        out.append({
            "conta_id": c.id, "codigo": c.codigo, "nome": c.nome,
            "natureza_custo": c.natureza_custo,
            "valor_sugerido": valor,
            "contrapartida_sugerida_id": contra_id,
            "contrapartida_sugerida_nome": (contra.codigo + " — " + contra.nome) if contra else None,
            "contrapartida_sugerida_ativa": bool(contra and contra.ativa),
            "ja_lancado_mes_atual": c.id in ja_lancadas,
        })
    return {"periodo_referencia": {"ini": ini_ant.isoformat(), "fim": fim_ant.isoformat()},
            "sugestoes": out}


def dre_simulada(db, owner_tipo, owner_id, modo, ini=None, fim=None):
    """DRE em modo simulado (2026-08-07, a pedido do usuário) — LEITURA pura, nunca escreve no razão
    nem duplica nada. Recalcula receita/despesa das rubricas com despesa-em-tempo-real (as 15 do
    antigo "matching pleno") usando o valor CONSTITUÍDO (a provisão da venda — a estimativa),
    atribuído a uma data diferente da real. Deduções, despesas administrativas/financeiras, outras
    receitas e impostos NÃO mudam (rota própria, fora desta simulação) — vêm sempre do `dre()` real,
    mesmo período.
      - 'competencia_estimada': despesa = constituído de cada rubrica, na data da NF-e (mesma data da
        receita real) — reproduz o antigo "matching pleno". Receita = a real.
      - 'antecipacao_contrato': receita E despesa simuladas na data da VENDA/contrato assinado —
        receita = Val_Cont (lançamento `registro_venda_contrato`); despesa = constituído de cada
        rubrica, na mesma data.
    Mesmo formato de `dre()`, INCLUINDO `detalhe` (achado do usuário 2026-08-15 — antes não tinha,
    e por isso o modo Analítico não abria nada nestas 2 visões): pras linhas que ela reusa sem
    alteração de `real[...]` (deduções/despesas administrativas/constituição de provisões/
    resultado financeiro/outras receitas, + receita bruta no modo competencia_estimada), o detalhe
    é o MESMO de `real["detalhe"]` — não mudou o valor, não muda a composição. Pras que ela
    recalcula (cmv_csp/despesas_comerciais, sempre; receita_bruta no modo antecipacao_contrato),
    monta um detalhe próprio a partir do que já apura internamente (ver fim da função)."""
    if modo not in ("competencia_estimada", "antecipacao_contrato"):
        raise ValueError("modo inválido: %s" % modo)
    real = dre(db, owner_tipo, owner_id, ini, fim)
    # normaliza p/ `date` puro — `marco.data` é DateTime; comparar date×datetime levanta TypeError
    # (o endpoint HTTP manda datetime via _parse_data; chamadas diretas podem mandar date).
    ini = ini.date() if hasattr(ini, "date") else ini
    fim = fim.date() if hasattr(fim, "date") else fim
    ids_receita = [c.id for c in db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()
                   if c.codigo.startswith("4.1.") or c.codigo.startswith("4.2.")]
    contas_prov = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
                   .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%")).order_by(Conta.codigo).all())
    nomes_conta = {c.codigo: c.nome for c in db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    receita_bruta = 0.0 if modo == "antecipacao_contrato" else real["receita_bruta"]
    por_conta_despesa = {}
    por_projeto_receita = []   # só populado no modo antecipacao_contrato — detalhe da receita_bruta
    for proj in projetos_com_lancamento(db, owner_tipo, owner_id):
        if modo == "antecipacao_contrato":
            marco = (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                     projeto_id=proj, origem="registro_venda_contrato")
                     .order_by(Lancamento.data.asc()).first())
        elif ids_receita:
            marco = (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, projeto_id=proj)
                     .filter(Lancamento.conta_credito_id.in_(ids_receita))
                     .order_by(Lancamento.data.asc()).first())
        else:
            marco = None
        if marco is None:
            continue
        data_ref = marco.data.date() if hasattr(marco.data, "date") else marco.data
        if ini and data_ref < ini:
            continue
        if fim and data_ref > fim:
            continue
        if modo == "antecipacao_contrato":
            receita_bruta = round(receita_bruta + marco.valor, 2)
            por_projeto_receita.append({"codigo": proj, "nome": proj.replace("_", " "),
                                        "valor": round(marco.valor, 2)})
        for c in contas_prov:
            desp_cod = _PROV_DESPESA_POR_ATIVO.get(_ativo_diferido_de(c.codigo))
            if not desp_cod:
                continue
            constituido = round(total_lancado(db, owner_tipo, owner_id, c.codigo, "credito", proj,
                                              excluir_origens={_ORIGEM_RESOL_FALTA})
                                - total_lancado(db, owner_tipo, owner_id, c.codigo, "debito", proj,
                                                origens={_ORIGEM_RECLASS}), 2)
            if constituido:
                por_conta_despesa[desp_cod] = round(por_conta_despesa.get(desp_cod, 0.0) + constituido, 2)
    # S109: 5.1/5.2 -> cmv_csp; 5.3 -> despesas comerciais (mesmo agrupamento formal do dre() real)
    cmv_csp = round(sum(v for cod, v in por_conta_despesa.items() if cod.startswith(("5.1", "5.2"))), 2)
    desp_com = round(sum(v for cod, v in por_conta_despesa.items() if cod.startswith("5.3")), 2)
    deducoes = real["deducoes"]
    receita_liquida = round(receita_bruta - deducoes, 2)
    lucro_bruto = round(receita_liquida - cmv_csp, 2)
    desp_adm = real["despesas_administrativas"]
    const_prov = real["constituicao_provisoes"]
    ebitda = round(lucro_bruto - desp_com - desp_adm - const_prov, 2)
    ebit = round(ebitda - real["depreciacao"], 2)
    resultado_financeiro = real["resultado_financeiro"]
    outras_receitas = real["outras_receitas"]
    resultado_antes_impostos = round(ebit + resultado_financeiro + outras_receitas, 2)
    lucro_liquido = round(resultado_antes_impostos - real["impostos"], 2)
    detalhe_cmv_csp = sorted(
        ({"codigo": cod, "nome": nomes_conta.get(cod, cod), "valor": v}
         for cod, v in por_conta_despesa.items() if cod.startswith(("5.1", "5.2"))),
        key=lambda l: l["codigo"])
    detalhe_desp_com = sorted(
        ({"codigo": cod, "nome": nomes_conta.get(cod, cod), "valor": v}
         for cod, v in por_conta_despesa.items() if cod.startswith("5.3")),
        key=lambda l: l["codigo"])
    detalhe_receita = (real["detalhe"]["receita_bruta"] if modo == "competencia_estimada"
                        else sorted(por_projeto_receita, key=lambda l: l["codigo"]))
    return {
        "modo": modo,
        "periodo": real["periodo"],
        "receita_bruta": receita_bruta, "deducoes": deducoes, "receita_liquida": receita_liquida,
        "cmv_csp": cmv_csp, "lucro_bruto": lucro_bruto,
        "despesas_comerciais": desp_com, "despesas_administrativas": desp_adm,
        "constituicao_provisoes": const_prov, "ebitda": ebitda,
        "depreciacao": real["depreciacao"], "ebit": ebit,
        "resultado_financeiro": resultado_financeiro, "outras_receitas": outras_receitas,
        "resultado_antes_impostos": resultado_antes_impostos,
        "impostos": real["impostos"], "lucro_liquido": lucro_liquido,
        "obs": ("Simulação (leitura, nunca lançada): despesa das rubricas com despesa em tempo real "
                "usa o valor CONSTITUÍDO na venda, não o efetivado real. Deduções/despesas "
                "administrativas/financeiras/outras receitas/impostos vêm do resultado real (fora do "
                "escopo desta simulação)."),
        "detalhe": {
            "receita_bruta": detalhe_receita,
            "deducoes": real["detalhe"]["deducoes"],
            "cmv_csp": detalhe_cmv_csp,
            "despesas_comerciais": detalhe_desp_com,
            "despesas_administrativas": real["detalhe"]["despesas_administrativas"],
            "constituicao_provisoes": real["detalhe"]["constituicao_provisoes"],
            "resultado_financeiro": real["detalhe"]["resultado_financeiro"],
            "outras_receitas": real["detalhe"]["outras_receitas"],
        },
    }


# ── Balanço Patrimonial (v5 §4) ──────────────────────────────────────────────
def balanco(db, owner_tipo, owner_id, data_corte=None):
    """Posição patrimonial num instante: saldo ACUMULADO (do início até `data_corte`) dos grupos
    1/2/3. O resultado do exercício (Receitas − Despesas acumuladas) entra no PL → fecha por
    partida dobrada (Ativo = Passivo + PL). `data_corte` = fim; ini=None (desde o começo)."""
    s = lambda pref, sen: _mov(db, owner_tipo, owner_id, pref, sen, None, data_corte)
    det = lambda pref, sen: _detalhe_grupo(db, owner_tipo, owner_id, pref, sen, None, data_corte)
    ativo_circ = s("1.1", "devedor")
    ativo_ncirc = s("1.2", "devedor")
    total_ativo = round(ativo_circ + ativo_ncirc, 2)
    passivo_circ = s("2.1", "credor")
    passivo_ncirc = s("2.2", "credor")
    total_passivo = round(passivo_circ + passivo_ncirc, 2)
    pl_contas = s("3", "credor")
    resultado = round(s("4", "credor") - s("5", "devedor"), 2)   # lucro/prejuízo acumulado do período
    total_pl = round(pl_contas + resultado, 2)
    total_passivo_pl = round(total_passivo + total_pl, 2)
    return {
        "data_corte": data_corte.isoformat() if data_corte else None,
        "ativo": {"circulante": ativo_circ, "nao_circulante": ativo_ncirc, "total": total_ativo},
        "passivo": {"circulante": passivo_circ, "nao_circulante": passivo_ncirc, "total": total_passivo},
        "patrimonio_liquido": {"contas": pl_contas, "resultado_exercicio": resultado, "total": total_pl},
        "total_passivo_mais_pl": total_passivo_pl,
        "confere": abs(total_ativo - total_passivo_pl) < 0.01,
        "detalhe": {   # composição nível 3 por grupo (modo Analítico)
            "ativo_circulante": det("1.1", "devedor"),
            "ativo_nao_circulante": det("1.2", "devedor"),
            "passivo_circulante": det("2.1", "credor"),
            "passivo_nao_circulante": det("2.2", "credor"),
            "patrimonio_liquido": det("3", "credor"),
        },
    }


# ── Visão CONSOLIDADA mãe+PDVs (PDV, spec _geral/2026-07-22-ponto-de-venda-design.md) ──
def _consolidar(res_list):
    """Merge estrutural de N resultados de mesma forma (dre/balanco por owner):
    números somam; dicts mergeiam por chave; listas de detalhe mergeiam por `codigo`
    somando `valor`; bools viram AND (recomputados pelo chamador quando fizer sentido);
    strings/None ficam do primeiro (períodos/observações são idênticos por construção)."""
    def merge(vals):
        v0 = vals[0]
        if isinstance(v0, bool):
            return all(bool(v) for v in vals)
        if isinstance(v0, (int, float)):
            return round(sum((v or 0) for v in vals), 2)
        if isinstance(v0, dict):
            return {k: merge([(v or {}).get(k) for v in vals]) for k in v0}
        if isinstance(v0, list):
            por = {}
            for lst in vals:
                for item in (lst or []):
                    k = item.get("codigo")
                    if k in por:
                        por[k] = dict(por[k], valor=round(por[k]["valor"] + (item.get("valor") or 0), 2))
                    else:
                        por[k] = dict(item)
            return sorted(por.values(), key=lambda x: x.get("codigo") or "")
        return v0
    return merge(res_list)


def eliminacoes_intercompany(db, owners, data_corte=None):
    """Pendência de conta corrente mãe×PDV DENTRO do perímetro consolidado: saldo líquido
    dos lançamentos com ref `rateio:*` na conta 1.1.09 de cada owner. O espelho 2.1.09 dos
    PDVs é IGUAL por construção (par espelhado — rateio, estorno e liquidação carregam o
    mesmo prefixo de ref), então um único lado mede a pendência. Saldos de 1.1.09 de outras
    origens (ex.: acordos com lojas fora do perímetro) NÃO são eliminados."""
    total = 0.0
    for ot, oid in owners:
        if not _conta_existe(db, ot, oid, "1.1.09"):
            continue   # owner nunca participou de rateio/PDV — sem a conta, sem pendência
        c = _conta_por_codigo(db, ot, oid, "1.1.09")
        q = (db.query(Lancamento).filter_by(owner_tipo=ot, owner_id=oid)
               .filter(Lancamento.ref.like("rateio:%")))
        if data_corte:
            q = q.filter(Lancamento.data <= data_corte)
        for l in q.all():
            if l.conta_debito_id == c.id:
                total += l.valor
            elif l.conta_credito_id == c.id:
                total -= l.valor
    return round(total, 2)


def dre_consolidada(db, owners, ini=None, fim=None):
    """DRE Consolidado = soma das DREs de [mãe]+PDVs. Sem eliminação: o rateio não toca a
    DRE da mãe (1.1.09 × 1.1.01, só balanço) e a despesa aparece UMA vez, no PDV."""
    res = _consolidar([dre(db, ot, oid, ini=ini, fim=fim) for ot, oid in owners])
    res["unidades"] = len(owners)
    return res


def balanco_consolidado(db, owners, data_corte=None):
    """Balanço Consolidado = soma dos balanços de [mãe]+PDVs com ELIMINAÇÃO do saldo
    intercompany pendente (1.1.09 da credora × 2.1.09 da devedora): os dois lados caem
    pelo mesmo valor e a linha `eliminacoes` exibe a pendência quando ≠ 0."""
    res = _consolidar([balanco(db, ot, oid, data_corte=data_corte) for ot, oid in owners])
    elim = eliminacoes_intercompany(db, owners, data_corte=data_corte)
    res["eliminacoes"] = elim
    res["unidades"] = len(owners)
    if elim:
        res["ativo"]["circulante"] = round(res["ativo"]["circulante"] - elim, 2)
        res["ativo"]["total"] = round(res["ativo"]["total"] - elim, 2)
        res["passivo"]["circulante"] = round(res["passivo"]["circulante"] - elim, 2)
        res["passivo"]["total"] = round(res["passivo"]["total"] - elim, 2)
        res["total_passivo_mais_pl"] = round(res["total_passivo_mais_pl"] - elim, 2)
        for lst, cod in ((res["detalhe"]["ativo_circulante"], "1.1.09"),
                         (res["detalhe"]["passivo_circulante"], "2.1.09")):
            for item in lst:
                if item["codigo"] == cod:
                    item["valor"] = round(item["valor"] - elim, 2)
    res["confere"] = abs(res["ativo"]["total"] - res["total_passivo_mais_pl"]) < 0.01
    return res


# ── Rateio ao PDV (custos da mãe em nome do PDV — spec PDV §3) ───────────────
def _prox_ref_rateio(db):
    n = db.query(Lancamento).filter(Lancamento.ref.like("rateio:%")).count() + 1
    while db.query(Lancamento).filter(Lancamento.ref == "rateio:%d" % n).first() is not None:
        n += 1
    return "rateio:%d" % n


def rateio_ao_pdv(db, owner_mae, owner_pdv, valor, conta_despesa, historico="",
                  projeto_id=None, data=None):
    """Rateio administrativo mãe→PDV: a mãe pagou um custo em nome do PDV (aluguel, folha
    compartilhada, marketing…). Par intercompany com ref ESPELHADA `rateio:<n>` nos DOIS
    razões — legítimo aqui (diferente do caso fábrica): o ator é a equipe da mãe COM escopo
    sobre ambos, numa ação administrativa consciente.
      mãe: DR 1.1.09 (conta corrente a receber) × CR 1.1.01 (caixa)
      PDV: DR <despesa 5.x da rubrica escolhida> × CR 2.1.09 (conta corrente a pagar)
    Reversível em par por estornar_rateio(ref)."""
    if tuple(owner_mae) == tuple(owner_pdv):
        raise ValueError("rateio exige razões distintos (mãe × PDV)")
    seed_plano(db, owner_mae[0], owner_mae[1])
    seed_plano(db, owner_pdv[0], owner_pdv[1])
    cod = (conta_despesa or "").strip()
    if not cod.startswith("5"):
        raise ValueError("a conta do rateio deve ser uma despesa (grupo 5)")
    c_desp = _conta_por_codigo(db, owner_pdv[0], owner_pdv[1], cod)
    if c_desp is None or c_desp.tipo != "analitica":
        raise ValueError("conta %s não é uma despesa analítica do plano do PDV" % cod)
    cc_receber = _conta_por_codigo(db, owner_mae[0], owner_mae[1], "1.1.09")
    caixa_mae = _conta_por_codigo(db, owner_mae[0], owner_mae[1], "1.1.01")
    cc_pagar = _conta_por_codigo(db, owner_pdv[0], owner_pdv[1], "2.1.09")
    ref = _prox_ref_rateio(db)
    hist = (historico or "").strip() or ("Rateio ao PDV — " + c_desp.nome)
    lan_mae = lancar(db, owner_mae[0], owner_mae[1], cc_receber.id, caixa_mae.id, valor,
                     data=data, projeto_id=projeto_id, origem="rateio_pdv", historico=hist, ref=ref)
    lan_pdv = lancar(db, owner_pdv[0], owner_pdv[1], c_desp.id, cc_pagar.id, valor,
                     data=data, projeto_id=projeto_id, origem="rateio_pdv", historico=hist, ref=ref)
    return {"ref": ref, "mae": lan_mae, "pdv": lan_pdv}


def estornar_rateio(db, ref):
    """Reverte o PAR do rateio: lançamentos invertidos com ref `<ref>:estorno` nos dois
    razões (a pendência intercompany volta a zero por construção). Idempotente."""
    ref = (ref or "").strip()
    if not ref.startswith("rateio:") or ref.endswith(":estorno"):
        raise ValueError("ref de rateio inválida")
    legs = db.query(Lancamento).filter_by(ref=ref).order_by(Lancamento.id.asc()).all()
    if not legs:
        raise ValueError("rateio %s não encontrado" % ref)
    ja = db.query(Lancamento).filter_by(ref=ref + ":estorno").order_by(Lancamento.id.asc()).all()
    if ja:
        return {"ref": ref + ":estorno", "lancamentos": [_lanc_serial(l) for l in ja],
                "ja_estornado": True}
    outs = [lancar(db, l.owner_tipo, l.owner_id, l.conta_credito_id, l.conta_debito_id,
                   l.valor, projeto_id=l.projeto_id, origem="rateio_pdv",
                   historico="Estorno — " + (l.historico or ref), ref=ref + ":estorno")
            for l in legs]
    return {"ref": ref + ":estorno", "lancamentos": outs, "ja_estornado": False}


def listar_rateios(db, owners):
    """Rateios do perímetro (1 item por ref, legs agrupadas, flag de estorno) — alimenta a
    tabela da visão unificada. Um rateio entra se QUALQUER leg pertence ao perímetro."""
    owner_set = {tuple(o) for o in owners}
    rows = (db.query(Lancamento).filter(Lancamento.ref.like("rateio:%"))
              .order_by(Lancamento.id.asc()).all())
    estornados = {l.ref[:-len(":estorno")] for l in rows if (l.ref or "").endswith(":estorno")}
    por_ref = {}
    for l in rows:
        if (l.ref or "").endswith(":estorno"):
            continue
        por_ref.setdefault(l.ref, []).append(l)
    out = []
    for ref, legs in por_ref.items():
        if not any((l.owner_tipo, l.owner_id) in owner_set for l in legs):
            continue
        l0 = legs[0]
        out.append({"ref": ref, "valor": l0.valor,
                    "data": l0.data.isoformat() if l0.data else None,
                    "historico": l0.historico, "projeto_id": l0.projeto_id,
                    "owners": [[l.owner_tipo, l.owner_id] for l in legs],
                    "estornado": ref in estornados})
    out.sort(key=lambda x: x["ref"], reverse=True)
    return out


# ── DRE por projeto / margem de contribuição (sub-projeto #5) ─────────────────
def margem_projeto(db, owner_tipo, owner_id, projeto_id, ini=None, fim=None):
    """Margem de contribuição de um projeto (v5 §5): receita − custo direto de produto −
    Provisão de Montagem − Provisão de Assistência Técnica − Provisão de Garantia − comissão.
    Garantia entra pelo **valor bruto** (custo real da loja); repasse à fábrica é controle à parte (§6.2).
    NÃO aloca despesa fixa (isso é o rateio da Auditoria).

    2026-08-07 (achado do usuário — "não reflete o estágio atual do projeto"): desde que a despesa
    passou a ser reconhecida na efetivação real (não mais estimada de uma vez na NF-e), essa margem
    só reflete o que JÁ foi efetivado — um projeto recém-faturado aparece com margem quase cheia,
    mesmo que ainda falte gastar boa parte da provisão. `saldo_provisao_aberto` (o mesmo total que o
    painel de Reconciliação mostra) e `margem_projetada` (margem_contribuicao − a PARTE do saldo
    aberto ainda não gasta) dão o quadro completo: realizado até agora × pior caso se toda a provisão
    pendente for gasta."""
    m = lambda pref, sen: _mov(db, owner_tipo, owner_id, pref, sen, ini, fim, projeto_id=projeto_id)
    receita = round(m("4.1", "credor") + m("4.2", "credor"), 2)
    custo_produto = m("5.1", "devedor")      # inclui o Frete de Fábrica (5.1.02, formalismo S109)
    # Formalismo (S109): as despesas das rubricas moram nos grupos formais — os campos prov_*
    # seguem expostos (mesma leitura de gestão de antes), agora lendo as contas formais.
    prov_montagem = m("5.2.01", "devedor")
    prov_assistencia = m("5.2.13", "devedor")
    prov_garantia = m("5.2.12", "devedor")
    comissao = m("5.3", "devedor")           # comissão do consultor + medidor/proj-exec/retenção (S109)
    margem = round(receita - custo_produto - prov_montagem - prov_assistencia - prov_garantia - comissao, 2)
    # Custo de SERVIÇO do projeto (lastro contábil real): com o formalismo, montagem/assistência/
    # garantia/frete local/insumos JÁ moram no 5.2 — o total do grupo cobre tudo, sem somar
    # nada em separado (somar de novo duplicaria o custo). Campo INFORMATIVO / peso de rateio
    # (reconciliar proporcional_custo_direto) — NÃO entra de novo na margem.
    custo_servico = m("5.2", "devedor")
    saldo_aberto = reconciliacao(db, owner_tipo, owner_id, projeto_id=projeto_id, ini=ini, fim=fim)["totais"]["saldo_aberto"]
    # só desconta a parte AINDA NÃO gasta (saldo_aberto > 0); saldo negativo (já gastou mais que o
    # provisionado) já está refletido em margem_contribuicao — subtrair de novo duplicaria o excesso.
    margem_projetada = round(margem - max(saldo_aberto, 0.0), 2)
    return {"projeto_id": projeto_id, "receita": receita, "custo_produto": custo_produto,
            "custo_servico": custo_servico,
            "prov_montagem": prov_montagem, "prov_assistencia": prov_assistencia,
            "prov_garantia": prov_garantia, "comissao": comissao, "margem_contribuicao": margem,
            "saldo_provisao_aberto": saldo_aberto, "margem_projetada": margem_projetada}


def margem_projeto_simulada(db, owner_tipo, owner_id, projeto_id, modo, ini=None, fim=None):
    """Margem de contribuição em modo simulado (2026-08-07) — mesmas regras de `dre_simulada`
    (leitura pura, nunca lança), escopada a 1 projeto. Ver `dre_simulada` pra semântica dos modos."""
    if modo not in ("competencia_estimada", "antecipacao_contrato"):
        raise ValueError("modo inválido: %s" % modo)
    real = margem_projeto(db, owner_tipo, owner_id, projeto_id, ini, fim)
    ini = ini.date() if hasattr(ini, "date") else ini
    fim = fim.date() if hasattr(fim, "date") else fim
    ids_receita = [c.id for c in db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()
                   if c.codigo.startswith("4.1.") or c.codigo.startswith("4.2.")]
    if modo == "antecipacao_contrato":
        marco = (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id,
                 projeto_id=projeto_id, origem="registro_venda_contrato")
                 .order_by(Lancamento.data.asc()).first())
    elif ids_receita:
        marco = (db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, projeto_id=projeto_id)
                 .filter(Lancamento.conta_credito_id.in_(ids_receita))
                 .order_by(Lancamento.data.asc()).first())
    else:
        marco = None
    dentro_periodo = False
    if marco is not None:
        data_ref = marco.data.date() if hasattr(marco.data, "date") else marco.data
        dentro_periodo = not ((ini and data_ref < ini) or (fim and data_ref > fim))
    receita = 0.0
    por_conta = {}
    if dentro_periodo:
        receita = marco.valor if modo == "antecipacao_contrato" else real["receita"]
        contas_prov = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
                       .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%")).order_by(Conta.codigo).all())
        for c in contas_prov:
            desp_cod = _PROV_DESPESA_POR_ATIVO.get(_ativo_diferido_de(c.codigo))
            if not desp_cod:
                continue
            constituido = round(total_lancado(db, owner_tipo, owner_id, c.codigo, "credito", projeto_id,
                                              excluir_origens={_ORIGEM_RESOL_FALTA})
                                - total_lancado(db, owner_tipo, owner_id, c.codigo, "debito", projeto_id,
                                                origens={_ORIGEM_RECLASS}), 2)
            if constituido:
                por_conta[desp_cod] = round(por_conta.get(desp_cod, 0.0) + constituido, 2)
    custo_produto = round(sum(v for cod, v in por_conta.items() if cod.startswith("5.1")), 2)
    prov_montagem = por_conta.get("5.2.01", 0.0)
    prov_assistencia = por_conta.get("5.2.13", 0.0)
    prov_garantia = por_conta.get("5.2.12", 0.0)
    comissao = round(sum(v for cod, v in por_conta.items() if cod.startswith("5.3")), 2)
    custo_servico = round(sum(v for cod, v in por_conta.items() if cod.startswith("5.2")), 2)
    margem = round(receita - custo_produto - prov_montagem - prov_assistencia - prov_garantia - comissao, 2)
    return {"projeto_id": projeto_id, "modo": modo, "receita": receita, "custo_produto": custo_produto,
            "custo_servico": custo_servico,
            "prov_montagem": prov_montagem, "prov_assistencia": prov_assistencia,
            "prov_garantia": prov_garantia, "comissao": comissao, "margem_contribuicao": margem}


def projetos_com_lancamento(db, owner_tipo, owner_id):
    rows = (db.query(Lancamento.projeto_id).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
            .filter(Lancamento.projeto_id.isnot(None)).distinct().all())
    return sorted(r[0] for r in rows if r[0])


def margem_todos_projetos(db, owner_tipo, owner_id, ini=None, fim=None):
    """Margem de contribuição de cada projeto com lançamento (ordenado por margem desc)."""
    res = [margem_projeto(db, owner_tipo, owner_id, p, ini, fim)
           for p in projetos_com_lancamento(db, owner_tipo, owner_id)]
    return sorted(res, key=lambda r: r["margem_contribuicao"], reverse=True)


# ── Auditoria / Reconciliação periódica (sub-projeto #6) ─────────────────────
BASES_RATEIO = ("proporcional_receita", "proporcional_custo_direto", "linear_por_projeto")


def reconciliar(db, owner_tipo, owner_id, ini=None, fim=None, metodologia="proporcional_receita"):
    """Rateia a despesa fixa do período (grupo 5.4) aos projetos → margem plena (full cost),
    e calcula a divergência residual vs. o resultado societário (DRE). Não persiste (ver fechar_periodo)."""
    if metodologia not in BASES_RATEIO:
        raise ValueError("metodologia de rateio inválida: %s" % metodologia)
    margens = margem_todos_projetos(db, owner_tipo, owner_id, ini, fim)
    despesas_fixas = _mov(db, owner_tipo, owner_id, "5.4", "devedor", ini, fim)

    def _peso(m):
        if metodologia == "proporcional_receita":
            return max(m["receita"], 0.0)
        if metodologia == "proporcional_custo_direto":
            return max(m["custo_produto"] + m["custo_servico"], 0.0)
        return 1.0   # linear_por_projeto

    total_peso = sum(_peso(m) for m in margens)
    alocacao = []
    for m in margens:
        w = _peso(m)
        rateado = round(despesas_fixas * (w / total_peso), 2) if total_peso > 0 else 0.0
        alocacao.append({
            "projeto_id": m["projeto_id"],
            "margem_contribuicao": m["margem_contribuicao"],
            "valor_rateado": rateado,
            "margem_plena": round(m["margem_contribuicao"] - rateado, 2),
        })
    soma_margem_plena = round(sum(a["margem_plena"] for a in alocacao), 2)
    resultado_societario = dre(db, owner_tipo, owner_id, ini, fim)["lucro_liquido"]
    divergencia = round(resultado_societario - soma_margem_plena, 2)
    return {
        "metodologia": metodologia,
        "despesas_fixas_periodo": despesas_fixas,
        "alocacao_por_projeto": alocacao,
        "soma_margem_plena": soma_margem_plena,
        "resultado_societario_oficial": resultado_societario,
        "divergencia_residual": divergencia,
        "nota_explicativa": (
            "%d projeto(s) no período; despesa fixa (grupo 5.4) R$ %.2f rateada por %s. "
            "A divergência é estrutural (itens não alocados a projeto: deduções, resultado financeiro, "
            "custos sem projeto, provisões ainda não realizadas) — tende a um piso pequeno, não a zero."
            % (len(alocacao), despesas_fixas, metodologia)),
    }


def fechar_periodo(db, owner_tipo, owner_id, ini=None, fim=None, metodologia="proporcional_receita"):
    """Calcula a reconciliação e persiste um PeriodoContabil (status='fechado'). Frente 2 (spec
    2026-08-25): junto grava um SNAPSHOT de relatorio_natureza/relatorio_centro_custo do mesmo
    intervalo — período fechado nunca mais recalcula esses dois relatórios (a classificação das
    contas pode mudar depois; o relatório de um mês já fechado tem que continuar batendo com ele
    mesmo). Só tem efeito prático quando `ini`/`fim` são passados (um fechamento sem intervalo,
    como o fluxo atual da UI faz, não corresponde a nenhum relatório filtrado depois — ver
    `_periodo_fechado_correspondente`)."""
    import json as _json
    rec = reconciliar(db, owner_tipo, owner_id, ini, fim, metodologia)
    snapshot = {
        "natureza": relatorio_natureza(db, owner_tipo, owner_id, ini, fim),
        "centro_custo": relatorio_centro_custo(db, owner_tipo, owner_id, ini, fim),
    }
    p = PeriodoContabil(owner_tipo=owner_tipo, owner_id=owner_id, inicio=ini, fim=fim, status="fechado",
                        metodologia=metodologia, resultado_societario=rec["resultado_societario_oficial"],
                        soma_margem_plena=rec["soma_margem_plena"], divergencia_residual=rec["divergencia_residual"],
                        dados_json=_json.dumps(rec["alocacao_por_projeto"]),
                        classificacao_snapshot_json=_json.dumps(snapshot))
    db.add(p)
    db.commit()
    return {"id": p.id, **rec}


def _periodo_fechado_correspondente(db, owner_tipo, owner_id, ini, fim):
    """PeriodoContabil FECHADO cujo (inicio, fim) bate EXATAMENTE com o pedido, ou None. Sem
    `ini`/`fim` explícitos (relatório sem filtro de período) nunca corresponde — sempre calcula
    ao vivo; do contrário, o retrato "sem filtro" congelaria pra sempre assim que o primeiro
    período fosse fechado, escondendo lançamentos novos do dia a dia."""
    if ini is None or fim is None:
        return None
    return (db.query(PeriodoContabil)
              .filter_by(owner_tipo=owner_tipo, owner_id=owner_id, status="fechado", inicio=ini, fim=fim)
              .order_by(PeriodoContabil.id.desc()).first())


def relatorio_natureza_periodo(db, owner_tipo, owner_id, ini=None, fim=None):
    """Frente 2 (spec 2026-08-25): se `(ini, fim)` corresponde a um período FECHADO, devolve o
    snapshot congelado no fechamento; senão calcula ao vivo (`relatorio_natureza`), igual antes."""
    import json as _json
    periodo = _periodo_fechado_correspondente(db, owner_tipo, owner_id, ini, fim)
    if periodo is not None and periodo.classificacao_snapshot_json:
        snap = _json.loads(periodo.classificacao_snapshot_json)
        if "natureza" in snap:
            return snap["natureza"]
    return relatorio_natureza(db, owner_tipo, owner_id, ini, fim)


def relatorio_centro_custo_periodo(db, owner_tipo, owner_id, ini=None, fim=None):
    """Mesma lógica de `relatorio_natureza_periodo`, para `relatorio_centro_custo`."""
    import json as _json
    periodo = _periodo_fechado_correspondente(db, owner_tipo, owner_id, ini, fim)
    if periodo is not None and periodo.classificacao_snapshot_json:
        snap = _json.loads(periodo.classificacao_snapshot_json)
        if "centro_custo" in snap:
            return snap["centro_custo"]
    return relatorio_centro_custo(db, owner_tipo, owner_id, ini, fim)


def listar_periodos(db, owner_tipo, owner_id):
    ps = (db.query(PeriodoContabil).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
          .order_by(PeriodoContabil.criado_em.desc()).all())
    return [{"id": p.id, "inicio": p.inicio.isoformat() if p.inicio else None,
             "fim": p.fim.isoformat() if p.fim else None, "status": p.status,
             "metodologia": p.metodologia, "resultado_societario": p.resultado_societario,
             "soma_margem_plena": p.soma_margem_plena, "divergencia_residual": p.divergencia_residual}
            for p in ps]
