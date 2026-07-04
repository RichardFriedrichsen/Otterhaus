from django.contrib import admin
from .models import Chore, ChoreCompletion, House, HouseInvite, Membership, Room

admin.site.register([House, Membership, HouseInvite, Room, Chore, ChoreCompletion])
