from functools import wraps

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Exists, OuterRef, Q
from django.db.models.functions import Lower
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit  # use rate limit to avoid spam abuse/bruteforce. can be used on ai/sbert too

from papers.models import Category, ResearchPaper
from similarity.models import Embedding, Feedback
from users.models import Role, User

from .forms import (
    AdminUserCreationForm,
    AdminUserEditForm,
    CategoryForm,
    ResearchPaperForm,
)
# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def admin_required(view_func):
    """
    Not logged in        -> redirect to the admin login page.
    Logged in, not staff -> 403 (Django renders templates/403.html).
    Staff                -> allow.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                reverse('administratordb:admin_login'),
            )
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def pending_papers_count():
    """Papers with no embedding yet (same rule as the embed_pending command)."""
    return ResearchPaper.objects.exclude(
        pk__in=Embedding.objects.values('paper_id')
    ).count()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_required
def admin_dashboard(request):
    total_documents = ResearchPaper.objects.count()
    total_users = User.objects.count()
    total_feedback = Feedback.objects.count()
    student_count = User.objects.filter(
        role__role_name='Student'
    ).count()
    faculty_count = User.objects.filter(
        role__role_name='Faculty'
    ).count()
    users = User.objects.select_related('role').order_by('user_id')[:6]
    recent_ratings = (
        Feedback.objects.select_related('user__role')
        .order_by('-feedback_id')[:3]
    )

    context = {
        'total_documents': total_documents,
        'total_users': total_users,
        'total_feedback': total_feedback,
        'student_count': student_count,
        'faculty_count': faculty_count,
        'users': users,
        'recent_ratings': recent_ratings,
        'pending_count': pending_papers_count(),
    }

    return render(
        request,
        'administratordb/admin-dashboard.html',
        context,
    )

#feedback feature Viewing/Deleting
@admin_required
def admin_feedback(request):
    feedbacks = Feedback.objects.select_related('user').all().order_by('feedback_id')

    context = {
        'feedbacks': feedbacks,
        'total_feedback': feedbacks.count(),
        'average_rating': feedbacks.aggregate(avg=Avg('rating'))['avg'] or 0,
        'messages_count': feedbacks.exclude(message='').count(),
    }

    return render(request, 'administratordb/admin-feedback.html', context)


@admin_required
def admin_delete_feedback(request, feedback_id):
    feedback = get_object_or_404(Feedback, pk=feedback_id)
    if request.method == 'POST':
        feedback.delete()
    return redirect('administratordb:admin_feedback')


# admin login needs authentication based on role. if not staff=permission denied.
@never_cache
@ratelimit(key='ip', rate='8/m', method='POST', block=False)
def admin_login(request):

    if request.user.is_authenticated and request.user.is_staff:
        return redirect('administratordb:admin_dashboard')

    was_limited = getattr(request, 'limited', False)

    if request.method == 'POST' and not was_limited:
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_staff:
                form.add_error(None, "You do not have permission to access the admin panel.")
            else:
                auth_login(request, user)
                next_url = request.POST.get('next')
                # Only follow "next" if it points back to this site (prevents open redirects)
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect('administratordb:admin_dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'administratordb/admin-login.html', {
        'form': form,
        'rate_limited': was_limited,
    })

@admin_required
def admin_research_categories(request):
    search_query = request.GET.get('q', '').strip()

    # Base queryset with paper counts
    categories = Category.objects.annotate(
        paper_count=Count('papers')
    ).order_by('category_id')

    if search_query:
        categories = categories.annotate(
            name_lower=Lower('category_name')
        ).filter(name_lower__contains=search_query.lower())

    # Most popular category (by number of papers) — used for the highlight card
    most_used_category = (
        Category.objects.annotate(paper_count=Count('papers'))
        .filter(paper_count__gt=0)
        .order_by('-paper_count', 'category_name')
        .first()
    )

    paginator = Paginator(categories, 10)
    categories = paginator.get_page(request.GET.get('page'))

    context = {
        'categories': categories,
        'total_categories': Category.objects.count(),
        'uncategorized_papers': ResearchPaper.objects.filter(
            categories__isnull=True
        ).count(),
        'most_used_category': most_used_category,
        'q': search_query,
    }

    return render(
        request,
        'administratordb/admin-research-categories.html',
        context,
    )

@admin_required
def admin_research_papers(request):
    search_query = request.GET.get('q', '').strip()
    selected_type = request.GET.get('type', 'all')

    if selected_type not in {'all', 'capstone', 'thesis'}:
        selected_type = 'all'

    # is_processed = True when the paper has an embedding (used for the "Not processed" label)
    papers_queryset = ResearchPaper.objects.annotate(
        is_processed=Exists(Embedding.objects.filter(paper=OuterRef('pk')))
    ).order_by('paper_id')

    if search_query:
        # Lower() on both sides keeps search case-insensitive even when the
        # database collation (e.g. TiDB's default) is case-sensitive.
        search_lower = search_query.lower()
        papers_queryset = papers_queryset.annotate(
            title_lower=Lower('title'),
            abstract_lower=Lower('abstract'),
            authors_lower=Lower('authors'),
            program_lower=Lower('program'),
        ).filter(
            Q(title_lower__contains=search_lower)
            | Q(abstract_lower__contains=search_lower)
            | Q(authors_lower__contains=search_lower)
            | Q(program_lower__contains=search_lower)
        )

    if selected_type in {'capstone', 'thesis'}:
        papers_queryset = papers_queryset.filter(type=selected_type)

    paginator = Paginator(papers_queryset, 10)
    papers = paginator.get_page(request.GET.get('page'))

    context = {
        'papers': papers,
        'total_papers': ResearchPaper.objects.count(),
        'capstone_count': ResearchPaper.objects.filter(type='capstone').count(),
        'thesis_count': ResearchPaper.objects.filter(type='thesis').count(),
        'pending_count': pending_papers_count(),
        'q': search_query,
        'selected_type': selected_type,
    }

    return render(
        request,
        'administratordb/admin-research-papers.html',
        context,
    )


@admin_required
def admin_add_research_paper(request):
    if request.method == 'POST':
        form = ResearchPaperForm(request.POST, request.FILES)

        if form.is_valid():
            with transaction.atomic():
                paper = form.save(commit=False)
                paper.user = request.user
                paper.save()
                form.save_m2m()

                destination_page = Paginator(
                    ResearchPaper.objects.all().order_by('paper_id'),
                    10,
                ).num_pages

            papers_url = reverse('administratordb:admin_research_papers')
            return redirect(f'{papers_url}?page={destination_page}')
    else:
        form = ResearchPaperForm()

    return render(
        request,
        'administratordb/admin-add-research.html',
        {'form': form},
    )


@admin_required
def admin_edit_research_paper(request, paper_id):
    paper = get_object_or_404(ResearchPaper, paper_id=paper_id)

    if request.method == 'POST':
        form = ResearchPaperForm(
            request.POST,
            request.FILES,
            instance=paper,
        )

        if form.is_valid():
            with transaction.atomic():
                paper = form.save(commit=False)
                paper.save()
                form.save_m2m()

            return redirect('administratordb:admin_research_papers')
    else:
        form = ResearchPaperForm(instance=paper)

    return render(
        request,
        'administratordb/admin-edit-research.html',
        {
            'form': form,
            'paper': paper,
        },
    )


@admin_required
def admin_delete_research_paper(request, paper_id):
    paper = get_object_or_404(ResearchPaper, paper_id=paper_id)
    error = None

    if request.method == 'POST':
        password = request.POST.get('password', '')

        if password and request.user.check_password(password):
            with transaction.atomic():
                paper.delete()
            return redirect('administratordb:admin_research_papers')

        error = 'Incorrect password. The research paper was not deleted.'

    return render(
        request,
        'administratordb/admin-delete-research.html',
        {'paper': paper, 'error': error},
    )


@admin_required
def admin_research(request):
    return render(request, 'administratordb/admin-research.html')


@admin_required
def admin_users(request):
    search_query = request.GET.get('q', '').strip()
    selected_role = request.GET.get('role', '')

    if selected_role not in {'Student', 'Faculty', 'Admin'}:
        selected_role = ''

    users = User.objects.select_related('role').order_by('user_id')

    if search_query:
        # Lower() on both sides keeps search case-insensitive even when the
        # database collation (e.g. TiDB's default) is case-sensitive.
        search_lower = search_query.lower()
        users = users.annotate(
            full_name_lower=Lower('full_name'),
            username_lower=Lower('username'),
            email_lower=Lower('email'),
            role_name_lower=Lower('role__role_name'),
        ).filter(
            Q(full_name_lower__contains=search_lower)
            | Q(username_lower__contains=search_lower)
            | Q(email_lower__contains=search_lower)
            | Q(role_name_lower__contains=search_lower)
        )

    if selected_role:
        users = users.filter(role__role_name=selected_role)

    paginator = Paginator(users, 10)
    users = paginator.get_page(request.GET.get('page'))

    context = {
        'users': users,
        'roles': Role.objects.all().order_by('role_id'),
        'total_users': User.objects.count(),
        'student_count': User.objects.filter(
            role__role_name='Student'
        ).count(),
        'faculty_count': User.objects.filter(
            role__role_name='Faculty'
        ).count(),
        'q': search_query,
        'selected_role': selected_role,
    }

    return render(
        request,
        'administratordb/admin-users.html',
        context,
    )


@admin_required
def admin_add_user(request):
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('administratordb:admin_users')
    else:
        form = AdminUserCreationForm()

    return render(
        request,
        'administratordb/admin-add-user.html',
        {'form': form},
    )


@admin_required
def admin_edit_user(request, user_id):
    managed_user = get_object_or_404(
        User.objects.select_related('role'),
        user_id=user_id,
    )
    is_protected_account = (
        managed_user.is_staff or managed_user.is_superuser
    )

    if request.method == 'POST':
        if is_protected_account:
            form = AdminUserEditForm(request.POST)
            form.is_valid()
            form.add_error(
                None,
                'Staff and superuser accounts cannot be '
                'changed through this form.',
            )
        else:
            form = AdminUserEditForm(request.POST, instance=managed_user)

            if form.is_valid():
                form.save()
                return redirect('administratordb:admin_users')
    else:
        form = AdminUserEditForm(instance=managed_user)

    return render(
        request,
        'administratordb/admin-edit-user.html',
        {
            'form': form,
            'managed_user': managed_user,
            'is_protected_account': is_protected_account,
        },
    )


@admin_required
def admin_deactivate_user(request, user_id):
    target_user = get_object_or_404(
        User.objects.select_related('role'),
        user_id=user_id,
    )
    is_protected_account = (
        target_user.is_staff
        or target_user.is_superuser
        or target_user.user_id == request.user.user_id
    )
    is_assignable_role = (
        target_user.role
        and target_user.role.role_name in {'Student', 'Faculty'}
    )

    if is_protected_account or not is_assignable_role:
        raise PermissionDenied(
            'Only Student and Faculty accounts can be deactivated. '
            'Staff, superuser, and your own account are protected.'
        )

    if request.method == 'POST':
        if target_user.is_active:
            target_user.is_active = False
            target_user.save(update_fields=['is_active'])

        return redirect('administratordb:admin_users')

    return render(
        request,
        'administratordb/admin-deactivate-user.html',
        {'managed_user': target_user},
    )



@admin_required
def admin_delete_category(request, category_id):
    category = get_object_or_404(Category, category_id=category_id)
    if request.method == 'POST':
        category.delete()
    return redirect('administratordb:admin_research_categories')

@admin_required
def admin_add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('administratordb:admin_research_categories')
    else:
        form = CategoryForm()

    return render(
        request,
        'administratordb/admin-add-category.html',
        {'form': form},
    )


@admin_required
def admin_edit_category(request, category_id):
    category = get_object_or_404(Category, category_id=category_id)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)

        if form.is_valid():
            form.save()
            return redirect('administratordb:admin_research_categories')
    else:
        form = CategoryForm(instance=category)

    return render(
        request,
        'administratordb/admin-edit-category.html',
        {
            'form': form,
            'category': category,
        },
    )




# if user clicks logout button (should be inside a form to work), they are redirected back to the login page.
def admin_logout(request):
    if request.method == "POST":
        logout(request)
    return redirect('administratordb:admin_login')