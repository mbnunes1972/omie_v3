# Central de Comunicação — plataforma omnichannel (design)

**Data:** 2026-07-27
**Status:** desenho aprovado (decisões fechadas com o lojista); implementação em fatias, ainda não iniciada.
**Evolui / engloba:** `2026-07-25-chat-projeto-porta-externa-whatsapp-email-design.md` (chat do projeto +
canal externo). A "Conversa" do projeto vira **um** tipo de conversa dentro da Central; nada do que existe
é jogado fora — é generalizado.

---

## 1. Motivação

Hoje a comunicação vive em dois lugares mentais: o **chat interno do projeto** (`Conversa`/
`ConversaMensagem`) e o **canal externo** (`EnvioExterno`, WhatsApp/e-mail para cliente/arquiteto). O
lojista quer **uma aplicação só que resolva todos os canais**: comunicação interna entre usuários (direct
e grupo), um mural público da loja, a conversa do projeto e os canais externos (WhatsApp/e-mail) — tudo
numa **inbox única**, com **anexos (fotos e arquivos)** e uma **ponte de WhatsApp** que alcança/identifica
o funcionário pelo celular cadastrado quando ele está fora do computador.

Renomeada de **Mensageria** para **Central de Comunicação** (a UI já teve o primeiro rename Conversa →
Mensageria no commit `8792d93`; a segunda troca de rótulo entra na fatia 1).

## 2. Decisões fechadas (com o lojista, 2026-07-27)

1. **Alcance:** plataforma interna completa — inbox por usuário + direct + grupo + público, convivendo
   com a conversa do projeto e os canais externos.
2. **Omnichannel:** "interno vs externo" deixa de ser dois fluxos; passa a ser o **transporte** de cada
   mensagem (web / whatsapp / email) dentro de **uma** conversa.
3. **Público = toda a loja** (isolado por loja). Canais cross-loja da **rede** (hub de serviços:
   marketing/jurídico/financeiro/compras/logística) ficam para uma fase futura.
4. **Canal/segmento (comercial, financeiro, logística…) é automático pela FUNÇÃO do remetente** — sem
   dropdown por mensagem; vira rótulo derivado, útil também para roteamento externo.
5. **Destinatário selecionado ao abrir a conversa** (estilo WhatsApp/Teams): a audiência é a conversa; a
   mensagem herda. Não se repete a seleção por mensagem.
6. **WhatsApp do funcionário: presença + espelho/template.** A web é a casa; o WhatsApp é ponte pelo
   número da EMPRESA, dentro das regras da Meta. Offline → espelha na janela de 24h, ou template fora dela.
7. **Anexos: fotos + arquivos** na primeira entrega (web e WhatsApp), respeitando o teto ~16 MB de mídia
   do WhatsApp.

## 3. Restrições da plataforma WhatsApp (verdade de engenharia — não ignorar)

- Só via **Cloud API** com o **número WhatsApp Business da empresa**. **Não** há acesso ao WhatsApp
  **pessoal** do funcionário; funcionário↔funcionário **não** viaja pelo WhatsApp pessoal deles.
- **Entrada:** livre. Alguém escreve para o número da empresa → casa o telefone com o **celular
  cadastrado** → identifica usuário (funcionário) ou contato (cliente) → roteia para a inbox/thread certa.
- **Saída para uma pessoa:** **livre só dentro de 24h** da última mensagem que ela enviou à empresa. Fora
  disso, exige **template pré-aprovado** pela Meta. Sem texto livre proativo a qualquer hora.
- Implicação de design: internamente tudo acontece no app; o WhatsApp **notifica/espelha** um indivíduo
  pelo número da empresa, sempre limitado por janela/template.
- Já existe base para a entrada: webhook `/webhooks/whatsapp` + `rotear_entrada`/`processar_entrada` em
  `mod_chat_externo.py` (hoje resolve cliente/arquiteto; estender para funcionário por celular).

