"""Zero-dependency near-duplicate text fingerprinting.

Design: 64-bit SimHash over 3-token shingles of the normalized text. SimHash
keeps near-duplicate texts within a few bits of each other, so a 16-hex-char
fingerprint is enough to compare any pair later without storing the body
itself.
"""

import hashlib
import html
import re

# Texts shorter than this (after normalization) carry too little signal to
# distinguish real matches from boilerplate - skip them.
FINGERPRINT_MIN_TEXT = 200

# Similarity at or above this is reported as a possible near-duplicate.
# 0.92 = at most 5 of 64 SimHash bits differ - near-verbatim bodies.
CROSSLIST_THRESHOLD = 0.92

_TAG_RE = re.compile(r"<[^>]*>")
_ENTITY_RE = re.compile(r"&[a-z#0-9]+;", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")
_MULTISPACE_RE = re.compile(r" {2,}")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{16}$")


def normalize_text(text: str) -> str:
    normalized = (text or "").lower()
    normalized = _TAG_RE.sub(" ", normalized)
    normalized = _ENTITY_RE.sub(" ", normalized)
    normalized = _URL_RE.sub(" ", normalized)
    normalized = "".join(ch if ch.isalnum() else " " for ch in normalized)
    normalized = _MULTISPACE_RE.sub(" ", normalized)
    return normalized.strip()


def fingerprint(text: str) -> str:
    normalized = normalize_text(text)
    if len(normalized) < FINGERPRINT_MIN_TEXT:
        return ""
    tokens = normalized.split(" ")
    # Length alone can pass on <3 tokens (e.g. an unspaced CJK body normalizes
    # to one giant token). No shingle would ever be hashed, leaving an
    # all-zero hash that similarity() would score 1.0 against every other
    # degenerate body - treat it as unfingerprintable instead.
    if len(tokens) < 3:
        return ""
    weights = [0] * 64
    for i in range(len(tokens) - 2):
        shingle = f"{tokens[i]} {tokens[i + 1]} {tokens[i + 2]}"
        digest = hashlib.sha1(shingle.encode("utf-8")).digest()[:8]
        for bit in range(64):
            byte = digest[bit >> 3]
            weights[bit] += 1 if (byte >> (7 - (bit & 7))) & 1 else -1
    hash_value = 0
    for bit in range(64):
        if weights[bit] > 0:
            hash_value |= 1 << (63 - bit)
    return f"{hash_value:016x}"


def similarity(a: str, b: str) -> float:
    if not _FINGERPRINT_RE.match(a or "") or not _FINGERPRINT_RE.match(b or ""):
        return 0.0
    dist = (int(a, 16) ^ int(b, 16)).bit_count()
    return 1 - dist / 64
