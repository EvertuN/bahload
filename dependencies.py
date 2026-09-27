"""Resolve native FFmpeg binaries consistently for the UI and yt-dlp."""
import os
from pathlib import Path
import shutil


WINDOWS_FFMPEG_DIRECTORY = Path('C:/ffmpeg/bin')


def find_ffmpeg_directory() -> str | None:
    suffix = '.exe' if os.name == 'nt' else ''
    configured = os.environ.get('BAHLOAD_FFMPEG_DIR')
    candidates = []
    if configured:
        candidates.append(Path(configured.strip('"')).expanduser())
    # Require native executables rather than npm's .cmd wrappers on Windows.
    executable = shutil.which(f'ffmpeg{suffix}')
    if executable:
        candidates.append(Path(executable).parent)
    if os.name == 'nt':
        # A running terminal may have inherited PATH before FFmpeg was installed.
        candidates.append(WINDOWS_FFMPEG_DIRECTORY)
    for directory in candidates:
        if all((directory / f'{name}{suffix}').is_file() for name in ('ffmpeg', 'ffprobe')):
            return str(directory.resolve())
    return None
