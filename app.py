from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, Response, abort
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import os, json, io, csv, re, secrets, sys
import urllib.request, urllib.error
from urllib.parse import urlparse
from datetime import datetime, date, timedelta


def _frozen():
    return bool(getattr(sys, "frozen", False))


# Windowed builds (PyInstaller console=False) have no usable stdout/stderr.
# Flask/click crash with OSError 22 when printing the server banner, so
# silence them in frozen mode.
if _frozen():
    try:
        import io
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
    except Exception:
        pass


def _resource_dir():
    """Read-only bundled resources (templates, static, shipped config)."""
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

# Ship a default config; on first run copy it into the writable data dir.
_BUNDLED_CONFIG = os.path.join(_resource_dir(), "app_config.json")
CONFIG_PATH = os.path.join(DATA_DIR, "app_config.json")
if not os.path.exists(CONFIG_PATH) and os.path.exists(_BUNDLED_CONFIG):
    import shutil
    shutil.copy2(_BUNDLED_CONFIG, CONFIG_PATH)


def _load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _get_secret_key():
    """Use a persistent, randomly generated secret key (created on first run)."""
    cfg = _load_config()
    key = cfg.get("secret_key")
    if not key:
        key = secrets.token_hex(32)
        cfg["secret_key"] = key
        try:
            _save_config(cfg)
        except Exception:
            pass  # read-only dir: use this key for the session, regenerate next run
    return key


app = Flask(__name__, template_folder=os.path.join(_resource_dir(), "templates"),
            static_folder=os.path.join(_resource_dir(), "static"))
app.secret_key = _get_secret_key()
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(DATA_DIR, "session_files")
# Keep drafts (and the session cookie) for 14 days so closing the browser
# does not wipe an in-progress lesson plan.
app.config["SESSION_PERMANENT"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=14)
Session(app)

# --- Social login (Google / Facebook) via Authlib -------------------------
oauth = OAuth(app)


def _env_or_cfg(name, cfg_key=None):
    val = os.environ.get(name, "").strip()
    if val:
        return val
    cfg = _load_config()
    return str(cfg.get(cfg_key or name, "")).strip()


def _social_credentials():
    return {
        "google_id": _env_or_cfg("GOOGLE_CLIENT_ID", "google_client_id"),
        "google_secret": _env_or_cfg("GOOGLE_CLIENT_SECRET", "google_client_secret"),
        "facebook_id": _env_or_cfg("FACEBOOK_APP_ID", "facebook_app_id"),
        "facebook_secret": _env_or_cfg("FACEBOOK_APP_SECRET", "facebook_app_secret"),
    }


def _register_oauth():
    creds = _social_credentials()
    try:
        if creds["google_id"] and creds["google_secret"]:
            oauth.register(
                name="google",
                client_id=creds["google_id"],
                client_secret=creds["google_secret"],
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={"scope": "openid email profile"},
            )
        if creds["facebook_id"] and creds["facebook_secret"]:
            oauth.register(
                name="facebook",
                client_id=creds["facebook_id"],
                client_secret=creds["facebook_secret"],
                access_token_url="https://graph.facebook.com/v19.0/oauth/access_token",
                authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
                userinfo_endpoint="https://graph.facebook.com/me?fields=id,name,email,picture",
                client_kwargs={"scope": "email public_profile"},
            )
    except Exception:
        pass


_register_oauth()


def _social_available():
    creds = _social_credentials()
    return bool(creds["google_id"] and creds["google_secret"] or
                creds["facebook_id"] and creds["facebook_secret"])


def _csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def _inject_csrf():
    return {"csrf_token": _csrf_token()}


@app.before_request
def _before_request():
    # Survive browser restarts so in-progress drafts are not lost.
    session.permanent = True
    token = session.get("_csrf_token")
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not token or not sent or not secrets.compare_digest(token, sent):
            abort(400, description="Invalid or missing CSRF token")
    if not token:
        session["_csrf_token"] = secrets.token_urlsafe(32)

    if not _access_gate_enabled():
        return
    path = request.path
    if _is_auth_free(path):
        return
    user = _current_user()
    if user:
        if _user_has_access(user):
            return
        if path != "/subscribe":
            return redirect(url_for("subscribe"))
        return
    if session.get("_access_granted"):
        return
    return redirect(url_for("access", next=path))


def _is_auth_free(path):
    return (path in ("/access", "/signup", "/subscribe", "/favicon.ico")
            or path.startswith("/static/")
            or path.startswith("/login/"))


def _current_user():
    uid = session.get("_user_id")
    if not uid:
        return None
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT id, email, password_hash, name, school, status, plan, "
            "trial_start, trial_end, paid_until, created_at, last_login, "
            "google_id, facebook_id, trial_exports "
            "FROM users WHERE id = ?", (uid,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0], "email": row[1], "password_hash": row[2], "name": row[3],
            "school": row[4], "status": row[5], "plan": row[6],
            "trial_start": row[7], "trial_end": row[8], "paid_until": row[9],
            "created_at": row[10], "last_login": row[11],
            "google_id": row[12], "facebook_id": row[13],
            "trial_exports": row[14] or 0,
        }
    except Exception:
        return None


def _user_has_access(user):
    if not user or user.get("status") == "disabled":
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    if user["status"] == "trial":
        return bool(user.get("trial_end")) and user["trial_end"] >= today
    if user["status"] == "active":
        if user.get("plan") == "beta":
            return True
        return bool(user.get("paid_until")) and user["paid_until"] >= today
    return False


def _has_any_access():
    if session.get("_access_granted"):
        return True
    user = _current_user()
    return bool(user and _user_has_access(user))


def _trial_export_limit():
    """Number of exports a free trial user may download (configurable)."""
    cfg = _load_config()
    try:
        return max(1, int(cfg.get("trial_export_limit", 3)))
    except (TypeError, ValueError):
        return 3


def _is_trial_user(user=None):
    user = user or _current_user()
    return bool(user and user.get("status") == "trial")


def _trial_export_blocked():
    """If the current user is a trial user who used up their export limit,
    return a redirect to /subscribe; otherwise None."""
    user = _current_user()
    if not _is_trial_user(user):
        return None
    used = int(user.get("trial_exports") or 0)
    if used >= _trial_export_limit():
        return redirect(url_for("subscribe", msg="limit"))
    return None


def _record_trial_export():
    """Count one export for the current user (trial users only)."""
    user = _current_user()
    if not _is_trial_user(user):
        return
    try:
        conn = get_connection()
        conn.execute("UPDATE users SET trial_exports = trial_exports + 1 WHERE id = ?", (user["id"],))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _access_gate_enabled():
    """Gate is on when an env master code is set OR there are active school codes."""
    if _get_master_code():
        return True
    try:
        conn = get_connection()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT COUNT(*) FROM school_access WHERE active = 1 AND "
            "(expires_at IS NULL OR expires_at = '' OR expires_at >= date('now'))"
        ).fetchone()
        conn.close()
        return bool(row and row[0] > 0)
    except Exception:
        return False


def _get_master_code():
    code = os.environ.get("LAMDAG_ACCESS_CODE", "").strip()
    if not code:
        code = (_load_config() or {}).get("access_code", "").strip()
    return code


def _lookup_school_code(sent):
    """Return (school_name, plan) if the code belongs to an active school code."""
    if not sent:
        return None
    try:
        conn = get_connection()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT school_name, plan, expires_at FROM school_access "
            "WHERE access_code = ? AND active = 1", (sent,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        if row[2] and row[2] and row[2] < datetime.now().strftime("%Y-%m-%d"):
            return None
        return {"school": row[0], "plan": row[1]}
    except Exception:
        return None


@app.route("/access", methods=["GET", "POST"])
def access():
    if not _access_gate_enabled():
        return redirect(url_for("index"))
    if _has_any_access():
        return redirect(request.args.get("next") or url_for("index"))
    error = ""
    tab = "login"
    if request.method == "POST":
        tab = request.form.get("tab", "login")
        if tab == "code":
            sent = request.form.get("access_code", "").strip()
            master = _get_master_code()
            if master and secrets.compare_digest(sent, master):
                session["_access_granted"] = True
                session["_access_admin"] = True
                session["_access_school"] = "LAMDAG Admin"
                return redirect(request.args.get("next") or url_for("index"))
            school = _lookup_school_code(sent)
            if school:
                session["_access_granted"] = True
                session["_access_admin"] = False
                session["_access_school"] = school["school"]
                session["_access_plan"] = school["plan"]
                return redirect(request.args.get("next") or url_for("index"))
            error = "That access code is not correct. Please try again."
        else:
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = _get_user_by_email(email)
            if not user or not check_password_hash(user["password_hash"], password):
                error = "That email or password is not correct."
            elif user["status"] == "disabled":
                error = "This account has been disabled."
            elif not _user_has_access(user):
                session["_user_id"] = user["id"]
                _touch_login(user["id"])
                return redirect(url_for("subscribe"))
            else:
                session["_user_id"] = user["id"]
                _touch_login(user["id"])
                return redirect(request.args.get("next") or url_for("index"))
    return render_template("access.html", error=error, tab=tab,
                           next_path=request.args.get("next") or "",
                           social_available=_social_available(),
                           social_creds=_social_credentials())


@app.route("/access/logout", methods=["POST"])
def access_logout():
    session.pop("_access_granted", None)
    session.pop("_access_admin", None)
    session.pop("_access_school", None)
    session.pop("_access_plan", None)
    session.pop("_user_id", None)
    return redirect(url_for("access"))


def _get_user_by_email(email):
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT id, email, password_hash, name, school, status, plan, "
            "trial_start, trial_end, paid_until, created_at, last_login, "
            "google_id, facebook_id "
            "FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0], "email": row[1], "password_hash": row[2], "name": row[3],
            "school": row[4], "status": row[5], "plan": row[6],
            "trial_start": row[7], "trial_end": row[8], "paid_until": row[9],
            "created_at": row[10], "last_login": row[11],
            "google_id": row[12], "facebook_id": row[13],
        }
    except Exception:
        return None


