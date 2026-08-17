from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from .models import User
from .tokens import email_verification_token

REGISTER_PAYLOAD = {
    "email": "shopkeeper@example.com",
    "password": "Str0ngPass!23",
    "confirm_password": "Str0ngPass!23",
    "shop_name": "Ram Kirana Pasal",
}


class RegistrationAndVerificationTests(TestCase):
    def setUp(self):
        # forgot-password/resend-verification share the "forgot_password"
        # ScopedRateThrottle bucket, backed by the real Redis cache — clear
        # it so one test's requests don't eat into another's 5/hour budget.
        cache.clear()
        self.client = APIClient()

    def _register(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                "/api/v1/user/register/", REGISTER_PAYLOAD, format="json"
            )

    def test_register_creates_inactive_user_with_a_shop_and_sends_verification_email(
        self,
    ):
        response = self._register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=REGISTER_PAYLOAD["email"])
        self.assertFalse(user.is_active)
        self.assertTrue(hasattr(user, "shop"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)

    def test_cannot_login_before_verifying(self):
        self._register()

        response = self.client.post(
            "/api/v1/auth/token/",
            {
                "email": REGISTER_PAYLOAD["email"],
                "password": REGISTER_PAYLOAD["password"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_email_activates_and_allows_login(self):
        self._register()
        user = User.objects.get(email=REGISTER_PAYLOAD["email"])
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)

        response = self.client.post(
            "/api/v1/user/verify-email/", {"uid": uid, "token": token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        login = self.client.post(
            "/api/v1/auth/token/",
            {
                "email": REGISTER_PAYLOAD["email"],
                "password": REGISTER_PAYLOAD["password"],
            },
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_verify_email_rejects_bad_token(self):
        self._register()
        user = User.objects.get(email=REGISTER_PAYLOAD["email"])
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        response = self.client.post(
            "/api/v1/user/verify-email/",
            {"uid": uid, "token": "garbage"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_verification_token_cannot_be_reused(self):
        self._register()
        user = User.objects.get(email=REGISTER_PAYLOAD["email"])
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        self.client.post(
            "/api/v1/user/verify-email/", {"uid": uid, "token": token}, format="json"
        )

        response = self.client.post(
            "/api/v1/user/verify-email/", {"uid": uid, "token": token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_does_not_reveal_whether_email_exists(self):
        response = self.client.post(
            "/api/v1/user/verify-email/resend/",
            {"email": "nobody@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_sends_a_new_email_for_unverified_user(self):
        self._register()
        mail.outbox.clear()

        response = self.client.post(
            "/api/v1/user/verify-email/resend/",
            {"email": REGISTER_PAYLOAD["email"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)


class PasswordTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="ram@example.com", password="Str0ngPass!23"
        )

    def test_forgot_password_sends_email_for_existing_user(self):
        response = self.client.post(
            "/api/v1/user/forgot-password/", {"email": self.user.email}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_silent_for_unknown_email(self):
        response = self.client.post(
            "/api/v1/user/forgot-password/",
            {"email": "nobody@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_change_password_requires_correct_old_password(self):
        self.client.force_authenticate(self.user)

        response = self.client.put(
            "/api/v1/user/change-password/",
            {
                "old_password": "wrong-password",
                "password": "NewStr0ngPass!23",
                "confirm_password": "NewStr0ngPass!23",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_succeeds(self):
        self.client.force_authenticate(self.user)

        response = self.client.put(
            "/api/v1/user/change-password/",
            {
                "old_password": "Str0ngPass!23",
                "password": "NewStr0ngPass!23",
                "confirm_password": "NewStr0ngPass!23",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStr0ngPass!23"))

    def test_unauthenticated_cannot_change_password(self):
        response = self.client.put(
            "/api/v1/user/change-password/",
            {
                "old_password": "Str0ngPass!23",
                "password": "NewStr0ngPass!23",
                "confirm_password": "NewStr0ngPass!23",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
