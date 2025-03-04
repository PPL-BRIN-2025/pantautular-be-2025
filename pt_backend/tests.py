from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import Case, Location, Disease
from .repositories import CaseRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch



    