# Manual de Implantação — Configuração de Parâmetros de uma Loja Nova

Guia operacional para configurar uma loja do zero no Orizon Manager, antes de começar a operar
de verdade (cadastrar clientes/projetos reais). Cobre só a **parte de parâmetros e cadastros
iniciais** — a parte de migração de dados (clientes, parceiros, projetos em andamento, histórico
de contratos) é uma frente separada.

Público: quem vai configurar a loja (Master). Sequência pensada pelas dependências reais entre
telas — uma etapa às vezes deixa a próxima incompleta ou vazia se pulada.

---

## Fase 0 — Base da loja

### 0.1 Admin → Dados da empresa
Cadastro comercial/institucional da loja (**diferente** do Fiscal — ver Fase 3). Campos:
- Nome, Código (3 letras, único — usado na numeração do contrato), CNPJ, Telefone, E-mail
- Testemunha 1 (nome + CPF), Testemunha 2 (nome + CPF) — vão no bloco de assinatura do contrato
- **Segmentação de receita**: % Mercadoria (NF-e produto) + % Serviço (NFS-e) — **tem que somar
  100%**, o sistema bloqueia salvar se não somar (default 65/35)

Preencha isso primeiro: os marcadores de endereço da loja (logradouro, número, bairro, cidade,
UF, CEP) são usados nos modelos de documento (Fase 4) — se ainda estiver vazio, o preview do
contrato sai com campos em branco.

### 0.2 Admin → Módulos
Liga/desliga os domínios que a loja usa. **Decida isso cedo** — controla quais abas de Config e
qual painel Fiscal aparecem na sidebar. Tem dependência entre módulos (o sistema barra no próprio
clique se faltar pré-requisito):

| Módulo | Depende de |
|---|---|
| Captação | — |
| Cadastro | — |
| Comercial | Cadastro |
| Fiscal | Cadastro, Comercial |
| Estoque | Cadastro, Comercial |
| Expedição | Comercial, Estoque, Fiscal |
| Operacional (montagem) | Comercial |
| Assistências | Comercial, Operacional, Financeiro |
| Financeiro | Comercial |
| Folha de Pagamento | Cadastro, Comercial, Financeiro |

Se a loja vende produto (móveis) e presta serviço (montagem), praticamente todos os módulos
acabam entrando — ligue de baixo pra cima na tabela (o sistema já impede ligar um módulo sem a
base).

---

## Fase 1 — Estrutura organizacional

### 1.1 Config → Funções (Tabela de Funções)
Cadastre os cargos primeiro (ex.: Consultor de Vendas, Montador, Medidor, Projetista Executivo,
Gerente Administrativo/Financeiro). Campo "Nova função" + botão **+ Adicionar**; depois **Editar**
por linha abre: Nome, Descrição, Padrão de remuneração (Fixa/Variável/Fixa+Variável), Regime de
trabalho (Presencial/Remoto/Misto), Regime de contratação (Registrado/Terceirização).

Isso é pré-requisito de **Remunerações** (1.3) e melhora **Cronograma** (2.3) e **Perfis de
Usuário → Funções** (1.2) — sem função cadastrada essas telas ficam vazias ou incompletas.

### 1.2 Admin → Perfis de Usuário
Os 3 perfis de sistema (**Master**, **Gerente**, **Operador**) já existem por padrão — não
precisa criar nada pra começar a cadastrar gente. Só mexa aqui se quiser um perfil sob medida
(ex.: um "Consultor Senior" com capacidades específicas) — nesse caso, faça isso **antes** de
cadastrar os usuários que vão usar esse perfil (1.4), porque o perfil só aparece no dropdown de
usuário depois de criado.

A sub-aba **Funções** desta tela liga um Perfil de acesso padrão a cada Função da Tabela de
Funções (1.1) — útil pra sugerir o perfil certo automaticamente ao cadastrar alguém com aquele
cargo.

### 1.3 Config → Remunerações
Só funciona com Funções (1.1) já cadastradas — a tela mostra "Nenhuma função. Cadastre em
Config › Funções." se pular esse passo. Duas partes:

