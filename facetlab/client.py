"""
FacetLab API Client
"""

import base64
import time
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlsplit
import requests

from ._http import check
from .exceptions import FacetLabError, InsufficientFundsError
from .models import ExperimentResult, MockupResult


def _v1_base_url(base_url: str) -> str:
    """'<scheme>://<host>/api/v1' for a base URL ending in '/api', '/api/sdk' or a bare host."""
    parts = urlsplit(base_url.strip())
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"base_url must be an absolute URL, got {base_url!r}")
    return f"{parts.scheme}://{parts.netloc}/api/v1"


class FacetLabClient:
    """
    FacetLab SDK Client for running A/B test simulations and generating mockups.
    
    Example:
        client = FacetLabClient(api_key="fl_xxxx")
        result = client.run_experiment(
            control_image="control.png",
            treatment_image="treatment.png",
            locale="usa"
        )
        print(result.winner)  # "treatment" or "control"
    """
    
    BASE_URL = "https://qyzkdesign.com/api/sdk"
    
    def __init__(
        self, 
        api_key: str,
        model: str = "claude-3-haiku-20240307",
        base_url: Optional[str] = None
    ):
        """
        Initialize FacetLab client.
        
        Args:
            api_key: Your FacetLab API key (starts with 'fl_')
            model: Model to use. Free/Base tier: haiku only. Pro tier: all Claude models.
            base_url: Optional custom API URL (for enterprise deployments)
        """
        if not api_key or not api_key.startswith("fl_"):
            raise ValueError("API key must start with 'fl_'")
        
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or self.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
        from .agent import AgentClient
        from .product_tests import ProductTestsClient
        v1_base = _v1_base_url(base_url or self.BASE_URL)
        self._v1 = v1_base
        self.product_tests = ProductTestsClient(self.session, v1_base, account=self.account)
        self.agent = AgentClient(self.session, v1_base.rsplit("/api/v1", 1)[0])

    def account(self) -> Dict[str, Any]:
        """Free tests left, prepaid balance (USD) and the per-persona rates of the current period.

        Example: {"plan": "pay_as_you_go", "free_tests": {"used": 1, "limit": 2, "remaining": 1},
        "balance": 25.0, "rates": {"first_tests": 10, "first_rate": 1.99, "then_rate": 2.99, ...},
        "next_test_rate": 1.99, ...}
        """
        return check(self.session.get(f"{self._v1}/account", timeout=30))

    def check_funds(self, persona_units: float) -> Dict[str, Any]:
        """Raises InsufficientFundsError before anything is uploaded when the next test cannot be paid.

        A free test (if any is left) covers the test; otherwise its cost is persona units x the next test's rate.
        The server checks the exact cost again when the test starts.
        """
        acct = self.account()
        free = acct.get("free_tests") or {}
        if free.get("remaining", 0) > 0 or acct.get("balance") is None:
            return acct
        cost = round(max(1, -(-persona_units // 1)) * acct["next_test_rate"], 2)
        if acct["balance"] < cost:
            raise InsufficientFundsError(
                f"Insufficient funds: this test costs about ${cost:.2f} and your balance is ${acct['balance']:.2f}. "
                "Top up at https://qyzkdesign.com/dashboard/billing",
                required=cost, balance=acct["balance"])
        return acct
    
    def run_experiment(
        self,
        control_image: str,
        treatment_image: str,
        locale: str = "usa",
        persona_count: int = 25,
        context: str = "",
        scenario: str = "ui_change",
        experiment_name: Optional[str] = None,
        positive_decision: str = "",
        negative_decision: str = "",
        user_query: str = "",
        experiment_goal: str = "",
        poll_interval: int = 15,
        timeout: int = 1800,
        check_balance: bool = True,
    ) -> ExperimentResult:
        """
        Run an A/B test simulation with AI personas.
        
        Args:
            control_image: Path to control image (PNG/JPG)
            treatment_image: Path to treatment image (PNG/JPG)
            locale: Region for personas - "usa", "europe", or "asia"
            persona_count: Number of personas: up to 25 without a plan, 200 on Base, 500 on Pro
                (a larger number is lowered to your limit)
            context: Description of the experiment
            scenario: Type of change - ui_change, price, promo, content, ranking, cart
            experiment_name: Optional name for the experiment
            positive_decision: Optional positive action description
            negative_decision: Optional negative action description
            user_query: Optional user research question
            experiment_goal: Optional goal description
            poll_interval: Seconds between status checks (default: 15)
            timeout: Max seconds to wait (default: 1800)
            check_balance: Check free tests and balance first (raises InsufficientFundsError before uploading)
            
        Returns:
            ExperimentResult with winner, confidence, lift, segmentation, recommendations
        """
        # Validate locale
        if locale not in ["usa", "europe", "asia"]:
            raise ValueError("locale must be 'usa', 'europe', or 'asia'")
        
        if check_balance:
            self.check_funds(persona_count)

        # Load and encode images
        control_b64 = self._load_image(control_image)
        treatment_b64 = self._load_image(treatment_image)
        
        # Create experiment
        payload = {
            "control_image": control_b64,
            "treatment_image": treatment_b64,
            "locale": locale,
            "persona_count": persona_count,
            "context": context,
            "scenario": scenario,
            "model": self.model,
            "experiment_name": experiment_name or f"SDK Experiment {int(time.time())}",
            "positive_decision": positive_decision,
            "negative_decision": negative_decision,
            "user_query": user_query,
            "experiment_goal": experiment_goal
        }
        
        result = check(self.session.post(f"{self.base_url}/experiments/create", json=payload, timeout=120))
        return self.wait_experiment(result["job_id"], poll_interval=poll_interval, timeout=timeout)

    def get_experiment(self, job_id: str) -> Dict[str, Any]:
        """Status (and, once completed, the results) of one of your UI A/B tests."""
        return check(self.session.get(f"{self.base_url}/experiments/{job_id}", timeout=30))

    def wait_experiment(self, job_id: str, poll_interval: int = 15, timeout: int = 1800) -> ExperimentResult:
        """Polls a UI A/B test until it completes; raises FacetLabError if it fails or times out."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_data = self.get_experiment(job_id)
            if status_data["status"] == "completed":
                return ExperimentResult.from_api_response(status_data)
            if status_data["status"] == "failed":
                raise FacetLabError(f"Experiment failed: {status_data.get('error') or 'unknown error'}", code="failed")
            time.sleep(poll_interval)
        raise FacetLabError(f"Experiment {job_id} did not complete within {timeout} seconds", code="timeout")
    
    def generate_mockups(
        self,
        control_image: str,
        recommendation: str,
        gemini_api_key: str,
        num_variations: int = 2,
        style_guidelines: Optional[Dict[str, Any]] = None,
        poll_interval: int = 10,
        timeout: int = 180
    ) -> MockupResult:
        """
        Generate UI mockups based on a recommendation (BYOK - Bring Your Own Gemini Key).
        
        Args:
            control_image: Path to control image (PNG/JPG)
            recommendation: What change to implement (min 10 chars)
            gemini_api_key: Your Google Gemini API key (starts with 'AIza')
            num_variations: Number of variations to generate (1-4)
            style_guidelines: Optional style preferences dict
            poll_interval: Seconds between status checks (default: 10)
            timeout: Max seconds to wait (default: 180)
            
        Returns:
            MockupResult with image URLs
        """
        if len(recommendation) < 10:
            raise ValueError("recommendation must be at least 10 characters")
        
        if not gemini_api_key or not gemini_api_key.startswith("AIza"):
            raise ValueError("gemini_api_key must be a valid Google API key")
        
        control_b64 = self._load_image(control_image)
        
        payload = {
            "gemini_api_key": gemini_api_key,
            "recommendation": recommendation,
            "control_image": control_b64,
            "num_variations": min(max(num_variations, 1), 4),
            "style_guidelines": style_guidelines or {}
        }
        
        response = self.session.post(f"{self.base_url}/mockups/generate", json=payload)
        response.raise_for_status()
        result = response.json()
        
        job_id = result["job_id"]
        
        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_response = self.session.get(f"{self.base_url}/mockups/status/{job_id}")
            status_response.raise_for_status()
            status_data = status_response.json()
            
            if status_data["status"] == "completed":
                return MockupResult.from_api_response(status_data)
            elif status_data["status"] == "failed":
                raise RuntimeError(f"Mockup generation failed: {status_data.get('error', 'Unknown error')}")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Mockup generation did not complete within {timeout} seconds")
    
    def _load_image(self, image_path: str) -> str:
        """Load an image and return base64 encoded string."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
