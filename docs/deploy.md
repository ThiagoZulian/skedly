# Deploy na MagaluCloud — Guia Completo

## Conceitos importantes (leitura de 2 minutos)

**Por que preciso de HTTPS?**
O Telegram só entrega mensagens ao seu bot via webhook HTTPS. Sem SSL, o bot não funciona em produção. Por isso precisamos de Nginx (proxy) + certificado SSL gratuito do Let's Encrypt.

**Por que preciso de um domínio?**
O Let's Encrypt valida que você é dono do domínio para emitir o certificado. Sem isso, não tem SSL, sem SSL, não tem webhook.

**Fluxo resumido:**

```
Telegram → HTTPS (porta 443) → Nginx na VPS → HTTP local (porta 8000) → FastAPI no Docker
```

---

## Pré-requisito: gerar o token do Google localmente

O Google Calendar exige uma autorização via browser na primeira vez. Na VPS não tem browser, então você precisa fazer isso **antes** de sair do seu computador.

```bash
# No seu computador, com o projeto rodando localmente:
docker compose up -d

# Mande qualquer mensagem de calendar no Telegram (ou via curl):
curl -X POST http://localhost:8000/webhook/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: SEU_WEBHOOK_SECRET" \
  -d '{"update_id":1,"message":{"message_id":1,"chat":{"id":123,"type":"private"},"date":1,"text":"quais meus eventos hoje?"}}'

# O browser vai abrir pedindo autorização do Google.
# Após autorizar, o arquivo credentials/token.json será criado.
```

Confirme que ele existe:

```bash
ls credentials/token.json   # deve aparecer o arquivo
```

---

## 1. Comprar ou conseguir um domínio

Você precisa de um domínio apontando para o IP da sua VPS.

**Opção A — Domínio pago (~R$50/ano):**

