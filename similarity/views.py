import math
from pathlib import Path
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Count                      # trends
from django.utils import timezone
from .decorators import is_faculty
from .forms import FeedbackForm, SimilarityForm
from .extractors import extract_text
from .pipeline import find_similar, band_for
from .clean_ocr import clean_text                 # FFM: same cleaning as the embeddings
from .ffm import generate_ffm, ffm_context        # FFM
from django.contrib import messages
from papers.models import ResearchPaper, PaperCategory
from similarity.models import Feedback, SimilarityResult
from users.models import User
#format for views: def nameofhtmlfile
#this is for static pages in the root folder only.
# error pages are handled elsewhere.


def save_check(user, source_name, results):
    """Record one similarity check: a hidden 'submission' paper plus its
    ranked matches. The uploaded file itself is never stored."""
    with transaction.atomic():
        submission = ResearchPaper.all_objects.create(
            title=source_name[:255],
            abstract="",
            authors="",
            year=timezone.now().year,
            type="submission",
            program="",
            user=user,
        )
        SimilarityResult.objects.bulk_create([
            SimilarityResult(
                input_paper=submission,
                compared_paper_id=r["paper_id"],
                similarity_score=r["score"],
                rank_order=rank,
            )
            for rank, r in enumerate(results, start=1)
        ])
    return submission


def check_rows(submission_id):
    """FFM: this check's saved SimilarityResult rows, best match first."""
    return (
        SimilarityResult.objects
        .filter(input_paper_id=submission_id)
        .select_related("compared_paper")
        .order_by("rank_order")
    )


@login_required(login_url='users:restricted')
def similarity_check(request):
    if request.method == "POST":
        form = SimilarityForm(request.POST, request.FILES)
    else:
        form = SimilarityForm()

    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data.get("document_file")
        try:
            text = extract_text(upload) if upload else form.cleaned_data["text_input"]
        except Exception:
            form.add_error("document_file", "This file could not be read. Try another file or paste the text instead.")
        else:
            try:
                results = find_similar(text)
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                source_name = Path(upload.name).name if upload else "Text input"
                # Embedding can take minutes; if TiDB closed the idle connection,
                # drop it so the save below opens a fresh one.
                close_old_connections()
                submission = save_check(request.user, source_name, results)
                # FFM: one Claude Haiku call per check. Skips itself if there are
                # no matches, no API key, or the call fails; results still show.
                generate_ffm(submission, clean_text(text) or text, check_rows(submission.pk))
                # Post/Redirect/Get: refreshing the results page won't re-run the embedding
                request.session["similarity_results"] = results
                request.session["similarity_submission_id"] = submission.pk
                return redirect("similarity:paper_results")

    return render(request, 'similarity/similarity_check.html', {
        "form": form,
        "threshold_pct": round(settings.SIMILARITY_THRESHOLD * 100),
        "high_pct": round(settings.SIMILARITY_HIGH_BAND * 100),
    })


