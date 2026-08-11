# Orientação para o code — Landing/Login (revisão Juliana v2)

**Data:** 2026-08-11
**Spec de referência:** `docs/superpowers/specs/landing/2026-08-11-sugestoes-correcao-landing.md`
**Mockup de referência:** `docs/superpowers/specs/landing/mockups/landing-proposta-v2.html`
**Arquivo a alterar:** `static/login.html`

## Contexto

A Juliana revisou a página de entrada (`/login`) comparando com o HTML que está no ar
(`http://167.88.33.121:8766/login` = `static/login.html`) e consolidou o feedback na spec de
referência acima, com um mockup navegável já com tudo aplicado. Este documento traduz esse
diff em um checklist objetivo para aplicar direto em `static/login.html`.

**Atenção antes de começar — o mockup é autocontido, `static/login.html` não é:**

1. O mockup embute o bloco inteiro de design tokens v1.7 (`:root, [data-theme="light"] {...}` e
   `[data-theme="dark"] {...}`) dentro do próprio `<style>`, porque foi feito para abrir isolado
   (comentário no próprio arquivo: "PROPOSTA v2 — mockup autocontido (tokens v1.7 embutidos)").
   `static/login.html` **não tem esse bloco** — ele importa `design-system/orizon-tokens.css`
   (já na v1.7, confirmado — não há mismatch de versão, então não precisa mexer nesse link).
   **Não copiar o bloco de tokens do mockup para dentro de `static/login.html`.** Só a "ponte"
   de variáveis legadas (`--muted`, `--accent-tint`, `--primary`, etc., já existente nas duas
   pontas com o mesmo conteúdo) continua como está.
2. O favicon do mockup aponta pra uma URL absoluta de teste
   (`http://167.88.33.121:8766/glifo-favicon.svg`) porque foi aberto fora do servidor real.
   Em `static/login.html` o favicon **deve continuar relativo** (`href="glifo-favicon.svg"`) —
   não trocar.
3. O `<script>` no fim do arquivo (toggle de tema + `POST /api/auth/login`) é **idêntico** nos
   dois arquivos, byte a byte — nenhuma mudança necessária ali.
4. Comentário na linha 10 de `static/login.html` diz "Design system v1.4" — está desatualizado
   (o arquivo já está na v1.7 de fato). Não é bloqueante, mas aproveite para corrigir o número
   no comentário já que vai mexer nessa região do arquivo mesmo.

## Pontos que precisam de atenção especial na leitura da spec

1. **Seção 5 da spec (remover "Manager") foi superada por uma atualização datada de
   27/07/2026 dentro do próprio documento** — o nome final do produto é **Orizon One**, não
   só "Orizon". Onde o checklist original da seção 5 diz "Orizon", o mockup já aplica "Orizon
   One" (nav, login, title, footer, aria-labels). Seguir o mockup, não o checklist original da
   seção 5 isolado.
2. **Seção 4 (gráfico do hero)** passou por várias iterações registradas na própria spec (v2.5
   → v2.6 → v2.7 → v2.9) até chegar no SVG final do mockup: uma trilha serpentina com os
   números 1–7 (sem nomes de etapa) e um indicador de margem (barrinhas ascendentes) sobre o
   ponto 7. **Use o SVG do mockup como fonte da verdade**, não as descrições intermediárias da
   spec (que documentam o histórico da decisão, não o resultado final).
3. **Seção 5 do mockup também é onde fica a ressalva "Fora do HTML"**: os comentários de CSS em
   `static/login.html` referenciam REGRAS_MARCA (lockup "glifo + wordmark Manager") — ver
   "Fora de escopo" abaixo.
