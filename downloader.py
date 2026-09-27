import logging
import re
import shutil
from pathlib import Path
from queue import Queue
from threading import Event, Thread
from uuid import uuid4

import yt_dlp

from models import EnqueueRequest
from repository import JobRepository

log = logging.getLogger('bahload')


def friendly_error(error):
    message = str(error).lower()
    for patterns, explanation in [
        (('private',), 'Vídeo ou playlist privada. O acesso público não está disponível.'),
        (('age', 'sign in', 'confirm you'), 'O YouTube exige autenticação ou verificação de idade para este conteúdo.'),
        (('country', 'region', 'geo'), 'Conteúdo indisponível nesta região.'),
        (('removed', 'deleted'), 'Este vídeo foi removido.'),
        (('not started', 'premiere', 'live event'), 'A transmissão ou estreia ainda não começou.'),
        (('unavailable', 'not available'), 'Conteúdo indisponível ou sem acesso público.'),
        (('requested format',), 'Não há combinação de áudio e vídeo disponível para esse formato e resolução. Tente MKV ou outra qualidade.'),
        (('ffmpeg', 'ffprobe'), 'Instale FFmpeg e FFprobe e adicione-os ao PATH.'),
        (('permission', 'access is denied'), 'Sem permissão para gravar na pasta de destino.'),
        (('space',), 'Espaço insuficiente no disco.'),
        (('timeout', 'network', 'connection', '429', '403'), 'Falha de rede ou limite do YouTube. Aguarde e tente novamente.'),
    ]:
        if any(pattern in message for pattern in patterns):
            return explanation
    return 'Não foi possível processar este item. Consulte app.log para detalhes e tente novamente.'


def base_options():
    return {'quiet': True, 'no_warnings': True, 'logger': log,
            'socket_timeout': 20, 'retries': 0, 'fragment_retries': 0,
            'js_runtimes': {'deno': {}, 'node': {}}}


def inspect_url(url):
    with yt_dlp.YoutubeDL({**base_options(), 'extract_flat': 'in_playlist',
                          'skip_download': True, 'playlistend': 500}) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise ValueError('Conteúdo indisponível')
    playlist = info.get('_type') == 'playlist'
    entries = info.get('entries', []) if playlist else [info]
    items = []
    for entry in entries:
        if not entry or not re.fullmatch(r'[A-Za-z0-9_-]{11}', entry.get('id', '')):
            continue
        items.append({'video_id': entry['id'], 'title': entry.get('title') or 'Vídeo indisponível',
                      'thumbnail': f'https://i.ytimg.com/vi/{entry["id"]}/default.jpg'})
    if not items:
        raise ValueError('Playlist indisponível ou vazia')
    return {'title': info.get('title', 'YouTube'), 'playlist': playlist, 'items': items,
            'limited': len(items) >= 500}


class Cancelled(Exception):
    pass


