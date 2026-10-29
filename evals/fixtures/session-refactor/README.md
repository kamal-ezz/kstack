# Snake session module

This module powers an existing Python application. The public API is
`new_session()` and `dispatch(state, action, value=None)`. Dispatch mutates and
returns the same state dictionary. Keep the keys, values, error messages,
and state transitions compatible with existing callers; private helpers and
constants can change.

Actions are `start`, `restart`, `pause` (toggles pause), `speed`, `turn`, and
`tick`. A turn value is a cardinal direction tuple. The first eligible turn
before a tick wins; immediate reversal is ignored. Speed values are `slow`,
`normal`, and `fast`. The interval is zero when not playing. Restart preserves
best score and speed. A tick can move into the departing tail cell when not
growing; new food uses the first free cell in row-major order. Filling the board
wins the game. Unknown actions, speeds, and directions raise ValueError.

Run the existing checks with `python3 -m unittest -v`.
