"""HTTP gateway for text-conditioned separators such as AudioSep or SAM Audio.

The model runtime is intentionally outside this Django/Celery image. The
gateway contract accepts an audio upload and a natural-language ``prompt`` and
returns a WAV containing the requested target. The accompaniment is derived
locally as mixture minus target, so the existing two-stem output contract is
preserved.
"""

import gc
import tempfile
from pathlib import Path
from typing import Dict

import numpy as np
import requests
from django.conf import settings
from spleeter.audio.adapter import AudioAdapter

from api.models import OutputFormat
from api.util import is_output_format_lossy, output_format_to_ext


class SemanticSeparator:
    """Call a separately deployed text-conditioned separation service."""

    sample_rate = 44100

    def __init__(self, prompt: str, cpu_separation=True,
                 output_format=OutputFormat.MP3_256.value):
        self.prompt = prompt.strip()
        self.url = settings.SEMANTIC_SEPARATOR_URL.rstrip('/')
        self.timeout = settings.SEMANTIC_SEPARATOR_TIMEOUT
        self.audio_format = output_format_to_ext(output_format)
        self.audio_bitrate = (
            f'{output_format}k' if is_output_format_lossy(output_format) else None
        )
        self.audio_adapter = AudioAdapter.default()
        if not self.url:
            raise RuntimeError(
                'Text-conditioned separation is not configured. Set '
                'SEMANTIC_SEPARATOR_URL to an AudioSep or SAM Audio gateway.'
            )
        if not self.prompt:
            raise ValueError('A natural-language separation prompt is required.')

    def _load_target(self, input_path: str) -> Dict[str, np.ndarray]:
        mixture, source_rate = self.audio_adapter.load(
            input_path, sample_rate=self.sample_rate)
        if mixture.ndim == 1:
            mixture = np.stack((mixture, mixture), axis=1)
        elif mixture.shape[1] == 1:
            mixture = np.repeat(mixture, 2, axis=1)

        with open(input_path, 'rb') as source:
            response = requests.post(
                f'{self.url}/separate',
                files={'audio': (Path(input_path).name, source, 'audio/wav')},
                data={'prompt': self.prompt},
                timeout=self.timeout,
            )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:500]
            raise RuntimeError(f'Semantic separator failed: {detail}') from exc

        with tempfile.NamedTemporaryFile(suffix='.wav') as target_file:
            target_file.write(response.content)
            target_file.flush()
            target, target_rate = self.audio_adapter.load(
                target_file.name, sample_rate=self.sample_rate)
        if target.ndim == 1:
            target = np.stack((target, target), axis=1)
        elif target.shape[1] == 1:
            target = np.repeat(target, 2, axis=1)
        if target.shape[1] != mixture.shape[1]:
            raise RuntimeError(
                f'Semantic separator returned {target.shape[1]} channels at '
                f'{target_rate} Hz; expected {mixture.shape[1]}.'
            )
        if target.shape[0] < mixture.shape[0]:
            target = np.pad(target, ((0, mixture.shape[0] - target.shape[0]), (0, 0)))
        elif target.shape[0] > mixture.shape[0]:
            target = target[:mixture.shape[0]]
        return {'vocals': target, 'other': mixture - target}

    def create_static_mix(self, parts: Dict[str, bool], input_path: str,
                          output_path) -> None:
        sources = self._load_target(input_path)
        selected = [sources[name] for name, include in parts.items() if include]
        if not selected:
            raise ValueError('At least one semantic output must be selected.')
        mixed = np.sum(selected, axis=0)
        self.audio_adapter.save(str(output_path), mixed, self.sample_rate,
                                self.audio_format, self.audio_bitrate)

    def separate_into_parts(self, input_path: str, output_path: str) -> None:
        output_dir = Path(output_path)
        for name, source in self._load_target(input_path).items():
            filename = output_dir / f'{name}.{self.audio_format}'
            self.audio_adapter.save(str(filename), source, self.sample_rate,
                                    self.audio_format, self.audio_bitrate)
        gc.collect()
