# Revisão de navegação — achados verificados ao vivo

**Data:** 2026-08-26
**Ambiente:** localhost:8765, usuário `QA Navegação` (master), loja INSPIRIUM
**Método:** navegação clicada no Edge (Claude in Chrome), com medições no DOM e na Performance API.
**Repo no momento da revisão:** `26714a7`
**Projetos criados para o teste:** `NAV_QA_P1 2026-08-26`, `NAV_QA_P2 2026-08-26` (cliente `Cliente NAV_QA P1`)

> Nota de método: não foi possível usar Playwright. O contêiner do Claude não alcança o
> `localhost` da máquina do Marcelo; a navegação foi clicada de verdade pela extensão no Edge.

Ordenado por gravidade. Cada item traz **como reproduzir** e **a evidência medida**.

---

## P0-1 · Toda data “só-data” é exibida um dia antes — e vira mês e ano na virada

`static/index.html:20021`

```js
function _fmtDataBR(s) {
  if (!s) return '';
  const d = new Date(s);                       // ← 'YYYY-MM-DD' é parseado como UTC
  return isNaN(d) ? '' : d.toLocaleDateString('pt-BR');   // ← renderizado em UTC-3
}
```

`new Date('2026-08-26')` é meia-noite **UTC** por especificação. Em UTC−3 isso é 25/08 às 21h.

**Medido no console da própria aplicação:**

| entrada | exibido | correto |
|---|---|---|
| `2026-08-26` | **25/08/2026** | 26/08/2026 |
| `2026-09-01` | **31/08/2026** | 01/09/2026 — muda o mês |
| `2027-01-01` | **31/12/2026** | 01/01/2027 — muda o ano |
| `2026-08-26T10:00:00` | 26/08/2026 ✓ | (com hora funciona) |

**Visível hoje:** modal de Retenção → “Data da retenção: **25/08/2026** (o dia do ato)”, enquanto
`_hojeISO()` devolve corretamente `2026-08-26`.

**Alcance:** 25 chamadas de `_fmtDataBR` + ~10 ocorrências inline de
`new Date(x).toLocaleDateString('pt-BR')` com o mesmo defeito (linhas 5911, 19945, 20451, 20620,
20973, 21004, 21246, 21255, 21275, 22406). Toda data vinda de `<input type="date">`
(`liberacao_prevista`, previsões de entrega, datas de contrato) é só-data e cai nessa armadilha.

**Correção:**

```js
function _fmtDataBR(s) {
  if (!s) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s).trim());
  const d = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(s);   // só-data = local
  return isNaN(d) ? '' : d.toLocaleDateString('pt-BR');
}
```

Vale varrer os `toLocaleDateString('pt-BR')` inline e passar todos por essa função.

---

## P0-2 · Dois pollers de 45s travam o navegador por até 85 segundos

**Medido na Performance API, numa sessão de ~40 min:** 112 requisições a `/api/`,
**510 segundos acumulados**, 11 delas acima de 10s.

| rota | chamadas | pior caso | total |
|---|---|---|---|
| `/api/comunicacao/inbox` | 40 | **85,7 s** | 269 s |
| `/api/me/ciclo/pendencias` | 23 | **80,7 s** | 230 s |
| `/api/projetos` | 10 | 0,37 s | 2,1 s |
| `/api/projetos/<n>/ciclo` | 16 | 0,36 s | 3,2 s |
| `/api/projetos/<n>/retencoes` | 2 | 0,36 s | 0,7 s |
| `/api/clientes` | 5 | 0,33 s | 1,2 s |

O resto do sistema responde em **300–370 ms**. O problema está concentrado nessas duas rotas.

**Os dois timers:**
- `static/index.html:4428` — `setInterval(_meFramePoll, 45000)` → `/api/me/ciclo/pendencias`
- `static/index.html:17749` — `setInterval(ocPollBadge, 45000)` → `/api/comunicacao/inbox`

**Por que o inbox é caro** (`main.py:4433`, comentário do próprio código):