class DownloadManager:
    def __init__(self, repository: JobRepository, workers=2):
        self.repo = repository
        self.queue = Queue()
        self.events = {}
        self.stopping = Event()
        self.threads = [Thread(target=self._worker, daemon=True, name=f'download-{i}') for i in range(workers)]

    def start(self):
        for thread in self.threads:
            thread.start()

    def close(self):
        self.stopping.set()
        with self.repo.lock:
            for event in self.events.values():
                event.set()
        for _ in self.threads:
            self.queue.put(None)
        for thread in self.threads:
            thread.join(timeout=1)

    def enqueue(self, request: EnqueueRequest):
        destination = Path(request.options.destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        with self.repo.lock:
            existing = {j['video_id'] for j in self.repo.all()}
            seen, duplicates = set(existing), set()
            for item in request.items:
                if item.video_id in seen:
                    duplicates.add(item.video_id)
                seen.add(item.video_id)
            if duplicates and not request.allow_duplicates:
                return [], sorted(duplicates)
            jobs = []
            for item in request.items:
                job_id = uuid4().hex
                job = {'id': job_id, **item.model_dump(), 'thumbnail': f'https://i.ytimg.com/vi/{item.video_id}/default.jpg',
                       'status': 'queued', 'progress': 0, 'speed': None, 'total': None,
                       'downloaded': 0, 'error': None, 'path': None, 'attempt': 0,
                       'options': {**request.options.model_dump(), 'destination': str(destination)}}
                self.repo.put(job)
                self.events[job_id] = Event()
                self.queue.put(job_id)
                jobs.append(job)
            return jobs, []

    def cancel(self, job_id):
        with self.repo.lock:
            job = self.repo.get(job_id)
            if job['status'] not in ('queued', 'downloading', 'processing', 'retrying'):
                raise ValueError('Este item já terminou.')
            self.events[job_id].set()
            # Active cancellation stays pending until its worker exits, so retry cannot race it.
            self.repo.update(job_id, status='cancelled' if job['status'] == 'queued' else 'cancelling')

    def retry(self, job_id):
        with self.repo.lock:
            if self.repo.get(job_id)['status'] not in ('error', 'cancelled'):
                raise ValueError('Somente itens com erro ou cancelados podem ser retomados.')
            # Claiming queued jobs under the same lock prevents duplicate workers.
            self.events[job_id] = Event()
            self.repo.update(job_id, status='queued', error=None, progress=0, attempt=0, speed=None)
            self.queue.put(job_id)

    def _worker(self):
        while True:
            job_id = self.queue.get()
            try:
                if job_id is None:
                    return
                with self.repo.lock:
                    job = self.repo.get(job_id)
                    if job['status'] != 'queued' or self.stopping.is_set():
                        continue
                    event = self.events[job_id]
                    self.repo.update(job_id, status='downloading')
                for attempt in range(job['options']['retries'] + 1):
                    try:
                        if event.is_set():
                            raise Cancelled()
                        self.repo.update(job_id, status='downloading', attempt=attempt + 1, error=None, progress=0)
                        path = self._download(job, event)
                        with self.repo.lock:
                            if event.is_set():
                                raise Cancelled()
                            self.repo.update(job_id, status='completed', progress=100, path=str(path), speed=None)
                        break
                    except Exception as error:
                        with self.repo.lock:
                            if event.is_set() or isinstance(error, Cancelled):
                                self.repo.update(job_id, status='cancelled', speed=None)
                                break
                            log.exception('Download %s, tentativa %s', job_id, attempt + 1)
                            self.repo.update(job_id, error=friendly_error(error), speed=None,
                                             status='retrying' if attempt < job['options']['retries'] else 'error')
                        if attempt < job['options']['retries'] and event.wait(2 ** (attempt + 1)):
                            self.repo.update(job_id, status='cancelled')
                            break
            finally:
                self.queue.task_done()

    def _download(self, job, event):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            raise RuntimeError('ffmpeg missing')
        options = job['options']
        folder = Path(options['destination']) / job['id']
        folder.mkdir(parents=True, exist_ok=True)

        def hook(data):
            if event.is_set():
                raise Cancelled()
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            downloaded = data.get('downloaded_bytes', 0)
            with self.repo.lock:
                if event.is_set():
                    raise Cancelled()
                self.repo.update(job['id'], status='processing' if data['status'] == 'finished' else 'downloading',
                                 progress=min(99, downloaded / total * 100) if total else 0,
                                 speed=data.get('speed'), total=total, downloaded=downloaded)

        def post_hook(data):
            with self.repo.lock:
                if event.is_set():
                    raise Cancelled()
                self.repo.update(job['id'], status='processing', speed=None)

        opts = {**base_options(), 'noplaylist': True, 'windowsfilenames': True, 'restrictfilenames': True,
                'outtmpl': str(folder / '%(title).100s.%(ext)s'),
                'progress_hooks': [hook], 'postprocessor_hooks': [post_hook],
                'match_filter': lambda info, **kw: 'Live event not started or still live' if info.get('is_live') or info.get('live_status') == 'is_upcoming' else None}
        if options['kind'] == 'audio':
            opts.update(format='bestaudio/best', postprocessors=[{'key': 'FFmpegExtractAudio',
                        'preferredcodec': options['format'], 'preferredquality': str(options['bitrate'])}])
        else:
            cap = '' if options['resolution'] == 'best' else f'[height<={options["resolution"]}]'
            ext = options['format']
            video_filter = '[ext=mp4]' if ext == 'mp4' else '[ext=webm]' if ext == 'webm' else ''
            audio_filter = '[ext=m4a]' if ext == 'mp4' else '[ext=webm]' if ext == 'webm' else ''
            opts.update(format=f'bestvideo{cap}{video_filter}+bestaudio{audio_filter}/best{cap}{video_filter}[vcodec!=none][acodec!=none]',
                        merge_output_format=ext, postprocessors=[{'key': 'FFmpegVideoRemuxer', 'preferedformat': ext}])
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(f'https://www.youtube.com/watch?v={job["video_id"]}', download=True)
        if event.is_set():
            raise Cancelled()
        files = list(folder.glob(f'*.{options["format"]}'))
        if len(files) != 1:
            raise RuntimeError('Arquivo final não encontrado')
        return files[0].resolve()