def _touch_login(uid):
    try:
        conn = get_connection()
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?",
                     (datetime.now().strftime("%Y-%m-%d %H:%M"), uid))
        conn.commit()
        conn.close()
    except Exception:
        pass


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if not _access_gate_enabled():
        return redirect(url_for("index"))
    if _has_any_access():
        return redirect(request.args.get("next") or url_for("index"))
    error = ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        school = request.form.get("school", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not name or not email or not password:
            error = "Please fill in all required fields."
        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            error = "Please enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif _get_user_by_email(email):
            error = "An account with that email already exists. Try logging in instead."
        else:
            today = datetime.now()
            trial_end = today + timedelta(days=14)
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (email, password_hash, name, school, status, plan, "
                    "trial_start, trial_end, paid_until, created_at) "
                    "VALUES (?, ?, ?, ?, 'trial', '', ?, ?, '', ?)",
                    (email, generate_password_hash(password), name, school,
                     today.strftime("%Y-%m-%d"), trial_end.strftime("%Y-%m-%d"),
                     today.strftime("%Y-%m-%d %H:%M")),
                )
                conn.commit()
                uid = cur.lastrowid
            finally:
                conn.close()
            session["_user_id"] = uid
            session.pop("_access_granted", None)
            session.pop("_access_admin", None)
            session.pop("_access_school", None)
            session.pop("_access_plan", None)
            return redirect(url_for("index"))
    return render_template("signup.html", error=error,
                           next_path=request.args.get("next") or "")


@app.route("/subscribe")
def subscribe():
    user = _current_user()
    msg = request.args.get("msg", "")
    return render_template("subscribe.html", user=user,
                           gcash_number="09952274754", msg=msg)


@app.route("/login/google")
def google_login():
    creds = _social_credentials()
    if not (creds["google_id"] and creds["google_secret"]):
        return redirect(url_for("access"))
    redirect_uri = url_for("google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        userinfo = oauth.google.userinfo()
    except Exception:
        return redirect(url_for("access"))
    if not userinfo or not userinfo.get("email"):
        return redirect(url_for("access"))
    return _social_login(userinfo.get("email"), userinfo.get("name", ""),
                         userinfo.get("sub", ""), "google")


@app.route("/login/facebook")
def facebook_login():
    creds = _social_credentials()
    if not (creds["facebook_id"] and creds["facebook_secret"]):
        return redirect(url_for("access"))
    redirect_uri = url_for("facebook_callback", _external=True)
    return oauth.facebook.authorize_redirect(redirect_uri)


@app.route("/login/facebook/callback")
def facebook_callback():
    try:
        token = oauth.facebook.authorize_access_token()
        resp = oauth.facebook.get("me?fields=id,name,email")
        info = resp.json()
    except Exception:
        return redirect(url_for("access"))
    if not info or not info.get("email"):
        return redirect(url_for("access"))
    return _social_login(info["email"], info.get("name", ""),
                         str(info.get("id", "")), "facebook")


def _social_login(email, name, provider_id, provider):
    """Log a user in via social login, creating a free-trial account if new."""
    email = email.strip().lower()
    user = _get_user_by_email(email)
    today = datetime.now()
    trial_end = today + timedelta(days=14)
    conn = get_connection()
    try:
        if user:
            col = "google_id" if provider == "google" else "facebook_id"
            conn.execute(
                f"UPDATE users SET {col} = ?, last_login = ? WHERE id = ?",
                (provider_id, today.strftime("%Y-%m-%d %H:%M"), user["id"]),
            )
            conn.commit()
            uid = user["id"]
        else:
            cur = conn.cursor()
            col = "google_id" if provider == "google" else "facebook_id"
            cur.execute(
                "INSERT INTO users (email, password_hash, name, school, status, plan, "
                "trial_start, trial_end, paid_until, created_at, " + col + ") "
                "VALUES (?, '', ?, '', 'trial', '', ?, ?, '', ?, ?)",
                (email, name, today.strftime("%Y-%m-%d"), trial_end.strftime("%Y-%m-%d"),
                 today.strftime("%Y-%m-%d %H:%M"), provider_id),
            )
            conn.commit()
            uid = cur.lastrowid
    finally:
        conn.close()
    session["_user_id"] = uid
    session.pop("_access_granted", None)
    session.pop("_access_admin", None)
    session.pop("_access_school", None)
    session.pop("_access_plan", None)
    user = _current_user()
    if user and not _user_has_access(user):
        return redirect(url_for("subscribe"))
    nxt = request.args.get("next") or ""
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(url_for("index"))


from database.init_db import get_connection
from generators.ilaw_docx import generate_ilaw_docx
from generators.ilaw_pdf import generate_ilaw_pdf
from generators.exemplar_pdf import generate_exemplar_pdf
from generators.exemplar_layout import QUARTER_LABELS, PROCEDURES
from generators import exemplar_layout as LE_LAYOUT
from generators.bow_docx import generate_bow_docx
from generators.bow_pdf import find_bow_extras, find_bow_pdf
from suggestions import build_suggestions, flow_times_dict, _parse_minutes, _is_tagalog

# WeasyPrint needs GTK libraries (Pango, FreeType, ...) on Windows. When frozen
# we ship those DLLs next to the app (in the "gtk" bundle folder) so the
# official HTML/CSS PDF renderer works on any machine with no install. If they
# are not available, fall back to the pure-Python fpdf2 generator so PDF export
# still works.
def _gtk_bin():
    if _frozen():
        return os.path.join(_resource_dir(), "gtk")
    return r"C:\msys64\mingw64\bin"


_GTK_BIN = _gtk_bin()
if os.path.isdir(_GTK_BIN):
    if _GTK_BIN not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _GTK_BIN + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(_GTK_BIN)
        except Exception:
            pass
    # Fontconfig needs to find its config (fonts.conf + conf.d/) and its DLL.
    # We bundle them in the gtk folder, so point the env vars there.
    fc_file = os.path.join(_GTK_BIN, "fonts.conf")
    if os.path.exists(fc_file):
        os.environ["FONTCONFIG_FILE"] = fc_file
        os.environ["FONTCONFIG_PATH"] = _GTK_BIN

try:
    from weasyprint import HTML
except Exception:
    HTML = None

# Export folder. On Windows it's Desktop/LAMDAG_Plans (familiar to teachers).
# On servers (Render/Railway) there is no Desktop, so allow LAMDAG_EXPORT_DIR
# or fall back to a local LAMDAG_Plans folder in the writable data dir.
if os.environ.get("LAMDAG_EXPORT_DIR"):
    DESKTOP = os.environ["LAMDAG_EXPORT_DIR"]
elif os.path.isdir(os.path.join(os.path.expanduser("~"), "Desktop")):
    DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop", "LAMDAG_Plans")
else:
    DESKTOP = os.path.join(DATA_DIR, "LAMDAG_Plans")
os.makedirs(DESKTOP, exist_ok=True)

DEFAULT_TERM_CONFIG = {
    "school_year": "2026-2027",
    "terms": {
        "1": {"start": "2026-06-08", "end": "2026-09-15"},
        "2": {"start": "2026-09-16", "end": "2026-12-18"},
        "3": {"start": "2027-01-04", "end": "2027-04-08"},
    },
}


def _get_term_config():
    cfg = _load_config()
    tc = cfg.get("term_config")
    if not tc or "terms" not in tc:
        return DEFAULT_TERM_CONFIG
    return tc


def _set_term_config(term_config):
    cfg = _load_config()
    cfg["term_config"] = term_config
    _save_config(cfg)


def _fmt_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d, %Y").replace(" 0", " ")
    except (ValueError, TypeError):
        return iso or ""


def _term_label(start, end):
    try:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
    except (ValueError, TypeError):
        return f"{start} – {end}"
    s_txt = s.strftime("%b %d").replace(" 0", " ")
    if s.year == e.year:
        e_txt = e.strftime("%b %d, %Y").replace(" 0", " ")
    else:
        s_txt = s.strftime("%b %d, %Y").replace(" 0", " ")
        e_txt = e.strftime("%b %d, %Y").replace(" 0", " ")
    return f"{s_txt} – {e_txt}"


def _term_ranges():
    tc = _get_term_config()
    return [
        {
            "value": k,
            "label": _term_label(v["start"], v["end"]),
            "start": v["start"],
            "end": v["end"],
        }
        for k, v in sorted(tc["terms"].items(), key=lambda x: int(x[0]))
    ]


def _get_update_url():
    return _load_config().get("curriculum_update_url", "")


def _set_update_url(url):
    cfg = _load_config()
    cfg["curriculum_update_url"] = url
    _save_config(cfg)


@app.context_processor
def _inject_globals():
    return {
        "school_year": _get_term_config().get("school_year", ""),
        "current_user": _current_user(),
    }

SUGGESTION_FIELDS = [
    "lesson_name", "objectives", "integration", "learner_context", "pre_lesson",
    "flow_introduce", "flow_learn", "flow_apply", "flow_wrapup",
    "learning_resources", "formative_assessment",
    "extended_learning", "reflection",
    "references", "ai_declaration",
    "le_step1", "le_step2", "le_step3", "le_step4", "le_step5", "le_step6", "le_step7",
    "le_ann_pre", "le_ann_purpose", "le_ann_examples", "le_ann_concept",
    "le_ann_mastery", "le_ann_apply", "le_ann_general",
    "le_quiz", "le_perf_overview", "le_perf_directions", "le_perf_rubric",
]

COMPETENCY_DERIVED_FIELDS = [
    "lesson_name", "objectives", "integration", "learner_context", "pre_lesson",
    "flow_introduce", "flow_learn", "flow_apply", "flow_wrapup",
    "learning_resources", "formative_assessment",
    "extended_learning", "reflection",
]

STEP_FIELDS = {
    1: [],
    3: ["lesson_name", "objectives", "integration", "learner_context"],
    4: ["pre_lesson", "flow_introduce", "flow_learn", "flow_apply", "flow_wrapup", "learning_resources"],
    5: ["formative_assessment"],
    6: ["extended_learning", "reflection", "references", "ai_declaration"],
}


def _suggest():
    subject = session.get("subject", "")
    competency_desc = session.get("competency_description", "")
    grade_level = session.get("grade_level", "")
    time_allotment = session.get("time_allotment", "50 mins")
    content_standard = session.get("content_standard", "")
    performance_standard = session.get("performance_standard", "")
    return build_suggestions(
        subject, competency_desc, grade_level, time_allotment,
        content_standard=content_standard,
        performance_standard=performance_standard,
    )


_LEGACY_REFLECTION_PLACEHOLDER = "What worked well today:"


def _merge_suggestions(suggestions, fields=None):
    keys = fields or suggestions.keys()
    for key in keys:
        if key not in suggestions:
            continue
        current = session.get(key)
        if key == "reflection" and current and _LEGACY_REFLECTION_PLACEHOLDER in current:
            current = ""  # clear stale fill-in-the-blank reflection from older builds
        if not current:
            session[key] = suggestions[key]


def _draft_step():
    return session.get("draft_step", 0)


def _draft_exists():
    return 0 < _draft_step() <= 6 and not session.get("_loaded_plan") and any(session.get(k) for k in ALL_FIELDS)


def _set_draft_step(step):
    session["draft_step"] = step
    session.modified = True


DRAFT_STEP_LABELS = {
    1: "Basic Info",
    2: "Select Learning Competency",
    3: "Intentions",
    4: "Learning Experience",
    5: "Assessment",
    6: "Ways Forward",
}


def _draft_url(step):
    if step >= 6:
        return "/preview"
    if step <= 1:
        return "/generate"
    return f"/generate/step{step}"


def _draft_status():
    step = _draft_step()
    if not _draft_exists():
        return None
    label = DRAFT_STEP_LABELS.get(step, "Lesson Plan")
    if step >= 6:
        return {"step": step, "label": "Preview", "complete": True, "url": "/preview"}
    return {"step": step, "label": label, "complete": False, "url": _draft_url(step)}


@app.route("/")
def index():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM saved_plans")
    total_plans = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM saved_plans WHERE term = '1'")
    term1_plans = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM competencies")
    total_comps = cursor.fetchone()[0]
    cursor.execute(
        """SELECT id, name, grade_level, subject, term, week, updated_at
           FROM saved_plans ORDER BY updated_at DESC LIMIT 3"""
    )
    recent = [
        {
            "id": r[0], "name": r[1], "grade_level": r[2], "subject": r[3],
            "term": r[4], "week": r[5], "updated_at": r[6],
        }
        for r in cursor.fetchall()
    ]
    conn.close()
    return render_template(
        "dashboard.html",
        total_plans=total_plans,
        term1_plans=term1_plans,
        total_comps=total_comps,
        recent=recent,
        draft=_draft_status(),
    )


@app.route("/draft/discard", methods=["POST"])
def discard_draft():
    for key in list(session.keys()):
        if key in ALL_FIELDS or key in ("draft_step", "competency_description",
                                        "content_standard", "performance_standard",
                                        "_suggest_source", "_loaded_plan",
                                        "_loaded_plan_id", "_loaded_plan_name"):
            session.pop(key, None)
    session.modified = True
    return redirect(url_for("index"))


def _capture_basic_info(form):
    session["_loaded_plan"] = False
    session["school"] = form.get("school", "")
    session["region"] = form.get("region", "")
    session["division"] = form.get("division", "")
    session["teacher"] = form.get("teacher", "")
    session["grade_level"] = form.get("grade_level", "")
    session["section"] = form.get("section", "")
    session["subject"] = form.get("subject", "")
    session["term"] = form.get("term", "1")
    session["week"] = form.get("week", "1")
    session["date"] = form.get("date", "")
    session["time_allotment"] = form.get("time_allotment", "50 mins")
    session["sessions"] = form.get("sessions", "")
    session["school_week"] = form.get("school_week", "5")


@app.route("/generate", methods=["GET", "POST"])
def step1():
    if request.method == "POST":
        _capture_basic_info(request.form)
        _set_draft_step(2)
        return redirect(url_for("step2"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT grade_level FROM subjects GROUP BY grade_level ORDER BY MIN(sort_order)")
    grades = [row[0] for row in cursor.fetchall()]
    conn.close()

    _merge_suggestions(_suggest(), STEP_FIELDS[1])

    term_ranges = _term_ranges()

    data = {
        "school": session.get("school", ""),
        "region": session.get("region", ""),
        "division": session.get("division", ""),
        "teacher": session.get("teacher", ""),
        "grade_level": session.get("grade_level", ""),
        "section": session.get("section", ""),
        "subject": session.get("subject", ""),
        "term": session.get("term", "1"),
        "week": session.get("week", "1"),
        "date": session.get("date", ""),
        "time_allotment": session.get("time_allotment", "50 mins"),
        "lesson_name": session.get("lesson_name", ""),
        "sessions": session.get("sessions", ""),
        "school_week": session.get("school_week", "5"),
        "designation": session.get("designation", ""),
        "school_head": session.get("school_head", ""),
        "school_head_designation": session.get("school_head_designation", ""),
    }
    return render_template("step1_basic_info.html", grades=grades, data=data,
                           term_ranges=term_ranges)


@app.route("/generate/step2", methods=["GET", "POST"])
def step2():
    if request.method == "POST":
        manual_code = request.form.get("manual_code", "").strip()
        competency_code = request.form.get("competency_code", "").strip()
        if manual_code:
            session["competency_code"] = manual_code
            session["competency_description"] = request.form.get("manual_description", "")
            session["content_standard"] = request.form.get("manual_content_standard", "")
            session["performance_standard"] = request.form.get("manual_performance_standard", "")
        else:
            session["competency_code"] = competency_code
            session["competency_description"] = request.form.get("competency_description", "")
            session["content_standard"] = request.form.get("content_standard", "")
            session["performance_standard"] = request.form.get("performance_standard", "")
        if not (session["competency_code"] or session["competency_description"]):
            return redirect(url_for("step2", error=1))
        new_source = "|".join([
            session.get("competency_code", ""), session.get("competency_description", ""),
            session.get("subject", ""), session.get("grade_level", ""),
        ])
        if session.get("_suggest_source") != new_source:
            for key in COMPETENCY_DERIVED_FIELDS:
                session.pop(key, None)
            session["_suggest_source"] = new_source
        _set_draft_step(3)
        return redirect(url_for("step3"))

    grade = session.get("grade_level", "Grade 1")
    subject = session.get("subject", "Language")
    term = session.get("term", "1")
    week = session.get("week", "1")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT DISTINCT c.week, c.code, c.description, c.content_standard, c.performance_standard
           FROM competencies c
           JOIN subjects s ON c.subject_id = s.id
           WHERE s.grade_level = ? AND s.name = ? AND c.term = ?
           ORDER BY c.week, c.code""",
        (grade, subject, term),
    )
    by_week = {}
    for row in cursor.fetchall():
        w = row[0]
        by_week.setdefault(w, []).append({
            "code": row[1],
            "description": row[2],
            "content_standard": row[3] or "",
            "performance_standard": row[4] or "",
        })
    conn.close()

    _set_draft_step(2)
    return render_template("step2_competency.html",
                           by_week=by_week, selected_week=int(week))


@app.route("/generate/step3", methods=["GET", "POST"])
def step3():
    if request.method == "POST":
        session["lesson_name"] = request.form.get("lesson_name", "")
        session["objectives"] = request.form.get("objectives", "")
        session["integration"] = request.form.get("integration", "")
        session["learner_context"] = request.form.get("learner_context", "")
        _set_draft_step(4)
        return redirect(url_for("step4"))
    s = _suggest()
    _merge_suggestions(s)
    _set_draft_step(3)
    return render_template("step3_intentions.html",
                           lesson_name=session.get("lesson_name", ""),
                           objectives=session.get("objectives", ""),
                           integration=session.get("integration", ""),
                           learner_context=session.get("learner_context", ""))


@app.route("/generate/step4", methods=["GET", "POST"])
def step4():
    if request.method == "POST":
        session["pre_lesson"] = request.form.get("pre_lesson", "")
        session["flow_introduce"] = request.form.get("flow_introduce", "")
        session["flow_learn"] = request.form.get("flow_learn", "")
        session["flow_apply"] = request.form.get("flow_apply", "")
        session["flow_wrapup"] = request.form.get("flow_wrapup", "")
        session["learning_resources"] = request.form.get("learning_resources", "")
        _set_draft_step(5)
        return redirect(url_for("step5"))
    s = _suggest()
    _merge_suggestions(s)
    _set_draft_step(4)
    return render_template("step4_experiences.html",
                           pre_lesson=session.get("pre_lesson", ""),
                           flow_introduce=session.get("flow_introduce", ""),
                           flow_learn=session.get("flow_learn", ""),
                           flow_apply=session.get("flow_apply", ""),
                           flow_wrapup=session.get("flow_wrapup", ""),
                           learning_resources=session.get("learning_resources", ""))


@app.route("/generate/step5", methods=["GET", "POST"])
def step5():
    if request.method == "POST":
        session["formative_assessment"] = request.form.get("formative_assessment", "")
        _set_draft_step(6)
        return redirect(url_for("step6"))
    s = _suggest()
    _merge_suggestions(s)
    _set_draft_step(5)
    return render_template("step5_assessment.html",
                           formative_assessment=session.get("formative_assessment", ""))


@app.route("/generate/step6", methods=["GET", "POST"])
def step6():
    if request.method == "POST":
        session["extended_learning"] = request.form.get("extended_learning", "")
        session["reflection"] = request.form.get("reflection", "")
        session["references"] = request.form.get("references", "")
        session["ai_declaration"] = request.form.get("ai_declaration", "")
        _set_draft_step(6)
        return redirect(url_for("preview"))
    s = _suggest()
    _merge_suggestions(s)
    _set_draft_step(6)
    return render_template("step6_ways_forward.html",
                           extended_learning=session.get("extended_learning", ""),
                           reflection=session.get("reflection", ""),
                           references=session.get("references", ""),
                           ai_declaration=session.get("ai_declaration", ""))


@app.route("/preview")
def preview():
    return render_template("preview.html", data=_plan_data())


@app.route("/preview/update_signature", methods=["POST"])
def update_signature():
    session["designation"] = request.form.get("designation", "")
    session["school_head"] = request.form.get("school_head", "")
    session["school_head_designation"] = request.form.get("school_head_designation", "")
    return redirect(url_for("preview"))


@app.route("/exemplar/update", methods=["POST"])
def update_exemplar():
    for key in EXEMPLAR_FIELDS:
        session[key] = request.form.get(key, "")
    session.modified = True
    return redirect(url_for("preview"))


def _safe_filename_component(value, default="Unknown"):
    value = (value or "").strip()
    if not value:
        return default
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    return value.replace(" ", "_")


def _export_dir(subject):
    """Folder per subject under Desktop/LAMDAG_Plans, so downloads stay organized."""
    folder = os.path.join(DESKTOP, _safe_filename_component(subject, default="Subject"))
    os.makedirs(folder, exist_ok=True)
    return folder


@app.route("/export/docx")
def export_docx():
    blocked = _trial_export_blocked()
    if blocked:
        return blocked
    data = _plan_data()

    safe_grade = _safe_filename_component(data["grade_level"])
    safe_subject = _safe_filename_component(data["subject"])
    safe_date = _safe_filename_component(data.get("date", ""), default="")
    filename = f"{safe_subject}_{safe_grade}_T{data['term']}_W{data['week']}.docx"
    if safe_date:
        filename = f"{safe_subject}_{safe_grade}_{safe_date}_T{data['term']}_W{data['week']}.docx"
    output_path = os.path.join(_export_dir(data["subject"]), filename)

    generate_ilaw_docx(data, output_path, watermark=_is_trial_user())
    _record_trial_export()
    return send_file(output_path, as_attachment=True, download_name=filename)


@app.route("/export/pdf")
def export_pdf():
    blocked = _trial_export_blocked()
    if blocked:
        return blocked
    data = _plan_data()

    safe_grade = _safe_filename_component(data["grade_level"])
    safe_subject = _safe_filename_component(data["subject"])
    safe_date = _safe_filename_component(data.get("date", ""), default="")
    filename = f"{safe_subject}_{safe_grade}_T{data['term']}_W{data['week']}.pdf"
    if safe_date:
        filename = f"{safe_subject}_{safe_grade}_{safe_date}_T{data['term']}_W{data['week']}.pdf"
    output_path = os.path.join(_export_dir(data["subject"]), filename)

    watermark = _is_trial_user()
    if HTML is not None:
        try:
            css_path = os.path.join(_resource_dir(), "static", "style.css")
            with open(css_path, "r", encoding="utf-8") as f:
                css = f.read()
            logo_path = os.path.join(_resource_dir(), "static", "deped_logo.png")
            html = render_template("pdf_plan.html", data=data, print_css=css, logo_path=logo_path, watermark=watermark)
            HTML(string=html).write_pdf(output_path)
            _record_trial_export()
            return send_file(output_path, as_attachment=True, download_name=filename)
        except Exception:
            pass  # fall through to the pure-Python generator

    generate_ilaw_pdf(data, output_path, watermark=watermark)
    _record_trial_export()
    return send_file(output_path, as_attachment=True, download_name=filename)


@app.route("/export/exemplar-pdf")
def export_exemplar_pdf():
    blocked = _trial_export_blocked()
    if blocked:
        return blocked
    data = _plan_data()

    safe_grade = _safe_filename_component(data["grade_level"])
    safe_subject = _safe_filename_component(data["subject"])
    safe_date = _safe_filename_component(data.get("date", ""), default="")
    filename = f"{safe_subject}_{safe_grade}_Exemplar_T{data['term']}_W{data['week']}.pdf"
    if safe_date:
        filename = f"{safe_subject}_{safe_grade}_{safe_date}_Exemplar_T{data['term']}_W{data['week']}.pdf"
    output_path = os.path.join(_export_dir(data["subject"]), filename)

    watermark = _is_trial_user()
    if HTML is not None:
        try:
            css_path = os.path.join(_resource_dir(), "static", "style.css")
            with open(css_path, "r", encoding="utf-8") as f:
                css = f.read()
            logo_path = os.path.join(_resource_dir(), "static", "deped_logo.png")
            html = render_template("pdf_exemplar.html", data=data, print_css=css, logo_path=logo_path, watermark=watermark)
            HTML(string=html).write_pdf(output_path)
            _record_trial_export()
            return send_file(output_path, as_attachment=True, download_name=filename)
        except Exception:
            pass  # fall through to the pure-Python generator

    generate_exemplar_pdf(data, output_path, watermark=watermark)
    _record_trial_export()
    return send_file(output_path, as_attachment=True, download_name=filename)


@app.route("/suggest/regenerate")
def regenerate_suggestions():
    step = int(request.args.get("step", "0"))
    fields = STEP_FIELDS.get(step, SUGGESTION_FIELDS)
    s = _suggest()
    for key in fields:
        if key == "reflection":
            continue  # never auto-fill the teacher's reflection
        session[key] = s.get(key, "")
    return jsonify(s)


@app.route("/subjects/<grade>")
def subjects_for_grade(grade):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, grouping FROM subjects WHERE grade_level = ? ORDER BY grouping, name",
        (grade,),
    )
    rows = cursor.fetchall()
    conn.close()
    grouped = {}
    for name, grouping in rows:
        grouped.setdefault(grouping or "Core Subjects", []).append(name)
    groups = [{"name": g, "subjects": subjects} for g, subjects in grouped.items()]
    return {"subjects": [name for _, subjects in grouped.items() for name in subjects], "groups": groups}


@app.route("/competency_terms/<grade>/<subject>")
def competency_terms(grade, subject):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT DISTINCT c.term
           FROM competencies c
           JOIN subjects s ON c.subject_id = s.id
           WHERE s.grade_level = ? AND s.name = ?
           ORDER BY c.term""",
        (grade, subject),
    )
    terms = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"terms": terms}


# Optional fields for the official Strengthened SHS Lesson Exemplar format.
# These are filled on the Preview page (they have no wizard step).
EXEMPLAR_FIELDS = [
    "le_competencies", "le_content",
    "le_quiz", "le_perf_overview", "le_perf_directions", "le_perf_rubric",
    "le_step1", "le_step2", "le_step3", "le_step4", "le_step5", "le_step6", "le_step7",
    "le_ann_pre", "le_ann_purpose", "le_ann_examples", "le_ann_concept",
    "le_ann_mastery", "le_ann_apply", "le_ann_general",
]

ALL_FIELDS = [
    "school", "region", "division", "teacher", "grade_level", "section", "subject", "term", "week",
    "date", "time_allotment", "lesson_name", "sessions",
    "school_week",
    "references", "ai_declaration",
    "designation", "school_head", "school_head_designation",
    "competency_code", "competency_description",
    "content_standard", "performance_standard", "objectives", "integration",
    "learner_context", "pre_lesson", "flow_introduce", "flow_learn",
    "flow_apply", "flow_wrapup", "learning_resources",
    "formative_assessment", "extended_learning", "reflection",
] + EXEMPLAR_FIELDS

ALL_FIELDS_SQL = [f'"{f}"' for f in ALL_FIELDS]


def _format_date(value):
    if not value:
        return ""
    try:
        d = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        return f"{d.strftime('%B')} {d.day}, {d.year}"
    except ValueError:
        return str(value)


def _plan_data():
    data = {k: session.get(k, "") for k in ALL_FIELDS}
    data["time_allotment"] = data["time_allotment"] or "50 mins"
    data["date"] = _format_date(data["date"])
    data["region"] = data["region"] or "Region VII - Central Visayas"
    data["letterhead_division"] = f"SCHOOLS DIVISION OF {data['division'].upper()}" if data["division"] else ""
    data["letterhead_school"] = data["school"].upper() if data["school"] else ""
    # Derived fields for the official ILAW template layout
    if not data["sessions"]:
        data["sessions"] = f"1 session ({data['time_allotment']})"
    data["flow_times"] = flow_times_dict(_parse_minutes(data["time_allotment"]))
    data["grade_section"] = data["grade_level"]
    if data["section"]:
        data["grade_section"] = f"{data['grade_level']} — {data['section']}".strip(" —")
    data["school_year"] = _get_term_config().get("school_year", "")
    data["quarter"] = QUARTER_LABELS.get(str(data["term"]), f"Term {data['term']}")
    comp_parts = []
    if data["competency_description"]:
        comp_parts.append(data["competency_description"])
    if data["competency_code"]:
        comp_parts.append(f"({data['competency_code']})")
    if data["content_standard"]:
        comp_parts.append(f"Content Standard: {data['content_standard']}")
    if data["performance_standard"]:
        comp_parts.append(f"Performance Standard: {data['performance_standard']}")
    data["competency_full"] = "\n".join(comp_parts)
    # Exemplar uses the competency alone (standards get their own rows).
    short_parts = []
    if data["competency_description"]:
        short_parts.append(data["competency_description"])
    if data["competency_code"]:
        short_parts.append(f"({data['competency_code']})")
    data["competency_short"] = "\n".join(short_parts)

    # --- Derived data for the official Strengthened SHS Lesson Exemplar format ---
    _OBJECTIVE_INTRO_LINES = (
        "sa pagtatapos ng aralin", "by the end of the lesson",
        "at the end of the lesson", "sa katapusan ng aralin",
    )

    def _line_items(text, skip_intro=False):
        out = []
        for raw in (text or "").splitlines():
            line = raw.strip().lstrip("-•*").strip()
            if not line:
                continue
            if skip_intro and line.lower().startswith(_OBJECTIVE_INTRO_LINES):
                continue
            line = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if line:
                out.append(line)
        return out

    data["le_competencies_raw"] = data["le_competencies"]
    comp_text = data["le_competencies"] or data["competency_description"] or ""
    if data["competency_code"]:
        comp_text = "\n".join(x for x in (comp_text, f"({data['competency_code']})") if x)
    data["le_competencies_text"] = comp_text

    data["le_content_raw"] = data["le_content"]
    data["le_content"] = data["le_content"] or data["lesson_name"] or ""

    data["le_objectives"] = _line_items(data["objectives"], skip_intro=True)
    data["le_objectives_intro"] = (
        LE_LAYOUT.OBJECTIVES_INTRO_TL if _is_tagalog(data.get("subject", ""))
        else LE_LAYOUT.OBJECTIVES_INTRO
    )
    data["le_ai_declaration"] = data["ai_declaration"] or LE_LAYOUT.DEFAULT_AI_DECLARATION
    data["reflection_directions"] = LE_LAYOUT.REFLECTION_DIRECTIONS

    phases = []
    for phase_name, steps in PROCEDURES:
        items = []
        for title, content_key, ann_key in steps:
            items.append({
                "title": title,
                "content": data.get(content_key, "") or "",
                "annotation": data.get(ann_key, "") or "",
                "content_key": content_key,
                "annotation_key": ann_key,
                "content_editable": content_key.startswith("le_"),
            })
        phases.append({"name": phase_name, "steps": items})
    data["le_phases"] = phases
    return data


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# new field -> older column names (newest first) used by previous versions
LEGACY_MAP = {
    "pre_lesson": ["activating_knowledge"],
    "flow_introduce": ["flow_engage", "lesson_purpose"],
    "flow_learn": ["flow_explore", "developing_understanding"],
    "flow_apply": ["flow_experience", "deepening_understanding"],
    "flow_wrapup": ["flow_empathize", "generalizations"],
}
LEGACY_COLS = [c for cols in LEGACY_MAP.values() for c in cols]


@app.route("/save", methods=["POST"])
def save_plan():
    name = request.form.get("name", "").strip()
    if not name:
        name = f"{session.get('grade_level', 'Unknown')} - {session.get('subject', 'Unknown')} - W{session.get('week', '?')}"
    mode = request.form.get("mode", "new")
    loaded_id = session.get("_loaded_plan_id")

    conn = get_connection()
    cursor = conn.cursor()
    now = _now()

    if mode == "update" and loaded_id:
        cursor.execute("SELECT id FROM saved_plans WHERE id = ?", (loaded_id,))
        if cursor.fetchone():
            set_clause = ", ".join(f"{f} = ?" for f in ALL_FIELDS_SQL)
            cursor.execute(
                f"UPDATE saved_plans SET {set_clause}, name = ?, updated_at = ? WHERE id = ?",
                tuple(session.get(k, "") for k in ALL_FIELDS) + (name, now, loaded_id),
            )
        else:
            # Plan was deleted while editing; save as a new one instead.
            cursor.execute(
                f"""INSERT INTO saved_plans ({', '.join(ALL_FIELDS_SQL)}, name, created_at, updated_at)
                    VALUES ({', '.join('?' for _ in ALL_FIELDS)}, ?, ?, ?)""",
                tuple(session.get(k, "") for k in ALL_FIELDS) + (name, now, now),
            )
    else:
        cursor.execute(
            f"""INSERT INTO saved_plans ({', '.join(ALL_FIELDS_SQL)}, name, created_at, updated_at)
                VALUES ({', '.join('?' for _ in ALL_FIELDS)}, ?, ?, ?)""",
            tuple(session.get(k, "") for k in ALL_FIELDS) + (name, now, now),
        )
    conn.commit()
    conn.close()
    for key in ALL_FIELDS:
        session.pop(key, None)
    session.pop("draft_step", None)
    session.pop("_suggest_source", None)
    session.pop("_loaded_plan", None)
    session.pop("_loaded_plan_id", None)
    session.pop("_loaded_plan_name", None)
    session.modified = True
    return redirect(url_for("my_plans"))


@app.route("/my-plans")
def my_plans():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, grade_level, subject, week, term, created_at, updated_at FROM saved_plans ORDER BY updated_at DESC"
    )
    plans = [
        {
            "id": row[0], "name": row[1], "grade_level": row[2],
            "subject": row[3], "week": row[4], "term": row[5],
            "created_at": row[6], "updated_at": row[7],
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return render_template("my_plans.html", plans=plans)


@app.route("/admin/access", methods=["GET", "POST"])
def admin_access():
    if not session.get("_access_admin"):
        return redirect(url_for("index"))
    msg = ""
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create":
            school = request.form.get("school_name", "").strip()
            plan = request.form.get("plan", "school_license")
            kind = request.form.get("kind", "school")
            expires = request.form.get("expires_at", "").strip()
            if school:
                code = _new_access_code()
                conn = get_connection()
                conn.execute(
                    "INSERT INTO school_access (school_name, access_code, plan, kind, created_at, expires_at, active, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                    (school, code, plan, kind, datetime.now().strftime("%Y-%m-%d %H:%M"),
                     expires or None, request.form.get("notes", "").strip()),
                )
                conn.commit()
                conn.close()
                msg = f"Created {kind} code for {school}: {code}"
        elif action == "disable":
            code_id = request.form.get("id", "")
            conn = get_connection()
            conn.execute("UPDATE school_access SET active = 0 WHERE id = ?", (code_id,))
            conn.commit()
            conn.close()
            msg = "Access code disabled."
        elif action == "enable":
            code_id = request.form.get("id", "")
            conn = get_connection()
            conn.execute("UPDATE school_access SET active = 1 WHERE id = ?", (code_id,))
            conn.commit()
            conn.close()
            msg = "Access code re-enabled."
        elif action == "delete":
            code_id = request.form.get("id", "")
            conn = get_connection()
            conn.execute("DELETE FROM school_access WHERE id = ?", (code_id,))
            conn.commit()
            conn.close()
            msg = "Access code deleted."

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, school_name, access_code, plan, kind, created_at, expires_at, active, notes "
        "FROM school_access ORDER BY active DESC, created_at DESC"
    ).fetchall()
    conn.close()
    codes = [
        {
            "id": r[0], "school_name": r[1], "access_code": r[2], "plan": r[3],
            "kind": r[4], "created_at": r[5], "expires_at": r[6], "active": bool(r[7]),
            "notes": r[8],
        }
        for r in rows
    ]
    return render_template("admin_access.html", codes=codes, msg=msg)


def _new_access_code():
    """6-char, human-friendly code (letters + digits, no confusing chars)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        conn = get_connection()
        exists = conn.execute(
            "SELECT COUNT(*) FROM school_access WHERE access_code = ?", (code,)
        ).fetchone()[0]
        conn.close()
        if not exists:
            return code


@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not session.get("_access_admin"):
        return redirect(url_for("index"))
    msg = ""
    if request.method == "POST":
        action = request.form.get("action", "")
        uid = request.form.get("id", "")
        conn = get_connection()
        if action == "activate_monthly":
            _set_paid_until(conn, uid, days=30)
            msg = "Account activated for 1 month."
        elif action == "activate_beta":
            conn.execute(
                "UPDATE users SET status='active', plan='beta', paid_until='' WHERE id = ?",
                (uid,),
            )
            msg = "Account activated as beta tester (no expiry)."
        elif action == "extend_trial":
            trial_end = datetime.now() + timedelta(days=14)
            conn.execute(
                "UPDATE users SET status='trial', trial_end=? WHERE id = ?",
                (trial_end.strftime("%Y-%m-%d"), uid),
            )
            msg = "Trial extended by 14 days."
        elif action == "disable":
            conn.execute("UPDATE users SET status='disabled' WHERE id = ?", (uid,))
            msg = "Account disabled."
        elif action == "enable":
            trial_end = datetime.now() + timedelta(days=14)
            conn.execute(
                "UPDATE users SET status='trial', trial_end=? WHERE id = ?",
                (trial_end.strftime("%Y-%m-%d"), uid),
            )
            msg = "Account re-enabled with a 14-day trial."
        elif action == "delete":
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))
            msg = "Account deleted."
        conn.commit()
        conn.close()

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, email, name, school, status, plan, trial_start, trial_end, "
        "paid_until, created_at, last_login FROM users ORDER BY id DESC"
    ).fetchall()
    conn.close()
    users = [
        {
            "id": r[0], "email": r[1], "name": r[2], "school": r[3],
            "status": r[4], "plan": r[5], "trial_start": r[6], "trial_end": r[7],
            "paid_until": r[8], "created_at": r[9], "last_login": r[10],
        }
        for r in rows
    ]
    return render_template("admin_users.html", users=users, msg=msg)


def _set_paid_until(conn, uid, days):
    end = datetime.now() + timedelta(days=days)
    conn.execute(
        "UPDATE users SET status='active', plan='paid', paid_until=? WHERE id = ?",
        (end.strftime("%Y-%m-%d"), uid),
    )


@app.route("/load/<int:plan_id>")
def load_plan(plan_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {', '.join(ALL_FIELDS_SQL)} FROM saved_plans WHERE id = ?", (plan_id,))
    row = cursor.fetchone()
    legacy = {}
    if row:
        for i, key in enumerate(ALL_FIELDS):
            session[key] = row[i] or ""
        cursor.execute(f"SELECT {', '.join(f'\"{k}\"' for k in LEGACY_COLS)} FROM saved_plans WHERE id = ?", (plan_id,))
        lrow = cursor.fetchone()
        if lrow:
            legacy = dict(zip(LEGACY_COLS, lrow))
    else:
        cursor.execute("SELECT * FROM saved_plans WHERE id = ?", (plan_id,))
        legacy_row = cursor.fetchone()
        if legacy_row:
            legacy_cols = [d[0] for d in cursor.description]
            legacy = dict(zip(legacy_cols, legacy_row))
            for key in ALL_FIELDS:
                session[key] = legacy.get(key, "") or ""
    for new_key, old_keys in LEGACY_MAP.items():
        if not session.get(new_key):
            for old_key in old_keys:
                if legacy.get(old_key):
                    session[new_key] = legacy[old_key]
                    break
    if session.get("reflection") and _LEGACY_REFLECTION_PLACEHOLDER in (session.get("reflection", "") or ""):
        session["reflection"] = ""  # don't restore a stale fill-in-the-blank reflection
    cursor.execute("SELECT name FROM saved_plans WHERE id = ?", (plan_id,))
    name_row = cursor.fetchone()
    conn.close()
    if not row and not legacy:
        return "Plan not found", 404
    session["_suggest_source"] = "|".join([
        session.get("competency_code", ""), session.get("competency_description", ""),
        session.get("subject", ""), session.get("grade_level", ""),
    ])
    session["_loaded_plan"] = True
    session["_loaded_plan_id"] = plan_id
    session["_loaded_plan_name"] = name_row[0] if name_row else ""
    _set_draft_step(6)
    return redirect(url_for("preview"))


@app.route("/delete/<int:plan_id>", methods=["POST"])
def delete_plan(plan_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_plans WHERE id = ?", (plan_id,))
    conn.commit()
    conn.close()
    if session.get("_loaded_plan_id") == plan_id:
        session.pop("_loaded_plan", None)
        session.pop("_loaded_plan_id", None)
        session.pop("_loaded_plan_name", None)
    return redirect(url_for("my_plans"))


@app.route("/update")
def update_page():
    return render_template("update.html", update_url=_get_update_url())


@app.route("/save-update-url", methods=["POST"])
def save_update_url():
    url = request.form.get("url", "").strip()
    if url and urlparse(url).scheme not in ("http", "https"):
        return "Only http/https URLs are allowed", 400
    _set_update_url(url)
    return redirect(url_for("update_page"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    error = None
    if request.method == "POST":
        school_year = request.form.get("school_year", "").strip()
        terms = {}
        parsed = {}
        for t in ("1", "2", "3"):
            start = request.form.get(f"term{t}_start", "").strip()
            end = request.form.get(f"term{t}_end", "").strip()
            if not (start and end):
                error = f"Term {t}: both start and end dates are required."
                break
            try:
                s = datetime.strptime(start, "%Y-%m-%d")
                e = datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                error = f"Term {t}: dates must be valid (YYYY-MM-DD)."
                break
            if e < s:
                error = f"Term {t}: end date is before the start date."
                break
            prev = parsed.get(str(int(t) - 1))
            if prev and s <= prev:
                error = f"Term {t} must start after Term {int(t) - 1} ends."
                break
            parsed[t] = e
            terms[t] = {"start": start, "end": end}
        if not error:
            if not school_year:
                y1 = terms["1"]["start"][:4]
                y2 = terms["3"]["end"][:4]
                school_year = y1 if y1 == y2 else f"{y1}-{y2}"
            entries = {}
            entries_raw = request.form.get("feedback_entries", "").strip()
            if entries_raw:
                try:
                    parsed_entries = json.loads(entries_raw)
                    if isinstance(parsed_entries, dict):
                        entries = {k: v for k, v in parsed_entries.items() if str(v).strip()}
                    else:
                        error = "Field mapping must be a JSON object, e.g. {\"liked\": \"entry.123\"}"
                except Exception:
                    error = "Field mapping must be valid JSON, e.g. {\"liked\": \"entry.123\"}"
            if not error:
                cfg = _load_config()
                cfg["feedback_form_url"] = request.form.get("feedback_form_url", "").strip()
                cfg["feedback_response_url"] = request.form.get("feedback_response_url", "").strip()
                cfg["feedback_entries"] = entries
                _save_config(cfg)
                _set_term_config({"school_year": school_year, "terms": terms})
                return redirect(url_for("settings", saved=1))

    tc = _get_term_config()
    cfg = _load_config()
    return render_template(
        "settings.html",
        tc=tc,
        ranges=_term_ranges(),
        saved=request.args.get("saved"),
        error=error,
        feedback_form_url=(cfg.get("feedback_form_url") or ""),
        feedback_response_url=(cfg.get("feedback_response_url") or ""),
        feedback_entries_json=json.dumps(cfg.get("feedback_entries") or {}),
    )


@app.route("/support")
def support():
    return render_template("support.html")


def _submit_feedback_cloud(name, email, rating, area, liked, problem, suggestions):
    """POST feedback to a configured Google Form response endpoint (hybrid mode).

    Returns (synced_bool_or_None, note). None = not configured (local only).
    """
    cfg = _load_config()
    url = (cfg.get("feedback_response_url") or "").strip()
    entries = cfg.get("feedback_entries") or {}
    if not url:
        return None, ""
    values = {"name": name, "email": email, "rating": rating, "area": area,
              "liked": liked, "problem": problem, "suggestions": suggestions}
    payload = {}
    for field, entry_id in entries.items():
        if entry_id and field in values:
            payload[entry_id] = values[field]
    area_entry = entries.get("area")
    area_val = (area or "Overall").strip()
    if area_entry:
        fixed = {
            "Basic Info", "Competency", "Intentions", "Assessment", "Ways Forward",
            "Preview / Export (PDF/DOCX)", "My Plans", "Manage Competencies",
            "Settings", "Overall",
        }
        payload.pop(area_entry, None)
        if area_val in fixed:
            payload[area_entry] = area_val
        else:
            payload[area_entry] = "__other_option__"
            payload[area_entry + ".other_option_response"] = area_val
    if not payload:
        return False, "Google Form configured but no field mapping set"
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LAMDAG/1.0")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            ok = resp.status in (200, 201, 302)
            return ok, f"Google Form ({resp.status})" if ok else f"Google Form responded {resp.status}"
    except Exception as e:
        return False, f"Not sent (no internet?): {e}"


@app.route("/feedback", methods=["GET"])
def feedback():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, created_at, name, email, rating, area, liked, problem, suggestions, synced, sync_note "
        "FROM feedbacks ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    cfg = _load_config()
    return render_template(
        "feedback.html",
        feedbacks=[
            {"id": r[0], "created_at": r[1], "name": r[2], "email": r[3] or "",
             "rating": r[4], "area": r[5] or "", "liked": r[6], "problem": r[7],
             "suggestions": r[8], "synced": r[9], "sync_note": r[10] or ""}
            for r in rows
        ],
        form_url=(cfg.get("feedback_form_url") or "").strip(),
        sent=request.args.get("sent"),
        error=request.args.get("error"),
    )


@app.route("/feedback/submit", methods=["POST"])
def feedback_submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    try:
        rating = int(request.form.get("rating", "0"))
    except ValueError:
        rating = 0
    rating = max(0, min(5, rating))
    area = request.form.get("area", "").strip()
    liked = request.form.get("liked", "").strip()
    problem = request.form.get("problem", "").strip()
    suggestions = request.form.get("suggestions", "").strip()
    if rating < 1 or not (liked or problem or suggestions):
        return redirect(url_for("feedback", error=1))
    synced, sync_note = _submit_feedback_cloud(
        name, email, rating, area, liked, problem, suggestions)
    if synced is None:
        sync_note = "Saved locally only"
    conn = get_connection()
    conn.execute(
        "INSERT INTO feedbacks (created_at, name, email, rating, area, liked, problem, suggestions, synced, sync_note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, email, rating, area,
         liked, problem, suggestions, 1 if synced else 0, sync_note),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("feedback", sent=1))


@app.route("/feedback/export")
def feedback_export():
    conn = get_connection()
    rows = conn.execute(
        "SELECT created_at, name, email, rating, area, liked, problem, suggestions, synced, sync_note "
        "FROM feedbacks ORDER BY id"
    ).fetchall()
    conn.close()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at", "name", "email", "rating", "area", "liked",
                     "problem", "suggestions", "sent_to_google", "sync_note"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                         "yes" if r[8] else "no", r[9]])
    resp = Response(buf.getvalue().encode("utf-8-sig"), mimetype="text/csv")
    resp.headers["Content-Disposition"] = 'attachment; filename="LAMDAG_feedback.csv"'
    return resp


@app.route("/feedback/delete/<int:fid>", methods=["POST"])
def feedback_delete(fid):
    conn = get_connection()
    conn.execute("DELETE FROM feedbacks WHERE id = ?", (fid,))
    conn.commit()
    conn.close()
    return redirect(url_for("feedback"))


@app.route("/do-update", methods=["POST"])
def do_update():
    source = request.form.get("source", "")
    url = request.form.get("url", "").strip()
    conn = get_connection()
    cursor = conn.cursor()

    if source == "check":
        url = _get_update_url()
        if not url:
            return "No update URL configured. Set one below on this page.", 400
    elif source == "url":
        if not url:
            return "No URL provided", 400

    if source in ("check", "url"):
        if urlparse(url).scheme not in ("http", "https"):
            return "Only http/https URLs are allowed", 400
        try:
            resp = urllib.request.urlopen(url, timeout=30)
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
        except Exception as e:
            return f"Failed to fetch or parse URL: {e}", 400

    elif source == "file":
        file = request.files.get("file")
        if not file:
            return "No file uploaded", 400
        raw = file.read().decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = _parse_csv(raw)
            except Exception as e:
                return f"Failed to parse file (tried JSON and CSV): {e}", 400

    else:
        return "Invalid source", 400

    if not isinstance(data, dict):
        return "Invalid update file: expected an object with 'subjects' and 'competencies'.", 400
    subjects = data.get("subjects") or []
    competencies = data.get("competencies") or []
    if not isinstance(subjects, list) or not isinstance(competencies, list):
        return "Invalid update file: 'subjects' and 'competencies' must be lists.", 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Apply the whole update atomically: if anything fails, nothing changes.
        cursor.execute("DELETE FROM competencies")
        cursor.execute("DELETE FROM subjects")

        for s in subjects:
            if not isinstance(s, dict) or not s.get("code") or not s.get("name"):
                raise ValueError("Each subject needs a 'code' and a 'name'.")
            cursor.execute(
                "INSERT OR IGNORE INTO subjects (code, name, grade_level, sort_order) VALUES (?, ?, ?, ?)",
                (s["code"], s["name"], s.get("grade_level", ""), s.get("sort_order", 0)),
            )

        cursor.execute("SELECT id, code FROM subjects")
        subject_map = {row[1]: row[0] for row in cursor.fetchall()}

        for c in competencies:
            if not isinstance(c, dict) or not c.get("code") or not c.get("description"):
                raise ValueError("Each competency needs a 'code' and a 'description'.")
            sid = subject_map.get(c.get("subject_code"))
            if not sid:
                continue
            cursor.execute(
                "INSERT OR IGNORE INTO competencies (subject_id, term, week, code, description, content_standard, performance_standard) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, c["term"], c.get("week"), c["code"], c["description"], c.get("content_standard", ""), c.get("performance_standard", "")),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Update failed and was rolled back (no data changed): {e}", 400
    conn.close()

    return redirect(url_for("index"))


def _parse_csv(raw):
    lines = raw.strip().splitlines()
    reader = csv.DictReader(lines)
    rows = list(reader)
    subjects_list = []
    competencies = []
    seen_subjects = set()
    for r in rows:
        subj_code = r.get("subject_code", "").strip()
        subj_name = r.get("subject_name", "").strip()
        grade = r.get("grade_level", "").strip()
        if subj_code and subj_code not in seen_subjects:
            seen_subjects.add(subj_code)
            subjects_list.append({
                "code": subj_code,
                "name": subj_name or subj_code,
                "grade_level": grade,
                "sort_order": 0,
            })
        competencies.append({
            "subject_code": subj_code,
            "term": int(r.get("term", 1)),
            "week": int(r.get("week", 0)) if r.get("week") else None,
            "code": r.get("code", "").strip(),
            "description": r.get("description", "").strip(),
            "content_standard": r.get("content_standard", ""),
            "performance_standard": r.get("performance_standard", ""),
        })
    return {"subjects": subjects_list, "competencies": competencies}


def _parse_batch_lines(text, default_week):
    items = []
    skipped = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"[\t|]", line) if p.strip()]
        if len(parts) >= 3 and parts[0].isdigit():
            week = int(parts[0])
            code = parts[1]
            desc = " | ".join(parts[2:])
        elif len(parts) >= 2:
            week = default_week
            code = parts[0]
            desc = " | ".join(parts[1:])
        else:
            week = default_week
            code = parts[0] if parts else ""
            desc = ""
        if code and desc:
            items.append((week, code, desc))
        else:
            skipped += 1
    return items, skipped


@app.route("/manage")
def manage_competencies():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT grade_level FROM subjects GROUP BY grade_level ORDER BY MIN(sort_order)")
    grades = [row[0] for row in cursor.fetchall()]
    conn.close()

    grade = request.args.get("grade", session.get("grade_level", ""))
    subject = request.args.get("subject", session.get("subject", ""))
    term = request.args.get("term", "1")
    week_raw = request.args.get("week", "")
    week = int(week_raw) if week_raw.isdigit() else ""
    search = request.args.get("search", "").strip()
    page = max(1, request.args.get("page", 1, type=int))

    weeks = []
    competencies = []
    total = 0
    total_pages = 1
    if grade and subject:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT DISTINCT c.week FROM competencies c
               JOIN subjects s ON c.subject_id = s.id
               WHERE s.grade_level = ? AND s.name = ? AND c.term = ?
               ORDER BY c.week""",
            (grade, subject, term),
        )
        weeks = [r[0] for r in cursor.fetchall() if r[0] is not None]

        base_sql = """FROM competencies c
                      JOIN subjects s ON c.subject_id = s.id
                      WHERE s.grade_level = ? AND s.name = ? AND c.term = ?"""
        params = [grade, subject, term]
        if week != "":
            base_sql += " AND c.week = ?"
            params.append(week)
        if search:
            base_sql += """ AND (c.code LIKE ? OR c.description LIKE ?
                                 OR c.content_standard LIKE ? OR c.performance_standard LIKE ?)"""
            like = f"%{search}%"
            params.extend([like, like, like, like])

        per_page = 25
        cursor.execute("SELECT COUNT(*) " + base_sql, params)
        total = cursor.fetchone()[0]
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, total_pages)

        cursor.execute(
            """SELECT c.id, c.term, c.week, c.code, c.description,
                      c.content_standard, c.performance_standard """
            + base_sql + " ORDER BY c.week, c.code LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page],
        )
        competencies = [
            {
                "id": r[0], "term": r[1], "week": r[2], "code": r[3],
                "description": r[4], "content_standard": r[5] or "",
                "performance_standard": r[6] or "",
            }
            for r in cursor.fetchall()
        ]
        conn.close()

    return render_template("manage.html", grades=grades, competencies=competencies,
                           grade=grade, subject=subject, term=term, week=week,
                           search=search, page=page, total=total,
                           total_pages=total_pages, weeks=weeks)


