import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union

from TTS.api import TTS
from audio_utils import create_pause, merge_audio, wav_duration
from text_utils import preprocess, postprocess, split


def tts_to_shortest_file(
    tts: TTS,
    text: str,
    speaker_wav: str,
    language: str,
    file_path: Union[str, Path],
    attempts: int = 5,
    **kwargs,
) -> None:
    """
    Generate the same utterance multiple times and keep the shortest result.
    """
    best_tmp: Optional[str] = None
    best_duration: float = float("inf")
    tmp_files: list[str] = []

    try:
        for _ in range(attempts):
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            tmp_files.append(tmp.name)

            tts.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language=language,
                file_path=tmp.name,
                **kwargs,
            )

            duration = wav_duration(tmp.name)

            if duration < best_duration:
                best_duration = duration
                best_tmp = tmp.name

        shutil.move(best_tmp, file_path)

    finally:
        for tmp in tmp_files:
            if tmp != best_tmp and os.path.exists(tmp):
                os.remove(tmp)




def txt_to_audio(
    tts: TTS,
    text_file: Union[str, Path],
    device: str,
    voice: Dict[str, str],
    out_path: Optional[Union[str, Path]] = None
) -> Union[str, Path]:
    text_file = Path(text_file)
    
    # ---- output file ----
    if not out_path:
        out_path = text_file.with_suffix(".wav")

    # ---- load text ----
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    text = preprocess(text)
    
    # ---- split ----
    chunks = split(text)

    wav_files: list[str] = []

    # ---- XTTS inference ----
    for i, (chunk_type, chunk) in enumerate(chunks):
        chunk = postprocess(chunk)
        out_chunk = f"chunk_{i}.wav"

        if not chunk:
            continue
        elif chunk == "**":
            create_pause(out_chunk)
        else:
            words = text.strip().split()
            repetitions = 1 if len(words) > 4 else 5 # generate few time to pick shottest in case of very short chunks
            if chunk_type == "system":
                tts_to_shortest_file(
                    tts,
                    text=chunk,
                    speaker_wav=voice["system"],
                    language="en",
                    file_path=out_chunk,
                    attempts=repetitions,
                    repetition_penalty=2.5,
                    temperature=0.55,
                    speed=0.95
                )
            elif chunk_type == "expressive":       
                tts_to_shortest_file(
                    tts,
                    text=chunk,
                    speaker_wav=voice["expressive"],
                    language="en",
                    file_path=out_chunk,
                    attempts=repetitions,
                    temperature=1.2,
                )
            else:
                tts_to_shortest_file(
                    tts,
                    text=chunk,
                    speaker_wav=voice[chunk_type],
                    language="en",
                    file_path=out_chunk,
                    attempts=repetitions,
                )

        wav_files.append(out_chunk)

    return merge_audio(wav_files, out_path)