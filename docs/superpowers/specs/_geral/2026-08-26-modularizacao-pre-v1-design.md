# Modularização pré-V1 — diagnóstico medido e plano de fases

**Data:** 2026-08-26 · **Repo medido em:** `26714a7`
**Companheiro visual:** artefato publicado (mesmo conteúdo, com o mapa de módulos)

> Método: `wc -l` para linhas, `__tablename__` para tabelas, correspondência de padrão para rotas,
> e extração dos blocos `<script>`/`<style>` do `index.html` para contar funções, globais e prefixos.

---

## 1. O que JÁ é modular (melhor do que parece)

`modulos.py` (245 linhas) é um **manifesto declarativo executável**: para cada módulo declara camada
(`nucleo` | `dominio`), arquivos, tabelas, prefixos de rota, `depende_de` e se é desligável por loja.

`tests/test_arquitetura_modulos.py` é o **ratchet** que o torna real — reprova o build se um `.py`
ficar órfão, se um módulo importar fora do declarado, ou se `chat/` importar do host.

**18 módulos: 8 núcleo, 10 domínio.**

| estado | módulos |
|---|---|
| pacote extraído | `auth`, `chat`, `integracoes`, `fiscal`, (`mod_fin` dentro de comercial) |
| declarado em `mod_*.py` | `tenancy`, `escopo`, `ciclo`, `plataforma`, `cadastro`, `comercial`, `financeiro`, `folha`, `expedicao`, `assistencias` |
| fronteira reservada, sem código | `auditoria`, `captacao`, `estoque`, `montagem` |

**O padrão já provado — `chat/` é destacável:** 3.038 linhas, com `chat/ports.py` (contrato do que o
módulo precisa do host), `chat_host.py` (adaptadores), direção única host→chat, e `mod_chat.py` como
shim de 10 linhas para não quebrar imports. Feito em 31/07/2026.

**Conclusão: não há arquitetura a inventar. Há a arquitetura de vocês a aplicar ao resto.**

---

## 2. Onde está o problema

| arquivo | linhas | estado |
|---|---:|---|
| `static/index.html` | 25.043 | sem nenhuma fronteira |
| `main.py` | 18.614 | sem fronteira interna (é o SHELL declarado) |
| `mod_*.py` (40 arquivos) | 11.652 | dono declarado e testado ✓ |
| pacotes (5) | 7.039 | dono declarado e testado ✓ |
| `database.py` | 2.528 | dono declarado, código junto |
| `modulos.py` | 245 | o manifesto |

**67% do código vive em dois arquivos** (`main.py` + `index.html` = 43.657 de 65.121 linhas).

### 2.1 `index.html` — 83% é um único `<script>`

| camada | linhas | situação |
|---|---:|---|
| JS num só bloco inline | 20.682 | monólito |
| HTML (18 painéis `#page-*`) | 3.277 | costuras já existem |
| CSS inline | 1.083 | já extraído p/ `design-system/` ✓ |

Dentro do script: **1.106 funções**, **348 globais** num escopo só, **401 `fetch()`** espalhados,
**599 `onclick=`** no HTML.

**Achado que muda o plano:** contando os prefixos das 1.106 funções, **69% já carregam o prefixo do
seu módulo** — `oc` (Orizon Chat) 100, `pe` 32, `cfg` 27, `admin` 27, `neg` 26, `cli` 26, `sim` 23,
`ag`+`agenda` 35, `tf` 22, `mp` 21, `op` 21, `exp` 16, `retido` 10, `ficha` 11… Os módulos já existem
por convenção de nome; falta a fronteira.

As **344 restantes** começam com verbo genérico (`abrir`, `render`, `salvar`, `fechar`, `carregar`,
`atualizar`, `confirmar`, `aplicar`) — essas são as de fato misturadas.

### 2.2 `main.py` — 329 rotas em 4 métodos

`do_GET` (linha 1503) ≈ 4.600 linhas; `do_POST` (6133) ≈ 8.900; `do_PUT` (15035); `do_PATCH` (15703).
O manifesto já diz de quem é cada rota por prefixo — o código não segue.

**Precedente já existente:** `auth/auth_routes.py` exporta `handle_auth_get(self, path)` e
`handle_auth_post(self, path, body)`; `main.py:13` importa e chama no topo do handler, saindo fora
se a rota foi tratada. É esse padrão, replicado 17 vezes.

### 2.3 `database.py` — 82 tabelas num arquivo

Menos grave. Dono já declarado no manifesto. Trabalho mecânico, baixo risco.

---

## 3. Modelo alvo

**Regra estrutural: um dono por arquivo, nunca por assunto.** O manifesto segue sendo a fonte da
verdade; o código passa a obedecê-lo.

| hoje | alvo | fonte da verdade |
|---|---|---|
| `main.py` · 329 rotas | `rotas/<modulo>.py`; `main.py` vira compositor | `modulos.py → rotas` |
| `database.py` · 82 tabelas | `modelos/<modulo>.py`; `database.py` vira compositor | `modulos.py → tabelas` |
| `index.html` · 1 script | `static/js/<modulo>.js` (ES modules); HTML vira casca | `modulos.py → js` *(campo novo)* |
| — | `static/js/nucleo/`: fetch, sessão, toast, formatação, roteador de painéis | o que todo módulo pode importar |

