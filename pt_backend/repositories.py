from .models import Case
from django.core.exceptions import ObjectDoesNotExist

class CaseRepository:
    @staticmethod
    def get_all_case_locations():
        return Case.get_all_locations()
    
