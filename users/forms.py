import re
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .models import User


USERNAME_RE = re.compile(r'^(?=.*[a-zA-Z0-9])[a-zA-Z0-9_]{3,30}$')
FULLNAME_RE = re.compile(r"^(?=.*[^\W\d_])(?:[^\W\d_]|[\s.'\-]){2,100}$")

class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "inactive": "Your account has been deactivated. Please contact the administrator.",
    }

    def clean_username(self):
        # Match SignUpForm, which stores usernames lowercased
        return self.cleaned_data.get("username", "").strip().lower()

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            UserModel = get_user_model()
            try:
                user = UserModel._default_manager.get_by_natural_key(username)
            except UserModel.DoesNotExist:
                user = None

            # Only reveal "deactivated" when the password is correct
            if user and not user.is_active and user.check_password(password):
                raise ValidationError(self.error_messages["inactive"], code="inactive")

        return super().clean()

class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['full_name', 'username', 'email']

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if len(full_name) < 2:
            raise ValidationError("Full name must be at least 2 characters.")
        if not FULLNAME_RE.match(full_name):
            raise ValidationError(
                "Full name can only contain letters, spaces, periods, and hyphens."
            )
        return full_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()

        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("Invalid email address.")

        return email


    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if len(username) < 3 or len(username) > 30:
            raise ValidationError("Username must be 3 to 30 characters long.")
        if not USERNAME_RE.match(username):
            raise ValidationError(
                "Username can only contain letters, numbers, and underscores."
            )
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # Pass a temporary user so UserAttributeSimilarityValidator can
        # reject passwords that are too close to the username/email/name.
        temp_user = User(
            username=self.cleaned_data.get('username', ''),
            email=self.cleaned_data.get('email', ''),
            full_name=self.cleaned_data.get('full_name', ''),
        )
        password_validation.validate_password(password, temp_user)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")

        return cleaned_data


class ProfileEditForm(forms.Form):
    """Form for editing the authenticated user's profile."""

    fullname = forms.CharField(
        max_length=150,
        min_length=2,
        required=True,
        error_messages={'required': 'Full name is required.'},
    )
    username = forms.CharField(
        max_length=100,
        min_length=2,
        required=True,
        error_messages={'required': 'Username is required.'},
    )
    email = forms.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.',
        },
    )
    current_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput,
        error_messages={'required': 'Current password is required to save changes.'},
    )
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_fullname(self):
        fullname = self.cleaned_data.get('fullname', '').strip()
        if not fullname:
            raise ValidationError('Full name is required.')
        if not FULLNAME_RE.match(fullname):
            raise ValidationError(
                'Full Name can only contain letters.'
            )
        return fullname

    def clean_username(self): 
        username = self.cleaned_data['username'].strip().lower()
        if not username:
            raise ValidationError('Username is required.')
        if not USERNAME_RE.match(username):
            raise ValidationError(
                'Username can only contain letters, numbers, and underscores.'
            )
        if User.objects.filter(username=username).exclude(
            pk=self.user.pk
        ).exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise ValidationError('Email is required.')
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError('Please enter a valid email address.')

        if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise ValidationError('This email address is already in use.')

        return email

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password', '')
        if not self.user.check_password(current_password):
            raise ValidationError('Incorrect current password.')
        return current_password

    def clean_new_password(self):
        new_password = self.cleaned_data.get('new_password', '')
        if new_password:
            password_validation.validate_password(new_password, self.user)
        return new_password