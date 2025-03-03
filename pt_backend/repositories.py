from .models import Case
from django.core.exceptions import ObjectDoesNotExist

class CaseRepository:
    def get_all_case_locations(self):
        try:
            locations = Case.get_all_cases_locations()
            if not locations.exists():
                return []
            return locations
        except ObjectDoesNotExist:
            return None
    
