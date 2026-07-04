from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import emails
from .models import Chore, ChoreCompletion, House, HouseInvite, Membership, Room
from .serializers import (
    ChoreCompletionSerializer, ChoreSerializer, HouseSerializer,
    RegisterSerializer, RoomSerializer, UserSerializer,
)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Apply any pending house invites that were sent to this email.
        for invite in HouseInvite.objects.filter(email__iexact=user.email, accepted=False):
            Membership.objects.get_or_create(user=user, house=invite.house)
            invite.accepted = True
            invite.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(ObtainAuthToken):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    """Always answers 200 so the endpoint can't be used to probe which
    email addresses exist."""
    email = request.data.get("email", "").strip()
    user = User.objects.filter(email__iexact=email).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        emails.send_password_reset_email(user, uid, token)
    return Response({"detail": "If that email exists, a reset link has been sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    uid = request.data.get("uid", "")
    token = request.data.get("token", "")
    new_password = request.data.get("new_password", "")
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return Response({"detail": "Invalid reset link."}, status=400)
    if not default_token_generator.check_token(user, token):
        return Response({"detail": "Reset link is invalid or has expired."}, status=400)
    try:
        validate_password(new_password, user)
    except DjangoValidationError as e:
        return Response({"detail": " ".join(e.messages)}, status=400)
    user.set_password(new_password)
    user.save()
    # Invalidate existing sessions/tokens after a reset.
    Token.objects.filter(user=user).delete()
    return Response({"detail": "Password updated. You can now sign in."})


@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)


# --------------------------------------------------------------------------
# Houses & invites
# --------------------------------------------------------------------------

class HouseViewSet(viewsets.ModelViewSet):
    serializer_class = HouseSerializer

    def get_queryset(self):
        return House.objects.filter(members=self.request.user).distinct()

    def perform_create(self, serializer):
        house = serializer.save(created_by=self.request.user)
        Membership.objects.create(user=self.request.user, house=house)

    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        house = self.get_object()
        email = request.data.get("email", "").strip()
        if not email:
            return Response({"detail": "Email is required."}, status=400)
        if house.members.filter(email__iexact=email).exists():
            return Response({"detail": "That person is already a member."}, status=400)
        invite, created = HouseInvite.objects.get_or_create(
            house=house, email=email, defaults={"invited_by": request.user}
        )
        if not created and invite.accepted:
            return Response({"detail": "That invite was already accepted."}, status=400)
        emails.send_invite_email(invite)
        return Response({"detail": f"Invite sent to {email}."}, status=201)

    @action(detail=True, methods=["get"])
    def scoreboard(self, request, pk=None):
        house = self.get_object()
        completions = ChoreCompletion.objects.filter(chore__room__house=house)
        scores = []
        for member in house.members.all():
            user_completions = completions.filter(user=member)
            scores.append({
                "user": UserSerializer(member).data,
                "total": user_completions.count(),
                "last_completions": ChoreCompletionSerializer(
                    user_completions[:5], many=True
                ).data,
            })
        scores.sort(key=lambda s: s["total"], reverse=True)
        recent = ChoreCompletionSerializer(completions[:15], many=True).data
        return Response({"scores": scores, "recent": recent})


@api_view(["POST"])
def accept_invite(request):
    token = request.data.get("token", "")
    try:
        invite = HouseInvite.objects.get(token=token, accepted=False)
    except (HouseInvite.DoesNotExist, DjangoValidationError, ValueError):
        return Response({"detail": "Invite is invalid or already used."}, status=400)
    Membership.objects.get_or_create(user=request.user, house=invite.house)
    invite.accepted = True
    invite.save()
    return Response({"detail": f"You joined '{invite.house.name}'.",
                     "house": HouseSerializer(invite.house).data})


# --------------------------------------------------------------------------
# Rooms & chores
# --------------------------------------------------------------------------

class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer

    def get_queryset(self):
        return Room.objects.filter(house__members=self.request.user).distinct()

    def perform_create(self, serializer):
        house = serializer.validated_data.get("house")
        if house is None or not house.members.filter(pk=self.request.user.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of that house.")
        serializer.save()


class ChoreViewSet(viewsets.ModelViewSet):
    serializer_class = ChoreSerializer

    def get_queryset(self):
        return Chore.objects.filter(room__house__members=self.request.user).distinct()

    def perform_create(self, serializer):
        room = serializer.validated_data.get("room")
        if room is None or not room.house.members.filter(pk=self.request.user.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of that house.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        chore = self.get_object()
        completion = ChoreCompletion.objects.create(chore=chore, user=request.user)
        emails.send_completion_notification(completion)
        return Response(
            {"detail": f"'{chore.name}' marked as done.",
             "chore": ChoreSerializer(chore).data},
            status=201,
        )


@api_view(["GET"])
def dashboard(request):
    """Every chore that is currently due across the user's houses.

    An overdue chore appears exactly once no matter how many intervals have
    passed, because due-ness is derived from the last completion date rather
    than from generated occurrences.
    """
    chores = Chore.objects.filter(
        room__house__members=request.user, is_active=True
    ).select_related("room__house").distinct()
    due = sorted((c for c in chores if c.is_due), key=lambda c: c.due_date)
    upcoming = sorted((c for c in chores if not c.is_due), key=lambda c: c.due_date)[:10]
    return Response({
        "due": ChoreSerializer(due, many=True).data,
        "upcoming": ChoreSerializer(upcoming, many=True).data,
    })


@api_view(["POST"])
def send_my_overview(request):
    """Manually trigger the outstanding-chores overview email for yourself."""
    chores = Chore.objects.filter(
        room__house__members=request.user, is_active=True
    ).select_related("room__house").distinct()
    due = [c for c in chores if c.is_due]
    if not request.user.email:
        return Response({"detail": "Your account has no email address."}, status=400)
    if not due:
        return Response({"detail": "Nothing is due — no email sent."})
    emails.send_overview_email(request.user, due)
    return Response({"detail": f"Overview with {len(due)} chore(s) sent to {request.user.email}."})
