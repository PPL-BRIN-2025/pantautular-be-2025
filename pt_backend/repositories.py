from .models import Case
from .interfaces import CaseRepositoryInterface

class CaseRepository(CaseRepositoryInterface):
    def get_all_locations(self):
        return Case.get_all_locations()
    
    def get_all_cases(self):
        return Case.objects.all()
    
    
    

