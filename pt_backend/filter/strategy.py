from typing import Dict, Any, Optional, Protocol
from django.db.models import Q

class FilterStrategy(Protocol):
    @property
    def field_name(self) -> str:
        pass  # pragma: no cover

    def should_apply(self, data: Dict) -> bool:
        return bool(data.get(self.field_name))

    def build_query(self, value: Any) -> Q:
        pass  # pragma: no cover

    def apply(self, data: Dict) -> Optional[Q]:
        if self.should_apply(data):
            return self.build_query(data[self.field_name])
        return None 
