import re
from num2words import num2words
from typing import List, Tuple, Optional, Dict, Any

Chunk = Tuple[str, str]
Event = Tuple[str, int, int, str]

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

def _normalize_regex(pattern: str) -> str:
    # JSON has no r-prefix; keep regex usable after loading from JSON.
    # Example JSON: "^\\s*\\*\\*\\s*$" -> Python regex: "^\s*\*\*\s*$"
    try:
        return pattern.encode("utf-8").decode("unicode_escape")
    except Exception:
        return pattern

def _time_unit(value: int, singular: str, plural: str) -> str:
    return singular if value == 1 else plural

def _time_to_words(match: re.Match[str]) -> str:
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second = match.groupdict().get("second")

    parts = [
        f"{num2words(hour)} {_time_unit(hour, 'hour', 'hours')}",
        f"{num2words(minute)} {_time_unit(minute, 'minute', 'minutes')}",
    ]

    if second is not None:
        second_value = int(second)
        parts.append(f"{num2words(second_value)} {_time_unit(second_value, 'second', 'seconds')}")

    return " ".join(parts)

def preprocess(text: str, config: Optional[Dict[str, Any]] = None) -> str:
    if config:
        # add pause after chapter title (configurable)
        title_pattern = config.get("patterns", {}).get("title")
        if title_pattern:
            title_pattern = _normalize_regex(title_pattern)
            text = re.sub(title_pattern, r"\1\n**", text, flags=re.MULTILINE)

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

    # time to speech: HH:mm:ss first, then HH:mm
    text = re.sub(
        r'(?<!\d)(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d):(?P<second>[0-5]\d)(?!\d)',
        _time_to_words,
        text,
    )
    text = re.sub(
        r'(?<!\d)(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d)(?!\d)',
        _time_to_words,
        text,
    )

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


def split(text: str, config: Optional[Dict[str, Any]] = None) -> List[Chunk]:
    parts: List[Chunk] = []
    events: List[Event] = []

    # No config => no splitting, all narrative
    if not config:
        narrative = text.strip()
        return [("narrative", narrative)] if narrative else []

    patterns_cfg = config.get("patterns", {}) if isinstance(config, dict) else {}
    voices_cfg = config.get("voices", []) if isinstance(config, dict) else []

    # Optional separator
    section_separator = patterns_cfg.get("section_separator")
    if section_separator:
        sep_re = re.compile(_normalize_regex(section_separator), re.MULTILINE)
        for m in sep_re.finditer(text):
            events.append(("special", m.start(), m.end(), "**"))

    # Dynamic voice patterns (flexible for future types)
    for v in voices_cfg:
        vtype = v.get("type")
        vpattern = v.get("pattern")
        if not vtype or not vpattern:
            continue

        flags = re.MULTILINE if bool(v.get("multiline", False)) else 0
        cre = re.compile(_normalize_regex(vpattern), flags)

        for m in cre.finditer(text):
            content = m.group(1) if (m.lastindex and m.lastindex >= 1) else m.group(0)
            events.append((vtype, m.start(), m.end(), content))

    # Config present but nothing to split with => narrative only
    if not events:
        narrative = text.strip()
        return [("narrative", narrative)] if narrative else []

    events.sort(key=lambda x: x[1])
    last = 0

    for typ, start, end, content in events:
        if start > last:
            narrative = text[last:start].strip()
            if narrative:
                parts.append(("narrative", narrative))

        parts.append((typ, content.strip()))
        last = end

    if last < len(text):
        tail = text[last:].strip()
        if tail:
            parts.append(("narrative", tail))

    return parts