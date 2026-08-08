import re
import random

VERB_BLACKLIST = {"identify", "describe", "explain", "discuss", "demonstrate", "perform", "apply", "analyze", "evaluate", "create", "define", "classify", "compare", "differentiate", "distinguish", "illustrate", "interpret", "solve", "use", "write", "read", "count", "name", "tell", "show", "practice", "recognize", "recall", "produce", "construct", "develop", "plan", "make", "do", "participate", "share", "express", "engage", "observe", "respond", "value", "appreciate", "state", "list", "enumerate", "label", "match", "sort", "order", "sequence", "cite", "give", "record", "gather", "collect", "communicate", "understand", "know", "add", "subtract", "multiply", "divide"}


def _time_band(time_str):
    if not time_str:
        return "standard"
    nums = re.findall(r"\d+", str(time_str))
    if not nums:
        return "standard"
    mins = int(nums[0])
    if mins <= 30:
        return "short"
    if mins >= 60:
        return "long"
    return "standard"


def _gerund(verb):
    if verb.endswith("ie"):
        return verb[:-3] + "ying"
    if verb.endswith("e"):
        return verb[:-1] + "ing"
    if verb == "add":
        return "adding"
    if verb == "subtract":
        return "subtracting"
    if verb == "multiply":
        return "multiplying"
    if verb == "divide":
        return "dividing"
    if re.search(r"[bcdfgklmnpqrstvz][aeiou][bcdfgklmnpqrstvz]$", verb) and not verb.endswith("w") and not verb.endswith("x"):
        return verb + verb[-1] + "ing"
    return verb + "ing"


def _nounify(verb):
    overrides = {
        "identify": "identification", "describe": "description", "explain": "explanation",
        "discuss": "discussion", "demonstrate": "demonstration", "perform": "performance",
        "apply": "application", "analyze": "analysis", "evaluate": "evaluation",
        "create": "creation", "define": "definition", "classify": "classification",
        "compare": "comparison", "differentiate": "differentiation",
        "distinguish": "distinction", "illustrate": "illustration",
        "interpret": "interpretation", "solve": "solving", "recognize": "recognition",
        "produce": "production", "construct": "construction", "develop": "development",
        "plan": "planning", "practice": "practicing", "use": "using",
        "read": "reading", "write": "writing", "count": "counting",
        "add": "adding", "subtract": "subtracting", "multiply": "multiplying",
        "divide": "dividing", "measure": "measurement", "tell": "telling",
        "name": "naming", "show": "showing", "make": "making",
        "participate": "participation", "share": "sharing", "express": "expression",
        "engage": "engagement", "observe": "observation", "respond": "response",
        "value": "valuing", "appreciate": "appreciation", "state": "stating",
        "list": "listing", "enumerate": "enumeration", "label": "labeling",
        "match": "matching", "sort": "sorting", "order": "ordering",
        "sequence": "sequencing", "cite": "citing", "give": "giving",
        "record": "recording", "gather": "gathering", "collect": "collecting",
        "communicate": "communication", "understand": "understanding", "know": "knowing",
    }
    return overrides.get(verb, _gerund(verb))


def _normalize_verb(word):
    word = word.lower().strip()
    candidates = [word]
    if word.endswith("ies"):
        candidates.append(word[:-3] + "y")
    if word.endswith("ied"):
        candidates.append(word[:-3] + "y")
    if word.endswith("ing"):
        stem = word[:-3]
        candidates.append(stem)
        candidates.append(stem + "e")
        if len(stem) >= 2 and stem.endswith(stem[-1]):
            candidates.append(stem[:-1])
    if word.endswith("ed"):
        stem = word[:-2]
        candidates.append(stem)
        candidates.append(stem + "e")
        if len(stem) >= 2 and stem.endswith(stem[-1]):
            candidates.append(stem[:-1])
    if word.endswith("es"):
        candidates.append(word[:-2])
    if word.endswith("s"):
        candidates.append(word[:-1])
    for candidate in candidates:
        if candidate in VERB_BLACKLIST:
            return candidate
    return word


def _parse_verb(competency_desc):
    if not competency_desc:
        return "understanding", "the topic", "understand"
    words = competency_desc.strip().split()
    verb = _normalize_verb(words[0])
    if verb in VERB_BLACKLIST:
        noun = _nounify(verb)
        rest = " ".join(words[1:]).strip()
        return noun, rest, verb
    return "understanding", competency_desc, "understand"


def _topic_from_comp(competency_desc):
    if not competency_desc:
        return "the lesson topic"
    desc = competency_desc.strip().rstrip(".")
    words = desc.split()
    verb = _normalize_verb(words[0])
    if verb in VERB_BLACKLIST and len(words) > 1:
        return f"{_gerund(verb)} {' '.join(words[1:]).strip()}"
    return desc[0].lower() + desc[1:]


def _subject_group(s):
    s = s.lower()
    if any(x in s for x in ["math"]):
        return "math"
    if any(x in s for x in ["science", "earth sci"]) and "social" not in s:
        return "science"
    if any(x in s for x in ["english", "reading", "oral", "language", "read",
                            "literature", "creative", "composition", "rhetoric"]):
        return "language"
    if any(x in s for x in ["filipino", "komunikasyon", "panitikan", "malikhaing",
                            "pagsulat", "kontemporaryong"]):
        return "filipino"
    if any(x in s for x in ["araling", "ap ", "makabansa", "ucsp", "kasaysayan",
                            "governance", "lipunan", "civic", "philosophy",
                            "social studies", "social sciences", "culture, society",
                            "society and politics"]):
        return "social_studies"
    if any(x in s for x in ["mapeh", "music", "art", "physical education",
                            "pehealth", "pe and health", "health"]):
        return "mapeh"
    if any(x in s for x in ["gmrc", "values", "persdev", "personal"]):
        return "values"
    if any(x in s for x in ["tle", "epp"]):
        return "tle"
    if any(x in s for x in ["statistics", "stats"]):
        return "math"
    return "general"


def _grade_band(g):
    m = re.search(r"grade\s*(\d+)", g.lower())
    grade = int(m.group(1)) if m else 0
    if "kindergarten" in g.lower() or grade == 0:
        return "k"
    if grade <= 3:
        return "primary"
    if grade <= 6:
        return "intermediate"
    if grade <= 10:
        return "jhs"
    return "shs"


# ---------------------------------------------------------------------------
# Language detection (Tagalog/Filipino generation for language & social
# studies subjects) and the new ILAW flow timing model.
# ---------------------------------------------------------------------------

_TL_MARKERS = [
    "araling panlipunan", "filipino", "makabansa", "gmrc", "values education",
    "malikhaing pagsulat", "kasaysayan", "panitikan", "komunikasyon",
    "kontemporaryong", "mga kontemporaryong isyu", "lipunan at kultura",
]
_TL_EXCLUDE = ["effective communication"]


def _is_tagalog(subject):
    s = (subject or "").strip().lower()
    if not s:
        return False
    if any(x in s for x in _TL_EXCLUDE):
        return False
    if any(m in s for m in _TL_MARKERS):
        return True
    if re.match(r"^ap\b", s):
        return True
    return False


_TL_VERBS = {
    "natatalakay", "nasusuri", "naipaliliwanag", "naipahahayag", "natataya",
    "naisasagawa", "nakapagsasagawa", "nakagagawa", "nailalarawan",
    "naibabahagi", "nagagamit", "nailalapat", "nakabubuo", "naiuugnay",
    "napapahalagahan", "napahahalagahan", "naipakikita", "naipapakita",
    "naisusulat", "nakikilala", "nakikilahok", "nakatutukoy", "natutukoy",
    "naisasabuhay", "nakababasa", "nakapagsasalita", "nakapagsusulat",
    "naipamamalas", "nasasabi", "nabibigyang", "napaghahambing",
    "naiisa-isa", "nasasagot", "nakapagpapakita", "naisasagawa",
    "naglalarawan", "nakapagmumuni-muni", "napagsusuri", "naiisaayos",
    "naisasaayos", "naipapaliwanag", "nakapagpapaliwanag", "nakapagsasabi",
    "nakapagsasagawa", "naibibigay", "nakapagbibigay", "nakapagmamalas",
}


def _tl_parse(desc):
    """Split a Filipino competency into (verb, full_phrase, core_topic)."""
    if not desc:
        return "", "", ""
    words = desc.strip().split()
    verb = words[0].lower().rstrip(".")
    if verb in _TL_VERBS:
        rest = " ".join(words[1:]).strip()
    else:
        verb = ""
        rest = desc.strip()
    core = re.sub(r"^ang\s+(mga\s+)?", "", rest, flags=re.I).strip() or rest
    return verb, rest, core


_TL_SMALL = {
    "ang", "ng", "mga", "sa", "at", "o", "na", "ay", "ngunit", "pero",
    "dahil", "kung", "kapag", "upang", "para", "kay", "kina", "si", "sina",
    "ni", "nina", "ito", "iyan", "iyon", "nga", "din", "rin", "pa", "naman",
    "de", "sa mga", "na mga", "isang",
}


def _tl_title(core):
    """Title-case a Filipino topic phrase for a lesson name."""
    if not core:
        return ""
    words = core.split()
    if not words:
        return core
    out = []
    for i, w in enumerate(words):
        if i == 0 or w.lower() not in _TL_SMALL:
            out.append(w.capitalize())
        else:
            out.append(w.lower())
    return " ".join(out)


def _parse_minutes(time_str):
    """Parse time allotment like '50 mins', '1 hour', '1 hour and 30 mins'."""
    if not time_str:
        return 50
    t = str(time_str).lower()
    if "hour" in t or re.search(r"\b\d+\s*h\b", t):
        hours = re.findall(r"(\d+)\s*h(?:our|r)?", t)
        mins = re.findall(r"(\d+)\s*m(?:in)?", t)
        total = (int(hours[0]) if hours else 0) * 60
        if mins:
            total += int(mins[0])
        if total:
            return total
    nums = re.findall(r"\d+", t)
    return int(nums[0]) if nums else 50


