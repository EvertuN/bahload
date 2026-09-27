import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from downloader import DownloadManager, friendly_error, inspect_url
from models import EnqueueRequest, InspectRequest
from repository import MemoryRepository

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger('bahload')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(ROOT / 'app.log', maxBytes=2_000_000, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)


@asynccontextmanager
async def lifespan(app):
    workers = max(1, min(4, int(os.getenv('BAHLOAD_WORKERS', '2'))))
    app.state.manager = DownloadManager(MemoryRepository(), workers)
    app.state.manager.start()
    yield
    app.state.manager.close()


app = FastAPI(title='Bahload', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


@app.middleware('http')
async def local_requests(request: Request, call_next):
    # JSON + custom header prevents other websites from submitting local write requests.
    if request.method == 'POST':
        if request.headers.get('x-bahload') != '1':
            return JSONResponse({'detail': 'Requisição local inválida.'}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Origem não permitida.'}, status_code=403)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse({'detail': 'Dados inválidos. Confira o link, os itens e as opções selecionadas.'}, status_code=422)


@app.get('/')
def index():
    return FileResponse(ROOT / 'templates' / 'index.html')


@app.get('/api/config')
def config():
    return {'destination': str((ROOT / 'downloads').resolve()),
            'ffmpeg': bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
            'javascript': bool(shutil.which('deno') or shutil.which('node'))}


@app.post('/api/inspect')
def inspect(body: InspectRequest):
    try:
        return inspect_url(body.url)
    except Exception as error:
        logger.exception('Inspeção falhou')
        raise HTTPException(400, friendly_error(error)) from error


@app.get('/api/jobs')
def jobs(request: Request):
    return request.app.state.manager.repo.all()


@app.post('/api/jobs')
def enqueue(body: EnqueueRequest, request: Request):
    try:
        added, duplicates = request.app.state.manager.enqueue(body)
        if duplicates:
            return JSONResponse({'detail': 'Vídeos já presentes na fila.', 'duplicates': duplicates}, status_code=409)
        return added
    except (OSError, ValueError) as error:
        raise HTTPException(400, 'Não foi possível criar a pasta de destino. Verifique o caminho e as permissões.') from error


@app.post('/api/jobs/{job_id}/{action}')
def action(job_id: str, action: str, request: Request):
    manager = request.app.state.manager
    try:
        if action == 'retry':
            manager.retry(job_id)
        elif action == 'cancel':
            manager.cancel(job_id)
        else:
            raise HTTPException(404, 'Ação não encontrada.')
        return manager.repo.get(job_id)
    except KeyError as error:
        raise HTTPException(404, 'Item não encontrado.') from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get('/api/jobs/{job_id}/file')
def download_file(job_id: str, request: Request):
    try:
        job = request.app.state.manager.repo.get(job_id)
    except KeyError as error:
        raise HTTPException(404, 'Item não encontrado.') from error
    if job['status'] != 'completed' or not job['path'] or not Path(job['path']).is_file():
        raise HTTPException(404, 'Arquivo ainda não disponível ou removido do disco.')
    return FileResponse(job['path'], filename=Path(job['path']).name)


@app.get('/api/events')
async def events(request: Request):
    async def stream():
        previous = None
        while not await request.is_disconnected():
            data = json.dumps(request.app.state.manager.repo.all(), ensure_ascii=False)
            if data != previous:
                yield f'data: {data}\n\n'
                previous = data
            else:
                yield ': heartbeat\n\n'
            await asyncio.sleep(0.5)
    return StreamingResponse(stream(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
