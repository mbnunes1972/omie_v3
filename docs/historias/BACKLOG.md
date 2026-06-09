# Histórias de Usuário — Omie_V3

> Versão de referência: **v0.1.0** | Junho 2026  
> Repositório: [github.com/mbnunes1972/omie_v3](https://github.com/mbnunes1972/omie_v3)

**Convenções de status:**
- `[IMPLEMENTADO]` — funcionalidade concluída e testada
- `[BUG CONHECIDO]` — implementada mas com comportamento incorreto documentado
- `[PLANEJADO]` — especificada, ainda não implementada

---

## Índice

- [EP-01 — Autenticação e Controle de Acesso](#ep-01--autenticação-e-controle-de-acesso)
- [EP-02 — Integração Promob → Omie](#ep-02--integração-promob--omie)
- [EP-03 — Negociação e Cálculo de Margens](#ep-03--negociação-e-cálculo-de-margens)
- [EP-04 — Módulos Financeiros](#ep-04--módulos-financeiros)
- [EP-05 — Cadastro de Clientes e Parceiros](#ep-05--cadastro-de-clientes-e-parceiros)
- [EP-06 — Infraestrutura e Deploy](#ep-06--infraestrutura-e-deploy)

---

## EP-01 — Autenticação e Controle de Acesso

> Sistema de login, perfis de usuário e hierarquia de permissões.

---

### US-01 — Login no sistema `[IMPLEMENTADO]`

**Como** consultor, gerente ou diretor,  
**quero** acessar o sistema com usuário e senha,  
**para que** apenas usuários autorizados utilizem a plataforma.

**Critérios de aceite:**
- Tela de login com campos de usuário e senha
- Autenticação via cookie de sessão (token hex-32, server-side)
- Redirecionamento automático ao sistema após login bem-sucedido
- Mensagem de erro clara em caso de credenciais inválidas
- Sessão mantida entre recarregamentos de página

---

### US-02 — Logout seguro `[IMPLEMENTADO]`

**Como** usuário autenticado,  
**quero** encerrar minha sessão,  
**para que** nenhum acesso não autorizado ocorra ao deixar o computador.

**Critérios de aceite:**
- Botão de logout visível na interface
- Sessão invalidada no servidor ao fazer logout
- Redirecionamento para a tela de login após logout

---

### US-03 — Perfil de usuário com foto `[IMPLEMENTADO]`

**Como** usuário autenticado,  
**quero** visualizar meu nome, perfil e foto na sidebar,  
**para que** tenha uma experiência personalizada e identifique rapidamente meu nível de acesso.

**Critérios de aceite:**
- Botão de perfil na sidebar exibindo nome e nível (Consultor / Gerente / Diretor)
- Upload de foto de perfil suportado
- Foto exibida na sidebar após upload
- Informações atualizadas sem necessidade de relogin

---

### US-04 — Limites de desconto por perfil `[IMPLEMENTADO]`

**Como** sistema,  
**quero** aplicar limites de desconto diferentes por nível de usuário,  
**para que** descontos excessivos não sejam concedidos sem autorização.

**Critérios de aceite:**
- Consultor: limite máximo de **10%** de desconto
- Gerente: limite máximo de **20%** de desconto
- Diretor: limite máximo de **50%** de desconto
- Limite visível e aplicado tanto na sidebar quanto no modal de parâmetros
- Campo de desconto bloqueado ao atingir o limite do perfil

---

### US-05 — Autorização delegada de desconto `[IMPLEMENTADO]`

**Como** consultor ou gerente,  
**quero** solicitar autorização de um superior para aplicar desconto acima do meu limite,  
**para que** possa fechar negociações com flexibilidade sem burlar o controle de margens.

**Critérios de aceite:**
- Modal de autorização delegada ativado ao tentar exceder o limite
- Modal solicita login do superior (gerente ou diretor)
- Aprovação registrada no banco com: quem aprovou, quem solicitou, desconto aprovado, timestamp
- Desconto aprovado aplicado automaticamente após autorização
- Histórico de autorizações acessível para auditoria

---

## EP-02 — Integração Promob → Omie

> Importação de projetos do Promob via XML e exportação para o ERP Omie.

---

### US-06 — Importação de XML do Promob `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** carregar o arquivo XML exportado pelo Promob,  
**para que** os ambientes e valores do projeto estejam disponíveis para negociação.

**Critérios de aceite:**
- Upload de arquivo XML via interface
- Parsing correto usando `BUDGET/@TOTAL` como preço de venda ao cliente
- Todos os 4 níveis de preço armazenados: `price_table`, `price_total`, `order_total`, `budget_total`
- Ambientes listados com seus respectivos valores
- Classificação dos itens em 16 grupos de produtos padronizados

---

### US-07 — Exportação de pedido para o Omie `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** exportar o pedido negociado diretamente para o Omie ERP,  
**para que** elimine retrabalho de digitação e garanta consistência dos dados.

**Critérios de aceite:**
- Cada grupo de produtos registrado no Omie com valor unitário R$1,00 e quantidade = subtotal do grupo
- Respeito ao limite de 240 requisições/minuto da API Omie
- Tratamento do HTTP 425 (rate-limit) com retentativa automática
- NCMs enviados sem pontuação (exigência da API)
- Endpoint correto: `IncluirPedVenda`

---

## EP-03 — Negociação e Cálculo de Margens

> Tela de negociação com cálculo de margens, descontos e custos internos.

---

### US-08 — Tela de negociação com ambientes `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** visualizar todos os ambientes do projeto com seus valores,  
**para que** conduza a negociação com o cliente de forma clara e organizada.

**Critérios de aceite:**
- Listagem de ambientes com valor final por ambiente
- Visual de terminal escuro (`bg #111d11`, `sidebar #0d160d`)
- Três rampas de cor: teal (valor líquido loja), âmbar (valor contratual cliente), coral (custos/taxas)
- Campo de desconto global aplicável a todos os ambientes

---

### US-09 — Toggle de custos adicionais `[BUG CONHECIDO]`

**Como** consultor de vendas,  
**quero** ativar ou desativar a inclusão de custos internos no preço ao cliente,  
**para que** controle se comissão de arquiteto, fidelidade, deslocamentos e brindes compõem o preço final.

**Critérios de aceite:**
- Toggle "Incluir custos adicionais?" visível na tela de negociação
- Quando ativado: custos internos fazem gross-up no preço ao cliente
- Quando desativado: custos internos não afetam o preço visível ao cliente
- Estado do toggle persistido corretamente entre aberturas do modal

> **⚠ Bug:** `carregarMargensSalvas()` sobrescreve `projetoAtivo.margens.incluir_custos` ao recarregar do servidor, fazendo o toggle ignorar a última seleção do usuário.

---

### US-10 — Modal de parâmetros com snapshot/restore `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** ajustar parâmetros de margem e cancelar sem perder a configuração anterior,  
**para que** explore cenários de negociação sem comprometer os valores já definidos.

**Critérios de aceite:**
- Modal abre com snapshot dos valores atuais
- Botão Cancelar restaura o snapshot sem salvar alterações
- Botão Salvar persiste os novos valores
- Parâmetros incluem: margens por tipo, comissão arquiteto, programa fidelidade, custos de deslocamento, brindes

---

### US-11 — Custos internos não afetam preço ao cliente `[IMPLEMENTADO]`

**Como** sistema,  
**quero** garantir que custos internos nunca alterem o valor visível ao cliente,  
**para que** o preço de venda seja calculado apenas sobre as margens comerciais declaradas.

**Critérios de aceite:**
- Valor bruto calculado exclusivamente a partir da margem comercial
- Custos internos (comissão arquiteto, fidelidade, brindes, deslocamento) registrados separadamente como absorção da loja
- Tela exibe claramente: valor líquido da loja vs. valor contratual do cliente

---

## EP-04 — Módulos Financeiros

> Cálculo de condições de pagamento: Aymoré, Cartão de Crédito e Total Flex.

---

### US-12 — Financiamento Aymoré `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** calcular o valor ao cliente em financiamentos via Aymoré,  
**para que** ofereça condições parceladas precisas sem erro de margem.

**Critérios de aceite:**
- Input: `valor_avista` (o que a loja quer receber líquido)
- Fórmula: `financiado = (valor_avista - entrada) / (1 - taxa_retencao)`
- Entrada reduz o valor financiado (e portanto o custo ao cliente)
- Caso validado: 8x/20d/R$100k avista → total cliente **R$110.223,82**
- Com entrada R$20k → total cliente **R$108.179,05**

---

### US-13 — Cartão de Crédito `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** calcular o repasse ao cliente das taxas de cartão de crédito,  
**para que** preserve a margem líquida da loja em vendas parceladas no cartão.

**Critérios de aceite:**
- Input: `valor_avista` (o que a loja quer receber líquido)
- Taxa de retenção aplicada sobre o valor financiado
- Caso validado: 6x/R$10k → taxa 5,65%, total cliente **R$10.598,83**

---

### US-14 — Total Flex `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** oferecer um plano de parcelas flexíveis com juros compostos sobre saldo devedor,  
**para que** atenda clientes com necessidade de datas e valores personalizados.

**Critérios de aceite:**
- Parcelas com datas e valores editáveis livremente
- Juros compostos calculados sobre dias reais entre vencimentos
- Última parcela calculada automaticamente para zerar o saldo (campo de valor travado, data editável)
- Taxa mensal lida **exclusivamente pelo backend** (nunca exposta no frontend, variáveis JS, logs ou DevTools)
- Configuração da taxa em `total_flex.json` no servidor

> **📌 Referência:** Spec técnica completa em `docs/modulos/financeiro/Spec_TotalFlex_v1.docx`

---

## EP-05 — Cadastro de Clientes e Parceiros

> Módulos de registro e gestão de clientes e parceiros comerciais.

---

### US-15 — Cadastro de cliente `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** registrar os dados de um novo cliente,  
**para que** mantenha um banco de dados centralizado de prospects e clientes ativos.

**Critérios de aceite:**
- Campos: nome, CPF/RG, endereço (bairro, cidade), telefone, e-mail
- Campos agrupados na mesma linha onde fizer sentido (CPF+RG, Bairro+Cidade, Tel+Email)
- Validação de CPF
- Busca de cliente existente antes de criar novo registro
- Associação do cliente a projetos e negociações

> **📌 Nota:** Módulo iniciado via Claude Code; suspenso por erros de rota no backend e limite de contexto. Retomar na v0.2.0.

---

### US-16 — Cadastro de parceiro `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** registrar parceiros que indicam ou especificam projetos,  
**para que** rastreie a origem dos projetos e calcule comissões corretamente.

**Critérios de aceite:**
- Tipos: arquiteto, designer, decorador, corretor, engenheiro, indicador
- Campos específicos por tipo (ex: CAU/CREA para arquitetos e engenheiros)
- Associação de parceiro a projetos e pedidos
- Base para cálculo de comissionamento futuro

---

## EP-06 — Infraestrutura e Deploy

> Configuração do servidor, repositório e pipeline de deploy.

---

### US-17 — Deploy no VPS Hostinger `[IMPLEMENTADO]`

**Como** desenvolvedor,  
**quero** ter o Omie_V3 rodando em servidor acessível remotamente,  
**para que** a equipe da loja acesse o sistema sem depender da máquina local.

**Critérios de aceite:**
- Aplicação rodando no VPS Ubuntu 24.04 (IP `167.88.33.121`, porta `8765`)
- Servidor isolado do ArchDecorPoints (produção em servidor separado)
- Processo mantido via `screen` session
- Binding em `0.0.0.0` para acesso externo
- Credenciais Omie externalizadas (não hardcoded)

---

### US-18 — Workflow Git para deploy `[IMPLEMENTADO]`

**Como** desenvolvedor,  
**quero** um fluxo padronizado de push e deploy,  
**para que** atualizações cheguem ao servidor de forma controlada e rastreável.

**Critérios de aceite:**
- Repositório: `github.com/mbnunes1972/omie_v3`
- Fluxo: `desenvolver local → testar local → git push → SSH servidor → git pull → restart`
- Tag `v0.1.0` criada como marco do estado atual
- Convenção: `v0.x.0` em desenvolvimento, `v1.0.0` na primeira loja em produção

---

### US-19 — Documentação de sessão contínua `[IMPLEMENTADO]`

**Como** desenvolvedor,  
**quero** manter documentação atualizada entre sessões de desenvolvimento com IA,  
**para que** retome o trabalho sem perder contexto e decisões anteriores.

**Critérios de aceite:**
- `DEV_RULES.md` — regras de desenvolvimento e convenções
- `DEV_LOG.md` — log cronológico de decisões e mudanças
- `REQUIREMENTS.md` — backlog de funcionalidades
- `docs/modulos/<modulo>/SPEC.md` — especificação por módulo
- Convenções aplicadas: `[IMPLEMENTADO]`, `[TODO]`, `[BUG]`, `[VALIDAR]`

---

*Documento mantido em `docs/historias/BACKLOG.md`*  
*Atualizar a cada funcionalidade concluída ou nova história identificada.*
