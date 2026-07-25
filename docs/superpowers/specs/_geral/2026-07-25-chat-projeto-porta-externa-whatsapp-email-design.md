# Chat por Projeto, Canais Segmentados e Tag de Responsabilidade (design) — 2026-07-25

## Demanda
Criar uma ferramenta de chat no Orizon para comunicação interna e tramitação de documentos (ex.:
encaminhar Projeto Executivo, encaminhar para revisão), com "porta de saída" externa via
**WhatsApp e e-mail** (envia e recebe resposta de volta), **segmentada por canal**: Comercial (no
futuro, canal do lead), Financeiro, Logística, Suporte Técnico e SAC. Internamente, a ferramenta
tem papel central na **transferência de informação e de responsabilidade** entre etapas do ciclo —
e precisa deixar claro, a qualquer momento, **quem está com a bola** (por pessoa, não só por
equipe).

## Decisões já tomadas
1. Chat **atrelado a projeto** (SAC é a exceção — ver seção 2).
2. Porta de saída de **2 vias** (envia e recebe resposta de volta).
3. WhatsApp via **API oficial** (Meta Cloud API, direto ou via BSP).
4. **Canais externos segmentados**: Comercial, Financeiro, Logística, Suporte Técnico, SAC.
5. **Duas naturezas de mensagem**: interação (não muda responsabilidade) e transferência
   (oficializa, muda responsabilidade, pode carregar documento e sinalizar bloqueador).
6. **Responsabilidade é por pessoa física**, resolvida a partir de mapas que já existem no
   sistema (Mapa de Atribuições + Consultor) ou pela Função/cargo, quando só há uma pessoa no
   papel (2026-07-25).
7. **Bloqueador trava o avanço do ciclo de verdade** — é uma ferramenta emergencial para forçar
   providência, não um alerta decorativo (2026-07-25).
8. **Histórico único e visível por padrão**, com um **modo privado** por mensagem: o conteúdo fica
   cifrado para a maioria, mas o fato de ter havido uma troca privada aparece pra todos; só
   usuários de nível **master e gerencial** descriptografam o conteúdo (2026-07-25).
9. **SAC também resolvido pela Função "SAC"** (já existe como cargo padrão), mesmo mecanismo de
   Financeiro/Logística (2026-07-25).
10. **Válvula de emergência do bloqueador** disponível para níveis **master e gerencial**, não só
    para quem recebeu a transferência (2026-07-25).
11. **Arquiteto é participante externo da conversa do projeto**, derivado do vínculo que já
    existe (`parceiro_id` do projeto) — nada é configurado por conversa (adendo 2026-07-25).
12. **Contatos externos vêm do CADASTRO** (Parceiro já tem `whatsapp`/`telefone`/`email`;
    Cliente ganha campo WhatsApp quando o canal chegar) — nunca da fase de contrato: cadastro é
    dado vivo, contrato é snapshot jurídico (adendo 2026-07-25).
13. **Confirmação de contatos na fase de contrato**: no ato do contrato o sistema verifica se
    os WhatsApps dos participantes (cliente e, se houver, arquiteto) estão preenchidos e, mesmo
    preenchidos, pede **confirmação explícita do canal** (registrando quem confirmou e quando).
    Nível de exigência FECHADO na implementação (mini-frente 2026-07-25, aprovada pelo
    usuário): gate BLOQUEANTE-SUAVE no POST do contrato — sem confirmação registrada o
    contrato não é gerado; o operador confirma OU declara "seguir sem WhatsApp" (as duas
    saídas ficam registradas com quem/quando + snapshot dos contatos vistos).
14. **Threading de resposta externa**: reply citando mensagem resolve determinístico
    (`context.id` × `EnvioExterno.id_externo`); resposta solta de número com UMA conversa ativa
    vai direto; com VÁRIAS conversas ativas cai numa **fila de triagem humana** (v1 — sem bot
    perguntando "qual projeto?"). E-mail é determinístico por `Message-ID`/`References` +
    plus-addressing opcional (adendo 2026-07-25).

## 1) Responsabilidade por pessoa — de onde vem cada uma
Achado no código: já existem **três mecanismos de atribuição por pessoa**, cada um cobrindo parte
das faixas do ciclo (`mod_ciclo.FAIXA_POR_ETAPA`). A tag de responsabilidade não cria um sistema
novo — ela **consulta** o que já existe, e só precisa de dois complementos:

