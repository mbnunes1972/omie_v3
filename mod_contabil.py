"""mod_contabil.py — motor contábil (domínio financeiro). Sub-projeto #1: Plano de Contas.
Fonte de verdade: Especificacao_Financeiro_Orizon_v2.docx §2/§2.1."""
from database import get_session, Conta, CentroCusto, Loja, Lancamento, PeriodoContabil

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
    ("2.1.05", "Financiamento Total Flex a Pagar"),
    ("2.1.06", "Receita a Realizar"),   # FASE D2: recebe o Val_Cont cheio no contrato (era "Adiantamento de Clientes")
    ("2.1.07", "Receita Financeira a Apropriar"),   # FASE B: ramo LOJA — juros diferidos, realizados por parcela
    # Ajustes Excepcionais de Fábrica (spec 2026-07-21)
    ("2.1.08", "Acordos com a Fábrica a Amortizar"),
    ("2.1.09", "Débitos com Empresas (conta corrente)"),
    ("2.1.10", "Empréstimos Bancários"),   # Acordos Financeiros (2026-07-21): contraparte banco
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
    ("5.4.17", "IPVA/IPTU/Licenciamentos"), ("5.4.18", "Manutenção (loja, veículos, informática)"),
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
    ("5.6.10", "Ajuste de Provisões"),   # FASE D: destino da FALTA (efetivado > provisionado)
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
    return "devedora" if grupo in (1, 5) else "credora"


def resolver_owner(db, usuario):
    """(owner_tipo, owner_id) do usuário: rede da loja se houver; senão a loja; admin de rede -> rede.
    PDV (loja com mãe, spec 2026-07-22): razão PRÓPRIO sempre — owner ("loja", pdv.id), mesmo com
    rede herdada da mãe; a individualização por unidade é o que a visão unificada consolida depois."""
    rid = usuario.get("rede_id")
    lid = usuario.get("loja_id")
    if lid:
        loja = db.get(Loja, lid)
        if loja is not None and getattr(loja, "loja_mae_id", None):
            return ("loja", lid)
        if loja and loja.rede_id:
            return ("rede", loja.rede_id)
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
            "tipo": c.tipo, "natureza": c.natureza, "pai_id": c.pai_id, "ativa": bool(c.ativa)}


def listar_contas(db, owner_tipo, owner_id, incluir_inativas=False):
    """Árvore (lista de raízes com 'filhos'), ordenada por 'ordem'/codigo. Seed-on-first-access."""
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


def criar_conta(db, owner_tipo, owner_id, pai_id, nome):
    pai = _get_own(db, owner_tipo, owner_id, pai_id)
    if not (nome or "").strip():
        raise ValueError("nome obrigatório")
    if pai.tipo == "analitica":
        pai.tipo = "sintetica"                            # pai passa a agrupar
    c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=_proximo_codigo(db, pai),
              nome=nome.strip(), grupo=pai.grupo, tipo="analitica", natureza=_natureza(pai.grupo),
              pai_id=pai.id, ativa=1, ordem=999)
    db.add(c)
    db.commit()
    return _serial(c)


def editar_conta(db, owner_tipo, owner_id, conta_id, nome=None, ordem=None):
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    if nome is not None:
        if not nome.strip():
            raise ValueError("nome obrigatório")
        c.nome = nome.strip()
    if ordem is not None:
        c.ordem = int(ordem)
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
    ("1.1", "Produção própria"), ("1.2", "Fábricas e Fornecedores"),
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
    return {"id": c.id, "codigo": c.codigo, "nome": c.nome, "pai_id": c.pai_id, "ativo": bool(c.ativo)}


