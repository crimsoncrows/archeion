from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, Role


class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'email', 'full_name', 'role', 'is_staff')
    ordering = ('username',)

    # Show password as read-only (the hash) — no editable field
    readonly_fields = ('password',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),  # password now read-only
        ('Personal Info', {'fields': ('full_name', 'email', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'full_name', 'role', 'password1', 'password2'),
        }),
    )


admin.site.register(User, UserAdmin)
admin.site.register(Role)