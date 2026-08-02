import { fetchFile, FFmpeg } from '@jeffreyca/ffmpeg';
import JSZip from 'jszip';
import { DynamicMix } from '../models/DynamicMix';
import { PartId } from '../models/PartId';

export type ExportMode = 'mix' | 'zip';

export interface StemPart {
  id: PartId;
  label: string;
  url: string;
  /** Filename used inside ZIP / ffmpeg FS (e.g. vocals.wav). */
  fileName: string;
}

export interface MixStemInput {
  fileName: string;
  url: string;
  /** Gain in dB. -Infinity means silent/excluded. */
  volumeDb: number;
}

const PART_META: { id: PartId; label: string; urlKey: keyof DynamicMix; stemFile: string }[] = [
  { id: 'vocals', label: 'Vocals', urlKey: 'vocals_url', stemFile: 'vocals' },
  { id: 'accomp', label: 'Accompaniment', urlKey: 'other_url', stemFile: 'other' },
  { id: 'bass', label: 'Bass', urlKey: 'bass_url', stemFile: 'bass' },
  { id: 'drums', label: 'Drums', urlKey: 'drums_url', stemFile: 'drums' },
  { id: 'guitar', label: 'Guitar', urlKey: 'guitar_url', stemFile: 'guitar' },
  { id: 'piano', label: 'Piano', urlKey: 'piano_url', stemFile: 'piano' },
];

/**
 * Return stems that exist on the given DynamicMix (non-empty URL).
 */
export function getAvailableStems(mix: DynamicMix): StemPart[] {
  const stems: StemPart[] = [];
  for (const meta of PART_META) {
    const url = mix[meta.urlKey];
    if (typeof url === 'string' && url !== '') {
      const ext = url.split('.').pop() || 'wav';
      stems.push({
        id: meta.id,
        label: meta.label,
        url,
        fileName: `${meta.stemFile}.${ext}`,
      });
    }
  }
  return stems;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Download selected stems as a ZIP archive.
 */
export async function exportStemsZip(
  parts: { url: string; fileName: string }[],
  zipName: string,
  onProgress?: (ratio: number) => void
): Promise<void> {
  if (parts.length === 0) {
    throw new Error('Select at least one part.');
  }

  const zip = new JSZip();
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    const response = await fetch(part.url);
    if (!response.ok) {
      throw new Error(`Failed to fetch ${part.fileName}`);
    }
    const data = await response.arrayBuffer();
    zip.file(part.fileName, data);
    if (onProgress) {
      onProgress((i + 1) / (parts.length + 1));
    }
  }

  const blob = await zip.generateAsync({ type: 'blob' }, metadata => {
    if (onProgress) {
      // Fetch phase used up to ~parts/(parts+1); zip generation fills the rest
      const base = parts.length / (parts.length + 1);
      onProgress(base + (metadata.percent / 100) * (1 / (parts.length + 1)));
    }
  });

  const name = zipName.toLowerCase().endsWith('.zip') ? zipName : `${zipName}.zip`;
  downloadBlob(blob, name);
  if (onProgress) {
    onProgress(1);
  }
}

/**
 * Mix selected stems with ffmpeg.wasm amix and download the result.
 * Only includes parts that are present; volumeDb of -Infinity is treated as 0 gain (silent).
 */
export async function exportSelectedMix(
  ffmpeg: FFmpeg,
  parts: MixStemInput[],
  outName: string,
  bitrate: number,
  onProgress?: (ratio: number) => void
): Promise<void> {
  const active = parts.filter(p => p.volumeDb !== -Infinity);
  if (active.length === 0) {
    throw new Error('Select at least one part.');
  }

  const ext = active[0].fileName.split('.').pop() || 'wav';
  const isLossless = ext === 'wav' || ext === 'flac';
  const outFile = `output.${ext}`;

  for (let i = 0; i < active.length; i++) {
    const part = active[i];
    ffmpeg.FS('writeFile', part.fileName, await fetchFile(part.url));
    if (onProgress) {
      onProgress(((i + 1) / (active.length + 1)) * 0.5);
    }
  }

  const inputArgs: string[] = [];
  const filterParts: string[] = [];
  const mixInputs: string[] = [];

  for (let i = 0; i < active.length; i++) {
    const part = active[i];
    const volArg = part.volumeDb === -Infinity ? '0' : `${part.volumeDb}dB`;
    inputArgs.push('-i', part.fileName);
    filterParts.push(`[${i}:a]volume=${volArg}[a${i}]`);
    mixInputs.push(`[a${i}]`);
  }

  const filterComplex = `${filterParts.join(';')};${mixInputs.join('')}amix=inputs=${
    active.length
  }:duration=first:normalize=0[a]`;

  const args = [
    ...inputArgs,
    '-filter_complex',
    filterComplex,
    isLossless ? '-sample_fmt' : '-b:a',
    isLossless ? 's16' : `${bitrate}k`,
    '-map',
    '[a]',
    outFile,
  ];

  await ffmpeg.run(...args);
  if (onProgress) {
    onProgress(1);
  }

  const data = ffmpeg.FS('readFile', outFile);
  const downloadName = outName.includes('.') ? outName : `${outName}.${ext}`;
  downloadBlob(new Blob([data.buffer]), downloadName);

  // Cleanup FS
  try {
    ffmpeg.FS('unlink', outFile);
    for (const part of active) {
      ffmpeg.FS('unlink', part.fileName);
    }
  } catch (e) {
    // Ignore cleanup errors
  }
}

export const FFMPEG_CORE_PATH = '/static/dist/node_modules/@jeffreyca/ffmpeg.wasm-core/dist/ffmpeg-core.js';