@app.route("/manage/batch", methods=["POST"])
def manage_batch():
    grade = request.form.get("grade", "")
    subject = request.form.get("subject", "")
    term = int(request.form.get("term", 1))
    default_week = int(request.form.get("default_week", 1))
    lines = request.form.get("lines", "")

    if not (grade and subject and lines.strip()):
        return "Grade, subject, and at least one line are required.", 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM subjects WHERE grade_level = ? AND name = ?", (grade, subject))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "Subject not found", 400
    subject_id = row[0]

    added = 0
    skipped = 0
    items, skipped = _parse_batch_lines(lines, default_week)
    for week, code, desc in items:
        cursor.execute(
            """INSERT OR IGNORE INTO competencies
               (subject_id, term, week, code, description, content_standard, performance_standard)
               VALUES (?, ?, ?, ?, ?, '', '')""",
            (subject_id, term, week, code, desc),
        )
        added += cursor.rowcount
    conn.commit()
    conn.close()
    return redirect(url_for(
        "manage_competencies", grade=grade, subject=subject, term=term,
        added=added, skipped=skipped,
    ))


@app.route("/manage/export")
def manage_export():
    grade = request.args.get("grade", "")
    subject = request.args.get("subject", "")
    term = request.args.get("term", "1")
    if not (grade and subject):
        return redirect(url_for("manage_competencies"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT c.week, c.code, c.description, c.content_standard, c.performance_standard
           FROM competencies c JOIN subjects s ON c.subject_id = s.id
           WHERE s.grade_level = ? AND s.name = ? AND c.term = ?
           ORDER BY c.week, c.code""",
        (grade, subject, term),
    )
    rows = cursor.fetchall()
    conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["grade", "subject", "term", "week", "code", "description",
                     "content_standard", "performance_standard"])
    for r in rows:
        writer.writerow([grade, subject, term, r[0], r[1], r[2], r[3] or "", r[4] or ""])
    buf.seek(0)
    filename = f"{grade}_{subject}_term{term}_competencies.csv".replace(" ", "_")
    return send_file(io.BytesIO(buf.getvalue().encode("utf-8-sig")),
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name=filename)


@app.route("/manage/import", methods=["POST"])
def manage_import():
    grade = request.form.get("grade", "")
    subject = request.form.get("subject", "")
    term = int(request.form.get("term", 1))
    f = request.files.get("file")
    if not (grade and subject and f):
        return "Grade, subject, and a CSV file are required.", 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM subjects WHERE grade_level = ? AND name = ?", (grade, subject))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "Subject not found", 400
    subject_id = row[0]

    raw = f.read().decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(raw))
    header = [h.strip().lower() for h in next(reader, [])]

    def col(name):
        try:
            return header.index(name)
        except ValueError:
            return None

    wi, ci, di, csi, psi = (col("week"), col("code"), col("description"),
                            col("content_standard"), col("performance_standard"))
    if ci is None or di is None:
        conn.close()
        return "CSV must have at least 'code' and 'description' columns.", 400

    def get(idx, r):
        return r[idx].strip() if idx is not None and idx < len(r) else ""

    added = 0
    for r in reader:
        if not r or not r[0].strip():
            continue
        wk = get(wi, r)
        week = int(wk) if wk.isdigit() else 0
        code = get(ci, r)
        desc = get(di, r)
        if not code or not desc:
            continue
        cursor.execute(
            """INSERT OR IGNORE INTO competencies
               (subject_id, term, week, code, description, content_standard, performance_standard)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (subject_id, term, week, code, desc, get(csi, r), get(psi, r)),
        )
        added += cursor.rowcount
    conn.commit()
    conn.close()
    return redirect(url_for("manage_competencies", grade=grade, subject=subject, term=term))


@app.route("/manage/add", methods=["POST"])
def manage_add():
    grade = request.form.get("grade", "")
    subject = request.form.get("subject", "")
    term = int(request.form.get("term", 1))
    week_raw = (request.form.get("week") or "").strip()
    week = int(week_raw) if week_raw.isdigit() else 0
    code = request.form.get("code", "").strip()
    description = request.form.get("description", "").strip()
    content_standard = request.form.get("content_standard", "").strip()
    performance_standard = request.form.get("performance_standard", "").strip()

    if not (grade and subject and code and description):
        return "Grade, subject, code, and description are required.", 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM subjects WHERE grade_level = ? AND name = ?", (grade, subject))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "Subject not found", 400
    subject_id = row[0]
    cursor.execute(
        """INSERT OR IGNORE INTO competencies
           (subject_id, term, week, code, description, content_standard, performance_standard)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (subject_id, term, week, code, description, content_standard, performance_standard),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("manage_competencies", grade=grade, subject=subject, term=term))


@app.route("/manage/update/<int:cid>", methods=["POST"])
def manage_update(cid):
    term = int(request.form.get("term", 1))
    week_raw = (request.form.get("week") or "").strip()
    week = int(week_raw) if week_raw.isdigit() else 0
    code = request.form.get("code", "").strip()
    description = request.form.get("description", "").strip()
    content_standard = request.form.get("content_standard", "").strip()
    performance_standard = request.form.get("performance_standard", "").strip()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE competencies
           SET term = ?, week = ?, code = ?, description = ?,
               content_standard = ?, performance_standard = ?
           WHERE id = ?""",
        (term, week, code, description, content_standard, performance_standard, cid),
    )
    conn.commit()
    conn.close()
    grade = request.form.get("grade", "")
    subject = request.form.get("subject", "")
    return redirect(url_for("manage_competencies", grade=grade, subject=subject, term=term))


@app.route("/manage/delete/<int:cid>", methods=["POST"])
def manage_delete(cid):
    grade = request.form.get("grade", "")
    subject = request.form.get("subject", "")
    term = request.form.get("term", "1")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM competencies WHERE id = ?", (cid,))
    conn.commit()
    conn.close()
    return redirect(url_for("manage_competencies", grade=grade, subject=subject, term=term))


def _bow_subject(grade, subject, term=None):
    """All-term (or single-term) rows for one subject."""
    conn = get_connection()
    cursor = conn.cursor()
    sql = """SELECT c.term, c.week, c.code, c.description
             FROM competencies c JOIN subjects s ON c.subject_id = s.id
             WHERE s.grade_level = ? AND s.name = ?"""
    params = [grade, subject]
    if term:
        sql += " AND c.term = ?"
        params.append(int(term))
    sql += " ORDER BY c.term, c.week, c.code"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    result = [{
        "term": term, "week": week, "code": code, "description": description,
    } for term, week, code, description in rows]

    # mark first row of each (term) and (term, week) group so the template can
    # rowspan-merge; rows are already ordered by term, week, code.
    prev_term = prev_key = None
    term_counts = {}
    week_counts = {}
    for r in result:
        r["term_show"] = r["term"] != prev_term
        key = (r["term"], r["week"])
        r["week_show"] = key != prev_key
        term_counts[r["term"]] = term_counts.get(r["term"], 0) + 1
        week_counts[key] = week_counts.get(key, 0) + 1
        prev_term, prev_key = r["term"], key
    for r in result:
        r["term_count"] = term_counts[r["term"]]
        r["week_count"] = week_counts[(r["term"], r["week"])]
    return result


def _bow_subjects(grade):
    """Every subject for a grade with its full BoW rows, ordered by grouping/name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT s.name, s.grouping
           FROM subjects s
           WHERE s.grade_level = ? AND EXISTS (
               SELECT 1 FROM competencies c WHERE c.subject_id = s.id
           )
           ORDER BY s.grouping, s.name""",
        (grade,),
    )
    pairs = cursor.fetchall()
    conn.close()

    subjects = []
    for name, grouping in pairs:
        rows = _bow_subject(grade, name)
        pdf = find_bow_pdf(grade, name)
        subjects.append({
            "name": name,
            "grouping": grouping or "",
            "rows": rows,
            "total": len(rows),
            "terms": sorted({r["term"] for r in rows}),
            "weeks": len({r["week"] for r in rows if r["week"] is not None}),
            "pdf_name": os.path.basename(pdf) if pdf else None,
            "extras": [{"name": os.path.basename(p)} for p in find_bow_extras(grade, name)],
        })
    return subjects


