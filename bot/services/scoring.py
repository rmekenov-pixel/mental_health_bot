import json
import os


def load_test(test_name: str) -> dict:
    path = os.path.join("tests", f"{test_name}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_score(answers: list[int]) -> int:
    return sum(answers)


def calculate_burnout_scores(answers: list[int]) -> dict:
    test = load_test("burnout")
    subscales = test["subscales"]

    ee_score = sum(answers[i] for i in subscales["emotional_exhaustion"])
    dp_score = sum(answers[i] for i in subscales["depersonalization"])
    pa_score = sum(answers[i] for i in subscales["personal_achievement"])

    def get_burnout_level(score, ranges):
        for range_str, level in ranges.items():
            parts = range_str.split("-")
            low, high = int(parts[0]), int(parts[1])
            if low <= score <= high:
                return level
        return "Неизвестно"

    scoring = test["scoring"]
    return {
        "emotional_exhaustion": ee_score,
        "ee_level": get_burnout_level(ee_score, scoring["emotional_exhaustion"]),
        "depersonalization": dp_score,
        "dp_level": get_burnout_level(dp_score, scoring["depersonalization"]),
        "personal_achievement": pa_score,
        "pa_level": get_burnout_level(pa_score, scoring["personal_achievement"]),
        "total": ee_score + dp_score + pa_score
    }


def get_level(test_name: str, score: int) -> str:
    if test_name == "burnout":
        return "См. детальный анализ"
    test = load_test(test_name)
    for range_str, level in test["scoring"].items():
        parts = range_str.split("-")
        low, high = int(parts[0]), int(parts[1])
        if low <= score <= high:
            return level
    return "Неизвестно"


def get_test_questions(test_name: str) -> list[str]:
    test = load_test(test_name)
    return test["questions"]


def get_test_options(test_name: str) -> list[str]:
    test = load_test(test_name)
    return test["options"]