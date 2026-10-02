"""Text -> structured command. Rules only; same output contract the LLM will use."""

import re

import config  
import store

ACTIONS = {"log_workout", "show_pr", "show_history", "show_program",  
           "undo", "help", "unknown"}

_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,  
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,  
          "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,  
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,  
          "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,  
          "seventy": 70, "eighty": 80, "ninety": 90}  
_TENS = {"twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"}  
_ONES = {w for w, v in _WORDS.items() if 1 <= v <= 9}

_SCHEME = re.compile(r"\b(\d{1,2})\s*(?:x|by|\*|sets?\s+of|set\s+of)\s*(\d{1,3})\b")  
_ADDED = re.compile(r"\+\s*(?P<n>\d{1,4}(?:\.\d+)?)")  
_ANCHORED = re.compile(r"(?:@|\bat\b|\bfor\b|\bwith\b|\busing\b)\s*"  
                       r"(?P<n>\d{1,4}(?:\.\d+)?)\s*(?P<u>lbs?|pounds?|kgs?|kilos?)?")  
_UNITED = re.compile(r"\b(?P<n>\d{1,4}(?:\.\d+)?)\s*(?P<u>lbs?|pounds?|kgs?|kilos?)\b")  
_NUMBER = re.compile(r"\d{1,4}(?:\.\d+)?")

_FILLER = re.compile(  
    r"\b(i|just|did|do|does|done|log|logged|add|added|record|whats|what|is|was|"  
    r"my|the|a|an|for|at|with|on|of|set|sets|rep|reps|pr|prs|personal|records?|"  
    r"best|max|please|show|me|get|history|last|time|recent|previously|and|then|"  
    r"to|today|am|supposed|doing|up|lift|lifted|hit|some)\b")

PROMPTS = {"exercise": "Which exercise?", "sets": "How many sets?",  
           "reps": "How many reps?", "weight": "What weight?"}

UNDO_WORDS = {"undo", "scratch that", "delete last", "oops", "nevermind",  
              "nvm", "remove last", "mistake"}  
HELP_WORDS = {"help", "?", "commands", "h"}


def normalize_numbers(text):  
    """'two twenty five' -> '225'. Needed now for typing, essential later for speech."""  
    toks = re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip().split()  
    out, i = [], 0  
    while i < len(toks):  
        w = toks[i]  
        # "two twenty five" -> 225  
        if w in _ONES and i + 1 < len(toks) and toks[i + 1] in _TENS:  
            val, j = _WORDS[w] * 100 + _WORDS[toks[i + 1]], i + 2  
            if j < len(toks) and toks[j] in _ONES:  
                val += _WORDS[toks[j]]  
                j += 1  
            out.append(str(val))  
            i = j  
            continue  
        # "one hundred thirty five" -> 135  
        if (w in _ONES or w == "a") and i + 1 < len(toks) and toks[i + 1] == "hundred":  
            val, j = _WORDS.get(w, 1) * 100, i + 2  
            if j < len(toks) and toks[j] in _TENS:  
                val += _WORDS[toks[j]]  
                j += 1  
                if j < len(toks) and toks[j] in _ONES:  
                    val += _WORDS[toks[j]]  
                    j += 1  
            elif j < len(toks) and toks[j] in _WORDS and _WORDS[toks[j]] < 100:  
                val += _WORDS[toks[j]]  
                j += 1  
            out.append(str(val))  
            i = j  
            continue  
        out.append(str(_WORDS[w]) if w in _WORDS else w)  
        i += 1  
    return " ".join(out)


def blank(action="unknown", **kw):  
    cmd = {"action": action, "exercise": None, "sets": None, "reps": None,  
           "weight": None, "unit": config.DEFAULT_UNIT, "weight_type": "absolute"}  
    cmd.update(kw)  
    return cmd


def parse(text):  
    raw = (text or "").strip()  
    if not raw:  
        return blank()

    low_raw = raw.lower()  
    if low_raw in UNDO_WORDS:  
        return blank("undo")  
    if low_raw in HELP_WORDS:  
        return blank("help")

    t = normalize_numbers(raw)  
    low = t.lower()

    scheme = _SCHEME.search(t)

    if re.search(r"\b(program|supposed to do|doing today|workout today|"  
                 r"whats next|plan)\b", low) and not scheme:  
        return blank("show_program")

    wants_pr = bool(re.search(r"\b(pr|personal record|best|max)\b", low))  
    wants_hist = bool(re.search(r"\b(history|last time|recent|previously)\b", low))

    sets = reps = None  
    residue = t  
    if scheme:  
        sets, reps = int(scheme.group(1)), int(scheme.group(2))  
        residue = residue.replace(scheme.group(0), " ")

    weight, unit, wtype = None, config.DEFAULT_UNIT, "absolute"

    if re.search(r"\b(bw|bodyweight|body weight)\b", low):  
        weight, wtype = 0.0, "bodyweight"  
        residue = re.sub(r"\b(bw|bodyweight|body weight)\b", " ", residue)

    if weight is None:  
        for rx, kind in ((_ADDED, "added"), (_ANCHORED, "absolute"), (_UNITED, "absolute")):  
            m = rx.search(residue)  
            if not m:  
                continue  
            weight = float(m.group("n"))  
            wtype = kind  
            u = m.groupdict().get("u")  
            if u and u.startswith(("kg", "kilo")):  
                unit = "kg"  
            residue = residue.replace(m.group(0), " ")  
            break

    # bare trailing number: "bench 3x8 225"  
    if weight is None and scheme:  
        nums = _NUMBER.findall(residue)  
        if len(nums) == 1:  
            weight = float(nums[0])  
            residue = residue.replace(nums[0], " ")

    residue = _FILLER.sub(" ", residue)  
    residue = re.sub(r"[^a-zA-Z ]+", " ", residue)  
    residue = re.sub(r"\s+", " ", residue).strip()  
    exercise = store.canonicalize(residue) if residue else None

    if wants_pr:  
        return blank("show_pr", exercise=exercise, sets=sets, reps=reps)  
    if wants_hist:  
        return blank("show_history", exercise=exercise, sets=sets, reps=reps)  
    if exercise or sets or reps or weight is not None:  
        return blank("log_workout", exercise=exercise, sets=sets, reps=reps,  
                     weight=weight, unit=unit, weight_type=wtype)  
    return blank()


def missing_fields(cmd):  
    if cmd["action"] == "log_workout":  
        return [f for f in ("exercise", "sets", "reps", "weight")  
                if cmd.get(f) is None]  
    if cmd["action"] in ("show_pr", "show_history"):  
        return ["exercise"] if cmd.get("exercise") is None else []  
    return []


def fill_slot(cmd, field, text):  
    """Interpret a bare reply like '225' or 'bench' as the answer to a prompt."""  
    if field == "exercise":  
        cmd["exercise"] = store.canonicalize(text)  
        return cmd  
    nums = _NUMBER.findall(normalize_numbers(text))  
    if nums:  
        cmd[field] = float(nums[0]) if field == "weight" else int(float(nums[0]))  
    return cmd  