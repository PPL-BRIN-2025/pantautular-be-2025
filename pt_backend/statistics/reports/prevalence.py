from datetime import datetime
from pt_backend.interfaces import CaseRepositoryInterface
from ..interface import ReportStrategy

class PrevalenceStatistics(ReportStrategy):
    def __init__(self, repository: CaseRepositoryInterface):
        self.repository = repository
        self.POPULATION_DATA = {
            2019: 266911.9,
            2020: 270203.9,
            2021: 272682.5,
            2022: 275773.8,  
            2023: 278696.2,  
            2024: 281603.8,   
        }

    def generate_report(self, filtered_cases=None, **kwargs) -> dict:
        del filtered_cases  # Unused parameter
        
        try:
            # 1) tentukan tahun
            year = 2024
            # coba ambil dari kwargs: start_date atau date_range.start
            sd = kwargs.get("start_date") \
                 or (kwargs.get("date_range") or {}).get("start")
            if sd:
                # strip time‐suffix
                if "T" in sd:
                    sd = sd.split("T")[0]
                year = datetime.strptime(sd, "%Y-%m-%d").year

            # 2) ambil data dan hitung
            cases = self.repository.get_cases_by_year(year)
            total_cases = cases.count()

            pop = self.POPULATION_DATA.get(year)
            if not pop:
                return {
                    "year": year,
                    "total_cases": total_cases,
                    "population": "Angka jiwa belum tercatat",
                    "prevalence": "No Data"
                }

            population = int(pop * 1_000)
            prevalence = (total_cases / population) * 100

            return {
                "year": year,
                "total_cases": total_cases,
                "population": population,
                "prevalence": round(prevalence, 4)
            }

        except Exception as e:
            return {"error": f"Error calculating prevalence: {e}"}