from .models import Case
from django.core.exceptions import ObjectDoesNotExist

class CaseRepository:
    @staticmethod
    def get_all_case_locations():
        locations = Case.get_all_locations()
        if not locations.exists():
            return []
        return locations
    
