import math
import random
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    login as auth_login,
    logout,
    update_session_auth_hash,
    views as auth_views,
)
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from django_ratelimit.decorators import ratelimit

from papers.models import ResearchPaper
from similarity.decorators import faculty_required
from similarity.models import SimilarityResult
from similarity.pipeline import band_for

from .forms import LoginForm, ProfileEditForm, SignUpForm
from .models import Role


@login_required(login_url='users:restricted') 
def homepage(request):
    ids = list(ResearchPaper.objects.values_list('paper_id', flat=True))

    
    
    rng = random.Random(timezone.localdate().toordinal())
    picked = rng.sample(ids, min(3, len(ids)))

    return render(request, 'users/homepage.html', {
        'paper_count': len(ids),
        'papers_of_the_day': ResearchPaper.objects.filter(paper_id__in=picked),
    })

@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def login_view(request):

    if request.user.is_authenticated:
        return redirect("landing")

    was_limited = getattr(request, 'limited', False)

    if request.method == "POST" and was_limited:
        messages.error(request, "Too many attempts. Please wait a moment before trying again.")
        form = LoginForm(request)
    elif request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            next_url = request.POST.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("landing")
    else:
        form = LoginForm(request)

    return render(request, "users/login.html", {
        "form": form,
        "deactivated": form.is_bound and form.has_error("__all__", code="inactive"),
    })

def password_reset(request):
    return render(request, 'users/password_reset.html')

class ArcheionPasswordResetView(auth_views.PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email.html'
    subject_template_name = 'users/password_reset_subject.txt'
    success_url = reverse_lazy('users:password_reset_done')

class ArcheionPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'users/password_reset_done.html'

class ArcheionPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('users:password_reset_complete')

class ArcheionPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'users/password_reset_complete.html'


@login_required(login_url='users:restricted')
def profile_edit(request):
    user = request.user

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, user=user)

        if form.is_valid():
            user.full_name = form.cleaned_data['fullname']
            user.username = form.cleaned_data['username']
            user.email = form.cleaned_data['email']

            new_password = form.cleaned_data.get('new_password')
            if new_password:
                user.set_password(new_password)

            user.save()

            
            if new_password:
                update_session_auth_hash(request, user)

            messages.success(request, 'Your profile has been updated.')
            return redirect('users:profile')
    else:
        form = ProfileEditForm(user=user, initial={
            'fullname': user.full_name,
            'username': user.username,
            'email': user.email,
        })

    return render(request, 'users/profile-edit.html', {'form': form})

def _level(score):
    # floor (not round) so the badge matches the result page percentage
    pct = math.floor(score * 100)
    if pct >= 39:
        return "high"
    if pct >= 30:
        return "moderate"
    return "low"

@login_required(login_url='users:restricted')
def profile(request):
    # Start from the user's submissions so checks with no matches are included
    submissions = (
        ResearchPaper.all_objects
        .filter(user=request.user, type="submission")
        .order_by("-upload_date", "-pk")
    )

    # 5 reports per page
    paginator = Paginator(submissions, 5)
    page = paginator.get_page(request.GET.get("page"))

    # Average score and match count for the papers on this page.
    # Checks with no matches have no SimilarityResult rows, so they're missing here.
    scores = {
        row["input_paper"]: row
        for row in (
            SimilarityResult.objects
            .filter(input_paper__in=[s.pk for s in page.object_list])
            .values("input_paper")
            .annotate(avg_score=Avg("similarity_score"), compared=Count("compared_paper"))
        )
    }

    reports = []
    for s in page.object_list:
        agg = scores.get(s.pk)
        avg = agg["avg_score"] if agg else 0
        reports.append({
            "paper_id": s.pk,
            "title": s.title,
            "date": s.upload_date,
            "compared": agg["compared"] if agg else 0,
            "pct": math.floor(max(0.0, avg) * 100),
            "level": _level(avg),
        })

    # Keep query parameters when moving between pages
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "users/profile.html", {
        "reports": reports,
        "page": page,
        "page_range": list(
            paginator.get_elided_page_range(
                page.number,
                on_each_side=1,
                on_ends=1
            )
        ),
        "querystring": params.urlencode(),
    })

def _as_date(value):
    """upload_date as a plain local date, whether it's a DateField or DateTimeField."""
    if isinstance(value, datetime):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return value


