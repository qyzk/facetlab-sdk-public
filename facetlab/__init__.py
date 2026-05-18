"""
FacetLab SDK - AI-powered pre-launch A/B testing

Usage:
    from facetlab import FacetLabClient
    
    client = FacetLabClient(api_key="fl_xxxx")
    result = client.run_experiment(
        control_image="control.png",
        treatment_image="treatment.png",
        locale="usa"
    )
    print(result.winner)
"""

from .client import FacetLabClient
from .models import ExperimentResult, MockupResult

__version__ = "0.1.0"
__all__ = ["FacetLabClient", "ExperimentResult", "MockupResult"]
