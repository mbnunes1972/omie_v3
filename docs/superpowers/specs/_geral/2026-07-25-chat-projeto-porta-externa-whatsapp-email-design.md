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
12. **Contatos externos vêm do CADASTRO** (Parceiro E Cliente já têm campo `whatsapp` próprio
    — constatado em 2026-07-25; telefone é só fallback) — nunca da fase de contrato: cadastro é
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
15. **Fatia 2 REAPROVEITA o sistema de responsável por etapa que já existe** (v12:
    `CicloEtapa.funcao_responsavel_id`/`responsavel_funcionario_id` + `responsavel_efetivo`) em
    vez de criar uma resolução paralela — ver seção 6 (adendo 2026-07-25, achado durante
    preparação da Fatia 2).
16. **Responsabilidade permanece por FUNCIONÁRIO** (decisão final 2026-07-25, após o teste). A
    ideia de mover para Usuário foi levantada e DESCARTADA pelo usuário: "se está por
    funcionário, mantemos funcionário; a responsabilidade recai sobre o funcionário". O v12
    Funcionário-based (decisões 6/15) segue como está — não há pivô. **Ajuste que fica:** o
    **default inicial da tag "com a bola" é o CRIADOR do projeto** (`Projeto.criado_por_id`, um
    Usuário → resolvido a Funcionário pela ponte `Usuario.funcionario_id`) — nunca "não
    atribuído" quando há criador; quando o criador não tem Funcionário vinculado, a tag mostra
    o NOME do usuário criador como fallback só-de-exibição (a responsabilidade formal segue
    sendo por Funcionário).
17. **Transição de fase gera uma mensagem AUTOMÁTICA de passagem oficial** na Conversa do
    projeto (2026-07-25): ao concluir uma fase, o sistema registra uma mensagem de
    transferência para o responsável da fase seguinte (que pode ser a mesma pessoa) —
    formaliza a passagem, não é só o avanço visual da tag.
18. **Dois canais para isolar interno × externo** (reframe 2026-07-25): canal **interno**
    (equipe do projeto — responsabilidade, transferência, bloqueador) e canal **externo**
    (cliente e arquiteto). **Qualquer pessoa envolvida no projeto** pode conversar pelo canal
    externo com cliente/arquiteto; a separação é de canal, não de permissão de quem fala.
19. **Destinatário do canal externo tem seletor com filtro** interno(usuário) / parceiro
    (arquiteto) / cliente, mais um **campo de WhatsApp avulso** (número diferente do cadastrado,
    para um envio pontual) — 2026-07-25. Isso é do canal externo (Fatias 6-7), NÃO da
    transferência de responsabilidade (que é interna, entre usuários — decisão 16). Esclarece a
    dúvida do teste: "não colocar cliente/arquiteto" valia SÓ para o seletor de *transferência
    de responsabilidade* (externo não é responsável por etapa do ciclo); no *canal externo* eles
    são exatamente os destinatários.

## 1) Responsabilidade por pessoa — de onde vem cada uma
Achado no código (validado 2 vezes — primeiro na preparação inicial, depois confirmado ao começar
a Fatia 2, ver seção 6 para a reconciliação completa): já existem **mecanismos de atribuição por
pessoa**, cada um cobrindo parte das faixas do ciclo (`mod_ciclo.FAIXA_POR_ETAPA`). A tag de
responsabilidade não cria um sistema novo — ela **consulta e estende** o que já existe:

| Faixa/canal          | Fonte da pessoa responsável                                   | Situação |
|-----------------------|----------------------------------------------------------------|----------|
| Comercial (`vendas`)  | `Briefing.consultor_id`                                        | ✅ já existe (precisa de ponte Usuário↔Funcionário — seção 6) |
| Execução (`execucao_projeto`) | `AtribuicaoAmbiente` (papéis `projeto_executivo`, `medicao`), já plugado no v12 via `_ETAPA_PAPEL` | ✅ já existe e já é o default automático |
| Suporte Técnico (`montagem`) | `AtribuicaoAmbiente` (papéis `montagem`, `assistencia`), já plugado no v12 via `_ETAPA_PAPEL` | ✅ já existe e já é o default automático |
| Financeiro (`gate_financeiro_*`, `conciliacao_final`) | Usuário com Função **"Gerente Administrativo/Financeiro"** na loja | 🆕 resolvido por função (só 1 pessoa por loja, como você confirmou) — falta plugar como default no v12 |
| Logística (`expedicao`) | Usuário com Função **"Assistente Logístico"** na loja        | 🆕 resolvido por função — falta plugar como default no v12 |
| SAC                    | Usuário com Função **"SAC"** na loja                          | 🆕 resolvido por função — a Função "SAC" **já existe** como cargo padrão (`FUNCOES_PADRAO`); sem etapa/faixa fixa (não entra no v12 por etapa) |

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