```python
# Sweep preguiçoso da triagem vencida (2026-08-05): sem job em background,
# aproveita a leitura do inbox (roda em toda carga de tela + poll de badge)
# pra materializar entradas paradas há mais de 2min
mod_chat_externo.varrer_triagem_vencida(db, loja_id)
_inbox = mod_chat.listar_inbox(db, loja_id, usuario["id"])
db.commit()
```

Um **GET que escreve**, disparado a cada 45s por aba aberta e em toda troca de tela.

**Sintoma para o usuário:** a página congela de 25 a 60 segundos. Reproduzi 4 vezes nesta sessão —
é o mesmo “parece estar parado” já relatado, e provavelmente a mesma família do
“Operacional → Montagem leva ~30s”.

**Sugestões, em ordem de custo/benefício:**
1. Tirar `varrer_triagem_vencida` do caminho do GET — job periódico próprio, ou no máximo uma vez
   a cada N minutos por loja, com guarda de tempo.
2. Fazer os dois pollers pararem com a aba em segundo plano (`document.visibilityState`).
3. Medir `listar_inbox` e `pendencias` com `EXPLAIN` — 300ms nas outras rotas sugere que o
   problema é a query/lock, não a infraestrutura.
4. Avaliar se o `ThreadingHTTPServer` está serializando: uma requisição lenta que segura
   sessão/lock põe as outras na fila, o que explica 85s num endpoint que sozinho não deveria custar isso.

---

## P1-1 · Montagem aparece CONCLUÍDA em projeto que nem começou — regressão de hoje

**Reproduz em 100% dos projetos novos.** Confirmado nos dois que criei do zero.

```
_statusFichario('17')  →  "concluida"
_cicloData['17']       →  null
```

Bolinha verde na lombada em “10 Montagem”, ao lado de Cadastro/Criação/Briefing, num projeto
que acabou de sair do Briefing.

**Causa** — `static/index.html:19496`:

```js
function _etapaSatisfeita(codigo) {
  if (STATUS_CONCLUSIVOS.has((_cicloData[codigo] || {}).status)) return true;
  const def = _fichaEtapaDef(codigo);
  return !!(def && def.toggleavel && !_cicloData[codigo]);   // ← pega a MÃE junto
}
```

`_statusFichario('17')` avalia `todas = ['17', '17a']`. A intenção era que a sub opcional `17a`
não travasse o grupo — mas a **própria** `17` é `toggleavel: true`, então as duas “satisfazem” e a
mãe vira concluída.

**Introduzido em `4c140ff` (hoje):** *“fix: triagem dos 11 achados médios da bateria E2E (rodadas 1-3)”*.

**Janela do bug:** enquanto a etapa 17 não ganha linha em `ciclo_etapas`. Em `Vera_QA_E2E7`, que já
tem a linha (`status: "pendente"`, responsável Luiz da Silva), o status sai correto. Ou seja: pega
todo projeto **antes** do contrato materializar o cronograma — Briefing, Orçamento e Contrato.

**Efeito colateral:** `_fichaEtapaAtual()` e o selo “Ciclo concluído” (`19277`) também usam
`_etapaSatisfeita`. Um projeto pode pular Montagem ao calcular a etapa atual, ou se declarar
concluído sem ela.

**Correção provável:** em `_statusFichario`, avaliar a mãe só por status e aplicar o passe
`toggleavel` apenas às subs.

---

## P1-2 · O fichário roda em um terço da tela

**Medido com a janela em 888px de altura:**

| | valor |
|---|---|
| `.content` | 820px (correto) |
| `#page-02` | **496px** — sobram **300px de tela vazia** |
| lombada | 239px para 586px de conteúdo → **6 de 15 abas visíveis** |
| card da etapa | 239px para 947px de conteúdo |

O Briefing é o pior caso: `#bf-box` tem 799px de altura declarada dentro de um container de 295px,
com **dois scrollbars aninhados**.

**Causa:** `.content` é `display:block`. O `flex:1` do `.page` filho é inerte — container block não
estica filho flex. Tudo abaixo herda o aperto.

**Correção testada por mim, no DOM da aba:**

```css
.content     { display:flex; flex-direction:column; min-height:0; overflow:hidden }
.page.active { flex:1 1 0; min-height:0 }
```

