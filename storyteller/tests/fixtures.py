"""Small invented story data, shared by offline contract and integration tests."""

from copy import deepcopy


def understanding_payload(source="a tale", **overrides):
    payload = {
        "player": "the traveller",
        "canon": "# World\n\n## Premise\nA place with a keeper and a parcel.",
        "opening": "Cold air touches your hands.",
        "space": {
            "anchors": [{"fact": "The supplied tale is the source.", "quote": source[:40]}],
            "situation": "You stand near a keeper holding a parcel.",
            "initial_facts": [
                {"key": "parcel.holder", "value": "keeper", "known_by": ["player", "keeper"]},
                {"key": "keeper.secret", "value": "hidden-password", "known_by": ["keeper"]},
                {"key": "world.limit", "value": "No flight.", "known_by": ["player"]},
            ],
            "fixed_keys": ["world.limit"],
            "possibilities": ["The keeper might negotiate.", "The traveller might leave."],
            "adaptation": "A loop returns to the meeting; only the player remembers.",
            "style": "Plain language. The keeper speaks tersely.",
        },
    }
    payload.update(overrides)
    return payload


def understand_reply(system, user):
    return understanding_payload(user.split("\n\n", 1)[1])


OPENING = {"narration": "Cold air touches your hands.", "hints": []}
NARRATION = {"narration": "The keeper turns away.", "hints": ["Wait."]}


def review_payload(target=None, *, blocking=True, **overrides):
    findings = [] if target is None else [{
        "target": target, "blocking": blocking, "category": "clarity",
        "location": "narration, first sentence", "evidence": "The keeper turns away.",
        "reason": "The phrasing obscures the established response.",
        "request": "Make the response clearer without changing what happens.",
    }]
    payload = {"decision": "revise" if target and blocking else "pass",
               "summary": "Content review.", "preserve": ["The restrained voice."],
               "findings": findings}
    payload.update(overrides)
    return payload


def ruling_payload(**overrides):
    payload = {
        "intent": "Ask the keeper to hand over the parcel.",
        "outcome": "partial",
        "events": [{"text": "The keeper turns away.", "observers": ["player", "keeper"]}],
        "expansions": [], "changes": [], "observations": [], "memories": [],
        "brief": {"focus": "An unanswered request.", "mode": "direct",
                  "visible": ["The keeper turns away."],
                  "uncertainty": ["Whether the keeper will listen."],
                  "stop_before": "The player's response."},
        "restart": False, "ending": False,
    }
    payload.update(overrides)
    payload = deepcopy(payload)
    if payload.get("restart"):
        payload["brief"]["mode"] = "return"
    if payload.get("ending"):
        payload["brief"]["mode"] = "ending"
    return payload
