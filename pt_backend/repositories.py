from .models import Case
from django.core.exceptions import ObjectDoesNotExist

class CaseRepository:
    def get_all_case_locations(self):
        try:
            locations = Case.get_all_cases_locations()
            if not locations.exists():
                return []
            return [
                {
                    "id": str(location.case.id),
                    "city": location.case.city,
                    "latitude": f"{float(location.latitude):.6f}",
                    "longitude": f"{float(location.longitude):.6f}",
                }
                for location in locations
            ]
        except ObjectDoesNotExist:  
            return {"error": "Error retrieving case locations"}

    
