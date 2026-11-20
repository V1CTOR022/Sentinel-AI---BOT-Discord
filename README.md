# Sentinel AI

[![CI](https://github.com/V1CTOR022/Sentinel-AI---BOT-Discord/actions/workflows/ci.yml/badge.svg)](https://github.com/V1CTOR022/Sentinel-AI---BOT-Discord/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Bot de Discord que transforma a atividade de um servidor em métricas úteis para quem administra: quanto se fala, onde se fala, quem participa e quando o movimento sai do normal. Vem com uma API para consultar esses dados e um dashboard web para visualizá-los.

O projeto é open source (MIT) e roda inteiro na sua máquina. Nenhum serviço pago é obrigatório: a integração de IA é opcional e, sem chave configurada, todo o resto continua funcionando.

## O que ele faz

**Monitoramento de atividade.** Cada mensagem gera um registro com servidor, canal, autor e horário. O conteúdo da mensagem nunca é lido nem armazenado.

**Detecção de flood.** Um contador por usuário em janela deslizante avisa a moderação quando alguém dispara muitas mensagens em poucos segundos. O bot só alerta; a decisão de punir fica com a equipe.

**Relatórios.** O comando `/relatorio` monta um resumo dos últimos dias com total de mensagens, canais mais ativos e a curva diária. Definindo `REPORT_CHANNEL_ID`, o mesmo relatório é publicado automaticamente em intervalos fixos.

**IA opcional.** Com `AI_API_KEY` e `AI_MODEL` preenchidos, `/ask` responde perguntas e os relatórios ganham um parágrafo de leitura dos números. Os números continuam vindo do banco; o modelo só comenta o que já foi calculado. O projeto não depende de nenhum fornecedor específico: ver [Trocando o provedor de IA](#trocando-o-provedor-de-ia).

**Dashboard.** Página em React com os totais, o gráfico de mensagens por dia e o ranking de canais, atualizando sozinha a cada minuto.

## Como está organizado

```
core/      configuração, acesso ao SQLite e as consultas de leitura
bot/       bot do Discord: cogs de comandos e serviços (atividade, moderação, IA, relatórios)
api/       FastAPI que serve as métricas já agregadas
dashboard/ front-end em React + Vite
tests/     testes com pytest
```

`core/` é compartilhado: o bot escreve, a API lê, e as consultas ficam em um único lugar para que o endpoint e o comando `/relatorio` nunca discordem sobre o que é "mensagem na última semana".

Duas decisões que valem explicação:

- As gravações passam por um buffer em memória e vão para o banco em lote a cada poucos segundos. Um `INSERT` com `commit` por mensagem trava o SQLite assim que o servidor fica movimentado, porque a API lê o mesmo arquivo em paralelo.
- A conexão é única por processo, com `journal_mode=WAL` ligado, pelo mesmo motivo.

## Rodando localmente

Precisa de Python 3.11+, Node.js 20+ e uma aplicação criada no [Discord Developer Portal](https://discord.com/developers/applications) com o bot adicionado ao servidor.

```bash
cp .env.example .env          # preencha DISCORD_TOKEN e DISCORD_GUILD_ID
pip install -r requirements.txt
python -m bot.main
```

Em outro terminal, a API:

```bash
uvicorn api.main:app --reload
```

E o dashboard:

```bash
cd dashboard
cp .env.example .env          # preencha VITE_DISCORD_GUILD_ID
npm install
npm run dev
```

A documentação interativa da API fica em http://127.0.0.1:8000/docs e o dashboard em http://localhost:5173.

Deixe o bot rodando alguns minutos antes de abrir o dashboard: sem mensagens registradas não há nada para mostrar.

## Variáveis de ambiente

| Variável | Obrigatória | Para que serve |
| --- | --- | --- |
| `DISCORD_TOKEN` | sim | Token do bot. |
| `DISCORD_GUILD_ID` | recomendada | Sincroniza os comandos só nesse servidor, o que vale na hora. Sem ela, o sync é global e leva até uma hora. |
| `DATABASE_PATH` | não | Caminho do arquivo SQLite. Padrão: `data/sentinel.db`. |
| `MOD_LOG_CHANNEL_ID` | não | Canal de texto que recebe os alertas de flood. |
| `FLOOD_LIMIT` / `FLOOD_WINDOW_SECONDS` | não | Sensibilidade do detector. Padrão: 6 mensagens em 8 segundos. |
| `REPORT_CHANNEL_ID` / `REPORT_INTERVAL_HOURS` | não | Ativa o relatório automático. |
| `AI_API_KEY` / `AI_MODEL` | não | Habilitam `/ask` e o comentário nos relatórios. Precisa dos dois. |
| `AI_BASE_URL` | não | Endpoint do provedor de IA. Padrão: `https://api.openai.com/v1`. |
| `SENTINEL_API_KEY` | não | Se definida, a API exige o header `X-API-Key`. |
| `DASHBOARD_ORIGINS` | não | Origens liberadas no CORS. |

Valores inválidos (um ID de canal escrito como texto, por exemplo) param o processo na subida com mensagem explicando o que está errado, em vez de falhar silenciosamente depois.

## Comandos

| Comando | O que faz |
| --- | --- |
| `/ping` | Confirma que o bot está online e mostra a latência. |
| `/server` | Informações gerais do servidor. |
| `/status` | Estado interno do monitoramento. |
| `/relatorio [dias]` | Resumo da atividade recente, de 1 a 30 dias. |
| `/ask <pergunta>` | Pergunta ao assistente. Exige `AI_API_KEY` e `AI_MODEL`. |

## Trocando o provedor de IA

O serviço fala o formato OpenAI de *chat completions*, que virou padrão de fato. Qualquer provedor que o implemente funciona mudando duas variáveis, sem tocar no código:

| Provedor | `AI_BASE_URL` | `AI_MODEL` (exemplo) |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | `<fornecedor>/<modelo>` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.1` |

Com Ollama não existe chave de verdade; preencha `AI_API_KEY=ollama` só para o serviço se considerar configurado. Confirme na documentação do provedor qual nome de modelo está disponível na sua conta, porque esses nomes mudam com o tempo.

Toda a conversa com o provedor está em [`bot/services/ai_service.py`](bot/services/ai_service.py), em duas funções: `answer_question` e `summarize_activity`. Se quiser um formato de API diferente, é o único arquivo a mexer.

## API

Todas as rotas devolvem dados agregados, nunca texto de mensagem.

| Rota | Retorno |
| --- | --- |
| `GET /health` | Estado do serviço. |
| `GET /api/guilds` | Servidores com dados registrados. |
| `GET /api/guilds/{id}/metrics` | Totais, usuários e canais distintos, volume em 24h e 7 dias. |
| `GET /api/guilds/{id}/activity` | Canais mais ativos, com nome e número de participantes. |
| `GET /api/guilds/{id}/members` | Participação por membro, identificada apenas por ID. |
| `GET /api/guilds/{id}/timeline` | Mensagens por dia. |

A autenticação é opcional no desenvolvimento e necessária em qualquer lugar exposto à internet. CORS é regra de navegador, não de servidor: sem `SENTINEL_API_KEY`, quem tiver a URL lê as métricas de qualquer servidor.

## Privacidade

O bot guarda IDs de servidor, canal e autor, o nome do canal e o horário. A intent `message_content` fica desligada no código, então ele não tem acesso ao texto das mensagens nem precisa pedir essa permissão ao Discord.

Mesmo assim, você está coletando dados de comportamento de pessoas reais. Avise os membros, use apenas em servidores onde tenha autorização e apague o banco quando não precisar mais dele.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Cobrem o detector de flood (incluindo o descarte de usuários inativos), a gravação em lote, as consultas agregadas e os endpoints da API com e sem chave. Não é preciso token do Discord nem chave de IA para rodar.

## Limitações conhecidas

- SQLite dá conta de alguns servidores; para muitos, troque por PostgreSQL. As consultas estão isoladas em `core/stats.py`, então a troca é localizada.
- O dashboard não tem login. Antes de hospedar, coloque autenticação na frente.
- O detector de flood vive na memória do processo: reiniciar o bot zera as janelas em andamento.
- Configuração é por processo, não por servidor. Vários servidores compartilham os mesmos limites de flood.

## Licença

MIT. Veja [LICENSE](LICENSE) — troque o nome do titular pelo seu antes de publicar, se quiser constar como autor.
