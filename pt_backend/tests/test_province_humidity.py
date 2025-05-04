from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from ..models import Climate
from ..repositories import ClimateRepository
from ..services import ClimateService, CacheService
import uuid
from unittest.mock import patch, MagicMock
import os
from .base_climate_test import BaseHumidityRepositoryTest, BaseHumidityServiceTest, BaseHumidityViewTest

class ClimateRepositoryTest(BaseHumidityRepositoryTest):
    pass

class ClimateServiceTest(BaseHumidityServiceTest):
    pass

class ProvinceHumidityViewTest(BaseHumidityViewTest):
    pass
