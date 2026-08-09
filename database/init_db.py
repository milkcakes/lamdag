import sqlite3
import os
import sys
import shutil


def _frozen():
    return bool(getattr(sys, "frozen", False))


def _resource_dir():
    """Read-only bundled resources (templates, static, shipped DB)."""
    if _frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    """Per-user writable data dir (works without admin on any machine)."""
    if _frozen():
        d = os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "LAMDAG"
        )
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d


DATA_DIR = _data_dir()
if _frozen():
    BUNDLED_DB = os.path.join(_resource_dir(), "database", "matatag_cg.db")
else:
    BUNDLED_DB = os.path.join(_resource_dir(), "matatag_cg.db")
DB_PATH = os.path.join(DATA_DIR, "matatag_cg.db")


def _ensure_db_file():
    """Copy the shipped DB to the writable data dir on first run."""
    if not os.path.exists(DB_PATH) and os.path.exists(BUNDLED_DB):
        shutil.copy2(BUNDLED_DB, DB_PATH)


_ensure_db_file()


def _refresh_curriculum():
    """If the shipped DB is a newer data version, refresh subjects/competencies
    in the writable DB without touching saved_plans (or other user data)."""
    if not os.path.exists(BUNDLED_DB) or not os.path.exists(DB_PATH):
        return
    try:
        bundled = sqlite3.connect("file:{}?mode=ro".format(BUNDLED_DB.replace("\\", "/")), uri=True)
        local = sqlite3.connect(DB_PATH)
        bv = bundled.execute("PRAGMA user_version").fetchone()[0]
        lv = local.execute("PRAGMA user_version").fetchone()[0]
        if bv <= lv:
            bundled.close()
            local.close()
            return
        bundled_path = BUNDLED_DB.replace("'", "''")
        local.execute(f"ATTACH DATABASE '{bundled_path}' AS bundled")
        cur = local.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("DELETE FROM competencies")
        cur.execute("DELETE FROM subjects")
        cur.execute(
            "INSERT INTO subjects (id, code, name, grade_level, sort_order, grouping) "
            "SELECT id, code, name, grade_level, sort_order, grouping FROM bundled.subjects"
        )
        cur.execute(
            "INSERT INTO competencies (id, subject_id, term, week, code, description, "
            "content_standard, performance_standard) "
            "SELECT id, subject_id, term, week, code, description, "
            "content_standard, performance_standard FROM bundled.competencies"
        )
        local.execute(f"PRAGMA user_version = {int(bv)}")
        local.commit()
        local.execute("DETACH DATABASE bundled")
        bundled.close()
        local.close()
        print(f"[init_db] curriculum refreshed to data version {bv}")
    except Exception as exc:
        print(f"[init_db] curriculum refresh failed: {exc}")
        try:
            local.rollback()
        except Exception:
            pass
        try:
            local.execute("DETACH DATABASE bundled")
        except Exception:
            pass
        try:
            bundled.close()
        except Exception:
            pass
        try:
            local.close()
        except Exception:
            pass

_initialized = False


def get_connection():
    global _initialized
    if not _initialized:
        _initialized = True
        try:
            init_database()
            conn = sqlite3.connect(DB_PATH)
            has_subjects = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] > 0
            conn.close()
            if not has_subjects:
                seed_data()
            _refresh_curriculum()
        except Exception:
            _initialized = False
            raise
    return sqlite3.connect(DB_PATH)


def _migrate():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(saved_plans)")
    existing = {row[1] for row in cursor.fetchall()}
    new_cols = {        "references": "TEXT",
        "ai_declaration": "TEXT",
        "designation": "TEXT",
        "school_head": "TEXT",
        "learner_context": "TEXT",
        "pre_lesson": "TEXT",
        "flow_engage": "TEXT",
        "flow_explore": "TEXT",
        "flow_experience": "TEXT",
        "flow_empathize": "TEXT",
        "learning_resources": "TEXT",
        "extended_learning": "TEXT",
        # Official ILAW template fields (2026 revision)
        "lesson_name": "TEXT",
        "section": "TEXT",
        "sessions": "TEXT",
        "school_head_designation": "TEXT",
        "flow_introduce": "TEXT",
        "flow_learn": "TEXT",
        "flow_apply": "TEXT",
        "flow_wrapup": "TEXT",
        # DepEd letterhead fields
        "region": "TEXT",
        "division": "TEXT",
        "school_week": "TEXT",
        # Official Strengthened SHS Lesson Exemplar optional fields
        "le_competencies": "TEXT",
        "le_content": "TEXT",
        "le_quiz": "TEXT",
        "le_perf_overview": "TEXT",
        "le_perf_directions": "TEXT",
        "le_perf_rubric": "TEXT",
        "le_step1": "TEXT",
        "le_step2": "TEXT",
        "le_step3": "TEXT",
        "le_step4": "TEXT",
        "le_step5": "TEXT",
        "le_step6": "TEXT",
        "le_step7": "TEXT",
        "le_ann_pre": "TEXT",
        "le_ann_purpose": "TEXT",
        "le_ann_examples": "TEXT",
        "le_ann_concept": "TEXT",
        "le_ann_mastery": "TEXT",
        "le_ann_apply": "TEXT",
        "le_ann_general": "TEXT",
    }
    for col, ctype in new_cols.items():
        if col not in existing:
            cursor.execute(f'ALTER TABLE saved_plans ADD COLUMN "{col}" {ctype}')
    cursor.execute("PRAGMA table_info(subjects)")
    subj_cols = {row[1] for row in cursor.fetchall()}
    if "grouping" not in subj_cols:
        cursor.execute('ALTER TABLE subjects ADD COLUMN "grouping" TEXT DEFAULT ""')
    cursor.execute("PRAGMA table_info(feedbacks)")
    fb_cols = {row[1] for row in cursor.fetchall()}
    for col, ctype in (("email", "TEXT DEFAULT ''"), ("area", "TEXT DEFAULT ''")):
        if col not in fb_cols:
            cursor.execute(f'ALTER TABLE feedbacks ADD COLUMN "{col}" {ctype}')
    cursor.execute("PRAGMA table_info(school_access)")
    sa_cols = {row[1] for row in cursor.fetchall()}
    if "kind" not in sa_cols:
        cursor.execute('ALTER TABLE school_access ADD COLUMN "kind" TEXT DEFAULT "school"')
    cursor.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    for col, ctype in (
        ("google_id", "TEXT DEFAULT ''"),
        ("facebook_id", "TEXT DEFAULT ''"),
    ):
        if col not in user_cols:
            cursor.execute(f'ALTER TABLE users ADD COLUMN "{col}" {ctype}')
    conn.commit()
    conn.close()


def init_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            grade_level TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            grouping TEXT DEFAULT '',
            UNIQUE(code, grade_level)
        );
        CREATE TABLE IF NOT EXISTS competencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            term INTEGER NOT NULL,
            week INTEGER,
            code TEXT NOT NULL,
            description TEXT NOT NULL,
            content_standard TEXT,
            performance_standard TEXT,
            UNIQUE(subject_id, term, week, code),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        );
        CREATE TABLE IF NOT EXISTS saved_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            school TEXT, teacher TEXT, grade_level TEXT, subject TEXT,
            term TEXT, week TEXT, date TEXT, time_allotment TEXT,
            competency_code TEXT, competency_description TEXT,
            content_standard TEXT, performance_standard TEXT,
            objectives TEXT, integration TEXT,
            activating_knowledge TEXT, lesson_purpose TEXT,
            developing_understanding TEXT, deepening_understanding TEXT,
            generalizations TEXT,
            formative_assessment TEXT, summative_assessment TEXT,
            remediation TEXT, enrichment TEXT, reflection TEXT
        );
        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            rating INTEGER DEFAULT 0,
            area TEXT DEFAULT '',
            liked TEXT DEFAULT '',
            problem TEXT DEFAULT '',
            suggestions TEXT DEFAULT '',
            synced INTEGER DEFAULT 0,
            sync_note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS school_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            access_code TEXT NOT NULL UNIQUE,
            plan TEXT DEFAULT 'school_license',
            kind TEXT DEFAULT 'school',
            created_at TEXT NOT NULL,
            expires_at TEXT,
            active INTEGER DEFAULT 1,
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            school TEXT DEFAULT '',
            status TEXT DEFAULT 'trial',
            plan TEXT DEFAULT '',
            trial_start TEXT DEFAULT '',
            trial_end TEXT DEFAULT '',
            paid_until TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            last_login TEXT DEFAULT '',
            google_id TEXT DEFAULT '',
            facebook_id TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()
    _migrate()


