"""Mel-Band RoFormer vocal isolation separator.

The model code is provided by the MIT-licensed ``bs-roformer`` package.  The
checkpoint is the public Kimberley Jensen vocal model, pinned to an immutable
Hugging Face revision so deployments receive reproducible weights.
"""

import gc
import subprocess
from pathlib import Path
from typing import Dict

import numpy as np
import torch
import torch.nn.functional as F
from bs_roformer import MelBandRoformer
from spleeter.audio.adapter import AudioAdapter

from api.models import OutputFormat
from api.util import is_output_format_lossy, output_format_to_ext


HF_REPO_ID = 'KimberleyJSN/melbandroformer'
HF_REVISION = 'ac9b0614ab3cd7f77219e18ba494dfd93956c348'
HF_MODEL_FILENAME = 'MelBandRoformer.ckpt'

DEFAULT_MODEL_DIR = Path('pretrained_models/mel_roformer')
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / HF_MODEL_FILENAME


MODEL_CONFIG = {
    'dim': 384,
    'depth': 6,
    'stereo': True,
    'num_stems': 1,
    'time_transformer_depth': 1,
    'freq_transformer_depth': 1,
    'num_bands': 60,
    'dim_head': 64,
    'heads': 8,
    'attn_dropout': 0,
    'ff_dropout': 0,
    'flash_attn': True,
    'dim_freqs_in': 1025,
    'sample_rate': 44100,
    'stft_n_fft': 2048,
    'stft_hop_length': 441,
    'stft_win_length': 2048,
    'stft_normalized': False,
    'mask_estimator_depth': 2,
    'multi_stft_resolution_loss_weight': 1.0,
    'multi_stft_resolutions_window_sizes': (4096, 2048, 1024, 512, 256),
    'multi_stft_hop_size': 147,
    'multi_stft_normalized': False,
}


def try_download_model(model_path: Path = DEFAULT_MODEL_PATH):
    """Download the pinned checkpoint the first time it is required."""
    if model_path.is_file():
        return

    model_path.parent.mkdir(parents=True, exist_ok=True)
    print(f'Downloading Mel-RoFormer model from {HF_REPO_ID} if needed...')
    try:
        subprocess.run(
            [
                'hf', 'download', HF_REPO_ID, HF_MODEL_FILENAME,
                '--revision', HF_REVISION,
                '--local-dir', str(model_path.parent),
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError('Failed to download the Mel-RoFormer model') from error

    if not model_path.is_file():
        raise RuntimeError('Mel-RoFormer download completed but the checkpoint is missing')


class MelRoformerSeparator:
    """Separate a mixture into vocals and accompaniment with Mel-RoFormer."""

    sample_rate = 44100
    chunk_size = 352800
    num_overlap = 2

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
        """Construct the exact architecture used by the published checkpoint."""
        try_download_model(self.model_path)
        model = MelBandRoformer(**MODEL_CONFIG)
        checkpoint = torch.load(self.model_path, map_location='cpu')
        model.load_state_dict(checkpoint)
        return model.to(self.device).eval()

    def demix(self, mix: np.ndarray, model) -> Dict[str, np.ndarray]:
        """Infer overlapping chunks and derive accompaniment by mixture subtraction."""
        mix_tensor = torch.as_tensor(mix, dtype=torch.float32)
        original_length = mix_tensor.shape[-1]
        step = self.chunk_size // self.num_overlap
        border = self.chunk_size - step
        fade_size = self.chunk_size // 10

        if original_length > 2 * border and border > 0:
            mix_tensor = F.pad(mix_tensor, (border, border), mode='reflect')

        total_length = mix_tensor.shape[-1]
        window = torch.ones(self.chunk_size, device=self.device)
        window[:fade_size] = torch.linspace(0, 1, fade_size, device=self.device)
        window[-fade_size:] = torch.linspace(1, 0, fade_size, device=self.device)
        result = torch.zeros_like(mix_tensor, device=self.device)
        counter = torch.zeros_like(mix_tensor, device=self.device)

        with torch.inference_mode():
            for position in range(0, total_length, step):
                part = mix_tensor[:, position:position + self.chunk_size]
                length = part.shape[-1]
                if length < self.chunk_size:
                    if length > self.chunk_size // 2 + 1:
                        part = F.pad(part, (0, self.chunk_size - length), mode='reflect')
                    else:
                        part = F.pad(part, (0, self.chunk_size - length))

                vocals = model(part.unsqueeze(0).to(self.device))[0]
                chunk_window = window.clone()
                if position == 0:
                    chunk_window[:fade_size] = 1
                elif position + self.chunk_size >= total_length:
                    chunk_window[-fade_size:] = 1

                result[:, position:position + length] += vocals[:, :length] * chunk_window[:length]
                counter[:, position:position + length] += chunk_window[:length]

        vocals = result / counter.clamp(min=1e-8)
        if original_length > 2 * border and border > 0:
            vocals = vocals[:, border:-border]

        vocals = vocals.cpu().numpy()
        np.nan_to_num(vocals, copy=False)
        return {'vocals': vocals, 'other': mix - vocals}

    def _load_and_separate(self, input_path: str) -> Dict[str, np.ndarray]:
        waveform, _ = self.audio_adapter.load(input_path, sample_rate=self.sample_rate)
        if waveform.ndim == 1:
            waveform = np.stack((waveform, waveform), axis=-1)
        elif waveform.shape[1] == 1:
            waveform = np.repeat(waveform, 2, axis=1)

        model = self.get_model()
        try:
            return self.demix(waveform.T, model)
        finally:
            del model
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            gc.collect()

    def create_static_mix(self, parts: Dict[str, bool], input_path: str,
                          output_path: Path):
        sources = self._load_and_separate(str(input_path))
        selected = [sources[name] for name, include in parts.items() if include]
        if not selected:
            raise ValueError('At least one Mel-RoFormer output must be selected')

        mixed = np.sum(selected, axis=0).T
        self.audio_adapter.save(str(output_path), mixed, self.sample_rate,
                                self.audio_format, self.audio_bitrate)

    def separate_into_parts(self, input_path: str, output_path: str):
        sources = self._load_and_separate(str(input_path))
        output_dir = Path(output_path)
        for name, source in sources.items():
            filename = output_dir / f'{name}.{self.audio_format}'
            print(f'Exporting {filename.name}...')
            self.audio_adapter.save(str(filename), source.T, self.sample_rate,
                                    self.audio_format, self.audio_bitrate)
