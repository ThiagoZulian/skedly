# Handoff — Fase 7 (Estabilização + Otimização)

## Estado atual
- Deploy completo na MagaluCloud — Ubuntu 22.04, Docker, Nginx, SSL Let's Encrypt
- Domínio: `sked-ai.duckdns.org`
- Telegram webhook registrado e funcionando
- Versão: `0.3.0` (código evoluiu mas versão não foi bumped)
- Último commit relevante: `fix: disable built-in Gemini retries to avoid burning quota on 429`

## O que foi feito nesta fase

| Área | O que mudou |
|------|-------------|
| Deploy | VPS criada, Docker + Nginx + Certbot configurados, webhook registrado |
| Dockerfile | Non-root user (`appuser` uid=100), curl adicionado, scripts/ copiado |
| docker-compose | Porta vinculada ao localhost, credenciais sem `:ro` (token refresh), sem version key |
| Nginx | `nginx/skedly.conf` — proxy reverso com SSL e security headers |
| Nomes | Projeto renomeado de SecretarIA para Skedly em todos os arquivos |
| Gemini models | `gemini-2.5-flash-preview-04-17` → `gemini-2.5-flash` (nome estável) |
| Calendar tools | Suporte a múltiplas agendas: `list_calendars`, `create_calendar`, `calendar_id="all"` |
| Content blocks | `_extract_text()` em `format_response` trata str/dict/list do Gemini 2.5 |
| classify_intent | Sanitização de `user_text` e `raw_intent` para content blocks |
| format_response | Só usa AIMessages após a última HumanMessage (evita resposta de turno anterior) |
| Calendar filter | `workingLocation` e `focusTime` filtrados do `list_events` |
| Quota | `max_retries=0` nos providers para não queimar quota em retries de 429 |

## Problemas conhecidos / não resolvidos

### P1 — Quota do Gemini
- Free tier: 20 req/dia para `gemini-2.5-flash`
- Cada turno consome 2-3 chamadas (classify + plan + format)
- **Ação necessária**: habilitar billing no Google AI Studio
- URL: https://aistudio.google.com → Get API key → Enable billing

### P2 — Contexto crescendo sem limite
- Histórico persistido no SQLite via LangGraph checkpointer
- Vai aumentar o custo por turno progressivamente
- Fix: trimmar para últimos N turnos antes de invocar o LLM
- Sugestão: manter últimos 10 turnos (20 mensagens)

### P3 — Validação pendente dos fixes
- Todos os fixes foram commitados mas a quota zerou antes de validar
- Testar após habilitar billing: multi-turn ("e depois desse?"), list_events em todas as agendas, create_calendar

### P4 — ClickUp não testado em produção
- Tools implementadas desde Fase 2, mas nunca validadas no ambiente de produção

## Próximos passos sugeridos (em ordem)

1. Habilitar billing Google AI Studio
2. Rodar `pytest` — calendar.py e format_response têm mudanças sem cobertura atualizada
3. Implementar context window trimming em `gather_context.py`
4. Reduzir chamadas ao LLM: considerar unificar `classify_intent` + `plan_action` para intents simples
5. Adicionar `delete_calendar` tool
6. Testar ClickUp em produção
7. Bump de versão para `0.4.0`

## Arquivos-chave modificados nesta fase

| Arquivo | O que mudou |
|---------|-------------|
| `Dockerfile` | non-root user, curl, scripts/ |
| `docker-compose.yml` | localhost bind, sem :ro em credentials |
| `nginx/skedly.conf` | novo arquivo |
| `src/llm/providers.py` | model names, max_retries=0 |
| `src/tools/calendar.py` | multi-calendar, list_calendars, create_calendar, filtro eventType |
| `src/graph/nodes/format_response.py` | _extract_text, last_human_idx, clean_messages |
| `src/graph/nodes/classify_intent.py` | sanitização content blocks |
| `prompts/plan_action.md` | instrução anti-dump de tool results, manage_calendars |
| `docs/deploy.md` | guia completo de deploy |

## Infraestrutura de produção

```
Domínio:    sked-ai.duckdns.org
VPS IP:     201.54.19.88
Provider:   MagaluCloud
SO:         Ubuntu 22.04 LTS
SSH key:    ~/.ssh/id_ed25519_secretaria
SSH alias:  secretaria-vps (via ~/.ssh/config)
App path:   ~/skedly/
```

## Comandos úteis na VPS

```bash
# Logs em tempo real
docker compose logs -f

# Rebuild após git pull
git pull && docker compose up -d --build

# Verificar saúde
curl http://localhost:8000/health

# Re-registrar webhook (se necessário)
docker compose exec app python scripts/setup_telegram_webhook.py https://sked-ai.duckdns.org
```

## Verificação de saúde antes de continuar

```bash
# Local:
python -m pytest          # todos os testes devem passar
ruff check src tests      # sem erros

# VPS:
curl http://localhost:8000/health
# {"status":"ok","db":"ok","scheduler":"ok","version":"0.3.0"}
```
