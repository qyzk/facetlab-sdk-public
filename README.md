# FacetLab Python SDK

[![PyPI version](https://badge.fury.io/py/facetlab.svg)](https://pypi.org/project/facetlab/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**AI-powered pre-launch A/B testing** - Predict experiment outcomes before going live.

```python
from facetlab import FacetLabClient

client = FacetLabClient(api_key="fl_xxxx")
result = client.run_experiment(
    control_image="control.png",
    treatment_image="treatment.png",
    locale="usa"
)
print(f"Winner: {result.winner} (confidence: {result.confidence})")
```

## Installation

```bash
pip install facetlab
```

## Quick Start

### 1. Get Your API Key

Sign up at [qyzkdesign.com](https://qyzkdesign.com) and get your API key from the dashboard.

### 2. Run Your First Experiment

```python
from facetlab import FacetLabClient

# Initialize with your API key
client = FacetLabClient(api_key="fl_your_api_key")

# Run A/B test simulation
result = client.run_experiment(
    control_image="screenshots/control.png",
    treatment_image="screenshots/treatment.png",
    context="E-commerce checkout page redesign",
    locale="usa",        # usa, europe, or asia
    persona_count=100    # 50-5000 based on your tier
)

# Get results
print(f"Winner: {result.winner}")           # "treatment" or "control"
print(f"Confidence: {result.confidence}")   # 0.87
print(f"Lift: {result.lift}")               # "+12.3%"
print(f"Recommendations: {result.recommendations}")
```

## Features

### A/B Test Simulation
- Run virtual experiments with AI personas before launch
- 91% prediction accuracy validated against real experiments
- Demographic segmentation (age, income, tech-savviness)
- Actionable recommendations

### Mockup Generation (BYOK)
Generate UI mockups based on recommendations using your own Gemini API key:

```python
result = client.generate_mockups(
    control_image="control.png",
    recommendation="Make the CTA button larger and green",
    gemini_api_key="AIza...",  # Your Gemini key
    num_variations=2
)

# Download generated images
saved_files = result.download_images("./mockups")
print(f"Saved: {saved_files}")
```

## API Reference

### FacetLabClient

```python
client = FacetLabClient(
    api_key: str,           # Your API key (fl_xxxx)
    model: str = "claude-3-haiku-20240307",  # Model (Pro tier for advanced)
    base_url: str = None    # Optional custom URL for enterprise
)
```

### run_experiment()

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `control_image` | str | Yes | Path to control image (PNG/JPG) |
| `treatment_image` | str | Yes | Path to treatment image (PNG/JPG) |
| `locale` | str | Yes | "usa", "europe", or "asia" |
| `persona_count` | int | No | 50-5000 (default: 100) |
| `context` | str | No | Description of the experiment |
| `scenario` | str | No | ui_change, price, promo, content, ranking, cart |

### generate_mockups()

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `control_image` | str | Yes | Path to control image |
| `recommendation` | str | Yes | What change to implement |
| `gemini_api_key` | str | Yes | Your Google Gemini API key |
| `num_variations` | int | No | 1-4 (default: 2) |

## Pricing

| Tier | Base Fee | Per-Persona | Models |
|------|----------|-------------|--------|
| Free | $0 | 6 experiments included | Haiku only |
| Base | $59.70/mo | $1.00 | Haiku only |
| Pro | $299.70/mo | $0.75 | All Claude models |
| Enterprise | Custom | Volume discount | All + BYOC |

Mockup generation uses your Gemini API key (~$0.04/image billed by Google).

## Examples

See the [examples](./examples/) folder for complete working examples:

- `basic_experiment.py` - Simple A/B test
- `mockup_generation.py` - Generate UI mockups
- `batch_experiments.py` - Run multiple tests

## Support

- 📚 Documentation: [qyzkdesign.com/docs/sdk](https://qyzkdesign.com/docs/sdk)
- 📧 Email: support@qyzkdesign.com
- 🐛 Issues: [GitHub Issues](https://github.com/qyzk/facetlab-sdk/issues)

## License

MIT License - see [LICENSE](./LICENSE) for details.
