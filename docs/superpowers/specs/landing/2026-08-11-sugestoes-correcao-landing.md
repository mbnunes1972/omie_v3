# Sugestões de correção — Landing / Login (Orizon)

Consolidação do feedback escrito + anotações do `Site 1.png`, cruzados com o HTML
que está no ar em `http://167.88.33.121:8766/login` (referências de linha abaixo
são desse HTML). Mockup com tudo aplicado: `landing-proposta-v2.html`.

---

## 1. Título do hero (H1) — linha 289

| | |
|---|---|
| **Hoje** | `Da venda ao balanço, um só sistema.` |
| **Proposta** | `Da venda ao resultado, um só sistema.` |

**Por quê:** "balanço" + ícone de balança passa ideia restrita de contabilidade /
balanço patrimonial. O destino prometido é mais amplo: resultado e visão
financeira do projeto. "Resultado" também conversa com o card "Gestão
Financeira" ("Margem real, por projeto, desde o primeiro dia").

**Atenção:** manter "Balanço" na seção `#financeiro` ("...o que vira DRE,
Balanço e margem por projeto") — lá o termo é o demonstrativo contábil de
verdade. A troca é só no hero.

## 2. Eyebrow do hero — linha 288

| | |
|---|---|
| **Hoje** | `GESTÃO PARA REDES DE MÓVEIS PLANEJADOS` |
| **Proposta** | `GESTÃO PARA REDES MULTI-LOJA DE MÓVEIS PLANEJADOS` |

**Por quê:** sobe a ideia de "feito para redes multi-loja" (hoje escondida na
nota pequena sob os CTAs) para o topo da hierarquia. Alternativas do feedback:
`GESTÃO PARA REDES MULTI-LOJA` (mais curta) ou
`GESTÃO INTEGRADA PARA REDES DE MÓVEIS PLANEJADOS` (mais genérica).

A nota sob os CTAs (linha 300) fica só com o complemento:
`Cada loja com seu escopo, a rede com visão consolidada.`

## 3. Lede do hero — linhas 290–293

| | |
|---|---|
| **Hoje** | "Orizon Manager conecta captação, projeto, produção e entrega às suas provisões, DRE e margem por projeto — sem planilha paralela e sem depender de dois sistemas que nunca batem." |
| **Proposta** | "O Orizon One conecta toda operação à gestão financeira do seu negócio." + parágrafo curto: "Sem planilhas paralelas. Sem dados desencontrados. Sem informações espalhadas entre diferentes sistemas." *(v2.4 — versão longa com "captação, projeto, produção e entrega... provisões, DRE e margem" foi enxugada; o detalhe já aparece na régua de etapas e nos cards)* |

O print também traz a frase *"Tudo configurado para refletir a realidade e os
processos do seu negócio."* — opcional; no mockup ela **não** entrou no hero
para não alongar o bloco (candidata natural à seção de login ou ao card de
Processo).

## 4. Gráfico do hero (SVG) — linhas 304–323

| | |
|---|---|
| **Hoje** | 3 pontos (`venda`, `produção`, `balanço`) e ícone de **balança** no topo |
| **Proposta** | 5 pontos — `venda → projeto → produção → entrega → resultado` — e, no último ponto, **mini indicador de margem** (barras ascendentes em cobre) no lugar da balança |

**Por quê:** o gráfico passa a contar exatamente a história que o texto acabou
de prometer; o leitor lê o fluxo e o vê desenhado. As 4 linhas de grade que já
existem no SVG acomodam bem os 5 pontos.

**Decisão (27/07/2026, v2.5):** o gráfico espelha **exatamente as 7 etapas da
régua** — `captação → vendas → projetos → produção → montagem → assistências →
resultado`. A versão intermediária de 5 pontos começando em `venda` foi
descartada. (Etapa 04 abreviada para `produção` no gráfico por espaço.)

**Redesenho (27/07/2026, v2.6): trilha serpentina.** A curva ascendente era
linguagem de gráfico de dados — sugeria que uma etapa "vale mais" que a
anterior. Como o desenho agora representa literalmente as etapas, virou um
**caminho que serpenteia em 3 linhas** (lê como texto: esquerda→direita, desce,
volta), terminando no resultado preenchido em cobre com o indicador de margem
acima. Sem linhas de grade — não é gráfico, é jornada.

**Refino (v2.7):** a trilha ficou **só com os números `1–7`** — os nomes das
etapas saíram para não repetir a régua logo abaixo. Hero mostra a forma da
jornada; a régua explica cada parada.

**Refino (v2.9):** a **régua também perdeu o zero à esquerda** (`1–7` em vez
de `01–07`) — o zero era maneirismo tipográfico sem função; com a trilha já em
`1–7`, a numeração unificada é mais coerente. A diferença entre os dois
elementos está na forma, não no estilo do número.

## 5. Marca: remover "Manager" (anotação do print)

O risco laranja sobre "Manager" no logo e no texto indica que a marca passa a
ser só **Orizon**. Pontos de impacto no HTML:

- [ ] `<title>` (linha 6): `Orizon — Gestão para redes de móveis planejados`
- [ ] Wordmark do nav (linhas 260–268): remover `<span class="wm-manager">`
- [ ] Lockup vertical do card de login (linhas 430–438): idem
- [ ] `aria-label="Orizon Manager"` (nav e login) → `"Orizon"`
- [ ] Texto do lede: "O Orizon conecta..." (sem Manager)
- [ ] Footer (linha 463): `© 2026 Orizon`
- [ ] **Fora do HTML:** REGRAS_MARCA / assets de lockup precisam ser revisados
      — os comentários no CSS referenciam lockups "glifo + wordmark Manager"

**Atualização (27/07/2026): o nome do sistema é _Orizon One_.** Onde o
checklist acima diz só "Orizon", usar **Orizon One** — title, wordmark do nav e
do login (com "One" em cobre), aria-labels, lede ("O Orizon One conecta...") e
footer ("© 2026 Orizon One").

## 6. Espaçamento vertical (anotação do print)

*"Diminuir espaços verticais para não quebrar seções"* — na captura, a seção
"Do primeiro contato..." aparece cortada na dobra.

| Regra | Hoje | Proposta |
|---|---|---|
| `section { padding }` | `88px 24px` | `64px 24px` |
| `.hero { padding }` | `96px 24px 40px` | `64px 24px 32px` |
| `.process-head { margin-bottom }` | `56px` | `40px` |
| `.split { margin-top }` | `56px` | `40px` |
| `.app-teaser { margin-top }` | `64px` | `48px` |

## 7. Régua "Uma jornada, ponta a ponta": adicionar 07 · Resultado

**Problema:** gráfico do hero e régua de etapas contavam quase a mesma história,
e a régua parava em `06 · Assistências` — sem chegar ao resultado que o H1
promete.

**Decisão (27/07/2026):** manter os dois, com papéis distintos —

- **Gráfico do hero** = resumo visual da promessa (5 pontos);
- **Régua** = detalhe operacional, agora com a etapa final
  `07 · Resultado — Margem real por projeto, DRE fechado`, destacada em cobre
  (o destaque de última etapa já existente migra do 06 para o 07).

Ajuste técnico: `.process-steps` passa de 6 para 7 colunas (`gap` 16→14px).

**Refinos (v2.2):**

- A linha horizontal da régua **termina na bola do 07** — resultado é o ponto
  final, a linha não segue até a borda (`right: calc((100% - 84px)/7 - 19px)`).
- H2 da seção: `Do primeiro contato à assistência pós-venda` →
  `Sete etapas, do primeiro contato ao resultado` — o título antigo parava
  numa etapa intermediária da jornada.
- Sub-texto de Projetos: `Medição, projeto executivo, corte` →
  `Medição, projeto executivo, plano de corte` → (v2.9) **`Medição e projeto
  executivo`** (plano de corte saiu).
- Sub-texto de Assistências (v2.9): `Loja, fábrica ou cliente — cada custo no
  seu lugar` → **`Atendimento pós-venda, custo por responsável`**.
- Sub-texto de Resultado (v2.9): `Margem real por projeto, DRE fechado` →
  **`Margem real por projeto`**.
- **Padrão de pontuação:** títulos-frase (H1 e H2 de seção) terminam com
  ponto final — "um só sistema.", "Sete etapas, do primeiro contato ao
  resultado.", "...conectados pela mesma informação." Rótulos nominais (nomes
  de card, "Entrar") ficam sem ponto.
