# Orientação para Claude Code — Ciclo interno em formato "Fichário"

**Frente:** redesign visual/interação da tela de Ciclo do Projeto (etapas 1–21).
**Branch:** nova branch separada (`feat/ciclo-fichario` ou similar) — frente independente das
duas já em andamento (eliminação do chat legado + fila de triagem). Não depende delas e elas não
dependem desta; pode rodar em paralelo, mas evite abrir/mergear as duas frentes no mesmo dia sem
sincronizar — ambas tocam o mesmo `static/index.html` monolítico (regiões de código diferentes,
mas mesmo arquivo, o que facilita conflito de merge se rodarem juntas sem cuidado).

**Escopo:** só o Ciclo INTERNO por projeto (`renderCiclo()` / `ETAPAS_CICLO`). Não é o Funil
cross-project — não mexer em nada relacionado a funil/pipeline entre projetos.

---

## 0. O que NÃO muda (não-objetivos)

Isto é puramente um redesign de **apresentação e navegação**. Nenhuma regra de negócio muda:

- `mod_ciclo.py` **não é alterado**: `ETAPAS_PRINCIPAIS`, `STATUS_CONCLUSIVOS`, `pode_avancar()`,
  `etapa_anterior()`/`etapa_seguinte()`, `SUBFASES_PE`, `ETAPAS_OPERACIONAIS`,
  `ETAPAS_APROVACAO_FINANCEIRA`, `FAIXA_POR_ETAPA`, `codigos_a_resetar()`,
  `reabertura_bloqueada_por_contrato()` — tudo isso continua exatamente como está.
- `database.py::CicloEtapa` **não muda** (nenhuma coluna nova, nenhuma migração).
- Os endpoints de backend do ciclo **não mudam**.
- **Sem drag-and-drop livre.** Navegação é só por clique. A ordem/gating sequencial das etapas
  continua 100% definida pelo backend (`pode_avancar`), igual hoje.
- As funções `_renderCard*` que já existem (`_renderCardContrato`, `_renderCardConciliacaoFinal`,
  `_renderCardAprovacaoFinanceira`, `_renderCardSolicitacaoMedicao`, `_renderCardMedicao`,
  `_renderCardPE`, `_renderCardImplantacao`, `_renderCardProducao`, `_renderCardEntrega`,
  `_renderCardEmissaoNfe`, `_renderCardGenerico`) continuam sendo a fonte da lógica/conteúdo de
  cada etapa — elas só passam a ser chamadas de um lugar diferente (a "tela cheia" da etapa
  selecionada, em vez de dentro de um card de acordeão).

## 1. Estado atual (para não redescobrir)

Hoje (`static/index.html`):

- `ETAPAS_CICLO` (linha ~12356): array com `{codigo, nome, sub, acao?, toggleavel?}` — 24 entradas
  (etapas principais 1–21 + sub-etapas `11a`..`11e`, `17a`). Já espelha `mod_ciclo.py`.
- `ETAPAS_PRINCIPAIS` / `STATUS_CONCLUSIVOS` (linha ~12385) — cópia JS das constantes do backend.
- `_etapaBloqueada(codigo)` (linha ~12391) — já calcula se a etapa está travada pela anterior não
  concluída (recursivo para sub-etapas, que herdam o bloqueio da mãe).
- `renderCiclo()` (linha ~13537) — monta a lista vertical de cards em acordeão, um por etapa,
  usando `document.createElement`/`innerHTML`. Cada card tem: indicador de status
  (`.ind-conclusao`), nome, label de cronograma, e corpo (`_renderCard*` conforme o tipo de etapa).
  No topo do painel, uma barra fixa com os botões: Grupo de Acompanhamento, Equipe, Cronograma,
  Auditoria Contábil, Mapa de Atribuições, Retenção por Obra (só aparecem se `projetoAtivo`).
- `toggleCicloCard(codigo)` (linha ~13617) — abre/fecha o acordeão; dispara carregamento sob
  demanda para a etapa 7 (dados do contrato) e 11e (complemento do PE).
- **Status já é um modelo de 3 estados**, só que hoje representado com UMA cor (`--accent`) em
  dois tratamentos + neutro:
  - `.ind-conclusao.pendente` (linha 208-212 do CSS): borda `--border`, sem preenchimento —
    "não iniciada"/bloqueada.
  - `.ind-conclusao.andamento`: borda `--accent`, sem preenchimento — "em andamento".
  - `.ind-conclusao.feito`: fundo `--accent` cheio + ícone de check — "concluída".
  Isso muda no fichário (ver seção 3): passamos a usar três tokens semânticos diferentes, não
  duas variações do mesmo `--accent`. Isso é uma decisão deliberada, registrar no commit/DEV_LOG.
- **Etapas "puláveis"** (`toggleavel: true` em `ETAPAS_CICLO`: `9`, `11b`, `16`, `17`, `17a`, `18`,
  `19`, `20`) — hoje, dentro de `_renderCardGenerico` (linha ~14009), aparece um botão
  "✓ Marcar como Concluída" / "↺ Reabrir" (`toggleSalvarEtapa(codigo)`) quando a etapa não tem
  ação/documento concreto. **Esse mecanismo não muda** — só se realoca para dentro da view de
  tela-cheia da etapa (confirmado com o Marcelo: "segue o mesmo padrão de fechamento" — não criar
  um sinal visual novo na aba da lombada para isso).
