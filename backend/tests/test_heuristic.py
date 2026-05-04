from app.llm.classifier import heuristic_flag


def test_empty_response():
    assert heuristic_flag("") == "empty_response"
    assert heuristic_flag("   ") == "empty_response"
    assert heuristic_flag("hi") == "empty_response"


def test_refusal():
    assert heuristic_flag("I cannot help with that.") == "refusal"
    assert heuristic_flag("As an AI, I won't.") == "refusal"
    assert heuristic_flag("I'm unable to do that.") == "refusal"


def test_hallucination_signal():
    assert heuristic_flag("It's possible that the total is 42.") == "hallucination_signal"
    assert heuristic_flag("I'm not sure but I think so.") == "hallucination_signal"


def test_pass_through():
    assert heuristic_flag("Sure, here is the result you requested: 42.") is None
