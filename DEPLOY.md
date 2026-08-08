# I-DEPLOY ang LAMDAG sa Internet (Render)

Ang LAMDAG naa na sa ready-deploy nga format — Docker + WSGI. Sunda kini nga
mga lakang aron ma-online kini (free tier).

## Unsa ang gitag-an nga files

| File | Katuyoan |
|---|---|
| `wsgi.py` | Entry point para gunicorn (dili ang `__main__` block sa app.py) |
| `Dockerfile` | Nag-install og Pango/Cairo (WeasyPrint PDF) ug fonts |
| `render.yaml` | Render Blueprint config |
| `.dockerignore` | Mga file nga dili i-bundle sa image |

## Giunsa ang deploy (Render)

1. **Create account** sa https://render.com (Google sign-in pwede).
2. **New → Blueprint** → i-connect ang imong GitHub repo nga naay kining files.
   - Kon wala pay GitHub, i-push una ang folder sa usa ka repository
     (uban ang `wsgi.py`, `Dockerfile`, `render.yaml`, `app.py`, `database/`,
     `generators/`, `templates/`, `static/`, `suggestions.py`, `requirements.txt`,
     `references/`).
3. Render mo-read sa `render.yaml` ug mo-create og web service.
4. **Free tier** — mubag-o ang RAM (512MB). Kon ma-Out-of-Memory, i-subscribe
   sa Starter ($7/mo) o i-remove ang `references/` sa `.dockerignore` ug
   i-redeploy.
5. Human ma-deploy, Render mohatag og URL sama sa
   `https://lamdag.onrender.com`. Ato nang ma-share sa mga teachers.

> **Note:** Sa free tier, ang MySQL/Postgres kay separate na bayad, mao nga
> ang app mogamit sa bundled SQLite database (`database/matatag_cg.db`).
> Ang saved plans ug feedbacks maluwas ra sa ephemeral disk — pero i-reset
> kini kon ma-restart ang server (free tier). Kon nanginahanglan og
> permanente nga storage, i-add ang Render Disk o Postgres ug i-update ang
> `database/init_db.py` nga mo-connect sa env var nga database URL.

## Railway (optional)

- Railway automatic nga mo-read sa `Dockerfile`. I-push lang ang repo ug
  i-create og "New Project → Deploy from GitHub". Railway mo-detect sa
  Dockerfile. Siguraduha nga mo-set og `PORT` (Railway auto-set ni).
- Ang command gamiton: `gunicorn wsgi:app --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 120`

## Local nga test (aron masigurado nga dili mabungkag)

```bash
# 1. I-verify nga modagan ang app (Windows, gamit ang venv)
.venv\Scripts\python.exe -c "import wsgi; print('OK')"

# 2. I-verify nga modagan ang PDF generators (walay Windows Fonts)
.venv\Scripts\python.exe -c "from generators import ilaw_pdf, exemplar_pdf; print('PDF OK')"
```

## Troubleshooting

| Problema | Solusyon |
|---|---|
| 512MB RAM sa free tier | I-remove `references/` sa Docker image o i-upgrade |
| PDF walay output | Siguraduha nga na-install ang `fonts-dejavu` / `fonts-liberation` sa Dockerfile (naa na) |
| Session mawala | Free tier ephemeral disk — i-add Render Disk alang sa permanente nga session |
| BOW PDF button wala | Naa ra `references/` sa image. Kon wala, ma-hide ang button |

Kung naay sayop sa `app.py` nga mahitabo sa Linux environment, i-check ang
`error.log` (kay Render mo-log sa stdout/stderr sa app).
