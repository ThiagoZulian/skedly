# Handoff — Fase 4 (Proatividade)

## Estado atual
- Fases 1, 2 e 3 completas. 101 testes passando, ruff limpo.
- Último commit: `ef39862` — "feat: Phase 3 complete"

## O que fazer

Implementar Fase 4 do CLAUDE.md sem parar entre etapas, commit ao final de cada uma:

### Etapa 1 — Briefing diário (cron fixo)
- Criar `src/scheduler/jobs.py` → função `send_daily_briefing(chat_id)`
  - Chama `list_events` (próximos 7 dias) + `list_tasks` + `get_current_datetime`
  - Monta texto com `prompts/daily_briefing.md` via Gemini Flash
  - Envia via Telegram Bot API
- Registrar job no `src/scheduler/setup.py` → cron diário (hora configurável via env `BRIEFING_HOUR`, default `8`)
- Adicionar `TELEGRAM_CHAT_ID` e `BRIEFING_HOUR` ao `src/config/settings.py`

### Etapa 2 — Alerta de deadlines (cron fixo)
- Função `check_deadlines(chat_id)` em `src/scheduler/jobs.py`
  - Busca tarefas ClickUp com due date nos próximos N dias (`DEADLINE_ALERT_DAYS`, default `2`)
  - Envia alerta via Telegram se houver tarefas próximas
- Registrar cron diário (mesma hora do briefing ou configurável)

### Etapa 3 — Lembretes dinâmicos (já implementado, validar)
- `src/tools/reminders.py` já cria jobs APScheduler em runtime
- Verificar que `send_reminder_job` em `src/scheduler/jobs.py` envia pro `chat_id` correto
- Garantir que o `chat_id` é salvo em `UserPreference` quando usuário manda primeira mensagem
  - Adicionar em `src/gateway/routes/telegram.py`: após extrair `chat_id`, chamar `set_preference(user_id, "chat_id", str(chat_id))`

### Etapa 4 — Testes + commit
- Mockar APScheduler e Telegram API
- `tests/test_scheduler/test_jobs.py`
- Commit: `feat: Phase 4 complete — proactive briefing, deadline alerts, dynamic reminders`

## Regras
- Sem chamadas reais a APIs externas — tudo mockado nos testes
- Type hints em tudo, async/await, sem hardcode de secrets
- Commit ao final de cada etapa
- Não deletar CLAUDE.md

## Arquivos-chave
- `src/scheduler/jobs.py` — adicionar funções de briefing e deadline
- `src/scheduler/setup.py` — registrar os cron jobs
- `src/config/settings.py` — adicionar `TELEGRAM_CHAT_ID`, `BRIEFING_HOUR`, `DEADLINE_ALERT_DAYS`
- `src/gateway/routes/telegram.py` — persistir chat_id na primeira mensagem
- `prompts/daily_briefing.md` — já existe, usar como template
