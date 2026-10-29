import unittest

from session import dispatch, new_session


class SessionTests(unittest.TestCase):
    def test_start_and_move(self):
        state = new_session()
        dispatch(state, "start")
        self.assertEqual(state["interval_ms"], 140)
        dispatch(state, "tick")
        self.assertEqual(state["snake"][0], (3, 2))

    def test_pause_and_resume(self):
        state = new_session()
        dispatch(state, "start")
        dispatch(state, "pause")
        before = list(state["snake"])
        dispatch(state, "tick")
        self.assertEqual(state["snake"], before)
        self.assertEqual(state["interval_ms"], 0)
        dispatch(state, "pause")
        self.assertEqual(state["interval_ms"], 140)

    def test_growth(self):
        state = new_session()
        dispatch(state, "start")
        dispatch(state, "tick")
        dispatch(state, "tick")
        self.assertEqual(state["score"], 1)
        self.assertEqual(state["best"], 1)
        self.assertEqual(len(state["snake"]), 4)


if __name__ == "__main__":
    unittest.main()
