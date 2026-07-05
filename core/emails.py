"""All outgoing email lives here so it is easy to adjust wording in one place.

Emails are sent through the Gmail SMTP settings in config/settings.py.
`fail_silently=True` is used for notification mail so a Gmail hiccup never
breaks the API request itself; password-reset mail raises errors because
the user needs to know if that failed.
"""
from django.conf import settings
from django.core.mail import send_mail


def send_password_reset_email(user, uid, token):
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_mail(
        subject="Reset your Choreboard password",
        message=(
            f"Hi {user.username},\n\n"
            f"Use the link below to set a new password:\n{link}\n\n"
            f"If you didn't request this, you can ignore this email.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def send_completion_notification(completion):
    """Notify all other members of the house that a chore was completed."""
    chore = completion.chore
    house = chore.house
    recipients = [
        m.email
        for m in house.members.exclude(pk=completion.user.pk)
        if m.email
    ]
    if not recipients:
        return
    where = f" in {chore.room.name}" if chore.room else ""
    recurs = (
        f"It will be due again in {chore.interval_days} days.\n"
        if chore.task_type != chore.TASK_ONE_TIME else ""
    )
    send_mail(
        subject=f"{completion.user.username} completed '{chore.name}'",
        message=(
            f"{completion.user.username} just completed the chore "
            f"'{chore.name}'{where} ({house.name}).\n\n{recurs}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=True,
    )


def send_overview_email(user, due_chores):
    """Send one user an overview of everything currently due in their houses."""
    if not user.email or not due_chores:
        return
    lines = []
    for chore in due_chores:
        overdue = chore.days_overdue
        when = "due today" if overdue == 0 else f"overdue by {overdue} day(s)"
        where = f"{chore.house.name} / {chore.room.name}" if chore.room else chore.house.name
        lines.append(f"- {chore.name} — {where} ({when})")
    send_mail(
        subject=f"Choreboard: {len(due_chores)} chore(s) waiting for you",
        message=(
            f"Hi {user.username},\n\nthese chores are currently outstanding:\n\n"
            + "\n".join(lines)
            + f"\n\nOpen your dashboard: {settings.FRONTEND_URL}\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
