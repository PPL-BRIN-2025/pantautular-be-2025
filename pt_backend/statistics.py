from collections import Counter
from datetime import datetime
from .interfaces import CaseRepositoryInterface
from .repositories import CaseRepository

class SeverityGroupingReport:
 
    def __init__(self, case_filter_service):
        self.case_filter_service = case_filter_service

    def generate_report(self, provinces=None, cities=None, news_portals=None, severities=None, news_date_range=None):
        filtered_cases = self.case_filter_service.filter_cases(
            provinces=provinces,
            cities=cities,
            news_portals=news_portals,
            severities=severities,
            news_date_range=news_date_range,
        )
        
        severity_counts = Counter()
        total_cases = 0
        
        for case in filtered_cases:
            total_cases += 1
            severity = case.get("severity")
            if severity is not None:
                severity_counts[severity] += 1
        
        return {
            "total_cases": total_cases,
            "severity_counts": dict(severity_counts)
        }

class AgeGroupingReport:
    """Generates age grouping statistics"""
    
    def generate_report(self, filtered_cases=None):
        """Generate age grouping report"""
        age_groups = {
            "under_12": 0,
            "12_25": 0,
            "26_45": 0,
            "above_45": 0
        }

        if not filtered_cases:
            return age_groups
        
        # Track cases we've already counted
        counted_cases = set()
        
        for case in filtered_cases:
            case_id = case.get("id")
            
            # Skip if we've already counted this case
            if case_id in counted_cases:
                continue
                
            counted_cases.add(case_id)
            
            age = case.get("age")
            if age is None:
                continue
                
            if age < 12:
                age_groups["under_12"] += 1
            elif 12 <= age <= 25:
                age_groups["12_25"] += 1
            elif 26 <= age <= 45:
                age_groups["26_45"] += 1
            else:
                age_groups["above_45"] += 1

        return age_groups

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
        try:
            year = 2024
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                year = start_date.year 

            cases = self.repository.get_cases_by_year(self.repository, year)
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

class StatisticsCoordinator:
    """
    Coordinates the generation of various statistics reports.
    This class acts as a facade for the statistics layer, providing a single entry point
    for generating comprehensive reports that include multiple statistics components.
    """
    
    def __init__(self, case_filter_service):
        self.case_filter_service = case_filter_service
        self.prevalence = PrevalenceStatistics(CaseRepository)
        self.age_report = AgeGroupingReport()
        # Add other statistics components here as needed
    
    def generate_comprehensive_report(self, **filter_params):
        try:
            # Filter data once
            filtered_cases = None
            
            if self.case_filter_service:
                filtered_cases = self.case_filter_service.filter_cases(**filter_params)

            result = {}
            
            # Extract date parameters from filter_params
            date_range = filter_params.get('date_range', {})
            start_date = date_range.get('start') if date_range else None
            
            # Generate prevalence statistics with date parameters
            result["prevalence_statistics"] = self.prevalence.get_prevalence_statistics(start_date)
            result["age_statistics"] = self.age_report.generate_report(
                filtered_cases=filtered_cases
            )
            
            # Add more statistics components here as needed
            
            return result
        
        except Exception as e:
            print(e)