def listar_centros_custo(db, owner_tipo, owner_id, incluir_inativos=False):
    """Árvore (lista de raízes com 'filhos'), ordenada por 'ordem'/codigo. Seed-on-first-access."""
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
    remover_conta — Centro de Custo não tem lançamento próprio, só é referenciado por Conta)."""
    c = _get_own_cc(db, owner_tipo, owner_id, cc_id)
    if not _cc_tem_filhos(db, c) and not _cc_tem_uso(db, c):
        db.delete(c)
        db.commit()
        return {"acao": "apagado", "id": cc_id}
    c.ativo = 0
    db.commit()
    return {"acao": "inativado", "id": cc_id}


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
CLASSIFICACAO_GRUPO5_V1 = {
    "5.1.01": ("1.2", "variavel"), "5.1.02": ("1.4", "variavel"),
    "5.2.01": ("1.3", "variavel"), "5.2.02": ("1.3", "variavel"), "5.2.03": ("1.3", "variavel"),
    "5.2.04": ("1.4", "fixo"),     "5.2.05": ("1.3", "variavel"), "5.2.06": ("1.4", "variavel"),
    "5.2.07": ("1.4", "variavel"), "5.2.08": ("1.4", "variavel"), "5.2.09": ("1.3", "variavel"),
    "5.2.10": ("1.4", "fixo"),     "5.2.12": ("3.1", "variavel"), "5.2.13": ("3.1", "variavel"),
    "5.3.01": ("2.1", "variavel"), "5.3.02": ("2.1", "variavel"), "5.3.03": ("4.3", "variavel"),
    "5.3.04": ("2.3", "variavel"), "5.3.05": ("2.1", "variavel"), "5.3.06": ("2.1", "fixo"),
    "5.3.07": ("2.3", "fixo"),     "5.3.08": ("2.3", "fixo"),     "5.3.09": ("2.3", "fixo"),
    "5.3.11": ("2.3", "fixo"),     "5.3.12": ("2.3", "fixo"),     "5.3.13": ("2.1", "variavel"),
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
    "5.5.04": ("4.3", "variavel"), "5.5.05": ("4.3", "fixo"),     "5.6.10": ("4.3", "fixo"),
}


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
    from datetime import datetime as _dt
    lan = Lancamento(owner_tipo=owner_tipo, owner_id=owner_id, data=data or _dt.utcnow(),
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


def listar_lancamentos(db, owner_tipo, owner_id, projeto_id=None, ini=None, fim=None, limite=500):
    q = db.query(Lancamento).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    if projeto_id:
        q = q.filter(Lancamento.projeto_id == projeto_id)
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
    # Impostos = PROVISÃO (Tipo D). CONTRATO: passivo nasce SEM tocar a DRE — ativo diferido (1.1.05) ×
    # Provisão de Impostos (2.1.04.13). EMISSÃO (proporcional Merc/Serv): a dedução entra na DRE
    # (4.3.01 × baixa do ativo 1.1.05) e a obrigação fiscal real crystalliza (2.1.04.13 × 2.1.03).
    "fechamento_venda_impostos":            ("1.1.05", "2.1.04.13", "Provisão de Impostos — reserva no contrato (ativo diferido)"),
    "faturamento_impostos_deducao":         ("4.3.01", "1.1.05",    "Impostos — dedução da receita na emissão (baixa do ativo diferido)"),
    "faturamento_impostos_obrigacao":       ("2.1.04.13", "2.1.03", "Impostos — efetivação da obrigação fiscal na emissão"),
    # Custo financeiro (Total Flex): despesa financeira × Financiamento a Pagar  [CONFIRMAR CONTADOR]
    "custo_financeiro":                     ("5.5.03", "2.1.05",    "Custo Financeiro (antecipação de recebíveis — Total Flex)"),
    # Ciclo de caixa
    "faturamento":                  ("1.1.02", "4.1.01",    "Faturamento (NF-e emitida)"),
    "recebimento":                  ("1.1.01", "1.1.02",    "Recebimento do cliente"),
    "pagamento_comissao":           ("2.1.04.01", "1.1.01",  "Pagamento de comissão (baixa da provisão)"),
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
    # Recebimento (entrada + parcelas Total Flex/Aymoré) abate Contas a Receber, não a Receita a Realizar.
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
    Faz o SPLIT do valor entre baixar o Adiantamento do projeto (2.1.06, até o saldo em aberto) e
    constituir Contas a Receber (1.1.02) pelo resto. Idempotente por documento (refs `ref_base:adiantado`
    e `ref_base:areceber`) e crash-safe: se a 1ª perna já existe, o split é RECUPERADO dela (não
    recalculado do pool, que já mudou). Invariantes: soma das pernas == valor; 2.1.06 do projeto ≥ 0."""
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
    if ja_a is not None:
        usa = ja_a["valor"]                    # crash-recovery: split congelado na 1ª perna
    else:
        usa = round(min(saldo_adiantamento_projeto(db, owner_tipo, owner_id, projeto_id), valor), 2)
    resto = round(valor - usa, 2)
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
# (_PROV_FECHAMENTO). com_adm não tem provisão constituída no contrato (sem ativo diferido) → sem delta.
_AF_ITEM_RUBRICA = {
    "prov_mont": "montagem", "prov_gar": "garantia", "assist": "assistencia",
    "frete_fab": "frete_fabrica", "frete_loc": "frete_local", "ins_loc": "insumos",
    "com_med": "com_medidor", "com_proj_exec": "com_proj_exec",
    "com_venda": "retencao_com_vendas", "prov_imp": "impostos",
    # F0 (bug ①): custos adicionais — ajustáveis na AF (mesma chave em _PROV_FECHAMENTO).
    "com_arq": "com_arq", "pro_fid": "pro_fid", "cust_via": "cust_via", "brinde": "brinde",
    # out_forn (Outros Fornecedores) NÃO entra: só nasce por reclassificação, sem evento de fechamento.
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
    "financeira":       "fechamento_venda_custo_financeiro",  # despesa financeira PROVISIONADA (taxa da financeira)
    "loja_antecipacao": "fechamento_venda_custo_financeiro",  # despesa PROVISIONADA (antecipação bancária; custo real depois)
    "loja":             "constituir_juros_direto",            # receita financeira a apropriar (capital próprio, sem despesa)
    # 'avista' → None (Cust_Fin = 0)
}


