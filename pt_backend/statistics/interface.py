from abc import ABC, abstractmethod

class ReportStrategy(ABC):
    """
    Abstract base class for report strategies.
    """

    @abstractmethod
    def generate_report(self, filtered_cases = None, **kwargs):
        """
        Generate a report based on the provided data.
        """