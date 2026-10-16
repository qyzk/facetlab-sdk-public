# FacetLab Python SDK

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Test before you launch.** AI shoppers react to your product pages in hours, not 3 weeks.
Results are an AI simulation for pre-testing ideas, not a sales forecast.

## Installation

```bash
pip install git+https://github.com/qyzk/facetlab-sdk-public.git
```

Version 0.2.0, Python 3.8+. (Not on PyPI yet.)

## Quick start

1. Sign up at [qyzkdesign.com](https://qyzkdesign.com) and create an API key at
   [qyzkdesign.com/dashboard/api-keys](https://qyzkdesign.com/dashboard/api-keys).
2. Run a product page test (2–6 versions of a product page on TikTok Shop or Amazon in the US, UK or Asia):

```python
from facetlab import FacetLabClient

client = FacetLabClient(api_key="fl_...")       # create a key at https://qyzkdesign.com/dashboard/api-keys
spec = {
    "name": "Shoe cabinet page test", "market": "tiktok_us",
    "product": {"name": "White 3-Tier Foldable Shoe Cabinet", "use": "Entryway shoe storage",
                "dimensions": "17.3 x 13.8 x 20.87 in"},
    "pricing": {"current_price": 37.69, "shipping": "Free shipping shown"},
    "scenario": {"shopper_intent": "browsing"},   # recommended; "in_market" assumes buying intent
    "question": {"primary": "Would you buy this shoe cabinet at the shown price?"},
    "arms": [{"id": "A", "label": "Original page"}, {"id": "B", "label": "Adjusted layout"},
             {"id": "C", "label": "Price emphasized"}],
}
print(client.product_tests.estimate(spec))
test = client.product_tests.create(spec, images={"A": "a.png", "B": "b.png", "C": "c.png"})
done = client.product_tests.wait(test["id"])
print(done["results"]["narrative"]["en"]["headline"])
```

Images must be PNG, JPEG or WebP (checked from the file contents), up to 5 MB each and at most
80 megapixels for JPEG, 45 for PNG, 25 for transparent PNG and 12 for WebP (checked locally before upload).

### Optional: compare different products

To compare different products rather than page designs (e.g. a 2-tier vs a 3-tier shoe rack), give a variant its own
facts with `product` (`name`, `variant`, `use`, `material`, `dimensions`, `inner_dimensions`, `key_features`,
`limitations`) and `pricing` (`current_price`, `shipping`, `delivery`). Each field you set replaces the shared value
for that variant (lists replace too); omitted fields fall back to the shared `product` and `pricing`, which describe
the control (A). Send only what differs.

```python
spec = {
    "name": "Shoe rack: 3-tier plastic vs 2-tier bamboo", "market": "tiktok_us",
    "product": {"name": "3-Tier Plastic Shoe Rack", "use": "Entryway shoe storage",
                "material": "Plastic", "dimensions": "20.9 in tall"},
    "pricing": {"current_price": 37.69, "shipping": "Free shipping shown"},
    "scenario": {"shopper_intent": "browsing"},
    "question": {"primary": "Would you buy this shoe rack at the shown price?"},
    "arms": [{"id": "A", "label": "3-tier plastic rack"},
             {"id": "B", "label": "2-tier bamboo rack",
              "product": {"name": "2-Tier Bamboo Shoe Rack", "material": "Bamboo", "dimensions": "14 in tall"},
              "pricing": {"current_price": 29.99}}],
}
```

Each variant's AI shoppers see that variant's facts. The estimate then includes a `different_products` scope
warning: differences reflect the product, its price and its page together. Gaps that only some variants have are
reported as `arms.<ID>.<field>` (e.g. `arms.B.product.material`). Credits and statistics are unchanged.

Credits: 1 credit = 5 sessions × 1 persona × 1 variant, so a test costs
`persona_count × variants × ceil(sessions_per_arm / 5)` credits (e.g. 25 personas × 3 variants × 5 sessions = 75 credits).
The free plan includes 6 free tests in total (shared by the web app, the Assistant and the API) and allows at most
50 personas and 5 sessions per variant per test (larger requests return `tier_limit`; no free tests left returns `free_tier_limit`).
A test that fails before any persona finishes is refunded automatically; partially completed failed tests are charged.


Errors raise `facetlab.exceptions.FacetLabError` (with `.code`, e.g. `tier_limit`, `free_tier_limit`, `audience_too_small`).

Full API reference: [qyzkdesign.com/docs](https://qyzkdesign.com/docs).

## UI A/B tests and mockups

UI A/B tests (control vs treatment screenshots) and AI mockup generation currently run in the web app and the
Assistant at [qyzkdesign.com](https://qyzkdesign.com). The SDK's older `run_experiment()` and `generate_mockups()`
calls do not accept API keys created in the current dashboard; use the web app for these for now.

## Pricing

See [qyzkdesign.com/pricing](https://qyzkdesign.com/pricing). The free plan includes 6 free tests in total.

## Support

- Documentation: [qyzkdesign.com/docs](https://qyzkdesign.com/docs)
- Email: qyzkai@gmail.com
- Issues: [GitHub Issues](https://github.com/qyzk/facetlab-sdk-public/issues)

## License

MIT License - see [LICENSE](./LICENSE) for details.
