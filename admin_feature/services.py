from django.core.cache import cache as django_cache
from pt_backend.repositories import CaseRepository


class DatasetsService:
    """
    Encapsulates business logic for dataset (case) metrics:
    - Caches the total count for a short TTL to reduce DB load
    - Delegates data access to the CaseRepository
    """

    def __init__(self, repository=None, cache_backend=None, cache_key: str = 'admin:datasets:count', ttl: int = 60):
        self.repository = repository or CaseRepository()
        self.cache = cache_backend or django_cache
        self.cache_key = cache_key
        self.ttl = ttl

    def get_total_datasets(self) -> int:
        value = self.cache.get(self.cache_key)
        if value is None:
            value = int(self.repository.count_cases())
            self.cache.set(self.cache_key, value, self.ttl)
        return value
