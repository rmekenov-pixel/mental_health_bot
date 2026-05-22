import json
import os


def load_test(test_name: str) -> dict:
    path = os.path.join("tests", f"{test_name}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_score(answers: list[int]) -> int:
    return sum(answers)


def get_level(test_name: str, score: int) -> str:
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