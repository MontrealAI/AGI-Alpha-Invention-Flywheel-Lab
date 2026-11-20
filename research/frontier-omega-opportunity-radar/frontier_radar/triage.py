"""Deterministic lead routing. Matches are hypotheses for review, not evidence."""
import re

RULES = {
    "table-revision-proof": (r"\b(?:ocr|document parsing|table extraction)\b", r"\b(?:table|documents?|scan|pages?)\b"),
    "weather-replay-instrument": (r"\b(?:precipitation|rainfall|weather radar)\b", r"\b(?:resolution|satellite|retrospective|hourly|gridded)\b"),
    "offline-audio-fault-report": (r"\b(?:asr|speech|audio)\b", r"\b(?:offline|on-device|bilingual|transcription|low-latency)\b"),
}


def route(observations, records):
    present = {r["id"] for r in records}
    leads = []
    for observation in observations:
        words = f'{observation["title"]} {observation["summary"]}'
        matched = [key for key, patterns in RULES.items() if key in present and
                   all(re.search(pattern, words, re.IGNORECASE) for pattern in patterns)]
        if matched:
            leads.append({"observation_id": observation["id"], "source_id": observation["source_id"],
                          "title": observation["title"], "url": observation["url"],
                          "matched_opportunities": matched, "status": "NEEDS_REVIEW"})
    return leads
