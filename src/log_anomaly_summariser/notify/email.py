from __future__ import annotations

import asyncio
import email.message
import smtplib


async def send_email(
    host: str,
    port: int,
    user: str | None,
    password: str | None,
    from_addr: str,
    to_addrs: list[str],
    subject: str,
    body: str,
) -> None:
    msg = email.message.EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    msg.set_content(body)

    def _send() -> None:
        with smtplib.SMTP(host=host, port=port, timeout=20) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
            except smtplib.SMTPException:
                pass
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)

    await asyncio.to_thread(_send)

