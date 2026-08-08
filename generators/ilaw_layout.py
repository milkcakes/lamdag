"""Shared text/layout constants for the official DepEd ILAW lesson plan template
(portrait, 8.5in x 13in long bond)."""

# (label, guidance, data_key) for the info rows at the top of the table
INFO_ROWS = [
    ("Name of Lesson", "", "lesson_name"),
    ("Learning Area/s", "", "subject"),
    ("Designed by Teacher/s", "", "teacher"),
    ("Designed for which Grade Level & Section", "", "grade_section"),
    ("No. of Sessions", "", "sessions"),
    ("Date of Lesson Delivery", "", "date"),
    ("References", "(books, websites, toolkits, etc.)", "references"),
    ("Declaration of AI use",
     "Cite how AI was used in the formulation of the lesson plan.\nSee DO 3 s. 2026 Annex-A",
     "ai_declaration"),
]

HEADER_INTENTIONS = (
    "Intentions: Meaningful learning experiences are anchored on how we frame them. "
    "Start by deciding what you want your learners to master by the end of the lesson "
    "\u2013 keep it clear and simple.\n"
    "Remember: understanding your learners\u2019 evolving contexts and designing around it "
    "help ensure that your lessons connect with and are relevant to them."
)

HEADER_EXPERIENCE = (
    "Learning Experience. A learning experience is like a thoughtfully designed journey. "
    "Each activity and interaction build towards meaningful understanding and growth. "
    "Identify activities and interactions to help learner gain knowledge, skills, or "
    "understanding in a purposeful way."
)

HEADER_ASSESSMENT = (
    "Assessment. Assessment reveal what learners have gained and what they still need "
    "help with. These are helpful in providing you with information to guide your future "
    "instruction."
)

HEADER_WAYS_FORWARD = (
    "Ways forward. Meaningful learning can also happen beyond the classroom \u2013 for both "
    "learner and the teacher.\n"
    "Pause and reflect on what happened today."
)

GUIDE_COMPETENCY = (
    "Write the competency/ies from the curriculum that we are targeting, and the content "
    "or performance standards applicable to the sessions."
)
GUIDE_OBJECTIVES = (
    "Write the smaller knowledge, skills, or tasks from the competency that the learners "
    "will work on and be able to show by the end of the sessions."
)
GUIDE_LEARNER_CONTEXT = (
    "Write your observations of your learners, and how they have been performing or "
    "responding to learning experiences recently. Include strengths, interest, and "
    "possible barriers to learning."
)
GUIDE_PRE_LESSON = "Describe how you will help the learners get ready for the lesson."
GUIDE_FLOW = (
    "Describe the activities that you can implement in one or more sessions to meet the "
    "learning objectives.\n"
    "Apply the Learning Design Principles by thinking about how to:\n"
    "\u2022 make the objective clear for the learners\n"
    "\u2022 guide learners before letting them try the task on their own\n"
    "\u2022 check the state of learners\u2019 well-being, understanding, and mastery over the lesson\n"
    "\u2022 connect today\u2019s new concept to past competencies\n"
    "\u2022 encourage collaboration among learners\n"
    "\u2022 invite learners to reflect on why these matters to them\n"
    "\u2022 ensure inclusion for learner\u2019s varied abilities, learning styles, and contexts"
)
GUIDE_RESOURCES = (
    "List down the learning resources that will help you reach your objectives. Ensure "
    "that they are available and inclusive. Include options and alternatives in case of "
    "emergencies."
)
GUIDE_INTEGRATION = (
    "Write down any possibilities to meaningfully integrate another area, special topic "
    "or technology. Write N/A if none."
)
GUIDE_FORMATIVE = (
    "Create a task, activity or questions to evaluate learning and provide feedback. "
    "Include ways for learners to ask for guidance or support. Remember to provide "
    "appropriate accommodation so all learners can demonstrate their understanding "
    "(e.g. varied response formats, small group options, visual or auditory support)"
)
GUIDE_EXTENDED = (
    "Suggest other learning experiences outside the classroom/class hours that learners "
    "may want to access to reinforce what they have learned, to spark their curiosities "
    "further, or that may provide them support in their areas of difficulty."
)
GUIDE_REFLECTIONS = (
    "Think about what you need to change for the next session based on what happened "
    "today. Is there something learners are interested in exploring? Are there some "
    "things you would like to share with your co-teachers, parents, school leaders, "
    "about your classroom experience? What would you like your instructional coach to "
    "help you with?"
)

FLOW_PARTS = [
    ("I \u2014 INTRODUCE", "flow_introduce", "introduce"),
    ("L \u2014 LEARN", "flow_learn", "learn"),
    ("A \u2014 APPLY", "flow_apply", "apply"),
    ("W \u2014 WRAP-UP", "flow_wrapup", "wrap"),
]


def flow_heading(heading, time_key, data):
    """Section heading with its minute budget, e.g. 'L — LEARN (28 min)'."""
    times = data.get("flow_times") or {}
    mins = times.get(time_key)
    if mins:
        return f"{heading} ({mins} min)"
    return heading


def flow_text(data):
    """Combined flow content with ILAW sub-headings (plain-text version)."""
    parts = []
    for heading, key, time_key in FLOW_PARTS:
        parts.append(flow_heading(heading, time_key, data))
        parts.append(data.get(key, "") or "\u2014")
        parts.append("")
    return "\n".join(parts).strip()
