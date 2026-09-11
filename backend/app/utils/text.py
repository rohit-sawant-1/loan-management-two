"""
Turning stored values into the words a person actually reads.

Everything in this file exists because of one shape of bug, found twice: the
data was right and the sentence built from it was wrong. A stored value like
`id_proof` is perfect as a database value and wrong in every sentence, and it
reaches people through two doors — the screen, and the AI, which echoes
whatever it is handed.

The browser has its own copy of this in `frontend/src/utils/format.js` as
`label()`, kept deliberately in step with this one. If you add a word here, add
it there (Rule 12: the code and what a customer is told must agree).
"""

# Words that are not simply capitalised once the underscore is gone.
# "id_proof" was becoming "Id proof", which reads as somebody's name rather
# than as the two initials it is.
_ACRONYMS = {
    "id": "ID",
    "kyc": "KYC",
    "emi": "EMI",
    "cibil": "CIBIL",
    "pan": "PAN",
    "ai": "AI",
    "nri": "NRI",
}


def readable(value, *, capitalise: bool = False) -> str:
    """
    A stored enum as a person would say it.

        readable("under_review")                    -> "under review"
        readable("id_proof")                        -> "ID proof"
        readable("under_review", capitalise=True)   -> "Under review"

    `capitalise` is off by default because most call sites drop this into the
    middle of a sentence, where a capital letter would be wrong.
    """
    if value is None or value == "":
        return ""
    words = str(value).replace("_", " ").split(" ")
    out = [_ACRONYMS.get(word.lower(), word) for word in words]
    if capitalise and out and out[0] not in _ACRONYMS.values():
        out[0] = out[0][:1].upper() + out[0][1:]
    return " ".join(out)


def readable_list(values) -> str:
    """A list of stored values as one readable phrase: "ID proof, bank statement"."""
    return ", ".join(readable(v) for v in (values or []))
