# DADA'S NUMEROLOGY — Backend

FastAPI service behind the DADA'S NUMEROLOGY apps. A Chaldean numerology engine for
**Name**, **Mobile** and **Vehicle** numbers, with email-OTP + Google authentication,
PDF reports, and an admin API where every meaning is editable without a redeploy.

| Repo | |
| --- | --- |
| **Backend** (this repo) | https://github.com/ulmind-com/DADA-NAMEROLOGY-Backend |
| Mobile app (Expo) | https://github.com/ulmind-com/DADA-NAMEROLOGY-MobileApp |
| Admin panel (React) | https://github.com/ulmind-com/DADA-NAMEROLOGY-Admin |

---

## Run it

```bash
uv sync --extra dev
cp -n .env.example .env          # then fill in SECRET_KEY etc.
uv run uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Seeded super-admin: `admin@dadanumerology.com` / `Admin@12345` (change in `.env`)

With `SMTP_HOST` empty the signup OTP is returned in the API response instead of being
emailed, so the whole flow can be exercised with no mail credentials.

```bash
uv run pytest        # 42 tests
uv run ruff check .  # lint
```

---

## Verified against the client's spreadsheet

`docs/DADAS NAMEROLOGY.xlsx` is the source of truth. Both worked examples in it
reproduce exactly, and are locked in as tests:

| Sheet value | Engine output |
| --- | --- |
| `Pankaj Kabiraj` → Compound 28, Total 1 | Pankaj 18 + Kabiraj 10 = **28 → 1** ✓ |
| 28 → *"start their projects again and again to get success"* | same text ✓ |
| `9531199355` → Compounding 50, Total 5 | **50 → 5** ✓ |
| Grid `9:5 5:3 3:1 1:1 1:9 9:9 9:3 3:5 5:5` | identical nine pairs ✓ |

See `docs/NUMEROLOGY.md` for how the maths works and how to hand over new rules.

---

## Layout

```
app/
├── main.py              app factory, error handlers, startup (tables, seed, rules)
├── core/
│   ├── config.py        pydantic-settings, reads .env
│   └── security.py      password + OTP hashing, JWT issue/verify
├── db/
│   ├── session.py       engine + session factory
│   └── seed.py          super-admin and default settings on first boot
├── models/models.py     User · OtpCode · RefreshToken · Report · Rule · AppSetting · AuditLog
├── schemas/             request/response models
├── services/
│   ├── otp.py           issue + verify, rate limited, attempt capped
│   ├── email.py         branded HTML mail (logs to console when SMTP is unset)
│   ├── google.py        Google ID-token verification
│   ├── pdf.py           branded reportlab reports
│   └── settings_store.py
├── api/
│   ├── deps.py          current_user / optional_user / admin_user / superadmin_user
│   └── v1/              auth · numerology · reports · admin · meta
└── numerology/
    ├── chaldean.py      letter values, reduction, radical / destiny / kua
    ├── name.py          quick + full reports, corrections, new born
    ├── mobile.py        compounding, total, pair grid, scoring, comparison
    ├── vehicle.py       plate parsing, running-number analysis, suggestions
    ├── rules.py         rule store, DB overrides layered on the JSON
    └── data/*.json      the editable rule set
docs/
├── API.md               all 42 endpoints with worked examples
├── NUMEROLOGY.md        how the engine works + how to supply rules
└── DADAS NAMEROLOGY.xlsx
```

---

## Auth model

- **Signup is three calls**: `/auth/signup/start` → `/auth/signup/verify` →
  `/auth/signup/complete`. Verifying the OTP returns a short-lived `signup_token`; the
  account is only created at step 3, so abandoned signups leave nothing behind.
- OTPs are HMAC-hashed, expire in 10 minutes, allow 5 attempts and enforce a 45-second
  resend cooldown.
- Access tokens last 1 day; refresh tokens last 60 days and **rotate** on every use, so
  a replayed refresh token is rejected.
- `/auth/forgot/*` mirrors signup and revokes every existing session on reset.

## Free vs premium

`/numerology/name/quick`, `/mobile`, `/vehicle` and `/newborn` are free and work
signed-out (anonymous results are computed but not stored).

`/numerology/name/full` requires a signed-in user and consumes the quota set by the
`free_full_reports` app setting. Over quota it returns **402**, which the app uses to
open the upgrade screen.

## Editable rules

Every meaning lives in JSON under `app/numerology/data/`:

| File | Contents |
| --- | --- |
| `root_profiles.json` | Numbers 1–9: planet, colours, gem, lucky days, friendly/enemy numbers, traits, careers |
| `compound_meanings.json` | Compound numbers 1–52: title, rating, description |
| `pair_meanings.json` | All 81 digit pairs used by the mobile TOTAL GRID |

`GET /admin/rules/{kind}` returns the merged set, `PUT /admin/rules` writes an override,
`DELETE /admin/rules/{kind}/{key}` reverts to the bundled default. Each write reloads the
store, so changes are live on the **next request** — no restart, no redeploy.

---

## Database

The API runs on **SQLAlchemy 2.0** — SQLite locally, PostgreSQL in production via
`DATABASE_URL`. Tables are created on startup; Alembic is installed for when the schema
needs versioned migrations.

> **Note:** a MongoDB Atlas cluster has been provisioned for this project. It is *not*
> currently used — MongoDB is a document store and this schema is relational (users,
> reports, rules, refresh tokens, audit log, with joins and aggregations behind the
> admin dashboard). To go live, either point `DATABASE_URL` at a managed Postgres, or
> ask for the data layer to be ported to MongoDB.

---

## Deploying

1. Set a real `SECRET_KEY` (`openssl rand -hex 32`), a Postgres `DATABASE_URL`, SMTP
   credentials and `GOOGLE_CLIENT_IDS_RAW`.
2. Set `OTP_DEV_ECHO=false` and `DEBUG=false`.
3. Narrow `CORS_ORIGINS_RAW` to the admin panel's domain.
4. Change `ADMIN_PASSWORD`, or delete the seeded admin once a real one exists.
5. Run behind a process manager:
   `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`

**Never commit `.env`.** It is gitignored; `.env.example` documents every key.
