import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union, Any

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


def _parse_kwargs(kwargs_str: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not kwargs_str:
        return result
    for part in kwargs_str.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = [x.strip() for x in part.split("=", 1)]
        if v.lower() in ("true", "false"):
            result[k] = v.lower() == "true"
            continue
        try:
            result[k] = int(v)
            continue
        except ValueError:
            pass
        try:
            result[k] = float(v)
            continue
        except ValueError:
            pass
        result[k] = v
    return result


def _build_kwargs_map(config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not config:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    narrative_cfg = config.get("narrative", {})
    ntype = narrative_cfg.get("type", "narrative")
    out[ntype] = _parse_kwargs(narrative_cfg.get("kwargs", ""))

    for v in config.get("voices", []):
        vtype = v.get("type")
        if not vtype:
            continue
        out[vtype] = _parse_kwargs(v.get("kwargs", ""))

    return out


def txt_to_audio(
    tts: TTS,
    text_file: Union[str, Path],
    voice: Dict[str, str],
    out_path: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Union[str, Path]:
    text_file = Path(text_file)
    language = config.get("language", "en") if config else "en"

    # ---- output file ----
    if not out_path:
        out_path = text_file.with_suffix(".wav")

    # ---- load text ----
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    text = preprocess(text, config)

    # ---- split ----
    chunks = split(text, config)
    kwargs_map = _build_kwargs_map(config)

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
            words = chunk.strip().split()
            repetitions = 1 if len(words) > 4 else 5
            speaker_wav = voice.get(chunk_type) or voice.get("narrative")
            tts_to_shortest_file(
                tts,
                text=chunk,
                speaker_wav=speaker_wav,
                language=language,
                file_path=out_chunk,
                attempts=repetitions,
                **kwargs_map.get(chunk_type, {})
            )

        wav_files.append(out_chunk)

    return merge_audio(wav_files, out_path)