Quero que você crie um projeto completo de "YouTube Downloader" com Python no backend e Bootstrap no frontend. Siga rigorosamente as especificações abaixo.

## OBJETIVO
Aplicação web local (rodando em localhost) onde o usuário cola um link do YouTube (vídeo ou playlist), escolhe se quer baixar apenas áudio ou vídeo+áudio, escolhe o formato/qualidade, e acompanha o progresso de cada item numa lista, com opção de retry individual em caso de falha.

## STACK
- Backend: Python 3.11+, framework FastAPI (preferível a Flask pela facilidade de streaming de progresso).
- Download engine: yt-dlp (não usar pytube, está desatualizado e quebra com frequência).
- Frontend: HTML + Bootstrap 5 + JavaScript puro (sem framework pesado tipo React), usando fetch/polling ou WebSocket para atualizar o progresso em tempo real.
- Persistência simples: não precisa de banco de dados; estado da fila pode ficar em memória no processo do servidor (dict/queue), mas estruture o código de forma que dê pra trocar por SQLite depois sem grande refatoração.

## FLUXO PRINCIPAL
1. Usuário cola uma URL no campo de input e clica em "Adicionar".
2. Backend identifica automaticamente se é um vídeo único ou uma playlist (usar `extract_flat` do yt-dlp para listar os itens da playlist rapidamente, sem baixar).
3. Se for playlist, mostrar a lista de vídeos encontrados com checkbox pra selecionar quais baixar (todos marcados por padrão, com botão "marcar/desmarcar todos").
4. Usuário escolhe:
   - Tipo: "Somente áudio" ou "Vídeo + Áudio"
   - Se áudio: formato (mp3, m4a, wav, opus) e qualidade (ex: 128/192/320 kbps)
   - Se vídeo: formato (mp4, mkv, webm) e qualidade/resolução (ex: melhor disponível, 1080p, 720p, 480p) — respeitando o que realmente está disponível na fonte.
5. Cada item entra numa fila de download com processamento (pode ser sequencial ou com um limite configurável de downloads simultâneos, ex: 2 por vez, pra não tomar rate limit do YouTube).
6. A lista visualizadora mostra, por item: thumbnail pequena, título, status (Na fila / Baixando / Concluído / Erro), barra de progresso (%), velocidade/tamanho quando disponível, e botão de ação (retry se erro, cancelar se pendente/baixando).
7. Ao finalizar, mostrar botão "Abrir pasta de downloads" (ou ao menos o caminho absoluto do arquivo) e permitir download direto do navegador se fizer sentido.

## REQUISITOS FUNCIONAIS DETALHADOS
- Validação de URL: aceitar apenas links válidos do YouTube (youtube.com/watch, youtu.be, playlist?list=, /shorts/). Mostrar mensagem de erro amigável se o link for inválido.
- Sanitização de nome de arquivo: remover caracteres inválidos do título do vídeo antes de salvar (barra, dois pontos, emojis problemáticos, etc.), com limite de tamanho de nome.
- Retry individual: cada item da lista deve poder ser re-tentado sozinho sem precisar reiniciar os outros. Guardar a mensagem de erro específica (vídeo privado, indisponível na região, idade restrita, removido, falha de rede, etc.) e exibir de forma legível.
- Retry automático opcional: até N tentativas automáticas (configurável, padrão 2) antes de marcar como erro definitivo, com pequeno backoff entre tentativas.
- Cancelamento: permitir cancelar um item que ainda não terminou.
- Progresso em tempo real: usar os hooks de progresso do yt-dlp (progress_hooks) e expor via Server-Sent Events (SSE) ou WebSocket para o frontend atualizar as barras de progresso sem precisar dar refresh na página.
- Pasta de destino configurável (campo no frontend ou config padrão em ./downloads), criando a pasta se não existir.
- Evitar duplicar download: se o usuário adicionar a mesma URL/mesmo vídeo que já está na lista ou já foi baixado com sucesso, avisar antes de duplicar.
- Tratamento de erros esperados do yt-dlp: vídeo privado, indisponível, removido, restrito por idade, geo-bloqueado, live não iniciada, playlist privada, etc. Cada erro deve virar uma mensagem clara pro usuário, não um stacktrace cru.
- Log simples em arquivo (ex: app.log) para debug, além do que aparece na UI.
- Disclaimer visível no rodapé sobre uso responsável/respeito aos termos do YouTube e direitos autorais (apenas um aviso textual, não precisa implementar bloqueio nenhum).

## REQUISITOS NÃO FUNCIONAIS
- Código organizado em módulos: ex. `main.py` (rotas FastAPI), `downloader.py` (lógica yt-dlp/fila), `models.py` (schemas Pydantic), `static/` (JS, CSS) e `templates/` (HTML com Bootstrap via CDN).
- Sem uso de comandos shell montados por concatenação de string (evitar risco de injeção); usar a API do yt-dlp diretamente em Python, não subprocess com string crua.
- Tratar concorrência de forma segura (locks ou estrutura thread-safe para a fila compartilhada entre threads/tasks).
- Virtualenv com nome 'venv'.
- Incluir requirements.txt com as versões usadas.
- Incluir um README.md com: como instalar (venv, pip install -r requirements.txt), como rodar (uvicorn main:app --reload), pré-requisitos (ffmpeg instalado no sistema, necessário pro yt-dlp mesclar áudio/vídeo), e prints/descrição rápida do uso.

## FRONTEND (Bootstrap)
- Layout simples e limpo: campo de URL + botão no topo, seletor de tipo (áudio/vídeo) e formato logo abaixo, lista/tabela de downloads abaixo disso (usar Bootstrap table ou list-group com progress bars do Bootstrap).
- Responsivo (funcionar bem em mobile também).
- Feedback visual claro de estado (badges coloridos: azul = na fila, amarelo = baixando, verde = concluído, vermelho = erro).
- Visual minimalista, preto e branco
- Sem necessidade de login/autenticação, é uso pessoal local.

## ENTREGÁVEIS ESPERADOS
- Projeto completo, funcional, pronto pra rodar localmente após `pip install -r requirements.txt` (+ ffmpeg instalado à parte).
- Estrutura de pastas organizada.
- Comentários no código explicando partes não óbvias (principalmente a lógica de fila/progresso).
- Não usar bibliotecas obsoletas ou abandonadas (validar se pytube não é usado em hipótese alguma; usar apenas yt-dlp).

Antes de começar a gerar código, se algo estiver ambíguo (ex: se você prefere WebSocket ou SSE, ou preferência de layout), pode assumir a opção mais simples e seguir em frente — não precisa parar pra perguntar.