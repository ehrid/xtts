import re
import numpy as np
import torch
import soundfile as sf
import librosa
import shutil
from pathlib import Path
from TTS.api import TTS
import warnings
import argparse
import wave
import struct
from num2words import num2words

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

def preprocess(text):  
    # add pause after chapter title
    text = re.sub(r"^(Chapter\s+\d+.*)$", r"\1\n**", text, flags=re.MULTILINE)
    
    # remove double spaces
    text = re.sub(r"[ \t]+", " ", text)
        
    # remove *
    text = text.replace("f*ck", "fuck")
    text = text.replace("f*", "fuck")
    text = text.replace("F*ck", "Fuck")
    text = text.replace("F*", "Fuck")
    
    # remove quotas
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    # text = text.replace("‘", '"')
    # text = text.replace("’", '"')
    # text = text.replace('"', '"')
    # text = text.replace("'", "")
    
    # improve omomatopeyas 
    text = text.replace("Hahahahaha", 'Ha ha ha ha ha')
    text = text.replace("Hahahaha", 'Ha ha ha ha')
    text = text.replace("Hahaha", "Ha ha ha")
    text = text.replace("Haha", "Ha ha")
    text = text.replace("Hah", "Ha")
    text = text.replace("Zing!", "Whoosh!")
    text = text.replace("Heh!", "")
    text = re.sub(r'(\w)\1{2,}', r'\1\1', text)  # Boooom -> Boom (etc)   
    
    # normalize ...
    text = re.sub(r'\.{4,}', '...', text)
    text = text.replace("… …", "...")
    text = text.replace("…", "...")
    text = text.replace("... ", "...")
    text = text.replace("...'", "'")
    text = text.replace('..."', '"')
    text = text.replace('"...', '"')
    text = text.replace("'...", "'")
    text = text.replace("...?", "?")
    text = text.replace("...!", "!")
    text = text.replace("...,", ",")
    text = re.sub(r"(?m)^\.\.\.\s*", "", text) # ...txt -> txt
    text = re.sub(r"\.\.\.(?=\s*$)", ".", text) # txt... -> txt.
    text = text.replace("...", ", ")
    
    # txt,txt -> txt, txt
    text = re.sub(r"(\S),(\S)", r"\1, \2", text)
    text = re.sub(r"(\S),  (\S)", r"\1, \2", text)
    
    # numbers to text
    text = re.sub(r'(?<=\d)[, ](?=\d{3}(?!\d))', '', text)
    text = re.sub(r"\d+", lambda m: num2words(int(m.group())), text)

    return text

def postprocess(text):
    if text.strip() == "**":
        return text.strip();
    
    #remove parenthesis
    text = text.replace("(", "")
    text = text.replace(")", "")
    text = text.replace("[", "")
    text = text.replace("]", "")
    text = text.replace("{", "")
    text = text.replace("}", "")
    
    #remove quotas
    text = text.replace('"', "")
    text = text.replace("'", "")
    
    # remove non letter from the beginning
    text = re.sub(r'^[^A-za-z]+', '', text)
    
    # remove tailing symbols, leve only .?!
    text = re.sub(r"[^A-Za-z?!.\s]+$", "", text)

    # remove *
    text = text.replace("*", "")
    
    # remove any tailing non character for very short sentences
    words = text.strip().split()
    if len(words) < 3:
        return re.sub(r"[^A-Za-z]+$", "", text)
    
    return text.strip();

SPEECH_RE = re.compile(r'"([^"]*)"')
SYSTEM_RE = re.compile(r'^\[([^\]]*)\]', re.MULTILINE)
EXPR_RE = re.compile(r'^\s*([-●◦])\s*(.+)$', re.MULTILINE)
SEPARATOR_RE = re.compile(r'^\s*\*\*\s*$', re.MULTILINE)

def split(text):
    parts = []

    events = []
    
    # system only at line start
    for m in SYSTEM_RE.finditer(text):
        events.append(("system", m.start(), m.end(), m.group(1)))

    # speech anywhere in text
    for m in SPEECH_RE.finditer(text):
        events.append(("speech", m.start(), m.end(), m.group(1)))

    # expressive/list only at line start
    for m in EXPR_RE.finditer(text):
        events.append(("expressive", m.start(), m.end(), m.group(0)))
        
    # text separators
    for m in SEPARATOR_RE.finditer(text):
        events.append(("special", m.start(), m.end(), "**"))

    events.sort(key=lambda x: x[1])

    last = 0

    for typ, start, end, content in events:

        # narrative chunk
        if start > last:
            narrative = text[last:start].strip()
            if narrative:
                parts.append(("narrative", narrative))

        # normalized output (TTS-friendly)
        if typ == "speech":
            parts.append(("speech", content.strip()))
        elif typ == "system":
            parts.append(("system", content.strip()))
        elif typ == "special":
            parts.append(("special", content.strip()))
        else:
            parts.append(("expressive", content.strip()))

        last = end

    # trailing narrative
    if last < len(text):
        tail = text[last:].strip()
        if tail:
            parts.append(("narrative", tail))

    return parts


def create_pause(file, duration=1, sample_rate=44100):
    num_samples = int(duration * sample_rate)
    silence = struct.pack("<h", 0) * num_samples

    with wave.open(file, "w") as wav_file:
        wav_file.setnchannels(1)      # mono
        wav_file.setsampwidth(2)      # 16-bit audio
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)

def txt_to_audio(text_file, device, voice, out_path=None):
    text_file = Path(text_file)

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
                tts.tts_to_file(
                    text=chunk,
                    speaker_wav=voice["expressive"],
                    language="en",
                    file_path=out_chunk,
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

    # ---- merge audio ----
    audio = []
    sr = None

    for f in wav_files:
        wav, sr = sf.read(f)

        audio.append(wav)

    # FIX 4: pure in-memory concatenation
    final_wav = np.concatenate(audio, axis=0)

    # ---- output file ----
    if not out_path:
        out_path = text_file.with_suffix(".wav")

    sf.write(out_path, final_wav, sr)

    print(f"Saved: {out_path}")
    
    # ---- archive chunks instead of deleting ----
    #archive_dir = text_file.parent / (text_file.stem + "_chunks")
    #archive_chunks(wav_files, archive_dir)
    
    delete_chunks(wav_files)

    return out_path

def get_voice_path(voice_path: str, voice_type: str) -> str:
    path = Path(voice_path)
    modified = path.with_name(f"{path.stem}_{voice_type}{path.suffix}")

    return str(modified) if modified.exists() else voice_path
     
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

    args = parser.parse_args()

    input_path = Path(args.input)
    voice_path = args.voice
    output_dir = Path(args.output_dir) if args.output_dir else None

    # -------------------------
    # Resolve input
    # -------------------------
    if input_path.is_file():
        txt_files = [input_path]

    elif input_path.is_dir():
        txt_files = sorted(input_path.glob("*.txt"))

    else:
        print(f"Invalid path: {input_path}")
        exit(1)

    print(f"Found {len(txt_files)} file(s)")

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    
    voice_dict = {
            "narrative": voice_path,
            "speech": get_voice_path(voice_path, "speech"),
            "system": get_voice_path(voice_path, "system"),
            "expressive": get_voice_path(voice_path, "expressive"),
        }

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
                file,
                device,
                voice=voice_dict,
                out_path=out_file
            )

        except Exception as e:
            print(f"ERROR in {file.name}: {e}")
		