## 4. Modelo de dados

Reuso máximo do que existe. `Conversa.projeto_nome` já é nullable e `ConversaMensagem.autor_usuario_id`
já registra o remetente — então "origem" e "conversa sem projeto" já são suportados.

### 4.1 `Conversa` (estende)
- `tipo` novo: `projeto | direct | grupo | publico` (default mantém compat: registros atuais = `projeto`).
- `titulo` (grupo nomeado; null para direct/publico/projeto).
- `criado_por_id` (quem abriu).
- `loja_id` já existe (isolamento). `publico` não lista participantes — audiência = a loja.

### 4.2 `conversa_participantes` (nova)
- `conversa_id`, `usuario_id`, `papel` (membro | admin), `adicionado_em`, `arquivada` (por usuário),
  `lido_ate_mensagem_id` (base do "não lido"). Só para `direct`/`grupo`. `direct` = exatamente 2 linhas.

### 4.3 `ConversaMensagem` (estende)
- `autor_usuario_id` (remetente — já existe).
- `transporte` novo: `web | whatsapp | email` (por onde a mensagem entrou/saiu). Substitui/generaliza o
  `canal` interno/externo atual.
- `canal_segmento` derivado da função do autor no envio (comercial/financeiro/…): rótulo, não seleção.
- `privada`, `corpo_cifrado`, `natureza`, `transferido_para_funcionario_id`, `bloqueador`,
  `documento_ref_id` — **preservados** (transferência/bloqueador do ciclo continuam valendo).

### 4.4 `mensagem_anexos` (nova)
- `mensagem_id`, `tipo` (imagem | arquivo), `nome`, `mime`, `tamanho`, `caminho` (armazenamento local,
  reusando a infra de upload/multipart já existente), `whatsapp_media_id` (quando veio/foi pelo WhatsApp).

### 4.5 `EnvioExterno` (mantém)
- Continua registrando saída/entrada externa e o threading (`id_externo`). Agora também para **funcionário**
  como destinatário (não só cliente/parceiro/avulso): `destinatario_tipo` ganha `funcionario`.

### 4.6 Presença (nova, leve)
- `usuario_presenca`: `usuario_id`, `visto_em` (heartbeat da web). Regra: offline há > N min → mensagens
  destinadas a ele podem espelhar/notificar no WhatsApp, dentro das regras da Meta. Alternativa/soma:
  preferência por usuário (`notificar_whatsapp`: sempre | quando_offline | nunca).

## 5. Identidade e roteamento (o "associe pelo celular cadastrado")

- **Saída:** o app manda para a conversa; para cada destinatário, decide o transporte (web sempre; WhatsApp
  se offline/preferência e dentro das regras). Número do funcionário = `usuarios.whatsapp` (ou
  `usuarios.telefone`/`funcionarios.telefone` como fallback), normalizado E.164.
- **Entrada:** webhook recebe do número da empresa → normaliza o telefone → procura **usuário** por
  celular; se achar, a mensagem entra como daquele usuário na conversa correspondente; senão, cai no fluxo
  de **contato externo** (cliente/arquiteto) como hoje. Colisão de número (mesmo celular em 2 cadastros)
  precisa de regra de desempate — **pendência** (ver §8).

## 6. UI (inbox única)

- Item de menu **Central de Comunicação** (lateral) + o botão no projeto continua abrindo a conversa
  **do projeto** já dentro da Central.
- **Inbox:** lista de conversas do usuário (direct, grupo, 📣 Loja, projetos) com prévia + não lidas.
- **Nova mensagem:** seletor de **Tipo** (Direct / Grupo / Loja) e **Para** (busca de usuário da loja,
  filtrável por função; grupo = N usuários + nome). "Loja" não pede destinatário (audiência implícita).
- **Thread:** histórico + compositor com **anexo (foto/arquivo)**, privada (cifrada), e — quando a conversa
  tiver contraparte externa — indicação do transporte usado (web/WhatsApp/e-mail) por mensagem.
- Mantém transferência/bloqueador do ciclo onde faz sentido (conversa de projeto).

## 7. Tenancy

- Tudo escopado por `loja_id`. Direct/grupo/publico **não** cruzam loja. Público = a loja do remetente.
- Alinha com a correção recente de contexto de loja (a Central herda `_lojaAtiva`/escopo operacional).
- **Futuro (hub da rede):** canais cross-loja para serviços compartilhados da rede — fora do escopo desta
  spec, mas o modelo (`Conversa.tipo`, participantes) já comporta um tipo `rede` depois.

## 8. Pendências / decisões abertas

- Desempate de **celular duplicado** em cadastros distintos na entrada do WhatsApp.
- **Templates** WhatsApp a aprovar na Meta (notificação "abra o sistema"; espelho de conteúdo).
- **Custos** WhatsApp (pricing por conversa) e limites operacionais — validar com o lojista.
- Retenção/limpeza de anexos; antivírus/validação de MIME (o `contrato_template` já tem url_fetcher
  confinado — anexos seguem princípio de não confiar em conteúdo).
- Notificações no navegador (Web Push) — provável fatia própria.

## 8b. Canais públicos — revisão 2026-07-27 (decisão do lojista, Fatia 4)

O "público = a loja" foi refinado para **três** canais, e o nome do app virou **Orizon Chat**:

- **Mural** (`tipo='mural'`): quadro de **avisos** por loja. Todos leem; **só Gerente/Diretor**
  postam (`pode_escrever_conversa` exige `ver_todas_conversas`). Um por loja (get-or-create).
- **Fórum da Loja** (`tipo='forum_loja'`): comunicação interna aberta da loja. É um **fórum de
  debates** — cada conversa é um **tópico** (título + Assunto), todos da loja leem/postam; busca por
  título/assunto.
- **Fórum Orizon** (`tipo='forum_orizon'`): **cross-loja pela REDE** (`Conversa.rede_id`) — o
  primeiro dado cross-loja deliberado do sistema. **Todos os usuários das lojas da rede** leem e
  postam (decisão do lojista). Também é fórum de debates (título; assunto fica 'livre' porque
  projeto/custom são por loja). Sem rede associada → o fórum não aparece.

Tenancy: mural/forum_loja seguem isolados por loja; forum_orizon é a exceção gated pela rede
(`pode_ler_conversa`/`pode_escrever_conversa` centralizam a regra). O antigo canal `publico` da
Fatia 3 migrou para um debate `forum_loja` "Geral".

## 9. Fatiamento proposto (TDD backend → UI, uma fatia por vez)

1. **Fatia 1 — núcleo interno:** rename UI → "Central de Comunicação"; `Conversa.tipo` +
   `conversa_participantes`; **direct** e **grupo** com seletor "Para"; inbox básica; canal_segmento
   derivado da função. (Sem anexos, sem WhatsApp novo.)
2. **Fatia 2 — público da loja + não-lidos:** conversa `publico` (mural da loja); `lido_ate_mensagem_id`
   e contadores de não lidas na inbox.
3. **Fatia 3 — anexos:** fotos + arquivos (web), reusando multipart; render de mídia na thread.
4. **Fatia 4 — ponte WhatsApp do funcionário:** identidade por celular na entrada; presença (heartbeat);
   espelho na janela 24h + template fora dela; anexos via mídia do WhatsApp.
5. **Fatia 5 — unificação fina:** transporte por mensagem visível; conversas com contraparte externa
   (cliente/arquiteto) integradas à mesma inbox; preferências de notificação.

Cada fatia: suíte verde, DEV_LOG atualizado, re-ingestão do grafo MCP, e verificação com a Vera antes de
fechar (área sensível: tenancy + integração externa).