def evento_custo_financeiro(ramo):
    """Evento de constituição do custo financeiro por ramo (Fatia B). None p/ 'avista'/desconhecido."""
    return _RAMO_CFIN_EVENTO.get(ramo)


def trocar_ramo_custo_financeiro(db, owner_tipo, owner_id, projeto_id, ramo_atual, ramo_novo, valor, ref_base, data=None):
    """#B.2 — troca o ramo do custo financeiro DEPOIS do fechamento (box da AF). Reverte o que o
    fechamento lançou e constitui o ramo novo. Idempotente por `ref_base`.
      - loja → provisão (financeira/antecipação): estorna os juros a apropriar (reverter_juros_direto) e
        constitui a Provisão de Custo Financeiro (fechamento_venda_custo_financeiro).
      - provisão → loja: reverte a provisão (ajustar_provisao_delta → 0) e constitui os juros a apropriar.
      - financeira ↔ loja_antecipacao: **no-op** contábil (mesma provisão; muda só a conta de despesa no
        reconhecimento futuro).
    Retorna o ramo efetivo (ramo_novo).
    """
    _PROV = {"financeira", "loja_antecipacao"}
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
    "financeira":       "reconhecimento_despesa_custo_financeiro", # 5.5.04 Custo Financeiro sobre Vendas
}