- **Adiantamento Oficial** (loja toda): liga por padrão + % do salário fixo (default 40%).
- **Por Função**, botão "Remuneração": Salário Fixo, Comissão fixa (R$, isenta de encargos),
  checkbox "Usa comissão de vendas por metas" (motor da loja — veja abaixo) ou comissão
  simples/por faixa própria da função, e Benefícios (Auxílio Transporte, Vale Alimentação, Plano
  de Saúde — liga/desliga + valor).

**Comissão de vendas** (parâmetro único por loja, compartilhado por toda função marcada "usa
comissão por metas"): Meta mensal (R$), Faixas de comissão (venda até R$ → %), Limitador de
desconto (redutor de comissão quando o vendedor concede desconto acima de um limiar).

### 1.4 Admin → Usuários
Cadastre as pessoas: Nome, Login, Senha, Perfil, Telefone, WhatsApp, E-mail, CPF. Se a loja tiver
mais de uma unidade no escopo do seu acesso, também escolhe quais lojas a pessoa acessa.

---

## Fase 2 — Parâmetros financeiros e operacionais

### 2.1 Config → Provisões
Independente — pode ser feito a qualquer momento, sem pré-requisito. Percentuais que alimentam o
motor de negociação e as provisões contábeis constituídas no fechamento da venda:

- % Comissão arquiteto, % Fidelidade, % Carga tributária (defaults da negociação)
- % Frete fábrica→loja, % Comissões administrativas, % Comissão de medidor, % Comissão projeto
  executivo, % Frete local, % Assistências, % Insumos locais
- **Provisões contábeis** (constituídas no fechamento): % Provisão de Montagem, % Provisão de
  Garantia, % Provisão de Comissão de Vendas (a de Assistência herda o "% Assistências" acima,
  automático)
- **Prazo de antecipação** (Recebimento de Venda): Cartão (dias, default 1), Aymoré/Financeira
  (dias, default 2)

### 2.2 Config → Agenda
Converte a janela de prazo de cada projeto/fase (que vem do Cronograma, 2.3) em capacidade
necessária no período. Faça **depois** do Cronograma pra fazer sentido:

- **Projeto Executivo**: Produtividade média (R$/dia, default 20000)
- **Montagem**: Produtividade por dupla (R$/dupla/dia, default 7000), Duplas disponíveis (default 2)
- **Calendário útil**: Horizonte da Capacidade (semanas, default 6), "Sábado conta como dia útil",
  lista de Feriados

### 2.3 Config → Cronograma
Prazo padrão (dias corridos) por etapa do ciclo (8 a 20) + Função responsável por etapa (usa a
Tabela de Funções, 1.1). Também define o **Prazo contratual (dias úteis)**, que vira marcador no
contrato. Na assinatura de cada projeto real, esse padrão gera a data prevista de conclusão de
cada etapa.

Defaults de fábrica (dias corridos): etapa 8→2, 9→3, 10→5, 11→10, 12→3, 13→25, 14→5, 15→2,
16→5, 17→5, 18→3, 19→2, 20→2. A tela avisa se a soma não cabe no prazo contratual em dias úteis.

---

## Fase 3 — Fiscal

Painel próprio na sidebar (não é aba de Admin nem de Config) — só aparece se Cadastro e Comercial
estiverem ativos (Fase 0.2).

Uma loja nova já nasce com 7 campos preenchidos como **valor de teste** (badge amarelo,
precisa confirmar um por um): Regime tributário = Simples Nacional, CSOSN padrão 102, CSOSN
contribuinte 101, CFOP dentro UF 5102, CFOP fora UF 6102, CNAE de serviço `4330404` (genérico —
**revisar**, não é o CNAE real da loja), Alíquota ISS 5%.

Passo a passo:
1. **Identificação fiscal**: CNPJ do emitente, Razão social, Inscrição Estadual, Inscrição
   Municipal.
2. **Regime tributário**: confirme/ajuste Regime, CSOSN não-contribuinte, CSOSN contribuinte.
3. **Endereço do emitente**: Logradouro, Número, Bairro, Cidade, UF, CEP.
4. **NF-e produto**: CFOP dentro/fora do estado, Série da NF-e, "Discrimina impostos".
5. **NFS-e** (captura de dado, emissão ainda futura): CNAE de serviço, Código do serviço no
   município, Alíquota ISS, Município (código IBGE).
6. **Perfil de emissão**: Papel deste CNPJ (Central de Produto / Loja com Serviço / Loja com
   Produto e Serviço / Avulso).
7. Clique **Salvar configuração fiscal**.
8. **Credenciais Focus NFe**: Token de homologação e/ou Token de produção — ação **separada**
   (botão próprio "Salvar credenciais Focus"), não junta com o passo 7.
9. Confirme, um a um, os 7 campos marcados "valor de teste" (checkbox ao lado de cada um).
10. **Ative Produção** só quando: todos os 7 confirmados + token de produção definido (o botão
    fica desabilitado até isso). Emissão de teste antes disso é sempre em homologação — sem
    valor fiscal.

Se a loja fizer parte de uma rede com CNPJ central (distribuidora), o Perfil de emissão também
define, por rede, qual CNPJ emite NF-e de Produto e qual emite NFS-e de Serviço.

---

## Fase 4 — Modelos de documento

### Config → Documentos
Três tipos com tela pronta hoje: **Contrato**, **Proposta comercial**, **Termo Aditivo** (um 4º
card, "Demais documentos", está desabilitado — em construção). Exige a capacidade "gerir
documentos" do perfil (só o Master tem por padrão).

Passo a passo, por tipo:
1. Abra o card do tipo (mostra a versão vigente + histórico, se já houver).
2. Suba o arquivo do modelo (`.docx`, `.odt`, `.doc`, `.rtf`, `.md` ou `.txt` — **PDF não é
   aceito**).
3. O sistema normaliza pra Markdown e roda uma análise: aponta marcador conhecido que ficou de
   fora, marcador desconhecido no texto, e dado da loja "cravado" no texto que deveria ser
   marcador (ex.: CNPJ escrito na mão em vez de `[LOJA_CNPJ]`).
4. Revise o preview e clique **Ativar** — isso cria uma nova versão e desativa a anterior
   automaticamente (versão salva é imutável; editar sempre gera versão nova).

Se a loja não subir modelo próprio de Contrato, o sistema usa o **modelo global** do sistema como
fallback — funciona, mas sem a identidade/cláusulas específicas da loja. Vale fazer isso com os
**Dados da empresa (0.1) já preenchidos**, senão o preview sai com campos em branco.

---

## Checklist rápido (ordem recomendada)

- [ ] 0.1 — Dados da empresa (nome, CNPJ, testemunhas, segmentação mercadoria/serviço)
- [ ] 0.2 — Módulos ativos
- [ ] 1.1 — Tabela de Funções
- [ ] 1.2 — Perfis de Usuário (só se precisar de perfil customizado)
- [ ] 1.3 — Remunerações (salário/comissão/benefícios por função)
- [ ] 1.4 — Usuários (cadastro das pessoas)
- [ ] 2.1 — Provisões (percentuais financeiros)
- [ ] 2.3 — Cronograma (prazos por etapa + prazo contratual)
- [ ] 2.2 — Agenda (capacidade/produtividade)
- [ ] 3 — Fiscal (identificação, regime, credenciais Focus, confirmar placeholders)
- [ ] 4 — Documentos (Contrato, Proposta, Termo Aditivo)

Depois disso: pronto pra cadastrar cliente e abrir o primeiro projeto de verdade. A migração de
dados existentes (clientes, parceiros, projetos em andamento, histórico) é uma frente separada,
tratada à parte.

---

*Levantamento feito em 2026-08-08 direto no código (`static/index.html`, `modulos.py`,
`mod_provisoes.py`, `mod_comissao.py`, `mod_cronograma.py`, `mod_documentos.py`, `auth/perfis.py`,
`fiscal/mod_fiscal.py`, `database.py`). Sujeito a ficar desatualizado se a tela mudar — na dúvida,
confira contra o código antes de seguir o manual ao pé da letra.*
