# Skedly

Assistente pessoal de IA com LangGraph, integrado a Telegram, Google Calendar e ClickUp.

## Stack

- **Orquestração**: LangGraph + LangChain Core + LangSmith
- **LLM principal**: Gemini 2.5 Flash (Google AI Studio)
- **LLM fallback**: Claude Sonnet 4.6 (Anthropic API)
- **Web framework**: FastAPI + Uvicorn
- **Integrações**: Telegram Bot API, Google Calendar API, ClickUp API v2
- **Persistência**: SQLite via SQLAlchemy + aiosqlite
- **Scheduler**: APScheduler

## Setup rápido

```bash
# 1. Copie o .env.example e preencha as variáveis
cp .env.example .env

# 2. Adicione suas credenciais Google OAuth
cp <seu-arquivo-oauth> credentials/google_oauth.json

# 3. Suba com Docker
docker-compose up --build

# 4. Registre o webhook do Telegram (após ter o servidor público)
python scripts/setup_telegram_webhook.py https://seu-dominio.com
```

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.gateway.app:app --reload
```

## Testes

```bash
pytest
```

## Lint

```bash
ruff check src/
```

## Roadmap / TODO

### Em aberto

- **Billing Google AI Studio** — free tier limita a 20 req/dia; habilitar para validar multi-turn e multi-calendar em produção
- **Testar ClickUp em produção** — tools implementadas desde Fase 2, nunca validadas no ambiente real
- **Unificar classify + plan para intents simples** — reduzir de 2-3 chamadas ao LLM por turno para 1-2

### Backlog

- Roteamento para LLM local via Ollama (RX 9070 XT)
- Suporte real a múltiplos usuários (isolamento de contexto)
- Interface web mínima para visualizar reminders e histórico
