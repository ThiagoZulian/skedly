# Handoff — Fase 5 (Hardening)

## Estado atual
- Fases 1, 2, 3 e 4 completas. 111 testes passando, ruff limpo.
- Último commit: `9bd4b08` — "feat: Phase 4 complete — proactive briefing, deadline alerts, dynamic reminders"

## O que foi entregue nas fases anteriores

| Fase | O que foi feito |
|------|-----------------|
| 1 | FastAPI + LangGraph + Telegram webhook + LangSmith |
| 2 | Google Calendar tools, ClickUp tools, webhooks ClickUp/Calendar, roteador de intent |
| 3 | Context builder, memória persistente (SQLite), model router (Gemini vs Gemini Pro), prompts refinados |
| 4 | `send_daily_briefing` (cron 8h), `check_deadlines` (cron 8h05), lembretes dinâmicos via APScheduler, `chat_id` persistido na primeira mensagem |

## Fase 5 — O que fazer

Implementar o Hardening do CLAUDE.md sem parar entre etapas, commit ao final de cada uma.

### Etapa 1 — Rate limiting

- Proteger o endpoint `/webhook/telegram` com rate limiting por `chat_id`
- Recomendação: usar `slowapi` (wrapper Starlette do `limits`) — instalar via `pip`
- Limite sugerido: 30 req/minuto por `chat_id` (configurável via env `RATE_LIMIT_PER_MINUTE`, default `30`)
- Responder HTTP 429 com mensagem amigável em PT-BR quando excedido
- Adicionar `RATE_LIMIT_PER_MINUTE: int` ao `src/config/settings.py`
- Registrar o limiter no `src/gateway/app.py` e aplicar o decorator no route handler em `src/gateway/routes/telegram.py`
- Testes: `tests/test_gateway/test_rate_limit.py`

### Etapa 2 — Logging estruturado

- Substituir `logging.basicConfig` por um handler JSON (ex: `python-json-logger` ou `structlog`)
  - Se preferir manter stdlib, emitir logs como JSON com campos: `timestamp`, `level`, `logger`, `message`, `extra`
- Adicionar campos de contexto em pontos críticos:
  - `src/gateway/routes/telegram.py`: logar `user_id`, `chat_id`, `intent` (depois do invoke)
  - `src/scheduler/jobs.py`: já loga `chat_id`, garantir consistência
- Adicionar `LOG_FORMAT: str` ao `src/config/settings.py` (valores: `"json"` | `"text"`, default `"text"`)
- Testes: verificar que o formato JSON é usado quando `LOG_FORMAT=json` (mock do `logging.basicConfig` ou handler)

### Etapa 3 — Health checks & readiness

- Expandir o endpoint `/health` no `src/gateway/app.py` para incluir status dos subsistemas:
  ```json
  {
    "status": "ok",
    "db": "ok",
    "scheduler": "ok | stopped",
    "version": "0.3.0"
  }
  ```
- Adicionar `/ready` (readiness probe) que retorna 503 enquanto o scheduler não estiver rodando
- Testes: `tests/test_gateway/test_health.py`

### Etapa 4 — Retry e circuit-breaker nas chamadas externas

- Adicionar retry automático com backoff exponencial nas chamadas a APIs externas:
  - ClickUp: `src/tools/clickup.py` — `_get`, `_post`, `_put` e `check_deadlines` no job
  - Telegram: `src/scheduler/jobs.py` — `_send_telegram`
  - Google Calendar: `src/tools/calendar.py` — os `_sync()` blocks já rodam em thread pool
- Estratégia recomendada: `tenacity` (`@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))`)
- Não fazer retry em erros 4xx (apenas 5xx e timeout)
- Testes: verificar que a função é chamada N vezes antes de desistir

### Etapa 5 — Testes de integração do fluxo completo

- Criar `tests/test_integration/test_full_flow.py`
- Cobrir o fluxo ponta-a-ponta mockando apenas chamadas HTTP externas (Telegram, ClickUp, Calendar):
  1. POST `/webhook/telegram` com mensagem "qual minha agenda?" → agente retorna lista de eventos
  2. POST `/webhook/telegram` com mensagem "crie lembrete para amanhã às 9h" → agente cria lembrete, confirma
  3. `send_daily_briefing` → Telegram recebe mensagem com briefing formatado
  4. `check_deadlines` com tarefas próximas → Telegram recebe alerta
- O grafo LangGraph deve ser invocado de verdade (sem mock do `_graph`), mas com LLM mockado

### Etapa 6 — [Opcional/Futuro] Roteamento para LLM local via Ollama

- Adicionar `OllamaProvider` em `src/llm/providers.py` (usa `ChatOllama` do `langchain-ollama`)
- Adicionar `OLLAMA_BASE_URL` e `OLLAMA_MODEL` ao settings
- Atualizar o router em `src/llm/router.py` para rotear para Ollama quando disponível
- O usuário tem uma AMD RX 9070 XT — verificar compatibilidade com `ollama` (ROCm)
- Esta etapa é futura e pode ser tratada como spike/investigação primeiro

## Arquivos-chave

| Arquivo | O que mudar |
|---------|-------------|
| `src/config/settings.py` | Adicionar `RATE_LIMIT_PER_MINUTE`, `LOG_FORMAT` |
| `src/gateway/app.py` | Registrar limiter SlowAPI, expandir `/health`, adicionar `/ready` |
| `src/gateway/routes/telegram.py` | Aplicar rate limit decorator |
| `src/tools/clickup.py` | Retry com tenacity em `_get/_post/_put` |
| `src/scheduler/jobs.py` | Retry em `_send_telegram` |
| `pyproject.toml` / `requirements.txt` | Adicionar `slowapi`, `tenacity`, `python-json-logger` (ou `structlog`) |

## Dependências a instalar

```bash
pip install slowapi tenacity python-json-logger
```

Adicionar ao `requirements.txt` e ao `pyproject.toml` (`[project.dependencies]`).

## Regras
- Sem chamadas reais a APIs externas — tudo mockado nos testes
- Type hints em tudo, async/await, sem hardcode de secrets
- Commit ao final de cada etapa
- Não deletar CLAUDE.md
- Versão do app: bumpar para `0.3.0` no `src/gateway/app.py` ao finalizar a fase

## Contexto de decisões anteriores
- O projeto usa Python 3.14.2 em dev — warnings de `pydantic.v1` e `datetime.utcnow` são pre-existentes e não bloqueantes
- `AsyncIOScheduler` do APScheduler com SQLite job store — jobs persistem entre restarts
- Model router usa Gemini Flash (simple/medium) e Gemini Pro (complex) — Claude Sonnet é mencionado no CLAUDE.md mas o provider atual é só Google
- Checkpointer LangGraph usa SQLite via `langgraph-checkpoint-sqlite`