def seed_data():
    conn = get_connection()
    cursor = conn.cursor()

    cs_map = {
        "CS_LANG": "The learner demonstrates understanding of language for effective communication.",
        "PS_LANG": "The learner communicates effectively in various situations.",
        "CS_LANG_EXP": "The learner demonstrates understanding of language for developing and expressing ideas.",
        "PS_LANG_EXP": "The learner expresses ideas using symbols and simple words.",
        "CS_ALPH": "The learner demonstrates understanding of alphabet knowledge for literacy.",
        "PS_ALPH": "The learner uses alphabet knowledge to identify letters and sounds.",
        "CS_VOC": "The learner demonstrates understanding of vocabulary development.",
        "PS_VOC": "The learner uses appropriate vocabulary in speaking and writing.",
        "CS_GRAM": "The learner demonstrates understanding of grammatical structures.",
        "PS_GRAM": "The learner uses correct grammar in speaking and writing.",
        "CS_WRIT": "The learner demonstrates understanding of writing as a process.",
        "PS_WRIT": "The learner writes legibly and creates simple texts.",
        "CS_COMP": "The learner demonstrates understanding of comprehension strategies.",
        "PS_COMP": "The learner comprehends and responds to texts.",
        "CS_READ": "The learner demonstrates understanding of reading strategies.",
        "PS_READ": "The learner reads with accuracy and comprehension.",
        "CS_FLU": "The learner demonstrates understanding of fluency.",
        "PS_FLU": "The learner reads with speed, accuracy, and proper expression.",
        "CS_NUM": "The learner demonstrates understanding of whole numbers and operations.",
        "PS_NUM": "The learner applies number sense in real-life situations.",
        "CS_PROB": "The learner demonstrates understanding of problem-solving strategies.",
        "PS_PROB": "The learner solves routine and non-routine problems.",
        "CS_GEOM": "The learner demonstrates understanding of geometric concepts.",
        "PS_GEOM": "The learner identifies and constructs geometric figures.",
        "CS_MEAS": "The learner demonstrates understanding of measurement concepts.",
        "PS_MEAS": "The learner applies measurement skills in daily life.",
        "CS_PATT": "The learner demonstrates understanding of patterns.",
        "PS_PATT": "The learner creates and extends patterns.",
        "CS_DATA": "The learner demonstrates understanding of data representation.",
        "PS_DATA": "The learner organizes and interprets data.",
        "CS_OP": "The learner demonstrates understanding of the four fundamental operations.",
        "PS_OP": "The learner performs operations accurately.",
        "CS_FRAC": "The learner demonstrates understanding of fractions.",
        "PS_FRAC": "The learner represents and compares fractions.",
        "CS_DEC": "The learner demonstrates understanding of decimals.",
        "PS_DEC": "The learner uses decimals in real-life situations.",
        "CS_TIME": "The learner demonstrates understanding of time concepts.",
        "PS_TIME": "The learner tells time and solves time-related problems.",
        "CS_VAL": "The learner demonstrates understanding of positive values.",
        "PS_VAL": "The learner practices positive values in daily life.",
        "CS_FAM": "The learner demonstrates understanding of family relationships.",
        "PS_FAM": "The learner strengthens family bonds through respect and cooperation.",
        "CS_COMM": "The learner demonstrates understanding of community responsibility.",
        "PS_COMM": "The learner actively participates in community activities.",
        "CS_SOC": "The learner demonstrates understanding of social responsibility.",
        "PS_SOC": "The learner shows respect and concern for others.",
        "CS_ENV": "The learner demonstrates understanding of environmental stewardship.",
        "PS_ENV": "The learner practices care for the environment.",
        "CS_ID": "The learner demonstrates understanding of personal and national identity.",
        "PS_ID": "The learner expresses pride in being Filipino.",
        "CS_RES": "The learner demonstrates understanding of natural resources.",
        "PS_RES": "The learner practices sustainable use of resources.",
        "CS_CULT": "The learner demonstrates understanding of Filipino culture.",
        "PS_CULT": "The learner appreciates and preserves Filipino culture.",
        "CS_PROP": "The learner demonstrates understanding of material properties.",
        "PS_PROP": "The learner classifies objects based on properties.",
        "CS_MAT": "The learner demonstrates understanding of matter.",
        "PS_MAT": "The learner describes the properties and changes of matter.",
        "CS_LIFE": "The learner demonstrates understanding of living things.",
        "PS_LIFE": "The learner identifies and describes living things and their needs.",
        "CS_HUMAN": "The learner demonstrates understanding of the human body.",
        "PS_HUMAN": "The learner identifies body parts and their functions.",
        "CS_ENERGY": "The learner demonstrates understanding of energy.",
        "PS_ENERGY": "The learner identifies sources and uses of energy.",
        "CS_MOTION": "The learner demonstrates understanding of motion.",
        "PS_MOTION": "The learner describes and compares movements of objects.",
        "CS_WEATHER": "The learner demonstrates understanding of weather.",
        "PS_WEATHER": "The learner identifies weather conditions and appropriate responses.",
        "CS_FIL": "The learner demonstrates understanding of Filipino for effective communication.",
        "PS_FIL": "The learner communicates effectively in Filipino.",
        "CS_FILR": "The learner demonstrates understanding of reading in Filipino.",
        "PS_FILR": "The learner reads and comprehends Filipino texts.",
        "CS_FILG": "The learner demonstrates understanding of Filipino grammar.",
        "PS_FILG": "The learner uses correct Filipino grammar.",
        "CS_FILW": "The learner demonstrates understanding of writing in Filipino.",
        "PS_FILW": "The learner writes effectively in Filipino.",
        "CS_AP": "The learner demonstrates understanding of community and society.",
        "PS_AP": "The learner analyzes and participates in community life.",
        "CS_APG": "The learner demonstrates understanding of Philippine geography.",
        "PS_APG": "The learner analyzes geographical characteristics of the Philippines.",
        "CS_APH": "The learner demonstrates understanding of Philippine history.",
        "PS_APH": "The learner analyzes historical events and their significance.",
        "CS_MUS": "The learner demonstrates understanding of musical elements.",
        "PS_MUS": "The learner performs and appreciates music.",
        "CS_ART": "The learner demonstrates understanding of visual art elements.",
        "PS_ART": "The learner creates and appreciates artwork.",
        "CS_PE": "The learner demonstrates understanding of movement and physical fitness.",
        "PS_PE": "The learner performs physical activities with proper form.",
        "CS_HEALTH": "The learner demonstrates understanding of health concepts.",
        "PS_HEALTH": "The learner practices healthy habits.",
        "CS_ICT": "The learner demonstrates understanding of ICT concepts.",
        "PS_ICT": "The learner uses ICT tools responsibly.",
        "CS_AGRI": "The learner demonstrates understanding of agricultural concepts.",
        "PS_AGRI": "The learner applies agricultural practices.",
        "CS_ENTREP": "The learner demonstrates understanding of entrepreneurship.",
        "PS_ENTREP": "The learner demonstrates entrepreneurial skills.",
        "CS_COOK": "The learner demonstrates understanding of culinary principles.",
        "PS_COOK": "The learner prepares dishes following safety standards.",
        "CS_SEW": "The learner demonstrates understanding of sewing principles.",
        "PS_SEW": "The learner performs basic sewing techniques.",
        "CS_NEED": "The learner demonstrates understanding of basic needs.",
        "PS_NEED": "The learner identifies and meets basic needs.",
        "CS_CULTURE": "The learner demonstrates understanding of Filipino culture and traditions.",
        "PS_CULTURE": "The learner participates in cultural practices.",
        "CS_RATIO": "The learner demonstrates understanding of ratios and proportions.",
        "PS_RATIO": "The learner applies ratios and proportions in real-life situations.",
        "CS_ALG": "The learner demonstrates understanding of algebraic concepts.",
        "PS_ALG": "The learner solves algebraic problems accurately.",
        "CS_TRIG": "The learner demonstrates understanding of trigonometric concepts.",
        "PS_TRIG": "The learner applies trigonometric ratios in problem solving.",
        "CS_INV": "The learner demonstrates understanding of scientific investigation.",
        "PS_INV": "The learner conducts scientific investigations using the scientific method.",
        "CS_SPACE": "The learner demonstrates understanding of celestial bodies and space.",
        "PS_SPACE": "The learner describes the characteristics of celestial bodies.",
        "CS_EARTH": "The learner demonstrates understanding of Earth systems and processes.",
        "PS_EARTH": "The learner explains Earth processes and their effects on the environment.",
    }

    def cs(key):
        return cs_map.get(key, "")

    CS_LANG = cs("CS_LANG")
    PS_LANG = cs("PS_LANG")
    CS_LANG_EXP = cs("CS_LANG_EXP")
    PS_LANG_EXP = cs("PS_LANG_EXP")
    CS_ALPH = cs("CS_ALPH")
    PS_ALPH = cs("PS_ALPH")
    CS_VOC = cs("CS_VOC")
    PS_VOC = cs("PS_VOC")
    CS_GRAM = cs("CS_GRAM")
    PS_GRAM = cs("PS_GRAM")
    CS_WRIT = cs("CS_WRIT")
    PS_WRIT = cs("PS_WRIT")
    CS_COMP = cs("CS_COMP")
    PS_COMP = cs("PS_COMP")
    CS_READ = cs("CS_READ")
    PS_READ = cs("PS_READ")
    CS_FLU = cs("CS_FLU")
    PS_FLU = cs("PS_FLU")
    CS_NUM = cs("CS_NUM")
    PS_NUM = cs("PS_NUM")
    CS_PROB = cs("CS_PROB")
    PS_PROB = cs("PS_PROB")
    CS_GEOM = cs("CS_GEOM")
    PS_GEOM = cs("PS_GEOM")
    CS_MEAS = cs("CS_MEAS")
    PS_MEAS = cs("PS_MEAS")
    CS_PATT = cs("CS_PATT")
    PS_PATT = cs("PS_PATT")
    CS_DATA = cs("CS_DATA")
    PS_DATA = cs("PS_DATA")
    CS_OP = cs("CS_OP")
    PS_OP = cs("PS_OP")
    CS_FRAC = cs("CS_FRAC")
    PS_FRAC = cs("PS_FRAC")
    CS_DEC = cs("CS_DEC")
    PS_DEC = cs("PS_DEC")
    CS_TIME = cs("CS_TIME")
    PS_TIME = cs("PS_TIME")
    CS_VAL = cs("CS_VAL")
    PS_VAL = cs("PS_VAL")
    CS_FAM = cs("CS_FAM")
    PS_FAM = cs("PS_FAM")
    CS_COMM = cs("CS_COMM")
    PS_COMM = cs("PS_COMM")
    CS_SOC = cs("CS_SOC")
    PS_SOC = cs("PS_SOC")
    CS_ENV = cs("CS_ENV")
    PS_ENV = cs("PS_ENV")
    CS_ID = cs("CS_ID")
    PS_ID = cs("PS_ID")
    CS_RES = cs("CS_RES")
    PS_RES = cs("PS_RES")
    CS_CULT = cs("CS_CULT")
    PS_CULT = cs("PS_CULT")
    CS_PROP = cs("CS_PROP")
    PS_PROP = cs("PS_PROP")
    CS_MAT = cs("CS_MAT")
    PS_MAT = cs("PS_MAT")
    CS_LIFE = cs("CS_LIFE")
    PS_LIFE = cs("PS_LIFE")
    CS_HUMAN = cs("CS_HUMAN")
    PS_HUMAN = cs("PS_HUMAN")
    CS_ENERGY = cs("CS_ENERGY")
    PS_ENERGY = cs("PS_ENERGY")
    CS_MOTION = cs("CS_MOTION")
    PS_MOTION = cs("PS_MOTION")
    CS_WEATHER = cs("CS_WEATHER")
    PS_WEATHER = cs("PS_WEATHER")
    CS_FIL = cs("CS_FIL")
    PS_FIL = cs("PS_FIL")
    CS_FILR = cs("CS_FILR")
    PS_FILR = cs("PS_FILR")
    CS_FILG = cs("CS_FILG")
    PS_FILG = cs("PS_FILG")
    CS_FILW = cs("CS_FILW")
    PS_FILW = cs("PS_FILW")
    CS_AP = cs("CS_AP")
    PS_AP = cs("PS_AP")
    CS_APG = cs("CS_APG")
    PS_APG = cs("PS_APG")
    CS_APH = cs("CS_APH")
    PS_APH = cs("PS_APH")
    CS_MUS = cs("CS_MUS")
    PS_MUS = cs("PS_MUS")
    CS_ART = cs("CS_ART")
    PS_ART = cs("PS_ART")
    CS_PE = cs("CS_PE")
    PS_PE = cs("PS_PE")
    CS_HEALTH = cs("CS_HEALTH")
    PS_HEALTH = cs("PS_HEALTH")
    CS_ICT = cs("CS_ICT")
    PS_ICT = cs("PS_ICT")
    CS_AGRI = cs("CS_AGRI")
    PS_AGRI = cs("PS_AGRI")
    CS_ENTREP = cs("CS_ENTREP")
    PS_ENTREP = cs("PS_ENTREP")
    CS_COOK = cs("CS_COOK")
    PS_COOK = cs("PS_COOK")
    CS_SEW = cs("CS_SEW")
    PS_SEW = cs("PS_SEW")
    CS_NEED = cs("CS_NEED")
    PS_NEED = cs("PS_NEED")
    CS_CULTURE = cs("CS_CULTURE")
    PS_CULTURE = cs("PS_CULTURE")
    CS_RATIO = cs("CS_RATIO")
    PS_RATIO = cs("PS_RATIO")
    CS_ALG = cs("CS_ALG")
    PS_ALG = cs("PS_ALG")
    CS_TRIG = cs("CS_TRIG")
    PS_TRIG = cs("PS_TRIG")
    CS_INV = cs("CS_INV")
    PS_INV = cs("PS_INV")
    CS_SPACE = cs("CS_SPACE")
    PS_SPACE = cs("PS_SPACE")
    CS_EARTH = cs("CS_EARTH")
    PS_EARTH = cs("PS_EARTH")

    def _grade_sort(g):
        order = {"Kindergarten": 0}
        for i in range(1, 13):
            order[f"Grade {i}"] = i
        return order.get(g, 99)

    subjects = [
        ("KINDER", "Kindergarten", "Kindergarten"),
        ("LANG-G1", "Language", "Grade 1"),
        ("RL-G1", "Reading and Literacy", "Grade 1"),
        ("MATH-G1", "Mathematics", "Grade 1"),
        ("GMRC-G1", "GMRC", "Grade 1"),
        ("MAKABANSA-G1", "Makabansa", "Grade 1"),
        ("FIL-G2", "Filipino", "Grade 2"),
        ("ENG-G2", "English", "Grade 2"),
        ("MATH-G2", "Mathematics", "Grade 2"),
        ("GMRC-G2", "GMRC", "Grade 2"),
        ("MAKABANSA-G2", "Makabansa", "Grade 2"),
        ("FIL-G3", "Filipino", "Grade 3"),
        ("ENG-G3", "English", "Grade 3"),
        ("MATH-G3", "Mathematics", "Grade 3"),
        ("SCI-G3", "Science", "Grade 3"),
        ("GMRC-G3", "GMRC", "Grade 3"),
        ("MAKABANSA-G3", "Makabansa", "Grade 3"),
        ("FIL-G4", "Filipino", "Grade 4"),
        ("ENG-G4", "English", "Grade 4"),
        ("MATH-G4", "Mathematics", "Grade 4"),
        ("SCI-G4", "Science", "Grade 4"),
        ("AP-G4", "Araling Panlipunan", "Grade 4"),
        ("MAPEH-G4", "MAPEH", "Grade 4"),
        ("GMRC-G4", "GMRC", "Grade 4"),
        ("EPP-G4", "EPP/TLE", "Grade 4"),
        ("FIL-G5", "Filipino", "Grade 5"),
        ("ENG-G5", "English", "Grade 5"),
        ("MATH-G5", "Mathematics", "Grade 5"),
        ("SCI-G5", "Science", "Grade 5"),
        ("AP-G5", "Araling Panlipunan", "Grade 5"),
        ("MAPEH-G5", "MAPEH", "Grade 5"),
        ("GMRC-G5", "GMRC", "Grade 5"),
        ("EPP-G5", "EPP/TLE", "Grade 5"),
        ("FIL-G6", "Filipino", "Grade 6"),
        ("ENG-G6", "English", "Grade 6"),
        ("MATH-G6", "Mathematics", "Grade 6"),
        ("SCI-G6", "Science", "Grade 6"),
        ("AP-G6", "Araling Panlipunan", "Grade 6"),
        ("MAPEH-G6", "MAPEH", "Grade 6"),
        ("GMRC-G6", "GMRC", "Grade 6"),
        ("EPP-G6", "EPP/TLE", "Grade 6"),
        ("FIL-G7", "Filipino", "Grade 7"),
        ("ENG-G7", "English", "Grade 7"),
        ("MATH-G7", "Mathematics", "Grade 7"),
        ("SCI-G7", "Science", "Grade 7"),
        ("AP-G7", "Araling Panlipunan", "Grade 7"),
        ("MAPEH-G7", "MAPEH", "Grade 7"),
        ("VE-G7", "Values Education", "Grade 7"),
        ("TLE-G7", "TLE", "Grade 7"),
        ("FIL-G8", "Filipino", "Grade 8"),
        ("ENG-G8", "English", "Grade 8"),
        ("MATH-G8", "Mathematics", "Grade 8"),
        ("SCI-G8", "Science", "Grade 8"),
        ("AP-G8", "Araling Panlipunan", "Grade 8"),
        ("MAPEH-G8", "MAPEH", "Grade 8"),
        ("VE-G8", "Values Education", "Grade 8"),
        ("TLE-G8", "TLE", "Grade 8"),
        ("FIL-G9", "Filipino", "Grade 9"),
        ("ENG-G9", "English", "Grade 9"),
        ("MATH-G9", "Mathematics", "Grade 9"),
        ("SCI-G9", "Science", "Grade 9"),
        ("AP-G9", "Araling Panlipunan", "Grade 9"),
        ("MAPEH-G9", "MAPEH", "Grade 9"),
        ("VE-G9", "Values Education", "Grade 9"),
        ("TLE-G9", "TLE", "Grade 9"),
        ("FIL-G10", "Filipino", "Grade 10"),
        ("ENG-G10", "English", "Grade 10"),
        ("MATH-G10", "Mathematics", "Grade 10"),
        ("SCI-G10", "Science", "Grade 10"),
        ("AP-G10", "Araling Panlipunan", "Grade 10"),
        ("MAPEH-G10", "MAPEH", "Grade 10"),
        ("VE-G10", "Values Education", "Grade 10"),
        ("TLE-G10", "TLE", "Grade 10"),
        # SHS Core Subjects - Grade 11
        ("ORALCOM-G11", "Oral Communication", "Grade 11"),
        ("READWRIT-G11", "Reading and Writing Skills", "Grade 11"),
        ("KOMFIL-G11", "Komunikasyon at Pananaliksik sa Wika at Kulturang Pilipino", "Grade 11"),
        ("PANITIKAN-G11", "21st Century Literature from the Philippines and the World", "Grade 11"),
        ("GENMATH-G11", "General Mathematics", "Grade 11"),
        ("STATS-G11", "Statistics and Probability", "Grade 11"),
        ("EARTHSCI-G11", "Earth Science", "Grade 11"),
        ("PERSDEV-G11", "Personal Development", "Grade 11"),
        ("PEHEALTH-G11", "Physical Education and Health", "Grade 11"),
        ("UCSP-G11", "Understanding Culture, Society and Politics", "Grade 11"),
        # SHS Core Subjects - Grade 12
        ("ORALCOM-G12", "Oral Communication", "Grade 12"),
        ("READWRIT-G12", "Reading and Writing Skills", "Grade 12"),
        ("KOMFIL-G12", "Komunikasyon at Pananaliksik sa Wika at Kulturang Pilipino", "Grade 12"),
        ("PANITIKAN-G12", "21st Century Literature from the Philippines and the World", "Grade 12"),
        ("GENMATH-G12", "General Mathematics", "Grade 12"),
        ("STATS-G12", "Statistics and Probability", "Grade 12"),
        ("EARTHSCI-G12", "Earth Science", "Grade 12"),
        ("PERSDEV-G12", "Personal Development", "Grade 12"),
        ("PEHEALTH-G12", "Physical Education and Health", "Grade 12"),
        ("UCSP-G12", "Understanding Culture, Society and Politics", "Grade 12"),
    ]

    for code, name, grade in subjects:
        cursor.execute(
            "INSERT OR IGNORE INTO subjects (code, name, grade_level, sort_order) VALUES (?, ?, ?, ?)",
            (code, name, grade, _grade_sort(grade)),
        )

    conn.commit()
    cursor.execute("SELECT id, code FROM subjects")
    subject_map = {row[1]: row[0] for row in cursor.fetchall()}

    comps = {
        "KINDER": [
            (1, 1, "K-SE-1", "Identify oneself and members of the family", "The learner demonstrates understanding of oneself, family, and community.", "The learner expresses oneself and relates with family and community."),
            (1, 2, "K-SE-2", "Express feelings and emotions appropriately", None, None),
            (1, 3, "K-SE-3", "Participate in group activities and routines", None, None),
            (1, 4, "K-LL-1", "Identify letters of the alphabet", "The learner demonstrates understanding of language and literacy.", "The learner uses language and literacy skills in daily activities."),
            (1, 5, "K-LL-2", "Recite rhymes and sing songs", None, None),
            (1, 6, "K-LL-3", "Follow simple one-step directions", None, None),
            (2, 1, "K-NU-1", "Count objects from 1 to 10", "The learner demonstrates understanding of early mathematical concepts.", "The learner applies mathematical concepts in daily activities."),
            (2, 2, "K-NU-2", "Identify basic shapes and colors", None, None),
            (2, 3, "K-NU-3", "Compare quantities (more/less, big/small)", None, None),
            (2, 4, "K-PD-1", "Perform simple body movements", "The learner demonstrates understanding of physical development.", "The learner performs movements and shows healthy habits."),
            (2, 5, "K-PD-2", "Practice proper handwashing and hygiene", None, None),
            (3, 1, "K-CR-1", "Draw and color familiar objects", "The learner demonstrates understanding of creative expression.", "The learner expresses ideas through arts and creative activities."),
            (3, 2, "K-CR-2", "Create simple patterns", None, None),
            (3, 3, "K-VA-1", "Show respect for elders and others", "The learner demonstrates understanding of values and social skills.", "The learner practices positive values in daily interactions."),
            (3, 4, "K-VA-2", "Care for the environment", None, None),
        ],
        "LANG-G1": [
            (1, 1, "L1LC-1", "Talk about oneself and family", CS_LANG, PS_LANG),
            (1, 1, "L1LC-2", "Participate in classroom interactions using verbal and non-verbal responses", None, None),
            (1, 2, "L1LC-3", "Use common and socially acceptable expressions (greetings, leave-taking)", None, None),
            (1, 3, "L1LD-1", "Express ideas using symbols (drawings, emojis)", CS_LANG_EXP, PS_LANG_EXP),
            (1, 4, "L1LD-2", "Name people, objects, and places in the environment", None, None),
            (1, 5, "L1LD-3", "Describe objects using adjectives", None, None),
            (1, 6, "L1AL-1", "Identify letters of the alphabet", CS_ALPH, PS_ALPH),
            (1, 7, "L1AL-2", "Match upper and lower case letters", None, None),
            (2, 1, "L1AL-3", "Associate letters with their sounds", CS_ALPH, PS_ALPH),
            (2, 2, "L1AL-4", "Blend sounds to form syllables", None, None),
            (2, 3, "L1VC-1", "Use vocabulary related to family and school", CS_VOC, PS_VOC),
            (2, 4, "L1VC-2", "Use vocabulary related to community and environment", None, None),
            (2, 5, "L1VC-3", "Identify synonyms and antonyms of simple words", None, None),
            (2, 6, "L1GA-1", "Use correct grammar (subject-verb agreement)", CS_GRAM, PS_GRAM),
            (2, 7, "L1GA-2", "Use correct grammar (simple tenses)", None, None),
            (3, 1, "L1GA-3", "Construct simple sentences", CS_GRAM, PS_GRAM),
            (3, 2, "L1WC-1", "Write letters and words legibly", CS_WRIT, PS_WRIT),
            (3, 3, "L1WC-2", "Write simple sentences about experiences", None, None),
            (3, 4, "L1WC-3", "Write short stories based on experiences", None, None),
            (3, 5, "L1CO-1", "Comprehend short stories and narratives", CS_COMP, PS_COMP),
            (3, 6, "L1CO-2", "Make predictions about stories", None, None),
        ],
        "RL-G1": [
            (1, 1, "RL1-1", "Identify letters and their sounds", "The learner demonstrates understanding of phonological awareness.", "The learner applies phonological awareness in reading."),
            (1, 2, "RL1-2", "Blend phonemes to form words", None, None),
            (1, 3, "RL1-3", "Segment words into syllables", None, None),
            (1, 4, "RL1-4", "Read high-frequency words", "The learner demonstrates understanding of word recognition.", "The learner reads words with accuracy and fluency."),
            (1, 5, "RL1-5", "Read CVC words", None, None),
            (2, 1, "RL1-6", "Read simple sentences", CS_READ, PS_READ),
            (2, 2, "RL1-7", "Read short paragraphs with comprehension", None, None),
            (2, 3, "RL1-8", "Identify main idea of a story", CS_COMP, PS_COMP),
            (2, 4, "RL1-9", "Identify characters and setting in a story", None, None),
            (2, 5, "RL1-10", "Sequence events in a story", None, None),
            (3, 1, "RL1-11", "Make inferences from texts", CS_COMP, PS_COMP),
            (3, 2, "RL1-12", "Distinguish reality from fantasy", None, None),
            (3, 3, "RL1-13", "Read with appropriate speed and expression", CS_FLU, PS_FLU),
            (3, 4, "RL1-14", "Answer wh-questions about texts", None, None),
        ],
        "MATH-G1": [
            (1, 1, "M1-1", "Count objects up to 100", "The learner demonstrates understanding of whole numbers and operations.", "The learner applies number sense in real-life situations."),
            (1, 2, "M1-2", "Read and write numbers up to 100", None, None),
            (1, 3, "M1-3", "Compare numbers using more than, less than, equal", None, None),
            (1, 4, "M1-4", "Add numbers with sums up to 20", None, None),
            (1, 5, "M1-5", "Subtract numbers with minuends up to 20", None, None),
            (1, 6, "M1-6", "Solve word problems involving addition and subtraction", CS_PROB, PS_PROB),
            (2, 1, "M1-7", "Identify and name basic shapes", CS_GEOM, PS_GEOM),
            (2, 2, "M1-8", "Compare objects by length, weight, capacity", None, None),
            (2, 3, "M1-9", "Tell time by the hour and half-hour", CS_MEAS, PS_MEAS),
            (2, 4, "M1-10", "Identify days of the week and months of the year", None, None),
            (2, 5, "M1-11", "Identify coins and bills up to PHP 100", None, None),
            (3, 1, "M1-12", "Identify and extend patterns", CS_PATT, PS_PATT),
            (3, 2, "M1-13", "Sort and classify objects by attributes", None, None),
            (3, 3, "M1-14", "Collect and organize data", CS_DATA, PS_DATA),
            (3, 4, "M1-15", "Read and interpret pictographs", None, None),
        ],
        "GMRC-G1": [
            (1, 1, "G1-1", "Show love and respect for oneself", "The learner demonstrates understanding of self-worth and positive values.", "The learner practices positive values in daily life."),
            (1, 2, "G1-2", "Express gratitude and appreciation", None, None),
            (1, 3, "G1-3", "Demonstrate honesty in words and actions", None, None),
            (2, 1, "G1-4", "Show respect for parents and elders", CS_FAM, PS_FAM),
            (2, 2, "G1-5", "Help with simple household chores", None, None),
            (2, 3, "G1-6", "Share with siblings and classmates", None, None),
            (2, 4, "G1-7", "Practice good manners (please, thank you, sorry)", None, None),
            (3, 1, "G1-8", "Care for the school environment", CS_COMM, PS_COMM),
            (3, 2, "G1-9", "Participate in school activities", None, None),
            (3, 3, "G1-10", "Show respect for the Philippine flag and national symbols", None, None),
            (3, 4, "G1-11", "Practice proper waste disposal", None, None),
        ],
        "MAKABANSA-G1": [
            (1, 1, "MB1-1", "Identify oneself as a Filipino", "The learner demonstrates understanding of Filipino identity and culture.", "The learner expresses pride in being Filipino."),
            (1, 2, "MB1-2", "Identify members of the family and their roles", None, None),
            (1, 3, "MB1-3", "Identify places in school and community", None, None),
            (2, 1, "MB1-4", "Identify basic needs (food, clothing, shelter)", CS_NEED, PS_NEED),
            (2, 2, "MB1-5", "Identify sources of water, food, and light", None, None),
            (2, 3, "MB1-6", "Practice healthy habits", None, None),
            (2, 4, "MB1-7", "Identify Philippine national symbols", None, None),
            (3, 1, "MB1-8", "Recognize Filipino cultural practices and traditions", CS_CULTURE, PS_CULTURE),
            (3, 2, "MB1-9", "Participate in community events", None, None),
            (3, 3, "MB1-10", "Identify occupations in the community", None, None),
        ],
    }

    grades_2_3 = {
        "GMRC": [
            (1, 1, "G-1", "Show respect for oneself and others", CS_VAL, PS_VAL),
            (1, 2, "G-2", "Practice honesty and integrity", None, None),
            (1, 3, "G-3", "Demonstrate responsibility at home", None, None),
            (2, 1, "G-4", "Show respect for diversity and inclusion", CS_SOC, PS_SOC),
            (2, 2, "G-5", "Practice helpfulness and cooperation", None, None),
            (2, 3, "G-6", "Demonstrate kindness and compassion", None, None),
            (3, 1, "G-7", "Care for the environment and natural resources", CS_ENV, PS_ENV),
            (3, 2, "G-8", "Practice proper waste management", None, None),
            (3, 3, "G-9", "Demonstrate love for country and community", None, None),
        ],
        "MAKABANSA": [
            (1, 1, "MB-1", "Identify oneself as part of family and community", CS_ID, PS_ID),
            (1, 2, "MB-2", "Identify roles and responsibilities at home", None, None),
            (1, 3, "MB-3", "Identify basic rights of children", None, None),
            (2, 1, "MB-4", "Identify natural resources in the community", CS_RES, PS_RES),
            (2, 2, "MB-5", "Identify ways to care for the environment", None, None),
            (2, 3, "MB-6", "Identify weather conditions and appropriate activities", None, None),
            (3, 1, "MB-7", "Identify Philippine festivals and traditions", CS_CULT, PS_CULT),
            (3, 2, "MB-8", "Identify Filipino heroes and their contributions", None, None),
            (3, 3, "MB-9", "Demonstrate pride in Filipino identity", None, None),
        ],
    }

    math_gen = {
        2: [
            (1, 1, "M-1", "Visualize and represent numbers up to 1,000", CS_NUM, PS_NUM),
            (1, 2, "M-2", "Add numbers with regrouping", None, None),
            (1, 3, "M-3", "Subtract numbers with regrouping", None, None),
            (1, 4, "M-4", "Solve word problems involving addition and subtraction", CS_PROB, PS_PROB),
            (2, 1, "M-5", "Multiply numbers by 2, 5, and 10", CS_OP, PS_OP),
            (2, 2, "M-6", "Divide numbers using repeated subtraction", None, None),
            (2, 3, "M-7", "Identify fractions as equal parts of a whole", CS_FRAC, PS_FRAC),
            (2, 4, "M-8", "Measure length, mass, and capacity", CS_MEAS, PS_MEAS),
            (3, 1, "M-9", "Tell time using analog and digital clocks", CS_TIME, PS_TIME),
            (3, 2, "M-10", "Identify and describe shapes and symmetry", CS_GEOM, PS_GEOM),
            (3, 3, "M-11", "Interpret pictographs and bar graphs", CS_DATA, PS_DATA),
            (3, 4, "M-12", "Create patterns using shapes and numbers", CS_PATT, PS_PATT),
        ],
        3: [
            (1, 1, "M-1", "Visualize numbers up to 10,000", CS_NUM, PS_NUM),
            (1, 2, "M-2", "Add and subtract numbers up to 1,000", None, None),
            (1, 3, "M-3", "Multiply 2-digit by 1-digit numbers", CS_OP, PS_OP),
            (1, 4, "M-4", "Divide numbers with remainders", None, None),
            (2, 1, "M-5", "Identify and compare proper fractions", CS_FRAC, PS_FRAC),
            (2, 2, "M-6", "Add and subtract fractions with similar denominators", None, None),
            (2, 3, "M-7", "Identify decimals using money", CS_DEC, PS_DEC),
            (2, 4, "M-8", "Measure perimeter of shapes", CS_MEAS, PS_MEAS),
            (3, 1, "M-9", "Find area of squares and rectangles", CS_MEAS, PS_MEAS),
            (3, 2, "M-10", "Identify parallel and perpendicular lines", CS_GEOM, PS_GEOM),
            (3, 3, "M-11", "Represent data using bar graphs", CS_DATA, PS_DATA),
            (3, 4, "M-12", "Solve routine and non-routine word problems", CS_PROB, PS_PROB),
        ],
    }

    eng_gen = {
        2: [
            (1, 1, "E-1", "Use polite expressions in conversations", CS_LANG, PS_LANG),
            (1, 2, "E-2", "Identify parts of a sentence (subject, predicate)", CS_GRAM, PS_GRAM),
            (1, 3, "E-3", "Use nouns and verbs correctly", None, None),
            (2, 1, "E-4", "Read grade-level texts with comprehension", CS_READ, PS_READ),
            (2, 2, "E-5", "Identify main idea, characters, and setting", CS_COMP, PS_COMP),
            (2, 3, "E-6", "Use adjectives and adverbs", CS_GRAM, PS_GRAM),
            (3, 1, "E-7", "Write simple paragraphs", CS_WRIT, PS_WRIT),
            (3, 2, "E-8", "Write short narratives", None, None),
            (3, 3, "E-9", "Use correct punctuation and capitalization", None, None),
        ],
        3: [
            (1, 1, "E-1", "Listen and respond to stories and instructions", CS_LANG, PS_LANG),
            (1, 2, "E-2", "Use different types of sentences (declarative, interrogative)", CS_GRAM, PS_GRAM),
            (1, 3, "E-3", "Identify and use pronouns", None, None),
            (2, 1, "E-4", "Read aloud with accuracy and fluency", CS_READ, PS_READ),
            (2, 2, "E-5", "Identify story elements (plot, conflict, resolution)", CS_COMP, PS_COMP),
            (2, 3, "E-6", "Use prepositions and conjunctions", CS_GRAM, PS_GRAM),
            (3, 1, "E-7", "Write narrative and descriptive paragraphs", CS_WRIT, PS_WRIT),
            (3, 2, "E-8", "Organize ideas using graphic organizers", None, None),
            (3, 3, "E-9", "Edit and revise written work", None, None),
        ],
    }

    sci_gen = {
        3: [
            (1, 1, "S-1", "Classify objects by properties (color, shape, texture)", CS_PROP, PS_PROP),
            (1, 2, "S-2", "Identify states of matter (solid, liquid, gas)", CS_MAT, PS_MAT),
            (1, 3, "S-3", "Describe changes in materials", None, None),
            (2, 1, "S-4", "Identify parts of plants and animals", CS_LIFE, PS_LIFE),
            (2, 2, "S-5", "Describe basic needs of living things", None, None),
            (2, 3, "S-6", "Identify the sense organs and their functions", CS_HUMAN, PS_HUMAN),
            (3, 1, "S-7", "Identify sources and uses of light, heat, and sound", CS_ENERGY, PS_ENERGY),
            (3, 2, "S-8", "Describe the movement of objects", CS_MOTION, PS_MOTION),
            (3, 3, "S-9", "Identify weather conditions and seasons", CS_WEATHER, PS_WEATHER),
        ],
    }

    fil_gen = {g: [
        (1, 1, "F-1", "Makilahok sa usapan at talakayan", CS_FIL, PS_FIL),
        (1, 2, "F-2", "Gamitin ang magagalang na pananalita", None, None),
        (1, 3, "F-3", "Tukuyin ang mga bahagi ng pangungusap", None, None),
        (2, 1, "F-4", "Basahin ang mga talata nang may pag-unawa", CS_FILR, PS_FILR),
        (2, 2, "F-5", "Tukuyin ang pangunahing kaisipan ng talata", None, None),
        (2, 3, "F-6", "Gamitin ang mga bahagi ng pananalita", CS_FILG, PS_FILG),
        (3, 1, "F-7", "Sumulat ng talata tungkol sa sariling karanasan", CS_FILW, PS_FILW),
        (3, 2, "F-8", "Sumulat ng liham pangkaibigan", None, None),
        (3, 3, "F-9", "Gumamit ng wastong baybay at bantas", None, None),
    ] for g in [2, 3]}

    ap_gen = {g: [
        (1, 1, "AP-1", "Natatalakay ang konsepto ng komunidad", CS_AP, PS_AP),
        (1, 2, "AP-2", "Natutukoy ang mga institusyon sa komunidad", None, None),
        (1, 3, "AP-3", "Nailalarawan ang mga tungkulin sa komunidad", None, None),
        (2, 1, "AP-4", "Natatalakay ang mga likas na yaman ng bansa", CS_APG, PS_APG),
        (2, 2, "AP-5", "Natutukoy ang mga lalawigan at rehiyon", None, None),
        (2, 3, "AP-6", "Naiuugnay ang kultura sa pagkakakilanlang Pilipino", None, None),
        (3, 1, "AP-7", "Natatalakay ang kasaysayan ng Pilipinas", CS_APH, PS_APH),
        (3, 2, "AP-8", "Natutukoy ang mga bayani at kontribusyon nila", None, None),
        (3, 3, "AP-9", "Napahahalagahan ang soberanya ng bansa", None, None),
    ] for g in [4, 5, 6]}

    mapeh_gen = {g: [
        (1, 1, "MP-1", "Identify elements of music (rhythm, melody, dynamics)", CS_MUS, PS_MUS),
        (1, 2, "MP-2", "Perform rhythmic patterns using body movements", None, None),
        (2, 1, "MP-3", "Identify elements of art (line, shape, color)", CS_ART, PS_ART),
        (2, 2, "MP-4", "Create artwork using different media", None, None),
        (2, 3, "MP-5", "Demonstrate proper body mechanics", CS_PE, PS_PE),
        (3, 1, "MP-6", "Identify health habits and nutrition", CS_HEALTH, PS_HEALTH),
        (3, 2, "MP-7", "Practice personal and environmental hygiene", None, None),
        (3, 3, "MP-8", "Demonstrate understanding of safety measures", None, None),
    ] for g in [4, 5, 6, 7, 8, 9, 10]}

    epp_tle_gen = {g: [
        (1, 1, "EPP-1", "Identify basic ICT tools and their uses", CS_ICT, PS_ICT),
        (1, 2, "EPP-2", "Practice proper use of computer and internet safety", None, None),
        (2, 1, "EPP-3", "Identify agricultural practices and tools", CS_AGRI, PS_AGRI),
        (2, 2, "EPP-4", "Perform basic gardening and plant care", None, None),
        (3, 1, "EPP-5", "Identify entrepreneurial skills and opportunities", CS_ENTREP, PS_ENTREP),
        (3, 2, "EPP-6", "Create simple products for sale", None, None),
    ] for g in [4, 5, 6]}

    tle_gen = {g: [
        (1, 1, "TLE-1", "Identify ICT tools and software applications", CS_ICT, PS_ICT),
        (1, 2, "TLE-2", "Create documents using word processing software", None, None),
        (2, 1, "TLE-3", "Identify kitchen tools and equipment", CS_COOK, PS_COOK),
        (2, 2, "TLE-4", "Prepare simple dishes following safety procedures", None, None),
        (2, 3, "TLE-5", "Identify sewing tools and basic stitches", CS_SEW, PS_SEW),
        (3, 1, "TLE-6", "Develop business ideas and marketing strategies", CS_ENTREP, PS_ENTREP),
        (3, 2, "TLE-7", "Compute product costs and pricing", None, None),
        (3, 3, "TLE-8", "Create an action plan for a small business", None, None),
    ] for g in [7, 8, 9, 10]}

    math_g = {
        4: [(1, 1, "M-1", "Visualize numbers up to 100,000", CS_NUM, PS_NUM),
            (1, 2, "M-2", "Add and subtract numbers with regrouping", None, None),
            (1, 3, "M-3", "Multiply and divide multi-digit numbers", CS_OP, PS_OP),
            (2, 1, "M-4", "Identify types of fractions and compare them", CS_FRAC, PS_FRAC),
            (2, 2, "M-5", "Add and subtract dissimilar fractions", None, None),
            (2, 3, "M-6", "Identify decimals and relate to fractions", CS_DEC, PS_DEC),
            (3, 1, "M-7", "Find perimeter and area of plane figures", CS_MEAS, PS_MEAS),
            (3, 2, "M-8", "Read and interpret data in tables and graphs", CS_DATA, PS_DATA),
            (3, 3, "M-9", "Solve multi-step word problems", CS_PROB, PS_PROB)],
        5: [(1, 1, "M-1", "Visualize numbers up to 1,000,000", CS_NUM, PS_NUM),
            (1, 2, "M-2", "Perform operations on whole numbers", CS_OP, PS_OP),
            (1, 3, "M-3", "Identify prime and composite numbers", None, None),
            (2, 1, "M-4", "Add and subtract decimals", CS_DEC, PS_DEC),
            (2, 2, "M-5", "Multiply and divide decimals", None, None),
            (2, 3, "M-6", "Add and subtract similar and dissimilar fractions", CS_FRAC, PS_FRAC),
            (3, 1, "M-7", "Find volume of cubes and rectangular prisms", CS_MEAS, PS_MEAS),
            (3, 2, "M-8", "Organize data in tables and line graphs", CS_DATA, PS_DATA),
            (3, 3, "M-9", "Solve word problems involving business math", CS_PROB, PS_PROB)],
        6: [(1, 1, "M-1", "Represent numbers in expanded form and scientific notation", CS_NUM, PS_NUM),
            (1, 2, "M-2", "Perform operations on integers", CS_OP, PS_OP),
            (1, 3, "M-3", "Find GCF and LCM of numbers", None, None),
            (2, 1, "M-4", "Identify ratios and proportions", CS_RATIO, PS_RATIO),
            (2, 2, "M-5", "Find percentage, rate, and base", None, None),
            (2, 3, "M-6", "Represent integers and perform operations", None, None),
            (3, 1, "M-7", "Calculate area of composite figures", CS_GEOM, PS_GEOM),
            (3, 2, "M-8", "Calculate mean, median, and mode", CS_DATA, PS_DATA),
            (3, 3, "M-9", "Solve word problems involving real-life situations", CS_PROB, PS_PROB)],
    }

    eng_g = {
        4: [(1, 1, "E-1", "Use correct grammar in oral communication", CS_LANG, PS_LANG),
            (1, 2, "E-2", "Identify different text types", CS_READ, PS_READ),
            (2, 1, "E-3", "Read and comprehend informational texts", CS_COMP, PS_COMP),
            (2, 2, "E-4", "Summarize information from texts", None, None),
            (2, 3, "E-5", "Use graphic organizers to organize information", None, None),
            (3, 1, "E-6", "Write expository and narrative texts", CS_WRIT, PS_WRIT),
            (3, 2, "E-7", "Use correct punctuation and capitalization", None, None),
            (3, 3, "E-8", "Prepare an outline for a composition", None, None)],
        5: [(1, 1, "E-1", "Identify point of view in texts", CS_COMP, PS_COMP),
            (1, 2, "E-2", "Use correct subject-verb agreement", CS_GRAM, PS_GRAM),
            (2, 1, "E-3", "Distinguish fact from opinion", CS_COMP, PS_COMP),
            (2, 2, "E-4", "Analyze story elements", None, None),
            (2, 3, "E-5", "Use modals and adverbs", CS_GRAM, PS_GRAM),
            (3, 1, "E-6", "Write persuasive and argumentative texts", CS_WRIT, PS_WRIT),
            (3, 2, "E-7", "Use transitional devices", None, None),
            (3, 3, "E-8", "Edit and revise compositions", None, None)],
        6: [(1, 1, "E-1", "Analyze sound devices in poetry", CS_COMP, PS_COMP),
            (1, 2, "E-2", "Identify figurative language", None, None),
            (2, 1, "E-3", "Compare and contrast content from multiple sources", CS_COMP, PS_COMP),
            (2, 2, "E-4", "Organize information using various methods", None, None),
            (2, 3, "E-5", "Use appropriate tenses consistently", CS_GRAM, PS_GRAM),
            (3, 1, "E-6", "Write a feature article", CS_WRIT, PS_WRIT),
            (3, 2, "E-7", "Conduct and report on research", None, None),
            (3, 3, "E-8", "Deliver oral presentations effectively", CS_LANG, PS_LANG)],
    }

    sci_g = {
        4: [(1, 1, "S-1", "Classify materials based on their properties", CS_MAT, PS_MAT),
            (1, 2, "S-2", "Describe changes in materials when exposed to different conditions", None, None),
            (2, 1, "S-3", "Identify the major organs of the human body", CS_HUMAN, PS_HUMAN),
            (2, 2, "S-4", "Describe the processes of digestion and respiration", None, None),
            (2, 3, "S-5", "Identify the life cycles of animals and plants", CS_LIFE, PS_LIFE),
            (3, 1, "S-6", "Identify sources and types of force and motion", CS_MOTION, PS_MOTION),
            (3, 2, "S-7", "Describe how light, heat, and sound travel", CS_ENERGY, PS_ENERGY),
            (3, 3, "S-8", "Describe weather patterns and the water cycle", CS_WEATHER, PS_WEATHER)],
        5: [(1, 1, "S-1", "Describe the properties of materials", CS_MAT, PS_MAT),
            (1, 2, "S-2", "Identify physical and chemical changes in materials", None, None),
            (2, 1, "S-3", "Describe the reproductive system in humans", CS_HUMAN, PS_HUMAN),
            (2, 2, "S-4", "Describe the interaction of living things in ecosystems", CS_LIFE, PS_LIFE),
            (2, 3, "S-5", "Identify parts and functions of plants", None, None),
            (3, 1, "S-6", "Describe electricity and magnetism", CS_ENERGY, PS_ENERGY),
            (3, 2, "S-7", "Observe the changes in the sky and weather", CS_WEATHER, PS_WEATHER),
            (3, 3, "S-8", "Describe the motion of objects in relation to reference points", CS_MOTION, PS_MOTION)],
        6: [(1, 1, "S-1", "Classify mixtures as homogeneous or heterogeneous", CS_MAT, PS_MAT),
            (1, 2, "S-2", "Describe techniques in separating mixtures", None, None),
            (2, 1, "S-3", "Describe the skeletal, muscular, and nervous systems", CS_HUMAN, PS_HUMAN),
            (2, 2, "S-4", "Describe the characteristics of different ecosystems", CS_LIFE, PS_LIFE),
            (2, 3, "S-5", "Identify the relationships in a food web", None, None),
            (3, 1, "S-6", "Describe the characteristics of planets in the solar system", CS_SPACE, PS_SPACE),
            (3, 2, "S-7", "Describe the effects of forces on objects", CS_MOTION, PS_MOTION),
            (3, 3, "S-8", "Identify renewable and non-renewable energy sources", CS_ENERGY, PS_ENERGY)],
    }

    fil_jhs = {g: [
        (1, 1, "F-1", "Makilala ang mga akdang pampanitikan ng Pilipinas", CS_FIL, PS_FIL),
        (1, 2, "F-2", "Suriin ang mga elemento ng maikling kwento", None, None),
        (2, 1, "F-3", "Matukoy ang mga uri ng tula at elemento nito", CS_FILR, PS_FILR),
        (2, 2, "F-4", "Magsuri ng mga akdang pampanitikan", None, None),
        (2, 3, "F-5", "Makilahok sa mga talakayan tungkol sa panitikan", None, None),
        (3, 1, "F-6", "Sumulat ng sariling akda (sanaysay, tula, kwento)", CS_FILW, PS_FILW),
        (3, 2, "F-7", "Gumamit ng mga teknikal na salita sa pagsulat", None, None),
        (3, 3, "F-8", "Magsagawa ng pananaliksik tungkol sa wika at panitikan", None, None),
    ] for g in [7, 8, 9, 10]}

    eng_jhs = {
        7: [(1, 1, "E-1", "Identify genres of Philippine literature", CS_COMP, PS_COMP),
            (1, 2, "E-2", "Use correct grammar in varied contexts", CS_GRAM, PS_GRAM),
            (1, 3, "E-3", "Use reading strategies for comprehension", CS_READ, PS_READ),
            (2, 1, "E-4", "Analyze elements of prose and poetry", CS_COMP, PS_COMP),
            (2, 2, "E-5", "Use figurative language in writing", None, None),
            (2, 3, "E-6", "Organize ideas using appropriate rhetorical devices", None, None),
            (3, 1, "E-7", "Write informative, persuasive, and narrative texts", CS_WRIT, PS_WRIT),
            (3, 2, "E-8", "Conduct and present research on a topic", None, None),
            (3, 3, "E-9", "Deliver a speech with effective presentation skills", CS_LANG, PS_LANG)],
        8: [(1, 1, "E-1", "Analyze Southeast Asian literary texts", CS_COMP, PS_COMP),
            (1, 2, "E-2", "Use appropriate grammatical signals", CS_GRAM, PS_GRAM),
            (2, 1, "E-3", "Analyze propaganda techniques", CS_COMP, PS_COMP),
            (2, 2, "E-4", "Compare and contrast ideas using graphic organizers", None, None),
            (2, 3, "E-5", "Use parallel structures in writing", CS_GRAM, PS_GRAM),
            (3, 1, "E-6", "Write a research report", CS_WRIT, PS_WRIT),
            (3, 2, "E-7", "Deliver a persuasive speech", None, None),
            (3, 3, "E-8", "Compose effective argumentative texts", None, None)],
        9: [(1, 1, "E-1", "Analyze Anglo-American and world literature", CS_COMP, PS_COMP),
            (1, 2, "E-2", "Use appropriate modals and conditionals", CS_GRAM, PS_GRAM),
            (2, 1, "E-3", "Analyze various literary devices", CS_COMP, PS_COMP),
            (2, 2, "E-4", "Differentiate between bias and prejudice", None, None),
            (2, 3, "E-5", "Employ effective verbal and non-verbal communication", CS_LANG, PS_LANG),
            (3, 1, "E-6", "Write a literary analysis paper", CS_WRIT, PS_WRIT),
            (3, 2, "E-7", "Compile a portfolio of written works", None, None),
            (3, 3, "E-8", "Deliver a panel discussion presentation", None, None)],
        10: [(1, 1, "E-1", "Analyze world literature as expression of cultural heritage", CS_COMP, PS_COMP),
             (1, 2, "E-2", "Apply grammar rules in complex communication tasks", CS_GRAM, PS_GRAM),
             (2, 1, "E-3", "Critique literary selections", CS_COMP, PS_COMP),
             (2, 2, "E-4", "Distinguish technical and operational definitions", None, None),
             (2, 3, "E-5", "Expand ideas using principles of cohesion", None, None),
             (3, 1, "E-6", "Write a research paper with proper citation", CS_WRIT, PS_WRIT),
             (3, 2, "E-7", "Deliver a research presentation", None, None),
             (3, 3, "E-8", "Compose a reflection on learning experiences", None, None)],
    }

    math_jhs = {
        7: [(1, 1, "M-1", "Identify sets and subsets", CS_NUM, PS_NUM),
            (1, 2, "M-2", "Perform operations on integers", CS_OP, PS_OP),
            (1, 3, "M-3", "Perform operations on rational numbers", None, None),
            (2, 1, "M-4", "Evaluate algebraic expressions", CS_ALG, PS_ALG),
            (2, 2, "M-5", "Solve linear equations and inequalities", None, None),
            (2, 3, "M-6", "Graph linear equations in two variables", CS_GEOM, PS_GEOM),
            (3, 1, "M-7", "Describe angles and angle pairs", CS_GEOM, PS_GEOM),
            (3, 2, "M-8", "Construct and interpret frequency distribution tables", CS_DATA, PS_DATA),
            (3, 3, "M-9", "Calculate measures of central tendency", None, None)],
        8: [(1, 1, "M-1", "Factor polynomials", CS_ALG, PS_ALG),
            (1, 2, "M-2", "Perform operations on rational algebraic expressions", None, None),
            (1, 3, "M-3", "Solve linear inequalities", None, None),
            (2, 1, "M-4", "Graph systems of linear equations", CS_GEOM, PS_GEOM),
            (2, 2, "M-5", "Solve systems of linear equations", None, None),
            (2, 3, "M-6", "Prove theorems on triangle congruence", CS_GEOM, PS_GEOM),
            (3, 1, "M-7", "Describe probability of events", CS_DATA, PS_DATA),
            (3, 2, "M-8", "Calculate measures of variability", None, None),
            (3, 3, "M-9", "Solve problems involving probability", CS_PROB, PS_PROB)],
        9: [(1, 1, "M-1", "Solve quadratic equations", CS_ALG, PS_ALG),
            (1, 2, "M-2", "Graph quadratic functions", None, None),
            (1, 3, "M-3", "Solve problems involving quadratic functions", CS_PROB, PS_PROB),
            (2, 1, "M-4", "Solve variation problems", CS_ALG, PS_ALG),
            (2, 2, "M-5", "Apply laws of exponents and radicals", None, None),
            (2, 3, "M-6", "Prove theorems on similarity", CS_GEOM, PS_GEOM),
            (3, 1, "M-7", "Illustrate trigonometric ratios", CS_TRIG, PS_TRIG),
            (3, 2, "M-8", "Solve oblique triangles using laws of sine and cosine", None, None),
            (3, 3, "M-9", "Solve problems involving triangles", CS_PROB, PS_PROB)],
        10: [(1, 1, "M-1", "Generate patterns and sequences", CS_ALG, PS_ALG),
             (1, 2, "M-2", "Solve problems involving sequences", None, None),
             (1, 3, "M-3", "Perform polynomial division", None, None),
             (2, 1, "M-4", "Solve problems involving circles", CS_GEOM, PS_GEOM),
             (2, 2, "M-5", "Prove theorems on chords, arcs, and angles", None, None),
             (2, 3, "M-6", "Derive the distance formula", None, None),
             (3, 1, "M-7", "Calculate probability of compound events", CS_DATA, PS_DATA),
             (3, 2, "M-8", "Apply measures of position in analysis", None, None),
             (3, 3, "M-9", "Solve problems involving permutations and combinations", None, None)],
    }

    sci_jhs = {
        7: [(1, 1, "S-1", "Describe scientific method and its application", CS_INV, PS_INV),
            (1, 2, "S-2", "Classify matter based on properties", CS_MAT, PS_MAT),
            (2, 1, "S-3", "Differentiate plant and animal cells", CS_LIFE, PS_LIFE),
            (2, 2, "S-4", "Describe levels of biological organization", None, None),
            (2, 3, "S-5", "Describe sexual and asexual reproduction", None, None),
            (3, 1, "S-6", "Describe motion in terms of distance, displacement, and speed", CS_MOTION, PS_MOTION),
            (3, 2, "S-7", "Identify energy transfer in ecosystems", CS_ENERGY, PS_ENERGY),
            (3, 3, "S-8", "Describe the Philippine environment and its resources", CS_ENV, PS_ENV)],
        8: [(1, 1, "S-1", "Describe Newton's laws of motion", CS_MOTION, PS_MOTION),
            (1, 2, "S-2", "Describe work, power, and energy relationships", CS_ENERGY, PS_ENERGY),
            (2, 1, "S-3", "Describe the structure of the atom", CS_MAT, PS_MAT),
            (2, 2, "S-4", "Identify the periodic table and elements", None, None),
            (2, 3, "S-5", "Describe chemical bonding", None, None),
            (3, 1, "S-6", "Describe the digestive, circulatory, and respiratory systems", CS_HUMAN, PS_HUMAN),
            (3, 2, "S-7", "Describe the digestive and excretory systems", None, None),
            (3, 3, "S-8", "Describe the concept of biodiversity", CS_LIFE, PS_LIFE)],
        9: [(1, 1, "S-1", "Describe the respiratory and circulatory systems", CS_HUMAN, PS_HUMAN),
            (1, 2, "S-2", "Explain how lifestyle affects body systems", None, None),
            (2, 1, "S-3", "Describe the quantum mechanical model of the atom", CS_MAT, PS_MAT),
            (2, 2, "S-4", "Identify types of chemical reactions", None, None),
            (2, 3, "S-5", "Describe the mole concept and stoichiometry", None, None),
            (3, 1, "S-6", "Describe the laws of thermodynamics", CS_ENERGY, PS_ENERGY),
            (3, 2, "S-7", "Describe the relationship between electricity and magnetism", None, None),
            (3, 3, "S-8", "Describe celestial motion and astronomical phenomena", CS_SPACE, PS_SPACE)],
        10: [(1, 1, "S-1", "Describe plate tectonics and its evidence", CS_EARTH, PS_EARTH),
             (1, 2, "S-2", "Describe the processes that shape the Earth's surface", None, None),
             (2, 1, "S-3", "Identify chemical and physical properties of gases", CS_MAT, PS_MAT),
             (2, 2, "S-4", "Apply the gas laws in problem solving", None, None),
             (2, 3, "S-5", "Describe biomolecules and their functions", CS_LIFE, PS_LIFE),
             (3, 1, "S-6", "Describe the nervous and endocrine systems", CS_HUMAN, PS_HUMAN),
             (3, 2, "S-7", "Describe feedback mechanisms in maintaining homeostasis", None, None),
             (3, 3, "S-8", "Describe the principles of evolution and genetics", CS_LIFE, PS_LIFE)],
    }

    ap_jhs = {
        7: [(1, 1, "AP-1", "Natatalakay ang heograpiya ng Asya", CS_APG, PS_APG),
            (1, 2, "AP-2", "Natutukoy ang mga rehiyon ng Asya", None, None),
            (1, 3, "AP-3", "Nailalarawan ang mga likas na yaman ng Asya", None, None),
            (2, 1, "AP-4", "Natatalakay ang mga sinaunang kabihasnan sa Asya", CS_APH, PS_APH),
            (2, 2, "AP-5", "Nasusuri ang mga kontribusyon ng sinaunang kabihasnan", None, None),
            (3, 1, "AP-6", "Natatalakay ang kolonyalismo at imperyalismo sa Asya", CS_APH, PS_APH),
            (3, 2, "AP-7", "Nasusuri ang mga hamon at pagtugon sa Asya", None, None),
            (3, 3, "AP-8", "Napahahalagahan ang papel ng Asya sa pandaigdigang komunidad", None, None)],
        8: [(1, 1, "AP-1", "Natatalakay ang heograpiya ng daigdig", CS_APG, PS_APG),
            (1, 2, "AP-2", "Natutukoy ang istruktura ng daigdig", None, None),
            (2, 1, "AP-4", "Nasusuri ang mga sinaunang kabihasnan ng daigdig", CS_APH, PS_APH),
            (2, 2, "AP-5", "Natatalakay ang pag-unlad ng mga kabihasnan", None, None),
            (3, 1, "AP-6", "Nasusuri ang mga pagbabago sa daigdig sa makabagong panahon", CS_APH, PS_APH),
            (3, 2, "AP-7", "Napahahalagahan ang pagkakaisa ng daigdig sa harap ng globalisasyon", None, None)],
        9: [(1, 1, "AP-1", "Natatalakay ang konsepto ng ekonomiks", CS_AP, PS_AP),
            (1, 2, "AP-2", "Nasusuri ang supply at demand", None, None),
            (2, 1, "AP-3", "Natatalakay ang istruktura ng pamilihan", CS_AP, PS_AP),
            (2, 2, "AP-4", "Nasusuri ang pambansang kita at pag-unlad", None, None),
            (2, 3, "AP-5", "Natatalakay ang patakaran ng pamahalaan sa ekonomiya", None, None),
            (3, 1, "AP-6", "Nasusuri ang implasyon at paggawa", CS_AP, PS_AP),
            (3, 2, "AP-7", "Natatalakay ang sektor ng ekonomiya", None, None),
            (3, 3, "AP-8", "Napahahalagahan ang papel ng sambahayan at bahay-kalakal", None, None)],
        10: [(1, 1, "AP-1", "Natatalakay ang mga kontemporaryong isyu", CS_AP, PS_AP),
             (1, 2, "AP-2", "Nasusuri ang mga isyung pangkapaligiran", None, None),
             (2, 1, "AP-3", "Natatalakay ang mga isyung pang-ekonomiya", CS_AP, PS_AP),
             (2, 2, "AP-4", "Nasusuri ang mga isyung pampolitika at karapatang pantao", None, None),
             (2, 3, "AP-5", "Natatalakay ang mga isyung panlipunan", None, None),
             (3, 1, "AP-6", "Nasusuri ang mga isyung pangkasarian", CS_AP, PS_AP),
             (3, 2, "AP-7", "Natatalakay ang mga hakbang sa pagtugon sa mga kontemporaryong isyu", None, None),
             (3, 3, "AP-8", "Napahahalagahan ang aktibong pakikilahok sa mga isyung panlipunan", None, None)],
    }

    ve_jhs = {g: [
        (1, 1, "VE-1", "Identify personal values and their importance", CS_VAL, PS_VAL),
        (1, 2, "VE-2", "Demonstrate self-discipline and responsibility", None, None),
        (2, 1, "VE-3", "Show respect for others and their differences", CS_SOC, PS_SOC),
        (2, 2, "VE-4", "Practice empathy and compassion", None, None),
        (2, 3, "VE-5", "Demonstrate honesty and integrity", None, None),
        (3, 1, "VE-6", "Identify roles in nation-building", CS_COMM, PS_COMM),
        (3, 2, "VE-7", "Practice environmental stewardship", CS_ENV, PS_ENV),
        (3, 3, "VE-8", "Demonstrate love of country and active citizenship", None, None),
    ] for g in [7, 8, 9, 10]}

    def seed_comps(code, comp_list):
        sid = subject_map.get(code)
        if not sid:
            return
        has = cursor.execute(
            "SELECT COUNT(*) FROM competencies WHERE subject_id = ?", (sid,)
        ).fetchone()[0]
        if has:
            return
        for term, week, ccode, desc, cstd, pstd in comp_list:
            cs_val = cstd if cstd else ""
            ps_val = pstd if pstd else ""
            cursor.execute(
                "INSERT OR IGNORE INTO competencies (subject_id, term, week, code, description, content_standard, performance_standard) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, term, week, ccode, desc, cs_val, ps_val),
            )
        conn.commit()

    # Kindergarten
    seed_comps("KINDER", comps["KINDER"])
    # Grade 1
    for key in ["LANG-G1", "RL-G1", "MATH-G1", "GMRC-G1", "MAKABANSA-G1"]:
        if key in comps:
            seed_comps(key, comps[key])

    # Grade 2
    seed_comps("FIL-G2", fil_gen[2])
    seed_comps("ENG-G2", eng_gen[2])
    seed_comps("MATH-G2", math_gen[2])
    seed_comps("GMRC-G2", grades_2_3["GMRC"])
    seed_comps("MAKABANSA-G2", grades_2_3["MAKABANSA"])

    # Grade 3
    seed_comps("FIL-G3", fil_gen[3])
    seed_comps("ENG-G3", eng_gen[3])
    seed_comps("MATH-G3", math_gen[3])
    seed_comps("SCI-G3", sci_gen[3])
    seed_comps("GMRC-G3", grades_2_3["GMRC"])
    seed_comps("MAKABANSA-G3", grades_2_3["MAKABANSA"])

    # Grades 4-6
    for g in [4, 5, 6]:
        seed_comps(f"FIL-G{g}", fil_gen[g] if g in fil_gen else fil_gen[3])
        seed_comps(f"ENG-G{g}", eng_g[g])
        seed_comps(f"MATH-G{g}", math_g[g])
        seed_comps(f"SCI-G{g}", sci_g[g])
        seed_comps(f"AP-G{g}", ap_gen[g])
        seed_comps(f"MAPEH-G{g}", mapeh_gen[g])
        seed_comps(f"GMRC-G{g}", grades_2_3["GMRC"])
        seed_comps(f"EPP-G{g}", epp_tle_gen[g])

    # Grades 7-10
    for g in [7, 8, 9, 10]:
        seed_comps(f"FIL-G{g}", fil_jhs[g])
        seed_comps(f"ENG-G{g}", eng_jhs[g])
        seed_comps(f"MATH-G{g}", math_jhs[g])
        seed_comps(f"SCI-G{g}", sci_jhs[g])
        seed_comps(f"AP-G{g}", ap_jhs[g])
        seed_comps(f"MAPEH-G{g}", mapeh_gen[g])
        seed_comps(f"VE-G{g}", ve_jhs[g])
        seed_comps(f"TLE-G{g}", tle_gen[g])

    # SHS Grades 11-12
    def _extend_weeks(base, max_week=10):
        """Fill all weeks 1-max_week for each term. Gaps reuse the nearest prior competency."""
        by_term = {}
        for t, w, code, desc, cs, ps in base:
            by_term.setdefault(t, {})[w] = (code, desc, cs, ps)
        out = []
        for t in sorted(by_term):
            weeks = sorted(by_term[t])
            first_code, first_desc, first_cs, first_ps = by_term[t][weeks[0]]
            last = (first_code, first_desc, first_cs, first_ps)
            for w in range(1, max_week + 1):
                if w in by_term[t]:
                    last = by_term[t][w]
                ccode, desc, cs, ps = last
                suffix = chr(96 + w) if w not in by_term[t] else ""
                out.append((t, w, ccode + suffix, desc, cs, ps))
        return out

    shs_comps = {
        "ORALCOM": _extend_weeks([
            (1, 1, "OC-1", "Explain the nature and elements of oral communication", CS_LANG, PS_LANG),
            (1, 2, "OC-2", "Differentiate various models of communication", None, None),
            (2, 4, "OC-3", "Use strategies for effective interpersonal communication", CS_LANG, PS_LANG),
            (2, 5, "OC-4", "Employ verbal and nonverbal communication appropriately", None, None),
            (3, 7, "OC-5", "Deliver a speech for a specific purpose and audience", CS_LANG, PS_LANG),
            (3, 8, "OC-6", "Evaluate the effectiveness of oral communication", None, None),
        ]),
        "READWRIT": _extend_weeks([
            (1, 1, "RW-1", "Describe the nature and purposes of written communication", CS_COMP, PS_COMP),
            (1, 2, "RW-2", "Use patterns of paragraph development", None, None),
            (2, 4, "RW-3", "Evaluate and critique a written text", CS_COMP, PS_COMP),
            (2, 5, "RW-4", "Apply strategies for critical reading", None, None),
            (3, 7, "RW-5", "Write different types of academic and professional texts", CS_WRIT, PS_WRIT),
            (3, 8, "RW-6", "Produce a well-written research or position paper", None, None),
        ]),
        "KOMFIL": _extend_weeks([
            (1, 1, "KF-1", "Natatalakay ang kahalagahan ng wika sa kultura", CS_FIL, PS_FIL),
            (1, 2, "KF-2", "Natutukoy ang mga varayti ng wika", None, None),
            (2, 4, "KF-3", "Nasusuri ang mga sitwasyong pangwika sa lipunan", CS_FIL, PS_FIL),
            (2, 5, "KF-4", "Nakagagamit ng angkop na rehistro ng wika", None, None),
            (3, 7, "KF-5", "Nakasusulat ng pananaliksik tungkol sa wika at kulturang Pilipino", CS_FILW, PS_FILW),
            (3, 8, "KF-6", "Nakapagtatanghal ng isang dulang pampanitikan", None, None),
        ]),
        "PANITIKAN": _extend_weeks([
            (1, 1, "21C-1", "Identify representative texts from the Philippines and the world", CS_COMP, PS_COMP),
            (1, 2, "21C-2", "Analyze themes and literary elements in 21st century literature", None, None),
            (2, 4, "21C-3", "Compare and contrast literary texts across cultures", CS_COMP, PS_COMP),
            (2, 5, "21C-4", "Interpret literary works using multimedia formats", None, None),
            (3, 7, "21C-5", "Create a creative adaptation of a literary text", CS_WRIT, PS_WRIT),
            (3, 8, "21C-6", "Produce a written literary analysis", None, None),
        ]),
        "GENMATH": _extend_weeks([
            (1, 1, "GM-1", "Solve problems involving functions and their graphs", CS_ALG, PS_ALG),
            (1, 2, "GM-2", "Perform operations on functions", None, None),
            (2, 4, "GM-3", "Solve problems involving rational, exponential, and logarithmic functions", CS_ALG, PS_ALG),
            (2, 5, "GM-4", "Solve problems involving simple and compound interest", CS_PROB, PS_PROB),
            (3, 7, "GM-5", "Illustrate and compute annuities, stocks, and bonds", CS_PROB, PS_PROB),
            (3, 8, "GM-6", "Apply logic and reasoning to real-life situations", None, None),
        ]),
        "STATS": _extend_weeks([
            (1, 1, "SP-1", "Illustrate random variables and probability distributions", CS_DATA, PS_DATA),
            (1, 2, "SP-2", "Compute probabilities using normal distribution", None, None),
            (2, 4, "SP-3", "Construct sampling distributions and estimate parameters", CS_DATA, PS_DATA),
            (2, 5, "SP-4", "Perform hypothesis testing on population means and proportions", None, None),
            (3, 7, "SP-5", "Analyze relationships using correlation and regression", CS_DATA, PS_DATA),
            (3, 8, "SP-6", "Present statistical findings in a written report", None, None),
        ]),
        "EARTHSCI": _extend_weeks([
            (1, 1, "ES-1", "Describe the origin and structure of the Earth", CS_EARTH, PS_EARTH),
            (1, 2, "ES-2", "Explain the formation of minerals and rocks", None, None),
            (2, 4, "ES-3", "Describe the processes that shape the Earth's surface", CS_EARTH, PS_EARTH),
            (2, 5, "ES-4", "Explain natural hazards and disaster risk reduction", None, None),
            (3, 7, "ES-5", "Describe the Earth's internal structure and processes", CS_EARTH, PS_EARTH),
            (3, 8, "ES-6", "Discuss the importance of water and energy resources", None, None),
        ]),
        "PERSDEV": _extend_weeks([
            (1, 1, "PD-1", "Explain the concept of self-development and personal effectiveness", CS_VAL, PS_VAL),
            (1, 2, "PD-2", "Identify personal strengths, weaknesses, and values", None, None),
            (2, 4, "PD-3", "Describe developmental stages and tasks of adolescence", CS_VAL, PS_VAL),
            (2, 5, "PD-4", "Demonstrate coping skills and resilience", None, None),
            (3, 7, "PD-5", "Make a personal development plan for career and life goals", CS_VAL, PS_VAL),
            (3, 8, "PD-6", "Identify career options aligned with personal skills and interests", None, None),
        ]),
        "PEHEALTH": _extend_weeks([
            (1, 1, "PEH-1", "Demonstrate understanding of fitness and exercise programs", CS_PE, PS_PE),
            (1, 2, "PEH-2", "Perform physical activities for health and fitness", None, None),
            (2, 4, "PEH-3", "Explain the concepts of healthy eating and nutrition", CS_HEALTH, PS_HEALTH),
            (2, 5, "PEH-4", "Practice stress management techniques", None, None),
            (3, 7, "PEH-5", "Design a personal health and fitness plan", CS_PE, PS_PE),
            (3, 8, "PEH-6", "Demonstrate safety practices during physical activities", None, None),
        ]),
        "UCSP": _extend_weeks([
            (1, 1, "UCSP-1", "Explain the concepts of culture, society, and politics", CS_AP, PS_AP),
            (1, 2, "UCSP-2", "Analyze cultural variation and social differences", None, None),
            (2, 4, "UCSP-3", "Describe the development of societies and social institutions", CS_AP, PS_AP),
            (2, 5, "UCSP-4", "Analyze social stratification and inequality", None, None),
            (3, 7, "UCSP-5", "Discuss citizenship and political engagement", CS_AP, PS_AP),
            (3, 8, "UCSP-6", "Evaluate the role of social movements and change", None, None),
        ]),
    }

    for g in [11, 12]:
        for code_prefix in ["ORALCOM", "READWRIT", "KOMFIL", "PANITIKAN", "GENMATH", "STATS", "EARTHSCI", "PERSDEV", "PEHEALTH", "UCSP"]:
            key = f"{code_prefix}-G{g}"
            seed_comps(key, shs_comps[code_prefix])

    conn.close()
    print(f"Database seeded successfully! {len(subjects)} subjects added.")


if __name__ == "__main__":
    init_database()
    seed_data()
