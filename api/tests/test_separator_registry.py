import unittest

from api.separators.registry import (SIX_STEMS, VOCALS_AND_OTHER,
                                     get_separator_spec, validate_separator_args)


class SeparatorRegistryTests(unittest.TestCase):
    def test_roformer_and_vocal_contracts(self):
        self.assertEqual(get_separator_spec('bs_roformer_6s').stems, SIX_STEMS)
        self.assertEqual(get_separator_spec('mel_roformer_vocals').stems,
                         VOCALS_AND_OTHER)
        self.assertEqual(get_separator_spec('scnet').stems,
                         ('vocals', 'other', 'bass', 'drums'))

    def test_demucs_requires_non_negative_random_shifts(self):
        validate_separator_args('htdemucs', {'random_shifts': 0})
        with self.assertRaisesRegex(ValueError, 'non-negative'):
            validate_separator_args('htdemucs', {'random_shifts': -1})

    def test_retired_models_are_rejected_for_new_jobs(self):
        with self.assertRaisesRegex(ValueError, 'no longer available'):
            validate_separator_args('d3net', {})
