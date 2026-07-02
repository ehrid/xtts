import os
import shutil
import struct
import wave
from pathlib import Path

import numpy as np
import soundfile as sf


def create_pause(file, duration=1, sample_rate=44100):
    num_samples = int(duration * sample_rate)
    silence = struct.pack("<h", 0) * num_samples

    with wave.open(file, "w") as wav_file:
        wav_file.setnchannels(1)      # mono
        wav_file.setsampwidth(2)      # 16-bit audio
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def merge_audio(wav_files, out_path):
    audio = []
    sr = None

    for f in wav_files:
        wav, sr = sf.read(f)

        audio.append(wav)

    # FIX 4: pure in-memory concatenation
    final_wav = np.concatenate(audio, axis=0)
    
    sf.write(out_path, final_wav, sr)

    print(f"Saved: {out_path}")
    
    delete_chunks(wav_files)

    return out_path


def archive_chunks(chunk_files, target_dir):
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for f in chunk_files:
        try:
            src = Path(f)
            dst = target_dir / src.name
            shutil.move(str(src), str(dst))
        except Exception as e:
            print(f"Could not move {f}: {e}")

def delete_chunks(chunk_files):
    for f in chunk_files:
        try:
            Path(f).unlink()
        except Exception as e:
            print(f"Could not delete {f}: {e}")