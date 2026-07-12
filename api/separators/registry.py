"""Single source of truth for supported source-separation model contracts.

The database stores the stable string identifiers below.  Keeping stem layouts,
runtime requirements, and construction here prevents the task, serializer, and
UI-facing metadata from drifting when a new model is added.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

FOUR_STEMS = ('vocals', 'other', 'bass', 'drums')
FIVE_STEMS_GUITAR = ('vocals', 'other', 'guitar', 'bass', 'drums')
FIVE_STEMS_PIANO = ('vocals', 'other', 'piano', 'bass', 'drums')
SIX_STEMS = ('vocals', 'other', 'piano', 'guitar', 'bass', 'drums')
VOCALS_AND_OTHER = ('vocals', 'other')


@dataclass(frozen=True)
class SeparatorSpec:
    """The stable public contract for one selectable separation model."""

    identifier: str
    label: str
    family: str
    stems: Tuple[str, ...]
    enabled: bool = True
    requires_random_shifts: bool = False
    roformer_stem_mode: str = ''

    @property
    def stem_description(self) -> str:
        if self.stems == VOCALS_AND_OTHER:
            return 'Vocals + accompaniment'
        return f'{len(self.stems)} stems'


def _spec(identifier, label, family, stems, **kwargs):
    return SeparatorSpec(identifier, label, family, tuple(stems), **kwargs)


_SPECS = (
    _spec('spleeter', 'Spleeter', 'spleeter', FOUR_STEMS),
    _spec('spleeter_5stems', 'Spleeter with Piano', 'spleeter', FIVE_STEMS_PIANO),
    _spec('bs_roformer', 'BS-RoFormer 4-stem', 'bs_roformer', FOUR_STEMS,
          roformer_stem_mode='4stem'),
    _spec('bs_roformer_5s_guitar', 'BS-RoFormer 5-stem (Guitar)', 'bs_roformer',
          FIVE_STEMS_GUITAR, roformer_stem_mode='5stem_guitar'),
    _spec('bs_roformer_5s_piano', 'BS-RoFormer 5-stem (Piano)', 'bs_roformer',
          FIVE_STEMS_PIANO, roformer_stem_mode='5stem_piano'),
    _spec('bs_roformer_6s', 'BS-RoFormer 6-stem', 'bs_roformer', SIX_STEMS,
          roformer_stem_mode='6stem'),
    _spec('mel_roformer_vocals', 'Mel-RoFormer Vocal Isolation', 'mel_roformer',
          VOCALS_AND_OTHER),
    _spec('htdemucs', 'Demucs v4', 'demucs', FOUR_STEMS, requires_random_shifts=True),
    _spec('htdemucs_ft', 'Demucs v4 Fine-tuned', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('hdemucs_mmi', 'Demucs v3 MMI', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('mdx', 'Demucs v3', 'demucs', FOUR_STEMS, requires_random_shifts=True),
    _spec('mdx_extra', 'Demucs v3 Extra', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('mdx_q', 'Demucs v3 Quantized', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('mdx_extra_q', 'Demucs v3 Extra Quantized', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('demucs', 'Demucs', 'demucs', FOUR_STEMS, requires_random_shifts=True),
    _spec('demucs48_hq', 'Demucs HQ', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('demucs_extra', 'Demucs Extra', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('demucs_quantized', 'Demucs Quantized', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('tasnet', 'Tasnet', 'demucs', FOUR_STEMS, requires_random_shifts=True),
    _spec('tasnet_extra', 'Tasnet Extra', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('light', 'Demucs Light', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    _spec('light_extra', 'Demucs Light Extra', 'demucs', FOUR_STEMS,
          requires_random_shifts=True),
    # Existing jobs retain playback metadata, but new jobs cannot select these.
    _spec('d3net', 'D3Net', 'legacy', FOUR_STEMS, enabled=False),
    _spec('xumx', 'X-UMX', 'legacy', FOUR_STEMS, enabled=False),
)

SEPARATORS: Dict[str, SeparatorSpec] = {spec.identifier: spec for spec in _SPECS}


def get_separator_spec(identifier: str) -> SeparatorSpec:
    """Return a registered model contract or raise a useful request error."""
    try:
        return SEPARATORS[identifier]
    except KeyError as exc:
        raise ValueError(f'Unknown separator "{identifier}".') from exc


def validate_separator_args(identifier: str, args: Dict) -> None:
    """Validate per-model arguments shared by both mix serializers."""
    spec = get_separator_spec(identifier)
    if not spec.enabled:
        raise ValueError(f'{spec.label} is no longer available for new separations.')
    if spec.requires_random_shifts:
        try:
            shifts = args['random_shifts']
        except KeyError as exc:
            raise ValueError("Must include 'random_shifts' argument.") from exc
        if not isinstance(shifts, int) or shifts < 0:
            raise ValueError('Random shifts must be a non-negative integer.')


def build_separator(identifier: str, args: Dict, bitrate: int, cpu_separation: bool,
                    settings):
    """Construct a separator lazily so optional ML dependencies stay isolated."""
    validate_separator_args(identifier, args)
    spec = get_separator_spec(identifier)
    if spec.family == 'spleeter':
        from .spleeter_separator import SpleeterSeparator
        return SpleeterSeparator(cpu_separation, bitrate,
                                 spec.identifier == 'spleeter_5stems')
    if spec.family == 'bs_roformer':
        from .bs_roformer_separator import BSRoformerSeparator
        return BSRoformerSeparator(cpu_separation=cpu_separation, output_format=bitrate,
                                   batch_size=settings.ROFORMER_BATCH_SIZE,
                                   overlap=settings.ROFORMER_NUM_OVERLAP,
                                   stem_mode=spec.roformer_stem_mode)
    if spec.family == 'mel_roformer':
        from .mel_roformer_separator import MelRoformerSeparator
        return MelRoformerSeparator(cpu_separation=cpu_separation, output_format=bitrate,
                                    num_overlap=settings.MEL_ROFORMER_NUM_OVERLAP)
    if spec.family == 'demucs':
        from .demucs_separator import DemucsSeparator
        return DemucsSeparator(spec.identifier, cpu_separation, bitrate,
                               args['random_shifts'])
    raise ValueError(f'{spec.label} is no longer available for new separations.')
