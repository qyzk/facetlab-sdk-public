"""
FacetLab SDK Data Models
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ExperimentResult:
    """Result from an A/B test simulation."""
    
    job_id: str
    winner: str  # "treatment" or "control"
    confidence: float  # 0.0 to 1.0
    lift: str  # e.g., "+12.3%"
    treatment_score: float
    control_score: float
    segmentation: Dict[str, Any]
    recommendations: List[str]
    report_url: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "ExperimentResult":
        """Create ExperimentResult from API response."""
        return cls(
            job_id=data.get("job_id", ""),
            winner=data.get("winner", "unknown"),
            confidence=data.get("confidence", 0.0),
            lift=data.get("lift", "0%"),
            treatment_score=data.get("treatment_score", 0.0),
            control_score=data.get("control_score", 0.0),
            segmentation=data.get("segmentation", {}),
            recommendations=data.get("recommendations", []),
            report_url=data.get("report_url"),
            raw_response=data
        )
    
    def __repr__(self) -> str:
        return f"ExperimentResult(winner='{self.winner}', confidence={self.confidence:.2f}, lift='{self.lift}')"


@dataclass
class MockupImage:
    """A generated mockup image."""
    
    url: str
    key: str
    variation_index: int
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockupImage":
        return cls(
            url=data.get("url", ""),
            key=data.get("key", ""),
            variation_index=data.get("variation_index", 0)
        )


@dataclass
class MockupResult:
    """Result from mockup generation."""
    
    job_id: str
    status: str
    images: List[MockupImage]
    count: int
    raw_response: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "MockupResult":
        """Create MockupResult from API response."""
        images = [MockupImage.from_dict(img) for img in data.get("images", [])]
        return cls(
            job_id=data.get("job_id", ""),
            status=data.get("status", "unknown"),
            images=images,
            count=data.get("count", len(images)),
            raw_response=data
        )
    
    def __repr__(self) -> str:
        return f"MockupResult(status='{self.status}', count={self.count})"
    
    def download_images(self, output_dir: str = ".") -> List[str]:
        """
        Download all generated images to a directory.
        
        Args:
            output_dir: Directory to save images (default: current directory)
            
        Returns:
            List of saved file paths
        """
        import os
        import requests
        
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []
        
        for i, img in enumerate(self.images):
            ext = img.key.split(".")[-1] if "." in img.key else "png"
            filename = f"mockup_{i}.{ext}"
            filepath = os.path.join(output_dir, filename)
            
            response = requests.get(img.url)
            response.raise_for_status()
            
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            saved_paths.append(filepath)
        
        return saved_paths
