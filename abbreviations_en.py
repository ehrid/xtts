from typing import Dict

ABBREVIATIONS: Dict[str, str] = {
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
    "Lvl.": "level",
}

ABBREVIATIONS.update({k.lower(): v for k, v in ABBREVIATIONS.copy().items()})
