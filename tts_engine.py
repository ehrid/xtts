import os
import shutil
import tempfile
from pathlib import Path

from audio_utils import create_pause, merge_audio, wav_duration
from text_utils import preprocess, postprocess, split


def tts_to_shortest_file(
    tts,
    text: str,
    speaker_wav: str,
    language: str,
    file_path: str,
    attempts: int = 5,
    **kwargs,
):
    """
    Generate the same utterance multiple times and keep the shortest result.
    """
    best_tmp = None
    best_duration = float("inf")
    tmp_files = []

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




def txt_to_audio(tts, text_file, device, voice, out_path=None):
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

    wav_files = []

    # ---- XTTS inference ----
    for i, (chunk_type, chunk) in enumerate(chunks):
        chunk = postprocess(chunk)
        out_chunk = f"chunk_{i}.wav"

        if not chunk:
            continue
        elif chunk == "**":
            create_pause(out_chunk)
        else:
            if chunk_type == "system":
                tts.tts_to_file(
                    text=chunk,
                    speaker_wav=voice["system"],
                    language="en",
                    file_path=out_chunk,
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
                    attempts=5,
                    temperature=1.2,
                )
            else:
                tts.tts_to_file(
                    text=chunk,
                    speaker_wav=voice[chunk_type],
                    language="en",
                    file_path=out_chunk
                )

        wav_files.append(out_chunk)

    return merge_audio(wav_files, out_path)