@app.route("/bow")
def bow():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT grade_level FROM subjects GROUP BY grade_level ORDER BY MIN(sort_order)")
    grades = [row[0] for row in cursor.fetchall()]
    conn.close()

    grade = request.args.get("grade", session.get("grade_level", ""))

    subjects = []
    grand_total = 0
    if grade:
        subjects = _bow_subjects(grade)
        grand_total = sum(s["total"] for s in subjects)

    return render_template(
        "bow.html",
        grades=grades, grade=grade, subjects=subjects,
        grand_total=grand_total,
    )


@app.route("/bow/export/docx")
def bow_export_docx():
    blocked = _trial_export_blocked()
    if blocked:
        return blocked
    grade = request.args.get("grade", "")
    subject = request.args.get("subject", "")
    term = request.args.get("term", "")
    if not (grade and subject):
        return redirect(url_for("bow"))

    rows = _bow_subject(grade, subject, term or None)
    division = session.get("division", "")
    school = session.get("school", "")
    data = {
        "region": session.get("region", ""),
        "letterhead_division": f"SCHOOLS DIVISION OF {division.upper()}" if division else "",
        "letterhead_school": school.upper() if school else "",
        "school_year": _get_term_config().get("school_year", ""),
        "subject": subject,
        "grade_level": grade,
        "total": len(rows),
        "rows": rows,
    }

    safe_grade = _safe_filename_component(grade)
    safe_subject = _safe_filename_component(subject)
    filename = f"BoW_{safe_grade}_{safe_subject}"
    if term:
        filename += f"_Term{term}"
    filename += ".docx"
    output_path = os.path.join(DESKTOP, filename)
    generate_bow_docx(data, output_path, watermark=_is_trial_user())
    _record_trial_export()
    return send_file(output_path, as_attachment=True, download_name=filename)


