"""
FacetLab SDK - Mockup Generation Client (BYOK - Bring Your Own Key)
"""

import os
import base64
import requests
from typing import Optional, Union, List, Dict, Any
from pathlib import Path

from .models import MockupImage
from .exceptions import (
    AuthenticationError,
    ValidationError,
    MockupGenerationError
)


class MockupClient:
    """
    FacetLab client for generating UI mockups based on recommendations.
    
    Requires user's own Gemini API key (BYOK - Bring Your Own Key).
    
    Example:
        >>> client = MockupClient(
        ...     api_key="fl_xxxx",
        ...     gemini_api_key="AIza..."
        ... )
        >>> images = client.generate_mockup(
        ...     recommendation="Add social proof badges near CTA",
        ...     control_image="control.png",
        ...     style_guidelines={"brand_colors": ["#2563EB"]}
        ... )
        >>> images[0].save("mockup_0.png")
    """
    
    DEFAULT_BASE_URL = "https://api.qyzkdesign.com/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120
    ):
        """
        Initialize MockupClient.
        
        Args:
            api_key: FacetLab API key (or set FACETLAB_API_KEY env var)
            gemini_api_key: Your Google Gemini API key (required)
            base_url: API base URL (default: production)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.environ.get("FACETLAB_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "FacetLab API key required. Pass api_key or set FACETLAB_API_KEY environment variable."
            )
        
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise AuthenticationError(
                "Gemini API key required. Pass gemini_api_key or set GEMINI_API_KEY environment variable."
            )
        
        self.base_url = base_url or os.environ.get("FACETLAB_BASE_URL", self.DEFAULT_BASE_URL)
        self.timeout = timeout
        
        # Session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "FacetLab-Python-SDK/0.1.0"
        })
    
    def _encode_image(self, image_path: Union[str, Path, bytes]) -> str:
        """Encode image to base64."""
        if isinstance(image_path, bytes):
            return base64.b64encode(image_path).decode("utf-8")
        
        path = Path(image_path)
        if not path.exists():
            raise ValidationError(f"Image file not found: {image_path}", field="control_image")
        
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make HTTP request with error handling."""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", self.timeout)
        
        try:
            response = self._session.request(method, url, **kwargs)
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            elif response.status_code >= 400:
                data = response.json()
                raise MockupGenerationError(data.get("error", "Request failed"))
            
            return response.json()
            
        except requests.RequestException as e:
            raise MockupGenerationError(f"Network error: {str(e)}")
    
    def generate_mockup(
        self,
        recommendation: str,
        control_image: Union[str, Path, bytes],
        style_guidelines: Optional[Dict[str, Any]] = None,
        num_variations: int = 1,
        output_format: str = "png"
    ) -> List[MockupImage]:
        """
        Generate UI mockups based on a recommendation.
        
        Args:
            recommendation: Text description of what to change/add
            control_image: Path or bytes of the original screenshot
            style_guidelines: Optional styling constraints:
                - brand_colors: List of hex colors (e.g., ["#2563EB", "#10B981"])
                - font_family: Font name (e.g., "Inter")
                - button_style: Button style (e.g., "rounded", "square")
                - tone: Design tone (e.g., "professional", "playful")
            num_variations: Number of mockup variations to generate (1-4)
            output_format: Image format ("png" or "jpeg")
            
        Returns:
            List of MockupImage objects
        """
        # Validate inputs
        if not recommendation or len(recommendation.strip()) < 10:
            raise ValidationError(
                "Recommendation must be at least 10 characters",
                field="recommendation"
            )
        
        if num_variations < 1 or num_variations > 4:
            raise ValidationError(
                "num_variations must be between 1 and 4",
                field="num_variations"
            )
        
        if output_format not in ("png", "jpeg"):
            raise ValidationError(
                "output_format must be 'png' or 'jpeg'",
                field="output_format"
            )
        
        # Prepare request
        payload = {
            "recommendation": recommendation,
            "control_image": self._encode_image(control_image),
            "style_guidelines": style_guidelines or {},
            "num_variations": num_variations,
            "output_format": output_format,
            # Gemini key passed per-request, never stored
            "gemini_api_key": self.gemini_api_key
        }
        
        # Submit generation request
        response = self._make_request("POST", "/mockups/generate", json=payload)
        
        # Parse response
        images = []
        for i, img_data in enumerate(response.get("images", [])):
            image_bytes = base64.b64decode(img_data["data"])
            images.append(MockupImage(
                image_data=image_bytes,
                format=output_format,
                recommendation_index=0,
                variation_index=i
            ))
        
        if not images:
            raise MockupGenerationError(
                "No images returned from generation",
                recommendation=recommendation
            )
        
        return images
    
    def generate_from_experiment(
        self,
        job_id: str,
        recommendation_indices: Optional[List[int]] = None,
        style_guidelines: Optional[Dict[str, Any]] = None,
        num_variations: int = 1
    ) -> Dict[int, List[MockupImage]]:
        """
        Generate mockups for recommendations from a completed experiment.
        
        Args:
            job_id: Experiment job ID
            recommendation_indices: Which recommendations to generate for (default: all)
            style_guidelines: Optional styling constraints
            num_variations: Number of variations per recommendation
            
        Returns:
            Dict mapping recommendation index to list of MockupImages
        """
        payload = {
            "job_id": job_id,
            "recommendation_indices": recommendation_indices,
            "style_guidelines": style_guidelines or {},
            "num_variations": num_variations,
            "gemini_api_key": self.gemini_api_key
        }
        
        response = self._make_request("POST", "/mockups/from-experiment", json=payload)
        
        result = {}
        for rec_idx, images_data in response.get("mockups", {}).items():
            rec_idx = int(rec_idx)
            result[rec_idx] = []
            for i, img_data in enumerate(images_data):
                image_bytes = base64.b64decode(img_data["data"])
                result[rec_idx].append(MockupImage(
                    image_data=image_bytes,
                    format="png",
                    recommendation_index=rec_idx,
                    variation_index=i
                ))
        
        return result
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()
