from .models import Case, Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist

class CaseRepository:
    def get_all_case_locations(self):
        try:
            cases = Case.get_all_cases()
            locations = [case.location for case in cases]
            if not locations.exists():
                return []
            return [
                {
                    "id": str(location.id),
                    "name": location.name,
                    "latitude": f"{float(location.latitude):.6f}",
                    "longitude": f"{float(location.longitude):.6f}",
                }
                for location in locations
            ]
        except ObjectDoesNotExist:  
            return {"error": "Error retrieving case locations"}