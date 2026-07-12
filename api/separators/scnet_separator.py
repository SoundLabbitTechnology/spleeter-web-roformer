"""SCNet four-stem music separator backed by the official MIT implementation."""

import gc
from contextlib import nullcontext
from pathlib import Path
from typing import Dict

import numpy as np
import torch
from django.conf import settings
from spleeter.audio.adapter import AudioAdapter

from api.models import OutputFormat
from api.util import is_output_format_lossy, output_format_to_ext


# Official SCNet base checkpoint published by the authors.  It is downloaded
# lazily into the persistent pretrained-models Docker volume.
SCNET_CHECKPOINT_FILE_ID = '1CdEIIqsoRfHn1SJ7rccPfyYioW3BlXcW'
DEFAULT_MODEL_PATH = Path('pretrained_models/scnet/scnet_base.th')
SOURCES = ('drums', 'bass', 'other', 'vocals')
MODEL_CONFIG = {
    'sources': list(SOURCES),
    'audio_channels': 2,
    'dims': [4, 32, 64, 128],
    'nfft': 4096,
    'hop_size': 1024,
    'win_size': 4096,
    'normalized': True,
    'band_SR': [0.175, 0.392, 0.433],
    'band_stride': [1, 4, 16],
    'band_kernel': [3, 4, 16],
    'conv_depths': [3, 2, 1],
    'compress': 4,
    'conv_kernel': 3,
    'num_dplayer': 6,
    'expand': 1,
}


def try_download_model(model_path: Path) -> None:
    """Download the authors' public base checkpoint if it is not cached."""
    if model_path.is_file():
        return
    try:
        import gdown
    except ImportError as exc:
        raise RuntimeError('SCNet support is not installed in this deployment.') from exc

    model_path.parent.mkdir(parents=True, exist_ok=True)
    print('Downloading the official SCNet base checkpoint if needed...')
    downloaded = gdown.download(id=SCNET_CHECKPOINT_FILE_ID,
                                output=str(model_path), quiet=False)
    if not downloaded or not model_path.is_file():
        raise RuntimeError('Failed to download the official SCNet checkpoint.')


class SCNetSeparator:
    """Separate a mixture into vocals, other, bass, and drums using SCNet."""

    sample_rate = 44100

    def __init__(self, cpu_separation=False,
                 output_format=OutputFormat.MP3_256.value, model_path=None):
        self.device = 'cpu' if cpu_separation else 'cuda'
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.audio_format = output_format_to_ext(output_format)
        self.audio_bitrate = (
            f'{output_format}k' if is_output_format_lossy(output_format) else None
        )
        self.audio_adapter = AudioAdapter.default()

    def get_model(self):
        """Load the pinned official SCNet code and published base checkpoint."""
        try:
            from scnet.SCNet import SCNet
            from scnet.utils import load_model
        except ImportError as exc:
            raise RuntimeError(
                'SCNet source code is missing. Rebuild the Docker image or follow '
                'the SCNet installation instructions in the README.'
            ) from exc

        try_download_model(self.model_path)
        model = SCNet(**MODEL_CONFIG)
        model = load_model(model, self.model_path)
        return model.to(self.device).eval()

    def _load_and_separate(self, input_path: str) -> Dict[str, np.ndarray]:
        try:
            from scnet.apply import apply_model
            from scnet.utils import convert_audio
        except ImportError as exc:
            raise RuntimeError('SCNet source code is missing from this deployment.') from exc

        waveform, source_rate = self.audio_adapter.load(input_path,
                                                        sample_rate=None)
        if waveform.ndim == 1:
            waveform = np.stack((waveform, waveform), axis=-1)
        elif waveform.shape[1] == 1:
            waveform = np.repeat(waveform, 2, axis=1)

        mixture = torch.as_tensor(waveform.T, dtype=torch.float32)
        model = self.get_model()
        try:
            mixture = convert_audio(mixture, source_rate, self.sample_rate,
                                    model.audio_channels)
            reference = mixture.mean(0)
            mean = reference.mean()
            std = reference.std().clamp(min=1e-8)
            mixture = (mixture - mean) / std
            autocast_context = (
                torch.autocast(device_type='cuda', dtype=torch.float16)
                if self.device == 'cuda' and settings.GPU_MIXED_PRECISION
                else nullcontext()
            )
            with torch.inference_mode(), autocast_context:
                estimates = apply_model(
                    model, mixture[None], overlap=settings.SCNET_OVERLAP,
                    progress=False, device=self.device,
                )[0]
            estimates = estimates * std + mean
            return {
                name: estimates[index].cpu().numpy()
                for index, name in enumerate(SOURCES)
            }
        finally:
            del model
            if self.device == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

    def create_static_mix(self, parts: Dict[str, bool], input_path: str,
                          output_path: Path) -> None:
        sources = self._load_and_separate(input_path)
        selected = [sources[name] for name, include in parts.items() if include]
        if not selected:
            raise ValueError('At least one SCNet output must be selected.')
        mixed = np.sum(selected, axis=0).T
        self.audio_adapter.save(str(output_path), mixed, self.sample_rate,
                                self.audio_format, self.audio_bitrate)

    def separate_into_parts(self, input_path: str, output_path: str) -> None:
        output_dir = Path(output_path)
        for name, source in self._load_and_separate(input_path).items():
            filename = output_dir / f'{name}.{self.audio_format}'
            print(f'Exporting {filename.name}...')
            self.audio_adapter.save(str(filename), source.T, self.sample_rate,
                                    self.audio_format, self.audio_bitrate)