- `_renderCardGenerico` também já tem o botão "Reabrir (gerente)" para etapas principais já
  concluídas (`abrirModalReabrir`) — mantém como está, só relocalizado.

## 2. Design tokens a usar (`design-system/orizon-tokens.css`)

**Regra inegociável do projeto (comentário no topo do arquivo de tokens): nenhuma cor em hex
literal no componente — sempre `var(--token)`.** Os três estados do fichário usam tokens
semânticos que já existem (não inventar cor nova):

| Status         | Cor principal | Fundo suave    | Borda/linha    |
|----------------|---------------|----------------|-----------------|
| Não iniciada   | `var(--text-3)` | `var(--surface-2)` | `var(--border-strong)` |
| Em andamento   | `var(--info)`   | `var(--info-soft)` | `var(--info-line)`     |
| Concluída      | `var(--ok)`     | `var(--ok-soft)`   | `var(--ok-line)`       |

Esses seis tokens (`--text-3`, `--surface-2`, `--border-strong`, `--info`, `--info-soft`,
`--info-line`, `--ok`, `--ok-soft`, `--ok-line`) já existem em **ambos os temas** (claro e
escuro) em `design-system/orizon-tokens.css` — não precisa criar nada, só usar. Validei
visualmente num mockup com as cores reais do projeto nos dois temas antes de escrever esta
orientação; o Marcelo aprovou.

Isso é uma mudança de convenção em relação ao `.ind-conclusao` atual (que usa só `--accent` em
dois tratamentos). Ao implementar, pode manter `.ind-conclusao` como está (é usado em outros
lugares do app, não só no ciclo) e criar classes novas específicas do fichário
(ex. `.ficha-tab.st-nao_iniciada/.st-andamento/.st-concluida`) — não reaproveitar/alterar
`.ind-conclusao` para não afetar outras telas que dependem dele.

## 3. Novo design: lombada + tela cheia

### 3.1 Estrutura geral

Substituir a lista vertical de cards em acordeão por duas áreas lado a lado dentro do painel do
ciclo:

- **Lombada** (coluna fixa à esquerda, ~260-280px): uma aba por etapa PRINCIPAL (as 19 de
  `ETAPAS_PRINCIPAIS`), na ordem canônica. Cada aba mostra `codigo · nome` e um indicador de
  status colorido conforme a tabela da seção 2. Clique numa aba seleciona aquela etapa.
- **Conteúdo** (resto da largura): mostra em tela cheia a etapa selecionada — cabeçalho (badge de
  status + nome), e o corpo, que é exatamente o que `_renderCard*` já produz para aquela etapa,
  só que ocupando a área inteira em vez de dentro de um card recolhido.
- A **barra de ações do projeto** (Grupo de Acompanhamento, Equipe, Cronograma, Auditoria
  Contábil, Mapa de Atribuições, Retenção por Obra) fica **fixa acima de lombada+conteúdo**,
  igual hoje, independente de qual etapa está selecionada.

Estado de seleção: variável JS nova (ex. `_cicloEtapaAtiva`), inicializada por padrão na etapa
"atual" do projeto (a primeira não concluída na ordem — equivalente a "onde o projeto está agora";
dá para calcular como a primeira de `ETAPAS_PRINCIPAIS` cujo status não está em
`STATUS_CONCLUSIVOS`, ou a última se todas concluídas).

### 3.2 Cálculo do status de exibição por etapa

Reaproveitar a lógica que já existe, só reclassificando em 3 buckets em vez de 4 palavras
distintas:

```js
function _statusFichario(codigo) {
  const dados = _cicloData[codigo] || {};
  if (STATUS_CONCLUSIVOS.has(dados.status)) return 'concluida';
  if (_etapaBloqueada(codigo)) return 'nao_iniciada';
  return 'andamento';   // desbloqueada, ainda sem status conclusivo
}
```

(Sub-etapas usam a mesma função — `_etapaBloqueada` já lida com a recursão para o pai.)

### 3.3 Sub-etapas (`11a`–`11e`, `17a`)

**Não** viram abas de primeiro nível na lombada (eram 19 principais; promover as sub-etapas
deixaria a lombada com ~24 itens, poluída). Em vez disso: quando a etapa-mãe (`11` ou `17`) está
selecionada, mostrar uma tira de sub-abas **dentro da área de conteúdo**, acima do corpo da etapa
— um "mini-fichário" aninhado. Clicar numa sub-aba troca o conteúdo para aquela sub-etapa
especificamente (reaproveitando `_renderCardPE` para `11a`-`11e`, o card genérico ou dedicado para
`17a`). A cor de cada sub-aba segue a mesma tabela de 3 estados.

Isso foi validado no mockup (etapa `11` selecionada mostra `11a` concluída, `11b` em andamento,
`11c`/`11d`/`11e` não iniciadas, todas como sub-abas dentro da tela da etapa 11) e aprovado.

