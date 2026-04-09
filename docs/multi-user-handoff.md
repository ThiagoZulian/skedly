# Handoff — Multi-usuário + OAuth por usuário

## Estado atual (após esta sessão)

Commits feitos (em ordem):
- `5a7a582` fix(telegram): prevent HTTP 500 on sendMessage failure and add plain-text fallback
- `b345613` fix(scheduler): retry Gemini 503 in daily briefing and notify user on failure
- `d5b3285` fix(scheduler): add plain-text fallback on Telegram 400 in _send_telegram
- `459c8d3` fix(agent): prevent stale history accumulation and block code leaks in responses
- `1b9ff97` fix(limiter): replace async key_func with sync get_remote_address
- `aeed99e` feat(db): add UserGoogleToken and OAuthState models for multi-user OAuth
- `706d4b6` feat(multi-user): per-user Google OAuth flow, allowlist, and calendar filter

Domínio VPS: `https://sked-ai.duckdns.org`
SSH: `ssh secretaria-vps`
Redirect URI já registrada no Google Cloud Console: `https://sked-ai.duckdns.org/auth/google/callback`
OAuth client type: **Web application** (novo, substituiu o Desktop client)

## O que foi implementado

| Área | O que mudou |
|------|-------------|
| `src/memory/models.py` | `UserGoogleToken` (token por user_id) + `OAuthState` (state temporário) |
| `src/tools/_google_auth.py` | `ContextVar current_user_id` + `get_credentials(user_id)` assíncrono carregando do banco |
| `src/tools/calendar.py` | Todas as tools usam `get_credentials()` antes da thread pool; `list_events` suporta IDs por vírgula |
| `src/gateway/routes/auth.py` | `/auth/google` (inicia OAuth) + `/auth/google/callback` (troca code por token, notifica via Telegram) |
| `src/gateway/app.py` | Registra `auth_router` |
| `src/gateway/routes/telegram.py` | Allowlist via `ALLOWED_CHAT_IDS` (env) + comando `/conectar-google` + ContextVar set/reset por request |
| `src/scheduler/jobs.py` | `send_all_briefings()` + `check_all_deadlines()` iteram sobre usuários permitidos; `current_user_id` setado por job |
| `src/scheduler/setup.py` | Jobs multi-usuário registrados (sem dependência de `TELEGRAM_CHAT_ID`) |
| `src/graph/nodes/gather_context.py` | Lê preferência `calendar_filter` do usuário e passa para `list_events` |
| `src/config/settings.py` | `app_base_url` + `allowed_chat_ids` |

## O que AINDA NÃO foi feito (próxima sessão)

### PRIORIDADE 1 — Remover ALLOWED_CHAT_IDS e implementar aprovação via banco

O `ALLOWED_CHAT_IDS` no `.env` foi a solução provisória — não escala.
Precisa ser substituído por um fluxo de aprovação DB-based:

**Fluxo desejado:**
1. Usuário novo envia qualquer mensagem
2. Bot salva status `pending` no banco e responde: "Aguardando aprovação do administrador."
3. Admin (TELEGRAM_CHAT_ID) recebe: "⚠️ Novo usuário quer acesso: [Nome] (@username) — chat_id: 123456. Use /aprovar 123456 ou /rejeitar 123456"
4. Admin responde `/aprovar 123456`
5. Bot registra `status=active` no banco e notifica o usuário: "✅ Acesso liberado!"
6. `/rejeitar 123456` → `status=blocked`, notifica o usuário com mensagem gentil

**O que mudar:**
- `src/memory/models.py`: adicionar campo `status` à `UserPreference` ou criar modelo `RegisteredUser(user_id, name, username, status, registered_at)`
- `src/gateway/routes/telegram.py`:
  - Remover lógica de `ALLOWED_CHAT_IDS`
  - No início do handler, checar DB por `status` do `user_id`
  - Se não existir: criar com `status=pending`, notificar admin, responder "aguardando"
  - Se `status=pending`: responder "ainda aguardando aprovação"
  - Se `status=blocked`: responder "acesso negado"
  - Se `status=active`: continuar normalmente
  - Detectar `/aprovar <chat_id>` e `/rejeitar <chat_id>` enviados pelo admin
- `src/config/settings.py`: remover `allowed_chat_ids`
- `src/scheduler/jobs.py`: substituir leitura de `allowed_chat_ids` por query no banco de usuários com `status=active`

### PRIORIDADE 2 — Adicionar APP_BASE_URL e APP_SECRET_KEY ao .env na VPS

O `APP_BASE_URL` foi adicionado ao settings mas ainda não está no `.env` da VPS.
Sem ele, o `/conectar-google` vai gerar links com `http://localhost:8000`.

Ação: via SSH, adicionar ao `.env` na VPS:
```
APP_BASE_URL=https://sked-ai.duckdns.org
```

### PRIORIDADE 3 — Migração do banco (novas tabelas)

As tabelas `user_google_tokens` e `oauth_states` foram adicionadas ao models.py mas
o banco SQLite existente não tem essas tabelas ainda.

O `init_db()` usa `create_all()` com `checkfirst=True`, então na próxima inicialização
do container as tabelas serão criadas automaticamente. Só fazer o deploy.

### PRIORIDADE 4 — Testar fluxo completo

Após deploy com as correções acima:
1. Acessar `https://sked-ai.duckdns.org/auth/google?state=teste` — deve retornar 400 (state inválido)
2. Enviar `/conectar-google` no Telegram — deve receber link
3. Clicar no link — deve redirecionar para Google OAuth
4. Autorizar — deve receber "✅ Google Calendar conectado!" no Telegram
5. Perguntar "quais meus próximos eventos?" — deve usar credenciais do usuário

## Arquivos chave para leitura rápida na próxima sessão

```
src/gateway/routes/telegram.py   # handler principal, onde fica o allowlist e comandos admin
src/memory/models.py             # modelos DB — adicionar RegisteredUser aqui
src/scheduler/jobs.py            # send_all_briefings — mudar de allowed_chat_ids para query DB
src/gateway/routes/auth.py       # fluxo OAuth completo — já implementado, só testar
src/tools/_google_auth.py        # get_credentials() — núcleo do auth por usuário
```

## Variáveis de ambiente necessárias na VPS (.env)

```
# Já existentes — verificar se estão corretos
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...          # seu chat_id — sempre será admin
GOOGLE_AI_API_KEY=...

# Novas — adicionar antes do próximo deploy
APP_BASE_URL=https://sked-ai.duckdns.org

# Remover após implementar aprovação via banco:
# ALLOWED_CHAT_IDS=...         # solução temporária, substituir por DB
```
