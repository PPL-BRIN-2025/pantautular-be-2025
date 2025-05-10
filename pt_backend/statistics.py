from asyncio.log import logger
from collections import Counter, defaultdict
from datetime import datetime
from .interfaces import CaseRepositoryInterface
from .repositories import CaseRepository
from .services import CaseService
import math
import numpy as np
from .constants import PROVINCE_TO_CODE

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
        self.national_news_report = NationalNewsStatisticsReport()
        self.local_portal_report = LocalPortalStatisticsReport()
        self.healthcare_news_report = HealthcareNewsStatisticsReport()
    
    def generate_comprehensive_report(self, **filter_params):
        result = {}
        
        # Filter data once
        filtered_cases = None
        
        if self.case_filter_service:
            try:
                filtered_cases = self.case_filter_service.filter_cases(**filter_params)
            except Exception as filter_error:
                logger.error(f"Error filtering cases: {str(filter_error)}")
                result["error"] = f"Failed to filter cases: {str(filter_error)}"
                return result
        
        # Extract date parameters from filter_params
        date_range = filter_params.get('date_range', {})
        start_date = date_range.get('start') if date_range else None
        
        # Generate each report individually with error handling
        report_generators = {
            "prevalence_statistics": lambda: self.prevalence.get_prevalence_statistics(start_date),
            "age_statistics": lambda: self.age_report.generate_report(filtered_cases=filtered_cases),
            "gender_statistics": lambda: self.gender_report.generate_report(filtered_cases=filtered_cases),
            "severity_statistics": lambda: self.severity_report.generate_report(filtered_cases=filtered_cases),
            "severity_dates_count_statistics": lambda: self.severity_dates_count_report.generate_report(filtered_cases=filtered_cases),
            "national_news_statistics": lambda: self.national_news_report.generate_report(filtered_cases=filtered_cases),
            "local_portal_statistics": lambda: self.local_portal_report.generate_report(filtered_cases=filtered_cases),
            "healthcare_news_statistics": lambda: self.healthcare_news_report.generate_report(filtered_cases=filtered_cases)
        }
        
        for key, generator in report_generators.items():
            try:
                result[key] = generator()
            except Exception as e:
                logger.error(f"Error generating {key}: {str(e)}")
                result[key] = {"error": f"Failed to generate report: {str(e)}"}
        
        return result

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

        for severity, dates in severity_dates.items():
            severity_dates[severity] = dict(sorted(dates.items()))

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
                # Handle ISO format date strings (e.g., 2024-09-08T17:00:00.000Z)
                if 'T' in start_date:
                    start_date = start_date.split('T')[0]
                
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                year = start_date.year 

            cases = self.repository.get_cases_by_year(year)
            total_cases = cases.count()
            
            population = self.POPULATION_DATA.get(year)
            if not population:
                return {
                "year": year,
                "total_cases": total_cases,
                "population": "Angka jiwa belum tercatat",
                "prevalence": "No Data"
            }
            
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
    
class NationalNewsStatisticsReport:
    """Generates statistics about national news portals"""
    
    def generate_report(self, filtered_cases=None):
        """
        Generate national news statistics report
        
        Returns:
            dict: Contains two keys:
                - top_national: List of portals sorted by news count
                - all_national: List of portals with news and disease counts
        """
        # Early return for empty data
        if not filtered_cases:
            return {
                "top_national": [],
                "all_national": []
            }
                
        # Track disease counts per portal
        portal_diseases = defaultdict(set)
        # Track news counts per portal
        portal_counts = Counter()
        
        # Process national news only
        for case in filtered_cases:
            portal = case.get("news__portal")
            news_type = case.get("news__type")
            disease = case.get("disease__name")
            
            # Skip non-national or missing portal news
            if not (portal and news_type == "Nasional"):
                continue
                
            # Count this news article
            portal_counts[portal] += 1
            
            # Add disease if present
            if disease:
                portal_diseases[portal].add(disease)
        
        # No need to sort manually - Counter has most_common() method
        top_national = [
            {"portal": portal, "count": count} 
            for portal, count in portal_counts.most_common(5)
        ]
        
        # Create all_national with news and disease counts
        all_national = [
            {
                "portal": portal,
                "news_count": count,
                "disease_count": len(portal_diseases[portal])
            }
            for portal, count in portal_counts.items()
        ]
        
        return {
            "top_national": top_national,
            "all_national": all_national
        }

