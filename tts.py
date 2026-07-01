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

def clean_text(text):
    
    
    # remove markdown formatting
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    
    # remove double spaces
    text = re.sub(r"\n \n", "\n", text)
    text = re.sub(r"\n\n", "\n", text)
    
    # move single tailing word in separate line to upper line
    #text = re.sub(r"[.!?]\s*\n([A-Za-z0-9_]+)[.!?]", r", \1.", text) 
    #text = re.sub(r"([.!?])\s*\n((?:[A-Za-z0-9_\'-]+\s+){0,2}[A-Za-z0-9_\'-]+)[.!?](?=\s*\n|$)]", r", \2.", text)

    # remove *
    text = text.replace("f*ck", "fuck")
    text = text.replace("f*", "fuck")
    text = text.replace("F*ck", "Fuck")
    text = text.replace("F*", "Fuck")
    text = text.replace("*", "")
    
    #remove parenthesis
    text = text.replace("(", "")
    text = text.replace(")", "")
    
    # remove quotas
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    # text = text.replace("‘", '"')
    # text = text.replace("’", '"')
    # text = text.replace('"', '"')
    # text = text.replace("'", "")
    text = re.sub(r"(?<!\w)'([^']+)'(?!\w)", r"\1", text) #test my 'will'.  -> test my will. 
    
    
    # improve omomatopeyas 
    text = text.replace("Hahahahaha", 'Ha ha ha ha ha')
    text = text.replace("Hahahaha", 'Ha ha ha ha')
    text = text.replace("Hahaha", "Ha ha ha")
    text = text.replace("Haha", "Ha ha")
    text = text.replace("Hah", "Ha")
    text = text.replace("Zing!", "Whoosh!")
    text = text.replace("Heh!", "")
    text = re.sub(r'(\w)\1{2,}', r'\1\1', text)  # Boooom -> Boom (etc)
    
    # remove leading -
    # text = re.sub(r'(?m)^-\s*', '', text)
    
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


SPEECH_RE = re.compile(r'"([^"]*)"')
SYSTEM_RE = re.compile(r'^\[([^\]]*)\]', re.MULTILINE)
EXPR_RE = re.compile(r'^\s*([-●◦])\s*(.+)$', re.MULTILINE)

def split_narrative_and_speech(text):
    parts = []

    events = []

    # speech anywhere in text
    for m in SPEECH_RE.finditer(text):
        events.append(("speech", m.start(), m.end(), m.group(1)))

    # expressive/list only at line start
    for m in EXPR_RE.finditer(text):
        events.append(("expressive", m.start(), m.end(), m.group(2).strip().rstrip(".?!,;")))
    
    # expressive/list only at line start
    for m in SYSTEM_RE.finditer(text):
        events.append(("system", m.start(), m.end(), m.group(1)))

    events.sort(key=lambda x: x[1])

    last = 0

    for typ, start, end, content in events:

        # narrative chunk
        if start > last:
            narrative = text[last:start].strip().replace("[", "").replace("]", "")
            if narrative:
                parts.append(("narrative", narrative))

        # normalized output (TTS-friendly)
        if typ == "speech":
            parts.append(("speech", content.strip()))
        elif typ == "system":
            parts.append(("system", content.strip()))
        else:
            parts.append(("expressive", content.strip()))

        last = end

    # trailing narrative
    if last < len(text):
        tail = text[last:].strip().replace("[", "").replace("]", "")
        if tail:
            parts.append(("narrative", tail))

    return parts

def txt_to_audio(text_file, device, voice, out_path=None):
    text_file = Path(text_file)

    # ---- load text ----
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    text = clean_text(text)
    
    # ---- split ----
    chunks = split_narrative_and_speech(text)

    wav_files = []

    # ---- XTTS inference ----
    for i, (chunk_type, chunk) in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk:
            continue

        out_chunk = f"chunk_{i}.wav"

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
		