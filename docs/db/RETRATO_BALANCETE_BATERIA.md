# Retrato do balancete — bateria de ciclo completo

**Gerado por `tests/test_bateria_ciclo.py::test_gravar_retrato_do_balancete`. NÃO é declaração de correção — é detector de mudança.** Vários saldos abaixo estão errados hoje (ver docs/db/ACHADOS_CONTABEIS.md, ACHADO-01/02/03/12) e aparecem no retrato do jeito que estão. Quem julga certo/errado são as invariantes de `tests/test_bateria_ciclo.py`, não este arquivo. Se este arquivo mudar num PR futuro, o diff é o alarme — investigue por que o comportamento mudou.

## loja_sem_custo_sem_aditivo (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 23600.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 21800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## loja_com_custo_sem_aditivo (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 26137.00 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 4.1.01 Receitas com Vendas | 24143.50 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.03 Receita Financeira | 1993.50 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## loja_sem_custo_com_aditivo (ramo=loja, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 26600.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 2.1.06 Receita a Realizar | 3000.00 |
| 4.1.01 Receitas com Vendas | 21800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 1050.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## loja_com_custo_com_aditivo (ramo=loja, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 29137.00 |
| 2.1.01 Fornecedores a Pagar | 11510.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 2.1.06 Receita a Realizar | 3000.00 |
| 4.1.01 Receitas com Vendas | 24143.50 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.03 Receita Financeira | 1993.50 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 1050.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## loja_antecipacao_sem_custo_sem_aditivo (ramo=loja_antecipacao, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 21800.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 2.1.04.19 Provisão de Custo Financeiro | 1800.00 |
| 4.1.01 Receitas com Vendas | 21800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.03 Custo de Antecipação de Recebíveis | 1800.00 |

## loja_antecipacao_com_custo_sem_aditivo (ramo=loja_antecipacao, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24143.50 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 2.1.04.19 Provisão de Custo Financeiro | 1993.50 |
| 4.1.01 Receitas com Vendas | 24143.50 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.03 Custo de Antecipação de Recebíveis | 1993.50 |

## loja_antecipacao_sem_custo_com_aditivo (ramo=loja_antecipacao, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24800.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 2.1.04.19 Provisão de Custo Financeiro | 1800.00 |
| 2.1.06 Receita a Realizar | 3000.00 |
| 4.1.01 Receitas com Vendas | 21800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 1050.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.03 Custo de Antecipação de Recebíveis | 1800.00 |

## loja_antecipacao_com_custo_com_aditivo (ramo=loja_antecipacao, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 27143.50 |
| 2.1.01 Fornecedores a Pagar | 11510.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 2.1.04.19 Provisão de Custo Financeiro | 1993.50 |
| 2.1.06 Receita a Realizar | 3000.00 |
| 4.1.01 Receitas com Vendas | 24143.50 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 1050.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.03 Custo de Antecipação de Recebíveis | 1993.50 |

## financeira_sem_custo_sem_aditivo (ramo=financeira, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 21800.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 2.1.04.19 Provisão de Custo Financeiro | 1800.00 |
| 4.1.01 Receitas com Vendas | 21800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.04 Custo Financeiro sobre Vendas | 1800.00 |

## financeira_com_custo_sem_aditivo (ramo=financeira, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24143.50 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 2.1.04.19 Provisão de Custo Financeiro | 1993.50 |
| 4.1.01 Receitas com Vendas | 24143.50 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.04 Custo Financeiro sobre Vendas | 1993.50 |

## financeira_sem_custo_com_aditivo (ramo=financeira, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24800.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 2.1.04.19 Provisão de Custo Financeiro | 1800.00 |
| 2.1.06 Receita a Realizar | 3000.00 |
| 4.1.01 Receitas com Vendas | 21800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 1050.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.04 Custo Financeiro sobre Vendas | 1800.00 |

## financeira_com_custo_com_aditivo (ramo=financeira, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 27143.50 |
| 2.1.01 Fornecedores a Pagar | 11510.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 2.1.04.19 Provisão de Custo Financeiro | 1993.50 |
| 2.1.06 Receita a Realizar | 3000.00 |
| 4.1.01 Receitas com Vendas | 24143.50 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 1050.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |
| 5.5.04 Custo Financeiro sobre Vendas | 1993.50 |

## toggle_comissao_arq_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24544.00 |
| 2.1.01 Fornecedores a Pagar | 10010.00 |
| 2.1.03 Obrigações Tributárias | 1813.76 |
| 4.1.01 Receitas com Vendas | 22672.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1813.76 |
| 4.4.03 Receita Financeira | 1872.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## toggle_fidelidade_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24072.00 |
| 2.1.01 Fornecedores a Pagar | 9610.00 |
| 2.1.03 Obrigações Tributárias | 1778.88 |
| 4.1.01 Receitas com Vendas | 22236.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1778.88 |
| 4.4.03 Receita Financeira | 1836.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## toggle_fora_da_sede_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 23954.00 |
| 2.1.01 Fornecedores a Pagar | 9510.00 |
| 2.1.03 Obrigações Tributárias | 1770.16 |
| 4.1.01 Receitas com Vendas | 22127.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1770.16 |
| 4.4.03 Receita Financeira | 1827.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## toggle_brinde_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 23777.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1757.08 |
| 4.1.01 Receitas com Vendas | 21963.50 |
| 4.3.01 Simples Nacional s/ Vendas | -1757.08 |
| 4.4.03 Receita Financeira | 1813.50 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## toggle_custo_especial_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24190.00 |
| 2.1.01 Fornecedores a Pagar | 9710.00 |
| 2.1.03 Obrigações Tributárias | 1787.60 |
| 4.1.01 Receitas com Vendas | 22345.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1787.60 |
| 4.4.03 Receita Financeira | 1845.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## toggle_incluir_custos_absorve (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 23600.00 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 21800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.04 Pontos Programa de Relacionamento | 400.00 |
| 5.3.12 Brindes | 150.00 |
| 5.3.14 Viagens de Especificador | 300.00 |
| 5.3.15 Comissão de Arquiteto | 800.00 |
| 5.3.17 Custo Especial de Projeto | 500.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## controle_positivo_loja_avista (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 20000.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1600.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1600.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## controle_positivo_loja_antecipacao_avista (ramo=loja_antecipacao, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 20000.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1600.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1600.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

## controle_positivo_financeira_avista (ramo=financeira, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 20000.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1600.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1600.00 |
| 5.1.01 CMV Fábrica | 6000.00 |
| 5.1.02 Frete de Fábrica | 250.00 |
| 5.2.01 Montagem | 900.00 |
| 5.2.08 Frete Local | 180.00 |
| 5.2.09 Insumos Locais | 220.00 |
| 5.2.12 Garantia | 400.00 |
| 5.2.13 Assistência Técnica | 350.00 |
| 5.3.01 Comissão de Vendedor | 300.00 |
| 5.3.03 Comissão Administrativa | 260.00 |
| 5.3.18 Comissão de Medidor | 150.00 |
| 5.3.19 Comissão de Projeto/Executivo | 200.00 |

