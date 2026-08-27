# Briefing — ajustes de código após a revisão do banco (27/08/2026)

## Contexto

O banco passou por uma revisão estrutural hoje. O que mudou:

- **Alembic adotado.** Revisões `0001` (baseline vazia) a `0004` aplicadas no
  localhost. `docs/db/ESTADO_REVISAO.md` registra o estado; `docs/db/schema.sql`
  e `docs/db/ERD.mmd` são o retrato atual.
- **19 foreign keys** que só existiam no código passaram a existir no banco,
  com regras de exclusão explícitas (9 `RESTRICT`, 10 `SET NULL`).
- **94 índices** criados nas colunas filhas de FKs que não tinham.
- **`conta.centro_custo_id` agora tem FK** para `centro_custo`, com
  `ON DELETE RESTRICT`.
- As nove regras permanentes estão em `CLAUDE.md`, seção "Banco de dados".

## Regras invioláveis neste trabalho

1. **Nenhuma coluna nova pelo `_migrar_colunas_pg`.** Ele está congelado:
   atende só o que já existe. Toda mudança de schema é migration Alembic.
2. **Não renomear `conta.natureza_custo`.** Foi avaliado e descartado: são
   ~130 referências, e o nome é campo da API e do frontend.
3. **Não remover `semivariavel` da validação.** O frontend já o trata como
   legado (só oferece a contas que já o têm). Remover quebraria 8 testes
   sem ganho.
4. **Migração de schema e de dados nunca na mesma revisão.**

## Tarefas

### T1 — Congelar o `_migrar_colunas_pg` (bloqueante, 10 min)

Em `database.py`, no topo da função, comentário explicando que ela está
congelada desde 27/08/2026: mantém o que já faz, não recebe ADD COLUMN novo.
Schema novo é migration Alembic.

### T2 — Corrigir a semente e remover as reclassificações pontuais (bloqueante)

Em `mod_contabil.py`, linhas ~895-923, existem três correções que rodam a
cada boot:

    brindes:     fixo -> variavel
    ajuste:      fixo -> variavel
    combustivel: variavel -> fixo

Elas já cumpriram o papel — o banco está correto. **Corrija a semente para
nascer certo e só então apague as três.** As duas coisas no mesmo commit:
removê-las antes de arrumar a semente faz toda loja nova nascer errada.

Valores corretos, aprovados por Marcelo e Juliana:

| conta | comportamento | centro de custo |
|---|---|---|
| 5.2.06 Combustível | **fixo** | 1.4 Logística/Expedição |
| 5.3.12 Brindes | **variável** | 2.3 Marketing |
| 5.6.10 Ajustes de Reconciliação | variável | 4.5 Custos Distribuídos |

Atenção: **5.2.06 é fixo**, contrariando a proposta original que dizia
variável. A decisão prevalece sobre o documento.

### T3 — Semente da árvore de centro de custo (bloqueante)

- `1.1 Produção própria` sai da semente. A `0004` já a removeu do banco;
  se a semente ainda a criar, ela volta na próxima loja.
- `4.5 Custos Distribuídos` deve nascer em **todos** os owners. Ela existiu
  em apenas uma das três árvores por um período — foi corrigida, mas
  confirme que a semente a cria sempre.
- `5.6.10` nasce como **"Ajustes de Reconciliação"**.

### T4 — Resolução de centro de custo por código (bloqueante)

`1.3 Montagem` tem id diferente em cada owner. Qualquer lançamento automático
que grave `centro_custo_id` fixo quebra para os demais.

**Regra:** a automação resolve o centro pelo `codigo` dentro da árvore do
próprio owner, nunca por id. Varra o código atrás de ids de centro de custo
hardcoded e converta.

Corolário: códigos usados por automação ficam protegidos contra exclusão e
renumeração. O lojista pode renomear ("Montagem" -> "Instalação"), não pode
apagar o `1.3` nem trocar seu código. Implemente essa proteção na tela de
edição da árvore.

### T5 — Variância de provisão vai para a conta da despesa (importante)

Hoje a FALTA (efetivado > provisionado) cai em `5.6.10`, genérica. Isso faz
`5.2.01 Montagem` subestimar o custo real de montagem, e com 15+ provisões
num balde só não se sabe qual está mal calibrada.

**Mude para:** a variância lança na mesma conta de despesa da provisão que a
originou — o evento conhece a provisão, a provisão conhece sua conta. A SOBRA
segue o caminho inverso, creditando a mesma conta.

`5.6.10 Ajustes de Reconciliação` sobrevive apenas para diferença sem origem
identificável (arredondamento, ajuste de fechamento), nunca como destino
padrão.

**Antes de implementar, investigue e relate** como o módulo de provisões liga
provisão -> conta de despesa hoje. Se a ligação já existir, a mudança é curta.
Se não existir, proponha antes de escrever.

`lancamento.origem` já registra o evento, então a visão de variância por
provisão vira relatório — não precisa de conta nem coluna nova.

### T6 — Alertas nas contas de escape (desejável)

- `5.4.20 Outras Despesas`: notificar quando passar de **1% do custo fixo do
  mês**. Começar frouxo; apertar depois de ver o comportamento real.
- `5.6.10 Ajustes de Reconciliação`: notificar sempre que receber lançamento.

### T7 — Comentário desfazendo a ambiguidade (5 min)

Em `mod_contabil.py`, junto da definição das naturezas:

    conta.natureza        credora | devedora        (natureza CONTÁBIL)
    conta.natureza_custo  fixo | variavel | semivariavel   (COMPORTAMENTO do custo)

São coisas sem relação. O nome parecido é herança; não renomear (regra 2).

## O que verificar ao terminar

    pytest tests/ -x
    alembic current                  # deve ser 0004 (head)
    alembic downgrade 0001 && alembic upgrade head   # ciclo completo funciona
    psql "$PGURL" -c "SELECT codigo, nome, natureza_custo FROM conta
                      WHERE codigo IN ('5.2.06','5.3.12','5.6.10') ORDER BY 1;"

E relate: quais tarefas ficaram completas, quais precisaram de decisão que
você não tinha, e o que encontrou de inesperado.
