# Handoff — Fase 6 (Ollama Local + Débito Técnico)

## Estado atual

- Fases 1–5 completas. 130 testes passando, ruff limpo.
- Último commit da Fase 5: `feat: Phase 5 complete — version bump 0.3.0`
- Versão: `0.3.0`

## O que foi entregue nas fases anteriores

| Fase | O que foi feito                                                                                                   |
| ---- | ----------------------------------------------------------------------------------------------------------------- |
| 1    | FastAPI + LangGraph + Telegram webhook + LangSmith                                                                |
| 2    | Google Calendar tools, ClickUp tools, webhooks, roteador de intent                                                |
| 3    | Context builder, memória persistente (SQLite), model router, prompts refinados                                    |
| 4    | Briefing diário (cron 8h), alerta de deadlines (cron 8h05), lembretes dinâmicos, chat_id persistido               |
| 5    | Rate limiting (slowapi), logging JSON estruturado, /health e /ready, retry com tenacity, testes de integração E2E |

## Fase 6 — O que fazer

### Etapa 1 — Roteamento para LLM local via Ollama (spike/investigação)

O usuário tem uma AMD RX 9070 XT. O Ollama tem suporte experimental a ROCm.

**Investigação antes de implementar:**

- Verificar versão atual do ROCm compatível com RX 9070 XT (RDNA 4 — pode ainda não ter suporte estável)
- Testar `ollama run llama3.2:3b` localmente antes de integrar
- Avaliar latência vs. qualidade em relação ao Gemini Flash

**Implementação (quando viável):**

1. Instalar `langchain-ollama` e adicionar ao `requirements.txt` / `pyproject.toml`
2. Adicionar `OllamaProvider` em `src/llm/providers.py`:

   ```python
   from langchain_ollama import ChatOllama

   def get_ollama(model: str | None = None) -> ChatOllama:
       return ChatOllama(
           base_url=settings.ollama_base_url,
           model=model or settings.ollama_model,
       )
   ```

3. Adicionar ao `src/config/settings.py`:

   ```python
   ollama_base_url: str = Field(default="http://localhost:11434", ...)
   ollama_model: str = Field(default="llama3.2:3b", ...)
   use_ollama: bool = Field(default=False, ...)
   ```

4. Atualizar `src/llm/router.py` para rotear para Ollama quando `settings.use_ollama=True` e o servidor estiver disponível (health check no startup).
5. Fallback automático: se Ollama não responder em 2s → Gemini Flash.
6. Testes: mock do ChatOllama, verificar fallback quando offline.

### Etapa 2 — Débito técnico identificado na Fase 5

#### 2a — `check_deadlines` não usa `_get` com retry

**Problema**: `check_deadlines` em `src/scheduler/jobs.py` faz sua própria chamada `httpx.AsyncClient` diretamente em vez de usar `_get` de `src/tools/clickup.py`.

**Fix sugerido**: extrair a chamada HTTP para uma função auxiliar em `jobs.py` decorada com `@retry`, ou importar e reusar `_get` do módulo de tools.

#### 2b — Sem retry em `_send_telegram_message` da rota

**Problema**: `_send_telegram_message` em `src/gateway/routes/telegram.py` não tem retry. Já temos retry em `src/scheduler/jobs.py:_send_telegram`, mas o helper da rota ficou sem.

**Fix sugerido**: aplicar o mesmo `@retry` de tenacity em `_send_telegram_message`.

#### 2c — Sem testes para as ferramentas do Google Calendar

**Problema**: `src/tools/calendar.py` é testado indiretamente, mas não há testes unitários para os helpers `_sync()` internos.

**Fix sugerido**: adicionar `tests/test_tools/test_calendar.py` com mocks do `googleapiclient`.

#### 2d — `LOG_FORMAT` não afeta loggers de bibliotecas

**Problema**: ao mudar para `LOG_FORMAT=json`, apenas o root logger é configurado. Loggers do uvicorn e do APScheduler têm seus próprios handlers e não são afetados.

**Fix sugerido**: no `_configure_logging`, propagar a configuração JSON para os loggers de bibliotecas conhecidas:

```python
for name in ("uvicorn", "uvicorn.access", "apscheduler"):
    lib_logger = logging.getLogger(name)
    lib_logger.handlers = [handler]
```

### Etapa 3 — Deploy na MagaluCloud (mencionado no CLAUDE.md)

Quando o código estiver maduro o suficiente:

1. Configurar `Dockerfile` para produção (multi-stage, non-root user)
2. Configurar `docker-compose.yml` para produção (volumes, restart policy, healthcheck)
3. Criar script de provisionamento para VPS MagaluCloud
4. Configurar `TELEGRAM_WEBHOOK_URL` e registrar o webhook via API do Telegram
5. Configurar variáveis de ambiente seguras no servidor (sem `.env` em produção)
6. Adicionar CI/CD básico (GitHub Actions: lint + test em cada PR)

## Arquivos-chave para Fase 6

| Arquivo                               | O que mudar                                               |
| ------------------------------------- | --------------------------------------------------------- |
| `src/llm/providers.py`                | Adicionar `get_ollama()`                                  |
| `src/llm/router.py`                   | Rotear para Ollama quando disponível                      |
| `src/config/settings.py`              | Adicionar `ollama_base_url`, `ollama_model`, `use_ollama` |
| `src/scheduler/jobs.py`               | Adicionar retry em `check_deadlines` HTTP call            |
| `src/gateway/routes/telegram.py`      | Adicionar retry em `_send_telegram_message`               |
| `Dockerfile` / `docker-compose.yml`   | Hardening para produção                                   |
| `requirements.txt` / `pyproject.toml` | Adicionar `langchain-ollama`                              |

## Dependências a instalar (Fase 6)

```bash
pip install langchain-ollama
# Ollama instalado localmente: https://ollama.com/download
```

## Contexto de decisões anteriores

- Python 3.14.2 em dev — warnings de `pydantic.v1` e `datetime.utcnow` são pre-existentes e não bloqueantes
- `AsyncIOScheduler` do APScheduler com SQLite job store — jobs persistem entre restarts
- Model router usa Gemini Flash (simple/medium) e Gemini Pro (complex)
- Retry policy: 3 tentativas, exponential backoff 1–8s, apenas 5xx e timeout (não 4xx)
- Rate limiting: 30 req/min por `chat_id` no webhook Telegram (configurável via `RATE_LIMIT_PER_MINUTE`)
- AMD RX 9070 XT (RDNA 4): ROCm pode não ter suporte estável ainda — verificar antes de integrar Ollama

## Verificação de saúde antes de iniciar

```bash
python -m pytest          # 130 testes devem passar
ruff check src tests      # sem erros
curl localhost:8000/health  # {"status":"ok","db":"ok","scheduler":"ok","version":"0.3.0"}
curl localhost:8000/ready   # {"status":"ready"}
```
