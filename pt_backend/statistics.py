from asyncio.log import logger
from collections import Counter, defaultdict
from datetime import datetime
from .interfaces import CaseRepositoryInterface
from .repositories import CaseRepository

class SeverityGroupingReport:
 
    def generate_report(self, filtered_cases = None):
        severity_counts = Counter()
        total_cases = 0
        
        if filtered_cases:
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

class SeverityDatesCountReport:
    def generate_report(self, filtered_cases=None):
        """Generate severity dates count report"""
        if not filtered_cases:
            logger.info("No filtered cases provided. Returning empty report.")
            return {}

        severity_dates = defaultdict(lambda: defaultdict(int))

        for case in filtered_cases:
            severity = case.get("severity")
            date_published = case.get("news__date_published")

            # Safely format the date
            if isinstance(date_published, datetime):
                date_published = date_published.strftime('%Y-%m-%d')
            else:
                logger.warning(f"Invalid or missing date_published in case: {case}")
                continue

            severity_dates[severity][date_published] += 1

        # Transform to the desired output format
        return {
            severity: [{"date": date, "count": count} for date, count in dates.items()]
            for severity, dates in severity_dates.items()
        }

class GenderGroupingReport:
    """Generates gender distribution statistics"""

    def generate_report(self, filtered_cases=None):
        """Generate gender distribution report"""
        gender_counts = Counter()

        if not filtered_cases:
            return {"male": 0, "female": 0}

        for case in filtered_cases:
            if case and isinstance(case, dict):
                gender = case.get("gender")
                if isinstance(gender, str):  # Pastikan gender adalah string
                    gender = gender.lower()
                    if gender in ["male", "female"]:
                        gender_counts[gender] += 1

        return {
            "male": gender_counts.get("male", 0),
            "female": gender_counts.get("female", 0),
        }

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

class StatisticsCoordinator:
    """
    Coordinates the generation of various statistics reports.
    This class acts as a facade for the statistics layer, providing a single entry point
    for generating comprehensive reports that include multiple statistics components.
    """
    
    def __init__(self, case_filter_service):
        self.case_filter_service = case_filter_service
        self.prevalence = PrevalenceStatistics(CaseRepository())
        self.age_report = AgeGroupingReport()
        self.gender_report = GenderGroupingReport()
        self.severity_report = SeverityGroupingReport()
        self.severity_dates_count_report = SeverityDatesCountReport()
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
            result["gender_statistics"] = self.gender_report.generate_report(
                filtered_cases=filtered_cases
            )
            result["severity_statistics"] = self.severity_report.generate_report(
                filtered_cases=filtered_cases
            )
            result["severity_dates_count_statistics"] = self.severity_dates_count_report.generate_report(
                filtered_cases=filtered_cases
            )
            # Add more statistics components here as needed
            
            return result
        
        except Exception as e:
            print(e)
