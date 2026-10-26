from django.test import TestCase



from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from .models import Role

User = get_user_model()

SIGNUP_URL = "users:signup"
LOGIN_URL = "users:login"
LOGOUT_URL = "users:logout"
HOME_URL = "users:homepage"
RESTRICTED_URL = "users:restricted"
VALIDATE_URL = "users:validate_signup"
PROFILE_URL = "users:profile"
PROFILE_EDIT_URL = "users:profile_edit"
LANDING_URL = "landing"  

PASSWORD = "StrongPass"
NEW_PASSWORD = "BrandNew"


def signup_data(**overrides):
    data = {
        "full_name": "Juan Dela Cruz",
        "username": "juandc",
        "email": "juan@example.com",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        "terms": "on",
    }
    data.update(overrides)
    return data


def is_logged_in(client):
    return "_auth_user_id" in client.session


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class BaseAuthTest(TestCase):
    def setUp(self):
        cache.clear()  
        
        self.student_role, _ = Role.objects.get_or_create(role_name="Student")

    def make_user(self, username="juandc", email="juan@example.com", **kwargs):
        return User.objects.create_user(
            username, email, "Juan Dela Cruz", PASSWORD, kwargs.get("role", self.student_role)
        )



class SignupTests(BaseAuthTest):
    def setUp(self):
        super().setUp()
        self.url = reverse(SIGNUP_URL)

    def submit(self, data):
        """POST with a clean rate-limit counter (signup is limited to 7/min per IP)."""
        cache.clear()
        return self.client.post(self.url, data)

    def test_page_loads(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_valid_signup_creates_student_and_redirects_to_login(self):
        response = self.submit(signup_data())
        self.assertRedirects(response, reverse(LOGIN_URL), fetch_redirect_response=False)
        user = User.objects.get(username="juandc")
        self.assertEqual(user.role, self.student_role)
        self.assertEqual(user.full_name, "Juan Dela Cruz")
        self.assertTrue(user.is_active)

    def test_username_and_email_are_lowercased(self):
        self.submit(signup_data(username="JuanDC", email="Juan@Example.COM"))
        user = User.objects.get(username="juandc")
        self.assertEqual(user.email, "juan@example.com")

    def test_password_is_hashed(self):
        self.submit(signup_data())
        user = User.objects.get(username="juandc")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_signup_does_not_log_user_in(self):
        self.submit(signup_data())
        self.assertFalse(is_logged_in(self.client))

    def test_terms_required(self):
        data = signup_data()
        data.pop("terms")
        response = self.submit(data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="juandc").exists())
        self.assertIn("Terms of Service", str(response.context["form"].non_field_errors()))

    def test_missing_required_fields(self):
        for field in ("full_name", "username", "email", "password", "confirm_password"):
            with self.subTest(missing=field):
                data = signup_data()
                data.pop(field)
                self.submit(data)
                self.assertFalse(User.objects.filter(username="juandc").exists())

    def test_password_mismatch_rejected(self):
        response = self.submit(signup_data(confirm_password="DifferentPass"))
        self.assertFalse(User.objects.filter(username="juandc").exists())
        self.assertIn("Passwords do not match", str(response.context["form"].non_field_errors()))

    def test_duplicate_username_rejected_including_case_variants(self):
        self.make_user("juandc", "first@example.com")
        for username in ("juandc", "JUANDC", "JuanDC"):
            with self.subTest(username=username):
                self.submit(signup_data(username=username, email="second@example.com"))
                self.assertEqual(User.objects.filter(username__iexact="juandc").count(), 1)

    def test_duplicate_email_rejected_including_case_variants(self):
        self.make_user("other", "juan@example.com")
        for email in ("juan@example.com", "JUAN@example.com"):
            with self.subTest(email=email):
                self.submit(signup_data(email=email))
                self.assertFalse(User.objects.filter(username="juandc").exists())

    def test_invalid_email_rejected(self):
        for email in ("not-an-email", "a@", "@example.com", "a b@example.com"):
            with self.subTest(email=email):
                self.submit(signup_data(email=email))
                self.assertFalse(User.objects.filter(username="juandc").exists())

    def test_weak_passwords_rejected(self):
        for pw in ("123", "short1!", "password", "12345678"):
            with self.subTest(password=pw):
                self.submit(signup_data(password=pw, confirm_password=pw))
                self.assertFalse(User.objects.filter(username="juandc").exists())

    def test_password_too_similar_to_username_rejected(self):
        
        self.submit(signup_data(password="juandc12", confirm_password="juandc12"))
        self.assertFalse(User.objects.filter(username="juandc").exists())

    def test_invalid_usernames_rejected(self):
        for username in ("ab", "a" * 31, "juan dc", "juan-dc", "juan@dc", "___", "juan.dc"):
            with self.subTest(username=username):
                self.submit(signup_data(username=username))
                self.assertFalse(User.objects.filter(email="juan@example.com").exists())

    def test_valid_username_boundaries_accepted(self):
        for i, username in enumerate(("abc", "a" * 30, "juan_dc_01")):
            with self.subTest(username=username):
                self.submit(signup_data(username=username, email=f"user{i}@example.com"))
                self.assertTrue(User.objects.filter(username=username).exists())

    def test_invalid_full_names_rejected(self):
        for name in ("J", "Juan123", "<script>", "1234", "_ _", "Juan@Cruz"):
            with self.subTest(full_name=name):
                self.submit(signup_data(full_name=name))
                self.assertFalse(User.objects.filter(username="juandc").exists())

    def test_valid_full_names_accepted(self):
        names = ("Ma. Cristina O'Brien-Reyes", "Jose Rizal Jr.", "Ñoño Peña")
        for i, name in enumerate(names):
            with self.subTest(full_name=name):
                self.submit(signup_data(full_name=name, username=f"user{i}", email=f"user{i}@example.com"))
                self.assertTrue(User.objects.filter(username=f"user{i}").exists())

    def test_cannot_self_assign_role_or_staff(self):
        admin_role = Role.objects.create(role_name="Admin")
        self.submit(signup_data(role=admin_role.pk, is_staff="on", is_superuser="on"))
        user = User.objects.get(username="juandc")
        self.assertEqual(user.role, self.student_role)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_authenticated_user_redirected_away(self):
        self.make_user()
        self.client.login(username="juandc", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse(LANDING_URL), fetch_redirect_response=False)

    def test_rate_limit_blocks_eighth_post_in_a_minute(self):
        
        cache.clear()
        for _ in range(7):
            self.client.post(self.url, signup_data(terms=""))
        response = self.client.post(self.url, signup_data())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="juandc").exists())
        self.assertTrue(any("Too many accounts" in m for m in message_texts(response)))

    def test_get_requests_are_not_rate_limited(self):
        cache.clear()
        for _ in range(10):
            self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_missing_student_role_does_not_crash(self):
        
        
        Role.objects.all().delete()
        client = Client(raise_request_exception=False)
        response = client.post(self.url, signup_data())
        self.assertNotEqual(response.status_code, 500)



