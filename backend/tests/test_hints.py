"""Adaptive hint ladder (planner decides 1-6 hints) and the direct-answer button."""
from app.services.hint_planner import HINT_PLANNER_PROMPT


def new_session(client, headers):
    return client.post("/api/sessions/", json={}, headers=headers).json()["id"]


def send(client, headers, sid, mode="normal", message=""):
    return client.post("/api/chat/", json={"session_id": sid, "message": message, "mode": mode}, headers=headers)


def planner_calls(fake_llm):
    return [c for c in fake_llm.calls if c.get("response_format")]


def last_instruction(fake_llm):
    tutor_calls = [c for c in fake_llm.calls if c.get("max_tokens") != 16 and not c.get("response_format")]
    last = tutor_calls[-1]["messages"][-1]
    return last["content"] if last["role"] == "system" else None


def test_hint_requires_a_question_first(client, make_student):
    s = make_student()
    sid = new_session(client, s["headers"])
    res = send(client, s["headers"], sid, "hint")
    assert res.status_code == 400
    assert "Ask a question first" in res.json()["detail"]
    assert send(client, s["headers"], sid, "answer").status_code == 400


def test_planner_drives_the_ladder(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="How do I integrate x*e^x?")

    first = send(client, h, sid, "hint").json()
    assert first["user_message"]["kind"] == "hint-1"
    assert first["assistant_message"]["content"] == "Planner hint 1"  # only next_hint is shown
    assert first["assistant_message"]["hint_total"] == 3
    assert first["user_message"]["hint_total"] == 3
    assert "hint_assessment" not in first["assistant_message"]  # assessment is instructors-only

    call = planner_calls(fake_llm)[0]
    assert call["messages"][0]["content"].startswith(HINT_PLANNER_PROMPT)
    prompt = call["messages"][1]["content"]
    question_block = prompt.split("</StudentQuestion>")[0]
    assert "How do I integrate x*e^x?" in question_block
    # The tutor's question the student is stuck on is what the hint must help with
    assert "What do you notice first?" in question_block.split("stuck on")[1]
    assert "<CurrentHintLevel>\n1\n</CurrentHintLevel>" in prompt

    # A student attempt between hints is evidence, not a reset
    send(client, h, sid, message="Is u = x?")
    second = send(client, h, sid, "hint").json()
    assert second["user_message"]["kind"] == "hint-2"
    prompt = planner_calls(fake_llm)[-1]["messages"][1]["content"]
    assert "Planner hint 1" in prompt.split("<PreviousHints>")[1]
    assert "Is u = x?" in prompt.split("<StudentEvidence>")[1]

    assert send(client, h, sid, "hint").json()["user_message"]["kind"] == "hint-3"
    # All planned hints used and the student hasn't written since
    blocked = send(client, h, sid, "hint")
    assert blocked.status_code == 400 and "used all the hints" in blocked.json()["detail"]

    # Writing again starts a fresh ladder
    send(client, h, sid, message="New question: what is a derivative?")
    assert send(client, h, sid, "hint").json()["user_message"]["kind"] == "hint-1"


def test_planner_values_are_clamped(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="What is 2+2?")
    fake_llm.plan_override = {"question_depth": "easy", "recommended_hint_count": 9, "current_hint_level": 5}
    body = send(client, h, sid, "hint").json()
    assert body["user_message"]["kind"] == "hint-1"  # can't skip ahead
    assert body["assistant_message"]["hint_total"] == 2  # easy -> at most 2


def test_model_can_restart_ladder_for_new_question(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="Explain recursion")
    send(client, h, sid, "hint")
    send(client, h, sid, message="Actually, what is a stack?")
    fake_llm.plan_override = {"current_hint_level": 1, "next_hint": "What do plates in a pile have in common?"}
    body = send(client, h, sid, "hint").json()
    assert body["user_message"]["kind"] == "hint-1"
    assert body["assistant_message"]["content"].startswith("What do plates")


def test_bad_planner_json_falls_back_to_fixed_hint(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="Why is the sky blue?")
    fake_llm.plan_override = "Sure! Here is a hint: think about light."  # not JSON
    res = send(client, h, sid, "hint")
    assert res.status_code == 200
    body = res.json()
    assert body["user_message"]["kind"] == "hint-1"
    assert body["assistant_message"]["content"] == "What do you notice first?"  # normal tutor call
    assert body["assistant_message"]["hint_total"] == 3
    assert "nudge" in last_instruction(fake_llm)


def test_admin_sees_assessment_and_answer_button_flag(client, make_student, fake_llm, admin_headers):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="Prove there are infinitely many primes")
    fake_llm.plan_override = {
        "question_depth": "very_difficult", "recommended_hint_count": 5,
        "misconceptions": ["Thinks primes stop appearing"], "should_allow_answer_button": False,
    }
    body = send(client, h, sid, "hint").json()
    assert body["assistant_message"]["hint_allow_answer"] is False
    assert body["assistant_message"]["hint_total"] == 5

    logs = client.get(f"/api/admin/students/{s['student']['id']}/sessions/{sid}", headers=admin_headers).json()
    assessment = logs[-1]["hint_assessment"]
    assert assessment["question_depth"] == "very_difficult"
    assert assessment["misconceptions"] == ["Thinks primes stop appearing"]
    assert logs[0]["hint_assessment"] is None


def test_direct_answer_button(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="Why is the sky blue?")
    send(client, h, sid, "hint")
    res = send(client, h, sid, "answer")
    assert res.status_code == 200
    body = res.json()
    assert body["user_message"]["kind"] == "answer"
    assert body["user_message"]["content"] == "Please show me the full answer."
    assert "complete, correct answer" in last_instruction(fake_llm)
    # The answer resets the hint ladder
    assert send(client, h, sid, "hint").json()["user_message"]["kind"] == "hint-1"


def test_hint_turns_do_not_rename_chat(client, make_student):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="Explain recursion")
    title = send(client, h, sid, "hint").json()["session_title"]
    assert title == "Photosynthesis Basics"  # the fake LLM's title from the first message


# The real case reported by a student: "hint 2" just re-asked the tutor's question
TUTOR_Q = ("Exactly! Now, let's think about how that learning process works. 1. What kind of data do you think "
           "AI models use to learn? 2. Can you describe any specific techniques or methods that might be involved "
           "in this learning process?")
REPEATED = ("What types of data do you think AI models typically use to learn, and can you think of any specific "
            "methods they might employ?")
HELPFUL = ("AI models learn from lots of examples, like thousands of photos labelled 'cat' or 'dog'. Learning from "
           "labelled examples is called supervised learning. What labelled examples would a spam filter need?")


def test_repetition_detector():
    from app.services.hint_planner import is_repetitive
    assert is_repetitive(REPEATED, [TUTOR_Q])
    assert not is_repetitive(HELPFUL, [TUTOR_Q])


def test_repeated_hint_is_rewritten(client, make_student, fake_llm):
    s = make_student()
    h = s["headers"]
    sid = new_session(client, h)
    send(client, h, sid, message="What is AI?")
    fake_llm.plan_override = [{"next_hint": "What do you notice first?"}, {"next_hint": HELPFUL}]
    body = send(client, h, sid, "hint").json()
    assert body["assistant_message"]["content"] == HELPFUL
    retry = planner_calls(fake_llm)[-1]["messages"]
    assert len(planner_calls(fake_llm)) == 2
    assert "repeated the tutor's question" in retry[-1]["content"]
