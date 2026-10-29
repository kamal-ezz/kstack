"""Private equivalence checks, copied only into the auth-free judge container."""

from copy import deepcopy
import importlib.util
import random

import session as candidate

spec = importlib.util.spec_from_file_location("reference", "/tmp/reference_session.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def outcome(module, state, action, value):
    try:
        result = module.dispatch(state, action, value)
        return ("returned", result is state, deepcopy(result))
    except Exception as error:
        return ("raised", type(error).__name__, str(error))


def compare_trace(actions, initial=None):
    expected = deepcopy(initial) if initial is not None else reference.new_session()
    actual = deepcopy(initial) if initial is not None else candidate.new_session()
    assert actual == expected, "Initial state changed"
    for index, (action, value) in enumerate(actions):
        left = outcome(reference, expected, action, value)
        right = outcome(candidate, actual, action, value)
        assert right == left, (index, action, value, left, right)
        assert actual == expected, (index, action, value, expected, actual)


compare_trace([
    ("pause", None), ("speed", "fast"), ("start", None),
    ("tick", None), ("tick", None), ("pause", None),
    ("tick", None), ("speed", "slow"), ("pause", None),
    ("turn", (-1, 0)), ("turn", (0, 1)), ("turn", (0, -1)),
    ("tick", None), ("restart", None),
] + [("tick", None)] * 12 + [("pause", None), ("restart", None)])

# A departing tail is legal; entering an occupied non-tail cell is not.
state = reference.new_session()
state.update(snake=[(1, 1), (1, 2), (0, 2), (0, 1)], direction=(-1, 0), status="playing", food=(7, 7))
compare_trace([("tick", None), ("turn", (0, 1)), ("tick", None)], state)
state.update(direction=(0, 1))
compare_trace([("tick", None)], state)

# The last available cell produces a win and stops the interval.
state = reference.new_session()
state.update(snake=[(0, 0)] + [(x, y) for y in range(8) for x in range(8)
                             if (x, y) not in ((0, 0), (1, 0))],
             direction=(1, 0), status="playing", food=(1, 0), score=60, best=60)
compare_trace([("tick", None), ("tick", None), ("pause", None), ("restart", None)], state)

choices = [("start", None), ("restart", None), ("pause", None)]
choices += [("tick", None)] * 10
choices += [("speed", value) for value in ("slow", "normal", "fast", "invalid")]
choices += [("turn", value) for value in ((0, -1), (0, 1), (-1, 0), (1, 0), (2, 0))]
choices += [("unknown", None)]
randomizer = random.Random(731)
for _ in range(20):
    compare_trace([randomizer.choice(choices) for _ in range(60)])
print("Preserved movement, growth, pause/resume, restart, speed, reversal, queued turns, collisions, win, errors, and 1,200 seeded actions.")
