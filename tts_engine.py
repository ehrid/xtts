import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union, Any

from TTS.api import TTS
from audio_utils import create_section_chunk, merge_audio, wav_duration
from text_utils import preprocess, postprocess, split, remove_tailing_non_character

SHORT_TEXT_LENGTH_LIMIT = 4


def tts_to_shortest_file(
    tts: TTS,
    text: str,
    speaker_wav: str,
    language: str,
    file_path: Union[str, Path],
    attempts: int = 3,
    **kwargs,
) -> None:
    """
    Generate the same utterance multiple times and keep the shortest result.
    For short text, also try punctuation variants to avoid bad endings.
    """
    best_tmp: Optional[str] = None
    best_duration: float = float("inf")
    tmp_files: list[str] = []

    texts = [text]

    if attempts > 1:
        cleaned_text = remove_tailing_non_character(text, SHORT_TEXT_LENGTH_LIMIT).strip()
        texts = [
            cleaned_text,
            f"{cleaned_text}.",
            f"{cleaned_text},",
        ]

    try:
        for candidate_text in texts:
            for _ in range(attempts):
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.close()
                tmp_files.append(tmp.name)

                tts.tts_to_file(
                    text=candidate_text,
                    speaker_wav=speaker_wav,
                    language=language,
                    file_path=tmp.name,
                    **kwargs,
                )

                duration = wav_duration(tmp.name)

                if duration < best_duration:
                    best_duration = duration
                    best_tmp = tmp.name

        if best_tmp is None:
            raise RuntimeError("No TTS output was generated")

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


def _prepare_ending_sound(config: Optional[Dict[str, Any]], text_file: Path) -> None:
    if not config:
        return

    patterns = config.get("patterns")
    if not isinstance(patterns, dict):
        return

    ending_sound = patterns.get("ending_sound")
    if not ending_sound:
        return

    ending_path = Path(ending_sound)
    if ending_path.is_dir():
        patterns["ending_sound_full"] = str(ending_path / text_file.with_suffix(".wav").name)

def _prepare_opening_sound(config: Optional[Dict[str, Any]], text_file: Path) -> None:
    if not config:
        return

    patterns = config.get("patterns")
    if not isinstance(patterns, dict):
        return

    opening_sound = patterns.get("opening_sound")
    if not opening_sound:
        return

    opening_path = Path(opening_sound)
    if opening_path.is_dir():
        patterns["opening_sound_full"] = str(opening_path / text_file.with_suffix(".wav").name)

def txt_to_audio(
    tts: TTS,
    text_file: Union[str, Path],
    voice: Dict[str, str],
    out_path: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Union[str, Path]:
    text_file = Path(text_file)
    language = config.get("language", "en") if config else "en"
    _prepare_ending_sound(config, text_file)
    _prepare_opening_sound(config, text_file)

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
            create_section_chunk(out_chunk, config)
        else:
            words = chunk.strip().split()
            repetitions = 1 if len(words) > SHORT_TEXT_LENGTH_LIMIT else 3
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

    return merge_audio(wav_files, out_path, config)