| | antes | depois |
|---|---|---|
| `#page-02` | 496px | **772px** |
| card da etapa | 239px | **515px** |
| abas visíveis | 6 de 15 | **13 de 15** |
| tela vazia | 300px | 24px |

**Ressalva:** `.content` é o container de **todas** as páginas. Precisa de regressão nas outras
telas antes de subir. Se preferir escopo menor, dá para limitar ao `#ciclo-panel`.

---

## P1-3 · Sessão única por usuário, sem aviso — e congelamento no logout

`auth/auth.py:82`, dentro do login bem-sucedido:

```python
# Invalida sessões anteriores do mesmo usuário
db.query(Sessao).filter_by(usuario_id=usuario.id, ativa=1).update({"ativa": 0})
```

Todo login novo mata as sessões ativas da conta. É política deliberada e defensável — mas **sem
nenhum aviso**, o que faz o comportamento correto parecer defeito. Foi o que nos derrubou várias
vezes hoje (duas pessoas, uma conta, dois navegadores).

Descartadas: a suíte usa banco dedicado (`tests/conftest.py:29-42`), o token dura 8h de verdade
(`SESSION_DURATION_HOURS = 8`), e não há segredo regenerado no boot.

**Decisão do Marcelo:** manter sessão única, **passar a avisar na tela** — algo como
*“Sua sessão foi encerrada porque esta conta entrou em outro dispositivo”*.

**Junto disso:** quando a sessão morre no meio de uma requisição, a página congela ~25s antes de
cair no `/login`. O `window.location.href = '/login'` (`index.html:4289`) redireciona sem abortar
as requisições pendentes.

---

## P2-1 · Três nomes e dois sistemas de numeração para a mesma etapa

Na **mesma tela** do projeto `Vera_QA_E2E7`, o código `13` aparece como:

| onde | rótulo |
|---|---|
| lombada | **9** Logística e Expedição |
| sub-abas | **13** · Visão geral |
| modal de Retenção | etapa **13 · Produção** |

Confirmado no console: `_fichaNumeroExibicao('13')` → `"9"`, `_fichaTituloGrupo('13')` →
`"Logística e Expedição"`, `_etapaRotulo('13')` → `"13 · Produção"`.

**Causa:** o render das sub-abas usa o código cru `c`, não `_fichaNumeroExibicao(c)`. E
`_etapaRotulo` usa o nome de `ETAPAS_CICLO`, não o nome do grupo.

**Relacionado — etapas 8 e 9 não têm aba.** `ETAPAS_PRINCIPAIS` vai de `"4"` para `"7"` e de
`"7"` para `"10"`; `_FICHA_SUBS` também não as adota. Consequências:

- `_fichaNumeroExibicao('9')` cai no `indexOf → -1` e devolve o **código cru**. O cabeçalho imprime
  “etapa 9 — Solicitação de medição”, e **9 na lombada é Logística e Expedição**. Quem lê o
  cabeçalho e procura a etapa 9 vai para a tela errada.
- No `Teste_0820`, `_cicloData['9'].status` é `"pendente"` — a etapa que trava o projeto — enquanto
  `_fichaEtapaAtual()` devolve `"7"` (Contrato, já concluída). **A etapa que segura o projeto não
  tem tela.**
- `_retencaoBloco` é oferecido para o código-mãe `'9'` (`index.html:19636`) — ramo que nunca executa.

Sugestão mínima: usar `_fichaNumeroExibicao` também nas sub-abas e no `_etapaRotulo`, e decidir
onde 8 e 9 vivem (hoje as ações delas estão dentro do card do Contrato, via `_FICHA_PENDENCIAS`,
mas a numeração não conta essa história).

---

## P2-2 · Cadastro de cliente: a mensagem de erro nasce fora da tela

**Reproduzir:** Novo Projeto → “+ Cadastrar novo cliente” → preencher só o Nome → Salvar.

O modal **pula para o topo** e foca o campo E-mail. Nenhuma mensagem aparece.

