from django.shortcuts import render


def policies(request):
    return render(request, "pages/policies.html")