def reconhecer_custo_financeiro(db, owner_tipo, owner_id, projeto_id, ramo, valor, ref, data=None):
    """#B — reconhece a DESPESA do custo financeiro na DRE quando o custo real é apurado (a loja desconta
    os boletos na antecipação bancária, ou a financeira liquida): despesa (antecipação → 5.5.03;
    financeira → 5.5.04) × baixa do ativo diferido 1.1.06.19, CAPADO ao saldo do ativo em aberto (padrão
    do matching operacional na NF-e). A Provisão 2.1.04.19 SOBREVIVE (paga ao banco/financeira depois).
    Ramo 'loja' (próprio) / 'avista' não tem despesa → None. Idempotente por ref."""
    evento = _RAMO_CFIN_DESPESA.get(ramo)
    if evento is None:
        return None
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    seed_plano(db, owner_tipo, owner_id)
    saldo_ativo = round(total_lancado(db, owner_tipo, owner_id, "1.1.06.19", "debito", projeto_id)
                        - total_lancado(db, owner_tipo, owner_id, "1.1.06.19", "credito", projeto_id), 2)
    mv = round(min(float(valor or 0), max(saldo_ativo, 0.0)), 2)
    if mv <= 0:
        return None
    return registrar_evento(db, owner_tipo, owner_id, evento, mv, projeto_id=projeto_id, ref=ref)


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
    previsto só estimado (caso do Total Flex, que mistura capital+juros na parcela). Não mexe na
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
    """Fecha o saldo em aberto da provisão (de um projeto). Pras rubricas com despesa em tempo real
    (`_PROV_DESPESA_POR_ATIVO` — as 15 do antigo matching pleno): CANCELA contra o ativo diferido
    espelho (1.1.06.0X), SEM TOCAR A DRE em nenhuma direção (2026-08-07, achado do usuário) — SOBRA
    (provisionado > efetivado) é dinheiro nunca gasto, não há despesa nenhuma a reverter, então não
    vira "receita"; FALTA (efetivado > provisionado) já teve a despesa real reconhecida em tempo real,
    a cada efetivação — não há nada NOVO a lançar, só o residual mecânico entre ativo e provisão a
    zerar. Pras demais (Impostos, Custo Financeiro — rota própria, despesa não é em tempo real aqui):
    mantido o comportamento antigo — SOBRA → Provisão × Reversão de Provisões (4.4.02, receita); FALTA
    → Ajuste de Provisões (5.6.10, despesa) × Provisão. Zera a provisão do projeto. Idempotente por ref."""
    ja = lancamento_por_ref(db, owner_tipo, owner_id, ref)
    if ja is not None:
        return ja
    seed_plano(db, owner_tipo, owner_id)
    saldo = round(_mov(db, owner_tipo, owner_id, codigo_provisao, "credor", None, None, projeto_id=projeto_id), 2)
    if abs(saldo) < 0.005:
        return None
    prov = _conta_por_codigo(db, owner_tipo, owner_id, codigo_provisao)
    ativo_cod = _ativo_diferido_de(codigo_provisao)
    despesa_em_tempo_real = (_PROV_DESPESA_POR_ATIVO.get(ativo_cod) is not None
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
    if saldo > 0:   # sobra → receita (débito Provisão × crédito 4.4.02) — rota antiga (impostos/custo financeiro)
        cc = _conta_por_codigo(db, owner_tipo, owner_id, "4.4.02")
        return lancar(db, owner_tipo, owner_id, prov.id, cc.id, saldo, data=data, projeto_id=projeto_id,
                      origem=_ORIGEM_RESOL_SOBRA, historico="Reversão de provisão (sobra → receita)", ref=ref)
    cd = _conta_por_codigo(db, owner_tipo, owner_id, "5.6.10")   # falta → despesa (débito 5.6.10 × crédito Provisão)
    return lancar(db, owner_tipo, owner_id, cd.id, prov.id, -saldo, data=data, projeto_id=projeto_id,
                  origem=_ORIGEM_RESOL_FALTA, historico="Ajuste de provisão (falta → despesa)", ref=ref)


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
        provs.append({"codigo": c.codigo, "nome": c.nome, "tipo": _PROV_PAINEL_TIPO.get(c.codigo, "O"),
                      "provisionado": provisionado, "efetivado": efetivado,
                      "saldo": saldo, "resolvido": resolvido, "resolvido_liquido": resolvido_liquido,
                      "saldo_aberto": saldo_aberto})
    t = lambda k: round(sum(p[k] for p in provs), 2)
    return {"projeto_id": projeto_id, "provisoes": provs,
            "totais": {"provisionado": t("provisionado"), "efetivado": t("efetivado"),
                       "saldo": t("saldo"), "resolvido": t("resolvido"),
                       "resolvido_liquido": t("resolvido_liquido"), "saldo_aberto": t("saldo_aberto")}}


def conciliar_final(db, owner_tipo, owner_id, projeto_id, ref_base):
    """FASE D2 — Conciliação Final (etapa 21): resolve à força TODO saldo remanescente das provisões de
    custo do projeto (as 10 rubricas). Sobra (provisionado > efetivado) → 4.4.02 (receita); falta →
    5.6.10 (despesa). Zera as pendências. FORA da conciliação (não força — mas ficam visíveis e
    editáveis via efetivar_provisao/resolver_saldo_provisao na tela, achado 2026-08-07):
    - Impostos (2.1.04.13): rota própria DE VERDADE — efetivar_impostos_segmento fecha a conta
      sozinha a cada NF-e emitida.
    - Custo Financeiro (2.1.04.19): rota PARCIAL — reconhecer_custo_financeiro (Fatia B) só baixa
      o ATIVO diferido (1.1.06.19); a provisão (2.1.04.19) em si não tem fechamento automático,
      sobrevive até alguém efetivar/resolver manualmente (venda financiada = dinheiro real).
    Idempotente por ref (ref_base:<codigo>). Retorna {codigo: saldo_resolvido} (positivo=sobra,
    negativo=falta)."""
    seed_plano(db, owner_tipo, owner_id)
    excluir = _PROV_PAINEL_EXCLUI | {"2.1.04.13", "2.1.04.19"}   # ver docstring — nem toda "rota própria" fecha a provisão sozinha
    contas = (db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, tipo="analitica")
              .filter(Conta.codigo.like(GRUPO_PROVISOES + ".%")).order_by(Conta.codigo).all())
    out = {}
    for c in contas:
        if c.codigo in excluir:
            continue
        saldo = round(_mov(db, owner_tipo, owner_id, c.codigo, "credor", None, None, projeto_id=projeto_id), 2)
        if abs(saldo) < 0.005:
            continue
        lan = resolver_saldo_provisao(db, owner_tipo, owner_id, projeto_id, c.codigo, ref=ref_base + ":" + c.codigo)
        if lan is not None:
            out[c.codigo] = saldo
    return out


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
    "2.1.04.01",   # Comissão — despesa de venda; baixa via pagamento_comissao, não é set-aside de custo
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
    "2.1.04.10": "A", "2.1.04.11": "A", "2.1.04.12": "A",             # Comissões / Pessoas
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
    }


