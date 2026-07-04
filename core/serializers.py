from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Chore, ChoreCompletion, House, HouseInvite, Room


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")


class ChoreCompletionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    chore_name = serializers.CharField(source="chore.name", read_only=True)
    room_name = serializers.CharField(source="chore.room.name", read_only=True)

    class Meta:
        model = ChoreCompletion
        fields = ("id", "user", "chore_name", "room_name", "completed_at")


class ChoreSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField(read_only=True)
    is_due = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    last_completed_by = serializers.SerializerMethodField()
    last_completed_at = serializers.SerializerMethodField()
    room_name = serializers.CharField(source="room.name", read_only=True)
    house_id = serializers.IntegerField(source="room.house_id", read_only=True)
    house_name = serializers.CharField(source="room.house.name", read_only=True)

    class Meta:
        model = Chore
        fields = (
            "id", "room", "room_name", "house_id", "house_name", "name",
            "description", "interval_days", "is_active", "due_date",
            "is_due", "days_overdue", "last_completed_by", "last_completed_at",
        )
        extra_kwargs = {
            "room": {"required": False},
            "is_active": {"default": True},
        }

    def get_last_completed_by(self, obj):
        last = obj.last_completion
        return last.user.username if last else None

    def get_last_completed_at(self, obj):
        last = obj.last_completion
        return last.completed_at if last else None


class RoomSerializer(serializers.ModelSerializer):
    chores = ChoreSerializer(many=True, read_only=True)

    class Meta:
        model = Room
        fields = ("id", "house", "name", "chores")
        extra_kwargs = {"house": {"required": False}}


class HouseInviteSerializer(serializers.ModelSerializer):
    invited_by = UserSerializer(read_only=True)

    class Meta:
        model = HouseInvite
        fields = ("id", "email", "accepted", "invited_by", "created_at")


class HouseSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)
    rooms = RoomSerializer(many=True, read_only=True)
    invites = serializers.SerializerMethodField()

    class Meta:
        model = House
        fields = ("id", "name", "created_by", "members", "rooms", "invites", "created_at")
        read_only_fields = ("created_by",)

    def get_invites(self, obj):
        pending = obj.invites.filter(accepted=False)
        return HouseInviteSerializer(pending, many=True).data
