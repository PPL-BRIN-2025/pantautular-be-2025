from datetime import datetime
from .interfaces import CaseRepositoryInterface

""" 
This is a statistics layer that is used to preprocess data for multiple components of the dashboard. 
For every new component, a new statistics class should be added here.

"""

class PrevalenceStatistics:
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

    def get_prevalence_statistics(self, start_date=None):
        year = 2024

        try:
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                year = start_date.year 

            cases = self.repository.get_cases_by_year(year)
            total_cases = cases.count()
            
            population = self.POPULATION_DATA.get(year)
            if not population:
                return {"error": f"Population data not available for year {year}"}
            
            population = int(population * 1_000)  
            
            prevalence = (total_cases / population) * 100
            
            return {
                "year": year,
                "total_cases": total_cases,
                "population": population,
                "prevalence": round(prevalence, 4)  
            }
            
        except Exception as e:
            return {"error": f"Error calculating prevalence: {str(e)}"}