- H2 da seção `#financeiro`: `Processo e financeiro...` →
  **`Operação e financeiro conectados pela mesma informação.`** (v2.8; a
  intermediária "alimentados pelos mesmos dados" foi substituída — "conectados"
  ecoa o verbo do hero, consistência de voz), e o card `Gestão de Processo` →
  **`Gestão da Operação`**. Decisão (27/07/2026): "processo" era amplo demais e
  "produção" estreito demais (o card cobre captação, venda e expedição);
  "operação" cobre a jornada inteira e é o termo que o próprio texto da seção
  já usava.
- **Teaser do app removido** ("Em breve, no seu bolso" + badge iOS/Android) —
  saiu o bloco, o link "App" do menu e o CSS associado.

## 8. Seção de login enxuta (v2.3)

**Problema:** a seção `#entrar` tinha uma segunda dobra de marketing (eyebrow
"Acesso" + H2 "Sua operação, sua conta, seu painel" + parágrafo) — redundante,
já que o visitante chega ali clicando em "Entrar" no nav.

**Decisão:** só o card de login, centralizado (max-width 420px). A única
informação útil daquele texto virou uma nota curta sob o card:
*"Administra mais de uma loja? Escolha qual está acessando logo depois de
entrar."*

**Decisão (27/07/2026):** o card no fim **permanece** — "Entrar" (nav) e
"Acessar minha conta" (hero) são âncoras que rolam até ele; é o único
formulário da página (que é a própria `/login`). Alternativa de modal foi
considerada e descartada por ora.