- [Registro.br](https://registro.br) para `.com.br`
- [Namecheap](https://namecheap.com) para `.com` (mais barato)

**Opção B — Subdomínio gratuito:**

- [DuckDNS](https://www.duckdns.org) — cria `seunome.duckdns.org` gratuitamente
  1. Acesse duckdns.org, faça login com Google
  2. Crie um subdomínio (ex: `skedly-thiago.duckdns.org`)
  3. Anote o subdomínio — você vai usá-lo em todos os passos abaixo no lugar de `yourdomain.com`

> Neste guia vamos usar `yourdomain.com` como placeholder. Substitua pelo seu domínio real.

---

## 2. Criar a VPS na MagaluCloud

1. Acesse [console.magalu.cloud](https://console.magalu.cloud) e crie uma conta
2. No painel, vá em **Compute → Virtual Machines → Criar instância**
3. Configure:
   - **Imagem**: Ubuntu 22.04 LTS
   - **Flavor**: `cloud.b1.medium` ou qualquer opção com 1 vCPU + 1–2 GB RAM
   - **Chave SSH**: crie ou importe sua chave pública (veja abaixo)
4. Anote o **IP público** da VPS após a criação

**Gerar chave SSH (se não tiver):**

```bash
# No seu computador:
ssh-keygen -t ed25519 -C "skedly-deploy"
# Aceite o caminho padrão (~/.ssh/id_ed25519)
# Cole o conteúdo de ~/.ssh/id_ed25519.pub na MagaluCloud
cat ~/.ssh/id_ed25519.pub
```

---

## 3. Apontar o domínio para a VPS

No painel do seu registrador de domínio (Registro.br, Namecheap, DuckDNS etc.), crie um registro **A**:

| Tipo | Nome | Valor             |
| ---- | ---- | ----------------- |
| A    | @    | IP_PUBLICO_DA_VPS |

Aguarde alguns minutos para propagar. Teste:

```bash
ping yourdomain.com   # deve mostrar o IP da sua VPS
```

---

## 4. Configuração inicial da VPS

```bash
# Conecte-se via SSH (do seu computador):
ssh ubuntu@IP_DA_VPS

# Atualize o sistema
sudo apt update && sudo apt upgrade -y

# Instale utilitários básicos
sudo apt install -y git curl unzip
```

### Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh        # porta 22
sudo ufw allow http       # porta 80  (necessário para o Certbot validar o domínio)
sudo ufw allow https      # porta 443 (Telegram webhook)
sudo ufw enable
sudo ufw status           # confirme que as regras estão ativas
```

### Desabilitar login por senha no SSH (segurança)

```bash
sudo nano /etc/ssh/sshd_config
```

Encontre e altere (ou adicione) estas linhas:

```
PermitRootLogin no
PasswordAuthentication no
```

```bash
sudo systemctl restart ssh
```

> **Atenção:** só faça isso depois de confirmar que consegue logar com a chave SSH.

---

## 5. Instalar Docker

```bash
# Instalador oficial do Docker
curl -fsSL https://get.docker.com | sh

# Adicionar seu usuário ao grupo docker (para não precisar de sudo)
sudo usermod -aG docker ubuntu
newgrp docker

# Verificar:
docker --version
docker compose version
```

---

## 6. Instalar Nginx e Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

## 7. Subir o código para a VPS

**Opção A — Via Git (recomendado se o repo estiver no GitHub):**

```bash
# Na VPS:
cd ~
git clone https://github.com/SEU_USUARIO/SEU_REPO.git skedly
cd skedly
```

**Opção B — Via rsync (do seu computador):**

```bash
# No seu computador:
rsync -avz \
  --exclude='.env' \
  --exclude='data/' \
  --exclude='__pycache__/' \
  --exclude='.git/' \
  ./ ubuntu@IP_DA_VPS:~/skedly/
```

---

## 8. Criar o .env na VPS

```bash
# Na VPS:
cd ~/skedly
nano .env
```

Cole o conteúdo do seu `.env` local, adicionando/ajustando estas variáveis extras para produção:

```env
# Adicione ao final do .env:
LOG_FORMAT=json
TELEGRAM_CHAT_ID=SEU_CHAT_ID_DO_TELEGRAM
```

> Para descobrir seu `TELEGRAM_CHAT_ID`: mande uma mensagem pro seu bot e acesse
> `https://api.telegram.org/botSEU_TOKEN/getUpdates` — o número em `"id"` dentro de `"chat"` é o chat_id.

---

## 9. Enviar credenciais do Google

```bash
# Do seu computador, envie os dois arquivos de credenciais:
scp credentials/google_oauth.json ubuntu@IP_DA_VPS:~/skedly/credentials/
scp credentials/token.json         ubuntu@IP_DA_VPS:~/skedly/credentials/
```

---

## 10. Configurar o Nginx

```bash
# Na VPS:
# Copie o template e abra para edição
sudo cp ~/skedly/nginx/skedly.conf /etc/nginx/sites-available/skedly
sudo nano /etc/nginx/sites-available/skedly
```

Substitua **todas** as ocorrências de `yourdomain.com` pelo seu domínio real. Salve e feche (`Ctrl+X`, `Y`, `Enter`).

Ative o site e teste a configuração:

```bash
sudo ln -s /etc/nginx/sites-available/skedly /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # remove o site padrão do Nginx
sudo nginx -t                                  # deve mostrar "syntax is ok"
sudo systemctl reload nginx
```

---

## 11. Obter certificado SSL

```bash
# Na VPS (substitua yourdomain.com pelo seu domínio):
sudo certbot --nginx -d yourdomain.com
```

O Certbot vai:

1. Perguntar seu e-mail (para notificações de renovação)
2. Perguntar se aceita os termos
3. Emitir o certificado e atualizar o Nginx automaticamente

Verifique a renovação automática:

```bash
sudo systemctl status certbot.timer   # deve estar ativo
```

---

## 12. Iniciar a aplicação

```bash
# Na VPS:
cd ~/skedly

# Build e subir o container
docker compose up -d --build

# Acompanhar os logs (Ctrl+C para sair sem derrubar o container)
docker compose logs -f

# Aguardar o /health responder ok (pode demorar ~15s no primeiro start):
curl http://localhost:8000/health
# Esperado: {"status":"ok","db":"ok","scheduler":"ok","version":"0.3.0"}
```

---

## 13. Registrar o webhook do Telegram

```bash
# Na VPS, com o container rodando:
docker compose exec app python scripts/setup_telegram_webhook.py https://yourdomain.com
# Esperado: "Webhook registered: https://yourdomain.com/webhook/telegram"
```

Verifique:

```bash
docker compose exec app python -c "
import asyncio, httpx
from src.config import settings
async def check():
    async with httpx.AsyncClient() as c:
        r = await c.get(f'https://api.telegram.org/bot{settings.telegram_bot_token}/getWebhookInfo')
        print(r.json())
asyncio.run(check())
"
```

O campo `url` deve mostrar `https://yourdomain.com/webhook/telegram`.

---

## 14. Teste final

Mande uma mensagem pro seu bot no Telegram. A resposta deve chegar em segundos.

Se não funcionar, veja os logs:

```bash
docker compose logs -f --tail=50
```

---

## Comandos úteis de manutenção

```bash
# Ver status do container
docker compose ps

# Reiniciar app (ex: após mudar o .env)
docker compose restart

# Rebuild após atualizar o código
docker compose up -d --build

# Parar tudo
docker compose down

# Ver logs em tempo real
docker compose logs -f

# Entrar no container para debug
docker compose exec app bash

# Verificar renovação SSL
sudo certbot renew --dry-run
```

---

## Atualizar o código (após um git push)

```bash
# Na VPS:
cd ~/skedly
git pull
docker compose up -d --build
```

---

## Troubleshooting comum

| Sintoma                              | Causa provável                    | Solução                               |
| ------------------------------------ | ---------------------------------- | --------------------------------------- |
| Bot não responde                    | Webhook não registrado            | Repita o passo 13                       |
| `curl localhost:8000/health` falha | Container não subiu               | `docker compose logs` para ver o erro |
| Erro de Google Calendar              | `token.json` ausente ou expirado | Reenvie o arquivo (passo 9)             |
| Nginx 502 Bad Gateway                | Container parado                   | `docker compose up -d`                |
| Certbot falha                        | Domínio não aponta para a VPS    | Verifique o registro DNS (passo 3)      |