## 6) Reconciliação com o sistema de responsável por etapa (v12) (adendo 2026-07-25)
Ao começar a implementar a Fatia 2, achei que o sistema já tem uma boa parte do que a Fatia 2 ia
construir — chamo de "v12" porque é a versão atual do motor de ciclo em produção:
- `CicloEtapa` já tem `funcao_responsavel_id` (herdado do Cronograma de Projeto Padrão em D0) e
  `responsavel_funcionario_id` (override manual, restrito a funcionários daquela função).
- O endpoint `GET /api/projetos/<nome>/ciclo` já calcula, por etapa, um **`responsavel_efetivo`**:
  usa `responsavel_funcionario_id` se estiver preenchido; senão resolve automaticamente via
  `AtribuicaoAmbiente` (Mapa de Atribuições) — mas só para as etapas de Medição/Projeto
  Executivo/Montagem/Assistência (`_ETAPA_PAPEL`, etapas 9, 10, 11/11a/11b/11c/11e, 17, 18).
  Vendas (1, 2, 3, 4, 7), Financeiro (8, 11d, 21) e Logística (12-16) **não têm default
  automático hoje** — só funcionam se alguém preencher `responsavel_funcionario_id` na mão.

Em vez de criar uma resolução paralela (como a spec original desenhava), a Fatia 2 passa a ser
uma **extensão** desse mecanismo existente. Ordem de precedência pra "quem está com a bola" em
cada etapa (do que manda mais pro que manda menos):

1. **Transferência oficial pelo chat** (mensagem `natureza=transferencia` apontando uma etapa) —
   não cria campo novo: grava diretamente em `CicloEtapa.responsavel_funcionario_id` da etapa em
   questão, o mesmo campo que já existe hoje como override manual. Ou seja, "transferir pelo
   chat" e "editar o responsável na tela do Ciclo" viram a mesma operação por baixo — só muda a
   origem (chat vs. tela).
2. **Default automático por etapa** — é o `_ETAPA_PAPEL` que já existe, estendido pra cobrir as
   faixas que faltam:
   - Vendas → `Briefing.consultor_id`. Esse campo aponta pra `Usuario`, e `responsavel_efetivo`
     precisa de um `funcionario_id` — então esse elo exige a **ponte Usuário↔Funcionário**
     (`Usuario.funcionario_id`, que já existe no modelo). Se o consultor não tiver Funcionário
     vinculado, essa etapa fica sem default automático (não quebra, só não preenche sozinho).
   - Financeiro → Função **"Gerente Administrativo/Financeiro"** ativa na loja.
   - Logística → Função **"Assistente Logístico"** ativa na loja.
3. **Sem default** — etapa aparece como "responsável não atribuído" na tag do topo; alguém
   precisa transferir (item 1) ou preencher manualmente pra sair desse estado.

**SAC fica de fora dessa cadeia** — como decidido na seção 2, conversa de SAC pode nem ter
projeto por trás, então não existe `CicloEtapa` pra ancorar. O responsável do SAC continua
resolvido direto pela Função "SAC" (seção 1), sem passar pelo `pode_avancar`/ciclo.

**Efeito prático na tag "quem está com a bola" no topo da tela do Ciclo**: ela não precisa de
nenhum campo novo no `Projeto` — só busca o `responsavel_efetivo` da etapa atual (a primeira
etapa pendente/em andamento) no mesmo `GET /api/projetos/<nome>/ciclo` que já existe hoje.

## 6b) Criador como default da tag + mensagem automática na transição (decisões 16-17, 2026-07-25)
Mantido tudo Funcionário-based (decisão 16 — sem pivô para Usuário). Dois ajustes desta revisão:
- **Criador é o dono-base:** a cadeia de resolução do responsável efetivo por etapa ganha um
  último degrau — `responsavel_funcionario_id` (transferência/manual) > Mapa de Atribuições >
  default da faixa (Vendas/Financeiro/Logística) > **criador do projeto** (`Projeto.criado_por_id`
  → Funcionário pela ponte `Usuario.funcionario_id`) > nada. A tag "com a bola" nunca fica "não
  atribuído" quando há criador; se o criador não é Funcionário, a tag exibe o nome do usuário
  criador (fallback só-visual, exposto como `criado_por_nome` no `GET /ciclo`).
