import requests
import cloudinary.utils
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from .models import ResearchPaper



def browse(request):
    q = request.GET.get('q', '').strip()
    selected_types = request.GET.getlist('type')
    selected_programs = request.GET.getlist('program')
    selected_years = [y for y in request.GET.getlist('year') if y.isdigit()]

    papers = ResearchPaper.objects.annotate(title_lower=Lower('title'))

    for term in q.lower().split():
        papers = papers.filter(title_lower__contains=term)

    if selected_types:
        papers = papers.filter(type__in=selected_types)
    if selected_programs:
        papers = papers.filter(program__in=selected_programs)
    if selected_years:
        papers = papers.filter(year__in=selected_years)

    papers = papers.order_by('-year', '-paper_id')

    paginator = Paginator(papers, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)

    params = request.GET.copy()
    params.pop('page', None)

    programs = (ResearchPaper.objects.exclude(program='')
                .values_list('program', flat=True).distinct().order_by('program'))
    years = (ResearchPaper.objects
             .values_list('year', flat=True).distinct().order_by('-year'))

    return render(request, 'papers/browse.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'page_range': page_range,
        'querystring': params.urlencode(),
        'q': q,
        'type_choices': [c for c in ResearchPaper.TYPE_CHOICES if c[0] != 'submission'],        'programs': programs,
        'years': years,
        'selected_types': selected_types,
        'selected_programs': selected_programs,
        'selected_years': selected_years,
        'active_filters': len(selected_types) + len(selected_programs) + len(selected_years),
    })


def document_info(request, paper_id):
    paper = get_object_or_404(ResearchPaper, paper_id=paper_id)
    return render(request, 'papers/document_info.html', {'paper': paper})


@login_required(login_url='users:restricted')
def view_paper(request, paper_id):
    paper = get_object_or_404(ResearchPaper, paper_id=paper_id)
    return render(request, 'papers/view_paper.html', {'paper': paper})


@login_required(login_url='users:restricted')
def stream_paper_pdf(request, paper_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('users:restricted')

    paper = get_object_or_404(ResearchPaper, paper_id=paper_id)

    url, options = cloudinary.utils.cloudinary_url(
        paper.file_path.name,
        resource_type="raw",
        type="upload",
    )

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        return HttpResponse("Could not load document.", status=502)

    if response.status_code != 200:
        return HttpResponse("Could not load document.", status=502)

    return HttpResponse(response.content, content_type='application/pdf')