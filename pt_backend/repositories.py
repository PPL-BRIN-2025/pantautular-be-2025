from .models import Case
from .interfaces import CaseRepositoryInterface

class CaseRepository(CaseRepositoryInterface):
    def get_all_cases(self):
        return Case.objects.all()
    
    
    

