import json
import os


def load_test(test_name: str, lang: str = "ru") -> dict:
    if lang and lang != "ru":
        localized_path = os.path.join("tests", f"{test_name}_{lang}.json")
        if os.path.exists(localized_path):
            with open(localized_path, "r", encoding="utf-8") as f:
                return json.load(f)

    path = os.path.join("tests", f"{test_name}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_score(answers: list[int]) -> int:
    return sum(answers)


def calculate_self_esteem_scores(answers: list[int]) -> int:
    """
    Расчёт по классической шкале самооценки Розенберга.
    Прямые вопросы (индексы 0, 2, 3, 6, 9): 3, 2, 1, 0
    Обратные вопросы (индексы 1, 4, 5, 7, 8): 0, 1, 2, 3
    """
    reverse_indices = {1, 4, 5, 7, 8}
    total = 0
    for i, ans in enumerate(answers):
        # ans: 0="Полностью согласен(3)", 1="Согласен(2)", 2="Не согласен(1)", 3="Полностью не согласен(0)"
        direct_val = 3 - ans
        if i in reverse_indices:
            score = 3 - direct_val
        else:
            score = direct_val
        total += score
    return total


def calculate_burnout_scores(answers: list[int], lang: str = "ru") -> dict:
    test = load_test("burnout", lang)
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


def get_level(test_name: str, score: int, lang: str = "ru") -> str:
    if test_name == "burnout":
        return "См. детальный анализ"
    test = load_test(test_name, lang)
    for range_str, level in test["scoring"].items():
        parts = range_str.split("-")
        low, high = int(parts[0]), int(parts[1])
        if low <= score <= high:
            return level
    return "Неизвестно"


def get_test_questions(test_name: str, lang: str = "ru") -> list[str]:
    test = load_test(test_name, lang)
    return test["questions"]


def get_test_options(test_name: str, lang: str = "ru") -> list[str]:
    test = load_test(test_name, lang)
    return test["options"]
