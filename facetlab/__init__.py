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
from .mockup import MockupClient
from .product_tests import ProductTestsClient
from .models import ExperimentResult, MockupResult

__version__ = "0.2.0"
__all__ = ["FacetLabClient", "ExperimentResult", "MockupResult", "ProductTestsClient", "MockupClient"]
