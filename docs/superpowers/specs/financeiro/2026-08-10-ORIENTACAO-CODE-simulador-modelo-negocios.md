# ORIENTAÇÃO PARA O CODE — Simulador de Modelo de Negócios

Implementar o módulo **Simulador de Modelo de Negócios** conforme:

- **Requisitos:** `docs/superpowers/specs/financeiro/2026-08-10-simulador-modelo-negocios-requisitos.md` (rev2)
- **Design:** `docs/superpowers/specs/financeiro/2026-08-10-simulador-modelo-negocios-design.md`
- **Mockup (FONTE LITERAL do frontend):** `docs/superpowers/specs/financeiro/mockups/2026-08-10-simulador-modelo-negocios-mockup.html`

Leia os três arquivos POR INTEIRO antes de escrever qualquer código. Contexto de projeto no
`CLAUDE.md` e estado no `DEV_LOG.md` (Sessão 185 registra esta frente).

## Regras inegociáveis

1. **TDD, backend primeiro.** Siga as fases F1→F5 do design. Suíte `python3 -m pytest -q`
   sempre verde antes de cada commit (roda em Postgres — `orizon_test`).
2. **Motor puro** (`mod_simulador.py`, sem I/O — padrão `mod_indicadores`): toda a matemática da
   simulação no backend; o frontend só envia ajustes e renderiza (`POST /api/simulador/simular`).
   Nenhuma fórmula duplicada em JS.
3. **Acesso:** capability nova `acesso_simulador` em `auth/perfis.py`, concedida SÓ ao
   super_admin. Nada de `if nivel == "super_admin"` hardcoded (lição do `acesso_estrategico`,
   Sessão 181). A aba Simulador no Painel Estratégico só aparece com a capability.
4. **Autorização por loja (LGPD) — funcional, não simbólica:** tabela `simulador_autorizacoes` +
   trilha `simulador_log_acessos` (separada do log operacional), concessão via **step-up por
   senha do Master da loja** (reaproveitar o mecanismo `POST /api/auth/step-up` /
   `LogAcessoDelegado` da frente de Perfis), revogação com efeito imediato, e **seed idempotente**
   `simulador_autorizacao_seed_v1` deixando as lojas existentes autorizadas. Sem autorização
   ativa → loja bloqueada no seletor e `403` com motivo nas rotas de dados.
5. **RN-01:** "Faturamento" no módulo = **Val_Liq** (valor líquido do sistema). **RN-02:** markup
   exibido em **% adicional** (2,18× = 118%); **Markup seco** (base fábrica) e **Markup com
   frete** (base fábrica + frete fábrica); iniciam pela média da janela e **só mudam por edição
   direta** — nunca por efeito de outras variáveis.
6. **Frontend fiel ao mockup** (estrutura, medidas, tokens — copiar, não reinterpretar; lição da
   Fatia 7). Só tokens de `design-system/orizon-tokens.css`, nenhum hex novo. Verificar nos dois
   temas + `node --check` do script extraído. Mudança de frontend = Ctrl+F5; mudança Python =
   restart do servidor.
7. **Simulação é somente leitura** sobre os dados reais — nunca grava de volta (RNF-01). Divisão
   com denominador zero → `None`/"—" (padrão `_div`).
8. **Classificação:** módulos novos entram em `modulos.py` no domínio `financeiro`
   (`test_arquitetura_modulos` deve seguir verde).
9. **Fechamento (padrão do projeto):** suíte verde → DEV_LOG (nova Sessão) → commit descritivo
   pt-BR (`git add` só dos arquivos da mudança) → push → re-ingerir grafo MCP → chamar a Vera
   para o fluxo ponta a ponta (autorizar → abrir → simular → demitir consultor com trava →
   revogar → 403).

## Pendências já decididas como FORA da v1 (não implementar)

Fluxo "quais variáveis fixar" da trava de faturamento (aplicar só a redistribuição proporcional
padrão) · persistência/comparação de cenários · UI multi-segmento (`rotulos` fica só no contrato
JSON) · exportação PDF · API pública externa.