@app.route("/bow/export/csv")
def bow_export_csv():
    blocked = _trial_export_blocked()
    if blocked:
        return blocked
    grade = request.args.get("grade", "")
    subject = request.args.get("subject", "")
    term = request.args.get("term", "")
    if not (grade and subject):
        return redirect(url_for("bow"))

    rows = _bow_subject(grade, subject, term or None)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["grade", "subject", "term", "week", "code", "description"])
    for c in rows:
        writer.writerow([grade, subject, c["term"],
                         c["week"] if c["week"] is not None else "",
                         c["code"], c["description"]])
    buf.seek(0)
    safe_grade = _safe_filename_component(grade)
    safe_subject = _safe_filename_component(subject)
    filename = f"BoW_{safe_grade}_{safe_subject}"
    if term:
        filename += f"_Term{term}"
    filename += ".csv"
    _record_trial_export()
    return send_file(io.BytesIO(buf.getvalue().encode("utf-8-sig")),
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name=filename)


@app.route("/bow/export/pdf")
def bow_export_pdf():
    blocked = _trial_export_blocked()
    if blocked:
        return blocked
    grade = request.args.get("grade", "")
    subject = request.args.get("subject", "")
    fname = request.args.get("file", "")
    if not (grade and subject):
        return redirect(url_for("bow"))
    if fname:
        for p in find_bow_extras(grade, subject):
            if os.path.basename(p) == fname:
                _record_trial_export()
                return send_file(p, mimetype="application/pdf", as_attachment=True,
                                 download_name=fname)
        return redirect(url_for("bow"))
    path = find_bow_pdf(grade, subject)
    if not path:
        return redirect(url_for("bow"))
    filename = os.path.basename(path)
    _record_trial_export()
    return send_file(path, mimetype="application/pdf", as_attachment=True,
                     download_name=filename)


