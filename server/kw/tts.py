"""Read-aloud fallback for the farmer check: an MP3 of a short text, for browsers with no Bangla voice (desktop Chrome).

edge-tts calls Microsoft's free online neural voices (an unofficial service, no key). Results are cached in memory by
text, so a repeated report costs nothing. A synthetic voice: disclosed in AI_USE.md.
"""
from functools import lru_cache

VOICES = {"bn": "bn-BD-NabanitaNeural", "en": "en-GB-SoniaNeural"}
MAX_CHARS = 1200


# ponytail: in-process cache, lost on restart; a disk cache if the same reports get replayed across sleeps
@lru_cache(maxsize=256)
def speak(text: str, lang: str = "bn") -> bytes:
    import asyncio
    import edge_tts

    text = text.strip()
    if not text or len(text) > MAX_CHARS:
        raise ValueError(f"text must be 1 to {MAX_CHARS} characters")
    if lang not in VOICES:
        raise ValueError(f"lang must be one of {sorted(VOICES)}")

    async def run() -> bytes:
        out = bytearray()
        async for chunk in edge_tts.Communicate(text, VOICES[lang]).stream():
            if chunk["type"] == "audio":
                out += chunk["data"]
        return bytes(out)

    # the free service now and then answers "no audio" for a text it reads fine a moment later (measured): try 3 times
    for attempt in range(3):
        try:
            audio = asyncio.run(run())
            if audio:
                return audio
        except Exception:
            if attempt == 2:
                raise
    raise RuntimeError("the voice service returned no audio")


if __name__ == "__main__":
    a = speak("আমিনবাজার: ১ কিলোমিটারের মধ্যে ৩টি ইটভাটা।")
    assert a[:3] == b"ID3" or a[0] == 0xFF, a[:8]
    print("ok", len(a), "bytes")
