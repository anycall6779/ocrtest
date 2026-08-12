# -*- coding: utf-8 -*-
"""대한민국 자동차 번호판 문자열 검증 및 보정 규칙.

이미지 OCR과 무관한 순수 문자열 로직을 분리해 회귀 테스트가 가능하도록 한다.
일반적인 2/3자리 차종번호 + 용도기호 1자 + 일련번호 4자리 형식을 대상으로 한다.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional


# 비사업용 승용/승합, 렌터카, 사업용 및 택배 번호판에 쓰이는 용도기호.
PRIVATE_SYLLABLES = frozenset("가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주")
RENTAL_SYLLABLES = frozenset("하허호")
COMMERCIAL_SYLLABLES = frozenset("아바사자배")
VALID_PLATE_SYLLABLES = PRIVATE_SYLLABLES | RENTAL_SYLLABLES | COMMERCIAL_SYLLABLES

PLATE_RE = re.compile(r"^(\d{2,3})([가-힣])(\d{4})$")
PLATE_SEARCH_RE = re.compile(r"(?<!\d)(\d{2,3})([가-힣])(\d{4})(?!\d)")

# 실제 excel 이력에서 반복 확인된 OneOCR 오인식 및 같은 형태의 종성/모음 오인식.
KNOWN_INVALID_SYLLABLE_CORRECTIONS = {
    "년": "너",
    "매": "마",
    "세": "서",
}


def split_plate(plate: str):
    match = PLATE_RE.fullmatch(plate or "")
    return match.groups() if match else None


def numeric_signature(plate: str) -> Optional[str]:
    parts = split_plate(plate)
    return f"{parts[0]}-{parts[2]}" if parts else None


def is_valid_plate(plate: str) -> bool:
    parts = split_plate(plate)
    return bool(parts and parts[1] in VALID_PLATE_SYLLABLES)


def _decompose_hangul(char: str):
    if len(char) != 1 or not ("가" <= char <= "힣"):
        return None
    code = ord(char) - 0xAC00
    return code // 588, (code % 588) // 28, code % 28


def hangul_distance(left: str, right: str) -> int:
    """초성/중성/종성 단위의 단순 거리. OCR 유사 글자 보정에만 사용한다."""
    a, b = _decompose_hangul(left), _decompose_hangul(right)
    if a is None or b is None:
        return 99
    return sum(x != y for x, y in zip(a, b))


def correct_invalid_syllable(syllable: str) -> Optional[str]:
    if syllable in VALID_PLATE_SYLLABLES:
        return syllable
    if syllable in KNOWN_INVALID_SYLLABLE_CORRECTIONS:
        return KNOWN_INVALID_SYLLABLE_CORRECTIONS[syllable]

    # 허용되지 않는 글자가 허용 글자 하나와 초/중/종성 한 요소만 다를 때만 보정한다.
    nearest = [candidate for candidate in VALID_PLATE_SYLLABLES if hangul_distance(syllable, candidate) == 1]
    return nearest[0] if len(nearest) == 1 else None


@dataclass(frozen=True)
class HistorySuggestion:
    plate: str
    observations: int


class PlateHistoryIndex:
    """숫자 부분이 같은 과거 번호판의 한글 음절 빈도 인덱스."""

    def __init__(self, counts: Optional[Mapping[str, Counter]] = None):
        self.counts = dict(counts or {})

    @classmethod
    def from_plates(cls, plates: Iterable[str]):
        counts = defaultdict(Counter)
        for plate in plates:
            plate = str(plate).replace(" ", "")
            if not is_valid_plate(plate):
                continue
            front, syllable, rear = split_plate(plate)
            counts[f"{front}-{rear}"][syllable] += 1
        return cls(counts)

    def unique_suggestion(self, plate: str, min_observations: int = 2) -> Optional[HistorySuggestion]:
        parts = split_plate(plate)
        if not parts:
            return None
        front, current, rear = parts
        counts = self.counts.get(f"{front}-{rear}", Counter())
        if len(counts) != 1:
            return None
        syllable, observations = counts.most_common(1)[0]
        if observations < min_observations or syllable == current:
            return None
        return HistorySuggestion(f"{front}{syllable}{rear}", observations)


def normalize_plate_candidate(candidate: str, history: Optional[PlateHistoryIndex] = None) -> Optional[str]:
    parts = split_plate(candidate)
    if not parts:
        return None
    front, syllable, rear = parts

    corrected = correct_invalid_syllable(syllable)
    if corrected is None:
        return None
    normalized = f"{front}{corrected}{rear}"

    # 원문 음절이 법정 용도기호가 아니면, 같은 차량의 과거 확정값을 우선한다.
    if syllable not in VALID_PLATE_SYLLABLES and history:
        suggestion = history.unique_suggestion(normalized, min_observations=1)
        if suggestion:
            return suggestion.plate
    return normalized


def extract_plate_candidates(text: str, history: Optional[PlateHistoryIndex] = None) -> list[str]:
    compact = re.sub(r"[^0-9가-힣]", "", text or "")
    results = []
    candidate_strings = ["".join(match.groups()) for match in PLATE_SEARCH_RE.finditer(compact)]

    # 번호판 고정 볼트를 숫자 0으로 읽어 5자리처럼 보이는 경우를 별도로 복원한다.
    for match in re.finditer(r"(?<!\d)(\d{2,3})([가-힣])0(\d{4})(?!\d)", compact):
        candidate_strings.append("".join(match.groups()))
    for match in re.finditer(r"(?<!\d)(\d{2,3})([가-힣])(\d{4})0(?!\d)", compact):
        candidate_strings.append("".join(match.groups()))

    for candidate in candidate_strings:
        plate = normalize_plate_candidate(candidate, history)
        if plate and plate not in results:
            results.append(plate)
    return results


def choose_best_candidate(candidates: Iterable[str], history: Optional[PlateHistoryIndex] = None) -> Optional[str]:
    votes = Counter(candidate for candidate in candidates if is_valid_plate(candidate))
    if not votes:
        return None

    scores = {plate: float(count) for plate, count in votes.items()}
    if history:
        for plate in list(scores):
            suggestion = history.unique_suggestion(plate)
            if not suggestion:
                continue
            current_middle = split_plate(plate)[1]
            suggested_middle = split_plate(suggestion.plate)[1]
            # 유사 글자이고 과거에 2회 이상 확인됐을 때만 약한 사전확률을 준다.
            if hangul_distance(current_middle, suggested_middle) <= 1:
                scores[suggestion.plate] = scores.get(suggestion.plate, 0.0) + min(1.5, 0.5 + suggestion.observations * 0.1)

    return max(scores, key=lambda plate: (scores[plate], votes.get(plate, 0), plate))
