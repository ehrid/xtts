import os
import shutil
import struct
import wave
from pathlib import Path
from typing import Sequence, Union, Optional, Dict, Any

import numpy as np
import soundfile as sf


def create_pause(file: Union[str, Path], duration: float = 1, sample_rate: int = 44100) -> None:
    num_samples = int(duration * sample_rate)
    silence = struct.pack("<h", 0) * num_samples

    with wave.open(file, "w") as wav_file:
        wav_file.setnchannels(1)      # mono
        wav_file.setsampwidth(2)      # 16-bit audio
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)


def _get_section_sound(config: Optional[Dict[str, Any]]) -> Optional[Path]:
    if not config:
        return None

    section_sound = config.get("patterns", {}).get("section_sound")
    if not section_sound:
        return None

    path = Path(section_sound)
    return path if path.exists() else None


def create_section_chunk(file: Union[str, Path], config: Optional[Dict[str, Any]]) -> None:
    section_sound = _get_section_sound(config)

    if section_sound:
        shutil.copyfile(section_sound, file)
        return

    create_pause(file)


def wav_duration(path: Union[str, Path]) -> float:
    with wave.open(path, "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def _get_pattern_sound(config: Optional[Dict[str, Any]], pattern_name: str) -> Optional[Path]:
    if not config:
        return None

    sound = config.get("patterns", {}).get(pattern_name)
    if not sound:
        return None

    path = Path(sound)
    return path if path.is_file() else None


def _as_2d(audio: np.ndarray) -> np.ndarray:
    return audio[:, None] if audio.ndim == 1 else audio


def _match_channels(audio: np.ndarray, channels: int) -> np.ndarray:
    audio = _as_2d(audio)

    if audio.shape[1] == channels:
        return audio

    if audio.shape[1] == 1:
        return np.repeat(audio, channels, axis=1)

    if channels == 1:
        return audio.mean(axis=1, keepdims=True)

    return audio[:, :channels]


def _mix_at_offset(base: np.ndarray, overlay: np.ndarray, offset: int) -> np.ndarray:
    channels = max(_as_2d(base).shape[1], _as_2d(overlay).shape[1])
    base = _match_channels(base, channels)
    overlay = _match_channels(overlay, channels)

    end = offset + len(overlay)
    mixed = np.zeros((max(len(base), end), channels), dtype=np.float64)

    mixed[:len(base)] += base
    mixed[offset:end] += overlay

    return np.clip(mixed, -1.0, 1.0)


def _read_audio_file(path: Union[str, Path], expected_sample_rate: Optional[int]) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path)

    if expected_sample_rate and sample_rate != expected_sample_rate:
        raise ValueError(f"Sample rate mismatch in {path}: {sample_rate} != {expected_sample_rate}")

    return audio, sample_rate


def _build_audio_with_opening(
    chunks: Sequence[np.ndarray],
    opening: np.ndarray,
    sample_rate: int,
    ending: Optional[np.ndarray] = None,
    overlap_seconds: float = 2.0,
) -> np.ndarray:
    if not chunks:
        parts = [_as_2d(opening)]
        if ending is not None:
            parts.append(_match_channels(ending, parts[0].shape[1]))
        return np.concatenate(parts, axis=0)

    first_chunk, *remaining_chunks = chunks
    overlap = min(int(overlap_seconds * sample_rate), len(opening))
    first_chunk_offset = max(len(opening) - overlap, 0)

    intro = _mix_at_offset(opening, first_chunk, first_chunk_offset)
    tail = [_match_channels(chunk, intro.shape[1]) for chunk in remaining_chunks]

    if ending is not None:
        tail.append(_match_channels(ending, intro.shape[1]))

    return np.concatenate([intro, *tail], axis=0)


def merge_audio(
    wav_files: Sequence[Union[str, Path]],
    out_path: Union[str, Path],
    config: Optional[Dict[str, Any]] = None,
) -> Union[str, Path]:
    sample_rate: Optional[int] = None
    chunks: list[np.ndarray] = []

    opening_sound = _get_pattern_sound(config, "opening_sound_full") or _get_pattern_sound(config, "opening_sound")
    ending_sound = _get_pattern_sound(config, "ending_sound_full") or _get_pattern_sound(config, "ending_sound")

    if opening_sound:
        opening_audio, sample_rate = _read_audio_file(opening_sound, sample_rate)
    else:
        opening_audio = None

    if ending_sound:
        ending_audio, sample_rate = _read_audio_file(ending_sound, sample_rate)
    else:
        ending_audio = None

    for wav_file in wav_files:
        chunk_audio, sample_rate = _read_audio_file(wav_file, sample_rate)
        chunks.append(chunk_audio)

    if opening_audio is not None and sample_rate is not None:
        final_wav = _build_audio_with_opening(chunks, opening_audio, sample_rate, ending_audio)
    else:
        final_parts = [_as_2d(chunk) for chunk in chunks]

        if ending_audio is not None:
            channels = final_parts[0].shape[1] if final_parts else _as_2d(ending_audio).shape[1]
            final_parts.append(_match_channels(ending_audio, channels))

        final_wav = np.concatenate(final_parts, axis=0)

    sf.write(out_path, final_wav, sample_rate)

    print(f"Saved: {out_path}")

    delete_chunks(wav_files)

    return out_path


def archive_chunks(chunk_files: Sequence[Union[str, Path]], target_dir: Union[str, Path]) -> None:
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for f in chunk_files:
        try:
            src = Path(f)
            dst = target_dir / src.name
            shutil.move(str(src), str(dst))
        except Exception as e:
            print(f"Could not move {f}: {e}")

def delete_chunks(chunk_files: Sequence[Union[str, Path]]) -> None:
    for f in chunk_files:
        try:
            Path(f).unlink()
        except Exception as e:
            print(f"Could not delete {f}: {e}")