from django.contrib import admin
from .models import Chore, ChoreCompletion, House, Membership, Room

admin.site.register([House, Membership, Room, Chore, ChoreCompletion])
