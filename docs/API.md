# API reference

Base URL: `/api/v1` · Interactive docs: `/docs` · Auth: `Authorization: Bearer <access_token>`

45 endpoints.

Errors always come back as `{ "error": true, "message": "...", "status": <code> }` —
`message` is written for humans and can be shown directly in the UI.

## Meta

Public. The app calls `/config` on every launch.

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/config` | Public runtime config the mobile app reads on launch |
| `GET` | `/health` | Health |

## Authentication

Signup is three steps; everything else is a single call.

| Method | Path | What it does |
| --- | --- | --- |
| `POST` | `/auth/forgot/reset` | Password reset - set the new password |
| `POST` | `/auth/forgot/start` | Password reset - send OTP |
| `POST` | `/auth/forgot/verify` | Password reset - verify OTP |
| `POST` | `/auth/google` | Sign in / sign up with Google |
| `POST` | `/auth/login` | Email + password sign in |
| `POST` | `/auth/logout` | Revoke the current refresh token |
| `GET` | `/auth/me` | The signed-in user |
| `DELETE` | `/auth/me` | Delete my account |
| `PATCH` | `/auth/me` | Update profile details |
| `POST` | `/auth/me/avatar` | Upload a profile photo |
| `DELETE` | `/auth/me/avatar` | Remove the profile photo |
| `POST` | `/auth/me/password` | Change password |
| `POST` | `/auth/refresh` | Exchange a refresh token for a new session |
| `POST` | `/auth/signup/complete` | Step 3 - name, phone, password |
| `POST` | `/auth/signup/resend` | Resend the signup OTP |
| `POST` | `/auth/signup/start` | Step 1 - send OTP to email |
| `POST` | `/auth/signup/verify` | Step 2 - verify the 6-digit OTP |

## Numerology

`/name/full` needs a signed-in user; the rest work signed-out (results are just not saved).

| Method | Path | What it does |
| --- | --- | --- |
| `POST` | `/numerology/mobile` | Mobile number analysis + TOTAL GRID |
| `POST` | `/numerology/mobile/compare` | Check / choose a new number |
| `POST` | `/numerology/name/corrections` | Suggested spelling corrections |
| `POST` | `/numerology/name/full` | Detailed name report |
| `POST` | `/numerology/name/quick` | Free name result |
| `POST` | `/numerology/newborn` | New born name guidance |
| `GET` | `/numerology/reference/compounds` | All compound number meanings |
| `GET` | `/numerology/reference/numbers` | All 1-9 planet profiles |
| `GET` | `/numerology/reference/pairs` | All 81 pair meanings used by the TOTAL GRID |
| `POST` | `/numerology/vehicle` | Vehicle registration analysis |
| `POST` | `/numerology/vehicle/suggest` | Best running numbers for a plate |

## Reports

A user's own saved readings. All require a bearer token.

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/reports` | My reports (paginated) |
| `GET` | `/reports/{report_id}` | Full stored report |
| `DELETE` | `/reports/{report_id}` | Delete a saved report |
| `GET` | `/reports/{report_id}/pdf` | Download report as PDF |
| `POST` | `/reports/{report_id}/share` | Get a shareable PDF link |

## Public sharing

No sign-in — access is granted by a signed token in the query string.

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/public/reports/{report_id}` | Open a shared report (no sign-in needed) |

## Admin

Requires `admin` or `superadmin`. Rows marked ★ are super-admin only.

| Method | Path | What it does |
| --- | --- | --- |
| `POST` | `/admin/admins` ★ | Create an admin account |
| `GET` | `/admin/audit` | Admin action log |
| `POST` | `/admin/broadcast` ★ | Email all users |
| `GET` | `/admin/reports` | Every report, filterable |
| `GET` | `/admin/reports/{report_id}` | One report with its full engine output |
| `GET` | `/admin/reports/{report_id}/pdf` | Render any report as a PDF |
| `PUT` | `/admin/rules` | Create or update one rule entry |
| `GET` | `/admin/rules/{kind}` | compound_meanings | root_profiles | pair_meanings |
| `DELETE` | `/admin/rules/{kind}/{key}` | Revert one rule to the bundled default |
| `GET` | `/admin/settings` | All app settings |
| `PUT` | `/admin/settings` | Update one app setting |
| `GET` | `/admin/stats` | Dashboard metrics |
| `GET` | `/admin/users` | List / search users |
| `GET` | `/admin/users/{user_id}` | One user with their report history |
| `PATCH` | `/admin/users/{user_id}` | Update a user (premium, active, role) |
| `DELETE` | `/admin/users/{user_id}` ★ | Delete a user |

---

## Worked examples

### Signing up

```bash
# 1 - send the code (in dev the response contains dev_otp)
curl -X POST localhost:8000/api/v1/auth/signup/start \
  -H 'Content-Type: application/json' \
  -d '{"email":"riya@example.com"}'
# -> {"email":"riya@example.com","expires_in":600,"resend_in":45,"dev_otp":"481902"}

