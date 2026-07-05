import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

ACCESS_CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_access_code():
    return "".join(secrets.choice(ACCESS_CODE_ALPHABET) for _ in range(8))


class House(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="houses_created"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="houses"
    )
    access_code = models.CharField(
        max_length=8, unique=True, editable=False, default=generate_access_code,
        help_text="Shared with others so they can join this house.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    house = models.ForeignKey(House, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "house")


class Room(models.Model):
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("house", "name")

    def __str__(self):
        return f"{self.house.name} / {self.name}"


class Chore(models.Model):
    RECURRENCE_FLOATING = "floating"
    RECURRENCE_FIXED = "fixed"
    RECURRENCE_CHOICES = [
        (RECURRENCE_FLOATING, "Every N days after last completed"),
        (RECURRENCE_FIXED, "Every N days from a fixed start date"),
    ]

    TASK_PLANNED = "planned"
    TASK_ONE_TIME = "one_time"
    TASK_TYPE_CHOICES = [
        (TASK_PLANNED, "Planned (assigned to a room, recurring)"),
        (TASK_ONE_TIME, "One time (ad hoc, not recurring)"),
    ]

    house = models.ForeignKey(
        House, on_delete=models.CASCADE, related_name="chores", null=True, blank=True
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="chores", null=True, blank=True
    )
    task_type = models.CharField(
        max_length=10, choices=TASK_TYPE_CHOICES, default=TASK_PLANNED
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    interval_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="The chore becomes due again this many days after it was last completed.",
    )
    recurrence_type = models.CharField(
        max_length=10, choices=RECURRENCE_CHOICES, default=RECURRENCE_FLOATING
    )
    start_date = models.DateField(
        null=True, blank=True,
        help_text="Anchor date for fixed-schedule recurrence (required when recurrence_type='fixed').",
    )
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_chores"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        if self.task_type == self.TASK_ONE_TIME:
            return f"{self.name} (one time)"
        return f"{self.name} (every {self.interval_days}d)"

    @property
    def last_completion(self):
        return self.completions.order_by("-completed_at").first()

    @property
    def due_date(self):
        """The single date on which this chore is (next) due.

        A chore that was never completed is due immediately (from creation).
        A chore that is overdue stays due once — it never stacks up as
        multiple occurrences, because due-ness is derived from the last
        completion, not from generated instances.

        One-time tasks have no schedule: they're due from creation until
        completed once, and never again after that.
        """
        last = self.last_completion
        if self.task_type == self.TASK_ONE_TIME:
            return timezone.localtime(self.created_at).date()
        if self.recurrence_type == self.RECURRENCE_FIXED and self.start_date:
            return self._fixed_due_date(last)
        if last is None:
            return timezone.localtime(self.created_at).date()
        return timezone.localtime(last.completed_at).date() + timedelta(days=self.interval_days)

    def _fixed_due_date(self, last):
        """Next occurrence on the fixed start_date + N*interval_days schedule."""
        today = timezone.localdate()
        if self.start_date > today:
            candidate = self.start_date
        else:
            cycles = (today - self.start_date).days // self.interval_days
            candidate = self.start_date + timedelta(days=cycles * self.interval_days)
        if last and timezone.localtime(last.completed_at).date() >= candidate:
            candidate += timedelta(days=self.interval_days)
        return candidate

    @property
    def is_due(self):
        if self.task_type == self.TASK_ONE_TIME:
            return self.is_active and self.last_completion is None
        return self.is_active and self.due_date <= timezone.localdate()

    @property
    def days_overdue(self):
        return (timezone.localdate() - self.due_date).days


class ChoreCompletion(models.Model):
    chore = models.ForeignKey(Chore, on_delete=models.CASCADE, related_name="completions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chore_completions"
    )
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-completed_at"]
