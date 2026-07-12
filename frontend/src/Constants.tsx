export const DEFAULT_MODEL = 'bs_roformer_6s';
export const DEFAULT_SEPARATION_MODE = 'quality';

export const LOSSY_OUTPUT_FORMATS: [number, string][] = [
  [192, '192 kbps'],
  [256, '256 kbps'],
  [320, '320 kbps'],
];
// Reserve 0 and 1 for backcompat
export const LOSSLESS_OUTPUT_FORMATS: [number, string][] = [
  [0, 'WAV'],
  [1, 'FLAC'],
];
export const DEFAULT_OUTPUT_FORMAT = 256;
export const FADE_DURATION_MS = 300;
export const FADE_DURATION_S = 0.3;

export const ALLOWED_EXTENSIONS = [
  // Lossless
  '.aif',
  '.aifc',
  '.aiff',
  '.flac',
  '.wav',
  // Lossy
  '.aac',
  '.m4a',
  '.mp3',
  '.opus',
  '.weba',
  '.webm',
  // Ogg-Vorbis (Lossy)
  '.ogg',
  '.oga',
  '.mogg',
];
