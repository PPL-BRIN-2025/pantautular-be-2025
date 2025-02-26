from .models import Case, Location

class CaseRepository:
    def get_all_case_locations(self):
        locations = Case.get_all_cases_locations()
        return [
            {
                "id": str(location.case.id),
                "city": location.case.city,
                "latitude": f"{float(location.latitude):.6f}", 
                "longitude": f"{float(location.longitude):.6f}",  
            }
            for location in locations
        ]

    