class HealthcareNewsStatisticsReport:
    """Generates statistics about healthcare news portals"""

    def generate_report(self, filtered_cases=None):
        """
        Generate healthcare news statistics report

        Returns:
            dict: Contains two keys:
                - top_healthcare: List of portals sorted by news count
                - all_healthcare: List of portals with news and disease counts
        """
        # Early return for empty data
        if not filtered_cases:
            return {"top_healthcare": [], "all_healthcare": []}

        # Track disease counts per portal
        portal_diseases = defaultdict(set)
        # Track news counts per portal
        portal_counts = Counter()

        # Process healthcare news only
        for case in filtered_cases:
            portal = case.get("news__portal")
            news_type = case.get("news__type")
            disease = case.get("disease__name")

            # Skip non-healthcare or missing portal news
            if not (portal and news_type and news_type.lower() == "kesehatan"):
                continue

            # Count this news article
            portal_counts[portal] += 1

            # Add disease if present
            if disease:
                portal_diseases[portal].add(disease)

        # Create top_healthcare with sorted news counts
        top_healthcare = [
            {"portal": portal, "count": count}
            for portal, count in portal_counts.most_common(5)
        ]

        # Create all_healthcare with news and disease counts
        all_healthcare = [
            {
                "portal": portal,
                "news_count": count,
                "disease_count": len(portal_diseases[portal])
            }
            for portal, count in portal_counts.items()
        ]

        return {"top_healthcare": top_healthcare, "all_healthcare": all_healthcare}

class LocalPortalStatisticsReport:
    """Generates local portal statistics"""

    def generate_report(self, filtered_cases=None):
        """
        Generates local portal statistics report

        Returns:
            dict: Contains two keys:
                - top_local: List of portals sorted by news count
                - all_local: List of portals with news and disease counts
        """
        if not filtered_cases:
            return {
                "top_local": [],
                "all_local": []
            }
        
        portal_diseases = defaultdict(set)
        portal_counts = Counter()

        # Process local news only
        for case in filtered_cases:
            portal = case.get("news__portal")
            news_type = case.get("news__type")
            disease = case.get("disease__name")

            # Skip non-local or missing portal news
            if not (portal and news_type and news_type.lower() == "lokal"):
                continue

            # Count this news article
            portal_counts[portal] += 1

            # Add disease if present
            if disease:
                portal_diseases[portal].add(disease)
        
        top_local = [
            {"portal": portal, "count": count}
            for portal, count in portal_counts.most_common(5)
        ]

        all_local = [
            {
                "portal": portal,
                "news_count": count,
                "disease_count": len(portal_diseases[portal])
            }
            for portal, count in portal_counts.items()
        ]

        return {
            "top_local": top_local,
            "all_local": all_local
        }
    

class AverageSeverityByProvince:
    STATUS_ENCODING = {
        "minimal": 1,
        "biasa": 2,
        "bahaya": 3,
        "katastropik": 4
    }

    def __init__(self, case_service):
        self.case_service = case_service
        self.PROVINCE_TO_CODE = PROVINCE_TO_CODE

    def compute(self):
        """
        Hitung weighted severity score dan kategorisasi status untuk setiap provinsi.
        Output: list of dicts [{ "id": province_code, "value": float, "status": str }, ...]
        """
        data = self.case_service.get_status_and_province()
        province_scores = defaultdict(list)

        for record in data:
            status = record.get("status")
            province = record.get("location__province")

            if status and province:
                status = status.lower()
                if status in self.STATUS_ENCODING:
                    encoded = self.STATUS_ENCODING[status]
                    province_scores[province].append(encoded)

        if not province_scores:
            return []

        weighted_result = {}
        all_scores = []

        for province, scores in province_scores.items():
            avg = sum(scores) / len(scores)
            weight = math.log(len(scores) + 1)
            weighted_score = round(avg * weight, 2)
            weighted_result[province] = {"value": weighted_score}
            all_scores.append(weighted_score)

        # Hitung kuartil dinamis
        q1 = np.percentile(all_scores, 25)
        q2 = np.percentile(all_scores, 50)
        q3 = np.percentile(all_scores, 75)

        # Klasifikasi berdasarkan score
        for province, result in weighted_result.items():
            score = result["value"]
            if score <= q1:
                result["status"] = "minimal"
            elif score <= q2:
                result["status"] = "biasa"
            elif score <= q3:
                result["status"] = "bahaya"
            else:
                result["status"] = "katastropik"
                
            # Add province code
            result["id"] = self.PROVINCE_TO_CODE.get(province, province)

        # Convert dictionary to list format
        formatted_result = [
            {
                "id": data["id"],
                "value": data["value"],
                "status": data["status"]
            } for province, data in weighted_result.items()
        ]

        return formatted_result
