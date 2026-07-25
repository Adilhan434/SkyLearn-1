from django.conf import settings
from django.contrib.auth.models import update_last_login
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_serializers import (
    CurrentUserSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    LoginUserSerializer,
    MessageSerializer,
)
from .cookies import clear_auth_cookies, set_access_cookie, set_refresh_cookie


def _authentication_error(message):
    return Response(
        {
            "error": {
                "code": "authentication_failed",
                "message": message,
                "fields": {},
            }
        },
        status=status.HTTP_401_UNAUTHORIZED,
    )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: LoginResponseSerializer},
        tags=["Auth"],
    )
    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        if settings.SIMPLE_JWT.get("UPDATE_LAST_LOGIN"):
            update_last_login(None, user)

        response = Response(
            {"user": LoginUserSerializer(user).data},
            status=status.HTTP_200_OK,
        )
        set_access_cookie(response, refresh.access_token)
        set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={200: MessageSerializer},
        tags=["Auth"],
    )
    def post(self, request):
        cookie_name = settings.SIMPLE_JWT.get(
            "AUTH_COOKIE_REFRESH", "refresh_token"
        )
        refresh_token = request.COOKIES.get(cookie_name)
        if not refresh_token:
            return _authentication_error("Refresh token is missing.")

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            return _authentication_error("Refresh token is invalid or expired.")

        response = Response(
            {"message": "Token refreshed successfully."},
            status=status.HTTP_200_OK,
        )
        set_access_cookie(response, serializer.validated_data["access"])
        rotated_refresh = serializer.validated_data.get("refresh")
        if rotated_refresh:
            set_refresh_cookie(response, rotated_refresh)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={200: MessageSerializer},
        tags=["Auth"],
    )
    def post(self, request):
        cookie_name = settings.SIMPLE_JWT.get(
            "AUTH_COOKIE_REFRESH", "refresh_token"
        )
        refresh_token = request.COOKIES.get(cookie_name)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass

        response = Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )
        clear_auth_cookies(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CurrentUserSerializer}, tags=["Auth"])
    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)
