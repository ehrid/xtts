import re
from num2words import num2words
from typing import List, Literal, Tuple

ChunkType = Literal["narrative", "speech", "system", "expressive", "special"]
Chunk = Tuple[ChunkType, str]
Event = Tuple[ChunkType, int, int, str]

SPEECH_RE = re.compile(r'"([^"]*)"')
SYSTEM_RE = re.compile(r'^\[([^\]]*)\]', re.MULTILINE)
EXPR_RE = re.compile(r'^\s*([-●◦])\s*(.+)$', re.MULTILINE)
SEPARATOR_RE = re.compile(r'^\s*\*\*\s*$', re.MULTILINE)

ABBREVIATIONS = {
    "No.": "number",
    "Mr.": "mister",
    "Mrs.": "missus",
    "Dr.": "doctor",
    "Prof.": "professor",
    "St.": "saint",
    "vs.": "versus",
    "etc.": "et cetera",
    "e.g.": "for example",
    "i.e.": "that is",
    "Lv.": "level",
    "Lvl.": "level"
}
ABBREVIATIONS.update(
    {k.lower(): v for k, v in ABBREVIATIONS.copy().items()}
)

ONOMATOPOEIAS = {
    "Hahahahaha": 'Ha ha ha ha ha',
    "Hahahaha": 'Ha ha ha ha',
    "Hahaha": "Ha ha ha",
    "Haha": "Ha ha",
    "Zing!": "Whoosh!",
    "Wiing": "Whing",
    "Heh!": "",
}
ONOMATOPOEIAS.update(
    {k.lower(): v for k, v in ONOMATOPOEIAS.copy().items()}
)

def preprocess(text: str) -> str:
    # add pause after chapter title
    text = re.sub(r"^(Chapter\s+\d+.*)$", r"\1\n**", text, flags=re.MULTILINE)
    
    # Replace Abbreviations with full text versions
    pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, ABBREVIATIONS)) + r')')
    text = pattern.sub(lambda m: ABBREVIATIONS[m.group(0)], text)
    
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
    text = re.sub(r"(?<!\w)'([^']+)'(?!\w)", r"\1", text) #test my 'will'.  -> test my will. 
    
    # improve omomatopeyas 
    text = re.sub(r'(\w)\1{2,}', r'\1\1', text)  # Boooom -> Boom (etc)   
    pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, ONOMATOPOEIAS)) + r')')
    text = pattern.sub(lambda m: ONOMATOPOEIAS[m.group(0)], text)
    
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
    
    # 1. txt -> 1 - txt
    text = re.sub(r'^(\d+)\.\s+(.+)$', r'\1 - \2', text, flags=re.MULTILINE)
    
    # numbers to text
    text = re.sub(r'(?<=\d)[, ](?=\d{3}(?!\d))', '', text)
    text = re.sub(r"\d+", lambda m: num2words(int(m.group())), text)
    
    # TODO: omomatopeyas replacement by good sounding ones

    return text

def postprocess(text: str) -> str:
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
    
    # Merge short sentences (less than 5 words) into the previous line
    text = re.sub(r'([.!?])\s*\n((?:[A-Za-z0-9_-]+\s+){0,3}[A-Za-z0-9_\'-]+[.!?])(?=\s*\n|\Z)', r'; \2', text)
    
    # remove non letter from the beginning
    text = re.sub(r'^[^A-za-z]+', '', text)
    
    # remove tailing symbols, leve only .?!
    text = re.sub(r"[^A-Za-z?!.\s]+$", "", text)
    
    # collapse multiple symbols between text: text - ???? text -> text - text
    text = re.sub(r'(?<=[A-Za-z])[ \t]*([^\w\s])(?:[ \t]*[^\w\s])+[ \t]*(?=[A-Za-z])', r'\1 ', text)

    # remove *
    text = text.replace("*", "")
    
    # remove any tailing non character for very short sentences
    words = text.strip().split()
    if len(words) < 3:
        return re.sub(r"[^A-Za-z]+$", "", text)
    
    return text.strip();


def split(text: str) -> List[Chunk]:
    parts: List[Chunk] = []
    events: List[Event] = []

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