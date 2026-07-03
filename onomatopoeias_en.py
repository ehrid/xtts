from typing import Dict

ONOMATOPOEIAS: Dict[str, str] = {
    "Hahahahaha": "Ha ha ha ha ha",
    "Hahahaha": "Ha ha ha ha",
    "Hahaha": "Ha ha ha",
    "Haha": "Ha ha",
    "Zing!": "Whoosh!",
    "Wiing": "Whing",
    "Heh!": "",
}

ONOMATOPOEIAS.update({k.lower(): v for k, v in ONOMATOPOEIAS.copy().items()})
