# Bahload

YouTube Downloader local em Python, FastAPI, yt-dlp, Bootstrap 5 e JavaScript puro. Interface em português, seleção de playlists e progresso por Server-Sent Events (SSE).

## Pré-requisitos

- Python **3.11 ou superior**.
- **FFmpeg e FFprobe** instalados e disponíveis no PATH. Confira com `ffmpeg -version` e `ffprobe -version`. Obtenha os binários em https://ffmpeg.org/download.html.
- **Deno (recomendado pelo yt-dlp) ou Node.js compatível com o yt-dlp** no PATH, para resolver os desafios JavaScript do YouTube. O extra `yt-dlp[default]` inclui os scripts EJS. Consulte os requisitos atuais em https://github.com/yt-dlp/yt-dlp#dependencies.
- Internet para acessar o YouTube e carregar o CSS Bootstrap via CDN.

## Instalar e executar

No PowerShell, dentro da pasta do projeto:

```powershell
py -3.14 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Troque `-3.14` pela sua versão instalada, desde que seja 3.11+. Se a ativação estiver bloqueada, use `.\venv\Scripts\python -m pip install -r requirements.txt` e `.\venv\Scripts\python -m uvicorn main:app --reload`.

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Acesse **http://127.0.0.1:8000**. Mantenha o servidor no endereço local padrão. Não há login; o aplicativo não foi projetado para publicação na internet. Use somente **um processo Uvicorn**: a fila é mantida em memória. O modo `--reload` é útil no desenvolvimento; para uso normal, execute `uvicorn main:app` para evitar interromper downloads ao editar arquivos.

## Uso

1. Cole um link de vídeo, Shorts ou playlist e clique em **Adicionar**. Um link de vídeo com `list=` abre a playlist.
2. Revise a lista de thumbnails e títulos; todos vêm selecionados. Use **Marcar/desmarcar todos** ou os checkboxes individuais.
3. Escolha áudio (MP3, M4A, WAV, Opus) ou vídeo com áudio (MP4, MKV, WebM), e a qualidade.
4. Em **Opções de download**, configure a pasta e os retries automáticos (0–5; padrão 2, além da tentativa inicial).
5. Clique em **Baixar selecionados**. A fila mostra status, progresso, bytes, velocidade e tentativas. Erros e cancelamentos podem ser retomados individualmente.
6. Ao concluir, o caminho absoluto fica visível e **Salvar pelo navegador** entrega o arquivo.

A tela tem um painel de entrada no topo e cartões de downloads abaixo. O visual é preto e branco, com badges coloridos de status, barras de progresso e layout adaptado para celulares. O indicador “Atualização ao vivo” informa a conexão SSE; ela reconecta automaticamente.

## Comportamento e limites

- Dois workers por padrão. Configure `BAHLOAD_WORKERS` de 1 a 4 antes de iniciar (PowerShell: `$env:BAHLOAD_WORKERS = '2'`).
- Até 500 itens por consulta de playlist. A interface avisa quando atinge esse limite.
- A resolução é um teto, sem upscale. MP4 e WebM selecionam streams compatíveis com o contêiner; MKV aceita mais combinações. Sem combinação disponível, o item apresenta erro claro.
- Bitrate é a configuração de saída, não melhora a fonte. WAV é PCM, sem seleção de bitrate.
- O progresso acompanha o stream atual: pode reiniciar ao passar do vídeo para o áudio. Conversão/mesclagem aparece como **Processando**, e 100% somente após a saída final.
- Cancelamento é cooperativo pelos hooks: uma operação de rede ou FFmpeg já em andamento pode demorar a terminar. **Cancelando** impede retry até o worker liberar o item. Arquivos parciais são preservados para eventual retomada.
- Backoff entre tentativas: 2, 4, 8… segundos. Downloads concluídos não são repetidos por retry de outro item.
- Duplicatas são detectadas pelo ID do vídeo na sessão, inclusive em links de formatos diferentes e dentro da seleção. A interface pede confirmação explícita para criar cópias.
- Reiniciar o servidor limpa fila/histórico em memória, mas preserva arquivos. Detecção de duplicatas não persiste entre sessões.
- Cada item ganha uma subpasta única no destino. O nome do arquivo usa somente o título sanitizado pelo yt-dlp, limitado a 100 caracteres, e a extensão escolhida. As subpastas evitam sobrescrever arquivos com títulos iguais.
- Conteúdo privado, restrito, removido, bloqueado regionalmente ou lives pode falhar. Não são implementados login, cookies ou contorno de restrições.
- Diagnóstico em `app.log`, com rotação (2 MB e dois backups). Se o YouTube mudar, atualize o yt-dlp e repita os testes: `python -m pip install --upgrade "yt-dlp[default]"`.

## Organização

```text
main.py              Rotas, SSE, ciclo de vida e log
models.py            Validação de URLs e opções
repository.py        Contrato de armazenamento e implementação em memória
downloader.py        Inspeção, fila, workers e hooks yt-dlp
templates/index.html Interface Bootstrap
static/              JavaScript e CSS
tests/               Testes sem downloads externos
downloads/           Destino padrão (ignorado no Git)
```

O repositório fornece snapshots e usa lock reentrante para operações atômicas. Uma implementação SQLite futura deve preservar o contrato e as transações usadas pelo gerenciador; os eventos de cancelamento permanecem no gerenciador.

## Verificação

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check static/app.js
```

Os testes usam simulações da rede e do download para validar fila, retries, cancelamento, URLs, inspeção, arquivos e rotas. Para teste real, instale os pré-requisitos e use um vídeo que você tenha autorização para baixar; confira áudio, mesclagem e saída com um player.

Use com responsabilidade, respeitando os termos do YouTube e os direitos autorais.
