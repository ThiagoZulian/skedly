# Skedly — Projeto de Secretária Pessoal com IA

## Visão geral
Assistente pessoal de IA que integra ClickUp, Google Calendar e Telegram.
Usa agentes autônomos com LangGraph, roteamento entre modelos (Gemini Flash como
principal via free tier/Vertex AI, Claude Sonnet como fallback para tarefas complexas).
Capaz de monitorar agenda e tarefas proativamente via webhooks e cron jobs,
enviar lembretes, responder comandos em linguagem natural e reorganizar prioridades.

## Stack técnica
- **Orquestração**: LangGraph + LangChain Core + LangSmith (tracing)
- **LLM principal**: Gemini 2.5 Flash via Google AI Studio (free tier) ou Vertex AI ($300 créditos)
- **LLM fallback**: Claude Sonnet 4.6 via Anthropic API (tasks complexas)
- **Web framework**: FastAPI + Uvicorn
- **Validação**: Pydantic v2 + pydantic-settings
- **HTTP client**: httpx (async)
- **Integrações**: python-telegram-bot, Google Calendar API, ClickUp API v2
- **Persistência**: SQLite via SQLAlchemy + aiosqlite
- **Checkpointing**: langgraph-checkpoint-sqlite
- **Scheduler**: APScheduler (cron jobs + lembretes dinâmicos criados pelo agente)
- **DevOps**: Docker, pytest, Ruff, pre-commit
- **Deploy futuro**: VPS na MagaluCloud (por enquanto roda local no Docker)

## Arquitetura do agente (LangGraph)
O agente é um StateGraph com os seguintes nós:
1. **classify_intent** — classifica o que o usuário quer (agendar, consultar, criar task, chat livre, etc.)
2. **gather_context** — coleta agenda + tarefas + horário atual pro contexto
3. **plan_action** — LLM decide a ação usando tools disponíveis
4. **execute_tools** — executa as tools chamadas pela LLM
5. **format_response** — formata a resposta pro Telegram

Conditional edges roteiam com base no intent classificado.

## Tools disponíveis para o agente
- **calendar**: list_events, create_event, find_free_slots, delete_event
- **clickup**: list_tasks, create_task, update_task, get_task_details
- **telegram**: send_message, send_reminder
- **datetime_utils**: get_current_time, parse_relative_date, get_weekday
- **reminders**: create_reminder, list_reminders, delete_reminder (persiste jobs no SQLite via APScheduler)

## Model routing
- Intent simples (ler agenda, listar tarefas) → Gemini 2.5 Flash
- Intent médio (agendar evento, criar task com contexto) → Gemini 2.5 Flash
- Intent complexo (replanejar semana, análise de prioridades, briefing diário) → Claude Sonnet 4.6

## Event-driven + cron jobs
- **Webhooks** (event-driven): Telegram Bot API, ClickUp webhooks, Google Calendar push notifications
- **Cron fixo**: briefing diário pela manhã, checagem de deadlines
- **Cron dinâmico**: lembretes criados pelo próprio agente em runtime (ex: "me lembre no final do mês de pagar o DAS"), persistidos no SQLite e recarregados no restart

## Configuração
- Variáveis de ambiente em `.env` (já configurado)
- Credenciais Google OAuth em `credentials/google_oauth.json` (já configurado)
- Token Google Calendar será gerado na primeira execução (abre browser para autorizar)
- SQLite será criado automaticamente pela app

## Estrutura de pastas esperada
```
secretary-ai/
├── .env
├── credentials/google_oauth.json
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── CLAUDE.md                        # Este arquivo
│
├── src/
│   ├── graph/                       # LangGraph
│   │   ├── state.py                 # AgentState (TypedDict)
│   │   ├── nodes/
│   │   │   ├── classify_intent.py
│   │   │   ├── gather_context.py
│   │   │   ├── plan_action.py
│   │   │   ├── execute_tools.py
│   │   │   └── format_response.py
│   │   ├── edges.py                 # Conditional edges
│   │   └── builder.py              # Compila o StateGraph
│   │
│   ├── tools/                       # LangChain Tools (@tool)
│   │   ├── calendar.py
│   │   ├── clickup.py
│   │   ├── telegram.py
│   │   ├── datetime_utils.py
│   │   └── reminders.py
│   │
│   ├── llm/
│   │   ├── providers.py             # ChatGoogleGenerativeAI, ChatAnthropic
│   │   └── router.py               # Qual modelo usar por tipo de task
│   │
│   ├── gateway/
│   │   ├── app.py                   # FastAPI
│   │   ├── routes/
│   │   │   ├── telegram.py
│   │   │   ├── clickup.py
│   │   │   └── calendar.py
│   │   └── validators.py
│   │
│   ├── memory/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── checkpointer.py
│   │
│   ├── scheduler/
│   │   ├── jobs.py
│   │   └── setup.py
│   │
│   └── config/
│       └── settings.py              # Pydantic BaseSettings
│
├── prompts/
│   ├── system.md
│   ├── classify_intent.md
│   └── daily_briefing.md
│
├── tests/
├── scripts/
└── docs/
```

## Fases de implementação

### Fase 1 — Fundação (atual)
1. Setup do projeto (Docker, FastAPI, dependências, .env)
2. Definir o AgentState
3. Criar nó classify_intent (chamada ao Gemini Flash)
4. Criar nó format_response
5. Compilar o grafo e testar localmente
6. Conectar ao webhook do Telegram
7. Configurar LangSmith

### Fase 2 — Integrações
8. Google Calendar tool
9. ClickUp tool
10. Webhooks do ClickUp e Calendar
11. Roteador de intent

### Fase 3 — Inteligência
12. Context builder
13. Memória persistente
14. Model router (Gemini vs Claude)
15. System prompts refinados

### Fase 4 — Proatividade
16. Briefing diário
17. Alerta de deadlines
18. Lembretes dinâmicos (cron jobs criados pelo agente)

### Fase 5 — Hardening
19. Testes, rate limiting, logging
20. [Futuro] Roteamento para LLM local via Ollama (RX 9070 XT)

## Regras de código
- Python 3.12+
- Type hints em tudo
- Docstrings em funções públicas
- Async/await onde possível (FastAPI, httpx, aiosqlite)
- Pydantic models para validação de dados
- Ruff para linting e formatação
- Testes com pytest + pytest-asyncio
- Sem hardcode de secrets — tudo via .env
- Sem commitar .env, credentials/, data/, *.db

## Contexto do desenvolvedor
Estou usando este projeto como portfólio e para aprendizado em MLE e construção de agentes.
Priorize boas práticas, código limpo e patterns reconhecidos pelo mercado.
Use LangGraph idiomaticamente — não reimplemente o que o framework já oferece.
