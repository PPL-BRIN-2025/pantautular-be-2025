from collections.abc import Iterable
from datetime import datetime
from typing import Optional

from pt_backend.interfaces import CaseRepositoryInterface

from ..interface import ReportStrategy


class PrevalenceStatistics(ReportStrategy):
    def __init__(self, repository: CaseRepositoryInterface):
        self.repository = repository
        self.POPULATION_DATA = {
            2019: 266_911_900,
            2020: 270_203_900,
            2021: 272_682_500,
            2022: 275_773_800,
            2023: 278_696_200,
            2024: 281_603_800,
        }

    def generate_report(self, filtered_cases=None, **kwargs) -> dict:
        try:
            year = self._resolve_year(filtered_cases, kwargs)
            cases_queryset = self._resolve_cases_queryset(filtered_cases, year)
            total_cases = self._count_cases(cases_queryset)

            population = self._resolve_population(year)
            if not population:
                return {
                    "year": year,
                    "total_cases": total_cases,
                    "population": "Angka jiwa belum tercatat",
                    "prevalence": "No Data",
                }

            prevalence = (total_cases / population) * 100 if population else 0

            return {
                "year": year,
                "total_cases": total_cases,
                "population": population,
                "prevalence": round(prevalence, 4),
            }
        except Exception as exc:
            return {"error": f"Error calculating prevalence: {exc}"}

    def _resolve_year(self, filtered_cases, kwargs) -> int:
        start_date = kwargs.get("start_date")
        date_range = kwargs.get("date_range") or {}
        date_range_start = None

        if isinstance(date_range, dict):
            date_range_start = date_range.get("start")
        elif isinstance(date_range, Iterable) and not isinstance(date_range, (str, bytes)):
            for item in date_range:
                date_range_start = item
                break

        candidate = start_date or date_range_start
        parsed_year = self._parse_year(candidate)
        if parsed_year:
            return parsed_year

        queryset_year = self._infer_year_from_queryset(filtered_cases)
        if queryset_year:
            return queryset_year

        return datetime.now().year

    def _parse_year(self, value: Optional[str]) -> Optional[int]:
        if not value:
            return None

        if isinstance(value, datetime):
            return value.year

        try:
            if isinstance(value, str):
                if "T" in value:
                    value = value.split("T", 1)[0]
                return datetime.strptime(value, "%Y-%m-%d").year
        except ValueError:
            return None

        return None

    def _infer_year_from_queryset(self, filtered_cases) -> Optional[int]:
        if not hasattr(filtered_cases, "first"):
            return None

        first_case = filtered_cases.order_by("news__date_published").first()
        if not first_case:
            return None

        published = getattr(first_case, "news", None)
        if hasattr(published, "date_published") and published.date_published:
            return published.date_published.year

        return None

    def _resolve_cases_queryset(self, filtered_cases, year):
        if hasattr(filtered_cases, "filter"):
            return filtered_cases.filter(news__date_published__year=year)

        return self.repository.get_cases_by_year(year)

    def _count_cases(self, cases_queryset) -> int:
        if hasattr(cases_queryset, "count"):
            return cases_queryset.count()

        if isinstance(cases_queryset, Iterable):
            return len(list(cases_queryset))

        return 0

    def _resolve_population(self, year: int) -> Optional[int]:
        if year in self.POPULATION_DATA:
            return self.POPULATION_DATA[year]

        known_years = sorted(self.POPULATION_DATA.keys())
        previous_years = [y for y in known_years if y <= year]
        if previous_years:
            return self.POPULATION_DATA[previous_years[-1]]

        return None