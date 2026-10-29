"""State transitions for the application's existing 8-by-8 Snake board."""


def new_session():
    return {"snake": [(2, 2), (1, 2), (0, 2)], "direction": (1, 0), "queued": None, "food": (4, 2), "score": 0, "best": 0, "status": "ready", "speed": "normal", "interval_ms": 0}


def dispatch(s, a, v=None):
    if a == "start" or a == "restart":
        b = s["best"]; z = s["speed"]; s.update(new_session()); s["best"] = b; s["speed"] = z; s["status"] = "playing"
    elif a == "pause":
        if s["status"] == "playing": s["status"] = "paused"
        elif s["status"] == "paused": s["status"] = "playing"
    elif a == "speed":
        if v not in ("slow", "normal", "fast"): raise ValueError("Unknown speed")
        s["speed"] = v
    elif a == "turn":
        if v not in ((0, -1), (0, 1), (-1, 0), (1, 0)): raise ValueError("Unknown direction")
        if s["status"] == "playing" and s["queued"] is None and v != (-s["direction"][0], -s["direction"][1]): s["queued"] = v
    elif a == "tick":
        if s["status"] == "playing":
            d = s["queued"] or s["direction"]; s["queued"] = None; s["direction"] = d; h = (s["snake"][0][0] + d[0], s["snake"][0][1] + d[1]); g = h == s["food"]
            if h[0] < 0 or h[0] >= 8 or h[1] < 0 or h[1] >= 8 or h in (s["snake"] if g else s["snake"][:-1]): s["status"] = "lost"
            else:
                s["snake"] = [h] + (s["snake"] if g else s["snake"][:-1])
                if g:
                    s["score"] += 1; s["best"] = max(s["best"], s["score"]); f = [(x, y) for y in range(8) for x in range(8) if (x, y) not in s["snake"]]; s["food"] = f[0] if f else None
                    if not f: s["status"] = "won"
    else:
        raise ValueError("Unknown action")
    s["interval_ms"] = {"slow": 200, "normal": 140, "fast": 90}[s["speed"]] if s["status"] == "playing" else 0
    return s
