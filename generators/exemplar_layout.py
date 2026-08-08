"""Shared text/layout constants for the official DepEd Strengthened Senior
High School Lesson Exemplar (LE) document (portrait, 8.5in x 13in long bond).

Structure follows the official Strengthened SHS LE template (sections I-VIII,
two-column PROCEDURES | ANNOTATIONS, per-step pedagogy annotations)."""

QUARTER_LABELS = {
    "1": "1st Quarter",
    "2": "2nd Quarter",
    "3": "3rd Quarter",
    "4": "4th Quarter",
}

# (label, data_key) for the lesson-details block under the title
INFO_ROWS = [
    ("Learning Area/s", "subject"),
    ("Grade Level & Section", "grade_section"),
    ("Quarter", "quarter"),
    ("Week", "week"),
    ("School Year", "school_year"),
    ("Designed by Teacher/s", "teacher"),
]

# Section headers (official Strengthened SHS LE structure — the official
# document numbers PROCEDURES as "IV" and ASSESSMENT/REFLECTION/GEN-AI as
# V/VI/VII, so we reproduce that exact numbering)
HEADER_OBJECTIVES = "I. OBJECTIVES"
HEADER_REFERENCES = "II. REFERENCES and MATERIALS"
HEADER_CONTENT = "III. CONTENT"
HEADER_OBJECTIVES2 = "IV. OBJECTIVES"
HEADER_PROCEDURES = "IV. PROCEDURES"
HEADER_ASSESSMENT = "V. ASSESSMENT"
HEADER_REFLECTION = "VI. REFLECTION"
HEADER_GENAI = "VII. USE OF GENERATIVE AI"

HEADER_PROC_COL = "PROCEDURES"
HEADER_ANN_COL = "ANNOTATIONS"

OBJECTIVES_INTRO = "At the end of the lesson, the learners should be able to:"
OBJECTIVES_INTRO_TL = "Sa pagtatapos ng aralin, inaasahang ang mga mag-aaral ay:"

# Procedures: phase label + list of (step_title, content_key, annotation_key).
# Step titles have NO leading number: the official template renumbers the steps
# within each phase (A: 1-2, B: 1-3, C: 1-2), and the phase label (A./B./C.)
# appears inside the ANNOTATIONS column rather than as a full-width banner.
# Each step's content comes from the wizard (le_step1..le_step7) and can be
# edited on the Preview page.
PROCEDURES = [
    ("A. Activating Prior Knowledge", [
        ("Activating Prior Knowledge", "le_step1", "le_ann_pre"),
    ]),
    ("B. Instituting New Knowledge", [
        ("Establishing the Purpose of the Lesson", "le_step2", "le_ann_purpose"),
        ("Presenting Examples", "le_step3", "le_ann_examples"),
        ("Discussing New Concept", "le_step4", "le_ann_concept"),
    ]),
    ("C. Demonstrating Knowledge and Skills", [
        ("Developing Mastery", "le_step5", "le_ann_mastery"),
        ("Finding Practical Application", "le_step6", "le_ann_apply"),
        ("Making Generalization", "le_step7", "le_ann_general"),
    ]),
]

REFLECTION_DIRECTIONS = (
    "Directions: Reflect on your lesson delivery and learners\u2019 performance through the following "
    "questions. These will help you evaluate the effectiveness of your strategies and identify areas "
    "for improvement:\n"
    "1. Which activities engaged students the most?\n"
    "2. How many learners achieved 80% on the assessment? How many learners need remediation?\n"
    "3. Which of my teaching strategies worked well?\n"
    "4. Which activities took longer than expected and how can I manage time more efficiently in "
    "future sessions?\n"
    "5. What difficulties did I encounter in the delivery of the lesson? How did I resolve these "
    "concerns?"
)

DEFAULT_AI_DECLARATION = (
    "In preparing this Learning Exemplar (LE), the author(s) used ChatGPT in order to assist in "
    "generating ideas, activity instructions, and annotations. The author(s) reviewed and finalized "
    "the writing of the content. The author(s) take(s) full responsibility for the content of this LE."
)

# Guidance/hints shown in the preview "Learning Exemplar Details" editor
GUIDE_LE_COMPETENCIES = (
    "Learning Competencies from the curriculum (one per line). Leave blank to use the competency "
    "selected in Step 2."
)
GUIDE_LE_CONTENT = (
    "A brief summary of the lesson content. Leave blank to use the lesson title/topic."
)
GUIDE_LE_QUIZ = (
    "Paper-and-pen assessment items (one per line). Include the directions and the items."
)
GUIDE_LE_PERF_OVERVIEW = (
    "Describe the performance task and the expected output (e.g., \u201cPerformance Task: Photo "
    "Essay\u201d)."
)
GUIDE_LE_PERF_DIRECTIONS = (
    "Step-by-step directions to the learners for completing the performance task."
)
GUIDE_LE_PERF_RUBRIC = (
    "Write the scoring rubric (criteria, proficiency levels, and scores)."
)
GUIDE_LE_STEP = (
    "Describe the activity for this procedure step: instructions, task, or guiding questions."
)
GUIDE_LE_ANN = (
    "Pedagogical note explaining the purpose/rationale of this step (visible in the ANNOTATIONS "
    "column)."
)
