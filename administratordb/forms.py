from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from papers.models import Category, ResearchPaper  
from users.forms import FULLNAME_RE, USERNAME_RE
from users.models import Role, User


ASSIGNABLE_ROLE_NAMES = ('Student', 'Faculty')


PROGRAM_CHOICES = [
    ('IT-WMA', 'Bachelor of Science in Information Technology major in Web and Mobile Application'),
    ('IT-TSM', 'Bachelor of Science in Information Technology major in Technical Service Management'),
    ('IT-NA',  'Bachelor of Science in Information Technology major in Network Administration'),
    ('CS',     'Bachelor of Science in Computer Science'),
    ('IS',     'Bachelor of Science in Information Systems'),
]   


class AssignableRoleFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Role.objects.filter(
            role_name__in=ASSIGNABLE_ROLE_NAMES
        ).order_by('role_id')
        self.fields['role'].required = True
        self.fields['role'].empty_label = 'Select role'


class AdminUserCreationForm(AssignableRoleFormMixin, forms.ModelForm):
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'autocomplete': 'new-password',
            }
        ),
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control',
                'autocomplete': 'new-password',
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            'full_name',
            'username',
            'email',
            'password',
            'confirm_password',
            'role',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(
                attrs={
                    'class': 'form-select admin-role-select',
                    'style': 'max-width: 100%;',
                }
            ),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not FULLNAME_RE.match(full_name):
            raise ValidationError(
                'Full Name can only contain letters and more than 2 characters.'
            )
        return full_name

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if not USERNAME_RE.match(username):
            raise ValidationError(
                'Username can only contain letters, numbers, and underscores.'
            )
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error(
                'confirm_password',
                'Passwords do not match.',
            )

        return cleaned_data

    def _post_clean(self):
        super()._post_clean()
        # ModelForm has populated the unsaved instance from cleaned fields.
        password = self.cleaned_data.get('password')
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error('password', error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = User.objects.normalize_email(user.email)
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()

        return user


class AdminUserEditForm(AssignableRoleFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'username', 'email', 'role']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(
                attrs={
                    'class': 'form-select admin-role-select',
                    'style': 'max-width: 100%;',
                }
            ),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not FULLNAME_RE.match(full_name):
            raise ValidationError(
                'Full Name can only contain letters and more than 2 characters.'
            )
        return full_name

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if not USERNAME_RE.match(username):
            raise ValidationError(
                'Username can only contain letters, numbers, and underscores.'
            )
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        return User.objects.normalize_email(email)


class ResearchPaperForm(forms.ModelForm):
    year = forms.TypedChoiceField(
        choices=[
            ('', 'Select year'),
            (2021, '2021'),
            (2022, '2022'),
            (2023, '2023'),
            (2024, '2024'),
            (2025, '2025'),
            (2026, '2026'),
        ],
        coerce=int,
        widget=forms.Select(
            attrs={
                'class': 'form-select admin-role-select',
                'style': 'max-width: 100%;',
            }
        ),
    )
    program = forms.ChoiceField(
        choices=[
            ('', 'Select program'),
            *PROGRAM_CHOICES,
        ],
        widget=forms.Select(
            attrs={
                'class': 'form-select admin-role-select',
                'style': 'max-width: 100%;',
            }
        ),
    )

    class Meta:
        model = ResearchPaper
        fields = [
            'title',
            'abstract',
            'authors',
            'year',
            'type',
            'program',
            'file_path',
            'categories',
        ]
        labels = {
            'authors': 'Author/s',
            'type': 'Document Type',
            'file_path': 'Research paper file',
        }
        help_texts = {
            'categories': 'Select one or more existing categories.',
        }
        widgets = {
            'title': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'abstract': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4}
            ),
            'authors': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'type': forms.Select(
                attrs={
                    'class': 'form-select admin-role-select',
                    'style': 'max-width: 100%;',
                }
            ),
            'file_path': forms.ClearableFileInput(
                attrs={'class': 'form-control'}
            ),
            'categories': forms.CheckboxSelectMultiple(
                attrs={'class': 'form-check-input'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file_path'].required = False
        self.fields['categories'].required = False


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['category_name']
        labels = {'category_name': 'Category Name'}
        widgets = {
            'category_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_category_name(self):
        name = ' '.join(self.cleaned_data.get('category_name', '').split())
        if not name:
            raise ValidationError('Category name is required.')

        # Case-insensitive duplicate check (TiDB collation is case-sensitive)
        duplicates = Category.objects.annotate(
            name_lower=Lower('category_name')
        ).filter(name_lower=name.lower())
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError('A category with this name already exists.')

        return name