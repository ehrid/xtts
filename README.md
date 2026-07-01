# XTTS TXT to Audio Converter

A simple Python script that converts text files into speech using **Coqui XTTS**. It supports single text files or entire folders and can clone a voice from a reference WAV file.

## Features

- Convert a single `.txt` file to `.wav`
- Batch process all `.txt` files in a folder
- Voice cloning using a reference WAV file
- Optional custom output directory

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
python tts.py --input example.txt --voice my_voice.wav
```

The script automatically looks for additional voice variants based on the filename of the reference voice:

| File | Used for | Fallback |
|------|----------|----------|
| `my_voice.wav` | Narration | — |
| `my_voice_speech.wav` | Dialogues | `my_voice.wav` |
| `my_voice_system.wav` | System notifications (e.g. `[notification]`) | `my_voice.wav` |
| `my_voice_expressive.wav` | Onomatopoeias and expressive sounds | `my_voice.wav` |

For example, if you specify:

```bash
--voice voices/my_voice.wav
```

the script will automatically try to use:

```
voices/
├── my_voice.wav
├── my_voice_speech.wav
├── my_voice_system.wav
└── my_voice_expressive.wav
```

Any missing variant is automatically replaced with `my_voice.wav`.

### Save output to a different directory

```bash
python tts.py --input ./texts --output_dir ./output
```

### Full example

```bash
python tts.py \
    --input ./texts \
    --voice voice.wav \
    --output_dir ./output
```

## Command-line arguments

| Argument | Description | Required | Default |
|----------|-------------|----------|---------|
| `-in`, `--input` | Path to a `.txt` file or a folder containing `.txt` files | Yes | — |
| `--voice` | Reference WAV file used for XTTS voice cloning | No | `voice.wav` |
| `--output_dir` | Directory where generated WAV files are saved | No | Same directory as the input file |

## Notes

- The reference voice should be a clean, high-quality WAV recording.
- Each input text file generates one output WAV file with the same filename.
- If `--output_dir` is omitted, the output is saved next to the input file.

## License

The code in this repository is licensed under the MIT License.

This project depends on Coqui TTS and XTTS models, which are distributed under their own licenses. Use of those libraries and models is subject to their respective license terms, including any restrictions on commercial use.

Please review the Coqui TTS and model licenses before using this project commercially.

### Voice Samples

The voice samples included in this repository are **not** covered by the MIT License or any other license applicable to the source code.

They are provided **solely for testing, evaluation, and reference purposes**. The included voices are based on recordings of **Mariusz Bonaszewski** and **Jeff Hays**. All rights to these voice recordings and their use remain with their respective rights holders.

The included voice samples **must not be used, redistributed, or incorporated into private, non-commercial, or commercial projects** without obtaining the appropriate rights or permissions from the respective rights holders.