### 3.1 ES modules, não bundler

O projeto não tem build; o servidor lê do disco a cada requisição e Ctrl+F5 basta.
`<script type="module">` é nativo, dá escopo por arquivo e **preserva esse ciclo**. Vite/Webpack
trocaria um problema de organização por um de infraestrutura às vésperas do lançamento.

### 3.2 A dificuldade real: os 599 `onclick=`

Módulo ES tem escopo próprio → `onclick="negSalvar()"` **para de funcionar**. É o custo escondido e
é ele que dimensiona o trabalho.

- **Ponte (durante a migração):** cada módulo extraído termina com um bloco explícito
  `window.negSalvar = negSalvar` apenas para o que o HTML chama. Feio, honesto, reversível.
- **Alvo (depois da V1):** trocar `onclick=` por `data-action="neg:salvar"` com um listener por
  painel, módulo a módulo.

---

## 4. Fases

Ordem escolhida para que cada fase entregue valor sozinha e a mais arriscada venha depois do padrão
já validado duas vezes.

### Fase 0 — Declarar antes de mover · ~1 dia · risco nenhum

Acrescentar ao `modulos.py` o campo `js` (arquivos de `static/js/` por módulo) e estender o ratchet
para checar rotas e JS **em modo advisório** (só relata). Produz um mapa executável do estado atual
antes de qualquer refatoração.

### Fase 1 — `database.py` → `modelos/` · ~2 dias · risco baixo · 2.528 linhas

Mecânico: as 82 classes já têm dono. `database.py` passa a importar todos os `modelos/*.py` para o
`Base` seguir registrando tudo — nenhum import externo muda. É o ensaio do padrão.

### Fase 2 — `main.py` → `rotas/` · ~2 semanas · risco médio · 18.614 linhas

Replicar o padrão do `auth_routes`: cada `rotas/<modulo>.py` exporta `handle_get/post/put/patch`;
`main.py` chama em cadeia no topo de cada handler.

Ordem sugerida (do mais isolado ao mais entrelaçado):
`cadastro` → `folha` → `assistencias` → `expedicao` → `fiscal` → `financeiro` → `comercial`.

**Um módulo por PR, suíte verde entre cada um.** Ao fim, `main.py` deveria caber em algumas centenas
de linhas: servidor, middleware de sessão e cadeia de despacho.

### Fase 3 — `index.html` → `static/js/` · ~3 semanas · risco alto · 20.682 linhas

**Começar por `oc` (Orizon Chat, 100 funções)** por um motivo específico: o backend do chat já é
módulo destacável com portas. Extrair o frontend dele prova o padrão nas duas pontas do mesmo módulo,
e um erro fica contido num módulo já isolado.

Depois: `admin` e `cfg` (telas de configuração, pouco acopladas) → `sim` → `ag`/`agenda` → `neg` →
`pe` → `ficha`. As 344 funções de prefixo genérico vão para `nucleo/` ou ganham prefixo de módulo na
hora da mudança — **essa é a decisão de projeto de verdade**, caso a caso.

**Total: 5 a 6 semanas**, com a suíte verde o tempo todo e nenhuma mudança de comportamento. Não é
reescrita — é mudança de endereço, com o ratchet impedindo que volte a se misturar.

---

## 5. O que NÃO fazer

**Não trocar de framework.** React/Vue resolveriam o escopo e trariam build, dependências e uma
reescrita de 20 mil linhas de JS que funcionam. ES modules resolvem 90% do problema com 5% do risco.

**Não quebrar por tela.** A tentação é `js/negociacao.js`, `js/fichario.js`, `js/provisoes.js`. Telas
se fundem e se dividem; módulos de negócio, não. Recortar pelo mesmo eixo do `modulos.py` faz as duas
pontas do sistema falarem a mesma língua.

**Não fazer tudo antes da V1.** Fases 0-2 são seguras e entregam o maior ganho (o `main.py` deixa de
ser gargalo de todo trabalho de backend). A fase 3 é a mais arriscada e a menos urgente — o
`index.html` é feio, mas funciona, e nada nele bloqueia o lançamento. **Se o calendário apertar,
corte a fase 3, não as outras.**

---

## 6. Efeito colateral que vale por si

Com `rotas/` e `static/js/` separados por módulo, **dois agentes podem trabalhar em paralelo sem
conflito** — hoje qualquer frente de frontend disputa o mesmo arquivo de 25 mil linhas.

---

## Dúvidas em aberto

Nenhuma decisão de arquitetura ficou pendente. Duas decisões de execução dependem do Marcelo:

1. **Fase 3 entra antes ou depois da V1?** A recomendação é depois.
2. **As 344 funções de prefixo genérico** — mover para `nucleo/` ou renomear com prefixo de módulo?
   A recomendação é caso a caso, decidido na hora da extração de cada módulo, não antecipadamente.
