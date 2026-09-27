import re
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


def normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.port:
        raise ValueError('Informe um link válido do YouTube.')
    host = (parsed.hostname or '').lower()
    if host not in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}:
        raise ValueError('Somente links do YouTube são aceitos.')
    query = parse_qs(parsed.query)
    playlist = query.get('list', [''])[0]
    if host != 'youtu.be' and parsed.path in ('/watch', '/playlist') and playlist:
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,100}', playlist):
            raise ValueError('Identificador de playlist inválido.')
        return f'https://www.youtube.com/playlist?list={playlist}'
    video = ''
    if host == 'youtu.be':
        video = parsed.path.strip('/')
    elif parsed.path == '/watch':
        video = query.get('v', [''])[0]
    elif parsed.path.startswith('/shorts/'):
        video = parsed.path.removeprefix('/shorts/').rstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('Use um link de vídeo, Shorts ou playlist do YouTube.')
    return f'https://www.youtube.com/watch?v={video}'


class InspectRequest(BaseModel):
    url: str = Field(max_length=2048)
    _url = field_validator('url')(normalize_url)


class Selection(BaseModel):
    video_id: str = Field(pattern=r'^[A-Za-z0-9_-]{11}$')
    title: str = Field(default='Vídeo', max_length=500)


class Options(BaseModel):
    kind: Literal['audio', 'video'] = 'audio'
    format: Literal['mp3', 'm4a', 'wav', 'opus', 'mp4', 'mkv', 'webm'] = 'mp3'
    bitrate: Literal[128, 192, 320] = 192
    resolution: Literal['best', '1080', '720', '480'] = 'best'
    destination: str = Field(min_length=1, max_length=1000)
    retries: int = Field(default=2, ge=0, le=5)

    @model_validator(mode='after')
    def compatible_format(self):
        allowed = {'mp3', 'm4a', 'wav', 'opus'} if self.kind == 'audio' else {'mp4', 'mkv', 'webm'}
        if self.format not in allowed:
            raise ValueError('Formato incompatível com o tipo escolhido.')
        return self


class EnqueueRequest(BaseModel):
    items: list[Selection] = Field(min_length=1, max_length=500)
    options: Options
    allow_duplicates: bool = False
