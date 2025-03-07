from .models import Case
from django.core.exceptions import ObjectDoesNotExist
from .interfaces import CaseRepositoryInterface

class CaseRepository(CaseRepositoryInterface):
    def get_all_locations(self):
        return Case.get_all_locations()
