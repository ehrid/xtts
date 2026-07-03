import argparse
import warnings
import json
from pathlib import Path
from typing import Optional, Sequence, Dict, Any

import torch
from TTS.api import TTS

from tts_engine import txt_to_audio



def get_voice_path(voice_path: str, voice_type: str) -> str:
    path = Path(voice_path)
    modified = path.with_name(f"{path.stem}_{voice_type}{path.suffix}")

    return str(modified) if modified.exists() else voice_path
    
def load_config(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_voice_dict(voice_path: str, config: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not config:
        return {"narrative": voice_path}

    voice_dict: Dict[str, str] = {}

    narrative_cfg = config.get("narrative", {})
    narrative_type = narrative_cfg.get("type", "narrative")
    voice_dict[narrative_type] = narrative_cfg.get("voice", voice_path) or voice_path

    for v in config.get("voices", []):
        vtype = v.get("type")
        if not vtype:
            continue
        vvoice = v.get("voice") or get_voice_path(voice_path, str(vtype))
        voice_dict[vtype] = vvoice

    return voice_dict

def run_tts(
    txt_files: Sequence[Path],
    voice_path: str,
    output_dir: Optional[Path],
    config: Optional[Dict[str, Any]],
) -> None:
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    voice_dict = build_voice_dict(voice_path, config)

    # -------------------------
    # Process
    # -------------------------
    for i, file in enumerate(txt_files):
        print(f"\n[{i+1}/{len(txt_files)}] Processing: {file.name}")

        try:
            # determine output path
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                out_file = output_dir / file.with_suffix(".wav").name
            else:
                out_file = file.with_suffix(".wav")

            txt_to_audio(
                tts,
                file,
                voice=voice_dict,
                out_path=out_file,
                config=config,
            )

        except Exception as e:
            print(f"ERROR in {file.name}: {e}")
     
if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    parser = argparse.ArgumentParser(description="XTTS TXT to Audio Converter")

    parser.add_argument(
        "-in",
        "--input",
        required=True,
        help="Path to a .txt file or folder containing .txt files"
    )

    parser.add_argument(
        "--voice",
        default="voice.wav",
        help="Path to speaker reference wav (XTTS voice cloning)"
    )

    parser.add_argument(
        "--output_dir",
        default=None,
        help="Directory to save output wav files (default: same as input file location)"
    )

    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to JSON config file (optional)"
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    voice_path: str = args.voice
    output_dir: Optional[Path] = Path(args.output_dir) if args.output_dir else None
    config: Optional[Dict[str, Any]] = load_config(Path(args.config)) if args.config else None

    # -------------------------
    # Resolve input
    # -------------------------
    if input_path.is_file():
        txt_files: list[Path] = [input_path]
    elif input_path.is_dir():
        txt_files = sorted(input_path.glob("*.txt"))
    else:
        print(f"Invalid path: {input_path}")
        exit(1)

    print(f"Found {len(txt_files)} file(s)")
    
    run_tts(txt_files, voice_path, output_dir, config)
