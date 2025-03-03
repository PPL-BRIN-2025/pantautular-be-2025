from .models import Case
from .serializers import CaseLocationSerializer
from django.core.exceptions import ObjectDoesNotExist

class CaseRepository:
    def get_all_case_locations(self):
        try:
            locations = Case.get_all_cases_locations()
            if not locations.exists():
                return []
            return CaseLocationSerializer.serialize(locations)
        except ObjectDoesNotExist:  
            return {"error": "Error retrieving case locations"}
    
