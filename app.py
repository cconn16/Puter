"""Flask dashboard + command handler."""

import threading

from flask import Flask, jsonify, render_template, request

import config  
import parser  
import store

app = Flask(__name__)

_lock = threading.Lock()  
_pending = {"cmd": None, "field": None}

HELP = ("bench 3x8 225 · squat 3 sets of 5 at 315 · pull up 4x6 +45 · "  
        "pr bench 5x5 · history squat · program · undo")


def reply(message, detail="", kind="info"):  
    return {"message": message, "detail": detail, "kind": kind}


def snapshot(resp):  
    return jsonify({  
        "reply": resp,  
        "recent": store.recent(12),  
        "prs": store.all_prs()[:14],  
        "program": store.program_for_day(),  
        "today_count": len(store.today()),  
        "pending": _pending["field"],  
    })


def dispatch(cmd):  
    action = cmd["action"]

    if action == "help":  
        return reply("Commands", HELP)

    if action == "undo":  
        gone = store.delete_last()  
        if not gone:  
            return reply("Nothing to undo", "", "warn")  
        return reply("Removed", f"{gone['exercise']} {gone['sets']}×{gone['reps']} "  
                                f"@ {gone['weight']:g}", "warn")

    if action == "log_workout":  
        r = store.log_set(cmd["exercise"], cmd["sets"], cmd["reps"], cmd["weight"],  
                          unit=cmd["unit"], weight_type=cmd["weight_type"])  
        scheme = f"{r['sets']} × {r['reps']} @ {r['weight']:g} {r['unit']}"  
        if r["is_pr"]:  
            note = f"New {r['sets']}×{r['reps']} PR"  
            note += f" — was {r['previous']:g}" if r["previous"] else " — first entry"  
            return reply(f"{r['exercise']}  {scheme}", note, "pr")  
        return reply(f"{r['exercise']}  {scheme}",  
                     f"Logged. PR stands at {r['previous']:g}", "ok")

    if action == "show_pr":  
        if cmd["sets"] and cmd["reps"]:  
            rec = store.get_pr(cmd["exercise"], cmd["sets"], cmd["reps"])  
            if not rec:  
                return reply(f"No {cmd['sets']}×{cmd['reps']} PR for {cmd['exercise']}",  
                             "", "warn")  
            return reply(f"{cmd['exercise']} {cmd['sets']}×{cmd['reps']} PR",  
                         f"{rec['Weight']:g} {rec.get('Unit') or 'lb'} "  
                         f"— set {rec.get('Date Set')}")  
        prs = store.all_prs(cmd["exercise"])  
        if not prs:  
            return reply(f"No PRs for {cmd['exercise']}", "", "warn")  
        return reply(f"{cmd['exercise']} PRs",  
                     "   ".join(f"{p['Sets']}×{p['Reps']}: {p['Weight']:g}" for p in prs))

    if action == "show_history":  
        rows = store.history_for(cmd["exercise"], cmd.get("sets"),  
                                 cmd.get("reps"), limit=6)  
        if not rows:  
            return reply(f"No history for {cmd['exercise']}", "", "warn")  
        return reply(f"{cmd['exercise']} — recent",  
                     "   ".join(f"{str(r['Date'])[5:]}: {r['Sets']}×{r['Reps']}"  
                                f"@{r['Weight']:g}" for r in rows))

    if action == "show_program":  
        rows = store.program_for_day()  
        if not rows:  
            return reply("Nothing programmed today", "Rest day", "warn")  
        return reply("Today's program",  
                     "   ".join(f"{r['Exercise']} {r.get('Sets')}×{r.get('Reps')}"  
                                for r in rows))

    return reply("Didn't understand that", HELP, "warn")


@app.route("/")  
def index():  
    return render_template("index.html")


@app.route("/api/state")  
def state():  
    return snapshot(reply("Ready", "Type a command and press Enter"))


@app.route("/api/command", methods=["POST"])  
def command():  
    text = (request.json or {}).get("text", "").strip()  
    with _lock:  
        try:  
            if text.lower() == "cancel":  
                _pending.update(cmd=None, field=None)  
                return snapshot(reply("Cancelled", "", "warn"))

            if _pending["cmd"] is not None and text.lower() not in parser.HELP_WORDS:  
                cmd = parser.fill_slot(_pending["cmd"], _pending["field"], text)  
            else:  
                cmd = parser.parse(text)

            missing = parser.missing_fields(cmd)  
            if missing:  
                _pending.update(cmd=cmd, field=missing[0])  
                w = cmd.get("weight")  
                known = (f"{cmd.get('exercise') or '?'}  "  
                         f"{cmd.get('sets') or '?'}×{cmd.get('reps') or '?'}  "  
                         f"@ {w if w is not None else '?'}")  
                return snapshot(reply(parser.PROMPTS[missing[0]], known, "ask"))

            _pending.update(cmd=None, field=None)  
            return snapshot(dispatch(cmd))

        except Exception as exc:  
            _pending.update(cmd=None, field=None)  
            return snapshot(reply("Error", str(exc), "warn"))


@app.route("/api/manual", methods=["POST"])  
def manual():  
    d = request.json or {}  
    with _lock:  
        try:  
            cmd = parser.blank(  
                "log_workout",  
                exercise=store.canonicalize(d.get("exercise", "")),  
                sets=int(d["sets"]), reps=int(d["reps"]), weight=float(d["weight"]))  
            if not cmd["exercise"]:  
                return snapshot(reply("Exercise required", "", "warn"))  
            return snapshot(dispatch(cmd))  
        except Exception as exc:  
            return snapshot(reply("Invalid entry", str(exc), "warn"))


if __name__ == "__main__":  
    store.init()  
    print(f"Workout tracker running -> http://0.0.0.0:{config.PORT}")  
    try:  
        from waitress import serve  
        serve(app, host=config.HOST, port=config.PORT, threads=4)  
    except ImportError:  
        app.run(host=config.HOST, port=config.PORT, threaded=True)  