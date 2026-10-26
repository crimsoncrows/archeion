from django.shortcuts import render


#format for views: def nameofhtmlfile
#this is for static pages in the root folder only.
# error pages are handled elsewhere.

def about(request):
    return render(request, 'about.html')

def contact(request):
    return render(request, 'contact.html')

def landing(request):
    return render(request, 'landing.html')

def privacy_policy(request):
    return render(request, 'privacy_policy.html')

def tos(request):
    return render(request, 'tos.html')




#error handler
def page_not_found(request, exception):
    return render(request, '404.html', status=404)

def server_error(request):
    return render(request, '500.html', status=500)

def access_denied(request, exception):
    return render(request, '403.html', status=403)

def coming_soon(request):
    return render(request, 'coming_soon.html') 