if __name__ == "__main__":
    from database.init_db import get_connection, init_database, seed_data
    import socket
    import threading
    import webbrowser

    def _get_lan_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return ""
        finally:
            s.close()

    def _ensure_cert(lan_ip):
        cert_file = os.path.join(DATA_DIR, "cert.pem")
        key_file = os.path.join(DATA_DIR, "key.pem")
        if os.path.exists(cert_file) and os.path.exists(key_file):
            return cert_file, key_file
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime
            import ipaddress
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            names = [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            if lan_ip:
                try:
                    names.append(x509.IPAddress(ipaddress.ip_address(lan_ip)))
                except ValueError:
                    pass
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "LAMDAG")])
            cert = (
                x509.CertificateBuilder()
                .subject_name(name).issuer_name(name)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
                .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
                .add_extension(x509.SubjectAlternativeName(names), critical=False)
                .sign(key, hashes.SHA256())
            )
            with open(cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open(key_file, "wb") as f:
                f.write(key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                ))
            return cert_file, key_file
        except Exception:
            return None, None

    init_database()
    _conn = get_connection()
    _fresh = _conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == 0
    _conn.close()
    if _fresh:
        seed_data()

    # Pick a free port (default 5000, fall back if already in use).
    _port = 5000
    for _p in range(5000, 5010):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", _p))
                _port = _p
                break
            except OSError:
                continue

    def open_browser():
        import time
        time.sleep(1.2)
        webbrowser.open(f"http://127.0.0.1:{_port}/")

    threading.Timer(1.2, open_browser).start()

    _lan_ip = _get_lan_ip()

    # LAN / phone access is OFF by default. Set LAMDAG_LAN=1 (e.g. in run.bat)
    # to expose the app to other devices on the same network.
    _use_lan = os.environ.get("LAMDAG_LAN", "").strip().lower() in ("1", "true", "yes", "on")

    print(f"\nLAMDAG is running.")
    print(f"  Local:   http://127.0.0.1:{_port}/")
    if not _use_lan:
        print("  (LAN/phone access disabled. Set LAMDAG_LAN=1 to enable it.)\n")
        try:
            app.run(host="127.0.0.1", debug=False, port=_port, use_reloader=False)
        except Exception:
            import traceback
            try:
                log_path = os.path.join(DATA_DIR, "error.log")
                with open(log_path, "w", encoding="utf-8") as f:
                    traceback.print_exc(file=f)
            except Exception:
                pass
            raise

    if not _lan_ip:
        print("  (Could not detect LAN IP - phone access unavailable.)\n")
        try:
            app.run(host="0.0.0.0", debug=False, port=_port, use_reloader=False)
        except Exception:
            import traceback
            try:
                log_path = os.path.join(DATA_DIR, "error.log")
                with open(log_path, "w", encoding="utf-8") as f:
                    traceback.print_exc(file=f)
            except Exception:
                pass
            raise

    _https_port = _port + 1

    def _run_https():
        cert_file, key_file = _ensure_cert(_lan_ip)
        if not (cert_file and key_file):
            print("  (HTTPS on phone skipped: could not create certificate)")
            return
        try:
            app.run(
                host="0.0.0.0", port=_https_port,
                ssl_context=(cert_file, key_file),
                debug=False, use_reloader=False,
            )
        except Exception:
            pass

    threading.Thread(target=_run_https, daemon=True).start()
    print(f"  On phone (same Wi-Fi): http://{_lan_ip}:{_port}/")
    print(f"  Phone HTTPS (if browser forces https): https://{_lan_ip}:{_https_port}/")
    print("  (First time: phone will warn about the certificate -> Advanced -> Proceed)\n")
    try:
        app.run(host="0.0.0.0", debug=False, port=_port, use_reloader=False)
    except Exception:
        import traceback
        try:
            log_path = os.path.join(DATA_DIR, "error.log")
            with open(log_path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise
