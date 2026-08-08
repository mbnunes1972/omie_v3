# Checklist de Acessos — transferir para o cofre compartilhado

> Fase 1, item 2 do Plano de Transição: "Repositório de código, credenciais das três instâncias
> compartilhadas (Integração, Homolog, Produção) e da API do WhatsApp Business/Meta,
> centralizados em um cofre de senhas compartilhado (nunca em texto simples)."
>
> **Este documento não contém nenhuma credencial** — só o inventário do que existe e onde
> procurar, pra quem for popular o cofre. Cada linha é uma tarefa: mover o valor real pro
> cofre, e (quando fizer sentido) revogar/trocar o que estiver espalhado fora dele.

## 1. Repositório

- [ ] **GitHub** `mbnunes1972/orizon-manager` — adicionar Juliana e Wesley como colaboradores
  (nível de permissão a definir: `write` pra ambos, ou `admin` só pra Juliana).
- [ ] Decidir se cada dev usa **chave SSH própria** cadastrada no GitHub (recomendado — não
  compartilhar a chave que está nesta máquina) ou HTTPS com token pessoal.

## 2. Acesso às 3 instâncias (SSH)

- [ ] **VPS de dev** `167.88.33.121` (hospeda Instância A `:8765` e Instância B `:8766`) —
  hoje o acesso `root@` é por chave SSH cadastrada nesta máquina. Decidir: chave por pessoa
  (mais rastreável) ou usuário próprio por dev (`useradd` + sudo, mais seguro que
  compartilhar `root`).
- [ ] **VPS de produção** `179.197.77.9` (`www.orizonone.com.br`) — acesso **só por chave**
  (login por senha está desabilitado no servidor). Mesma decisão acima: chave por pessoa ou
  usuário próprio. **Esta é a mais sensível das três — vale restringir a menos gente
  possível** (ex.: só Juliana, e Marcelo continua tendo).

## 3. Variáveis de ambiente por instância (arquivo `.env`, fora do git em cada uma)

Cada ambiente (local de cada dev, Instância A, Instância B, Produção) tem seu próprio arquivo
de env com, pelo menos:

- [ ] `DATABASE_URL` (Postgres — usuário/senha/host/porta/nome do banco; um valor DIFERENTE
  por ambiente, nunca reusar senha entre eles).
- [ ] `ORIZON_CHAT_ENC_KEY` — chave do modo privado do Chat (uma por ambiente: A e B têm
  chaves próprias hoje, conferir se Produção também tem a dela).
- [ ] Credenciais do transporte WhatsApp (Meta Cloud API) — ver seção 4.
- [ ] Credenciais de e-mail (SMTP) se/quando o transporte de e-mail dos canais externos do
  Chat for ativado (`ORIZON_SMTP_HOST/PORT/USER/PASS/FROM`).
- [ ] Credencial de emissão de NF-e (Focus NFe ou equivalente — **confirmar com Marcelo qual é
  a fonte de verdade atual**, o histórico do projeto menciona migração de Omie pra Focus NFe).

## 4. WhatsApp Business / Meta API

- [ ] Acesso ao **Meta Business Manager** / App do WhatsApp Business (console de
  desenvolvedor da Meta) — quem tem login hoje, e se precisa adicionar Juliana.
- [ ] Tokens em uso: `ORIZON_WA_TOKEN`, `ORIZON_WA_PHONE_ID`, `ORIZON_WA_VERIFY_TOKEN`,
  `ORIZON_WA_APP_SECRET` — um conjunto por ambiente que tiver o transporte ativo (confirmar
  quais ambientes já têm isso configurado; o histórico indica que pelo menos Homolog teve
  configuração ativa).
- [ ] Número de WhatsApp da loja conectado ao sistema (visível em Config → Números
  Conectados dentro do próprio app, sem expor o token).

## 5. Certificado digital / Fiscal (achado ao levantar este checklist — ver nota abaixo)

- [ ] **Certificado digital A1 (.pfx) da empresa**, usado pra assinar NF-e — **está hoje como
  arquivo solto** na pasta compartilhada `E:\2026\DESENVOLVIMENTO\` (não em cofre, não
  criptografado em repouso). Isso é um dos itens **mais sensíveis** de todo o checklist —
  mover pro cofre (ou pra um cofre de certificados dedicado, se o vault escolhido não lidar
  bem com binário) o quanto antes, e restringir quem tem cópia local.
- [ ] Senha do certificado — se estiver escrita em algum lugar em texto simples, mover pro
  cofre e apagar da origem.
- [ ] Credenciais da SEFAZ/ambiente fiscal (homologação × produção) usadas na integração.

## 6. Outro achado — documento de credencial em texto simples

- [ ] Há um arquivo `Chave Secreta do Agente de email.docx` na mesma pasta
  `E:\2026\DESENVOLVIMENTO\` — pelo nome, é exatamente o tipo de coisa que o próprio plano
  pede pra nunca ficar em texto simples fora do cofre. Vale abrir, mover o conteúdo pro
  cofre e apagar/arquivar o `.docx` original.

## 7. Domínio / DNS / certificado HTTPS

- [ ] Acesso ao **painel do registrador do domínio** (Hostinger) — pra manutenção de DNS
  (`orizonone.com.br`).
- [ ] HTTPS é automático via **certbot/Let's Encrypt** na VPS de produção (renovação
  automática) — não precisa de credencial própria, só o acesso SSH da seção 2.

## 8. Login de super admin da aplicação (não é infra, mas é acesso)

- [ ] Login de **super_admin em Produção** — hoje é uma conta pessoal do Marcelo (não a senha
  de exemplo do `seed.py`). Decidir se Juliana ganha conta própria de `admin_rede`/`master`
  em vez de compartilhar essa.

---

**Como usar este checklist:** cada item marcado `[ ]` vira uma linha no cofre de senhas
escolhido (1Password, Bitwarden, Vaultwarden self-hosted, etc. — ferramenta a definir se ainda
não tiver uma). Depois de migrado, os arquivos soltos (certificado, docx de senha) devem ser
apagados da pasta compartilhada, não só copiados.
