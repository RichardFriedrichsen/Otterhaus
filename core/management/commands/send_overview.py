"""Send every user an email overview of their outstanding chores.

Schedule this with cron (or Windows Task Scheduler), e.g. daily at 08:00:

    0 8 * * * cd /path/to/backend && python manage.py send_overview
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core import emails
from core.models import Chore


class Command(BaseCommand):
    help = "Email each user an overview of their currently due chores."

    def handle(self, *args, **options):
        sent = 0
        for user in User.objects.exclude(email=""):
            chores = Chore.objects.filter(
                room__house__members=user, is_active=True
            ).select_related("room__house").distinct()
            due = [c for c in chores if c.is_due]
            if due:
                emails.send_overview_email(user, due)
                sent += 1
        self.stdout.write(self.style.SUCCESS(f"Overview emails sent to {sent} user(s)."))
