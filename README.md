# XTTS TXT to Audio Converter

A simple Python script that converts text files into speech using **Coqui XTTS**. It supports single text files or entire folders and can clone a voice from a reference WAV file.

## Features

- Convert a single `.txt` file to `.wav`
- Batch process all `.txt` files in a folder
- Voice cloning using a reference WAV file

## Requirements

- Python 3.10
- See `requirements.txt` for required Python packages.

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Convert a single text file

```bash
python tts.py -in example.txt
python tts.py --input example.txt
```

### Convert all text files in a folder

```bash
python tts.py --input ./texts
```

### Use a custom voice

```bash
python tts.py --input example.txt -v my_voice.wav
python tts.py --input example.txt --voice my_voice.wav
```

### Save output to a different directory

```bash
python tts.py --input ./texts -out ./output/
python tts.py --input ./texts --output_dir ./output/
```

### Use config file

```bash
python tts.py --input ./texts -c config.json
python tts.py --input ./texts -config config.json
```

### Full example

```bash
python tts.py \
    --input ./texts \
    --voice voice.wav \
    --output_dir ./output
```

## Config file Overview

The configuration file is structured into parameters and three main parts:

| Parameter | Description |
|------|-------------|
| `language` | language for XTTS generation (Optional, default "en") |

```json
{
  "language": "en",
  "patterns": { ... },
  "narrative": { ... },
  "voices": [ ... ]
}
```

### Patterns

Defines global text structure detection rules.

| Field | Description |
|------|-------------|
| `title` | Pattern for matching chapter title (Optional) |
| `section_separator` | Pattern for matching section separator like ** (Optional) |

example:

```json
"patterns": {
  "title": "^(Chapter\\s+\\d+.*)$",
  "section_separator": "^\\s*\\*\\*\\s*$"
}
```


### Narrative (Default Voice)

This voice is used when no specific rule matches.

| Field | Description |
|------|-------------|
| `type` | Logical category |
| `voice` | Reference audio for XTTS cloning |
| `kwargs` | XTTS generation parameters |

example:

```json
"narrative": {
  "type": "narrative",
  "voice": "voice.wav",
  "kwargs": ""
}
```


### Voice Routing Rules

The `voices` array defines how different text patterns are handled.

| Field | Description |
|------|-------------|
| `type` | Logical category |
| `voice` | Reference audio for XTTS cloning |
| `pattern` | Regex used for matching text |
| `multiline` | Whether to use flags=re.MULTILINE or not|
| `kwargs` | XTTS generation parameters |

---
example:

```json
{
  "type":"system",
  "voice":"voice_system.wav",
  "pattern":"^\\[([^\\]]*)\\]",
  "multiline":true,
  "kwargs":"repetition_penalty=2.5, temperature=0.55, speed=0.95"
}
```

## Command-line arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `-in`, `--input` | Path to a `.txt` file or a folder containing `.txt` files | Yes | — |
| `-v`, `--voice` | Reference WAV file used for XTTS voice cloning | No | `voice.wav` |
| `-out`, `--output_dir` | Directory where generated WAV files are saved | No | Same directory as the input file |
| `-c`, `--config` | Path to JSON config file | No | `None` |

## Notes

- The reference voice should be a clean, high-quality WAV recording.
- Each input text file generates one output WAV file with the same filename.
- If `--output_dir` is omitted, the output is saved next to the input file.