### 3.4 Etapa futura selecionada → placeholder "Etapa não iniciada"

Abas de etapas com status `nao_iniciada` continuam **clicáveis** (não desabilitadas) — ao
selecionar, a área de conteúdo mostra um placeholder central, sem o formulário/ação real da etapa:

> 🔒 **Etapa não iniciada**
> Esta etapa é liberada automaticamente quando a etapa anterior do ciclo é concluída. Nenhuma
> ação disponível ainda.

Não chamar o `_renderCard*` correspondente nesse caso — evita expor botões/campos de uma etapa
ainda travada. (Isso é consistente com o `bloqueada` que os `_renderCard*` já recebem como
parâmetro hoje, mas em vez de renderizar o card com o aviso de bloqueio no topo como hoje, o
fichário troca o card inteiro pelo placeholder.)

### 3.5 Etapa em andamento / concluída selecionada → tela cheia com `_renderCard*`

Para etapas com status `andamento` ou `concluida`, a área de conteúdo chama exatamente a mesma
função `_renderCard*` que já existe para aquele `etapa.codigo` (o `switch` que já está em
`renderCiclo()`, linhas ~13584-13604, só que aplicado a UMA etapa por vez, na área de tela cheia,
em vez de dentro de um card recolhido no loop). Para etapas concluídas, adicionar acima do card a
faixa "✓ Concluída em DD/MM/AAAA" que já existe em alguns `_renderCard*` (ex.
`_renderCardConciliacaoFinal`) — padronizar essa faixa para todas as etapas concluídas, se ainda
não for uniforme.

## 4. O que preservar sem exceção

- `toggleCicloCard`'s efeitos colaterais de carregamento sob demanda (dados do contrato na 7,
  complemento do PE na 11e) — devem continuar disparando quando a respectiva etapa/sub-etapa é
  selecionada no fichário (equivalente a "abrir o card").
- O botão "Reabrir (gerente)" (`abrirModalReabrir`) nas etapas principais já concluídas.
- O mecanismo de etapas puláveis (`toggleSalvarEtapa`, botão "Marcar como Concluída"/"Reabrir")
  nas etapas com `toggleavel: true` — sem mudança de comportamento, só de local visual.
- Todos os labels de cronograma (`_cronoLabelEtapa`, `_cronoRespBlock`), o indicador de progresso
  do PE (`_renderEtapa11Progress`), e a tag "com a bola" (`_tagComABola`) — continuam aparecendo,
  reposicionados conforme fizer sentido no novo layout (cronograma pode ficar ao lado do nome na
  aba da lombada, ou no cabeçalho do conteúdo — critério de vocês, mas não pode desaparecer).

## 5. Plano de execução sugerido

1. Criar a branch.
2. Implementar a lombada (HTML/CSS) + função de seleção, com os 3 status calculados via
   `_statusFichario()`.
3. Implementar a área de conteúdo em tela cheia, reaproveitando o `switch` de `_renderCard*` que
   já existe — mover, não reescrever a lógica de cada etapa.
4. Sub-abas de `11` e `17`.
5. Placeholder de etapa não iniciada.
6. Testar manualmente nos dois temas (claro/escuro) — `node --check` no `<script>` extraído para
   sintaxe, e verificação visual real no navegador (não há teste JS automatizado no projeto).
   Vale chamar a Vera para o fluxo de telas + consistência de tema claro/escuro antes de fechar.
7. Testar especificamente: projeto no início (etapa 1 em andamento, resto não iniciado), projeto
   no meio (com sub-etapas do PE em estados variados, como no mockup), projeto concluído (etapa 21
   concluída, todas as anteriores concluídas), e uma etapa reaberta pelo gerente (deve voltar a
   aparecer como "em andamento" na lombada, e tudo posterior deve voltar a "não iniciada" — a
   cascata de `codigos_a_resetar` já faz isso no backend, só confirmar que o front reflete certo).
8. Fechar a frente no padrão do projeto (suíte verde — não deve haver teste de backend afetado,
   já que nada em Python muda; atualizar DEV_LOG com a decisão de design + os 3 tokens de cor
   escolhidos; commit; merge; push; re-ingerir o grafo MCP).

## 6. Referência visual

Mockup interativo e documentado em
`docs/superpowers/specs/ciclo/2026-08-01-ciclo-fichario-mockup.html` (HTML standalone, dados
fake, sem backend — abrir direto no navegador). Já foi aprovado pelo Marcelo nos dois temas.
Tem um cabeçalho de documentação no próprio código-fonte e um painel "ℹ️ Notas de design"
clicável na página (mapeamento cor→token, decisões confirmadas, não-objetivos) — use como
referência de estrutura/interação (lombada + abas coloridas + sub-abas da 11 + placeholder de
etapa futura). Os valores de cor exatos a usar em produção são os tokens da seção 2 deste spec;
o mockup usa os hex literais dos tokens só para poder rodar standalone sem carregar o CSS do
projeto — no código de produção use sempre `var(--token)`, nunca hex.
