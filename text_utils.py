import re
from functools import lru_cache
from importlib import import_module
from num2words import num2words
from typing import List, Tuple, Optional, Dict, Any

Chunk = Tuple[str, str]
Event = Tuple[str, int, int, str]

# Python's re is Unicode-aware by default.
# Any Unicode letter, excluding digits.
_UNICODE_LETTER = r"[^\W\d]"

# Any Unicode letter/digit plus apostrophes
_READABLE_WORD = r"(?:[^\W]|')+"

# Anything that is not a Unicode letter
_NON_UNICODE_LETTER = r"(?:[^\w]|\d)"

@lru_cache(maxsize=None)
def _load_localized_dict(prefix: str, constant: str, language: str) -> Dict[str, str]:
    try:
        module = import_module(f"{prefix}_{language}")
        value = getattr(module, constant, {})
        return value if isinstance(value, dict) else {}
    except ModuleNotFoundError:
        return {}


def _get_language(config: Optional[Dict[str, Any]]) -> str:
    return str(config.get("language", "en")) if config else "en"

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
    language = _get_language(config)
    abbreviations = _load_localized_dict("abbreviations", "ABBREVIATIONS", language)
    onomatopoeias = _load_localized_dict("onomatopoeias", "ONOMATOPOEIAS", language)

    if config:
        # add pause after chapter title (configurable)
        title_pattern = config.get("patterns", {}).get("title")
        if title_pattern:
            title_pattern = _normalize_regex(title_pattern)
            text = re.sub(title_pattern, r"\1\n**", text, flags=re.MULTILINE)

    # Replace Abbreviations with full text versions
    if abbreviations:
        pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, abbreviations)) + r')')
        text = pattern.sub(lambda m: abbreviations[m.group(0)], text)

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
    if onomatopoeias:
        pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, onomatopoeias)) + r')')
        text = pattern.sub(lambda m: onomatopoeias[m.group(0)], text)

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
        return text.strip()
    
    # Normalize whitespace, then put each sentence on its own line.
    # This makes the short-sentence merge work consistently even when input has no \n.
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"([.!?]+)\s*", r"\1\n", text).strip()

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
    text = re.sub(
        rf'([.!?])\s*\n((?:{_READABLE_WORD}\s+){{0,3}}{_READABLE_WORD}[.!?])(?=\s*\n|\Z)',
        r'; \2',
        text,
    )

    # remove non letter from the beginning
    text = re.sub(rf'^{_NON_UNICODE_LETTER}+', '', text)

    # remove tailing symbols, leave only .?! plus _ and -
    text = re.sub(rf"(?:(?!{_UNICODE_LETTER}|[_-]|[?!.\s]).)+$", "", text)

    # collapse multiple symbols between text: text - ???? text -> text - text
    text = re.sub(
        rf'(?<={_UNICODE_LETTER})[ \t]*([^\w\s-])(?:[ \t]*[^\w\s-])+[ \t]*(?={_UNICODE_LETTER})',
        r'\1 ',
        text,
    )

    # remove *
    text = text.replace("*", "")

    return text.strip()

def remove_tailing_non_character(text: str, length_limit: int = 4) -> str:
    # remove any tailing non character for very short sentences
    words = text.strip().split()
    if len(words) > length_limit:
        return text
    return re.sub(rf"{_NON_UNICODE_LETTER}+$", "", text)



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