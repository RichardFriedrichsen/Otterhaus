from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("houses", views.HouseViewSet, basename="house")
router.register("rooms", views.RoomViewSet, basename="room")
router.register("chores", views.ChoreViewSet, basename="chore")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/me/", views.me),
    path("auth/password-reset/", views.password_reset_request),
    path("auth/password-reset/confirm/", views.password_reset_confirm),
    path("invites/accept/", views.accept_invite),
    path("dashboard/", views.dashboard),
    path("overview-email/", views.send_my_overview),
    path("", include(router.urls)),
]