@login_required(login_url='users:restricted')
def similarity_result(request, paper_id=None):
    file_name = ""

    if paper_id is not None:
        # Past check opened from the profile page (owner) or the faculty
        # reports page (faculty): rebuild from saved rows
        submission = ResearchPaper.all_objects.filter(
            pk=paper_id, type="submission"
        ).first()
        if submission is None or (
            submission.user_id != request.user.pk and not is_faculty(request.user)
        ):
            return redirect("users:profile")  # not theirs, or doesn't exist

        file_name = "" if submission.title == "Text input" else submission.title

        rows = (
            SimilarityResult.objects
            .filter(input_paper=submission)
            .select_related("compared_paper")
            .order_by("rank_order")
        )
        results = [
            {
                "paper_id": r.compared_paper.paper_id,
                "title": r.compared_paper.title,
                "abstract": r.compared_paper.abstract,
                "authors": r.compared_paper.authors,
                "year": r.compared_paper.year,
                "program": r.compared_paper.program,
                "type": r.compared_paper.type,
                "score": r.similarity_score,
                # same as find_similar(): floor the percent and attach the band
                "percent": math.floor(max(0.0, r.similarity_score) * 100),
                "band": band_for(r.similarity_score),
            }
            for r in rows
        ]
        submission_id = submission.pk                                   # FFM
        is_owner = submission.user_id == request.user.pk
        redirect_to = ("similarity:past_result", paper_id)
    else:
        results = request.session.get("similarity_results")
        if results is None:
            return redirect("similarity:sbert")  # no check run yet
        submission_id = request.session.get("similarity_submission_id")  # FFM
        is_owner = True  # a session result is always the user's own fresh check
        redirect_to = ("similarity:paper_results",)

        if submission_id:
            title = (
                ResearchPaper.all_objects
                .filter(pk=submission_id, type="submission")
                .values_list("title", flat=True)
                .first()
            ) or ""
            file_name = "" if title == "Text input" else title

    if request.method == "POST":
        if not is_owner:
            return redirect(*redirect_to)  # faculty viewing someone else's check
        # Feedback is once per user: ignore any repeat submission
        if Feedback.objects.filter(user=request.user).exists():
            messages.info(request, "You've already submitted your feedback.")
            return redirect(*redirect_to)
        form = FeedbackForm(request.POST)
        if form.is_valid():
            fb = form.save(commit=False)
            fb.user = request.user
            fb.save()
            messages.success(request, 'Thanks for your feedback!')
            # Post/Redirect/Get: refreshing after feedback won't resubmit the form
            return redirect(*redirect_to)
    else:
        form = FeedbackForm()

    userInputCount = Feedback.objects.filter(user=request.user).count()

    # FFM: read the saved matrix for this check (no API call here)
    ffm = ffm_context(check_rows(submission_id)) if submission_id else None

    # Overall score = average of all matched studies (not just the top one)
    if results:
        avg = sum(max(0.0, r["score"]) for r in results) / len(results)
        overall = {
            "score": avg,
            "percent": math.floor(avg * 100),
            "band": band_for(avg),
        }
    else:
        overall = None

    return render(request, 'similarity/similarity_result.html', {
        "feedback_form": form,
        "userInputCount": userInputCount,
        "results": results,
        "overall": overall,
        "ffm": ffm,                                                     # FFM
        "file_name": file_name,
        "is_owner": is_owner,
        "threshold_pct": round(settings.SIMILARITY_THRESHOLD * 100),
        "high_pct": round(settings.SIMILARITY_HIGH_BAND * 100),
    })


# Public page (no login required), matching the navbar link.
# To make it login-only, add: @login_required(login_url='users:restricted')
def trends(request):
    papers = ResearchPaper.objects.all()  # default manager already excludes submissions

    # last 5 years that actually have papers
    years = sorted(papers.values_list('year', flat=True).distinct())[-5:]

    # Yearly output: thesis vs capstone per year
    rows = (papers.filter(year__in=years)
                  .values('year', 'type')
                  .annotate(n=Count('paper_id')))
    lookup = {(r['year'], r['type']): r['n'] for r in rows}
    yearly = [
        {"year": str(y),
         "data": [lookup.get((y, 'thesis'), 0), lookup.get((y, 'capstone'), 0)]}
        for y in years
    ]

    # Distribution by program
    dist = (papers.values('program')
                  .annotate(n=Count('paper_id'))
                  .order_by('-n'))
    distribution = {
        "labels": [d['program'] for d in dist],
        "data": [d['n'] for d in dist],
    }

    cat_rows = (PaperCategory.objects
                .filter(paper__year__in=years)
                .exclude(paper__type='submission')
                .values('category__category_name', 'paper__year')
                .annotate(n=Count('id')))

    counts, totals = {}, {}
    for r in cat_rows:
        name, y, n = r['category__category_name'], r['paper__year'], r['n']
        counts.setdefault(name, {})[y] = n
        totals[name] = totals.get(name, 0) + n

        top = sorted(totals, key=totals.get, reverse=True)
    heatmap = {
        "years": years,
        "topics": top,
        "data": {t: [counts[t].get(y, 0) for y in years] for t in top},
    }

    return render(request, 'similarity/trends.html', {
        'trends_data': {
            "yearly": yearly,
            "distribution": distribution,
            "heatmap": heatmap,
        }
    })