**Menu e rodapé (v2.3):** link `Processo` → **`Etapas`** — espelha o título da
seção de destino e evita colidir com "Gestão da Operação" da seção do
financeiro. (Link "App" já havia sido removido junto com o teaser.)

**Menu e rodapé (v2.9):** link `Financeiro` → **`Gestão`** — a seção de
destino apresenta os dois lados (Gestão da Operação + Gestão Financeira);
"Financeiro" era fechado demais. "Gestão" é o termo comum aos dois cards.
Menu final: `Etapas · Gestão · Entrar`.

**CTAs do hero (v2.4 → v2.5):** primeiro os rótulos foram unificados com o nav
(`Acessar minha conta` → `Entrar`, `Ver como funciona` → `Ver as etapas`);
depois os botões foram **removidos de vez** — o cabeçalho é fixo (sticky),
então "Entrar" e "Etapas" ficam sempre visíveis durante a rolagem, e os CTAs do
hero eram redundantes. A nota sob os CTAs ("Cada loja com seu escopo, a rede
com visão consolidada") também foi **excluída** — o eyebrow multi-loja e o
card da Operação já cobrem a ideia.

## 9. Copy dos cards mais profissional (v2.7)

Registro mais formal, mantendo o concreto de cada bullet:

**Gestão da Operação** — tag: `Cada venda, do jeito certo, sempre` →
`Cada venda conduzida no padrão da rede`

- `Ciclo com etapas e aprovações claras — nunca perde o fio de uma venda` →
  `Ciclo de venda com etapas e aprovações definidas, do primeiro contato à conclusão`
- `Captação, projeto, produção e expedição em um só lugar, não em três sistemas` →
  `Captação, projeto, produção e expedição integrados em uma única plataforma`
- `Times sabem onde cada pedido está, sem perguntar no grupo` →
  `Status de cada pedido visível para toda a equipe, em tempo real`
- `Rede com várias lojas, cada uma com seu escopo — visão consolidada...` →
  `Permissões por loja e visão consolidada da rede para quem administra`

**Gestão Financeira** — tag sem a vírgula: `Margem real por projeto, desde o
primeiro dia`

- `DRE e Balanço nascem dos mesmos lançamentos que a operação já gera` →
  `DRE e Balanço gerados a partir dos lançamentos que a operação registra`
- `Assistências classificadas por quem paga — cliente, loja ou fábrica` →
  `Custo de cada assistência atribuído ao responsável — cliente, loja ou fábrica`
- Demais bullets mantidos (já estavam em registro profissional).

**Layout (v2.8):** ícone e título dos cards lado a lado (antes empilhados) —
novo wrapper `.card-head` em flex, tag logo abaixo do conjunto.

## 10. Coerência final do conjunto

Com tudo aplicado, a leitura do hero vira exatamente a cadeia que o feedback
descreve: **quem é o cliente** (eyebrow multi-loja) → **promessa** (da venda ao
resultado) → **explicação** (lede) → **representação visual da jornada**
(gráfico de 5 pontos) → **CTA**.

---

*Arquivo gerado em 27/07/2026 a partir da análise da página no ar, do feedback
escrito e das anotações de `Site 1.png`.*