| Faixa/canal          | Fonte da pessoa responsável                                   | Situação |
|-----------------------|----------------------------------------------------------------|----------|
| Comercial (`vendas`)  | `Briefing.consultor_id`                                        | ✅ já existe |
| Execução (`execucao_projeto`) | `AtribuicaoAmbiente` (papéis `projeto_executivo`, `medicao`) | ✅ já existe |
| Suporte Técnico (`montagem`) | `AtribuicaoAmbiente` (papéis `montagem`, `assistencia`)  | ✅ já existe |
| Financeiro (`gate_financeiro_*`, `conciliacao_final`) | Usuário com Função **"Gerente Administrativo/Financeiro"** na loja | 🆕 resolvido por função (só 1 pessoa por loja, como você confirmou) |
| Logística (`expedicao`) | Usuário com Função **"Assistente Logístico"** na loja        | 🆕 resolvido por função |
| SAC                    | Usuário com Função **"SAC"** na loja                          | 🆕 resolvido por função — a Função "SAC" **já existe** como cargo padrão (`FUNCOES_PADRAO`) |

Pra Financeiro/Logística/SAC não crio uma tabela nova — é uma consulta simples "quem tem essa
Função ativa nessa loja" (mesma tabela `Funcao`/`Funcionario` que já existe). Se um dia a loja
tiver mais de uma pessoa na função, a regra provisória é pegar a primeira ativa e sinalizar
ambiguidade no cadastro — não deve acontecer no seu cenário atual (você confirmou 1 pessoa por
função), mas o sistema não quebra se mudar.

## 2) SAC sem projeto — Conversa passa a aceitar vínculo flexível
Você apontou algo que muda a estrutura: SAC pode surgir de "demanda aleatória, até associada a
projetos não fechados, problemas da marca etc." — ou seja, **nem toda conversa de SAC tem um
Projeto por trás**. A `Conversa` deixa de ser 1:1 obrigatório com Projeto:
- `Conversa.projeto_nome` (opcional) e `Conversa.cliente_id` (opcional) — pelo menos um dos dois
  preenchido no caso comum (projeto em andamento, ou cliente sem projeto específico); **os dois em
  branco** cobre o caso extremo de reclamação institucional sem cliente identificado (ex.: alguém
  reclamando da marca nas redes, sem projeto nem cadastro).
- Todo o resto do desenho (Mensagem, natureza, canal, EnvioExterno) funciona igual, só a "âncora"
  da conversa fica mais flexível.

## 3) Bloqueador como gate real (não só alerta)
Confirmado: bloqueador deve **impedir o avanço do ciclo**, igual às aprovações financeiras que já
travam hoje (etapas 8/11d). Integra direto no motor existente:
- `mod_ciclo.pode_avancar()` (fonte única da verdade do gating) ganha uma condição a mais: se o
  projeto tem um bloqueador **ativo** (não resolvido), a etapa atual não pode avançar,
  independente das outras condições já estarem OK.
- **Quem resolve**: a pessoa/faixa pra quem foi transferido o bloqueador marca como resolvida
  (segue o fluxo normal — ela agora "está com a bola" e a devolve resolvida ou transfere adiante).
- **Válvula de emergência**: usuários de nível **master e gerencial** podem destravar um bloqueador
  diretamente, mesmo sem ser o destinatário da transferência — com registro obrigatório de quem
  destravou e por quê (auditoria, mesmo padrão de `LogAcaoGerencial` já usado em outras ações
  sensíveis do sistema).
- **Atenção de implementação**: como isso mexe no motor de gating do ciclo (código sensível,
  usado em produção agora), esta fatia especificamente merece mais rigor de teste do que o resto
  da spec — trato isso explicitamente na seção de fatias abaixo.

## 4) Modo privado — mensagem visível-que-existiu, conteúdo cifrado
- `Mensagem.privada` (booleano). Quando marcada, o **corpo é criptografado de verdade no
  servidor** (não é só uma máscara de tela) — evita que alguém lendo a resposta da API ou o banco
  direto veja o conteúdo sem autorização.
- **Quem pode enviar como privada**: qualquer usuário — é a liberdade que você descreveu, qualquer
  pessoa pode tratar algo com privacidade quando precisar.
- **Quem pode descriptografar/ler o conteúdo**: níveis de acesso **`master` e `gerencial`**.
- **O que os demais veem**: a mensagem aparece normalmente na linha do tempo (autor, hora, natureza
  se for transferência), mas o corpo é substituído por algo como
  `🔒 Mensagem privada — visível apenas à gerência` — dá exatamente o efeito que você descreveu:
  todo mundo sabe que uma conversa privada aconteceu, ninguém de fora da gerência lê o conteúdo.
