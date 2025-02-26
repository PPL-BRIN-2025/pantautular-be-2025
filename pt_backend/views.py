from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.http import HttpResponse


@require_GET
def hello_world(request):
    return HttpResponse("Hello, World!")