**Medido:** a mensagem existe (`#cli-modal-erro` = “E-mail é obrigatório.”), mas fica em
**y = 1213** numa janela de **888px** — 325px abaixo da dobra. O elemento está declarado no rodapé
do modal (`index.html:2267`), logo acima dos botões, enquanto `cliSalvar` (`12212`) dá `focus()`
num campo do topo.

**Correção:** rolar a mensagem para a vista, ou colocá-la junto do campo que falhou.

**Junto disso — os asteriscos estão nos campos errados.** `cliSalvar` valida **Nome, E-mail e
Telefone**. Na tela, só “Nome completo *” tem asterisco; E-mail e Telefone não têm. E
**“Número *”** tem asterisco e **não é validado em lugar nenhum**. CPF, que vai para contrato e
NF-e, é opcional e não teve o dígito verificador conferido no teste.

---

## P2-3 · Depois de recarregar, duas páginas ficam empilhadas

**Reproduzir:** abrir um projeto → Etapas do Projeto → recarregar a página (F5) → clicar em Projetos.

A lista de Projetos aparece **e**, logo abaixo, o fichário completo do projeto anterior continua
renderizado — cabeçalho “Etapas do Projeto”, lombada e card da etapa.

Confirmado visualmente **após um reload completo** (documento novo, sem os meus ajustes de CSS —
cheguei a suspeitar que fosse coisa minha e reproduzi limpo). Não consegui capturar o estado do
DOM porque a página congelou logo depois (ver P0-2), então a causa exata fica em aberto.

**Junto disso:** o texto do filtro de busca persiste ao recarregar, mas o campo aceita digitação
por cima — digitei “Teste_0820” e o campo ficou “Teste_0820Teste_0820”, resultando em “Nenhum
projeto encontrado” sem causa visível.

---

## P3 · Atritos menores, todos confirmados

**Briefing**
- O modal é titulado **pelo cliente**, não pelo projeto: “Briefing — Cliente NAV_QA P1”. Criei dois
  projetos para o mesmo cliente e os dois briefings têm título idêntico — não dá para saber qual
  se está preenchendo.
- **Consultor responsável é perguntado duas vezes.** No Novo Projeto é um `<select>` (escolhi
  JULIANA KAERCHER); no Briefing é um `<input type="text">` vazio (`bf-consultor`), sem
  pré-preenchimento. Além da redigitação, os dois podem divergir.
- **Escape não fecha** o modal do Briefing (outros modais fecham).
- Fechar o Briefing no X joga na **lista de projetos**, não no projeto recém-criado — que agora
  precisa ser encontrado numa lista de 37 linhas.

**Provisões**
- Nomes truncados em 199px (“Provisão de Comissão de …”, “Provisão de Custo de Fábri…”). Têm
  `title`, então o dado não se perde — mas numa tela onde se clica “Efetivar” em cima de valores,
  ter que passar o mouse para saber qual provisão é atrito real. As colunas numéricas têm folga.
- Dois botões “Efetivar” desabilitados **sem `title`** — nenhuma explicação de por que estão
  cinzas. (Outros dois explicam: “Alimentado pelo módulo Assistências…”.)

**Lista de Projetos**
- STATUS e FASE DO CICLO usam vocabulários diferentes que se sobrepõem: existe linha com
  STATUS “✓ Concluído” e FASE “Concluído”, e linha com STATUS “— Definir” e FASE “Orçamento”.
  Vale decidir se as duas colunas dizem coisas diferentes o bastante para coexistirem.

---

## O que ficou por verificar

- **Retenção ponta a ponta** (registrar → histórico → liberar): não cheguei a gravar. O defeito de
  data está provado no formatador, que é mais forte que uma instância de tela, mas a gravação em si
  não foi exercitada.
- **Provisões**: só leitura. Não cliquei em Efetivar/Resolver.
- **CPF**: não confirmei se o dígito verificador é validado. Usei um CPF inventado
  (`390.533.447-05`) e foi aceito sem reclamação — mas não olhei o código para confirmar.
- **Ciclo completo** dos projetos novos: pararam no Orçamento. Não subi XML nem fechei contrato.
- **P2-3** (páginas empilhadas): confirmado na tela, causa não isolada.