- Combina normalmente com `natureza`: uma transferência também pode ser marcada como privada (ex.:
  transferir um problema sensível de cliente pro Financeiro, sem expor detalhes pro resto da
  equipe).

## 5) Participantes externos da conversa (adendo 2026-07-25)
O projeto pode ter **arquiteto** (Parceiro tipo arquiteto, via `parceiro_id` — vínculo que já
existe), e ele participa da conversa do projeto como destinatário externo do canal Comercial:
- **Derivação, não configuração**: os participantes externos da conversa são derivados da
  âncora — Cliente (via `cliente_id`) e Arquiteto (via `parceiro_id` do projeto). Nenhum
  cadastro de participante por conversa.
- **Contatos do cadastro** (decisão 12): número/e-mail sempre lidos do cadastro no momento do
  envio — arquiteto trocou de número, atualiza num lugar só e vale pra todos os projetos dele.
- **Confirmação na fase de contrato** (decisão 13): painel da etapa de contrato mostra os
  contatos dos participantes e pede confirmação explícita do canal (preenchimento + validade),
  registrando quem confirmou/quando. UI avisa "arquiteto sem WhatsApp no cadastro" quando faltar.
- **Mesmo arquiteto com N projetos na loja**: N conversas separadas (a âncora é o projeto — a
  Fatia 1 já garante). O desafio é só o THREADING do retorno, resolvido pela decisão 14
  (reply citado → determinístico; solto com ambiguidade → fila de triagem humana).

## Modelo de dados (consolidado)
```
Projeto (0..1) ──┐
Cliente  (0..1) ──┴──── Conversa ──── Mensagem ──── EnvioExterno (0..N)
```
- **Conversa**: `projeto_nome` (nullable), `cliente_id` (nullable), `criado_em`.
- **Mensagem**: `conversa_id`, `autor_usuario_id` (NULL se resposta externa), `corpo` (ou
  `corpo_cifrado` quando `privada=True`), `canal` (comercial|financeiro|logistica|
  suporte_tecnico|sac|interno), `natureza` (interacao|transferencia + campos da transferência:
  `transferido_para_usuario_id`, `documento_ref_id`, `bloqueador`, `resolvido_em`), `privada`
  (booleano), `criado_em`.
- **EnvioExterno**: como já desenhado (canal, destino, status, `id_externo` pra threading).
- **Projeto** ganha campos derivados (recalculáveis, não fonte de verdade):
  `responsavel_atual_usuario_id`, `responsavel_bloqueador` (bool), `responsavel_desde`.

*(Documento compartilhável, canal e-mail e canal WhatsApp seguem como já desenhado nas versões
anteriores — sem mudança de conteúdo.)*

## Fatias e complexidade (estimativa, atualizada)
1. **Fundação** (~1,5–2 sessões): Conversa (com vínculo flexível projeto/cliente) + Mensagem
   interna, sem canal externo, sem transferência/bloqueador/privada ainda.
2. **Responsabilidade + transferência** (~1,5 sessão): campo `natureza`, resolução da pessoa
   responsável pelos três mecanismos existentes (Consultor/Mapa de Atribuições/Função), tag no
   topo do Ciclo.
3. **Bloqueador como gate** (~1–1,5 sessão, **atenção redobrada**: mexe em `pode_avancar()`, motor
   de produção — merece testes de regressão no gating existente, não só nos casos novos).
4. **Modo privado** (~0,5–1 sessão): criptografia do corpo, controle de acesso por nível.
5. **Documento compartilhável** (~0,5–1 sessão).
6. **Canal e-mail** (~1,5 sessões, 5 endereços — é configuração, não 5x desenvolvimento).
7. **Canal WhatsApp** (~2–2,5 sessões + aprovação Meta em paralelo, 5 números na mesma conta).

## Riscos e pontos de atenção
- (mantidos: dependência de prazo da Meta, threading heurístico, contato avulso, LGPD)
- **Bloqueador mexe em código sensível**: `pode_avancar()` é hoje a fonte única de verdade do
  gating do ciclo, já usada em produção — a Fatia 3 precisa rodar a suíte de testes existente do
  ciclo inteira, não só os testes novos, antes de ir pra produção.
- **Criptografia do modo privado**: precisa de uma chave de cifragem gerenciada com cuidado (não
  pode ficar hardcoded no código nem no mesmo lugar do banco) — é um detalhe de infraestrutura a
  resolver na Fatia 4, fora do escopo desta spec de produto.

## Status
Todas as decisões de produto estão fechadas (ver "Decisões já tomadas", itens 1-10). Não há
pendências abertas — a spec está pronta para orçamento de implementação/entrada em backlog.
