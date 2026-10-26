from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from papers.models import Category, PaperCategory, ResearchPaper
from similarity.models import (
    Embedding,
    FFM,
    FFMEntry,
    FFMResult,
    Feedback,
    SimilarityResult,
)
from users.models import Role

from .forms import AdminUserCreationForm


User = get_user_model()


def create_staff_user(username, email):
    user = User.objects.create_user(
        username=username,
        email=email,
        full_name='Test Staff User',
    )
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    return user


class AdminDashboardCounterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_role = Role.objects.create(role_name='Student')
        cls.faculty_role = Role.objects.create(role_name='Faculty')
        cls.admin_role = Role.objects.create(role_name='Admin')
        cls.other_role = Role.objects.create(role_name='Other')

        cls.staff_user = create_staff_user(
            username='dashboard_staff',
            email='dashboard-staff@example.com',
        )
        cls.staff_user.role = cls.admin_role
        cls.staff_user.save(update_fields=['role'])

        cls.student_user = User.objects.create_user(
            username='dashboard_student',
            email='dashboard-student@example.com',
            full_name='Dashboard Student',
            role=cls.student_role,
        )
        cls.faculty_user = User.objects.create_user(
            username='dashboard_faculty',
            email='dashboard-faculty@example.com',
            full_name='Dashboard Faculty',
            role=cls.faculty_role,
        )
        cls.other_user = User.objects.create_user(
            username='dashboard_other',
            email='dashboard-other@example.com',
            full_name='Dashboard Other User',
            role=cls.other_role,
        )

        ResearchPaper.objects.create(
            title='Dashboard Capstone',
            abstract='Dashboard capstone abstract.',
            authors='Dashboard Capstone Author',
            year=2025,
            type='capstone',
            program='Computer Science',
            file_path='research_papers/dashboard-capstone.pdf',
        )
        ResearchPaper.objects.create(
            title='Dashboard Thesis',
            abstract='Dashboard thesis abstract.',
            authors='Dashboard Thesis Author',
            year=2026,
            type='thesis',
            program='Information Systems',
            file_path='research_papers/dashboard-thesis.pdf',
        )

    def setUp(self):
        self.client.force_login(self.staff_user)
        self.dashboard_url = reverse(
            'administratordb:admin_dashboard'
        )

    def test_staff_user_can_access_dashboard(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)

    def test_total_documents_counts_all_research_papers(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context['total_documents'], 2)

    def test_total_users_counts_all_users_including_staff_admin(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context['total_users'], 4)

    def test_student_users_contribute_to_student_count(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context['student_count'], 1)

    def test_faculty_users_contribute_to_faculty_count(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context['faculty_count'], 1)

    def test_admin_and_other_roles_do_not_affect_role_counts(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context['student_count'], 1)
        self.assertEqual(response.context['faculty_count'], 1)

    def test_zero_student_users_returns_zero(self):
        self.student_user.delete()

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context['student_count'], 0)

    def test_zero_faculty_users_returns_zero(self):
        self.faculty_user.delete()

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.context['faculty_count'], 0)

    def test_dashboard_user_preview_is_limited_and_ordered_by_user_id(self):
        fifth_user = User.objects.create_user(
            username='dashboard_fifth',
            email='dashboard-fifth@example.com',
            full_name='Dashboard Fifth User',
        )
        sixth_user = User.objects.create_user(
            username='dashboard_sixth',
            email='dashboard-sixth@example.com',
            full_name='Dashboard Sixth User',
        )
        User.objects.create_user(
            username='dashboard_seventh',
            email='dashboard-seventh@example.com',
            full_name='Dashboard Seventh User',
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(
            list(response.context['users']),
            [
                self.staff_user,
                self.student_user,
                self.faculty_user,
                self.other_user,
                fifth_user,
                sixth_user,
            ],
        )

    def test_dashboard_user_table_renders_custom_user_fields(self):
        response = self.client.get(self.dashboard_url)

        self.assertContains(
            response,
            f'<td>{self.student_user.user_id:03d}</td>',
            html=True,
        )
        self.assertContains(response, self.student_user.full_name)
        self.assertContains(response, self.student_user.username)
        self.assertContains(response, self.student_user.email)
        self.assertContains(response, self.student_role.role_name)

    def test_dashboard_user_table_displays_unassigned_for_null_role(self):
        User.objects.create_user(
            username='dashboard_unassigned',
            email='dashboard-unassigned@example.com',
            full_name='Dashboard Unassigned User',
        )

        response = self.client.get(self.dashboard_url)

        self.assertContains(response, '<td>Unassigned</td>', html=True)

    def test_documents_card_links_to_research_papers(self):
        response = self.client.get(self.dashboard_url)

        self.assertContains(
            response,
            f'href="{reverse("administratordb:admin_research_papers")}"',
        )

    def test_total_users_card_links_to_manage_users(self):
        response = self.client.get(self.dashboard_url)

        self.assertContains(
            response,
            f'href="{reverse("administratordb:admin_users")}"',
        )

    def test_student_card_links_to_filtered_manage_users(self):
        response = self.client.get(self.dashboard_url)

        self.assertContains(
            response,
            f'href="{reverse("administratordb:admin_users")}?role=Student"',
        )

    def test_faculty_card_links_to_filtered_manage_users(self):
        response = self.client.get(self.dashboard_url)

        self.assertContains(
            response,
            f'href="{reverse("administratordb:admin_users")}?role=Faculty"',
        )


class AdminManageUsersReadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_role = Role.objects.create(role_name='Student')
        cls.faculty_role = Role.objects.create(role_name='Faculty')
        cls.admin_role = Role.objects.create(role_name='Admin')
        cls.other_role = Role.objects.create(role_name='Other')

        cls.staff_user = create_staff_user(
            username='manage_users_staff',
            email='manage-users-staff@example.com',
        )
        cls.staff_user.role = cls.admin_role
        cls.staff_user.save(update_fields=['role'])

        cls.student_one = User.objects.create_user(
            username='student_one',
            email='student-one@example.com',
            full_name='Student One',
            role=cls.student_role,
        )
        cls.student_two = User.objects.create_user(
            username='student_two',
            email='student-two@example.com',
            full_name='Student Two',
            role=cls.student_role,
        )
        cls.faculty_user = User.objects.create_user(
            username='faculty_one',
            email='faculty-one@example.com',
            full_name='Faculty One',
            role=cls.faculty_role,
        )
        cls.other_user = User.objects.create_user(
            username='other_one',
            email='other-one@example.com',
            full_name='Other One',
            role=cls.other_role,
        )
        cls.unassigned_user = User.objects.create_user(
            username='unassigned_one',
            email='unassigned-one@example.com',
            full_name='Unassigned One',
        )

    def setUp(self):
        self.client.force_login(self.staff_user)
        self.manage_users_url = reverse(
            'administratordb:admin_users'
        )

    def create_additional_users(
        self,
        count,
        *,
        role,
        username_prefix,
        full_name_prefix,
    ):
        return [
            User.objects.create_user(
                username=f'{username_prefix}_{index}',
                email=f'{username_prefix}-{index}@example.com',
                full_name=f'{full_name_prefix} {index}',
                role=role,
            )
            for index in range(count)
        ]

    def test_staff_user_can_access_manage_users(self):
        response = self.client.get(self.manage_users_url)

        self.assertEqual(response.status_code, 200)

    def test_actual_users_appear_in_context_and_table(self):
        response = self.client.get(self.manage_users_url)
        displayed_users = list(response.context['users'])

        self.assertIn(self.student_one, displayed_users)
        self.assertIn(self.faculty_user, displayed_users)
        self.assertContains(response, self.student_one.full_name)
        self.assertContains(response, self.faculty_user.email)

    def test_total_registered_users_count_is_global(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.student_one.username},
        )

        self.assertEqual(response.context['total_users'], 6)

    def test_student_count_is_global(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.faculty_user.username},
        )

        self.assertEqual(response.context['student_count'], 2)

    def test_faculty_count_is_global(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.student_one.username},
        )

        self.assertEqual(response.context['faculty_count'], 1)

    def test_search_by_full_name(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.student_one.full_name},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.student_one],
        )

    def test_search_by_username(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.faculty_user.username},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.faculty_user],
        )

    def test_search_by_email(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.other_user.email},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.other_user],
        )

    def test_search_by_role_name(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': 'Admin'},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.staff_user],
        )

    def test_search_is_case_insensitive(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': 'sTuDeNt OnE'},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.student_one],
        )

    def test_empty_search_returns_all_users(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': '   '},
        )

        self.assertEqual(len(response.context['users']), 6)
        self.assertEqual(response.context['q'], '')

    def test_nonmatching_search_returns_empty_result_safely(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': 'no-matching-user'},
        )

        self.assertEqual(list(response.context['users']), [])
        self.assertContains(response, 'No registered users found.')

    def test_user_with_null_role_displays_unassigned(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.unassigned_user.username},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['users']),
            [self.unassigned_user],
        )
        self.assertContains(response, 'Unassigned')

    def test_search_does_not_change_global_counters(self):
        response = self.client.get(
            self.manage_users_url,
            {'q': self.student_one.username},
        )

        self.assertEqual(len(response.context['users']), 1)
        self.assertEqual(response.context['total_users'], 6)
        self.assertEqual(response.context['student_count'], 2)
        self.assertEqual(response.context['faculty_count'], 1)

    def test_student_role_filter_returns_only_student_users(self):
        response = self.client.get(
            self.manage_users_url,
            {'role': 'Student'},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.student_one, self.student_two],
        )

    def test_faculty_role_filter_returns_only_faculty_users(self):
        response = self.client.get(
            self.manage_users_url,
            {'role': 'Faculty'},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.faculty_user],
        )

    def test_admin_role_filter_returns_only_admin_role_users(self):
        response = self.client.get(
            self.manage_users_url,
            {'role': 'Admin'},
        )

        self.assertEqual(
            list(response.context['users']),
            [self.staff_user],
        )

    def test_blank_role_filter_returns_all_users(self):
        response = self.client.get(
            self.manage_users_url,
            {'role': ''},
        )

        self.assertEqual(len(response.context['users']), 6)
        self.assertEqual(response.context['selected_role'], '')

    def test_invalid_role_filter_safely_returns_all_users(self):
        response = self.client.get(
            self.manage_users_url,
            {'role': 'SomethingInvalid'},
        )

        self.assertEqual(len(response.context['users']), 6)
        self.assertEqual(response.context['selected_role'], '')

    def test_null_role_user_appears_only_when_all_roles_are_selected(self):
        all_roles_response = self.client.get(
            self.manage_users_url,
            {'role': ''},
        )
        student_response = self.client.get(
            self.manage_users_url,
            {'role': 'Student'},
        )

        self.assertIn(
            self.unassigned_user,
            list(all_roles_response.context['users']),
        )
        self.assertNotIn(
            self.unassigned_user,
            list(student_response.context['users']),
        )

    def test_selected_role_is_preserved_in_context_and_template(self):
        response = self.client.get(
            self.manage_users_url,
            {'role': 'Faculty'},
        )

        self.assertEqual(response.context['selected_role'], 'Faculty')
        self.assertContains(response, 'value="Faculty" selected')

    def test_role_filter_does_not_change_global_counters(self):
        response = self.client.get(
            self.manage_users_url,
            {'role': 'Student'},
        )

        self.assertEqual(response.context['total_users'], 6)
        self.assertEqual(response.context['student_count'], 2)
        self.assertEqual(response.context['faculty_count'], 1)

    def test_search_and_role_filter_use_and_behavior(self):
        response = self.client.get(
            self.manage_users_url,
            {
                'q': 'One',
                'role': 'Student',
            },
        )

        self.assertEqual(
            list(response.context['users']),
            [self.student_one],
        )

    def test_search_text_and_selected_role_are_both_preserved(self):
        response = self.client.get(
            self.manage_users_url,
            {
                'q': 'student',
                'role': 'Student',
            },
        )

        self.assertEqual(response.context['q'], 'student')
        self.assertEqual(response.context['selected_role'], 'Student')
        self.assertContains(response, 'value="student"')
        self.assertContains(response, 'value="Student" selected')

    def test_pagination_displays_ten_users_on_first_page(self):
        self.create_additional_users(
            6,
            role=self.other_role,
            username_prefix='page_size',
            full_name_prefix='Page Size User',
        )

        response = self.client.get(self.manage_users_url)

        self.assertEqual(len(response.context['users']), 10)
        self.assertEqual(response.context['users'].number, 1)

    def test_second_page_contains_remaining_users(self):
        additional_users = self.create_additional_users(
            6,
            role=self.other_role,
            username_prefix='page_two',
            full_name_prefix='Page Two User',
        )

        response = self.client.get(
            self.manage_users_url,
            {'page': 2},
        )

        self.assertEqual(
            list(response.context['users']),
            additional_users[-2:],
        )
        self.assertTrue(response.context['users'].has_previous())

    def test_invalid_page_value_is_handled_safely(self):
        response = self.client.get(
            self.manage_users_url,
            {'page': 'abc'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['users'].number, 1)

    def test_out_of_range_page_value_is_handled_safely(self):
        self.create_additional_users(
            6,
            role=self.other_role,
            username_prefix='out_of_range',
            full_name_prefix='Out Of Range User',
        )

        response = self.client.get(
            self.manage_users_url,
            {'page': 999999},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['users'].number, 2)

    def test_pagination_link_preserves_search_query(self):
        self.create_additional_users(
            11,
            role=self.other_role,
            username_prefix='search_page',
            full_name_prefix='Pagination Match',
        )

        response = self.client.get(
            self.manage_users_url,
            {'q': 'Pagination Match'},
        )

        self.assertContains(
            response,
            (
                'href="?q=Pagination%20Match&amp;role='
                '&amp;page=2"'
            ),
        )

    def test_pagination_link_preserves_role_filter(self):
        self.create_additional_users(
            9,
            role=self.student_role,
            username_prefix='role_page',
            full_name_prefix='Role Page Student',
        )

        response = self.client.get(
            self.manage_users_url,
            {'role': 'Student'},
        )

        self.assertContains(
            response,
            'href="?q=&amp;role=Student&amp;page=2"',
        )

    def test_pagination_link_preserves_search_and_role_filter(self):
        self.create_additional_users(
            11,
            role=self.student_role,
            username_prefix='combined_page',
            full_name_prefix='Combined Pagination Target',
        )

        response = self.client.get(
            self.manage_users_url,
            {
                'q': 'Combined Pagination Target',
                'role': 'Student',
            },
        )

        self.assertContains(
            response,
            (
                'href="?q=Combined%20Pagination%20Target'
                '&amp;role=Student&amp;page=2"'
            ),
        )

    def test_global_counters_remain_unchanged_between_pages(self):
        self.create_additional_users(
            6,
            role=self.other_role,
            username_prefix='counter_page',
            full_name_prefix='Counter Page User',
        )

        first_response = self.client.get(
            self.manage_users_url,
            {'page': 1},
        )
        second_response = self.client.get(
            self.manage_users_url,
            {'page': 2},
        )

        self.assertEqual(
            first_response.context['total_users'],
            second_response.context['total_users'],
        )
        self.assertEqual(
            first_response.context['student_count'],
            second_response.context['student_count'],
        )
        self.assertEqual(
            first_response.context['faculty_count'],
            second_response.context['faculty_count'],
        )


class AdminAddUserTests(TestCase):
    password = 'Safe-Admin-Password-9274!'
    punctuation_only_values = ('!', '__', '...', '---')

    @classmethod
    def setUpTestData(cls):
        cls.student_role = Role.objects.create(role_name='Student')
        cls.faculty_role = Role.objects.create(role_name='Faculty')
        cls.admin_role = Role.objects.create(role_name='Admin')
        cls.staff_user = create_staff_user(
            username='add_user_staff',
            email='add-user-staff@example.com',
        )
        cls.staff_user.role = cls.admin_role
        cls.staff_user.save(update_fields=['role'])
        cls.non_staff_user = User.objects.create_user(
            username='add_user_non_staff',
            email='add-user-non-staff@example.com',
            full_name='Add User Non Staff',
            role=cls.student_role,
        )

    def setUp(self):
        self.client.force_login(self.staff_user)
        self.add_user_url = reverse('administratordb:admin_add_user')
        self.manage_users_url = reverse('administratordb:admin_users')

    def valid_data(self, **overrides):
        data = {
            'full_name': 'New Managed User',
            'username': 'new_managed_user',
            'email': 'new-managed-user@example.com',
            'password': self.password,
            'confirm_password': self.password,
            'role': str(self.student_role.role_id),
        }
        data.update(overrides)
        return data

    def test_staff_admin_can_open_add_user(self):
        response = self.client.get(self.add_user_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add a new user account')

    def test_anonymous_user_cannot_access_add_user(self):
        self.client.logout()

        response = self.client.get(self.add_user_url)

        self.assertEqual(response.status_code, 302)

    def test_non_staff_user_cannot_access_add_user(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(self.add_user_url)

        self.assertEqual(response.status_code, 302)

    def test_manage_users_page_contains_add_user_link(self):
        response = self.client.get(self.manage_users_url)

        self.assertContains(
            response,
            f'href="{self.add_user_url}"',
        )

    def test_valid_student_user_creation(self):
        response = self.client.post(self.add_user_url, self.valid_data())

        created_user = User.objects.get(username='new_managed_user')
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(created_user.role, self.student_role)
        self.assertTrue(created_user.is_active)
        self.assertFalse(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)

    def test_valid_faculty_user_creation(self):
        response = self.client.post(
            self.add_user_url,
            self.valid_data(
                username='new_faculty_user',
                email='new-faculty-user@example.com',
                role=str(self.faculty_role.role_id),
            ),
        )

        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(
            User.objects.get(username='new_faculty_user').role,
            self.faculty_role,
        )

    def test_created_user_password_is_hashed(self):
        self.client.post(
            self.add_user_url,
            self.valid_data(
                username='password_check_user',
                email='password-check-user@example.com',
            ),
        )

        created_user = User.objects.get(username='password_check_user')
        self.assertNotEqual(created_user.password, self.password)
        self.assertTrue(created_user.check_password(self.password))

    def test_identity_is_cleaned_without_saving_during_validation(self):
        user_count = User.objects.count()
        form = AdminUserCreationForm(
            data=self.valid_data(
                full_name='  Normalized Managed User  ',
                username='  MiXeD_Case_User  ',
            )
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.instance.pk)
        self.assertEqual(form.instance.full_name, 'Normalized Managed User')
        self.assertEqual(form.instance.username, 'mixed_case_user')
        self.assertEqual(
            form.instance.email,
            'new-managed-user@example.com',
        )
        self.assertEqual(User.objects.count(), user_count)

        created_user = form.save()
        created_user.refresh_from_db()
        self.assertEqual(created_user.full_name, 'Normalized Managed User')
        self.assertEqual(created_user.username, 'mixed_case_user')
        self.assertTrue(created_user.check_password(self.password))

    def test_invalid_full_name_is_rejected(self):
        user_count = User.objects.count()

        response = self.client.post(
            self.add_user_url,
            self.valid_data(full_name='Invalid Name 123'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('full_name', response.context['form'].errors)
        self.assertEqual(User.objects.count(), user_count)

    def test_invalid_username_is_rejected(self):
        user_count = User.objects.count()

        response = self.client.post(
            self.add_user_url,
            self.valid_data(username='invalid username!'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(User.objects.count(), user_count)

    def test_punctuation_only_username_is_rejected(self):
        user_count = User.objects.count()

        for value in self.punctuation_only_values:
            with self.subTest(value=value):
                response = self.client.post(
                    self.add_user_url,
                    self.valid_data(username=value),
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn('username', response.context['form'].errors)
                self.assertEqual(User.objects.count(), user_count)

    def test_punctuation_only_email_is_rejected(self):
        user_count = User.objects.count()

        for value in self.punctuation_only_values:
            with self.subTest(value=value):
                response = self.client.post(
                    self.add_user_url,
                    self.valid_data(email=value),
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn('email', response.context['form'].errors)
                self.assertEqual(User.objects.count(), user_count)

    @override_settings(AUTH_PASSWORD_VALIDATORS=[
        {
            'NAME': (
                'django.contrib.auth.password_validation.'
                'UserAttributeSimilarityValidator'
            ),
        },
    ])
    def test_password_similar_to_username_or_email_is_rejected(self):
        user_count = User.objects.count()
        cases = [
            ('username', 'similar_username_9274', 'similar_username_9274'),
            ('email', 'mailbox9274@example.com', 'mailbox9274'),
        ]

        for field, value, password in cases:
            with self.subTest(field=field):
                data = self.valid_data(
                    password=password,
                    confirm_password=password,
                )
                data[field] = value

                response = self.client.post(self.add_user_url, data)

                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    response.context['form'].has_error(
                        'password', 'password_too_similar'
                    )
                )
                self.assertEqual(User.objects.count(), user_count)

    def test_invalid_fields_do_not_break_password_validation(self):
        user_count = User.objects.count()
        invalid_values = {
            'full_name': '1234',
            'username': 'invalid username!',
            'email': 'not-an-email',
            'role': '',
            'password': '',
            'confirm_password': '',
        }

        for field, value in invalid_values.items():
            with self.subTest(field=field):
                response = self.client.post(
                    self.add_user_url,
                    self.valid_data(**{field: value}),
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                self.assertEqual(User.objects.count(), user_count)

    def test_password_mismatch_is_rejected(self):
        user_count = User.objects.count()

        response = self.client.post(
            self.add_user_url,
            self.valid_data(confirm_password='Different-Password-5291!'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('confirm_password', response.context['form'].errors)
        self.assertEqual(User.objects.count(), user_count)

    def test_duplicate_username_is_rejected(self):
        user_count = User.objects.count()

        response = self.client.post(
            self.add_user_url,
            self.valid_data(username=self.non_staff_user.username),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(User.objects.count(), user_count)

    def test_duplicate_username_is_rejected_after_normalization(self):
        user_count = User.objects.count()

        response = self.client.post(
            self.add_user_url,
            self.valid_data(
                username=f'  {self.non_staff_user.username.upper()}  ',
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(User.objects.count(), user_count)

    def test_duplicate_email_is_rejected(self):
        user_count = User.objects.count()

        response = self.client.post(
            self.add_user_url,
            self.valid_data(email=self.non_staff_user.email),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertEqual(User.objects.count(), user_count)

    def test_admin_role_assignment_is_rejected(self):
        user_count = User.objects.count()

        response = self.client.post(
            self.add_user_url,
            self.valid_data(role=str(self.admin_role.role_id)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('role', response.context['form'].errors)
        self.assertEqual(User.objects.count(), user_count)

    def test_new_user_appears_in_manage_users(self):
        self.client.post(self.add_user_url, self.valid_data())

        response = self.client.get(
            self.manage_users_url,
            {'q': 'new_managed_user'},
        )

        self.assertContains(response, 'New Managed User')
        self.assertContains(response, 'new-managed-user@example.com')


class AdminEditUserTests(TestCase):
    punctuation_only_values = ('!', '__', '...', '---')

    @classmethod
    def setUpTestData(cls):
        cls.student_role = Role.objects.create(role_name='Student')
        cls.faculty_role = Role.objects.create(role_name='Faculty')
        cls.admin_role = Role.objects.create(role_name='Admin')
        cls.staff_user = create_staff_user(
            username='edit_user_staff',
            email='edit-user-staff@example.com',
        )
        cls.staff_user.role = cls.admin_role
        cls.staff_user.save(update_fields=['role'])
        cls.student_user = User.objects.create_user(
            username='edit_student',
            email='edit-student@example.com',
            full_name='Edit Student User',
            password='Original-Student-Password-42!',
            role=cls.student_role,
        )
        cls.faculty_user = User.objects.create_user(
            username='edit_faculty',
            email='edit-faculty@example.com',
            full_name='Edit Faculty User',
            password='Original-Faculty-Password-42!',
            role=cls.faculty_role,
        )
        cls.admin_role_user = User.objects.create_user(
            username='role_only_admin',
            email='role-only-admin@example.com',
            full_name='Role Only Admin',
            role=cls.admin_role,
        )
        cls.superuser_target = User.objects.create_superuser(
            username='edit_superuser',
            email='edit-superuser@example.com',
            full_name='Edit Superuser',
            password='Original-Superuser-Password-42!',
        )
        cls.superuser_target.role = cls.admin_role
        cls.superuser_target.save(update_fields=['role'])

    def setUp(self):
        self.client.force_login(self.staff_user)
        self.manage_users_url = reverse('administratordb:admin_users')

    def edit_url(self, user):
        return reverse(
            'administratordb:admin_edit_user',
            args=[user.user_id],
        )

    def valid_data(self, user=None, **overrides):
        user = user or self.student_user
        data = {
            'full_name': user.full_name,
            'username': user.username,
            'email': user.email,
            'role': str(user.role_id),
        }
        data.update(overrides)
        return data

    def test_staff_admin_can_open_edit_for_normal_student_and_faculty(self):
        for user in (self.student_user, self.faculty_user):
            with self.subTest(username=user.username):
                response = self.client.get(self.edit_url(user))

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['managed_user'], user)
                self.assertFalse(response.context['is_protected_account'])
                self.assertEqual(
                    response.context['form'].initial['full_name'],
                    user.full_name,
                )
                self.assertEqual(
                    response.context['form'].initial['username'],
                    user.username,
                )
                self.assertEqual(
                    response.context['form'].initial['email'],
                    user.email,
                )
                self.assertContains(response, 'name="full_name"')
                self.assertContains(response, 'name="username"')
                self.assertContains(response, 'name="email"')
                self.assertContains(response, 'name="role"')
                self.assertContains(response, 'readonly', count=1)
                self.assertNotContains(response, user.password)
                self.assertNotContains(response, 'name="password"')
                self.assertNotContains(response, 'name="is_staff"')
                self.assertNotContains(response, 'name="is_superuser"')
                self.assertNotContains(response, 'name="groups"')
                self.assertNotContains(
                    response,
                    'name="user_permissions"',
                )

    def test_anonymous_user_cannot_access_edit_user(self):
        self.client.logout()

        response = self.client.get(self.edit_url(self.student_user))

        self.assertEqual(response.status_code, 302)

    def test_non_staff_user_cannot_access_edit_user(self):
        self.client.force_login(self.student_user)

        response = self.client.get(self.edit_url(self.faculty_user))

        self.assertEqual(response.status_code, 302)

    def test_full_name_can_be_updated(self):
        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(full_name='Updated Student Name'),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(
            self.student_user.full_name,
            'Updated Student Name',
        )

    def test_username_can_be_updated(self):
        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(username='updated_student'),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(self.student_user.username, 'updated_student')

    def test_email_can_be_updated_and_normalized(self):
        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(email='updated-student@EXAMPLE.COM'),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(
            self.student_user.email,
            'updated-student@example.com',
        )

    def test_student_role_can_be_changed_to_faculty(self):
        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(role=str(self.faculty_role.role_id)),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(self.student_user.role, self.faculty_role)

    def test_faculty_role_can_be_changed_to_student(self):
        response = self.client.post(
            self.edit_url(self.faculty_user),
            self.valid_data(
                self.faculty_user,
                role=str(self.student_role.role_id),
            ),
        )

        self.faculty_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(self.faculty_user.role, self.student_role)

    def test_current_username_and_email_remain_valid_when_unchanged(self):
        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(full_name='Updated With Same Identity'),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(self.student_user.username, 'edit_student')
        self.assertEqual(
            self.student_user.email,
            'edit-student@example.com',
        )

    def test_duplicate_username_belonging_to_another_user_is_rejected(self):
        original_username = self.student_user.username

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(username=self.faculty_user.username),
        )

        self.student_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(self.student_user.username, original_username)

    def test_duplicate_email_belonging_to_another_user_is_rejected(self):
        original_email = self.student_user.email

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(email=self.faculty_user.email),
        )

        self.student_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertEqual(self.student_user.email, original_email)

    def test_invalid_email_is_rejected(self):
        original_email = self.student_user.email

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(email='not-an-email-address'),
        )

        self.student_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertEqual(self.student_user.email, original_email)

    def test_invalid_full_name_is_rejected(self):
        original_full_name = self.student_user.full_name

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(full_name='12345'),
        )

        self.student_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn('full_name', response.context['form'].errors)
        self.assertEqual(self.student_user.full_name, original_full_name)

    def test_invalid_username_format_is_rejected(self):
        original_username = self.student_user.username

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(username='invalid username!'),
        )

        self.student_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(self.student_user.username, original_username)

    def test_punctuation_only_username_is_rejected(self):
        original_username = self.student_user.username

        for value in self.punctuation_only_values:
            with self.subTest(value=value):
                response = self.client.post(
                    self.edit_url(self.student_user),
                    self.valid_data(username=value),
                )

                self.student_user.refresh_from_db()
                self.assertEqual(response.status_code, 200)
                self.assertIn('username', response.context['form'].errors)
                self.assertEqual(
                    self.student_user.username,
                    original_username,
                )

    def test_punctuation_only_email_is_rejected(self):
        original_email = self.student_user.email

        for value in self.punctuation_only_values:
            with self.subTest(value=value):
                response = self.client.post(
                    self.edit_url(self.student_user),
                    self.valid_data(email=value),
                )

                self.student_user.refresh_from_db()
                self.assertEqual(response.status_code, 200)
                self.assertIn('email', response.context['form'].errors)
                self.assertEqual(self.student_user.email, original_email)

    def test_unapproved_role_is_rejected(self):
        original_role = self.student_user.role

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(role=str(self.admin_role.role_id)),
        )

        self.student_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn('role', response.context['form'].errors)
        self.assertEqual(self.student_user.role, original_role)

    def test_user_id_remains_unchanged(self):
        original_user_id = self.student_user.user_id

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(
                full_name='Updated Without ID Change',
                user_id=999999,
            ),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(self.student_user.user_id, original_user_id)

    def test_missing_user_returns_404(self):
        missing_url = reverse(
            'administratordb:admin_edit_user',
            args=[999999],
        )

        response = self.client.get(missing_url)

        self.assertEqual(response.status_code, 404)

    def test_password_hash_and_forged_password_are_unchanged(self):
        original_password = self.student_user.password

        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(
                full_name='Approved Name Update',
                password='Injected-Password-9274!',
            ),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(self.student_user.password, original_password)

    def test_forged_privilege_fields_are_ignored(self):
        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(
                full_name='Safe Normal Account',
                is_staff='true',
                is_superuser='true',
                groups='1',
                user_permissions='1',
            ),
        )

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertFalse(self.student_user.is_staff)
        self.assertFalse(self.student_user.is_superuser)

    def test_protected_staff_target_remains_unchanged(self):
        original_values = (
            self.staff_user.user_id,
            self.staff_user.full_name,
            self.staff_user.username,
            self.staff_user.email,
            self.staff_user.role_id,
            self.staff_user.password,
            self.staff_user.is_staff,
            self.staff_user.is_superuser,
        )

        response = self.client.post(
            self.edit_url(self.staff_user),
            self.valid_data(
                self.staff_user,
                full_name='Forged Staff Name',
                username='forged_staff',
                email='forged-staff@example.com',
                role=str(self.student_role.role_id),
                is_staff='false',
                is_superuser='false',
            ),
        )

        self.staff_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (
                self.staff_user.user_id,
                self.staff_user.full_name,
                self.staff_user.username,
                self.staff_user.email,
                self.staff_user.role_id,
                self.staff_user.password,
                self.staff_user.is_staff,
                self.staff_user.is_superuser,
            ),
            original_values,
        )
        self.assertContains(
            response,
            'account details cannot be changed here',
        )
        self.assertNotContains(response, 'Save Changes')

    def test_protected_superuser_target_remains_unchanged(self):
        original_values = (
            self.superuser_target.user_id,
            self.superuser_target.full_name,
            self.superuser_target.username,
            self.superuser_target.email,
            self.superuser_target.role_id,
            self.superuser_target.password,
            self.superuser_target.is_staff,
            self.superuser_target.is_superuser,
        )

        response = self.client.post(
            self.edit_url(self.superuser_target),
            self.valid_data(
                self.superuser_target,
                full_name='Forged Superuser Name',
                username='forged_superuser',
                email='forged-superuser@example.com',
                role=str(self.student_role.role_id),
                is_staff='false',
                is_superuser='false',
            ),
        )

        self.superuser_target.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (
                self.superuser_target.user_id,
                self.superuser_target.full_name,
                self.superuser_target.username,
                self.superuser_target.email,
                self.superuser_target.role_id,
                self.superuser_target.password,
                self.superuser_target.is_staff,
                self.superuser_target.is_superuser,
            ),
            original_values,
        )
        self.assertContains(
            response,
            'account details cannot be changed here',
        )
        self.assertNotContains(response, 'Save Changes')

    def test_non_staff_admin_role_account_can_be_reassigned(self):
        response = self.client.post(
            self.edit_url(self.admin_role_user),
            self.valid_data(
                self.admin_role_user,
                role=str(self.student_role.role_id),
            ),
        )

        self.admin_role_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertEqual(self.admin_role_user.role, self.student_role)

    def test_successful_update_redirects_to_manage_users(self):
        response = self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(full_name='Redirected User'),
        )

        self.assertRedirects(response, self.manage_users_url)

    def test_updated_values_appear_in_manage_users(self):
        self.client.post(
            self.edit_url(self.student_user),
            self.valid_data(
                full_name='Visible Updated User',
                username='visible_updated_user',
                email='visible-updated-user@example.com',
                role=str(self.faculty_role.role_id),
            ),
        )

        response = self.client.get(self.manage_users_url)

        self.assertContains(response, 'Visible Updated User')
        self.assertContains(response, 'visible_updated_user')
        self.assertContains(response, 'visible-updated-user@example.com')
        self.assertContains(response, 'Faculty')

    def test_manage_users_edit_action_uses_real_user_url(self):
        response = self.client.get(self.manage_users_url)

        self.assertContains(
            response,
            f'href="{self.edit_url(self.student_user)}"',
        )

    def test_manage_users_does_not_contain_delete_action(self):
        response = self.client.get(self.manage_users_url)

        self.assertNotContains(response, 'Delete')


class AdminDeactivateUserTests(TestCase):
    password = 'Deactivate-User-Password-9274!'

    @classmethod
    def setUpTestData(cls):
        cls.student_role = Role.objects.create(role_name='Student')
        cls.faculty_role = Role.objects.create(role_name='Faculty')
        cls.admin_role = Role.objects.create(role_name='Admin')

        cls.staff_admin = create_staff_user(
            username='deactivate_admin',
            email='deactivate-admin@example.com',
        )
        cls.staff_admin.role = cls.admin_role
        cls.staff_admin.save(update_fields=['role'])

        cls.student_user = User.objects.create_user(
            username='deactivate_student',
            email='deactivate-student@example.com',
            full_name='Deactivate Student',
            password=cls.password,
            role=cls.student_role,
        )
        cls.faculty_user = User.objects.create_user(
            username='deactivate_faculty',
            email='deactivate-faculty@example.com',
            full_name='Deactivate Faculty',
            password=cls.password,
            role=cls.faculty_role,
        )
        cls.inactive_user = User.objects.create_user(
            username='already_inactive',
            email='already-inactive@example.com',
            full_name='Already Inactive',
            password=cls.password,
            role=cls.student_role,
        )
        cls.inactive_user.is_active = False
        cls.inactive_user.save(update_fields=['is_active'])

        cls.protected_staff = create_staff_user(
            username='protected_staff_target',
            email='protected-staff-target@example.com',
        )
        cls.protected_staff.role = cls.student_role
        cls.protected_staff.save(update_fields=['role'])

        cls.protected_superuser = User.objects.create_superuser(
            username='protected_superuser_target',
            email='protected-superuser-target@example.com',
            full_name='Protected Superuser Target',
            password=cls.password,
        )
        cls.protected_superuser.role = cls.faculty_role
        cls.protected_superuser.save(update_fields=['role'])

        cls.student_paper = ResearchPaper.objects.create(
            title='Retained Student Paper',
            abstract='This paper must remain after account deactivation.',
            authors='Deactivate Student',
            year=2026,
            type='capstone',
            program='Computer Science',
            file_path='research_papers/retained-student-paper.pdf',
            user=cls.student_user,
        )
        cls.student_feedback = Feedback.objects.create(
            rating=5,
            message='This feedback must remain after deactivation.',
            user=cls.student_user,
        )

    def setUp(self):
        self.client.force_login(self.staff_admin)
        self.manage_users_url = reverse('administratordb:admin_users')
        self.admin_login_url = reverse('administratordb:admin_login')

    def deactivate_url(self, user):
        return reverse(
            'administratordb:admin_deactivate_user',
            args=[user.user_id],
        )

    def test_anonymous_user_cannot_access_deactivation(self):
        self.client.logout()
        url = self.deactivate_url(self.student_user)

        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(url)

                self.assertRedirects(
                    response,
                    f'{self.admin_login_url}?next={url}',
                )
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.is_active)

    def test_non_staff_user_cannot_access_deactivation(self):
        self.client.force_login(self.student_user)
        url = self.deactivate_url(self.faculty_user)

        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(url)

                self.assertEqual(response.status_code, 302)
        self.faculty_user.refresh_from_db()
        self.assertTrue(self.faculty_user.is_active)

    def test_staff_admin_can_view_student_and_faculty_confirmation(self):
        for user in (self.student_user, self.faculty_user):
            with self.subTest(username=user.username):
                response = self.client.get(self.deactivate_url(user))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response,
                    'administratordb/admin-deactivate-user.html',
                )
                self.assertEqual(response.context['managed_user'], user)
                self.assertContains(response, user.full_name)
                self.assertContains(response, user.username)
                self.assertContains(response, user.email)
                self.assertContains(response, user.role.role_name)
                self.assertContains(response, 'Deactivate Account')

    def test_get_displays_confirmation_without_deactivating(self):
        response = self.client.get(self.deactivate_url(self.student_user))

        self.student_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.student_user.is_active)

    def test_post_deactivates_student_without_deleting_user_row(self):
        initial_count = User.objects.count()

        response = self.client.post(self.deactivate_url(self.student_user))

        self.student_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertFalse(self.student_user.is_active)
        self.assertEqual(User.objects.count(), initial_count)
        self.assertTrue(
            User.objects.filter(user_id=self.student_user.user_id).exists()
        )

    def test_post_deactivates_faculty(self):
        response = self.client.post(self.deactivate_url(self.faculty_user))

        self.faculty_user.refresh_from_db()
        self.assertRedirects(response, self.manage_users_url)
        self.assertFalse(self.faculty_user.is_active)

    def test_deactivation_preserves_role_and_password_hash(self):
        original_role_id = self.student_user.role_id
        original_password_hash = self.student_user.password

        self.client.post(self.deactivate_url(self.student_user))

        self.student_user.refresh_from_db()
        self.assertEqual(self.student_user.role_id, original_role_id)
        self.assertEqual(self.student_user.password, original_password_hash)

    def test_deactivation_preserves_research_paper_and_feedback(self):
        self.client.post(self.deactivate_url(self.student_user))

        self.student_paper.refresh_from_db()
        self.student_feedback.refresh_from_db()
        self.assertEqual(
            self.student_paper.user_id,
            self.student_user.user_id,
        )
        self.assertEqual(
            self.student_feedback.user_id,
            self.student_user.user_id,
        )

    def test_staff_target_cannot_be_deactivated(self):
        url = self.deactivate_url(self.protected_staff)

        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(url)

                self.assertEqual(response.status_code, 403)

        self.protected_staff.refresh_from_db()
        self.assertTrue(self.protected_staff.is_active)

    def test_superuser_target_cannot_be_deactivated(self):
        url = self.deactivate_url(self.protected_superuser)

        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(url)

                self.assertEqual(response.status_code, 403)

        self.protected_superuser.refresh_from_db()
        self.assertTrue(self.protected_superuser.is_active)

    def test_current_admin_cannot_deactivate_itself(self):
        url = self.deactivate_url(self.staff_admin)

        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(url)

                self.assertEqual(response.status_code, 403)

        self.staff_admin.refresh_from_db()
        self.assertTrue(self.staff_admin.is_active)

    def test_nonexistent_user_returns_404(self):
        missing_url = reverse(
            'administratordb:admin_deactivate_user',
            args=[999999],
        )

        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(missing_url)

                self.assertEqual(response.status_code, 404)

    def test_repeated_post_for_inactive_user_is_harmless(self):
        initial_count = User.objects.count()
        url = self.deactivate_url(self.inactive_user)

        first_response = self.client.post(url)
        second_response = self.client.post(url)

        self.inactive_user.refresh_from_db()
        self.assertRedirects(first_response, self.manage_users_url)
        self.assertRedirects(second_response, self.manage_users_url)
        self.assertFalse(self.inactive_user.is_active)
        self.assertEqual(User.objects.count(), initial_count)

    def test_manage_users_displays_active_and_inactive_statuses(self):
        response = self.client.get(self.manage_users_url)

        self.assertContains(response, '>Active<')
        self.assertContains(response, '>Inactive<')

    def test_active_student_and_faculty_have_deactivate_actions(self):
        response = self.client.get(self.manage_users_url)

        self.assertContains(
            response,
            f'href="{self.deactivate_url(self.student_user)}"',
        )
        self.assertContains(
            response,
            f'href="{self.deactivate_url(self.faculty_user)}"',
        )

    def test_inactive_user_has_no_deactivate_action(self):
        response = self.client.get(self.manage_users_url)

        self.assertNotContains(
            response,
            f'href="{self.deactivate_url(self.inactive_user)}"',
        )

    def test_staff_and_superuser_have_no_deactivate_actions(self):
        response = self.client.get(self.manage_users_url)

        self.assertNotContains(
            response,
            f'href="{self.deactivate_url(self.protected_staff)}"',
        )
        self.assertNotContains(
            response,
            f'href="{self.deactivate_url(self.protected_superuser)}"',
        )

    def test_inactive_user_cannot_log_in(self):
        self.client.post(self.deactivate_url(self.student_user))
        self.client.logout()

        response = self.client.post(
            reverse('users:login'),
            {
                'username': self.student_user.username,
                'password': self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class AdminAuthorizationConsistencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_role = Role.objects.create(role_name='Student')
        cls.faculty_role = Role.objects.create(role_name='Faculty')
        cls.admin_role = Role.objects.create(role_name='Admin')
        cls.staff_admin = create_staff_user(
            username='policy_staff_admin',
            email='policy-staff-admin@example.com',
        )
        cls.staff_admin.role = cls.admin_role
        cls.staff_admin.save(update_fields=['role'])
        cls.staff_student = create_staff_user(
            username='policy_staff_student',
            email='policy-staff-student@example.com',
        )
        cls.staff_student.role = cls.student_role
        cls.staff_student.save(update_fields=['role'])
        cls.student_user = User.objects.create_user(
            username='policy_student',
            email='policy-student@example.com',
            full_name='Policy Student',
            role=cls.student_role,
        )
        cls.faculty_user = User.objects.create_user(
            username='policy_faculty',
            email='policy-faculty@example.com',
            full_name='Policy Faculty',
            role=cls.faculty_role,
        )
        cls.role_only_admin = User.objects.create_user(
            username='policy_role_admin',
            email='policy-role-admin@example.com',
            full_name='Policy Role Admin',
            role=cls.admin_role,
        )
        cls.superuser = User.objects.create_superuser(
            username='policy_superuser',
            email='policy-superuser@example.com',
            full_name='Policy Superuser',
            password='Policy-Superuser-Password-9274!',
        )

    def setUp(self):
        self.dashboard_url = reverse(
            'administratordb:admin_dashboard'
        )
        self.landing_url = reverse('landing')

    def test_student_and_faculty_cannot_access_admin_dashboard(self):
        for user in (self.student_user, self.faculty_user):
            with self.subTest(username=user.username):
                self.client.force_login(user)

                response = self.client.get(self.dashboard_url)

                self.assertEqual(response.status_code, 302)

    def test_admin_role_without_staff_cannot_access_admin_dashboard(self):
        self.client.force_login(self.role_only_admin)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 302)

    def test_staff_user_with_student_role_can_access_admin_dashboard(self):
        self.client.force_login(self.staff_student)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)

    def test_superuser_without_role_can_access_admin_dashboard(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)

    def test_landing_hides_admin_link_from_role_only_admin(self):
        self.client.force_login(self.role_only_admin)

        response = self.client.get(self.landing_url)

        self.assertNotContains(response, f'href="{self.dashboard_url}"')

    def test_landing_shows_admin_link_for_staff_non_admin_role(self):
        self.client.force_login(self.staff_student)

        response = self.client.get(self.landing_url)

        self.assertContains(response, f'href="{self.dashboard_url}"')

    def test_staff_account_with_student_role_remains_edit_protected(self):
        self.client.force_login(self.staff_admin)
        edit_url = reverse(
            'administratordb:admin_edit_user',
            args=[self.staff_student.user_id],
        )

        response = self.client.post(
            edit_url,
            {'role': str(self.faculty_role.role_id)},
        )

        self.staff_student.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.staff_student.role, self.student_role)
        self.assertContains(response, 'account is protected')


class AdminResearchPapersAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='access_staff',
            email='access-staff@example.com',
        )
        cls.non_staff_user = User.objects.create_user(
            username='non_staff',
            email='non-staff@example.com',
            full_name='Test Non-Staff User',
        )
        cls.superuser = User.objects.create_superuser(
            username='test_superuser',
            email='superuser@example.com',
            full_name='Test Superuser',
        )

    def setUp(self):
        self.papers_url = reverse(
            'administratordb:admin_research_papers'
        )
        self.admin_login_url = reverse('administratordb:admin_login')

    def assert_redirected_to_admin_login(self, response):
        expected_url = (
            f'{self.admin_login_url}?next={self.papers_url}'
        )
        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
        )

    def test_anonymous_user_cannot_access_page(self):
        response = self.client.get(self.papers_url)

        self.assert_redirected_to_admin_login(response)

    def test_authenticated_non_staff_user_cannot_access_page(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(self.papers_url)

        self.assert_redirected_to_admin_login(response)

    def test_active_staff_user_can_access_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.papers_url)

        self.assertEqual(response.status_code, 200)

    def test_superuser_can_access_page(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.papers_url)

        self.assertEqual(response.status_code, 200)


class AdminResearchPapersDisplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='display_staff',
            email='display-staff@example.com',
        )
        cls.capstone = ResearchPaper.objects.create(
            title='Capstone Paper',
            abstract='Capstone abstract',
            authors='Capstone Author',
            year=2025,
            type='capstone',
            program='BSIT',
            file_path='research_papers/test-capstone.pdf',
        )
        cls.thesis = ResearchPaper.objects.create(
            title='Thesis Paper',
            abstract='Thesis abstract',
            authors='Thesis Author',
            year=2024,
            type='thesis',
            program='BSCS',
            file_path='research_papers/test-thesis.pdf',
        )

    def setUp(self):
        self.client.force_login(self.staff_user)
        self.papers_url = reverse(
            'administratordb:admin_research_papers'
        )

    def assert_filtered_papers(self, params, expected_papers):
        response = self.client.get(self.papers_url, params)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['papers']),
            expected_papers,
        )
        return response

    def test_papers_and_counts_are_displayed(self):
        response = self.client.get(
            reverse('administratordb:admin_research_papers')
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['papers']),
            [self.capstone, self.thesis],
        )
        self.assertEqual(response.context['total_papers'], 2)
        self.assertEqual(response.context['capstone_count'], 1)
        self.assertEqual(response.context['thesis_count'], 1)

        self.assertContains(response, self.capstone.title)
        self.assertContains(response, self.capstone.abstract)
        self.assertContains(response, self.capstone.authors)
        self.assertContains(response, str(self.capstone.year))
        self.assertContains(response, self.capstone.program)

    def test_paper_id_is_formatted_for_display_only(self):
        response = self.client.get(
            reverse('administratordb:admin_research_papers')
        )

        displayed_id = f'DOC-{self.capstone.paper_id:03d}'

        self.assertContains(response, displayed_id)
        self.assertIsInstance(self.capstone.paper_id, int)

    def test_type_uses_human_readable_display_value(self):
        response = self.client.get(
            reverse('administratordb:admin_research_papers')
        )

        self.assertContains(response, 'Capstone')
        self.assertContains(response, 'Thesis')

    def test_search_by_title(self):
        self.assert_filtered_papers(
            {'q': 'Capstone Paper'},
            [self.capstone],
        )

    def test_search_by_abstract(self):
        self.assert_filtered_papers(
            {'q': 'Thesis abstract'},
            [self.thesis],
        )

    def test_search_by_authors(self):
        self.assert_filtered_papers(
            {'q': 'Capstone Author'},
            [self.capstone],
        )

    def test_search_by_program(self):
        self.assert_filtered_papers(
            {'q': 'BSCS'},
            [self.thesis],
        )

    def test_search_is_case_insensitive(self):
        self.assert_filtered_papers(
            {'q': 'cApStOnE pApEr'},
            [self.capstone],
        )

    def test_type_filter(self):
        response = self.assert_filtered_papers(
            {'type': 'thesis'},
            [self.thesis],
        )

        self.assertEqual(response.context['selected_type'], 'thesis')
        self.assertContains(
            response,
            '<option value="thesis" selected>Thesis</option>',
            html=True,
        )

    def test_search_and_type_filter_work_together(self):
        self.assert_filtered_papers(
            {
                'q': 'abstract',
                'type': 'thesis',
            },
            [self.thesis],
        )

    def test_invalid_type_falls_back_to_all(self):
        response = self.assert_filtered_papers(
            {'type': 'invalid-type'},
            [self.capstone, self.thesis],
        )

        self.assertEqual(response.context['selected_type'], 'all')
        self.assertContains(
            response,
            '<option value="all" selected>All Types</option>',
            html=True,
        )

    def test_global_statistics_remain_unfiltered(self):
        response = self.assert_filtered_papers(
            {
                'q': 'No matching paper',
                'type': 'capstone',
            },
            [],
        )

        self.assertEqual(response.context['total_papers'], 2)
        self.assertEqual(response.context['capstone_count'], 1)
        self.assertEqual(response.context['thesis_count'], 1)

    def test_search_and_filter_controls_are_rendered(self):
        response = self.client.get(self.papers_url)

        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="type"')
        self.assertContains(response, 'admin-search-input')
        self.assertContains(response, 'admin-search-btn')
        self.assertContains(response, 'admin-filter-btn')

    def test_add_button_links_to_add_page(self):
        response = self.client.get(self.papers_url)
        add_url = reverse(
            'administratordb:admin_add_research_paper'
        )

        self.assertContains(response, f'href="{add_url}"')
        self.assertContains(response, 'Add Research Paper')

    def test_edit_links_point_to_correct_pages(self):
        response = self.client.get(
            reverse('administratordb:admin_research_papers')
        )

        for paper in (self.capstone, self.thesis):
            edit_url = reverse(
                'administratordb:admin_edit_research_paper',
                args=[paper.paper_id],
            )
            self.assertContains(response, f'href="{edit_url}"')

        self.assertContains(
            response,
            'class="admin-edit-link"',
            count=2,
        )

    def test_delete_links_point_to_confirmation_pages(self):
        response = self.client.get(self.papers_url)

        for paper in (self.capstone, self.thesis):
            delete_url = reverse(
                'administratordb:admin_delete_research_paper',
                args=[paper.paper_id],
            )
            self.assertContains(response, f'href="{delete_url}"')
            self.assertNotContains(
                response,
                f'action="{delete_url}"',
            )

        self.assertContains(
            response,
            'class="admin-delete-link"',
            count=2,
        )

    def test_manage_research_links_to_papers_page(self):
        response = self.client.get(
            reverse('administratordb:admin_research')
        )
        papers_url = reverse(
            'administratordb:admin_research_papers'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{papers_url}"')


class AdminResearchPapersPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='pagination_staff',
            email='pagination-staff@example.com',
        )
        cls.papers = []

        for index in range(12):
            cls.papers.append(
                ResearchPaper.objects.create(
                    title=f'Pagination Paper {index:02d}',
                    abstract=f'Pagination target abstract {index:02d}',
                    authors=f'Pagination Author {index:02d}',
                    year=2020 + index,
                    type='capstone',
                    program='BSIT',
                    file_path=(
                        f'research_papers/pagination-{index}.pdf'
                    ),
                )
            )

    def setUp(self):
        self.client.force_login(self.staff_user)
        self.papers_url = reverse(
            'administratordb:admin_research_papers'
        )

    def test_pagination_shows_ten_papers_per_page(self):
        first_response = self.client.get(self.papers_url)
        first_page = first_response.context['papers']

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_page.paginator.per_page, 10)
        self.assertEqual(first_page.number, 1)
        self.assertEqual(list(first_page), self.papers[:10])
        self.assertContains(first_response, 'Page 1 of 2')
        self.assertContains(first_response, 'Next')
        self.assertNotContains(first_response, 'Previous')

        second_response = self.client.get(
            self.papers_url,
            {'page': 2},
        )
        second_page = second_response.context['papers']

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_page.number, 2)
        self.assertEqual(list(second_page), self.papers[10:])
        self.assertContains(second_response, 'Page 2 of 2')
        self.assertContains(second_response, 'Previous')
        self.assertNotContains(second_response, 'Next')

    def test_invalid_and_out_of_range_pages_are_handled_safely(self):
        invalid_response = self.client.get(
            self.papers_url,
            {'page': 'not-a-number'},
        )
        out_of_range_response = self.client.get(
            self.papers_url,
            {'page': 999},
        )

        self.assertEqual(invalid_response.status_code, 200)
        self.assertEqual(
            invalid_response.context['papers'].number,
            1,
        )
        self.assertEqual(out_of_range_response.status_code, 200)
        self.assertEqual(
            out_of_range_response.context['papers'].number,
            2,
        )

    def test_pagination_links_preserve_search_and_type(self):
        first_response = self.client.get(
            self.papers_url,
            {
                'q': 'pagination target',
                'type': 'capstone',
            },
        )

        self.assertContains(
            first_response,
            (
                'href="?q=pagination%20target&amp;type=capstone'
                '&amp;page=2"'
            ),
        )

        second_response = self.client.get(
            self.papers_url,
            {
                'q': 'pagination target',
                'type': 'capstone',
                'page': 2,
            },
        )

        self.assertContains(
            second_response,
            (
                'href="?q=pagination%20target&amp;type=capstone'
                '&amp;page=1"'
            ),
        )


class AdminAddResearchPaperAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='add_access_staff',
            email='add-access-staff@example.com',
        )
        cls.non_staff_user = User.objects.create_user(
            username='add_non_staff',
            email='add-non-staff@example.com',
            full_name='Add Non-Staff User',
        )

    def setUp(self):
        self.add_url = reverse(
            'administratordb:admin_add_research_paper'
        )
        self.admin_login_url = reverse('administratordb:admin_login')

    def assert_redirected_to_admin_login(self, response):
        expected_url = (
            f'{self.admin_login_url}?next={self.add_url}'
        )
        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
        )

    def test_anonymous_user_cannot_access_add_page(self):
        response = self.client.get(self.add_url)

        self.assert_redirected_to_admin_login(response)

    def test_authenticated_non_staff_user_cannot_access_add_page(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(self.add_url)

        self.assert_redirected_to_admin_login(response)

    def test_staff_user_can_access_add_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.add_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'administratordb/admin-add-research.html',
        )
        self.assertIn('form', response.context)


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.InMemoryStorage',
        },
        'staticfiles': {
            'BACKEND': (
                'whitenoise.storage.CompressedManifestStaticFilesStorage'
            ),
        },
    }
)
class AdminAddResearchPaperCreateTests(TestCase):
    max_upload_bytes = 10 * 1024 * 1024
    pdf_header = b'%PDF-1.4\n'

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='add_create_staff',
            email='add-create-staff@example.com',
        )
        cls.category_one = Category.objects.create(
            category_name='Artificial Intelligence',
        )
        cls.category_two = Category.objects.create(
            category_name='Information Systems',
        )

    def setUp(self):
        self.client.force_login(self.staff_user)
        self.add_url = reverse(
            'administratordb:admin_add_research_paper'
        )
        self.papers_url = reverse(
            'administratordb:admin_research_papers'
        )

    def valid_post_data(self):
        return {
            'title': 'New Research Paper',
            'abstract': 'New research paper abstract.',
            'authors': 'First Author, Second Author',
            'year': 2025,
            'type': 'thesis',
            'program': 'Computer Science',
            'file_path': SimpleUploadedFile(
                'new-paper.pdf',
                b'%PDF-1.4\n% test file\n',
                content_type='application/pdf',
            ),
            'categories': [
                str(self.category_one.pk),
                str(self.category_two.pk),
            ],
        }

    def test_valid_post_creates_paper_and_category_relationships(self):
        for index in range(10):
            ResearchPaper.objects.create(
                title=f'Existing Paper {index:02d}',
                abstract=f'Existing abstract {index:02d}',
                authors=f'Existing Author {index:02d}',
                year=2025,
                type='capstone',
                program='BSIT',
                file_path=(
                    f'research_papers/existing-{index}.pdf'
                ),
            )

        initial_count = ResearchPaper.objects.count()

        response = self.client.post(
            self.add_url,
            self.valid_post_data(),
        )

        self.assertEqual(
            ResearchPaper.objects.count(),
            initial_count + 1,
        )

        paper = ResearchPaper.objects.get(
            title='New Research Paper'
        )

        self.assertEqual(
            response.status_code,
            302,
        )
        self.assertRedirects(
            response,
            f'{self.papers_url}?page=2',
            fetch_redirect_response=False,
        )
        self.assertEqual(
            paper.abstract,
            'New research paper abstract.',
        )
        self.assertEqual(
            paper.authors,
            'First Author, Second Author',
        )
        self.assertEqual(paper.year, 2025)
        self.assertEqual(paper.type, 'thesis')
        self.assertEqual(paper.program, 'Computer Science')
        self.assertEqual(paper.user, self.staff_user)
        self.assertEqual(
            paper.file_path.name,
            'research_papers/new-paper.pdf',
        )
        self.assertSetEqual(
            set(paper.categories.all()),
            {self.category_one, self.category_two},
        )
        self.assertEqual(
            PaperCategory.objects.filter(paper=paper).count(),
            2,
        )
        self.assertEqual(Category.objects.count(), 2)

        list_response = self.client.get(response.url)

        self.assertContains(
            list_response,
            'New Research Paper',
        )

    def test_invalid_form_does_not_create_paper(self):
        data = self.valid_post_data()
        data['title'] = ''
        initial_count = ResearchPaper.objects.count()

        response = self.client.post(self.add_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ResearchPaper.objects.count(),
            initial_count,
        )
        self.assertIn('title', response.context['form'].errors)
        self.assertTemplateUsed(
            response,
            'administratordb/admin-add-research.html',
        )

    def assert_upload_rejected(self, uploaded_file=None, remove=False):
        data = self.valid_post_data()
        if remove:
            del data['file_path']
        else:
            data['file_path'] = uploaded_file
        initial_count = ResearchPaper.objects.count()

        response = self.client.post(self.add_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('file_path', response.context['form'].errors)
        self.assertEqual(ResearchPaper.objects.count(), initial_count)

    def test_missing_file_is_rejected(self):
        self.assert_upload_rejected(remove=True)

    def test_non_pdf_extension_is_rejected(self):
        self.assert_upload_rejected(
            SimpleUploadedFile(
                'notes.txt',
                b'plain text, not a pdf',
                content_type='text/plain',
            )
        )

    def test_pdf_extension_with_non_pdf_content_is_rejected(self):
        # Fails if validation only checks the file extension.
        self.assert_upload_rejected(
            SimpleUploadedFile(
                'fake.pdf',
                b'this is definitely not a pdf',
                content_type='application/pdf',
            )
        )

    def test_file_over_10mb_is_rejected(self):
        self.assert_upload_rejected(
            SimpleUploadedFile(
                'too-big.pdf',
                self.pdf_header
                + b'0' * (self.max_upload_bytes - len(self.pdf_header) + 1),
                content_type='application/pdf',
            )
        )


class AdminEditResearchPaperAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='edit_access_staff',
            email='edit-access-staff@example.com',
        )
        cls.non_staff_user = User.objects.create_user(
            username='edit_non_staff',
            email='edit-non-staff@example.com',
            full_name='Edit Non-Staff User',
        )
        cls.paper = ResearchPaper.objects.create(
            title='Edit Access Paper',
            abstract='Edit access abstract.',
            authors='Edit Access Author',
            year=2024,
            type='capstone',
            program='Information Technology WMA',
            file_path='research_papers/edit-access.pdf',
            user=cls.staff_user,
        )

    def setUp(self):
        self.edit_url = reverse(
            'administratordb:admin_edit_research_paper',
            args=[self.paper.paper_id],
        )
        self.admin_login_url = reverse('administratordb:admin_login')

    def assert_redirected_to_admin_login(self, response):
        expected_url = (
            f'{self.admin_login_url}?next={self.edit_url}'
        )
        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
        )

    def test_anonymous_user_cannot_access_edit_page(self):
        response = self.client.get(self.edit_url)

        self.assert_redirected_to_admin_login(response)

    def test_authenticated_non_staff_user_cannot_access_edit_page(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(self.edit_url)

        self.assert_redirected_to_admin_login(response)

    def test_staff_user_can_access_edit_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'administratordb/admin-edit-research.html',
        )
        self.assertEqual(response.context['paper'], self.paper)
        self.assertIn('form', response.context)

    def test_nonexistent_paper_returns_404(self):
        self.client.force_login(self.staff_user)
        missing_url = reverse(
            'administratordb:admin_edit_research_paper',
            args=[999999],
        )

        response = self.client.get(missing_url)

        self.assertEqual(response.status_code, 404)


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.InMemoryStorage',
        },
        'staticfiles': {
            'BACKEND': (
                'whitenoise.storage.CompressedManifestStaticFilesStorage'
            ),
        },
    }
)
class AdminEditResearchPaperUpdateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.original_uploader = create_staff_user(
            username='original_uploader',
            email='original-uploader@example.com',
        )
        cls.editing_staff = create_staff_user(
            username='editing_staff',
            email='editing-staff@example.com',
        )
        cls.category_one = Category.objects.create(
            category_name='Artificial Intelligence',
        )
        cls.category_two = Category.objects.create(
            category_name='Gamification',
        )
        cls.category_three = Category.objects.create(
            category_name='Information Systems',
        )
        cls.paper = ResearchPaper.objects.create(
            title='Original Research Paper',
            abstract='Original abstract.',
            authors='Original Author',
            year=2024,
            type='capstone',
            program='Information Technology WMA',
            file_path='research_papers/original-paper.pdf',
            user=cls.original_uploader,
        )
        cls.paper.categories.set(
            [cls.category_one, cls.category_two]
        )

    def setUp(self):
        self.client.force_login(self.editing_staff)
        self.edit_url = reverse(
            'administratordb:admin_edit_research_paper',
            args=[self.paper.paper_id],
        )
        self.papers_url = reverse(
            'administratordb:admin_research_papers'
        )

    def valid_post_data(self):
        return {
            'title': 'Updated Research Paper',
            'abstract': 'Updated abstract.',
            'authors': 'Updated Author One, Updated Author Two',
            'year': 2025,
            'type': 'thesis',
            'program': 'Computer Science',
            'categories': [
                str(self.category_two.pk),
                str(self.category_three.pk),
            ],
        }

    def test_existing_fields_and_categories_populate(self):
        response = self.client.get(self.edit_url)
        form = response.context['form']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(form.initial['title'], self.paper.title)
        self.assertEqual(form.initial['abstract'], self.paper.abstract)
        self.assertEqual(form.initial['authors'], self.paper.authors)
        self.assertEqual(form.initial['year'], self.paper.year)
        self.assertEqual(form.initial['type'], self.paper.type)
        self.assertEqual(form.initial['program'], self.paper.program)
        self.assertEqual(
            form.initial['file_path'].name,
            self.paper.file_path.name,
        )

        selected_category_ids = {
            str(checkbox.data['value'])
            for checkbox in form['categories']
            if checkbox.data['selected']
        }
        self.assertSetEqual(
            selected_category_ids,
            {
                str(self.category_one.pk),
                str(self.category_two.pk),
            },
        )

    def test_valid_post_updates_same_paper_and_relationships(self):
        initial_count = ResearchPaper.objects.count()
        original_paper_id = self.paper.paper_id
        original_uploader_id = self.paper.user_id

        response = self.client.post(
            self.edit_url,
            self.valid_post_data(),
        )

        self.assertRedirects(
            response,
            self.papers_url,
            fetch_redirect_response=False,
        )
        self.assertEqual(ResearchPaper.objects.count(), initial_count)

        self.paper.refresh_from_db()

        self.assertEqual(self.paper.paper_id, original_paper_id)
        self.assertEqual(self.paper.title, 'Updated Research Paper')
        self.assertEqual(self.paper.abstract, 'Updated abstract.')
        self.assertEqual(
            self.paper.authors,
            'Updated Author One, Updated Author Two',
        )
        self.assertEqual(self.paper.year, 2025)
        self.assertEqual(self.paper.type, 'thesis')
        self.assertEqual(self.paper.program, 'Computer Science')
        self.assertEqual(self.paper.user_id, original_uploader_id)
        self.assertSetEqual(
            set(self.paper.categories.all()),
            {self.category_two, self.category_three},
        )
        self.assertEqual(
            PaperCategory.objects.filter(paper=self.paper).count(),
            2,
        )

    def test_existing_file_is_preserved_without_replacement(self):
        original_file_name = self.paper.file_path.name

        response = self.client.post(
            self.edit_url,
            self.valid_post_data(),
        )

        self.assertRedirects(
            response,
            self.papers_url,
            fetch_redirect_response=False,
        )
        self.paper.refresh_from_db()
        self.assertEqual(self.paper.file_path.name, original_file_name)

    def test_replacement_file_updates_file_path(self):
        original_file_name = self.paper.file_path.name
        data = self.valid_post_data()
        data['file_path'] = SimpleUploadedFile(
            'replacement-paper.pdf',
            b'%PDF-1.4\n% replacement test file\n',
            content_type='application/pdf',
        )

        response = self.client.post(self.edit_url, data)

        self.assertRedirects(
            response,
            self.papers_url,
            fetch_redirect_response=False,
        )
        self.paper.refresh_from_db()
        self.assertNotEqual(
            self.paper.file_path.name,
            original_file_name,
        )
        self.assertEqual(
            self.paper.file_path.name,
            'research_papers/replacement-paper.pdf',
        )

    def test_replacement_file_over_10mb_is_rejected(self):
        original_file_name = self.paper.file_path.name
        header = b'%PDF-1.4\n'
        data = self.valid_post_data()
        data['file_path'] = SimpleUploadedFile(
            'too-big.pdf',
            header + b'0' * (10 * 1024 * 1024 - len(header) + 1),
            content_type='application/pdf',
        )

        response = self.client.post(self.edit_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('file_path', response.context['form'].errors)
        self.paper.refresh_from_db()
        self.assertEqual(self.paper.file_path.name, original_file_name)

    def test_invalid_post_does_not_update_paper_or_categories(self):
        data = self.valid_post_data()
        data['title'] = ''
        initial_count = ResearchPaper.objects.count()
        original_values = {
            'title': self.paper.title,
            'abstract': self.paper.abstract,
            'authors': self.paper.authors,
            'year': self.paper.year,
            'type': self.paper.type,
            'program': self.paper.program,
            'file_path': self.paper.file_path.name,
            'user_id': self.paper.user_id,
        }
        original_categories = set(self.paper.categories.all())

        response = self.client.post(self.edit_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'administratordb/admin-edit-research.html',
        )
        self.assertIn('title', response.context['form'].errors)
        self.assertEqual(ResearchPaper.objects.count(), initial_count)

        self.paper.refresh_from_db()

        for field_name, original_value in original_values.items():
            self.assertEqual(
                getattr(self.paper, field_name),
                original_value,
            )
        self.assertSetEqual(
            set(self.paper.categories.all()),
            original_categories,
        )


class AdminDeleteResearchPaperAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='delete_access_staff',
            email='delete-access-staff@example.com',
        )
        cls.non_staff_user = User.objects.create_user(
            username='delete_non_staff',
            email='delete-non-staff@example.com',
            full_name='Delete Non-Staff User',
        )
        cls.paper = ResearchPaper.objects.create(
            title='Delete Access Paper',
            abstract='Delete access abstract.',
            authors='Delete Access Author',
            year=2026,
            type='capstone',
            program='Information Technology WMA',
            file_path='research_papers/delete-access.pdf',
            user=cls.staff_user,
        )

    def setUp(self):
        self.delete_url = reverse(
            'administratordb:admin_delete_research_paper',
            args=[self.paper.paper_id],
        )
        self.admin_login_url = reverse('administratordb:admin_login')

    def assert_redirected_to_admin_login(self, response):
        expected_url = (
            f'{self.admin_login_url}?next={self.delete_url}'
        )
        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
        )

    def test_anonymous_get_is_blocked(self):
        response = self.client.get(self.delete_url)

        self.assert_redirected_to_admin_login(response)
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=self.paper.paper_id
            ).exists()
        )

    def test_anonymous_post_is_blocked(self):
        response = self.client.post(self.delete_url)

        self.assert_redirected_to_admin_login(response)
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=self.paper.paper_id
            ).exists()
        )

    def test_authenticated_non_staff_get_is_blocked(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(self.delete_url)

        self.assert_redirected_to_admin_login(response)
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=self.paper.paper_id
            ).exists()
        )

    def test_authenticated_non_staff_post_is_blocked(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.post(self.delete_url)

        self.assert_redirected_to_admin_login(response)
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=self.paper.paper_id
            ).exists()
        )

    def test_staff_get_renders_confirmation_without_deleting(self):
        self.client.force_login(self.staff_user)
        initial_count = ResearchPaper.objects.count()

        response = self.client.get(self.delete_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'administratordb/admin-delete-research.html',
        )
        self.assertEqual(response.context['paper'], self.paper)
        self.assertContains(
            response,
            f'DOC-{self.paper.paper_id:03d}',
        )
        self.assertContains(response, self.paper.title)
        self.assertEqual(
            ResearchPaper.objects.count(),
            initial_count,
        )
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=self.paper.paper_id
            ).exists()
        )

    def test_nonexistent_paper_get_returns_404(self):
        self.client.force_login(self.staff_user)
        missing_url = reverse(
            'administratordb:admin_delete_research_paper',
            args=[999999],
        )

        response = self.client.get(missing_url)

        self.assertEqual(response.status_code, 404)

    def test_nonexistent_paper_post_returns_404(self):
        self.client.force_login(self.staff_user)
        missing_url = reverse(
            'administratordb:admin_delete_research_paper',
            args=[999999],
        )

        response = self.client.post(missing_url)

        self.assertEqual(response.status_code, 404)


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.InMemoryStorage',
        },
        'staticfiles': {
            'BACKEND': (
                'whitenoise.storage.CompressedManifestStaticFilesStorage'
            ),
        },
    }
)
class AdminDeleteResearchPaperBehaviorTests(TestCase):
    password = 'Delete-Confirm-Password-9274!'

    @classmethod
    def setUpTestData(cls):
        cls.uploader = create_staff_user(
            username='delete_uploader',
            email='delete-uploader@example.com',
        )
        cls.deleting_staff = create_staff_user(
            username='deleting_staff',
            email='deleting-staff@example.com',
        )
        cls.deleting_staff.set_password(cls.password)
        cls.deleting_staff.save(update_fields=['password'])
        cls.category = Category.objects.create(
            category_name='Artificial Intelligence',
        )
        cls.target_paper = ResearchPaper.objects.create(
            title='Research Paper to Delete',
            abstract='Delete target abstract.',
            authors='Delete Target Author',
            year=2026,
            type='thesis',
            program='Computer Science',
            file_path=SimpleUploadedFile(
                'delete-target.pdf',
                b'%PDF-1.4\n% delete storage test file\n',
                content_type='application/pdf',
            ),
            user=cls.uploader,
        )
        cls.other_paper = ResearchPaper.objects.create(
            title='Research Paper to Keep',
            abstract='Surviving paper abstract.',
            authors='Surviving Author',
            year=2025,
            type='capstone',
            program='Information Systems',
            file_path='research_papers/keep-paper.pdf',
            user=cls.uploader,
        )
        cls.target_paper.categories.add(cls.category)
        cls.embedding = Embedding.objects.create(
            paper=cls.target_paper,
            vector_data=b'test embedding',
        )
        cls.input_similarity = SimilarityResult.objects.create(
            input_paper=cls.target_paper,
            compared_paper=cls.other_paper,
            similarity_score=0.91,
            rank_order=1,
        )
        cls.compared_similarity = SimilarityResult.objects.create(
            input_paper=cls.other_paper,
            compared_paper=cls.target_paper,
            similarity_score=0.82,
            rank_order=2,
        )
        cls.feature = FFM.objects.create(
            feature_name='Delete Cascade Feature',
            domain='Delete Tests',
        )
        cls.related_ffm_result = FFMResult.objects.create(
            similarity=cls.input_similarity,
        )
        cls.related_ffm_entry = FFMEntry.objects.create(
            ffm_result=cls.related_ffm_result,
            paper=cls.other_paper,
            feature=cls.feature,
            is_present=True,
        )
        cls.unrelated_similarity = SimilarityResult.objects.create(
            input_paper=cls.other_paper,
            compared_paper=cls.other_paper,
            similarity_score=1.0,
            rank_order=1,
        )
        cls.unrelated_ffm_result = FFMResult.objects.create(
            similarity=cls.unrelated_similarity,
        )
        cls.direct_paper_entry = FFMEntry.objects.create(
            ffm_result=cls.unrelated_ffm_result,
            paper=cls.target_paper,
            feature=cls.feature,
            is_present=False,
        )

    def setUp(self):
        self.client.force_login(self.deleting_staff)
        self.delete_url = reverse(
            'administratordb:admin_delete_research_paper',
            args=[self.target_paper.paper_id],
        )
        self.papers_url = reverse(
            'administratordb:admin_research_papers'
        )

    def test_staff_post_deletes_only_selected_paper(self):
        initial_count = ResearchPaper.objects.count()
        target_paper_id = self.target_paper.paper_id
        other_paper_id = self.other_paper.paper_id
        uploader_id = self.uploader.pk
        category_id = self.category.pk

        response = self.client.post(
            self.delete_url,
            {'password': self.password},
        )

        self.assertRedirects(
            response,
            self.papers_url,
            fetch_redirect_response=False,
        )
        self.assertEqual(
            ResearchPaper.objects.count(),
            initial_count - 1,
        )
        self.assertFalse(
            ResearchPaper.objects.filter(
                paper_id=target_paper_id
            ).exists()
        )
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=other_paper_id
            ).exists()
        )
        self.assertTrue(
            User.objects.filter(pk=uploader_id).exists()
        )
        self.assertTrue(
            Category.objects.filter(pk=category_id).exists()
        )
        self.assertFalse(
            PaperCategory.objects.filter(
                paper_id=target_paper_id
            ).exists()
        )

    def test_related_records_follow_declared_cascades(self):
        embedding_id = self.embedding.pk
        input_similarity_id = self.input_similarity.pk
        compared_similarity_id = self.compared_similarity.pk
        related_ffm_result_id = self.related_ffm_result.pk
        related_ffm_entry_id = self.related_ffm_entry.pk
        direct_paper_entry_id = self.direct_paper_entry.pk
        unrelated_similarity_id = self.unrelated_similarity.pk
        unrelated_ffm_result_id = self.unrelated_ffm_result.pk

        self.client.post(
            self.delete_url,
            {'password': self.password},
        )

        self.assertFalse(
            Embedding.objects.filter(pk=embedding_id).exists()
        )
        self.assertFalse(
            SimilarityResult.objects.filter(
                pk=input_similarity_id
            ).exists()
        )
        self.assertFalse(
            SimilarityResult.objects.filter(
                pk=compared_similarity_id
            ).exists()
        )
        self.assertFalse(
            FFMResult.objects.filter(
                pk=related_ffm_result_id
            ).exists()
        )
        self.assertFalse(
            FFMEntry.objects.filter(
                pk=related_ffm_entry_id
            ).exists()
        )
        self.assertFalse(
            FFMEntry.objects.filter(
                pk=direct_paper_entry_id
            ).exists()
        )
        self.assertTrue(
            SimilarityResult.objects.filter(
                pk=unrelated_similarity_id
            ).exists()
        )
        self.assertTrue(
            FFMResult.objects.filter(
                pk=unrelated_ffm_result_id
            ).exists()
        )

    def test_physical_uploaded_file_remains_after_database_delete(self):
        storage = self.target_paper.file_path.storage
        file_name = self.target_paper.file_path.name

        self.assertTrue(storage.exists(file_name))

        self.client.post(
            self.delete_url,
            {'password': self.password},
        )

        self.assertFalse(
            ResearchPaper.objects.filter(
                paper_id=self.target_paper.paper_id
            ).exists()
        )
        self.assertTrue(storage.exists(file_name))

    def test_wrong_password_does_not_delete_paper(self):
        response = self.client.post(
            self.delete_url,
            {'password': 'Wrong-Password-0000!'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'administratordb/admin-delete-research.html',
        )
        self.assertContains(response, 'Incorrect password')
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=self.target_paper.paper_id
            ).exists()
        )
        self.assertTrue(
            Embedding.objects.filter(pk=self.embedding.pk).exists()
        )

    def test_missing_password_does_not_delete_paper(self):
        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Incorrect password')
        self.assertTrue(
            ResearchPaper.objects.filter(
                paper_id=self.target_paper.paper_id
            ).exists()
        )

        
class AdminResearchPapersEmptyStateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='empty_state_staff',
            email='empty-state-staff@example.com',
        )

    def setUp(self):
        self.client.force_login(self.staff_user)

    def test_empty_state_is_displayed_when_no_papers_exist(self):
        response = self.client.get(
            reverse('administratordb:admin_research_papers')
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_papers'], 0)
        self.assertEqual(response.context['capstone_count'], 0)
        self.assertEqual(response.context['thesis_count'], 0)
        self.assertContains(response, 'No research papers found.')


class AdminFeedbackAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='feedback_staff',
            email='feedback-staff@example.com',
        )
        cls.non_staff_user = User.objects.create_user(
            username='feedback_non_staff',
            email='feedback-non-staff@example.com',
            full_name='Test Non-Staff User',
        )

    def setUp(self):
        self.feedback_url = reverse('administratordb:admin_feedback')

    def test_staff_can_access_feedback_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.feedback_url)

        self.assertEqual(response.status_code, 200)

    def test_non_staff_cannot_access_feedback_page(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(self.feedback_url)

        self.assertNotEqual(response.status_code, 200)


class AdminFeedbackDisplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='feedback_display_staff',
            email='feedback-display-staff@example.com',
        )
        cls.user = User.objects.create_user(
            username='feedback_author',
            email='feedback-author@example.com',
            full_name='Feedback Author',
        )
        cls.fb1 = Feedback.objects.create(
            rating=4,
            message='Great system!',
            user=cls.user,
        )
        cls.fb2 = Feedback.objects.create(
            rating=2,
            message='',
            user=cls.user,
        )
        cls.fb3 = Feedback.objects.create(
            rating=5,
            message='Love it!',
            user=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.staff_user)

    def test_feedbacks_in_context(self):
        response = self.client.get(
            reverse('administratordb:admin_feedback')
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('feedbacks', response.context)
        self.assertEqual(
            list(response.context['feedbacks']),
            [self.fb1, self.fb2, self.fb3],
        )

    def test_total_feedback_is_correct(self):
        response = self.client.get(
            reverse('administratordb:admin_feedback')
        )

        self.assertEqual(response.context['total_feedback'], 3)

    def test_average_rating_is_correct(self):
        response = self.client.get(
            reverse('administratordb:admin_feedback')
        )

        # (4 + 2 + 5) / 3 = 3.666...
        self.assertAlmostEqual(
            float(response.context['average_rating']),
            11 / 3,
            places=2,
        )

    def test_messages_count_is_correct(self):
        response = self.client.get(
            reverse('administratordb:admin_feedback')
        )

        # fb2 has empty message, so messages_count = 2
        self.assertEqual(response.context['messages_count'], 2)


class AdminDeleteFeedbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = create_staff_user(
            username='delete_fb_staff',
            email='delete-fb-staff@example.com',
        )
        cls.non_staff_user = User.objects.create_user(
            username='delete_fb_non_staff',
            email='delete-fb-non-staff@example.com',
            full_name='Test Non-Staff User',
        )
        cls.user = User.objects.create_user(
            username='delete_fb_author',
            email='delete-fb-author@example.com',
            full_name='Delete FB Author',
        )

    def setUp(self):
        self.feedback = Feedback.objects.create(
            rating=3,
            message='Some feedback',
            user=self.user,
        )
        self.delete_url = reverse(
            'administratordb:admin_delete_feedback',
            args=[self.feedback.feedback_id],
        )

    def test_staff_can_delete_feedback_via_post(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 302)

    def test_feedback_is_removed_after_delete(self):
        self.client.force_login(self.staff_user)

        self.client.post(self.delete_url)

        self.assertFalse(
            Feedback.objects.filter(pk=self.feedback.feedback_id).exists()
        )

    def test_get_request_does_not_delete_feedback(self):
        self.client.force_login(self.staff_user)

        self.client.get(self.delete_url)

        self.assertTrue(
            Feedback.objects.filter(pk=self.feedback.feedback_id).exists()
        )