def provisoes_da_venda(db, owner_tipo, owner_id, projeto_id, ini=None, fim=None):
    """Painel de Provisões da venda (v6 §6): as 3 provisões do projeto com o saldo EM ABERTO
    (constituído − revertido) = saldo da conta de Provisão (credora) filtrado pelo projeto."""
    linhas = []
    for chave, (_ev, cod) in _PROV_VENDA.items():
        c = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id, codigo=cod).first()
        saldo = 0.0
        if c is not None:
            saldo = _mov(db, owner_tipo, owner_id, cod, "credor", ini, fim, projeto_id=projeto_id)
        linhas.append({"chave": chave, "codigo": cod, "nome": c.nome if c else chave,
                       "saldo_em_aberto": saldo})
    return {"projeto_id": projeto_id, "provisoes": linhas,
            "total_em_aberto": round(sum(l["saldo_em_aberto"] for l in linhas), 2)}


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
    Mesmo formato de `dre()` (compatível com o frontend); sem `detalhe` (a simulação não tem
    composição linha-a-linha real pra detalhar)."""
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
    receita_bruta = 0.0 if modo == "antecipacao_contrato" else real["receita_bruta"]
    por_conta_despesa = {}
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
        c = _conta_por_codigo(db, ot, oid, "1.1.09")
        if c is None:
            continue
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
    """Calcula a reconciliação e persiste um PeriodoContabil (status='fechado')."""
    import json as _json
    rec = reconciliar(db, owner_tipo, owner_id, ini, fim, metodologia)
    p = PeriodoContabil(owner_tipo=owner_tipo, owner_id=owner_id, inicio=ini, fim=fim, status="fechado",
                        metodologia=metodologia, resultado_societario=rec["resultado_societario_oficial"],
                        soma_margem_plena=rec["soma_margem_plena"], divergencia_residual=rec["divergencia_residual"],
                        dados_json=_json.dumps(rec["alocacao_por_projeto"]))
    db.add(p)
    db.commit()
    return {"id": p.id, **rec}


def listar_periodos(db, owner_tipo, owner_id):
    ps = (db.query(PeriodoContabil).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
          .order_by(PeriodoContabil.criado_em.desc()).all())
    return [{"id": p.id, "inicio": p.inicio.isoformat() if p.inicio else None,
             "fim": p.fim.isoformat() if p.fim else None, "status": p.status,
             "metodologia": p.metodologia, "resultado_societario": p.resultado_societario,
             "soma_margem_plena": p.soma_margem_plena, "divergencia_residual": p.divergencia_residual}
            for p in ps]
