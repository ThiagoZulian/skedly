O fluxo principal: Telegram → resposta

Telegram Bot API
│ POST /webhook/telegram
▼
src/gateway/app.py ← ponto de entrada HTTP
│
▼
src/gateway/routes/telegram.py ← valida, parseia, invoca
│ valida header
▼
src/gateway/validators.py ← confirma autenticidade
│ monta AgentState
▼
src/graph/builder.py ← grafo compilado (singleton)
│
├─→ src/graph/nodes/classify_intent.py ← chama Gemini Flash
│ │
│ ▼
│ src/graph/edges.py ← decide próximo nó
│ │
├─→ src/graph/nodes/format_response.py ← formata a resposta
│
▼
src/gateway/routes/telegram.py ← POST sendMessage de volta
│
▼
Telegram Bot API (entrega ao usuário)

---

Arquivo por arquivo

Infraestrutura / config

src/config/settings.py
Define Settings(BaseSettings) com todos os campos do .env — tokens do Telegram, ClickUp, Google AI, database URL, flags do LangSmith. Campos sem
default são obrigatórios em produção; campos opcionais têm None. É a única fonte de verdade para configuração.

src/config/**init**.py
Expõe settings como um proxy \_LazySettings: só constrói Settings() no primeiro acesso de atributo, não no import. Isso permite que os testes injetem
variáveis de ambiente antes de qualquer instanciação — sem isso, pytest quebraria ao importar módulos que dependem de settings.

---

Gateway (HTTP)

src/gateway/app.py
Cria o FastAPI com um lifespan handler. No startup: configura logging e, se LANGSMITH_TRACING=true, seta as env vars do LangSmith
(LANGCHAIN_TRACING_V2 etc.) para que todo LangGraph seja trackeado automaticamente sem alterar código. Registra o router do Telegram e expõe GET
/health.

src/gateway/routes/telegram.py
É onde começa o trabalho de verdade. Na inicialização do módulo chama build_graph() e armazena o grafo compilado em \_graph (singleton — compilar
grafo é caro, fazer uma vez só). Quando chega um POST: valida o secret, parseia o JSON em TelegramUpdate (via Pydantic), monta o AgentState inicial
com a mensagem do usuário, invoca \_graph.ainvoke() de forma async, e chama \_send_telegram_message() com a resposta. Tem três models Pydantic:
TelegramUser, TelegramChat, TelegramMessage — o model_validate customizado existe porque from é keyword reservada do Python.

src/gateway/validators.py
Duas funções puras de segurança: validate_telegram_secret (compara o header X-Telegram-Bot-Api-Secret-Token com o valor do .env) e
validate_clickup_signature (HMAC-SHA256 para quando ClickUp webhooks forem adicionados na Fase 2). Usa hmac.compare_digest para evitar timing
attacks.

---

LangGraph (o agente)

src/graph/state.py
Define AgentState, o único objeto que transita entre todos os nós. O campo messages usa o reducer add_messages do LangGraph — em vez de substituir a
lista, ele acumula mensagens. Os outros campos (intent, context, response, user_id) são substituídos diretamente por cada nó que retorna um dict
parcial.

src/graph/builder.py
A "planta" do grafo. Registra dois nós (classify_intent, format_response), define o entry point, adiciona a conditional edge de classify_intent →
route_by_intent → próximo nó, e fecha com format_response → END. Aceita um checkpointer opcional: quando passado, o LangGraph persiste o estado por
thread_id no SQLite, dando memória de conversa. Na Fase 1 roda sem checkpointer.

src/graph/edges.py
Contém route_by_intent(state) → str. Na Fase 1 retorna sempre "format_response" — é um stub intencional. Nas fases seguintes vai ramificar: intents
que precisam de tools vão passar por gather_context → plan_action → execute_tools antes de chegar em format_response.

src/graph/nodes/classify_intent.py
Pega a última mensagem do state, carrega o prompt de prompts/classify_intent.md, chama get_gemini_flash() com [SystemMessage, HumanMessage] e parseia
a resposta. Valida contra VALID_INTENTS (frozenset) — se o LLM alucinar uma categoria nova, cai em general_chat. Se o LLM lançar exceção, também cai
em general_chat. O nó retorna {"intent": "..."} e o LangGraph merge isso no state.

src/graph/nodes/format_response.py
Lê state["intent"], converte para um label em português via \_INTENT_LABELS, e monta uma string de confirmação com Markdown do Telegram. Na Fase 1 é
um placeholder que echo o intent. Nas fases seguintes vai receber state["context"] e state["tool_results"] para gerar uma resposta real com o LLM.

---

LLM

src/llm/providers.py
Duas factories: get_gemini_flash() (modelo gemini-2.5-flash, max_tokens=2048, temp=0.2) e get_gemini_pro() (modelo gemini-2.5-pro, max_tokens=8192,
temp=0.3). Ambas leem a mesma GOOGLE_AI_API_KEY — a chave de API do Google AI Studio é única para os dois modelos. Instanciam um novo objeto a cada
chamada (stateless por design).

src/llm/router.py
Define INTENT_COMPLEXITY_MAP que associa cada categoria de intent a um tier (SIMPLE, MEDIUM, COMPLEX). get_model_for_intent(intent) usa esse mapa
para decidir: SIMPLE/MEDIUM → Flash, COMPLEX → Pro. Na Fase 1 o roteador ainda não é chamado pelo grafo (o nó classify_intent chama get_gemini_flash
diretamente) — o roteador será usado no plan_action da Fase 3.

---

Prompts

prompts/classify_intent.md
System prompt que instrui o Gemini a retornar exatamente uma string de categoria, sem explicações. Tem uma tabela com 8 categorias e exemplos em
português. É lido do disco a cada invocação do nó (simples e barato — é um arquivo pequeno).

prompts/system.md
Personalidade da SecretarIA: concisa, proativa, warm mas profissional, sempre em pt-BR. Define capacidades (Calendar, ClickUp, lembretes) e limites
(não navega na web, não manda emails). Será injetado como SystemMessage nas fases de plan_action.

prompts/daily_briefing.md
Template estruturado para o briefing matinal: saudação, agenda do dia, tarefas prioritárias, lembretes ativos, sugestão proativa. Será usado pelo nó
format_response (ou um nó dedicado) na Fase 4.

---

Testes

tests/conftest.py
Seta os.environ no nível de módulo — antes de qualquer import de src.\* — porque o pytest coleta e importa os módulos de teste antes de executar
fixtures. Tem reset_settings_singleton como autouse=True para garantir que cada teste começa com settings "limpo". O ANTHROPIC_API_KEY ainda está
aqui como artefato do setup anterior — pode remover.

tests/test_graph/test_state.py — verifica que AgentState tem as chaves certas e aceita os tipos esperados.

tests/test_graph/test_nodes.py — testa classify_intent e format_response com LLM mockado. Cobre: intent válido, intent desconhecido (fallback),
exceção no LLM, state vazio, e todos os 8 intents via @parametrize.

tests/test_graph/test_edges.py — testa route_by_intent para todos os intents, incluindo string vazia e intent desconhecido.

tests/test_gateway/test_webhooks.py — testa o endpoint HTTP: secret válido, secret inválido (403), sem secret (403), update sem mensagem (ignored),
mensagem vazia (ignored), exceção no grafo (ainda retorna 200 — Telegram exige isso para parar de retentar).

---

Scripts

scripts/run_graph_local.py — REPL interativo no terminal para testar o grafo sem Telegram. Requer .env com GOOGLE_AI_API_KEY. Útil para iterar nos
prompts sem subir o servidor.

scripts/setup_telegram_webhook.py — Registra (ou remove) o webhook no Telegram Bot API. Precisa de URL pública HTTPS. Não execute localmente.

---

O que ainda são stubs (pastas vazias)

src/tools/, src/memory/, src/scheduler/ existem como pacotes mas não têm código — são os alvos das Fases 2–4. O grafo hoje só tem dois nós; nas
próximas fases entram gather_context, plan_action e execute_tools entre eles.