@login_required(login_url='users:restricted')
@faculty_required
def faculty_reports(request):
    """Every similarity check, by students and faculty. Faculty role only."""
    # Average score and match count per submission. Checks with no matches
    # have no SimilarityResult rows, so they're missing from this dict.
    scores = {
        row["input_paper"]: row
        for row in (
            SimilarityResult.objects
            .filter(input_paper__type="submission")
            .values("input_paper")
            .annotate(avg_score=Avg("similarity_score"), compared=Count("compared_paper"))
        )
    }

    submissions = (
        ResearchPaper.all_objects
        .filter(type="submission")
        .select_related("user", "user__role")
        .order_by("-upload_date")
    )

    reports = []
    for s in submissions:
        agg = scores.get(s.pk)
        avg = agg["avg_score"] if agg else None
        user = s.user
        reports.append({
            "paper_id": s.pk,
            "title": s.title,
            "date": _as_date(s.upload_date),
            "student_id": s.user_id,
            "student": (user.full_name or user.username) if user else "Unknown",
            "username": user.username if user else "",
            "role": user.role.role_name if user and user.role else "",
            "compared": agg["compared"] if agg else 0,
            "pct": math.floor(max(0.0, avg) * 100) if avg is not None else 0,
            "band": band_for(avg) if avg is not None else None,
        })

    # Summary numbers (all checks, before filters)
    week_ago = timezone.localdate() - timedelta(days=7)
    summary = {
        "total": len(reports),
        "this_week": sum(1 for r in reports if r["date"] and r["date"] > week_ago),
        "high": sum(1 for r in reports if r["band"] == "High"),
        "moderate": sum(1 for r in reports if r["band"] == "Moderate"),
        "none": sum(1 for r in reports if r["band"] is None),
        "students": len({r["student_id"] for r in reports if r["role"] != "Faculty"}),
        "faculty": len({r["student_id"] for r in reports if r["role"] == "Faculty"}),
        # start date for the "last 7 days" card link
        "week_from": (week_ago + timedelta(days=1)).isoformat(),
    }

    # Filters
    q = request.GET.get("q", "").strip()
    band = request.GET.get("band", "")
    sort = request.GET.get("sort", "newest")
    date_from = parse_date(request.GET.get("from", "") or "")
    date_to = parse_date(request.GET.get("to", "") or "")
    student_id = request.GET.get("student", "")
    selected_student = None

    if student_id.isdigit():
        student_id = int(student_id)
        reports = [r for r in reports if r["student_id"] == student_id]
        selected_student = reports[0]["student"] if reports else None
    if q:
        needle = q.lower()
        reports = [
            r for r in reports
            if needle in r["student"].lower()
            or needle in r["username"].lower()
            or needle in r["title"].lower()
        ]
    if band == "high":
        reports = [r for r in reports if r["band"] == "High"]
    elif band == "moderate":
        reports = [r for r in reports if r["band"] == "Moderate"]
    elif band == "none":
        reports = [r for r in reports if r["band"] is None]
    if date_from:
        reports = [r for r in reports if r["date"] and r["date"] >= date_from]
    if date_to:
        reports = [r for r in reports if r["date"] and r["date"] <= date_to]
    if sort == "highest":
        reports.sort(key=lambda r: r["pct"] if r["band"] else -1, reverse=True)

    # 10 checks per page
    page = Paginator(reports, 10).get_page(request.GET.get("page"))

    # Keep the filters when moving between pages
    params = request.GET.copy()
    params.pop("page", None)

    # Repository studies that student checks match most often
    most_matched = (
        SimilarityResult.objects
        .filter(input_paper__type="submission")
        .values("compared_paper", "compared_paper__title",
                "compared_paper__program", "compared_paper__year")
        .annotate(
            times=Count("input_paper", distinct=True),
            people=Count("input_paper__user", distinct=True),
        )
        .order_by("-times")[:5]
    )

    return render(request, "users/faculty_reports.html", {
        "summary": summary,
        "page": page,
        "page_range": list(
            page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)
        ),
        "reports": page.object_list,
        "result_count": len(reports),
        "most_matched": most_matched,
        "q": q,
        "band": band,
        "sort": sort,
        "date_from": request.GET.get("from", ""),
        "date_to": request.GET.get("to", ""),
        "student_id": student_id,
        "selected_student": selected_student,
        "querystring": params.urlencode(),
        "threshold_pct": round(settings.SIMILARITY_THRESHOLD * 100),
        "high_pct": round(settings.SIMILARITY_HIGH_BAND * 100),
    })


@never_cache
@ratelimit(key='ip', rate='7/m', method='POST', block=False)


def signup(request):
    if request.user.is_authenticated:
        return redirect("landing") 
    

    was_limited = getattr(request, 'limited', False)

    if request.method == "POST" and was_limited:
        messages.error(
            request,
            "Too many accounts created in a short period of time. Try again after a minute."
        )
        form = SignUpForm()
    elif request.method == "POST":
        form = SignUpForm(request.POST)

        if not request.POST.get('terms'):
            form.add_error(None, "You must agree to the Terms of Service.")

        if form.is_valid():
            student_role, _ = Role.objects.get_or_create(role_name='Student') 
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.role = student_role
            user.save()
            return redirect("users:login")
    else:
        form = SignUpForm()

    return render(request, "users/signup.html", {"form": form})



LIVE_SIGNUP_FIELDS = ('full_name', 'username', 'email', 'password')

@require_POST
@ratelimit(key='ip', rate='60/m', method='POST', block=False)



def validate_signup(request):
    if getattr(request, 'limited', False):
        return JsonResponse({'errors': {}}, status=429)

    form = SignUpForm(request.POST)
    form.is_valid()
    all_errors = form.errors.get_json_data()

    errors = {}
    for field in LIVE_SIGNUP_FIELDS:
        
        if request.POST.get(field, '').strip() and field in all_errors:
            errors[field] = " ".join(e['message'] for e in all_errors[field])

    return JsonResponse({'errors': errors})


@require_POST
def user_logout(request):
    logout(request)
    return redirect('landing')



def restricted(request):
    return render(request, 'restricted.html')