- **Passagem oficial automática (decisão 17):** ao CONCLUIR uma fase, o `PATCH /ciclo/<cod>` posta
  na Conversa do projeto uma mensagem `natureza=transferencia` apontando a **próxima etapa
  principal** e o responsável dela (mesma resolução acima) — documenta a passagem sem congelar o
  default (não grava `responsavel_funcionario_id` da próxima; só registra). Última fase (sem
  próxima) não gera nada. Autor da mensagem = quem concluiu a fase.

## 6c) Dois canais: interno × externo (decisões 18-19, 2026-07-25)
- **Canal interno** — equipe do projeto (usuários). Onde vivem responsabilidade, transferência,
  bloqueador, modo privado. É o que as Fatias 1-5 construíram.
- **Canal externo** — cliente e arquiteto. Qualquer pessoa do projeto pode falar por ele
  (separação é de canal, não de permissão). Destinatário por **seletor com filtro** (usuário
  interno / parceiro-arquiteto / cliente) + **WhatsApp avulso** para número fora do cadastro.
  Materializa-se nas **Fatias 6-7** (e-mail/WhatsApp) — o `enviar_mensagem` segue recusando canal
  ≠ interno até lá. A transferência de RESPONSABILIDADE nunca aponta para externo (externo não é
  responsável por etapa do ciclo) — o seletor rico é só do canal externo.

## Modelo de dados (consolidado)
```
Projeto (0..1) ──┐
Cliente  (0..1) ──┴──── Conversa ──── Mensagem ──── EnvioExterno (0..N)
```
- **Conversa**: `projeto_nome` (nullable), `cliente_id` (nullable), `criado_em`.
- **Mensagem**: `conversa_id`, `autor_usuario_id` (NULL se resposta externa), `corpo` (ou
  `corpo_cifrado` quando `privada=True`), `canal` (comercial|financeiro|logistica|
  suporte_tecnico|sac|interno), `natureza` (interacao|transferencia + campos da transferência:
  `etapa_codigo` (etapa do ciclo afetada, quando aplicável), `transferido_para_funcionario_id`,
  `documento_ref_id`, `bloqueador`, `resolvido_em`), `privada` (booleano), `criado_em`.
- **EnvioExterno**: como já desenhado (canal, destino, status, `id_externo` pra threading).
- **Responsabilidade NÃO ganha campo novo no `Projeto`** (correção 2026-07-25, ver seção 6): uma
  mensagem de transferência grava direto em `CicloEtapa.responsavel_funcionario_id` da etapa
  referenciada — a fonte de verdade continua sendo o `CicloEtapa`/`responsavel_efetivo` que já
  existe (v12), o chat só é mais um jeito de escrever nele. SAC (sem etapa) é a exceção: resolve
  por Função, sem gravar em `CicloEtapa`.

*(Documento compartilhável, canal e-mail e canal WhatsApp seguem como já desenhado nas versões
anteriores — sem mudança de conteúdo.)*

## Fatias e complexidade (estimativa, atualizada)
1. **Fundação** (~1,5–2 sessões): Conversa (com vínculo flexível projeto/cliente) + Mensagem
   interna, sem canal externo, sem transferência/bloqueador/privada ainda.
2. **Responsabilidade + transferência** (~1 sessão, **reduzido** — achado 2026-07-25: boa parte
   já existe via v12, ver seção 6): campo `natureza` na Mensagem; mensagem de transferência
   passa a gravar em `CicloEtapa.responsavel_funcionario_id` (reaproveita o campo/mecanismo já
   em produção, não cria tabela nova); estender o default automático (hoje só
   Medição/PE/Montagem/Assistência) pra Vendas (via `Briefing.consultor_id` + ponte
   Usuário↔Funcionário) e Financeiro/Logística (via Função); SAC resolve à parte, por Função,
   sem etapa; tag no topo do Ciclo passa a ler o `responsavel_efetivo` da etapa atual do
   endpoint que já existe (`GET /api/projetos/<nome>/ciclo`), sem campo novo no Projeto.
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
Todas as decisões de produto estão fechadas (ver "Decisões já tomadas", itens 1-15). Fatia 1
(Fundação) **implementada e commitada** (`mod_chat.py`, tabelas `Conversa`/`ConversaMensagem`/
`ContatoConfirmacao`, endpoints `GET`/`POST /api/projetos/<nome>/conversa`) — incluiu, além do
escopo original, os adendos 11-14 (participantes externos derivados do cadastro, confirmação de
contato na fase de contrato, threading de resposta externa). Fatia 2 teve o desenho ajustado
2026-07-25 (item 15 + seção 6) para reaproveitar o sistema de responsável por etapa (v12) já em
produção, em vez de construir uma resolução paralela — reduz o escopo de implementação da Fatia 2.
Não há pendências de produto abertas — a spec está pronta para a Fatia 2 entrar em implementação.