def _flow_times(total):
    """ILAW flow model: Introduce 1-3 min, Apply 15 min, Wrap-up up to 5 min,
    and Learn gets the remaining (biggest) share of the period."""
    total = max(int(total or 50), 30)
    intro = 3 if total >= 55 else (2 if total >= 40 else 1)
    apply = 15 if total >= 35 else 12
    wrap = min(5, max(2, total // 10))
    learn = total - intro - apply - wrap
    while learn < apply and wrap > 0:  # keep Learn as the biggest share
        wrap -= 1
        learn += 1
    while learn < apply and intro > 1:
        intro -= 1
        learn += 1
    return intro, learn, apply, wrap


def flow_times_dict(total):
    """Public map of the ILAW time budget: {introduce, learn, apply, wrap}."""
    intro, learn, apply, wrap = _flow_times(total)
    return {"introduce": intro, "learn": learn, "apply": apply, "wrap": wrap}


def _split_minutes(total, weights):
    """Split a minute total into integer parts proportional to weights."""
    total = max(int(total), 1)
    parts = []
    used = 0
    n = len(weights)
    for i, w in enumerate(weights):
        if i == n - 1:
            parts.append(max(total - used, 0))
        else:
            p = min(round(total * w), total - used - (n - i - 1))
            p = max(p, 1)
            parts.append(p)
            used += p
    return parts


def _obj_title(line):
    """A short title for an objective, used inside the Flow sections."""
    line = re.sub(r"^\d+[\.\)]\s*", "", line or "").strip().rstrip(".")
    if not line:
        return ""
    words = line.split()
    if len(words) > 7:
        return " ".join(words[:7]).rstrip(",") + "..."
    return line


def build_suggestions(subject, competency_desc, grade_level, time_allotment="50 mins",
                      content_standard="", performance_standard=""):
    band = _grade_band(grade_level)
    group = _subject_group(subject)
    total = _parse_minutes(time_allotment)

    if _is_tagalog(subject):
        _verb, _phrase, core = _tl_parse(competency_desc)
        topic = core or "ang aralin"
        objectives = _make_objectives_tl(competency_desc, core, band)
        obj_lines = _obj_lines(objectives)
        return _anchor_standards_tl({
            "lesson_name": _make_lesson_name_tl(core),
            "objectives": objectives,
            "integration": _make_integration_tl(core, group),
            "learner_context": _make_learner_context_tl(core, band),
            "pre_lesson": _make_pre_lesson_tl(group, band, core),
            "flow_introduce": _make_activating(group, band, topic, total, obj_lines, tl=True),
            "flow_learn": _make_developing(group, band, topic, total, obj_lines, tl=True),
            "flow_apply": _make_deepening(group, band, topic, total, obj_lines, tl=True),
            "flow_wrapup": _make_generalizations(group, band, topic, total, obj_lines, tl=True),
            "learning_resources": _make_learning_resources_tl(band, core),
            "formative_assessment": _make_formative_tl(band),
            "extended_learning": _make_extended_learning_tl(core),
            "reflection": _make_reflection(),
            "references": _make_references_tl(subject),
            "ai_declaration": _make_ai_declaration_tl(),
            # Learning Exemplar extras (Tagalog)
            "le_step1": _le_step1(group, band, topic, len(obj_lines), tl=True),
            "le_step2": _le_step2(group, band, topic, len(obj_lines), tl=True),
            "le_step3": _le_step3(group, band, topic, len(obj_lines), tl=True),
            "le_step4": _le_step4(group, band, topic, len(obj_lines), tl=True),
            "le_step5": _le_step5(group, band, topic, len(obj_lines), tl=True),
            "le_step6": _le_step6(group, band, topic, len(obj_lines), tl=True),
            "le_step7": _le_step7(group, band, topic, len(obj_lines), tl=True),
            "le_ann_pre": _le_annot(1, topic, tl=True),
            "le_ann_purpose": _le_annot(2, topic, tl=True),
            "le_ann_examples": _le_annot(3, topic, tl=True),
            "le_ann_concept": _le_annot(4, topic, tl=True),
            "le_ann_mastery": _le_annot(5, topic, tl=True),
            "le_ann_apply": _le_annot(6, topic, tl=True),
            "le_ann_general": _le_annot(7, topic, tl=True),
            "le_quiz": _le_quiz(group, band, topic, tl=True),
            "le_perf_overview": _le_perf_overview(group, band, topic, tl=True),
            "le_perf_directions": _le_perf_directions(group, band, topic, tl=True),
            "le_perf_rubric": _le_perf_rubric(group, band, topic, tl=True),
        }, content_standard, performance_standard)

    topic = _topic_from_comp(competency_desc)
    noun, rest, verb = _parse_verb(competency_desc)
    tb = _time_band(time_allotment)
    objectives = _make_objectives(competency_desc, topic, verb, rest, band)
    obj_lines = _obj_lines(objectives)

    return _anchor_standards({
        "lesson_name": _make_lesson_name(topic),
        "objectives": objectives,
        "integration": _make_integration(subject, topic),
        "learner_context": _make_learner_context(band, topic),
        "pre_lesson": _make_pre_lesson(group, band, topic, tb),
        # ILAW flow: Introduce, Learn, Apply, Wrap-up
        "flow_introduce": _make_activating(group, band, topic, total, obj_lines),
        "flow_learn": _make_developing(group, band, topic, total, obj_lines),
        "flow_apply": _make_deepening(group, band, topic, total, obj_lines),
        "flow_wrapup": _make_generalizations(group, band, topic, total, obj_lines),
        "learning_resources": _make_learning_resources(group, band, topic),
        "formative_assessment": _make_formative(group, band, tb),
        "extended_learning": _make_extended_learning(group, topic),
        "reflection": _make_reflection(),
        "references": _make_references(subject),
        "ai_declaration": _make_ai_declaration(),
        # Learning Exemplar extras (English)
        "le_step1": _le_step1(group, band, topic, len(obj_lines)),
        "le_step2": _le_step2(group, band, topic, len(obj_lines)),
        "le_step3": _le_step3(group, band, topic, len(obj_lines)),
        "le_step4": _le_step4(group, band, topic, len(obj_lines)),
        "le_step5": _le_step5(group, band, topic, len(obj_lines)),
        "le_step6": _le_step6(group, band, topic, len(obj_lines)),
        "le_step7": _le_step7(group, band, topic, len(obj_lines)),
        "le_ann_pre": _le_annot(1, topic),
        "le_ann_purpose": _le_annot(2, topic),
        "le_ann_examples": _le_annot(3, topic),
        "le_ann_concept": _le_annot(4, topic),
        "le_ann_mastery": _le_annot(5, topic),
        "le_ann_apply": _le_annot(6, topic),
        "le_ann_general": _le_annot(7, topic),
        "le_quiz": _le_quiz(group, band, topic),
        "le_perf_overview": _le_perf_overview(group, band, topic),
        "le_perf_directions": _le_perf_directions(group, band, topic),
        "le_perf_rubric": _le_perf_rubric(group, band, topic),
    }, content_standard, performance_standard)


def _anchor_standards(data, content_standard, performance_standard):
    cs = (content_standard or "").strip().rstrip(".")
    ps = (performance_standard or "").strip().rstrip(".")
    if cs:
        data["learner_context"] = (
            data["learner_context"]
            + f"\n\nLesson design is anchored on the content standard: {cs}."
        )
    if ps:
        data["flow_apply"] = (
            data["flow_apply"]
            + f"\n\nThis activity leads learners toward the performance standard: {ps}."
        )
    return data


def _obj_lines(objectives):
    if not objectives:
        return []
    lines = []
    for ln in objectives.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.lower().startswith(("by the end", "i will", "we will")):
            continue
        ln = re.sub(r"^\d+[\.\)]\s*", "", ln).strip()
        ln = ln.rstrip(".").strip()
        if not ln:
            continue
        if ln[0].isupper():
            ln = ln[0].lower() + ln[1:]
        lines.append(ln)
    return lines


def _act(a, key, topic):
    return a[key].replace("<topic>", topic)


def _make_lesson_name(topic):
    if not topic or topic == "the lesson topic":
        return ""
    words = topic.split()
    small = {"a", "an", "the", "and", "or", "of", "in", "on", "to", "for", "with", "at", "by", "sa", "ng", "mga", "ang"}
    titled = [w.capitalize() if (i == 0 or w.lower() not in small) else w.lower()
              for i, w in enumerate(words)]
    return " ".join(titled)


def _make_objectives(competency_desc, topic, verb, rest, band):
    """Build learner objectives from the actual competency verb so they are
    specific and aligned, not generic."""
    if band == "k":
        return random.choice([
            f"By the end of the lesson, learners will be able to:\n1. Tell what they know about {topic} through words, pictures, or actions.\n2. Join a simple class activity on {topic}.\n3. Share one thing they learned about {topic}.",
            f"By the end of the lesson, learners will be able to:\n1. Name or point to things connected to {topic}.\n2. Try a hands-on activity on {topic} with teacher help.\n3. Show or say what they learned about {topic}.",
        ])

    # Use the real competency skill: e.g. "Identify the parts and functions..."
    rest = (rest or "").rstrip(".").strip()
    skill = f"{verb} {rest}".strip() if verb and rest else topic
    skill = skill[0].upper() + skill[1:] if skill else "the lesson topic"
    skill_ger = _gerund(verb) + (" " + rest if rest else "") if verb else topic

    if band == "primary":
        return random.choice([
            f"By the end of the lesson, learners will be able to:\n1. {skill} under teacher guidance.\n2. Practice {skill_ger} through a simple activity or game.\n3. Show what they learned about {topic} in their own way.",
            f"By the end of the lesson, learners will be able to:\n1. Talk about {skill_ger} using simple words.\n2. Try {skill_ger} in pairs or small groups.\n3. Share one example of {skill_ger} they observed.",
        ])
    if band == "intermediate":
        return random.choice([
            f"By the end of the lesson, learners will be able to:\n1. {skill} with understanding.\n2. Demonstrate {skill_ger} in a guided activity or short task.\n3. Reflect on how {topic} connects to real life.",
            f"By the end of the lesson, learners will be able to:\n1. Explain the key ideas of {topic} in their own words.\n2. Practice {skill_ger} through pair or group work.\n3. Use {skill_ger} in a short task and check their work.",
        ])
    return random.choice([
        f"By the end of the lesson, learners will be able to:\n1. {skill} with accuracy.\n2. Practice {skill_ger} in a structured task or activity.\n3. Create or present an output related to {topic} and justify their choices.",
        f"By the end of the lesson, learners will be able to:\n1. {skill} independently.\n2. Demonstrate {skill_ger} in a given scenario or task.\n3. Evaluate the outcome of {skill_ger} and suggest improvements.",
    ])


def _make_integration(subject, topic):
    s = subject.lower()
    group = _subject_group(subject)
    options = {
        "math": [
            f"Financial Literacy and Numeracy: learners see how {topic} connects to everyday situations like counting money, comparing prices, or telling time.",
            f"Mathematics in daily life: learners use {topic} when sharing fairly, estimating amounts, or planning a simple budget.",
        ],
        "science": [
            f"Environmental Awareness: {topic} connects to caring for plants, animals, and the community.",
            f"Health and Safety: learners apply {topic} to everyday choices that keep themselves and others safe.",
        ],
        "language": [
            f"Communication: {topic} helps learners express ideas clearly in discussions and written work.",
            f"Reading and Writing: learners use {topic} when understanding stories, following instructions, and sharing their thoughts.",
        ],
        "filipino": [
            f"Pagpapahalaga sa Kultura: naipapakita ng {topic} ang pagpapahalaga sa sariling kultura at wika.",
            f"Komunikasyon: nakatutulong ang {topic} sa mas malinaw na pagpapahayag ng mga ideya sa klase.",
        ],
        "social_studies": [
            f"Civic Awareness: {topic} helps learners understand their role in the family, school, and community.",
            f"Cultural Understanding: {topic} connects learners to the traditions and experiences of people around them.",
        ],
        "mapeh": [
            f"Health and Wellness: {topic} supports a balanced and active lifestyle.",
            f"Creative Expression: {topic} lets learners express themselves through movement, art, or performance.",
        ],
        "values": [
            f"Moral and Social Development: {topic} encourages learners to practice respect and responsibility.",
            f"Community Values: {topic} connects to how learners treat others and contribute to their community.",
        ],
        "tle": [
            f"Livelihood and Entrepreneurship: {topic} gives learners practical skills for home and future work.",
            f"Technology and Innovation: {topic} builds practical, hands-on skills learners need today.",
        ],
    }
    lst = options.get(group, [f"Cross-curricular connection: {topic} ties into real life and other subjects."])
    return random.choice(lst)


def _make_learner_context(band, topic):
    if band == "k":
        return random.choice([
            f"Learners are still building vocabulary on {topic}, so words stay simple and repeated. They learn best through movement, songs, and hands-on tasks; a few are shy, so give everyone a turn in small groups.",
            f"Attention spans are short, so the lesson is broken into small, active chunks. Some learners already know a bit about {topic} while others meet it for the first time, so I make room for both.",
        ])
    if band == "primary":
        return random.choice([
            f"Prior knowledge of {topic} is uneven; some need help reading instructions. Use pair work, read aloud, and pictures alongside words so quieter learners can answer first.",
            f"Learners learn best through stories and games. Most have something to say about {topic}, but confidence varies, so I use simple starting points and build up step by step.",
        ])
    if band == "intermediate":
        return random.choice([
            f"Learners connect {topic} to real life and enjoy discussion, though a few prefer to work quietly. Offer choices in how they show learning and use quick checks to see who needs support.",
            f"This class brings a wide range of experience with {topic}. Pair and small-group work helps everyone contribute; sentence starters and extra time support those who need it.",
        ])
    return random.choice([
        f"Learners bring strong prior knowledge of {topic} and value independence. Provide choices, clear rubrics, and tasks that require real thinking; leave time for reflection.",
        f"A capable group, but they can finish quickly, so tasks must require real thinking. Mix groups to spread strong leaders and differentiate so everyone is stretched but no one is lost.",
    ])


def _make_pre_lesson(group, band, topic, tb="standard"):
    if tb == "short":
        if band == "k":
            return f"Show one picture on {topic}; ask 'What do you see?', take a few answers, then move on. (3 min)"
        if band == "primary":
            return f"Put a simple question about {topic} on the board; learners turn-and-talk with a partner, then share a few responses."
        if band == "intermediate":
            return f"Write a quick prompt on {topic}; learners jot one or two ideas, share with a partner, and a few report back."
        return f"Open with one question on {topic}; learners do a 2-minute quick write, then share a single idea."

    if tb == "long":
        if band == "k":
            return random.choice([
                f"Set up discovery tables with objects and pictures on {topic}; groups explore and talk about what they see, then share findings.",
                f"Gather in a circle and go through a picture book or big pictures on {topic}, pausing to ask what they notice or have seen before.",
            ])
        if band == "primary":
            return random.choice([
                f"Play 'guess the picture' with a partly hidden image on {topic}; learners guess, then share what they already know.",
                f"Show a few pictures on {topic} and ask what they have in common; learners pair-share, then we brainstorm and record responses.",
            ])
        if band == "intermediate":
            return random.choice([
                f"Pose 'What do you already know about {topic}?'; learners write, share with a partner, and we fill the K-W-L 'Know' column.",
                f"Present a short scenario on {topic} and ask what learners would do; they write a quick response, discuss in groups, then share.",
            ])
        return random.choice([
            f"Pose a reflective question like 'How does {topic} affect your daily life?'; learners write briefly, share in groups, and we build a concept map.",
            f"Show a thought-provoking image or short clip on {topic}; learners write their questions on sticky notes and we group them on the board.",
        ])

    if band == "k":
        return random.choice([
            f"Show a picture book or short clip on {topic}; ask what they saw and if they have experienced it before, then let them point or share.",
            f"Place real objects on {topic} in a mystery box; each child reaches in, feels one, guesses, and we talk about what we know.",
        ])
    if band == "primary":
        return random.choice([
            f"Play 'guess the picture' with a slowly revealed image on {topic}; learners guess, then share what they already know.",
            f"Play a quick 'yes or no' game with simple statements on {topic}; learners stand if they agree, and a few explain their answers.",
        ])
    if band == "intermediate":
        return random.choice([
            f"Post '{topic} — what do you already know?'; learners write, share with a partner, and we fill the K-W-L 'Know' column.",
            f"Present a short scenario on {topic} and ask what learners would do; they write a quick response, discuss in groups, and share.",
        ])
    return random.choice([
        f"Pose a quick question on {topic}; pairs share what they know, then with the class, and I record ideas on the board.",
        f"Show a picture or one-line quote on {topic} and ask learners to react; their answers lead naturally into the lesson.",
    ])


def _make_learning_resources(group, band, topic):
    if band == "k":
        return random.choice([
            f"DepEd K to 12 materials on {topic}\nReal objects, toys, and cut-outs\nPicture books, flashcards, and picture cards\nChart paper, crayons, and art materials",
            f"DepEd Curriculum Guide and Three-Term BOW\nPuppets or flannel board pieces for storytelling\nSorting trays and manipulatives\nSongs and chants (audio or live)",
        ])
    if band == "primary":
        return random.choice([
            f"DepEd Curriculum Guide and Three-Term BOW (SY 2026-2027)\nTextbook and learner's materials\nVisual aids and flashcards on {topic}\nWorksheets and hands-on manipulatives",
            f"DepEd Learning Portal (https://lrmds.deped.gov.ph/)\nStorybooks and reading passages on {topic}\nWhiteboard, chart paper, and markers\nGames materials (picture puzzles, matching cards)",
        ])
    if band == "intermediate":
        return random.choice([
            f"DepEd Curriculum Guide and Three-Term BOW (SY 2026-2027)\nLearner's module and supplementary reading materials\nPowerPoint, video clips, and online resources on {topic}\nGraphic organizers and rubrics",
            f"DepEd Learning Portal (https://lrmds.deped.gov.ph/)\nReference books and articles on {topic}\nCase studies and real-world scenarios\nTask cards or quiz cards for practice",
        ])
    return random.choice([
        f"DepEd Curriculum Guide and Three-Term BOW (SY 2026-2027)\nLearner's module and reference textbooks on {topic}\nVideo clips, articles, and scholarly resources\nGraphic organizers, rubrics, and assessment checklists",
        f"DepEd Learning Portal (https://lrmds.deped.gov.ph/)\nCase studies and current-event articles on {topic}\nResearch references and online databases\nTask cards and scenario prompts for group work",
    ])


def _make_extended_learning(group, topic):
    return random.choice([
        f"Learners may explore {topic} at home through a simple investigation or family interview and share their findings in the next session.",
        f"Learners may read an article or watch an educational video on {topic} at home and create a short output (drawing, journal, or mini-report) to share.",
        f"Invite learners to apply {topic} in a real situation at home or in the community; parents/guardians may guide and sign a short observation note.",
    ])


def _make_references(subject):
    return (
        "DepEd Three-Term Budget of Works (BOW) SY 2026-2027\n"
        f"DepEd Curriculum Guide – {subject}\n"
        "K to 12 Most Essential Learning Competencies (MELCs) with CG Codes\n"
        "DepEd Learning Portal (https://lrmds.deped.gov.ph/)"
    )


def _make_ai_declaration():
    return (
        "This lesson plan was developed with the assistance of LAMDAG (AI) to help "
        "generate ideas, organize content, and improve clarity. The AI served only "
        "as a support tool; the teacher made all final decisions and takes full "
        "responsibility for the lesson's accuracy and implementation."
    )


# Subject-aware activity ideas. <topic> is replaced with the competency skill.
_FLOW_TOOLS = {
    "math": {
        "hook": ["a number talk or 'how many?' estimation game", "a word problem written on the board", "a quick 'which is more?' voting poll"],
        "model": ["solve 2-3 examples on the board while thinking aloud", "show a step-by-step worked example and ask what I did next"],
        "guided": ["pairs solve one item on their mini-whiteboards while I circulate", "a 'number flip' game where the class solves each step together"],
        "apply": ["a problem set or word-problem worksheet on <topic>", "groups create and swap their own <topic> problems"],
        "check": ["one mini-whiteboard problem and a 'fist-to-five' confidence check", "exit slip: solve one item on <topic> and explain in one sentence"],
    },
    "science": {
        "hook": ["a short demonstration, photo, or 'predict what will happen' question", "a mystery object or sample to observe", "a quick 'do you agree?' statement about <topic>"],
        "model": ["run a short demonstration and label each part as you go", "show a labeled diagram or short video, stopping to explain each step"],
        "guided": ["pairs complete a guided observation sheet while I circulate", "small groups arrange picture cards into the correct order"],
        "apply": ["a hands-on observation, mini-experiment, or classification task on <topic>", "groups investigate one example of <topic> and record findings"],
        "check": ["a labeled drawing plus one oral explanation", "exit slip: 'one new thing I observed about <topic> is...'"],
    },
    "language": {
        "hook": ["a short picture, prompt, or opening line that sparks curiosity", "a 'what comes next?' prediction from a story or text", "a quick word-splash of key vocabulary on <topic>"],
        "model": ["read/model one example aloud, showing how to build the response", "think aloud through a short passage on <topic>"],
        "guided": ["pairs build one example together using sentence starters I provide", "shared reading/writing where the class completes each line together"],
        "apply": ["learners draft their own short response, story, or paragraph on <topic>", "groups retell, summarize, or perform a short piece on <topic>"],
        "check": ["a partner share plus a one-line written summary", "exit slip: finish the sentence 'From this lesson, I can <topic>...'"],
    },
    "filipino": {
        "hook": ["isang larawan o tanong na kaugnay ng <topic>", "isang maikling kwento o awit na nagsisimula sa <topic>"],
        "model": ["gumawa ng halimbawa nang malakas, isa-isang ipakita ang hakbang", "magbasa/magsalaysay ng isang maikling halimbawa sa <topic>"],
        "guided": ["magpares ang mga bata at magsanay gamit ang gabay kong pangungusap", "sabay-sabay na bumuo ng isang pangungusap/palitan sa <topic>"],
        "apply": ["magsulat o magsalaysay ang mga bata ng sarili nilang bersyon sa <topic>", "magpangkat at magsagawa ng maikling talata/roleplay sa <topic>"],
        "check": ["magbahagi ng isang pangungusap na buod", "exit slip: 'Natutuhan ko na sa <topic>...'"],
    },
    "social_studies": {
        "hook": ["a map, photo, timeline, or current event that sparks curiosity", "a 'what would you do?' scenario on <topic>"],
        "model": ["walk through one example using a timeline, map, or diagram", "think aloud through a short case or story on <topic>"],
        "guided": ["pairs answer guiding questions on a short reading or map", "small groups sort events/ideas on <topic> into a sequence"],
        "apply": ["groups analyze a case or scenario on <topic> and prepare a short report", "a gallery walk where groups post their ideas on <topic>"],
        "check": ["a 'claim-evidence' one-liner on <topic>", "exit slip: name one example of <topic> in their community"],
    },
    "mapeh": {
        "hook": ["a short video clip, song, or movement warm-up", "a quick 'freeze! copy my move' game", "show a finished artwork/routine and ask how it was made"],
        "model": ["demonstrate the movement, rhythm, or technique slowly, step by step", "show one short sequence and have learners mirror it"],
        "guided": ["everyone performs one short section together while I correct form", "pairs practice the movement/rhythm and give each other one tip"],
        "apply": ["small groups combine <topic> into a short routine, artwork, or performance", "create a variation of <topic> and teach it to the group"],
        "check": ["a quick performance with peer feedback using a simple rubric", "exit slip: one thing they improved on <topic> today"],
    },
    "values": {
        "hook": ["a short story, quote, or 'what would you do?' situation", "a picture of a real-life situation that sparks curiosity"],
        "model": ["tell/show one example and think aloud about the value being practiced", "role-play one short scenario on <topic>"],
        "guided": ["pairs discuss a scenario and share what they would do and why", "small groups sort actions as 'showing <topic>' or 'not yet'"],
        "apply": ["groups role-play or write a short skit that shows <topic> in action", "learners write a short promise/pledge on applying <topic>"],
        "check": ["a quick share of one way they will practice <topic> today", "exit slip: finish 'I will show <topic> when...'"],
    },
    "tle": {
        "hook": ["a finished sample/product or a short demo video", "a 'guess what this tool is for' show-and-tell", "a real object or recipe/materials related to <topic>"],
        "model": ["demonstrate the procedure step by step, pointing out safety and quality points", "show one full sample while explaining each decision"],
        "guided": ["pairs try one step with my feedback before doing the full task", "stations where each group practices one part of <topic>"],
        "apply": ["learners produce their own output on <topic> following a checklist", "groups complete a project and self-check against a rubric"],
        "check": ["a finished product checked against the checklist", "exit slip: 'the most important step in <topic> is...'"],
    },
    "general": {
        "hook": ["a picture, question, or short clip that sparks curiosity", "a quick 'what do you think?' poll on <topic>"],
        "model": ["show one example step by step while thinking aloud", "walk through a short sample on <topic> together"],
        "guided": ["pairs practice one item while I circulate and give feedback", "the class completes one example together with my prompts"],
        "apply": ["learners complete a structured task on <topic>", "small groups work on a short output on <topic>"],
        "check": ["one quick-write and a thumbs check", "exit slip: one sentence summary of <topic>"],
    },
}


# Tagalog variants of the activity tools, used for AP / Filipino / GMRC /
# Makabansa / SHS Filipino & social-science subjects.
_FLOW_TOOLS_TL = {
    "filipino": {
        "hook": ["isang larawan, awit, o maikling kuwento na kaugnay ng <topic>",
                 "isang tanong o palaisipan na mag-uudyok ng usapan hinggil sa <topic>"],
        "model": ["magpakita ng isang halimbawa nang hakbang-hakbang, na binibigkas nang malakas ang bawat hakbang",
                  "magbasa o magsalaysay ng isang maikling halimbawa hinggil sa <topic>"],
        "guided": ["magpares ang mga mag-aaral at magsanay gamit ang gabay na pangungusap",
                   "sabay-sabay na bumuo ng isang halimbawa o pangungusap tungkol sa <topic>"],
        "apply": ["magsulat o magsalaysay ang mga mag-aaral ng kanilang sariling bersyon hinggil sa <topic>",
                  "magpangkat at magsagawa ng maikling talata o roleplay sa <topic>"],
        "check": ["isang pangungusap na buod o pagbabahagi",
                  "exit slip: 'Natutuhan ko na sa <topic>...'"],
    },
    "social_studies": {
        "hook": ["isang larawan, mapa, timeline, o pangyayari sa kasalukuyan na nag-uudyok ng usapan",
                 "isang sitwasyong 'ano ang iyong gagawin?' hinggil sa <topic>"],
        "model": ["ipaliwanag ang isang halimbawa nang hakbang-hakbang gamit ang timeline, mapa, o dayagram",
                  "isalaysay ang isang maikling kaso o kuwento hinggil sa <topic>"],
        "guided": ["magpares ang mga mag-aaral at sagutin ang mga gabay na tanong sa isang maikling babasahin",
                   "pagpangkat-pangkatin at ayusin ang mga ideya o pangyayari hinggil sa <topic>"],
        "apply": ["suriin ng mga pangkat ang isang sitwasyon hinggil sa <topic> at gumawa ng maikling ulat",
                  "gumawa ng gallery walk kung saan inilalathala ng mga pangkat ang kanilang mga ideya"],
        "check": ["isang pangungusap na 'patunay at ebidensya' hinggil sa <topic>",
                  "exit slip: magbigay ng isang halimbawa ng <topic> sa inyong pamayanan"],
    },
    "values": {
        "hook": ["isang maikling kuwento, kasabihan, o sitwasyong 'ano ang gagawin mo?'",
                 "isang larawan ng totoong sitwasyon sa buhay"],
        "model": ["magkuwento o magpakita ng isang halimbawa at ipaliwanag ang pagpapahalagang isinasabuhay",
                  "mag-roleplay ng isang maikling sitwasyon hinggil sa <topic>"],
        "guided": ["magpares ang mga mag-aaral at talakayin kung ano ang gagawin at bakit",
                   "pagpangkat-pangkatin at pagsunud-sunurin ang mga kilos na nagpapakita ng <topic>"],
        "apply": ["gumawa ng maikling dula o pangako ang mga pangkat na magpapakita ng <topic> sa aksyon",
                  "isulat ng mga mag-aaral ang isang paraan kung paano isasabuhay ang <topic>"],
        "check": ["isang maikling pagbabahagi ng isang paraan upang maisabuhay ang <topic>",
                  "exit slip: 'Ipapakita ko ang <topic> kapag...'"],
    },
    "general": {
        "hook": ["isang larawan, tanong, o maikling bidyo na pumukaw ng interes",
                 "isang mabilis na botohan o 'ano sa palagay ninyo?' hinggil sa <topic>"],
        "model": ["ipakita ang isang halimbawa nang hakbang-hakbang habang ipinapaliwanag",
                  "sabay-sabay na talakayin ang isang halimbawa hinggil sa <topic>"],
        "guided": ["magpares ang mga mag-aaral at magsanay habang umiikot ang guro",
                   "buuin nang sama-sama ang isang halimbawa sa tulong ng guro"],
        "apply": ["kumpletuhin ng mga mag-aaral ang isang nakaayos na gawain hinggil sa <topic>",
                  "magpangkat at gumawa ng maikling awtput hinggil sa <topic>"],
        "check": ["isang mabilis na pagsulat at thumbs check",
                  "exit slip: isang pangungusap na buod ng <topic>"],
    },
}


def _flow_tool(group, key, topic, tl=False):
    if tl:
        pool = _FLOW_TOOLS_TL.get(group, _FLOW_TOOLS_TL["general"])
    else:
        pool = _FLOW_TOOLS.get(group, _FLOW_TOOLS["general"])
    return random.choice(pool[key]).replace("<topic>", topic)


def _make_activating(group, band, topic, total=50, obj_lines=(), tl=False):
    intro, learn, apply, wrap = _flow_times(total)
    hook = _flow_tool(group, "hook", topic, tl)
    title = _obj_title(obj_lines[0]) if obj_lines else ""
    if tl:
        goal = f"Layunin 1: {title}" if title else "ang layunin ng aralin ngayon"
        return "\n".join([
            f"1. {intro} min — Pagganyak at Pagtatakda ng Layunin: {hook.capitalize()}. "
            f"Ilahad ang {goal} sa mga salitang madaling unawain ng mga mag-aaral.",
        ])
    goal = f"Objective 1: {title}" if title else "today's objective"
    return "\n".join([
        f"1. {intro} min — Motivate & set the goal: {hook.capitalize()}. "
        f"State {goal} in learner-friendly words.",
    ])


def _make_developing(group, band, topic, total=50, obj_lines=(), tl=False):
    intro, learn, apply, wrap = _flow_times(total)
    splits = _split_minutes(learn, (0.30, 0.50, 0.20))
    model = _flow_tool(group, "model", topic, tl)
    guided = _flow_tool(group, "guided", topic, tl)
    check = _flow_tool(group, "check", topic, tl)
    if tl:
        t2 = f"Layunin 2: {_obj_title(obj_lines[1])}" if len(obj_lines) > 1 else "ang layunin"
        return "\n".join([
            f"1. {splits[0]} min — Direktang Pagtuturo (Pagmomodelo): {model.capitalize()}. "
            f"Gawing hakbang-hakbang at iugnay ang bawat hakbang sa {topic}.",
            f"2. {splits[1]} min — Pinatnubayang Pagsasanay: {guided.capitalize()} — tungo ito sa {t2}.",
            f"3. {splits[2]} min — Pagtataya ng Pag-unawa: {check.capitalize()} upang matiyak "
            f"na handa na ang mga mag-aaral bago ang bahaging Aplikasyon.",
        ])
    t2 = f"Objective 2: {_obj_title(obj_lines[1])}" if len(obj_lines) > 1 else "the objective"
    return "\n".join([
        f"1. {splits[0]} min — Direct Instruction (Model): {model.capitalize()}. "
        f"Keep it step-by-step and link each step back to {topic}.",
        f"2. {splits[1]} min — Guided Practice: {guided.capitalize()} — this moves learners toward {t2}.",
        f"3. {splits[2]} min — Check for Understanding: {check.capitalize()} to confirm "
        f"mastery before the Apply phase.",
    ])


def _make_deepening(group, band, topic, total=50, obj_lines=(), tl=False):
    intro, learn, apply, wrap = _flow_times(total)
    a1 = apply * 2 // 3
    a2 = apply - a1
    app = _flow_tool(group, "apply", topic, tl)
    if tl:
        t3 = f"Layunin 3: {_obj_title(obj_lines[2])}" if len(obj_lines) > 2 else "ang layunin"
        return "\n".join([
            f"1. {a1} min — Aplikasyon: {app.capitalize()} — isang nakaayos na gawain na "
            f"nagpapakita ng {t3}.",
            f"2. {a2} min — Pagbabahagi at Feedback: magpakitang-bahagi nang maikli ang mga pangkat; "
            f"magbigay ng isang positibong komento at iugnay ang mga awtput sa tunay na buhay.",
        ])
    t3 = f"Objective 3: {_obj_title(obj_lines[2])}" if len(obj_lines) > 2 else "the objective"
    return "\n".join([
        f"1. {a1} min — Apply: {app.capitalize()} — a structured task that demonstrates {t3}.",
        f"2. {a2} min — Share & feedback: groups present briefly; classmates give one positive "
        f"comment and I connect outputs to real life.",
    ])


def _make_generalizations(group, band, topic, total=50, obj_lines=(), tl=False):
    intro, learn, apply, wrap = _flow_times(total)
    if wrap >= 4:
        s = (wrap // 2, wrap - wrap // 2)
    else:
        s = (wrap,)
    if tl:
        if len(s) > 1:
            return "\n".join([
                f"1. {s[0]} min — Paglalahat: ibubuod ng mga mag-aaral sa isang pangungusap ang "
                f"pangunahing kaisipan tungkol sa {topic}; magbabahagi ang ilan.",
                f"2. {s[1]} min — Pagninilay at exit slip: 3-2-1 (3 natutuhan, 2 kawili-wili, "
                f"1 natitirang tanong); ipunin ang mga slips upang maiplano ang susunod na sesyon.",
            ])
        return "\n".join([
            f"1. {s[0]} min — Paglalahat at exit slip: isusulat ng mga mag-aaral ang isang "
            f"pangungusap na buod ng {topic}; ipunin ang mga 3-2-1 slips.",
        ])
    if len(s) > 1:
        return "\n".join([
            f"1. {s[0]} min — Generalize: learners summarize the key idea of {topic} in one "
            f"sentence; a few share aloud.",
            f"2. {s[1]} min — Reflect & exit slip: 3-2-1 (3 learned, 2 interesting, 1 question); "
            f"collect slips to plan the next session.",
        ])
    return "\n".join([
        f"1. {s[0]} min — Generalize & exit slip: learners write a one-line summary of {topic}; "
        f"collect 3-2-1 slips.",
    ])


# ---------------------------------------------------------------------------
# Lesson Exemplar extra content: per-step annotations, Presenting Examples /
# Developing Mastery content, and the VI. ASSESSMENT block (quiz + performance
# task). English subjects get English text; Tagalog subjects get Tagalog.
# ---------------------------------------------------------------------------

_LE_ANNOTATIONS = {
    1: {
        "en": [
            "This phase activates learners' prior knowledge and lived experiences using a constructivist approach, in which meaning is built on what they already know. Pair and class sharing makes their ideas visible before the new concept is introduced.",
            "Activating prior knowledge grounds the new lesson in what learners already know, an application of schema theory. Sharing ideas aloud values their voices and builds a bridge to the new concept.",
        ],
        "tl": [
            "Ang bahaging ito ay nagpapagana ng dating kaalaman at karanasan ng mga mag-aaral gamit ang konstruktibistang dulog, kung saan nabubuo ang kahulugan batay sa alam na nila. Nakikita ang kanilang mga ideya sa pamamagitan ng pagbabahagi sa kapareha at sa klase bago ipakilala ang bagong konsepto.",
            "Ang pagpapagana ng dating kaalaman ay nag-uugnay ng bagong aralin sa alam na ng mga mag-aaral (schema theory). Ang pagbabahagi ng mga ideya ay nagpapahalaga sa kanilang boses at naghahanda sa bagong konsepto.",
        ],
    },
    2: {
        "en": [
            "Stating the lesson purpose and objectives reflects explicit instruction, giving learners a clear target and keeping the session focused. Connecting the objectives to real life motivates learners and shows the value of the lesson.",
            "Clear objectives provide constructive alignment between the competency, the activities, and the assessment, so every learner knows what success looks like and why it matters.",
        ],
        "tl": [
            "Ang paglalahad ng layunin ng aralin ay halimbawa ng eksplisit na pagtuturo; binibigyan nito ang mga mag-aaral ng malinaw na direksyon at pokus. Ang pag-uugnay ng mga layunin sa totoong buhay ay nag-uudyok sa kanila at nagpapakita ng kahalagahan ng aralin.",
            "Ang malinaw na mga layunin ay nagbibigay ng matatag na ugnayan sa pagitan ng kasanayan, mga gawain, at pagtataya, upang malaman ng bawat mag-aaral kung ano ang tagumpay at kung bakit ito mahalaga.",
        ],
    },
    3: {
        "en": [
            "Concrete examples serve as a model of the concept before learners try it themselves (modeling). Varied examples help learners recognize patterns and build confidence for the guided practice that follows.",
            "Showing examples first is a form of scaffolding, giving learners a concrete anchor they can refer back to as the lesson becomes more abstract.",
        ],
        "tl": [
            "Ang mga kongkretong halimbawa ay nagsisilbing modelo ng konsepto bago subukan ng mga mag-aaral (pagmomodelo). Ang iba't ibang halimbawa ay tumutulong sa pagkilala ng mga pattern at nagbibigay ng kumpiyansa para sa susunod na gawain.",
            "Ang pagpapakita muna ng mga halimbawa ay isang paraan ng pagtutulak sa pag-unawa (scaffolding), na nagbibigay sa mga mag-aaral ng kongkretong basehan na maaaring balikan habang nagiging mas abstrak ang aralin.",
        ],
    },
    4: {
        "en": [
            "Guided discussion lets learners construct understanding with teacher support (gradual release of responsibility). Guiding questions move learners from recall to deeper analysis of the concept.",
            "Through inquiry-based discussion, learners examine the concept from different angles. The teacher clarifies and deepens understanding as learners form their own explanations.",
        ],
        "tl": [
            "Ang pinatnubayang talakayan ay nagpapabuo ng pag-unawa sa tulong ng guro (gradual release of responsibility). Ang mga gabay na tanong ay naglilipat ng pag-iisip mula sa paggunita tungo sa mas malalim na pagsusuri ng konsepto.",
            "Sa pamamagitan ng inquiry-based na talakayan, sinusuri ng mga mag-aaral ang konsepto mula sa iba't ibang anggulo. Nilinaw at pinalalalim ng guro ang pag-unawa habang bumubuo ang mga mag-aaral ng kanilang sariling paliwanag.",
        ],
    },
    5: {
        "en": [
            "Structured practice lets learners apply the concept with support and checks understanding before moving on (formative assessment). Early feedback corrects misconceptions while they are still manageable.",
            "Guided practice is the middle stage of gradual release, where learners begin working with more independence while the teacher circulates and gives targeted support.",
        ],
        "tl": [
            "Ang nakaayos na pagsasanay ay naglalapat ng konsepto habang may gabay at tinitiyak ang pag-unawa bago magpatuloy (pormatibong pagtataya). Ang agarang feedback ay nagwawasto sa maling pag-unawa nang maaga.",
            "Ang pinatnubayang pagsasanay ay ang gitnang bahagi ng gradual release, kung saan nagsisimulang gumawa nang may kalayaan ang mga mag-aaral habang umiikot ang guro at nagbibigay ng tiyak na suporta.",
        ],
    },
    6: {
        "en": [
            "Applying the concept to real-life situations shows its relevance and supports transfer of learning (authentic learning). Collaborative output lets learners demonstrate understanding in creative, meaningful ways.",
            "Real-life application makes the lesson observable and useful beyond the classroom, helping learners see the value of what they learned and take ownership of their output.",
        ],
        "tl": [
            "Ang paglalapat ng konsepto sa totoong buhay ay nagpapakita ng kaugnayan at paglilipat ng pagkatuto (awtentikong pagkatuto). Ang pangkatang awtput ay nagbibigay-daan sa mga mag-aaral na maipakita ang pag-unawa sa malikhain at makabuluhang paraan.",
            "Ang paglalapat sa totoong buhay ay nagiging nakikita at kapaki-pakinabang ang aralin sa labas ng silid-aralan, na tumutulong sa mga mag-aaral na makita ang halaga ng kanilang natutuhan at maging may-ari ng kanilang awtput.",
        ],
    },
    7: {
        "en": [
            "Having learners generalize in their own words consolidates learning and builds metacognition. The exit slip provides quick evidence of who has mastered the objective and what needs reteaching.",
            "Synthesizing the lesson into a big idea helps learners connect specific details to a broader understanding, a reflective practice that strengthens retention.",
        ],
        "tl": [
            "Ang pagbubuod ng mga mag-aaral sa kanilang sariling salita ay nagpapatatag ng pagkatuto at nagpapalalim ng metakognisyon. Ang exit slip ay mabilis na ebidensya kung sino ang nakamit ang layunin at kung ano ang kailangang ulitin.",
            "Ang pagbubuo ng aralin sa isang pangunahing kaisipan ay tumutulong sa mga mag-aaral na maiugnay ang mga tiyak na detalye sa mas malawak na pag-unawa, isang mapanimdim na kasanayang nagpapatibay ng pagkatuto.",
        ],
    },
}


def _le_annot(step, topic, tl=False):
    lang = "tl" if tl else "en"
    pool = _LE_ANNOTATIONS.get(step, {}).get(lang, [""])
    return random.choice(pool)


def _target_objectives(step, n, tl=False):
    """Which learner objectives a procedure step targets (official LE format
    shows e.g. 'Target Objective/s: Objectives 1, 2, and 3')."""
    fixed = {1: [1, 2], 2: None, 3: [1, 2], 4: [1, 2], 5: [2, 3], 6: [2, 3], 7: None}
    nums = fixed.get(step) or list(range(1, n + 1))
    nums = sorted(set(x for x in nums if x <= n)) or [1]
    word = "Layunin" if tl else "Objective"
    if len(nums) == 1:
        return f"{word} {nums[0]}"
    label = "Mga Layunin" if tl else "Objectives"
    if len(nums) == 2:
        joiner = " at " if tl else " and "
        return f"{label} {nums[0]}{joiner}{nums[1]}"
    sep = ", "
    last = f" at {nums[-1]}" if tl else f", and {nums[-1]}"
    return f"{label} {sep.join(str(x) for x in nums[:-1])}{last}"


def _le_step1(group, band, topic, n, tl=False):
    targets = _target_objectives(1, n, tl)
    if tl:
        return (
            f"Gawain 1: Think\u2013Pair\u2013Share \u2014 Ang Aking Alam\n"
            f"Target na Layunin: {targets}\n\n"
            "Mga Panuto:\n"
            "1. Mag-isip (Think): Isulat o gunitain ang lahat ng alam mo na tungkol sa {topic}.\n"
            "2. Magpares (Pair): Ibahagi ang iyong mga ideya sa katabi sa loob ng 2 minuto at pansinin ang pagkakatulad o pagkakaiba.\n"
            "3. Magbahagi (Share): Magboluntaryo ang ilang pares na ibahagi ang isang ideya sa klase; ilista ng guro ang mga ito sa pisara.\n\n"
            "Mga Gabay na Tanong:\n"
            "1. Ano ang alam mo na tungkol sa {topic}?\n"
            "2. Aling ideya ng iyong kapares ang bago sa iyo?\n"
            "3. Ano pa ang nais mong matutuhan tungkol sa {topic}?"
        )
    return (
        f"Activity 1: Think\u2013Pair\u2013Share \u2014 What I Already Know\n"
        f"Target Objective/s: {targets}\n\n"
        "Directions:\n"
        "1. Think: On your own, recall or write down everything you already know about {topic}.\n"
        "2. Pair: Share your ideas with a partner for 2 minutes and note any similarities or differences.\n"
        "3. Share: Pairs volunteer to share one idea with the class; the teacher lists these on the board.\n\n"
        "Processing Questions:\n"
        "1. What did you already know about {topic}?\n"
        "2. Which idea from your partner was new to you?\n"
        "3. What do you still want to find out about {topic}?"
    )


def _le_step2(group, band, topic, n, tl=False):
    targets = _target_objectives(2, n, tl)
    if tl:
        return (
            f"Gawain 2: Pagtatakda ng Ating Layunin\n"
            f"Target na Layunin: {targets}\n\n"
            "Mga Panuto:\n"
            "1. Basahin nang malakas ang mga layunin ng aralin.\n"
            "2. Talakayin ang ibig sabihin ng bawat layunin sa payak na salita.\n"
            "3. Magbigay ng halimbawa kung paano nauugnay ang bawat layunin sa totoong buhay.\n\n"
            "Mga Gabay na Tanong:\n"
            "1. Ano ang magagawa ninyo sa pagtatapos ng aralin?\n"
            "2. Bakit mahalaga ang mga layuning ito sa inyong pang-araw-araw na buhay?"
        )
    return (
        f"Activity 2: Setting Our Target\n"
        f"Target Objective/s: {targets}\n\n"
        "Directions:\n"
        "1. Read the lesson objectives aloud.\n"
        "2. Discuss what each objective means in simple words.\n"
        "3. Give one example of how each objective connects to real life.\n\n"
        "Processing Questions:\n"
        "1. What will you be able to do at the end of the lesson?\n"
        "2. Why are these objectives important in your everyday life?"
    )


def _le_step3(group, band, topic, n, tl=False):
    targets = _target_objectives(3, n, tl)
    if tl:
        return (
            f"Gawain 3: Tingnan, Isipin, at Matuto\n"
            f"Target na Layunin: {targets}\n\n"
            f"Opsyon 1: Magpakita ng 2-3 kongkretong halimbawa hinggil sa {topic} "
            "(larawan, maikling teksto, halimbawa, o demonstrasyon).\n\n"
            "Mga Panuto:\n"
            "1. Pagmasdan nang mabuti ang bawat halimbawa.\n"
            "2. Itala kung paano ipinapakita ng bawat isa ang paksa.\n"
            "3. Talakayin sa katabi kung bakit magandang modelo ng {topic} ang bawat halimbawa.\n\n"
            "Mga Gabay na Tanong:\n"
            "1. Ano ang pagkakatulad ng mga halimbawang ito?\n"
            "2. Paano ipinapakita ng bawat isa ang {topic}?\n"
            "3. Aling halimbawa ang higit na nakatulong sa inyong pag-unawa, at bakit?"
        )
    return (
        f"Activity 3: Look, Think, and Learn\n"
        f"Target Objective/s: {targets}\n\n"
        f"Option 1: Present 2-3 concrete examples on {topic} (pictures, short "
        "texts, samples, or demonstrations).\n\n"
        "Directions:\n"
        "1. Observe each example carefully.\n"
        "2. Note what each example shows about the topic.\n"
        "3. Discuss with your seatmate what makes each example a good model of {topic}.\n\n"
        "Processing Questions:\n"
        "1. What do these examples have in common?\n"
        "2. How does each one show {topic}?\n"
        "3. Which example helped you understand {topic} best, and why?"
    )


def _le_step4(group, band, topic, n, tl=False):
    targets = _target_objectives(4, n, tl)
    if tl:
        return (
            f"Gawain 4: Gabay na Pagsusuri\n"
            f"Target na Layunin: {targets}\n\n"
            "Mga Panuto:\n"
            "1. Ipaliwanag ng guro ang mga pangunahing ideya tungkol sa {topic} nang sunud-sunod gamit ang tsart, dayagram, o timeline.\n"
            "2. Itala ng mga mag-aaral ang mahahalagang impormasyon at magtanong kung may hindi malinaw.\n"
            "3. Sagutin nang magkapares ang mga gabay na tanong gamit ang bagong impormasyon.\n\n"
            "Mga Gabay na Tanong:\n"
            "1. Ano ang pinakamahalagang ideya tungkol sa {topic} na tinalakay ngayon?\n"
            "2. Paano nauugnay ang ideyang ito sa inyong dati nang kaalaman?\n"
            "3. Ano pa ang hindi ninyo lubos na nauunawaan?"
        )
    return (
        f"Activity 4: Guided Inquiry\n"
        f"Target Objective/s: {targets}\n\n"
        "Directions:\n"
        "1. The teacher presents the key ideas of {topic} step by step using a chart, diagram, or timeline.\n"
        "2. Learners take notes and ask clarifying questions.\n"
        "3. In pairs, learners answer the guiding questions using the new information.\n\n"
        "Processing Questions:\n"
        "1. What is the most important idea about {topic} presented today?\n"
        "2. How does this idea connect to what you already know?\n"
        "3. What is still unclear to you?"
    )


def _le_step5(group, band, topic, n, tl=False):
    targets = _target_objectives(5, n, tl)
    if tl:
        return (
            f"Gawain 5: Pagsasanay para sa Pag-unlad\n"
            f"Target na Layunin: {targets}\n\n"
            f"Opsyon 1: Kumpletuhin ang isang nakaayos na gawain sa {topic} "
            "(maikling pagsasanay, worksheet, o gabay na pagsusuri).\n\n"
            "Mga Panuto:\n"
            "1. Gumawa nang magkapares.\n"
            "2. Ilapat ang mga hakbang o kasanayang tinalakay sa aralin.\n"
            "3. Suriin ang inyong awtput batay sa mga gabay na tanong.\n\n"
            "Mga Gabay na Tanong:\n"
            "1. Anong mga hakbang ang sinundan ninyo?\n"
            "2. Ano ang naging madali o mahirap para sa inyo?\n"
            "3. Paano ninyo mapapabuti ang inyong sagot?"
        )
    return (
        f"Activity 5: Practice Makes Progress\n"
        f"Target Objective/s: {targets}\n\n"
        f"Option 1: Complete a structured practice task on {topic} (short "
        "exercise, worksheet, or guided analysis).\n\n"
        "Directions:\n"
        "1. Work in pairs.\n"
        "2. Apply the steps or skills discussed in the lesson.\n"
        "3. Check your work against the guiding questions below.\n\n"
        "Processing Questions:\n"
        "1. What steps did you follow?\n"
        "2. What did you find easy or difficult?\n"
        "3. How will you improve your answer?"
    )


def _le_step6(group, band, topic, n, tl=False):
    targets = _target_objectives(6, n, tl)
    if tl:
        return (
            f"Gawain 6: Ilapat sa Totoong Buhay\n"
            f"Target na Layunin: {targets}\n\n"
            "Mga Panuto:\n"
            "1. Sa inyong pangkat, pumili ng isang tunay na sitwasyon kung saan kinakailangan ang {topic}.\n"
            "2. Talakayin kung paano nakatutulong ang {topic} sa sitwasyong iyon.\n"
            "3. Maghanda ng maikling presentasyon (role play, poster, o skit) na nagpapakita ng napiling sitwasyon.\n"
            "4. Ipakita at ipaliwanag kung paano ginagamit ang {topic} sa sitwasyong iyon.\n\n"
            "Mga Gabay na Tanong:\n"
            "1. Saan ginagamit ng mga tao ang {topic} sa pang-araw-araw na buhay?\n"
            "2. Ano ang mangyayari kung hindi ilalapat ang {topic}?\n"
            "3. Paano nauugnay ang gawaing ito sa pamantayan sa pagganap ng aralin?"
        )
    return (
        f"Activity 6: Apply It to Real Life\n"
        f"Target Objective/s: {targets}\n\n"
        "Directions:\n"
        "1. In your group, choose a real-life situation where {topic} is needed.\n"
        "2. Discuss how {topic} helps in that situation.\n"
        "3. Prepare a short presentation (role play, poster, or skit) showing your chosen situation.\n"
        "4. Present and explain how the situation uses {topic}.\n\n"
        "Processing Questions:\n"
        "1. Where do people use {topic} in everyday life?\n"
        "2. What would happen if {topic} were not applied?\n"
        "3. How does this activity connect to the lesson's performance standard?"
    )


def _le_step7(group, band, topic, n, tl=False):
    targets = _target_objectives(7, n, tl)
    if tl:
        return (
            f"Gawain 7: Ang Aking Natutuhan Ngayon\n"
            f"Target na Layunin: {targets}\n\n"
            "Mga Panuto:\n"
            "1. Sumulat nang mag-isa ng isang pangungusap na buod ng pangunahing kaisipan tungkol sa {topic}.\n"
            "2. Kumpletuhin ang 3-2-1 na pagninilay: 3 natutuhan, 2 kawili-wiling ideya, 1 natitirang tanong.\n"
            "3. Ibahagi ang buod sa klase; kukunin ng guro ang mga pagninilay na sulat.\n\n"
            "Mga Gabay na Tanong:\n"
            "1. Ano ang pinakamahalagang bagay na natutuhan ninyo ngayon?\n"
            "2. Paano ninyo gagamitin ang {topic} mula ngayon?"
        )
    return (
        f"Activity 7: What I Learned Today\n"
        f"Target Objective/s: {targets}\n\n"
        "Directions:\n"
        "1. On your own, write one sentence summarizing the main idea about {topic}.\n"
        "2. Complete the 3-2-1 reflection: 3 things you learned, 2 interesting ideas, 1 question you still have.\n"
        "3. Share your summary with the class; the teacher collects the reflection slips.\n\n"
        "Processing Questions:\n"
        "1. What is the most important thing you learned today?\n"
        "2. How will you use {topic} from now on?"
    )


def _le_quiz(group, band, topic, tl=False):
    if tl:
        return (
            "Mga Panuto: Basahin nang mabuti ang bawat tanong at piliin ang titik "
            "ng tamang sagot. Isulat ang sagot sa \u00bc na papel.\n\n"
            "1. Alin sa mga sumusunod ang pinakamainam na paglalarawan sa {topic}?\n"
            "A. Ipinapaliwanag nito ang mga pangunahing ideya at kasanayan hinggil sa {topic}.\n"
            "B. Nakatuon lamang ito sa pagsasaulo ng mga kahulugan.\n"
            "C. Wala itong kaugnayan sa totoong buhay.\n"
            "D. Para lamang ito sa mga mahuhusay na mag-aaral.\n\n"
            "2. Alin sa mga sumusunod ang nagpapakita ng halimbawa ng {topic}?\n"
            "A. Paggamit ng {topic} sa isang tunay na sitwasyon.\n"
            "B. Pagkopya ng sagot nang hindi nauunawaan.\n"
            "C. Pag-iwas sa pagsasanay at pagbabalik-aral.\n"
            "D. Paggawa nang mag-isa palagi.\n\n"
            "3. Ano ang mabuting unang hakbang sa pag-aaral ng {topic}?\n"
            "A. Paggunita sa alam mo na.\n"
            "B. Diretso na sa panghuling awtput.\n"
            "C. Pagsasaulo nang walang pagsasanay.\n"
            "D. Pagsuko kapag mahirap ang gawain.\n\n"
            "4. Bakit mahalaga ang {topic} sa pang-araw-araw na buhay?\n"
            "A. Nakatutulong ito sa paglutas ng mga suliranin at paggawa ng wastong desisyon.\n"
            "B. Wala itong epekto sa pang-araw-araw na gawain.\n"
            "C. Kapaki-pakinabang lamang ito sa loob ng silid-aralan.\n"
            "D. Hindi ito nauugnay sa ibang mga asignatura.\n\n"
            "5. Alin sa mga sumusunod ang nagpapakita ng malalim na pag-unawa sa {topic}?\n"
            "A. Pagpapaliwanag nito sa sariling salita at paglalapat nito.\n"
            "B. Pag-uulit nang hindi nauunawaan.\n"
            "C. Pagkopya lamang sa kaklase.\n"
            "D. Paghula nang hindi sinusuri."
        )
    return (
        "Directions: Read each item carefully and choose the letter of the "
        "correct answer. Write your answers on a \u00bc sheet of paper.\n\n"
        f"1. Which of the following best describes {topic}?\n"
        f"A. It explains the key ideas and skills about {topic}.\n"
        "B. It only focuses on memorizing definitions.\n"
        "C. It has no connection to real life.\n"
        "D. It is meant only for advanced learners.\n\n"
        "2. Which statement shows an example of {topic}?\n"
        f"A. Using {topic} in a real situation.\n"
        "B. Copying an answer without understanding.\n"
        "C. Avoiding practice and review.\n"
        "D. Working alone all the time.\n\n"
        "3. What is a good first step in learning about {topic}?\n"
        "A. Recalling what you already know.\n"
        "B. Skipping directly to the final output.\n"
        "C. Memorizing without practice.\n"
        "D. Giving up when the task is hard.\n\n"
        "4. Why is {topic} important in everyday life?\n"
        "A. It helps solve real problems and make good choices.\n"
        "B. It has no effect on daily activities.\n"
        "C. It is useful only inside the classroom.\n"
        "D. It is not related to other subjects.\n\n"
        "5. Which of the following shows deep understanding of {topic}?\n"
        "A. Explaining it in your own words and applying it.\n"
        "B. Repeating it without understanding.\n"
        "C. Only copying from a classmate.\n"
        "D. Guessing without checking."
    )


def _le_perf_overview(group, band, topic, tl=False):
    if tl:
        return (
            f"Performance Task: \u201cIlapat at Lumikha\u201d \u2014 isang awtput tungkol sa {topic}\n\n"
            "Pangkalahatang-tanaw: Gagawa ka ng isang malikhaing awtput na naglalapat ng "
            f"{topic} sa isang tunay na sitwasyon. Sa gawaing ito, maipapakita mo ang iyong "
            "pag-unawa sa makabuluhan at orihinal na paraan."
        )
    return (
        f"Performance Task: \u201cApply and Create\u201d \u2014 an output on {topic}\n\n"
        "Overview: You will create a creative output that applies {topic} to a real-life "
        "situation. This task lets you demonstrate your understanding in a meaningful and "
        "original way."
    )


def _le_perf_directions(group, band, topic, tl=False):
    if tl:
        return (
            "Mga Panuto:\n"
            "1. Bumuo ng pangkat na may 3-5 kasapi.\n"
            "2. Pumili ng isang tunay na sitwasyon na nagpapakita ng {topic}.\n"
            "3. Planuhin ang awtput at maghati-hati sa mga gawain.\n"
            "4. Gawin ang awtput (hal. maikling presentasyon, poster, role play, o sulatin).\n"
            "5. Magsanay sa pagpapakita ng awtput.\n"
            "6. Ipakita ang awtput sa klase at ipaliwanag kung paano nito ipinapakita ang {topic}.\n\n"
            "Presentasyon: Ipakita nang malikhain ang awtput. Pagkatapos, ipaliwanag kung ano ang "
            f"kahulugan ng {topic} sa inyong awtput at ang kaugnayan nito sa totoong buhay."
        )
    return (
        "Directions:\n"
        "1. Form a group of 3-5 members.\n"
        "2. Choose a real-life situation that shows {topic}.\n"
        "3. Plan your output and assign tasks to each member.\n"
        "4. Create your output (e.g., short presentation, poster, role play, or written piece).\n"
        "5. Practice presenting your output.\n"
        "6. Present your output to the class and explain how it shows {topic}.\n\n"
        "Presentation: Present your output creatively. After presenting, explain what {topic} "
        "means in your output and how it connects to real life."
    )


def _le_perf_rubric(group, band, topic, tl=False):
    if tl:
        return (
            "Rubrik sa Pagmamarka:\n\n"
            "1. Pag-unawa sa Paksa \u2014 Mahusay (10-8): Nagpapakita ng malalim at wastong "
            f"pag-unawa sa {topic}. | Nasisiyahan (7-5): Nagpapakita ng batayang pag-unawa ngunit "
            "may ilang puwang. | Nangangailangan ng Pag-unlad (4-0): Kaunti o walang pag-unawa.\n\n"
            "2. Paglalapat sa Gawain \u2014 Mahusay: Natutugunan nang buo at makabuluhan ang lahat "
            "ng kinakailangan. | Nasisiyahan: Natutugunan ang karamihan sa mga kinakailangan. | "
            "Nangangailangan ng Pag-unlad: Hindi sumunod sa mga panuto.\n\n"
            "3. Pagkamalikhain at Pagpapahayag \u2014 Mahusay: Lubos na malikhain, orihinal, at "
            "nakaaantig ang awtput. | Nasisiyahan: May ilang pagkamalikhain at pagka-orihinal. | "
            "Nangangailangan ng Pag-unlad: Kaunti o walang pagkamalikhain.\n\n"
            "4. Kalinawan at Organisasyon \u2014 Mahusay: Malinaw, maayos, at madaling sundan ang "
            "mga ideya. | Nasisiyahan: Karamihan ay malinaw at maayos. | Nangangailangan ng "
            "Pag-unlad: Mahirap sundan at hindi maayos.\n\n"
            "5. Presentasyon \u2014 Mahusay: Pino at may kumpiyansang ipinakita ang awtput. | "
            "Nasisiyahan: Malinaw at sapat ang presentasyon. | Nangangailangan ng Pag-unlad: Hindi "
            "kumpleto o hindi maganda ang presentasyon."
        )
    return (
        "Scoring Rubric:\n\n"
        f"1. Understanding of the Topic \u2014 Excellent (10-8): Shows deep and accurate "
        f"understanding of {topic}. | Satisfactory (7-5): Shows basic understanding with some "
        "gaps. | Needs Improvement (4-0): Shows little to no understanding.\n\n"
        "2. Application to the Task \u2014 Excellent: Fully meets all task requirements in a "
        "meaningful way. | Satisfactory: Meets most requirements correctly. | Needs Improvement: "
        "Does not follow task instructions.\n\n"
        "3. Creativity & Expression \u2014 Excellent: Output is highly creative, original, and "
        "impactful. | Satisfactory: Shows some creativity and originality. | Needs Improvement: "
        "Shows little or no creativity.\n\n"
        "4. Clarity & Organization \u2014 Excellent: Ideas are clear, well-organized, and easy to "
        "follow. | Satisfactory: Mostly clear and organized. | Needs Improvement: Hard to follow "
        "and disorganized.\n\n"
        "5. Presentation \u2014 Excellent: Output is polished and presented with confidence. | "
        "Satisfactory: Output is clear and adequately presented. | Needs Improvement: Output is "
        "incomplete or poorly presented."
    )


def _make_formative(group, band, tb="standard"):
    if tb == "short":
        if band == "k":
            return "Thumbs-up/thumbs-down checks after each step; observe learners during guided practice and note who needs support."
        if band == "primary":
            return "Oral questioning with thumbs-up/down checks; one mini-whiteboard check; collect exit slips."
        if band == "intermediate":
            return "Mini-whiteboard responses during instruction; one traffic-light self-assessment; collect exit slips at the end."
        return "Quick-write responses during the lesson; colored cards (green/yellow/red) after each key concept; address misconceptions immediately."

    if tb == "long":
        if band == "k":
            return random.choice([
                "Ongoing observation with a class list checklist; thumbs-up/down throughout; anecdotal notes on 3-5 focus learners.",
                "Use a 'Learning Lap Map': learners move their name tag through 5 checkpoints as they master each step; note who is stuck for reteaching.",
            ])
        if band == "primary":
            return random.choice([
                "Oral questioning during 'We Do', thumbs-up/down checks, completed worksheets, and a 'Fist to Five' check after each key concept; exit slip at the end.",
                "Use 'Quiz-Quiz-Trade' cards on the topic; teacher observes and notes common errors.",
            ])
        if band == "intermediate":
            return random.choice([
                "Mini-whiteboard responses, group task outputs, exit slips, and a traffic-light self-assessment; adjust pacing based on results.",
                "Use 'Quiz-Quiz-Trade' cards on the topic; teacher observes and notes common errors for reteaching.",
            ])
        return random.choice([
            "Quick-write responses, group presentation quality, and exit slip analysis; colored cards (green/yellow/red) for real-time feedback; address misconceptions in real time.",
            "Entry-exit tickets: a review question at the start and a reflection question at the end; compare responses to measure growth and plan the next session.",
        ])

    # standard (default)
    if band == "k":
        return random.choice([
            "Ongoing observation with a class list checklist; thumbs-up/down throughout; anecdotal notes on 3-5 focus learners.",
            "Use a 'Learning Lap Map': learners move their name tag through 5 checkpoints as they master each step; note who is stuck for reteaching.",
        ])
    if band == "primary":
        return random.choice([
            "Oral questioning during 'We Do', thumbs-up/down checks, completed worksheets, and a 'Fist to Five' check after each key concept; exit slip as the day's main check.",
            "Use 'Fist to Five' checks after each key concept (1 = confused, 5 = expert); record the class average and adjust instruction.",
        ])
    if band == "intermediate":
        return random.choice([
            "Mini-whiteboard responses, group task outputs, exit slips, and a traffic-light self-assessment; adjust pacing based on results.",
            "Use 'Quiz-Quiz-Trade' cards on the topic; teacher observes and notes common errors for reteaching.",
        ])
    return random.choice([
        "Quick-write responses, group presentation quality, and exit slip analysis; colored cards (green/yellow/red) for real-time feedback; address misconceptions in real time.",
        "Entry-exit tickets: a review question at the start and a reflection question at the end; compare responses to measure growth and plan the next session.",
    ])


def _make_reflection():
    return ""


# ---------------------------------------------------------------------------
# Tagalog (Filipino) content generation for AP / Filipino / Makabansa /
# GMRC / Values Education / SHS Filipino & social-science subjects.
# ---------------------------------------------------------------------------

def _make_objectives_tl(desc, core, band):
    skill = (desc or "").strip().rstrip(".")
    if not skill:
        skill = f"Ang aralin tungkol sa {core or 'paksa'}"
    skill = skill[0].upper() + skill[1:]
    if band == "k":
        return random.choice([
            f"Sa pagtatapos ng aralin, inaasahang ang mga mag-aaral ay:\n"
            f"1. {skill} nang may gabay ng guro.\n"
            f"2. Nakikilahok sa mga gawaing pangklase tungkol sa {core}.\n"
            f"3. Naibabahagi ang isang natutuhan tungkol sa {core}.",
        ])
    if band in ("primary", "intermediate"):
        return random.choice([
            f"Sa pagtatapos ng aralin, inaasahang ang mga mag-aaral ay:\n"
            f"1. {skill} nang may pag-unawa.\n"
            f"2. Naisasagawa ang mga gawaing may kaugnayan sa {core} nang may patnubay.\n"
            f"3. Naiuugnay ang {core} sa kanilang pang-araw-araw na buhay.",
        ])
    return random.choice([
        f"Sa pagtatapos ng aralin, inaasahang ang mga mag-aaral ay:\n"
        f"1. {skill} nang may kawastuhan.\n"
        f"2. Naipamamalas ang {core} sa isang nakaayos na gawain o gawaing-bahay.\n"
        f"3. Napapahalagahan ang {core} at naipapaliwanag ang kahalagahan nito sa iba.",
    ])


def _make_lesson_name_tl(core):
    return _tl_title(core)


def _make_integration_tl(core, group):
    options = {
        "social_studies": [
            f"Pagkamamamayan at Lipunan: nakatutulong ang {core} upang maunawaan ng mga mag-aaral "
            f"ang kanilang papel sa pamilya, paaralan, at pamayanan.",
            f"Pagpapahalaga sa Kultura at Kasaysayan: naipapakita ng {core} ang pagpapahalaga sa "
            f"sariling kultura at kasaysayan.",
        ],
        "filipino": [
            f"Pagpapahalaga sa Wika at Kultura: naipapakita ng {core} ang pagpapahalaga sa wikang "
            f"Filipino at kulturang Pilipino.",
            f"Komunikasyon: nakatutulong ang {core} sa mas malinaw na pagpapahayag ng mga ideya sa klase.",
        ],
        "values": [
            f"Pagpapahalagang Moral: hinihikayat ng {core} ang pagpapakita ng respeto at responsibilidad.",
            f"Pagpapahalaga sa Pamayanan: nauugnay ang {core} sa kung paano tinatrato ng mga mag-aaral "
            f"ang iba at nakikilahok sa komunidad.",
        ],
    }
    lst = options.get(group, [
        f"Integrasyon: nauugnay ang {core} sa tunay na buhay at iba pang asignatura."
    ])
    return random.choice(lst)


def _make_learner_context_tl(core, band):
    if band in ("k", "primary"):
        return random.choice([
            f"Iba-iba ang dating kaalaman ng mga mag-aaral tungkol sa {core}; may ilang "
            f"nangangailangan ng tulong sa pagbabasa ng panuto. Gumamit ng magkapares na gawain, "
            f"pagbabasa nang malakas, at mga larawan upang makasali ang lahat.",
            f"Natututo ang mga mag-aaral sa pamamagitan ng mga kuwento at laro. May mga alam na "
            f"nang kaunti tungkol sa {core} samantalang baguhan pa ang iba, kaya magsimula sa mga "
            f"simpleng gawain at dahan-dahang buuin ang aralin.",
        ])
    return random.choice([
        f"May kakayahan at karanasan na ang mga mag-aaral sa {core} at mahalaga sa kanila ang "
        f"malayang pag-iisip. Magbigay ng mga pagpipilian, malinaw na pamantayan, at mga gawaing "
        f"nangangailangan ng tunay na pagsusuri.",
        f"Isang pangkat na may kakayahan, ngunit mabilis silang matapos, kaya dapat may lalim ang "
        f"mga gawain. Paghaluin ang mga pangkat upang kumalat ang mahuhusay na lider at maiangat "
        f"ang lahat.",
    ])


def _make_pre_lesson_tl(group, band, core):
    if band in ("k", "primary"):
        return random.choice([
            f"Magpakita ng isang larawan o bagay tungkol sa {core}; itanong kung ano ang kanilang "
            f"nakikita o alam na, pagkatapos ay magbahagi ang ilan.",
            f"Maglaro ng mabilis na 'oo o hindi' gamit ang mga simpleng pahayag tungkol sa {core}; "
            f"tumayo ang mga mag-aaral kung sumasang-ayon.",
        ])
    return random.choice([
        f"Magtanong tulad ng 'Ano ang alam ninyo tungkol sa {core}?'; isusulat ng mga mag-aaral "
        f"ang kanilang mga ideya, magbabahagi sa kapareha, at itatala sa pisara.",
        f"Magpakita ng isang larawan o maikling sitwasyon tungkol sa {core}; magsusulat ang mga "
        f"mag-aaral ng kanilang reaksyon, tatalakayin sa pangkat, at ibabahagi sa klase.",
    ])


def _make_learning_resources_tl(band, core):
    if band in ("k", "primary"):
        return random.choice([
            f"Gabay sa Kurikulum ng DepEd at BOW\nAklat at kagamitan ng mag-aaral\n"
            f"Mga larawan, flashcards, at biswal na pantulong\nWorksheet at mga kagamitan sa sining",
            f"Gabay sa Kurikulum ng DepEd at BOW\nMga kuwento at babasahin tungkol sa {core}\n"
            f"Whiteboard, chart paper, at markers\nKagamitan para sa laro (picture puzzles, matching cards)",
        ])
    return random.choice([
        f"Gabay sa Kurikulum ng DepEd at BOW (SY 2026-2027)\nModule at mga karagdagang babasahin\n"
        f"PowerPoint, bidyo, at mga online resources tungkol sa {core}\nGraphic organizers at rubrik",
        f"DepEd Learning Portal (https://lrmds.deped.gov.ph/)\nAklat at artikulo tungkol sa {core}\n"
        f"Case study at mga totoong sitwasyon\nTask cards o quiz cards para sa pagsasanay",
    ])


def _make_formative_tl(band):
    if band in ("k", "primary"):
        return ("Pagtatanong nang pasalita, thumbs-up/down check pagkatapos ng bawat hakbang, "
                "at exit slip sa katapusan; obserbahan kung sino ang nangangailangan ng "
                "karagdagang tulong.")
    return ("Mabilis na pagsulat ng sagot, pagtataya gamit ang colored cards (berde/dilaw/pula) "
            "pagkatapos ng bawat pangunahing konsepto, at pagsusuri ng exit slips; tugunan agad "
            "ang mga maling pagkaunawa.")


def _make_extended_learning_tl(core):
    return random.choice([
        f"Maaaring ipagpatuloy ng mga mag-aaral ang pagtuklas sa {core} sa pamamagitan ng isang "
        f"simpleng pagsasaliksik o pakikipanayam sa pamilya at ibahagi ang natuklasan sa susunod "
        f"na sesyon.",
        f"Maaaring magbasa o manood ang mga mag-aaral ng isang pang-edukasyong bidyo tungkol sa "
        f"{core} sa bahay at gumawa ng maikling awtput (guhit, journal, o mini-report).",
    ])


def _make_references_tl(subject):
    return (
        "DepEd Three-Term Budget of Work (BOW) SY 2026-2027\n"
        f"Gabay sa Kurikulum ng DepEd – {subject}\n"
        "Most Essential Learning Competencies (MELCs) na may CG Codes\n"
        "DepEd Learning Portal (https://lrmds.deped.gov.ph/)"
    )


def _make_ai_declaration_tl():
    return (
        "Ang lesson plan na ito ay binuo sa tulong ng LAMDAG (AI) upang magmungkahi ng mga ideya, "
        "ayusin ang nilalaman, at mapabuti ang kalinawan. Nagsisilbi lamang itong pantulong; "
        "ang guro ang may huling desisyon at pananagutan sa katumpakan at pagpapatupad ng aralin."
    )


def _anchor_standards_tl(data, content_standard, performance_standard):
    cs = (content_standard or "").strip().rstrip(".")
    ps = (performance_standard or "").strip().rstrip(".")
    if cs:
        data["learner_context"] = (
            data["learner_context"]
            + f"\n\nAng disenyo ng aralin ay nakabatay sa pamantayang pangnilalaman: {cs}."
        )
    if ps:
        data["flow_apply"] = (
            data["flow_apply"]
            + f"\n\nAng gawaing ito ay humahantong sa mga mag-aaral tungo sa pamantayan sa pagganap: {ps}."
        )
    return data
