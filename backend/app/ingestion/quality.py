import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.legal.enums import ProvisionKind
from app.legal.parser import normalize_legal_text

LEGAL_GRADE_MIN_CHARACTER_ACCURACY = 0.9995

_SECTION_RE = re.compile(r"(?:^|\.)section([0-9]+[a-z]?)\b", re.I)
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
_MEANING_CHANGING_TOKENS = {
    "appointed",
    "assembly",
    "citizen",
    "citizens",
    "court",
    "elected",
    "election",
    "governor",
    "house",
    "may",
    "must",
    "no",
    "not",
    "person",
    "persons",
    "president",
    "prohibited",
    "protected",
    "rights",
    "senate",
    "shall",
    "state",
    "subject",
}


@dataclass(frozen=True)
class GoldProvision:
    canonical_path: str
    text: str
    section_number: str | None = None
    source_page_start: int | None = None
    source_page_end: int | None = None
    source_spans: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class ExtractedProvision:
    canonical_path: str
    text: str | None
    kind: ProvisionKind | str | None = None
    number: str | None = None
    source_page_start: int | None = None
    source_page_end: int | None = None
    source_spans: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class LegalGradeQualityReport:
    gold_dataset_version: str
    gold_provision_count: int
    evaluated_provision_count: int
    missing_canonical_paths: list[str]
    expected_section_numbers: list[str]
    observed_section_numbers: list[str]
    complete_section_number_coverage: bool
    source_coordinate_assertion_count: int
    missing_source_coordinate_paths: list[str]
    source_coordinate_errors: list[dict[str, Any]]
    complete_source_coordinate_coverage: bool
    character_accuracy: float
    meaning_changing_token_errors: int
    passed: bool

    def to_policy_metrics(self) -> dict[str, Any]:
        return {
            "gold_dataset_version": self.gold_dataset_version,
            "gold_provision_count": self.gold_provision_count,
            "evaluated_provision_count": self.evaluated_provision_count,
            "missing_canonical_paths": self.missing_canonical_paths,
            "expected_section_numbers": self.expected_section_numbers,
            "observed_section_numbers": self.observed_section_numbers,
            "complete_section_number_coverage": self.complete_section_number_coverage,
            "source_coordinate_assertion_count": self.source_coordinate_assertion_count,
            "missing_source_coordinate_paths": self.missing_source_coordinate_paths,
            "source_coordinate_errors": self.source_coordinate_errors,
            "complete_source_coordinate_coverage": (
                self.complete_source_coordinate_coverage
            ),
            "character_accuracy": self.character_accuracy,
            "meaning_changing_token_errors": self.meaning_changing_token_errors,
            "metrics_source": "computed_gold_evaluation",
            "passed_legal_grade_gate": self.passed,
        }


def evaluate_legal_grade_quality(
    *,
    gold_dataset_version: str,
    gold_provisions: list[GoldProvision],
    extracted_provisions: list[ExtractedProvision],
    min_character_accuracy: float = LEGAL_GRADE_MIN_CHARACTER_ACCURACY,
) -> LegalGradeQualityReport:
    extracted_by_path = {
        provision.canonical_path: provision for provision in extracted_provisions
    }
    expected_section_numbers = sorted(
        {
            number
            for number in (
                provision.section_number
                or _section_number_from_path(provision.canonical_path)
                for provision in gold_provisions
            )
            if number
        },
        key=_section_sort_key,
    )
    observed_section_numbers = sorted(
        {
            provision.number.lower()
            for provision in extracted_provisions
            if _is_section(provision) and provision.number
        },
        key=_section_sort_key,
    )

    missing_paths: list[str] = []
    total_distance = 0
    total_gold_characters = 0
    meaning_errors = 0
    evaluated_count = 0
    source_coordinate_assertions = 0
    missing_source_coordinate_paths: list[str] = []
    source_coordinate_errors: list[dict[str, Any]] = []
    for gold in gold_provisions:
        extracted = extracted_by_path.get(gold.canonical_path)
        gold_text = normalize_legal_text(gold.text)
        if _has_source_coordinate_assertion(gold):
            source_coordinate_assertions += 1
        else:
            missing_source_coordinate_paths.append(gold.canonical_path)
        total_gold_characters += len(gold_text)
        if not extracted or not extracted.text:
            missing_paths.append(gold.canonical_path)
            total_distance += len(gold_text)
            meaning_errors += _meaning_changing_error_count(gold_text, "")
            if _has_source_coordinate_assertion(gold):
                source_coordinate_errors.append(
                    {
                        "canonical_path": gold.canonical_path,
                        "reason": "missing_extracted_provision",
                    }
                )
            continue
        evaluated_count += 1
        extracted_text = normalize_legal_text(extracted.text)
        total_distance += _levenshtein_distance(gold_text, extracted_text)
        meaning_errors += _meaning_changing_error_count(gold_text, extracted_text)
        source_coordinate_errors.extend(
            _source_coordinate_errors(gold=gold, extracted=extracted)
        )

    accuracy = 1.0
    if total_gold_characters:
        accuracy = max(0.0, 1 - (total_distance / total_gold_characters))
    accuracy = round(accuracy, 6)
    complete_coverage = set(expected_section_numbers).issubset(
        set(observed_section_numbers)
    )
    passed = (
        not missing_paths
        and complete_coverage
        and not missing_source_coordinate_paths
        and not source_coordinate_errors
        and accuracy >= min_character_accuracy
        and meaning_errors == 0
    )
    return LegalGradeQualityReport(
        gold_dataset_version=gold_dataset_version,
        gold_provision_count=len(gold_provisions),
        evaluated_provision_count=evaluated_count,
        missing_canonical_paths=missing_paths,
        expected_section_numbers=expected_section_numbers,
        observed_section_numbers=observed_section_numbers,
        complete_section_number_coverage=complete_coverage,
        source_coordinate_assertion_count=source_coordinate_assertions,
        missing_source_coordinate_paths=missing_source_coordinate_paths,
        source_coordinate_errors=source_coordinate_errors,
        complete_source_coordinate_coverage=not missing_source_coordinate_paths
        and not source_coordinate_errors,
        character_accuracy=accuracy,
        meaning_changing_token_errors=meaning_errors,
        passed=passed,
    )


