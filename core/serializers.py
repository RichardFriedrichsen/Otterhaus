from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Chore, ChoreCompletion, House, Room


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
    room_name = serializers.SerializerMethodField()

    class Meta:
        model = ChoreCompletion
        fields = ("id", "user", "chore_name", "room_name", "completed_at")

    def get_room_name(self, obj):
        return obj.chore.room.name if obj.chore.room else None


class ChoreSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField(read_only=True)
    is_due = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    last_completed_by = serializers.SerializerMethodField()
    last_completed_at = serializers.SerializerMethodField()
    room_name = serializers.CharField(source="room.name", read_only=True, default=None)
    house = serializers.PrimaryKeyRelatedField(
        queryset=House.objects.all(), required=False, allow_null=True
    )
    house_name = serializers.CharField(source="house.name", read_only=True, default=None)
    assigned_to = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=False
    )
    assigned_to_detail = UserSerializer(source="assigned_to", many=True, read_only=True)

    class Meta:
        model = Chore
        fields = (
            "id", "task_type", "room", "room_name", "house", "house_name", "name",
            "description", "interval_days", "recurrence_type", "start_date",
            "is_active", "assigned_to", "assigned_to_detail", "due_date",
            "is_due", "days_overdue", "last_completed_by", "last_completed_at",
        )
        extra_kwargs = {
            "room": {"required": False, "allow_null": True},
            "is_active": {"default": True},
        }

    def validate(self, attrs):
        task_type = attrs.get("task_type", getattr(self.instance, "task_type", Chore.TASK_PLANNED))
        room = attrs.get("room", getattr(self.instance, "room", None))
        house = attrs.get("house", getattr(self.instance, "house", None))
        interval_days = attrs.get("interval_days", getattr(self.instance, "interval_days", None))
        recurrence_type = attrs.get(
            "recurrence_type", getattr(self.instance, "recurrence_type", Chore.RECURRENCE_FLOATING)
        )
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))

        if task_type == Chore.TASK_PLANNED:
            if room is None:
                raise serializers.ValidationError({"room": "Required for planned tasks."})
            if not interval_days:
                raise serializers.ValidationError({"interval_days": "Required for planned tasks."})
            if recurrence_type == Chore.RECURRENCE_FIXED and not start_date:
                raise serializers.ValidationError(
                    {"start_date": "Required when recurrence type is 'fixed'."}
                )
        elif room is None and house is None:
            raise serializers.ValidationError(
                {"house": "Required for a one-time task that isn't tied to a room."}
            )
        return attrs

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


class HouseSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)
    rooms = RoomSerializer(many=True, read_only=True)

    class Meta:
        model = House
        fields = ("id", "name", "created_by", "members", "rooms", "access_code", "created_at")
        read_only_fields = ("created_by", "access_code")