4. **A seção de login perde a coluna de marketing à esquerda** (eyebrow "Acesso" + H2 "Sua
   operação, sua conta, seu painel" + parágrafo) — vira só o card centralizado com uma nota
   curta abaixo. Isso muda `.login-grid` de `display:grid` (2 colunas) para
   `display:flex; flex-direction:column; align-items:center`, então a media query que hoje
   colapsa `.login-grid` em telas pequenas (`@media (max-width:860px){ .login-grid{
   grid-template-columns:1fr } }`) fica sem função e pode ser removida.

## Checklist de mudanças em `static/login.html`

### 1. `<head>`

- `<title>`: `Orizon Manager — Gestão para redes de móveis planejados` →
  `Orizon One — Gestão para redes de móveis planejados`
- Favicon: **manter** `href="glifo-favicon.svg"` (relativo) — não copiar a URL absoluta do
  mockup (ver Contexto, item 2).
- Comentário da linha 10: atualizar "v1.4" → "v1.7" (cosmético, mas já que vai tocar no
  arquivo).

### 2. CSS — ajustes de espaçamento vertical (spec, seção 6)

| Regra | Hoje | Novo |
|---|---|---|
| `section { padding }` | `88px 24px` | `64px 24px` |
| `.hero { padding }` | `96px 24px 40px` | `64px 24px 32px` |
| `.process-head { margin-bottom }` | `56px` | `40px` |
| `.split { margin-top }` | `56px` | `40px` |

(`.app-teaser { margin-top }` some junto com a remoção do bloco todo — item 7 abaixo.)

### 3. CSS — marca (nav e login-card)

Trocar o par de classes empilhadas (`.wm-orizon` + `.wm-manager`) por lockup de uma linha só,
com "One"/"Manager" em cobre:

```css
/* nav — hoje: .logo-wm{display:flex;flex-direction:column;...} + .wm-orizon + .wm-manager */
.logo-wm { font-family: var(--font-display); font-weight: 700; font-size: 17px; letter-spacing: .02em; color: var(--text); }
.logo-wm .wm-one { color: var(--accent); }

/* login-card — hoje: .login-brand .lb-wm{display:flex;flex-direction:column;...} + .wm-orizon + .wm-manager (com tamanhos próprios) */
.login-brand .lb-wm { font-family: var(--font-display); font-weight: 700; font-size: 20px; letter-spacing: .02em; color: var(--sidebar-text-active); }
.login-brand .lb-wm .wm-one { color: var(--sidebar-accent); }
```

Remover as regras antigas `.logo-wm .wm-orizon`, `.logo-wm .wm-manager`, `.login-brand .wm-orizon`,
`.login-brand .wm-manager`.

### 4. CSS — hero: nova classe `.lede-plus`

Adicionar (não existe hoje):

```css
.lede-plus { font-size: 15px; line-height: 1.6; max-width: 560px; margin-top: 14px; }
```

Remover `.hero-ctas` e `.hero-note` (regras de CSS) — o markup que as usa também sai (item 6).

### 5. CSS — régua de processo (7 etapas)

```css
.process-line {
  position: absolute; top: 19px; left: 0;
  right: calc((100% - 84px) / 7 - 19px); /* hoje: right: 0 */
  height: 1px; background: var(--border-strong);
}
.process-steps { display: grid; grid-template-columns: repeat(7, 1fr); gap: 14px; position: relative; }
/* hoje: repeat(6, 1fr), gap: 16px */
```

### 6. CSS — cards (`#financeiro`) e app-teaser

```css
.card-head { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; } /* novo */
.card-icon { width: 44px; height: 44px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
/* remove margin-bottom:20px do .card-icon — agora fica lado a lado com o h3, não empilhado */
.card h3 { font-size: 20px; } /* remove margin-bottom: 6px */
```

Remover por completo o bloco `.app-teaser`, `.app-teaser-text h3/p`, `.app-badge`.

### 7. CSS — seção de login

```css
.login-grid { display: flex; flex-direction: column; align-items: center; }
/* hoje: display:grid; grid-template-columns: 1fr 420px; gap:64px; align-items:center; */
.login-card { width: 100%; max-width: 420px; } /* nova regra, adicionar às existentes do .login-card */
.login-hint { margin-top: 18px; font-size: 13px; color: var(--muted); text-align: center; max-width: 420px; } /* novo */
```

Remover a media query `@media (max-width: 860px) { .login-grid { grid-template-columns: 1fr; } }`
(sem função depois da mudança acima).

### 8. HTML — nav

- `<div class="logo" role="img" aria-label="Orizon Manager">` → `aria-label="Orizon One"`
- `<span class="logo-wm"><span class="wm-orizon">Orizon</span><span class="wm-manager">Manager</span></span>`
  → `<span class="logo-wm">Orizon <span class="wm-one">One</span></span>`
- `.nav-links`: `<a href="#processo">Processo</a><a href="#financeiro">Financeiro</a><a href="#app">App</a>`
  → `<a href="#processo">Etapas</a><a href="#financeiro">Gestão</a>` (link "App" sai junto com o
  teaser removido)

### 9. HTML — hero

- Eyebrow: `Gestão para redes de móveis planejados` → `Gestão para redes multi-loja de móveis
  planejados`
- H1: `Da venda ao balanço,<br>um só sistema.` → `Da venda ao resultado,<br>um só sistema.`
  (manter "Balanço" como está na seção `#financeiro` — a troca é só no H1, ver spec seção 1)
- Lede: trocar o parágrafo único por dois parágrafos —
  ```html
  <p class="lede" style="margin-top:20px;">
    O Orizon One conecta toda operação à gestão financeira do seu negócio.
  </p>
  <p class="lede-plus">
    Sem planilhas paralelas. Sem dados desencontrados. Sem informações
    espalhadas entre diferentes sistemas.
  </p>
  ```
- Remover o bloco `.hero-ctas` (dois botões "Acessar minha conta" / "Ver como funciona") e o
  bloco `.hero-note` inteiros.
- Substituir o SVG do hero (o de balança, `viewBox="0 0 480 380"`) pelo SVG novo do mockup —
  trilha serpentina `viewBox="0 0 480 320"` com os 7 círculos numerados (7 preenchido em cobre)
  e o indicador de margem (barrinhas). Copiar o bloco `<svg class="signature"...>` diretamente
  do mockup (linhas 383–408 do arquivo salvo em `mockups/landing-proposta-v2.html`).

### 10. HTML — régua "Uma jornada, ponta a ponta" (`#processo`)

- H2: `Do primeiro contato à assistência pós-venda` → `Sete etapas, do primeiro contato ao
  resultado.`
- Números dos `.process-num` perdem o zero à esquerda (`01`→`1` ... `06`→`6`) e ganha um `7`
  novo.
- Sub-texto de **Projetos** (etapa 3): `Medição, projeto executivo, corte` → `Medição e projeto
  executivo`
- Sub-texto de **Assistências** (etapa 6): `Loja, fábrica ou cliente — cada custo no seu lugar`
  → `Atendimento pós-venda, custo por responsável`
- Novo `.process-step` (etapa 7): label `Resultado`, sub-texto `Margem real por projeto`
  (esse é o card que herda o destaque em cobre via `:last-child`, migrado do 06 para o 07).

### 11. HTML — seção `#financeiro`

- H2: `Processo e financeiro, alimentados pelos mesmos dados` → `Operação e financeiro
  conectados pela mesma informação.`
- Lede da seção: sem mudança (texto igual nas duas versões).
- **Card "Gestão de Processo" → "Gestão da Operação":**
  - Envolver ícone + `<h3>` em `<div class="card-head">...</div>` (hoje estão soltos, um
    empilhado sobre o outro).
  - Tag: `Cada venda, do jeito certo, sempre` → `Cada venda conduzida no padrão da rede`
  - Bullets (4), todos reescritos:
    1. `Ciclo com etapas e aprovações claras — nunca perde o fio de uma venda` → `Ciclo de venda
       com etapas e aprovações definidas, do primeiro contato à conclusão`
    2. `Captação, projeto, produção e expedição em um só lugar, não em três sistemas` →
       `Captação, projeto, produção e expedição integrados em uma única plataforma`
    3. `Times sabem onde cada pedido está, sem perguntar no grupo` → `Status de cada pedido
       visível para toda a equipe, em tempo real`
    4. `Rede com várias lojas, cada uma com seu escopo — visão consolidada para quem administra`
       → `Permissões por loja e visão consolidada da rede para quem administra`
- **Card "Gestão Financeira"** (nome não muda):
  - Mesmo wrapper `.card-head` para ícone + `<h3>`.
  - Tag: `Margem real, por projeto, desde o primeiro dia` → `Margem real por projeto, desde o
    primeiro dia` (só tira a vírgula)
  - Bullets 1 e 4: sem mudança. Bullets 2 e 3 reescritos:
    2. `DRE e Balanço nascem dos mesmos lançamentos que a operação já gera` → `DRE e Balanço
       gerados a partir dos lançamentos que a operação registra`
    3. `Assistências classificadas por quem paga — cliente, loja ou fábrica` → `Custo de cada
       assistência atribuído ao responsável — cliente, loja ou fábrica`
- Remover por completo o bloco `<div class="app-teaser" id="app">...</div>` ("Em breve, no seu
  bolso" + badge iOS/Android).

### 12. HTML — seção de login (`#entrar`)

- Remover a coluna esquerda de marketing (`<div class="reveal"><div class="eyebrow">Acesso</div>
  <h2>Sua operação, sua<br>conta, seu painel.</h2><p class="lede">...</p></div>`) — some
  inteira.
- `.login-card` continua, mas:
  - `aria-label="Orizon Manager"` → `aria-label="Orizon One"`
  - Lockup interno: `<span class="lb-wm"><span class="wm-orizon">Orizon</span><span
    class="wm-manager">Manager</span></span>` → `<span class="lb-wm">Orizon <span
    class="wm-one">One</span></span>`
  - Formulário (ids, placeholders, `autocomplete`, botão "Entrar", `#loginErro`, `.login-foot`
    com "Esqueci minha senha" / "Fale com o suporte") — **sem mudanças**, já está idêntico ao
    mockup.
- Adicionar depois do `.login-card`, ainda dentro de `.login-grid`:
  ```html
  <p class="login-hint">Administra mais de uma loja? Escolha qual está acessando logo depois de entrar.</p>
  ```

### 13. HTML — footer

- `© 2026 Orizon Manager. Todos os direitos reservados.` → `© 2026 Orizon One. Todos os
  direitos reservados.`
- `.footer-links`: `Processo/Financeiro/Entrar` → `Etapas/Gestão/Entrar` (mesmos `href`s:
  `#processo`, `#financeiro`, `#entrar` — só o texto do link muda)

### 14. `<script>`

Sem mudanças — conferido que o bloco é idêntico nos dois arquivos (toggle de tema +
`POST /api/auth/login` com `credentials:'same-origin'`, redireciona pra `/` no sucesso).

## Integração com o restante do projeto

É uma alteração isolada em `static/login.html` — não mexe em rotas de backend, não muda o
contrato de `/api/auth/login`, não afeta o painel autenticado (`static/index.html`). O único
ponto de atenção é o design system compartilhado: `design-system/orizon-tokens.css` já está na
v1.7 (confirmado), então não há necessidade de tocar nele nesta rodada.

## Fora de escopo nesta rodada

- **`design-system/marca/REGRAS_MARCA.md`** — a spec da Juliana (seção 5) flagra que os
  comentários de CSS em `static/login.html` referenciam explicitamente as regras de lockup
  "glifo + wordmark Manager" (REGRAS_MARCA §5/§6). Com a marca virando "Orizon One" e o lockup
  ficando de uma linha só, esse documento provavelmente precisa de uma revisão própria — não
  faz parte deste checklist, é um follow-up separado (perguntar ao Marcelo antes de editar
  REGRAS_MARCA.md).
- Qualquer outra página que também use o lockup "Orizon Manager" (painel autenticado,
  `static/index.html`, etc.) — esta rodada é só a landing/login pública.

## Verificação sugerida

1. Abrir `/login` nos dois temas (claro/escuro) e conferir visualmente contra o mockup
   (`mockups/landing-proposta-v2.html`) lado a lado.
2. Testar o toggle de tema e o submit do formulário (login real) — nenhum dos dois deveria ter
   mudado de comportamento.
3. Testar responsivo (`max-width: 860px` e `max-width: 760px`) — a régua de 7 colunas cai para 2
   colunas, `.split` empilha, `.nav-links` some (sem mudança nesses breakpoints).
4. Conferir que não sobrou nenhuma referência a "Manager" na página renderizada (title, nav,
   login-card, footer) nem no `aria-label`.