def _is_section(provision: ExtractedProvision) -> bool:
    kind = provision.kind
    if isinstance(kind, ProvisionKind):
        return kind == ProvisionKind.SECTION
    return str(kind or "").lower() == ProvisionKind.SECTION.value


def _section_number_from_path(canonical_path: str) -> str | None:
    match = _SECTION_RE.search(canonical_path)
    return match.group(1).lower() if match else None


def _section_sort_key(number: str) -> tuple[int, str]:
    match = re.match(r"^(\d+)([a-z]?)$", number.lower())
    if not match:
        return (10**9, number.lower())
    return (int(match.group(1)), match.group(2))


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            substitution_cost = 0 if left_char == right_char else 1
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1]


def _meaning_changing_error_count(gold_text: str, extracted_text: str) -> int:
    gold_tokens = _tokens(gold_text)
    extracted_tokens = _tokens(extracted_text)
    errors = 0
    matcher = SequenceMatcher(a=gold_tokens, b=extracted_tokens, autojunk=False)
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed_tokens = (
            gold_tokens[left_start:left_end] + extracted_tokens[right_start:right_end]
        )
        if any(token in _MEANING_CHANGING_TOKENS for token in changed_tokens):
            errors += 1
    return errors


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _has_source_coordinate_assertion(gold: GoldProvision) -> bool:
    return bool(gold.source_spans)


def _source_coordinate_errors(
    *, gold: GoldProvision, extracted: ExtractedProvision
) -> list[dict[str, Any]]:
    if not _has_source_coordinate_assertion(gold):
        return []
    errors: list[dict[str, Any]] = []
    if (
        gold.source_page_start is not None
        and extracted.source_page_start != gold.source_page_start
    ):
        errors.append(
            {
                "canonical_path": gold.canonical_path,
                "reason": "source_page_start_mismatch",
                "expected": gold.source_page_start,
                "observed": extracted.source_page_start,
            }
        )
    if (
        gold.source_page_end is not None
        and extracted.source_page_end != gold.source_page_end
    ):
        errors.append(
            {
                "canonical_path": gold.canonical_path,
                "reason": "source_page_end_mismatch",
                "expected": gold.source_page_end,
                "observed": extracted.source_page_end,
            }
        )
    observed_signatures = {
        _source_span_signature(span) for span in extracted.source_spans or []
    }
    for span in gold.source_spans or []:
        signature = _source_span_signature(span)
        if signature in observed_signatures:
            continue
        errors.append(
            {
                "canonical_path": gold.canonical_path,
                "reason": "source_span_missing",
                "expected": {
                    "page_number": signature[0],
                    "bbox": list(signature[1]),
                },
            }
        )
    return errors


def _source_span_signature(
    span: dict[str, Any],
) -> tuple[int | None, tuple[float, ...]]:
    page_number = span.get("page_number", span.get("page"))
    bbox = span.get("bbox")
    if not isinstance(bbox, dict):
        return (_int_or_none(page_number), ())
    return (
        _int_or_none(page_number),
        (
            _rounded_float(bbox.get("x0")),
            _rounded_float(bbox.get("y0")),
            _rounded_float(bbox.get("x1")),
            _rounded_float(bbox.get("y1")),
        ),
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _rounded_float(value: Any) -> float:
    try:
        return round(float(value), 4)
    except TypeError, ValueError:
        return 0.0
