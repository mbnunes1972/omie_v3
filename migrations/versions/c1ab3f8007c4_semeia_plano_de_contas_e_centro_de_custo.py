"""semeia plano de contas e centro de custo

O gabarito (arvore de centro_custo + classificacao de conta.centro_custo_id/
natureza_custo) so' existe hoje porque foi gravado uma vez pelo bootstrap do
servidor, contra o localhost — nao esta em nenhuma migration. Um ambiente
construido pela baseline (0001) nasce com a estrutura certa e o plano de
contas vazio, o que bloqueia reconstruir Integracao/Homologacao/Producao so'
por `alembic upgrade head`. Esta revisao fecha essa lacuna.

CENTRO_CUSTO e CONTA abaixo foram GERADOS por introspeccao do localhost
(owner de referencia: rede id=1), nao digitados a mao — 16 nos de centro de
custo e 160 codigos de conta, dos quais ~59 (grupo 5) carregam classificacao
de centro de custo/natureza. `CONTA_NOME_OVERRIDE_POR_OWNER_TIPO` cobre os 2
unicos codigos (1.1.09, 2.1.09) cujo nome diverge entre rede e loja no dado
real ("Conta Corrente com Lojas do Grupo" vs "Créditos/Débitos com Empresas").
Fora isso, a arvore e a classificacao sao identicas nos 3 owners de hoje.

OWNERS fixa (owner_tipo, owner_id) = 3 valores literais (rede=1, loja=1,
loja=3). Isso NAO viola a regra de "nenhum id numerico": owner_id aqui e'
dado de negocio (qual dos 3 owners reais), o mesmo em todo ambiente porque e'
a MESMA empresa clonada por estagio de deploy — nao um id de linha desta
migration. Os ids que a regra proibe sao os PRoprios (centro_custo.id,
conta.id, pai_id, centro_custo_id): nenhum aparece como literal abaixo, todos
sao resolvidos em runtime por SELECT contra a chave natural (owner + codigo,
owner + nome + pai) apos cada INSERT/UPDATE.

upgrade() roda em 3 passadas por owner, cada uma dependendo da anterior:
  1) arvore de centro_custo (cria quem falta por codigo, atualiza nome/pai/
     ativo de quem ja existe e diverge do gabarito).
  2) arvore de conta (mesma logica: cria por codigo faltante, atualiza nome/
     grupo/tipo/natureza/pai de quem diverge). Precisa da passada 1 pronta
     so' para os codigos de conta que sao filhos de outra conta (pai_id),
     nao do centro de custo.
  3) classificacao (conta.centro_custo_id/natureza_custo). Roda por ultimo
     porque depende dos ids de centro_custo (passada 1) e de conta (passada
     2) ja resolvidos por codigo.
Idempotente nas duas direcoes: banco vazio semeia (passa pelo ramo INSERT em
tudo); banco que ja tem a arvore so' atualiza o que diverge do gabarito (ramo
UPDATE, comparando valor atual x gabarito antes de escrever) — rodar 2x nao
duplica linha nem falha em UniqueConstraint.

Revision ID: c1ab3f8007c4
Revises: bf43dd02888b
Create Date: 2026-08-27 20:28:34.037065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1ab3f8007c4'
down_revision: Union[str, Sequence[str], None] = 'bf43dd02888b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OWNERS = [('rede', 1), ('loja', 1), ('loja', 3)]

# (codigo, nome, pai_codigo, ativo) — pais sempre antes dos filhos na lista.
CENTRO_CUSTO = [
    ('1', 'Operacional', None, 1),
    ('2', 'Comercial', None, 1),
    ('3', 'Pós-venda', None, 1),
    ('4', 'Suporte', None, 1),
    ('1.2', 'Fábricas e Fornecedores', '1', 1),
    ('1.3', 'Montagem', '1', 1),
    ('1.4', 'Logística/Expedição', '1', 1),
    ('1.5', 'Instalações/Infraestrutura', '1', 1),
    ('2.1', 'Vendas/Loja', '2', 1),
    ('2.3', 'Marketing', '2', 1),
    ('3.1', 'Assistência Técnica/Pós-venda', '3', 1),
    ('3.2', 'Projetos/Design', '3', 1),
    ('4.2', 'Sistemas e TI', '4', 1),
    ('4.3', 'Administrativo-financeiro', '4', 1),
    ('4.4', 'Diretoria/Gestão', '4', 1),
    ('4.5', 'Custos Distribuídos', '4', 1),
]

# (codigo, nome, grupo, tipo, natureza, pai_codigo, ativa, centro_custo_codigo, natureza_custo)
CONTA = [
    ('1', 'ATIVO', 1, 'sintetica', 'devedora', None, 1, None, None),
    ('2', 'PASSIVO', 2, 'sintetica', 'credora', None, 1, None, None),
    ('3', 'PATRIMÔNIO LÍQUIDO', 3, 'sintetica', 'credora', None, 1, None, None),
    ('4', 'RECEITAS', 4, 'sintetica', 'credora', None, 1, None, None),
    ('5', 'DESPESAS / CUSTOS', 5, 'sintetica', 'devedora', None, 1, None, None),
    ('1.1', 'Circulante', 1, 'sintetica', 'devedora', '1', 1, None, None),
    ('1.2', 'Não Circulante', 1, 'sintetica', 'devedora', '1', 1, None, None),
    ('2.1', 'Circulante', 2, 'sintetica', 'credora', '2', 1, None, None),
    ('2.2', 'Não Circulante', 2, 'sintetica', 'credora', '2', 1, None, None),
    ('3.1', 'Capital Social', 3, 'analitica', 'credora', '3', 1, None, None),
    ('3.2', 'Reservas', 3, 'analitica', 'credora', '3', 1, None, None),
    ('3.3', 'Lucros/Prejuízos Acumulados', 3, 'analitica', 'credora', '3', 1, None, None),
    ('3.4', 'Distribuição de Lucros', 3, 'analitica', 'credora', '3', 1, None, None),
    ('3.5', 'Ajustes de Exercícios Anteriores', 3, 'analitica', 'credora', '3', 1, None, None),
    ('4.1', 'Vendas de Produtos', 4, 'sintetica', 'credora', '4', 1, None, None),
    ('4.2', 'Serviços', 4, 'sintetica', 'credora', '4', 1, None, None),
    ('4.3', 'Deduções', 4, 'sintetica', 'credora', '4', 1, None, None),
    ('4.4', 'Outras Receitas Não Operacionais', 4, 'sintetica', 'credora', '4', 1, None, None),
    ('5.1', 'CMV', 5, 'sintetica', 'devedora', '5', 1, None, None),
    ('5.2', 'Custo de Serviço', 5, 'sintetica', 'devedora', '5', 1, None, None),
    ('5.3', 'Despesas Comerciais', 5, 'sintetica', 'devedora', '5', 1, None, None),
    ('5.4', 'Despesas Administrativas', 5, 'sintetica', 'devedora', '5', 1, None, None),
    ('5.5', 'Despesas Financeiras', 5, 'sintetica', 'devedora', '5', 1, None, None),
    ('5.6', 'Ajustes de Provisões', 5, 'sintetica', 'devedora', '5', 1, None, None),
    ('1.1.01', 'Caixa/Bancos', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.02', 'Contas a Receber (Clientes)', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.03', 'Estoques', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.04', 'Adiantamentos a Fornecedores', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.05', 'Impostos a Apropriar', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.06', 'Custos a Apropriar', 1, 'sintetica', 'devedora', '1.1', 1, None, None),
    ('1.1.07', 'Recebíveis de Parcelamentos', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.08', 'Créditos com a Fábrica', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.09', 'Conta Corrente com Lojas do Grupo (a receber)', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.1.10', 'Recebíveis Duvidosos', 1, 'analitica', 'devedora', '1.1', 1, None, None),
    ('1.2.1', 'Imobilizado', 1, 'sintetica', 'devedora', '1.2', 1, None, None),
    ('1.2.2', 'Intangível', 1, 'analitica', 'devedora', '1.2', 1, None, None),
    ('2.1.01', 'Fornecedores a Pagar', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.02', 'Obrigações Trabalhistas', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.03', 'Obrigações Tributárias', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.04', 'Provisões', 2, 'sintetica', 'credora', '2.1', 1, None, None),
    ('2.1.05', 'Financiamento Total Flex a Pagar', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.06', 'Receita a Realizar', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.07', 'Receita Financeira a Apropriar', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.08', 'Acordos com a Fábrica a Amortizar', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.09', 'Conta Corrente com Lojas do Grupo (a pagar)', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.10', 'Empréstimos Bancários', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.1.11', 'Créditos a Clientes', 2, 'analitica', 'credora', '2.1', 1, None, None),
    ('2.2.01', 'Financiamentos de Longo Prazo (principal)', 2, 'analitica', 'credora', '2.2', 1, None, None),
    ('4.1.01', 'Receitas com Vendas', 4, 'analitica', 'credora', '4.1', 1, None, None),
    ('4.1.02', 'Receita com Vendas de Assistência', 4, 'analitica', 'credora', '4.1', 1, None, None),
    ('4.2.01', 'Receita de Serviços', 4, 'analitica', 'credora', '4.2', 1, None, None),
    ('4.2.02', 'Prestação de Serviços para Terceiros', 4, 'analitica', 'credora', '4.2', 1, None, None),
    ('4.3.01', 'Simples Nacional s/ Vendas', 4, 'analitica', 'credora', '4.3', 1, None, None),
    ('4.3.02', 'Devolução de Vendas', 4, 'analitica', 'credora', '4.3', 1, None, None),
    ('4.4.01', 'Receita de Aluguéis', 4, 'analitica', 'credora', '4.4', 1, None, None),
    ('4.4.02', 'Reversão de Provisões', 4, 'analitica', 'credora', '4.4', 1, None, None),
    ('4.4.03', 'Receita Financeira', 4, 'analitica', 'credora', '4.4', 1, None, None),
    ('4.4.04', 'Ganhos com Acordos Financeiros', 4, 'analitica', 'credora', '4.4', 1, None, None),
    ('5.1.01', 'CMV Fábrica', 5, 'analitica', 'devedora', '5.1', 1, '1.2', 'variavel'),
    ('5.1.02', 'Frete de Fábrica', 5, 'analitica', 'devedora', '5.1', 1, '1.4', 'variavel'),
    ('5.2.01', 'Montagem', 5, 'analitica', 'devedora', '5.2', 1, '1.3', 'variavel'),
    ('5.2.02', 'Comissão de Montagem', 5, 'analitica', 'devedora', '5.2', 1, '1.3', 'variavel'),
    ('5.2.03', 'Viagens de Montagens', 5, 'analitica', 'devedora', '5.2', 1, '1.3', 'variavel'),
    ('5.2.04', 'Salários Operacionais', 5, 'analitica', 'devedora', '5.2', 1, '1.4', 'fixo'),
    ('5.2.05', 'Ajudante Eventual', 5, 'analitica', 'devedora', '5.2', 1, '1.3', 'variavel'),
    ('5.2.06', 'Combustível', 5, 'analitica', 'devedora', '5.2', 1, '1.4', 'fixo'),
    ('5.2.07', 'Pedágio', 5, 'analitica', 'devedora', '5.2', 1, '1.4', 'variavel'),
    ('5.2.08', 'Frete Local', 5, 'analitica', 'devedora', '5.2', 1, '1.4', 'variavel'),
    ('5.2.09', 'Insumos Locais', 5, 'analitica', 'devedora', '5.2', 1, '1.3', 'variavel'),
    ('5.2.10', 'Manutenção de Veículos', 5, 'analitica', 'devedora', '5.2', 1, '1.4', 'fixo'),
    ('5.2.12', 'Garantia', 5, 'analitica', 'devedora', '5.2', 1, '3.1', 'variavel'),
    ('5.2.13', 'Assistência Técnica', 5, 'analitica', 'devedora', '5.2', 1, '3.1', 'variavel'),
    ('5.3.01', 'Comissão de Vendedor', 5, 'analitica', 'devedora', '5.3', 1, '2.1', 'variavel'),
    ('5.3.02', 'Comissão de Indicador', 5, 'analitica', 'devedora', '5.3', 1, '2.1', 'variavel'),
    ('5.3.03', 'Comissão Administrativa', 5, 'analitica', 'devedora', '5.3', 1, '4.3', 'variavel'),
    ('5.3.04', 'Pontos Programa de Relacionamento', 5, 'analitica', 'devedora', '5.3', 1, '2.3', 'variavel'),
    ('5.3.05', 'Premiação de Vendedores', 5, 'analitica', 'devedora', '5.3', 1, '2.1', 'variavel'),
    ('5.3.06', 'Salários de Vendas', 5, 'analitica', 'devedora', '5.3', 1, '2.1', 'fixo'),
    ('5.3.07', 'Marketing/Campanhas de Divulgação', 5, 'analitica', 'devedora', '5.3', 1, '2.3', 'fixo'),
    ('5.3.08', 'Salário Marketing', 5, 'analitica', 'devedora', '5.3', 1, '2.3', 'fixo'),
    ('5.3.09', 'Site e Hospedagem', 5, 'analitica', 'devedora', '5.3', 1, '2.3', 'fixo'),
    ('5.3.11', 'Uniformes', 5, 'analitica', 'devedora', '5.3', 1, '2.3', 'fixo'),
    ('5.3.12', 'Brindes', 5, 'analitica', 'devedora', '5.3', 1, '2.3', 'variavel'),
    ('5.3.13', 'Suprimento a Cliente', 5, 'analitica', 'devedora', '5.3', 1, '2.1', 'variavel'),
    ('5.3.14', 'Viagens de Especificador', 5, 'analitica', 'devedora', '5.3', 1, '2.3', 'fixo'),
    ('5.3.15', 'Comissão de Arquiteto', 5, 'analitica', 'devedora', '5.3', 1, '2.1', 'variavel'),
    ('5.3.16', 'Benefícios a Funcionários (AT/VA/PS)', 5, 'analitica', 'devedora', '5.3', 1, '4.3', 'fixo'),
    ('5.3.17', 'Custo Especial de Projeto', 5, 'analitica', 'devedora', '5.3', 1, '3.2', 'variavel'),
    ('5.3.18', 'Comissão de Medidor', 5, 'analitica', 'devedora', '5.3', 1, '3.2', 'variavel'),
    ('5.3.19', 'Comissão de Projeto/Executivo', 5, 'analitica', 'devedora', '5.3', 1, '3.2', 'variavel'),
    ('5.3.21', 'Concessão a Cliente', 5, 'analitica', 'devedora', '5.3', 1, '2.1', 'variavel'),
    ('5.4.01', 'Aluguel', 5, 'analitica', 'devedora', '5.4', 1, '1.5', 'fixo'),
    ('5.4.02', 'Energia Elétrica', 5, 'analitica', 'devedora', '5.4', 1, '1.5', 'fixo'),
    ('5.4.03', 'Água', 5, 'analitica', 'devedora', '5.4', 1, '1.5', 'fixo'),
    ('5.4.04', 'Telefonia Fixa/Móvel e Internet', 5, 'analitica', 'devedora', '5.4', 1, '4.2', 'fixo'),
    ('5.4.05', 'Contabilidade', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.06', 'Assessoria Jurídica', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.07', 'Consultoria', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.08', 'Segurança e Seguros', 5, 'analitica', 'devedora', '5.4', 1, '1.5', 'fixo'),
    ('5.4.09', 'Material de Limpeza/Expediente', 5, 'analitica', 'devedora', '5.4', 1, '1.5', 'fixo'),
    ('5.4.10', 'Sistemas (ERP, CRM, assinatura digital)', 5, 'analitica', 'devedora', '5.4', 1, '4.2', 'fixo'),
    ('5.4.11', 'Salários Administrativos', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.12', 'Pró-labore', 5, 'analitica', 'devedora', '5.4', 1, '4.4', 'fixo'),
    ('5.4.13', 'Encargos sobre Folha', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.14', 'Vale-Transporte', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.15', 'Sindicato e Contribuições', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.16', 'Rescisões', 5, 'analitica', 'devedora', '5.4', 1, '4.3', 'fixo'),
    ('5.4.17', 'IPVA/IPTU/Licenciamentos', 5, 'analitica', 'devedora', '5.4', 1, '4.5', 'fixo'),
    ('5.4.18', 'Manutenção (loja e informática)', 5, 'analitica', 'devedora', '5.4', 1, '4.5', 'fixo'),
    ('5.4.19', 'Licenças Promob e Sketchup', 5, 'analitica', 'devedora', '5.4', 1, '4.2', 'fixo'),
    ('5.4.20', 'Outras Despesas', 5, 'analitica', 'devedora', '5.4', 1, '4.5', 'fixo'),
    ('5.5.01', 'Tarifas Bancárias', 5, 'analitica', 'devedora', '5.5', 1, '4.3', 'fixo'),
    ('5.5.02', 'Juros de Empréstimos', 5, 'analitica', 'devedora', '5.5', 1, '4.3', 'fixo'),
    ('5.5.03', 'Custo de Antecipação de Recebíveis', 5, 'analitica', 'devedora', '5.5', 1, '4.3', 'variavel'),
    ('5.5.04', 'Custo Financeiro sobre Vendas', 5, 'analitica', 'devedora', '5.5', 1, '4.3', 'variavel'),
    ('5.5.05', 'Perdas com Acordos Financeiros', 5, 'analitica', 'devedora', '5.5', 1, '4.3', 'fixo'),
    ('5.6.10', 'Ajustes de Reconciliação', 5, 'analitica', 'devedora', '5.6', 1, '4.5', 'variavel'),
    ('1.1.06.02', 'Montagem a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.03', 'Garantia a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.05', 'Assistência Técnica a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.06', 'Custo de Fábrica a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.07', 'Frete de Fábrica a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.08', 'Frete Local a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.09', 'Insumos Locais a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.10', 'Comissão de Medidor a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.11', 'Comissão de Projeto/Executivo a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.12', 'Retenção de Comissão de Vendas a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.14', 'Outros Fornecedores a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.15', 'Comissão de Arquiteto a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.16', 'Programa de Fidelidade a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.17', 'Custo de Viagem a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.18', 'Brinde a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.19', 'Custo Financeiro a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.20', 'Custo Especial a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.1.06.21', 'Comissão Administrativa a Apropriar', 1, 'analitica', 'devedora', '1.1.06', 1, None, None),
    ('1.2.1.01', 'Itens de Informática', 1, 'analitica', 'devedora', '1.2.1', 1, None, None),
    ('1.2.1.02', 'Veículos', 1, 'analitica', 'devedora', '1.2.1', 1, None, None),
    ('1.2.1.03', 'Obras/Reforma de Loja', 1, 'analitica', 'devedora', '1.2.1', 1, None, None),
    ('1.2.1.04', 'Show Room', 1, 'analitica', 'devedora', '1.2.1', 1, None, None),
    ('2.1.04.01', 'Provisão de Comissão', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.02', 'Provisão de Montagem', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.03', 'Provisão de Garantia', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.04', 'Provisão de Devolução', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.05', 'Provisão de Assistência Técnica', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.06', 'Provisão de Custo de Fábrica', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.07', 'Provisão de Frete de Fábrica', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.08', 'Provisão de Frete Local', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.09', 'Provisão de Insumos Locais', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.10', 'Provisão de Comissão de Medidor', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.11', 'Provisão de Comissão de Projeto/Executivo', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.12', 'Provisão de Retenção de Comissão de Vendas', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.13', 'Provisão de Impostos', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.14', 'Provisão de Outros Fornecedores', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.15', 'Provisão de Comissão de Arquiteto', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.16', 'Provisão de Programa de Fidelidade', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.17', 'Provisão de Custo de Viagem', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.18', 'Provisão de Brinde', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.19', 'Provisão de Custo Financeiro', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.20', 'Provisão de Custo Especial', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
    ('2.1.04.21', 'Provisão de Comissão Administrativa', 2, 'analitica', 'credora', '2.1.04', 1, None, None),
]

CONTA_NOME_OVERRIDE_POR_OWNER_TIPO = {
    'loja': {
        '1.1.09': 'Créditos com Empresas (conta corrente)',
        '2.1.09': 'Débitos com Empresas (conta corrente)',
    },
}


def upgrade() -> None:
    conn = op.get_bind()

    def cc_existentes(owner_tipo, owner_id):
        rows = conn.execute(sa.text(
            "SELECT id, codigo, nome, pai_id, ativo FROM centro_custo "
            "WHERE owner_tipo = :ot AND owner_id = :oid"
        ), {"ot": owner_tipo, "oid": owner_id}).mappings().all()
        return {r["codigo"]: dict(r) for r in rows}

    def conta_existentes(owner_tipo, owner_id):
        rows = conn.execute(sa.text(
            "SELECT id, codigo, nome, grupo, tipo, natureza, pai_id, ativa, "
            "centro_custo_id, natureza_custo FROM conta "
            "WHERE owner_tipo = :ot AND owner_id = :oid"
        ), {"ot": owner_tipo, "oid": owner_id}).mappings().all()
        return {r["codigo"]: dict(r) for r in rows}

    # --- passada 1: arvore de centro_custo, por owner --------------------------------
    for owner_tipo, owner_id in OWNERS:
        existentes = cc_existentes(owner_tipo, owner_id)
        id_por_codigo = {cod: r["id"] for cod, r in existentes.items()}
        for codigo, nome, pai_codigo, ativo in CENTRO_CUSTO:
            pai_id = id_por_codigo.get(pai_codigo) if pai_codigo else None
            atual = existentes.get(codigo)
            if atual is None:
                novo_id = conn.execute(sa.text(
                    "INSERT INTO centro_custo (owner_tipo, owner_id, codigo, nome, pai_id, ativo, ordem) "
                    "VALUES (:ot, :oid, :codigo, :nome, :pai_id, :ativo, 999) RETURNING id"
                ), {"ot": owner_tipo, "oid": owner_id, "codigo": codigo, "nome": nome,
                    "pai_id": pai_id, "ativo": ativo}).scalar_one()
                id_por_codigo[codigo] = novo_id
            elif (atual["nome"], atual["pai_id"], atual["ativo"]) != (nome, pai_id, ativo):
                conn.execute(sa.text(
                    "UPDATE centro_custo SET nome = :nome, pai_id = :pai_id, ativo = :ativo "
                    "WHERE id = :id"
                ), {"nome": nome, "pai_id": pai_id, "ativo": ativo, "id": atual["id"]})

    # --- passada 2: arvore de conta (sem classificacao ainda), por owner -------------
    for owner_tipo, owner_id in OWNERS:
        existentes = conta_existentes(owner_tipo, owner_id)
        id_por_codigo = {cod: r["id"] for cod, r in existentes.items()}
        overrides = CONTA_NOME_OVERRIDE_POR_OWNER_TIPO.get(owner_tipo, {})
        for codigo, nome_base, grupo, tipo, natureza, pai_codigo, ativa, _cc_codigo, _nat_custo in CONTA:
            nome = overrides.get(codigo, nome_base)
            pai_id = id_por_codigo.get(pai_codigo) if pai_codigo else None
            atual = existentes.get(codigo)
            if atual is None:
                novo_id = conn.execute(sa.text(
                    "INSERT INTO conta (owner_tipo, owner_id, codigo, nome, grupo, tipo, natureza, "
                    "pai_id, ativa, ordem) VALUES "
                    "(:ot, :oid, :codigo, :nome, :grupo, :tipo, :natureza, :pai_id, :ativa, 999) "
                    "RETURNING id"
                ), {"ot": owner_tipo, "oid": owner_id, "codigo": codigo, "nome": nome, "grupo": grupo,
                    "tipo": tipo, "natureza": natureza, "pai_id": pai_id, "ativa": ativa}).scalar_one()
                id_por_codigo[codigo] = novo_id
            elif (atual["nome"], atual["grupo"], atual["tipo"], atual["natureza"], atual["pai_id"],
                  atual["ativa"]) != (nome, grupo, tipo, natureza, pai_id, ativa):
                conn.execute(sa.text(
                    "UPDATE conta SET nome = :nome, grupo = :grupo, tipo = :tipo, natureza = :natureza, "
                    "pai_id = :pai_id, ativa = :ativa WHERE id = :id"
                ), {"nome": nome, "grupo": grupo, "tipo": tipo, "natureza": natureza,
                    "pai_id": pai_id, "ativa": ativa, "id": atual["id"]})

    # --- passada 3: classificacao (centro_custo_id / natureza_custo), por owner ------
    for owner_tipo, owner_id in OWNERS:
        cc_ids = {cod: r["id"] for cod, r in cc_existentes(owner_tipo, owner_id).items()}
        conta_atual = conta_existentes(owner_tipo, owner_id)
        for codigo, _nome, _grupo, _tipo, _natureza, _pai_codigo, _ativa, cc_codigo, nat_custo in CONTA:
            cc_id = cc_ids.get(cc_codigo) if cc_codigo else None
            atual = conta_atual[codigo]
            if (atual["centro_custo_id"], atual["natureza_custo"]) != (cc_id, nat_custo):
                conn.execute(sa.text(
                    "UPDATE conta SET centro_custo_id = :cc_id, natureza_custo = :nat_custo "
                    "WHERE id = :id"
                ), {"cc_id": cc_id, "nat_custo": nat_custo, "id": atual["id"]})


def downgrade() -> None:
    """Nao reversivel de forma util.

    Desfazer significaria apagar (ou desclassificar) contas e nos de centro de
    custo que, num ambiente real, ja podem ter Lancamento apontando pra eles
    (conta_debito_id/conta_credito_id, sem ondelete definido -> bloqueia o
    DELETE) ou terem sido reclassificados por acao manual depois desta
    migration (a passada 3 e' idempotente pra frente, nao guarda o valor
    anterior pra restaurar). Downgrade tentaria adivinhar um estado que nao da
    pra reconstruir com seguranca a partir daqui — por isso fica so' o registro
    da decisao, sem pass() fingindo reversibilidade.
    """
