from .models import Case
from .interfaces import CaseRepositoryInterface

class CaseRepository(CaseRepositoryInterface):
    def get_all_cases(self):
        return Case.objects.all().values(
            "id",
            "location__province",
            "location__city",
            "news__portal",
            "severity",
            "news__date_published"
        )
    
    