class LoginTests(BaseAuthTest):
    def setUp(self):
        super().setUp()
        self.url = reverse(LOGIN_URL)
        self.user = self.make_user()

    def creds(self, username="juandc", password=PASSWORD, **extra):
        return {"username": username, "password": password, **extra}

    def attempt(self, **kwargs):
        """POST with a clean rate-limit counter (login is limited to 5/min per IP)."""
        cache.clear()
        return self.client.post(self.url, self.creds(**kwargs))

    def test_page_loads(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_valid_login_redirects_to_landing(self):
        response = self.attempt()
        self.assertRedirects(response, reverse(LANDING_URL), fetch_redirect_response=False)
        self.assertTrue(is_logged_in(self.client))

    def test_username_is_case_insensitive(self):
        
        self.attempt(username="JUANDC")
        self.assertTrue(is_logged_in(self.client))

    def test_wrong_password(self):
        response = self.attempt(password="WrongPass")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(is_logged_in(self.client))

    def test_unknown_user(self):
        self.attempt(username="ghost")
        self.assertFalse(is_logged_in(self.client))

    def test_wrong_password_and_unknown_user_give_same_error(self):
        
        r1 = self.attempt(password="WrongPass")
        r2 = self.attempt(username="ghost")
        self.assertEqual(
            str(r1.context["form"].non_field_errors()),
            str(r2.context["form"].non_field_errors()),
        )

    def test_empty_credentials(self):
        self.attempt(username="", password="")
        self.assertFalse(is_logged_in(self.client))

    def test_password_is_case_sensitive(self):
        self.attempt(password=PASSWORD.lower())
        self.assertFalse(is_logged_in(self.client))

    def test_sql_injection_attempt(self):
        self.attempt(username="' OR '1'='1", password="' OR '1'='1")
        self.assertFalse(is_logged_in(self.client))

    
    def test_inactive_user_with_correct_password_sees_deactivated_notice(self):
        self.user.is_active = False
        self.user.save()
        response = self.attempt()
        self.assertFalse(is_logged_in(self.client))
        self.assertTrue(response.context["deactivated"])
        self.assertIn("deactivated", str(response.context["form"].non_field_errors()))

    def test_inactive_user_with_wrong_password_does_not_leak_status(self):
        self.user.is_active = False
        self.user.save()
        response = self.attempt(password="WrongPass")
        self.assertFalse(is_logged_in(self.client))
        self.assertFalse(response.context["deactivated"])
        self.assertNotIn("deactivated", str(response.context["form"].non_field_errors()))

    def test_active_user_wrong_password_not_flagged_deactivated(self):
        response = self.attempt(password="WrongPass")
        self.assertFalse(response.context["deactivated"])

    
    def test_safe_next_is_followed(self):
        target = reverse(HOME_URL)
        cache.clear()
        response = self.client.post(self.url, self.creds(next=target))
        self.assertRedirects(response, target, fetch_redirect_response=False)

    def test_unsafe_next_values_are_ignored(self):
        for bad in ("https://evil.example.com/", "//evil.example.com/", "javascript:alert(1)"):
            with self.subTest(next=bad):
                self.client.logout()
                cache.clear()
                response = self.client.post(self.url, self.creds(next=bad))
                self.assertRedirects(response, reverse(LANDING_URL), fetch_redirect_response=False)

    def test_authenticated_user_redirected_away(self):
        self.client.login(username="juandc", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse(LANDING_URL), fetch_redirect_response=False)

    
    def test_sixth_attempt_blocked_even_with_correct_password(self):
        cache.clear()
        for _ in range(5):
            self.client.post(self.url, self.creds(password="WrongPass"))
        response = self.client.post(self.url, self.creds())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(is_logged_in(self.client))
        self.assertTrue(any("Too many attempts" in m for m in message_texts(response)))

    def test_fifth_attempt_still_allowed(self):
        cache.clear()
        for _ in range(4):
            self.client.post(self.url, self.creds(password="WrongPass"))
        self.client.post(self.url, self.creds())
        self.assertTrue(is_logged_in(self.client))

    def test_rate_limit_is_per_ip(self):
        cache.clear()
        for _ in range(6):
            self.client.post(self.url, self.creds(password="WrongPass"))
        other = Client(REMOTE_ADDR="10.0.0.2")
        other.post(self.url, self.creds())
        self.assertTrue(is_logged_in(other))

    def test_get_requests_are_not_rate_limited(self):
        cache.clear()
        for _ in range(10):
            self.assertEqual(self.client.get(self.url).status_code, 200)



class LogoutTests(BaseAuthTest):
    def setUp(self):
        super().setUp()
        self.make_user()
        self.client.login(username="juandc", password=PASSWORD)

    def test_post_logs_out_and_redirects(self):
        response = self.client.post(reverse(LOGOUT_URL))
        self.assertRedirects(response, reverse(LANDING_URL), fetch_redirect_response=False)
        self.assertFalse(is_logged_in(self.client))

    def test_get_does_not_crash_or_log_out(self):
        
        
        client = Client(raise_request_exception=False)
        client.login(username="juandc", password=PASSWORD)
        response = client.get(reverse(LOGOUT_URL))
        self.assertIn(response.status_code, (302, 405))
        self.assertTrue(is_logged_in(client))



class AccessControlTests(BaseAuthTest):
    def test_anonymous_redirected_to_restricted(self):
        for name in (HOME_URL, PROFILE_URL, PROFILE_EDIT_URL):
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                expected = f"{reverse(RESTRICTED_URL)}?next={reverse(name)}"
                self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_logged_in_pages_load(self):
        self.make_user()
        self.client.login(username="juandc", password=PASSWORD)
        for name in (HOME_URL, PROFILE_URL, PROFILE_EDIT_URL):
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_restricted_page_is_public(self):
        self.assertEqual(self.client.get(reverse(RESTRICTED_URL)).status_code, 200)



class ValidateSignupTests(BaseAuthTest):
    def setUp(self):
        super().setUp()
        self.url = reverse(VALIDATE_URL)

    def errors_for(self, **overrides):
        cache.clear()
        return self.client.post(self.url, signup_data(**overrides)).json()["errors"]

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_valid_data_returns_no_errors(self):
        self.assertEqual(self.errors_for(), {})

    def test_taken_username_reported(self):
        self.make_user("juandc", "other@example.com")
        self.assertIn("username", self.errors_for())

    def test_taken_email_reported(self):
        self.make_user("other", "juan@example.com")
        self.assertIn("email", self.errors_for())

    def test_bad_username_reported_with_message(self):
        self.assertIn("3 to 30", self.errors_for(username="ab")["username"])

    def test_bad_full_name_reported(self):
        self.assertIn("full_name", self.errors_for(full_name="Juan123"))

    def test_weak_password_reported(self):
        self.assertIn("password", self.errors_for(password="123", confirm_password="123"))

    def test_empty_fields_not_reported(self):
        
        errors = self.errors_for(username="", email="")
        self.assertNotIn("username", errors)
        self.assertNotIn("email", errors)

    def test_password_mismatch_not_reported_live(self):
        
        
        self.assertEqual(self.errors_for(confirm_password="DifferentPass"), {})

    def test_does_not_create_user(self):
        self.errors_for()
        self.assertFalse(User.objects.filter(username="juandc").exists())

    def test_rate_limit_returns_429_after_60(self):
        cache.clear()
        for _ in range(60):
            self.client.post(self.url, signup_data())
        response = self.client.post(self.url, signup_data())
        self.assertEqual(response.status_code, 429)



class ProfileEditTests(BaseAuthTest):
    def setUp(self):
        super().setUp()
        self.url = reverse(PROFILE_EDIT_URL)
        self.user = self.make_user()
        self.client.login(username="juandc", password=PASSWORD)

    def data(self, **overrides):
        base = {
            "fullname": "Juan Dela Cruz",
            "username": "juandc",
            "email": "juan@example.com",
            "current_password": PASSWORD,
            "new_password": "",
        }
        base.update(overrides)
        return base

    def test_valid_update_saves_and_redirects(self):
        response = self.client.post(self.url, self.data(
            fullname="Juan D. Cruz", username="NewName", email="New@Example.com"))
        self.assertRedirects(response, reverse(PROFILE_URL), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Juan D. Cruz")
        self.assertEqual(self.user.username, "newname")
        self.assertEqual(self.user.email, "new@example.com")

    def test_keeping_own_username_and_email_is_allowed(self):
        response = self.client.post(self.url, self.data(fullname="Juan Cruz"))
        self.assertRedirects(response, reverse(PROFILE_URL), fetch_redirect_response=False)

    def test_wrong_current_password_blocks_changes(self):
        response = self.client.post(self.url, self.data(fullname="Hacker", current_password="WrongPass"))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Juan Dela Cruz")

    def test_missing_current_password_blocks_changes(self):
        data = self.data(fullname="Hacker")
        data.pop("current_password")
        self.client.post(self.url, data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Juan Dela Cruz")

    def test_username_taken_by_someone_else(self):
        self.make_user("maria", "maria@example.com")
        self.client.post(self.url, self.data(username="maria"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "juandc")

    def test_email_taken_by_someone_else(self):
        self.make_user("maria", "maria@example.com")
        self.client.post(self.url, self.data(email="maria@example.com"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "juan@example.com")

    def test_password_change_keeps_session_and_updates_hash(self):
        response = self.client.post(self.url, self.data(new_password=NEW_PASSWORD))
        self.assertRedirects(response, reverse(PROFILE_URL), fetch_redirect_response=False)
        self.assertTrue(is_logged_in(self.client))
        self.assertEqual(self.client.get(reverse(PROFILE_URL)).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(PASSWORD))

    def test_weak_new_password_rejected(self):
        self.client.post(self.url, self.data(new_password="123"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_blank_new_password_leaves_password_unchanged(self):
        self.client.post(self.url, self.data(fullname="Juan Cruz"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))