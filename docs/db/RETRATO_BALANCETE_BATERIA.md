# Retrato do balancete — bateria de ciclo completo

**Gerado por `tests/test_bateria_ciclo.py::test_gravar_retrato_do_balancete`. NÃO é declaração de correção — é detector de mudança.** Quem julga certo/errado são as invariantes de `tests/test_bateria_ciclo.py`, não este arquivo. Se este arquivo mudar num PR futuro, o diff é o alarme — investigue por que o comportamento mudou.

## loja_sem_custo_sem_aditivo (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 21800.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |

## loja_com_custo_sem_aditivo (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24143.50 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 4.1.01 Receitas com Vendas | 22150.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.03 Receita Financeira | 1993.50 |

## loja_sem_custo_com_aditivo (ramo=loja, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24800.00 |
| 1.1.06.02 Montagem a Apropriar | 1050.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 23000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |

## loja_com_custo_com_aditivo (ramo=loja, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 27143.50 |
| 1.1.06.02 Montagem a Apropriar | 1050.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 11510.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 4.1.01 Receitas com Vendas | 25150.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.03 Receita Financeira | 1993.50 |

## loja_antecipacao_sem_custo_sem_aditivo (ramo=loja_antecipacao, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 21800.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |

## loja_antecipacao_com_custo_sem_aditivo (ramo=loja_antecipacao, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24143.50 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 4.1.01 Receitas com Vendas | 22150.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.03 Receita Financeira | 1993.50 |

## loja_antecipacao_sem_custo_com_aditivo (ramo=loja_antecipacao, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 24800.00 |
| 1.1.06.02 Montagem a Apropriar | 1050.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 23000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |

## loja_antecipacao_com_custo_com_aditivo (ramo=loja_antecipacao, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 27143.50 |
| 1.1.06.02 Montagem a Apropriar | 1050.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 11510.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 4.1.01 Receitas com Vendas | 25150.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.03 Receita Financeira | 1993.50 |

## financeira_sem_custo_sem_aditivo (ramo=financeira, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 20000.00 |
| 1.1.02 Contas a Receber (Clientes) | -1800.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.05 Ajuste de Retenção Financeira | -1800.00 |

## financeira_com_custo_sem_aditivo (ramo=financeira, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 22150.00 |
| 1.1.02 Contas a Receber (Clientes) | -1993.50 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 4.1.01 Receitas com Vendas | 22150.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.05 Ajuste de Retenção Financeira | -1993.50 |

## financeira_sem_custo_com_aditivo (ramo=financeira, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 23000.00 |
| 1.1.02 Contas a Receber (Clientes) | -1800.00 |
| 1.1.06.02 Montagem a Apropriar | 1050.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 23000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.05 Ajuste de Retenção Financeira | -1800.00 |

## financeira_com_custo_com_aditivo (ramo=financeira, aditivo=True)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 25150.00 |
| 1.1.02 Contas a Receber (Clientes) | -1993.50 |
| 1.1.06.02 Montagem a Apropriar | 1050.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 11510.00 |
| 2.1.03 Obrigações Tributárias | 1931.48 |
| 4.1.01 Receitas com Vendas | 25150.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1931.48 |
| 4.4.05 Ajuste de Retenção Financeira | -1993.50 |

## toggle_comissao_arq_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 22672.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 10010.00 |
| 2.1.03 Obrigações Tributárias | 1813.76 |
| 4.1.01 Receitas com Vendas | 20800.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1813.76 |
| 4.4.03 Receita Financeira | 1872.00 |

## toggle_fidelidade_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 22236.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9610.00 |
| 2.1.03 Obrigações Tributárias | 1778.88 |
| 4.1.01 Receitas com Vendas | 20400.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1778.88 |
| 4.4.03 Receita Financeira | 1836.00 |

## toggle_fora_da_sede_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 22127.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9510.00 |
| 2.1.03 Obrigações Tributárias | 1770.16 |
| 4.1.01 Receitas com Vendas | 20300.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1770.16 |
| 4.4.03 Receita Financeira | 1827.00 |

## toggle_brinde_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 21963.50 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9360.00 |
| 2.1.03 Obrigações Tributárias | 1757.08 |
| 4.1.01 Receitas com Vendas | 20150.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1757.08 |
| 4.4.03 Receita Financeira | 1813.50 |

## toggle_custo_especial_isolado (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 22345.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9710.00 |
| 2.1.03 Obrigações Tributárias | 1787.60 |
| 4.1.01 Receitas com Vendas | 20500.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1787.60 |
| 4.4.03 Receita Financeira | 1845.00 |

## toggle_incluir_custos_absorve (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 21800.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.15 Comissão de Arquiteto a Apropriar | 800.00 |
| 1.1.06.16 Programa de Fidelidade a Apropriar | 400.00 |
| 1.1.06.17 Custo de Viagem a Apropriar | 300.00 |
| 1.1.06.18 Brinde a Apropriar | 150.00 |
| 1.1.06.20 Custo Especial a Apropriar | 500.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 11360.00 |
| 2.1.03 Obrigações Tributárias | 1744.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1744.00 |
| 4.4.03 Receita Financeira | 1800.00 |

## controle_positivo_loja_avista (ramo=loja, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 20000.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1600.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1600.00 |

## controle_positivo_loja_antecipacao_avista (ramo=loja_antecipacao, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 20000.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1600.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1600.00 |

## controle_positivo_financeira_avista (ramo=financeira, aditivo=False)

| conta | saldo |
|---|---|
| 1.1.01 Caixa/Bancos | 20000.00 |
| 1.1.06.02 Montagem a Apropriar | 900.00 |
| 1.1.06.03 Garantia a Apropriar | 400.00 |
| 1.1.06.05 Assistência Técnica a Apropriar | 350.00 |
| 1.1.06.06 Custo de Fábrica a Apropriar | 6000.00 |
| 1.1.06.07 Frete de Fábrica a Apropriar | 250.00 |
| 1.1.06.08 Frete Local a Apropriar | 180.00 |
| 1.1.06.09 Insumos Locais a Apropriar | 220.00 |
| 1.1.06.10 Comissão de Medidor a Apropriar | 150.00 |
| 1.1.06.11 Comissão de Projeto/Executivo a Apropriar | 200.00 |
| 1.1.06.12 Retenção de Comissão de Vendas a Apropriar | 300.00 |
| 1.1.06.21 Comissão Administrativa a Apropriar | 260.00 |
| 2.1.01 Fornecedores a Pagar | 9210.00 |
| 2.1.03 Obrigações Tributárias | 1600.00 |
| 4.1.01 Receitas com Vendas | 20000.00 |
| 4.3.01 Simples Nacional s/ Vendas | -1600.00 |

