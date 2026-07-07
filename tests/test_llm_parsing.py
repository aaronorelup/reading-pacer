"""Tests for parsing LLM question output — the part most likely to misbehave."""

import json

from reading_pacer.services.llm_service import parse_questions

GOOD_Q = {
    "question": "What color is the sky?",
    "A": "Blue", "B": "Green", "C": "Red", "D": "Yellow",
    "answer": "A",
}


def _expect_normalized(q):
    assert q["question"] == "What color is the sky?"
    assert q["choices"] == ["Blue", "Green", "Red", "Yellow"]
    assert q["correct"] == "A"


def test_parses_object_with_questions_key():
    raw = json.dumps({"questions": [GOOD_Q, GOOD_Q]})
    qs = parse_questions(raw)
    assert len(qs) == 2
    _expect_normalized(qs[0])


def test_parses_bare_array():
    raw = json.dumps([GOOD_Q])
    qs = parse_questions(raw)
    assert len(qs) == 1
    _expect_normalized(qs[0])


def test_strips_markdown_fences():
    raw = "```json\n" + json.dumps({"questions": [GOOD_Q]}) + "\n```"
    assert len(parse_questions(raw)) == 1


def test_extracts_array_from_surrounding_prose():
    raw = "Here are your questions:\n" + json.dumps([GOOD_Q]) + "\nEnjoy!"
    assert len(parse_questions(raw)) == 1


def test_salvages_individual_objects_from_broken_json():
    # Trailing comma makes the array invalid; objects should still be salvaged
    obj = json.dumps(GOOD_Q)
    raw = f"[{obj}, {obj},]"
    qs = parse_questions(raw)
    assert len(qs) == 2


def test_accepts_lowercase_keys():
    q = {"question": "Q?", "a": "1", "b": "2", "c": "3", "d": "4", "answer": "b"}
    qs = parse_questions(json.dumps([q]))
    assert len(qs) == 1
    assert qs[0]["correct"] == "B"


def test_accepts_correct_alias_and_verbose_answer():
    q = dict(GOOD_Q)
    del q["answer"]
    q["correct"] = "A) Blue"  # some models echo the choice text
    qs = parse_questions(json.dumps([q]))
    assert len(qs) == 1
    assert qs[0]["correct"] == "A"


def test_rejects_bad_answer_letter():
    q = dict(GOOD_Q, answer="E")
    assert parse_questions(json.dumps([q])) == []


def test_rejects_missing_choice():
    q = dict(GOOD_Q)
    del q["C"]
    assert parse_questions(json.dumps([q])) == []


def test_rejects_non_dict_items():
    assert parse_questions(json.dumps(["not a question", 42])) == []


def test_empty_and_garbage_input():
    assert parse_questions("") == []
    assert parse_questions("The model refused to answer.") == []
