import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class House(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="houses_created"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="houses"
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


class HouseInvite(models.Model):
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("house", "email")


class Room(models.Model):
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("house", "name")

    def __str__(self):
        return f"{self.house.name} / {self.name}"


class Chore(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="chores")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    interval_days = models.PositiveIntegerField(
        help_text="The chore becomes due again this many days after it was last completed."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
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
        """
        last = self.last_completion
        if last is None:
            return self.created_at.date()
        return last.completed_at.date() + timedelta(days=self.interval_days)

    @property
    def is_due(self):
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
