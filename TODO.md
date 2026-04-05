# TODO

Itens pendentes em ordem de prioridade. Atualize conforme avança.

## Em aberto

### P1 — Habilitar billing Google AI Studio
Free tier limita a 20 req/dia para `gemini-2.5-flash`. Cada turno consome 2-3 chamadas.
Após habilitar: validar multi-turn, `list_events` em todas as agendas e `create_calendar` em produção.
- URL: https://aistudio.google.com → Get API key → Enable billing

### P2 — Testar ClickUp em produção
Tools implementadas desde Fase 2, nunca validadas no ambiente de produção.
Testar: `list_tasks`, `create_task`, `update_task`, `get_task_details`.

### P3 — Unificar classify_intent + plan_action para intents simples
Atualmente cada turno faz 2-3 chamadas ao LLM (classify → plan → format).
Para intents simples (`general_chat`, `query_calendar`, `query_tasks`), o classify pode ser
eliminado — plan_action já tem contexto suficiente para decidir sem passo separado.
Requer cuidado com o roteamento do grafo (classify também serve para decidir edges).
**Discutir abordagem antes de implementar.**

## Ideias / backlog

- Roteamento para LLM local via Ollama (RX 9070 XT) — Fase 5 do CLAUDE.md
- Suporte a múltiplos usuários (hoje `user_id` existe mas não há isolamento real de contexto)
- Interface web mínima para visualizar reminders e histórico