# 2 - verify it, receive a short-lived signup token
curl -X POST localhost:8000/api/v1/auth/signup/verify \
  -H 'Content-Type: application/json' \
  -d '{"email":"riya@example.com","code":"481902"}'
# -> {"signup_token":"eyJ…","email":"riya@example.com","expires_in":1200}

# 3 - create the account and get a session
curl -X POST localhost:8000/api/v1/auth/signup/complete \
  -H 'Content-Type: application/json' \
  -d '{"signup_token":"eyJ…","full_name":"Riya Sen","phone":"9531199355",
       "password":"Riya12345","dob":"1995-08-15"}'
# -> {"access_token":"…","refresh_token":"…","expires_in":86400,"user":{…}}
```

The account does not exist until step 3 succeeds, so abandoned signups leave no trace.

### A free name reading

```bash
curl -X POST localhost:8000/api/v1/numerology/name/quick \
  -H 'Content-Type: application/json' \
  -d '{"name":"Pankaj Kabiraj"}'
```

```jsonc
{
  "report_id": null,          // null when signed out - nothing is stored
  "saved": false,
  "tier": "free",
  "result": {
    "normalized": "PANKAJ KABIRAJ",
    "compound": 28,
    "total": 1,
    "chain": [28, 10, 1],
    "title": "The Trusting Lamb",
    "rating": "caution",
    "description": "A number full of contradictions…",
    "suggest": "Your Name is not perfectly aligned. It would be advisable to make the necessary corrections.",
    "needs_correction": true,
    "words": [
      { "word": "PANKAJ",  "compound": 18, "root": 9 },
      { "word": "KABIRAJ", "compound": 10, "root": 1 }
    ]
  }
}
```

Send a bearer token and the reading is saved, so `report_id` comes back populated and
`GET /reports/{id}/pdf` will render it.

### A mobile number

```bash
curl -X POST localhost:8000/api/v1/numerology/mobile \
  -H 'Content-Type: application/json' \
  -d '{"number":"9531199355","dob":"1995-08-15"}'
```

```jsonc
{
  "result": {
    "formatted": "95311 99355",
    "compound": 50,
    "total": 5,
    "score": 100,
    "verdict": { "level": "excellent", "label": "Excellent Number", "color": "#0E8F5E", "note": "…" },
    "grid": [
      { "pair": "9:5", "planets": "Mars + Mercury", "rating": "good",
        "label": "Good", "color": "#1E9E6A", "score": 2, "impact": "Mars with Mercury — …" }
      // … one entry per consecutive digit pair
    ],
    "grid_summary": { "good": 8, "average": 1, "bad": 0, "total_pairs": 9 },
    "owner": { "radical": 6, "destiny": 2, "match": { "label": "Neutral", "note": "…" } },
    "recommendations": ["…"]
  }
}
```

`+91` and a leading `0` are stripped automatically. A `0` inside the number has no
planet, so it is reported as an amplifier of the digit beside it.

### Sharing a report

```bash
curl -X POST localhost:8000/api/v1/reports/$REPORT_ID/share \
  -H "Authorization: Bearer $TOKEN"
```

```jsonc
{
  "url": "http://localhost:8000/api/v1/public/reports/82c534…?t=eyJhbGciOi…",
  "cdn_url": "https://res.cloudinary.com/…/raw/upload/…/82c534….pdf",
  "source": "api",       // "cloudinary" once PDF delivery is enabled on the account
  "cached": false
}
```

`url` opens for anyone, no sign-in — paste it into WhatsApp. The token is bound to that
one report and cannot be reused for another. The PDF is also archived to Cloudinary
(`cdn_url`); see the backend README for why the CDN link is not handed out by default.

### Uploading a profile photo

```bash
curl -X POST localhost:8000/api/v1/auth/me/avatar \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@me.jpg;type=image/jpeg"
```

Returns the updated user with `avatar_url`. JPG, PNG, WEBP or HEIC, up to 5 MB.
`DELETE /auth/me/avatar` removes it. With Cloudinary unconfigured both return **503**
and the app falls back to the user's initial.

### Editing a meaning from the admin panel

```bash
curl -X PUT localhost:8000/api/v1/admin/rules \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"kind":"compound_meanings","key":"28",
       "data":{"short":"Client-supplied wording for 28."}}'
```

The next `/numerology/name/quick` for a name totalling 28 returns the new text — no
restart. `DELETE /admin/rules/compound_meanings/28` puts the bundled default back.

## Status codes

| Code | Meaning |
| --- | --- |
| `400` | Bad OTP, expired token, invalid input the schema could not catch |
| `401` | Missing or expired access token — refresh, then retry once |
| `402` | Free detailed-report quota used up — send the user to the upgrade screen |
| `403` | Signed in, but not allowed (disabled account, a non-admin hitting `/admin/*`, or a bad share token) |
| `404` | Not found, or the resource belongs to another user |
| `409` | Email already registered |
| `422` | Validation failed — `message` names the field |
| `413` | Uploaded image is larger than 5 MB |
| `429` | OTP resend cooldown or too many wrong attempts |
| `503` | Cloudinary is not configured, so uploads are unavailable |
