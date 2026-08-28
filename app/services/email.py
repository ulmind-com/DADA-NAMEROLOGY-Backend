"""Transactional email.

With SMTP configured it sends real mail; without it (local dev) it logs the message
so the OTP flow can be exercised end to end without any credentials.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import settings

log = logging.getLogger("dada.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"

BRAND = "#B3441E"
BG = "#FBF3E7"


def _otp_html(code: str, purpose: str, name: str = "") -> str:
    heading = {
        "signup": "Verify your email",
        "login": "Your login code",
        "reset": "Reset your password",
        "email_change": "Confirm your new email",
    }.get(purpose, "Your verification code")
    greeting = f"Namaste {name}," if name else "Namaste,"
    boxes = "".join(
        f'<td style="width:44px;height:56px;border:1.5px solid #E4C9A8;border-radius:10px;'
        f'background:#FFFDF8;text-align:center;font:600 24px/56px Poppins,Georgia,serif;'
        f'color:#3A2A1E;">{d}</td><td style="width:8px"></td>'
        for d in code
    )
    return f"""\
<div style="margin:0;padding:32px 0;background:{BG};font-family:Poppins,'Segoe UI',Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center">
      <table role="presentation" width="520" cellpadding="0" cellspacing="0"
             style="background:#FFFDF8;border:1px solid #EEDCC4;border-radius:22px;overflow:hidden;">
        <tr><td style="padding:28px 32px 8px;text-align:center;">
          <div style="font:700 13px/1 Poppins,sans-serif;letter-spacing:3px;color:{BRAND};">DADA'S</div>
          <div style="font:700 27px/1.3 Georgia,serif;color:#3A2A1E;margin-top:6px;">NUMEROLOGY</div>
          <div style="height:1px;background:#EEDCC4;margin:20px 0;"></div>
          <div style="font:600 19px/1.4 Poppins,sans-serif;color:#3A2A1E;">{heading}</div>
        </td></tr>
        <tr><td style="padding:4px 32px 0;font:400 14px/1.7 Poppins,sans-serif;color:#6B5647;">
          {greeting}<br/>Use the code below to continue. It is valid for
          {settings.OTP_TTL_MINUTES} minutes.
        </td></tr>
        <tr><td style="padding:22px 32px;" align="center">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>{boxes}</tr></table>
        </td></tr>
        <tr><td style="padding:0 32px 28px;font:400 12.5px/1.7 Poppins,sans-serif;color:#9A8574;">
          If you did not request this, you can safely ignore this email. Never share this
          code with anyone — our team will never ask for it.
        </td></tr>
        <tr><td style="background:{BG};padding:16px 32px;text-align:center;
                       font:400 11.5px/1.6 Poppins,sans-serif;color:#A2907F;">
          © DADA'S NUMEROLOGY · Name · Mobile · Vehicle
        </td></tr>
      </table>
    </td></tr>
  </table>
</div>"""


def _send_via_resend(to: str, subject: str, html: str, text: str) -> bool:
    """Resend's HTTPS API — preferred, since many hosts block outbound SMTP ports."""
    try:
        res = httpx.post(
            RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text or "Please view this email in an HTML-capable client.",
            },
            timeout=20.0,
        )
    except Exception as exc:  # pragma: no cover - network dependent
        log.error("Resend request to %s failed: %s", to, exc)
        return False

    if res.status_code >= 400:
        # Resend explains refusals clearly (unverified domain, bad key, rate limit)
        log.error("Resend rejected mail to %s (%s): %s", to, res.status_code, res.text[:300])
        return False

    log.info("Sent %r to %s via Resend (id=%s)", subject, to, res.json().get("id"))
    return True


def _send_via_smtp(to: str, subject: str, html: str, text: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    msg.set_content(text or "Please view this email in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as srv:
            if settings.SMTP_TLS:
                srv.starttls()
            if settings.SMTP_USER:
                srv.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            srv.send_message(msg)
        return True
    except Exception as exc:  # pragma: no cover - network dependent
        log.error("SMTP send to %s failed: %s", to, exc)
        return False


def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    """Resend first, SMTP second, console last. Returns whether it actually left."""
    if settings.RESEND_API_KEY:
        return _send_via_resend(to, subject, html, text)
    if settings.SMTP_HOST:
        return _send_via_smtp(to, subject, html, text)

    log.warning("[EMAIL:DEV] to=%s subject=%s\n%s", to, subject, text or "(html only)")
    return False


def send_otp_email(to: str, code: str, purpose: str = "signup", name: str = "") -> bool:
    subject = {
        "signup": f"{code} is your DADA'S NUMEROLOGY verification code",
        "login": f"{code} is your login code",
        "reset": f"{code} — reset your password",
    }.get(purpose, f"{code} is your verification code")
    return send_email(
        to, subject, _otp_html(code, purpose, name),
        text=f"Your DADA'S NUMEROLOGY code is {code}. It expires in {settings.OTP_TTL_MINUTES} minutes.",
    )


def send_welcome_email(to: str, name: str) -> bool:
    html = f"""\
<div style="margin:0;padding:32px 0;background:{BG};font-family:Poppins,sans-serif;">
 <table role="presentation" width="100%"><tr><td align="center">
  <table role="presentation" width="520" style="background:#FFFDF8;border:1px solid #EEDCC4;border-radius:22px;">
   <tr><td style="padding:32px;text-align:center;">
     <div style="font:700 13px/1 Poppins;letter-spacing:3px;color:{BRAND};">WELCOME TO</div>
     <div style="font:700 27px/1.3 Georgia,serif;color:#3A2A1E;margin:6px 0 18px;">DADA'S NUMEROLOGY</div>
     <div style="font:400 14px/1.8 Poppins;color:#6B5647;text-align:left;">
       Namaste {name},<br/><br/>
       Your account is ready. You can now check your <b>Name</b>, <b>Mobile Number</b> and
       <b>Vehicle Number</b> against the classical Chaldean system, get corrections,
       and download detailed PDF reports.<br/><br/>
       Start with your name — it takes ten seconds.
     </div>
   </td></tr>
  </table>
 </td></tr></table></div>"""
    return send_email(to, "Welcome to DADA'S NUMEROLOGY", html, f"Welcome {name}!")
