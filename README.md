# FacetLab Python SDK

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Know which page sells before you launch.** AI shoppers react to your product pages and UI changes in hours, not 3 weeks.
Results are an AI simulation for pre-testing ideas, not a sales forecast.

## Installation

```bash
pip install git+https://github.com/qyzk/facetlab-sdk-public.git
```

Version 0.3.0, Python 3.8+. (Not on PyPI yet.) To upgrade: `pip install -U git+https://github.com/qyzk/facetlab-sdk-public.git`.

## Quick start

1. Sign up at [qyzkdesign.com](https://qyzkdesign.com) (we email you a code to verify your address) and create an
   API key at [qyzkdesign.com/dashboard/api-keys](https://qyzkdesign.com/dashboard/api-keys). A key is shown only
   once: if you didn't copy it, revoke it there and create a new one.
2. Optional: add a card on [Billing](https://qyzkdesign.com/dashboard/billing) for a one-time $25 credit
   (a $0 check, nothing is charged) and top up your balance. See [Billing](#billing) below.
3. Run a product page test (2–6 versions of a product page on TikTok Shop or Amazon in the US, UK or Asia):

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

Product page tests use credits for their monthly cap: `persona_count × variants × ceil(sessions_per_arm / 5)`
(e.g. 25 personas × 3 variants × 5 sessions = 75 credits). A free test covers up to 100 personas, 2 variants and 5
sessions per variant; larger tests are paid from your balance (up to 100 personas per test without a plan, 500 on
Base, 2,000 on Pro; 3–10 sessions per variant).

### Fill product facts from a listing

Read the facts from up to 2 listing screenshots and/or the pasted listing text, then check them before you use them in
the spec. Nothing is guessed: facts the listing does not show come back as `None`.

```python
facts = client.product_tests.extract_facts(["listing.png"], text=open("listing.txt").read(), market="tiktok_us")
print(facts["facts"], facts["notes"])   # name, variant, use, current_price, dimensions, material, key_features, shipping
```

Full API reference: [qyzkdesign.com/docs](https://qyzkdesign.com/docs).

## UI A/B tests

Compare two screenshots of the same page (control and treatment), such as a sign-up or subscribe page:

```python
result = client.run_experiment(
    control_image="control.png", treatment_image="treatment.png",
    locale="usa",                      # "usa", "europe" or "asia"
    persona_count=25,                  # up to 100 without a plan, 500 on Base, 2,000 on Pro
                                       # (a larger persona_count is lowered to the limit)
    context="Sign-up page: bigger free-trial banner",
    positive_decision="Start the free trial", negative_decision="Leave the page",
)
print(result.winner, result.lift, result.confidence)
```

`run_experiment` checks your free tests and balance first, uploads both screenshots, starts the test and waits for the
result (`timeout=1800` seconds by default). Use `client.get_experiment(job_id)` and `client.wait_experiment(job_id)`
to follow a test yourself. Screenshots are PNG, JPEG or WebP; both together must stay under about 3 MB.

## Billing

Every test you start through the API is counted and paid like one started in the app:

1. **Free tests first:** 2 free tests in total, shared by the web app, the Assistant and the API. A free test covers
   up to 100 personas, 2 variants and 5 sessions per variant. Base and Pro subscribers don't use free tests.
2. **Then your prepaid balance**, charged when the test starts, **per persona per variant** (also for any test larger
   than a free test covers, even while free tests remain):
   - without a plan: $0.80 (up to 50 tests a month, up to 100 personas per test);
   - Base: $0.50 for the first 10 tests of each billing period, then $0.55 (up to 50 tests, 500 personas per test);
   - Pro: $0.35 for the first 50, then $0.40 (up to 1,000 tests, 2,000 personas per test).

   A test costs `personas × variants × (sessions ÷ 5)` persona-variants × the rate. A UI A/B test has 2 variants
   (control and treatment), so 100 personas = 200 persona-variants: $160 without a plan.

Add a card on [Billing](https://qyzkdesign.com/dashboard/billing) for a one-time $25 credit, and top up with $50,
$100 or $250. A test that fails before any persona finishes is refunded to your balance.

```python
acct = client.account()
print(acct["free_tests"], acct["balance"], acct["next_test_rate"])   # e.g. {'remaining': 0, ...} 25.0 0.8
```

`run_experiment()` and `product_tests.create()` check this before uploading anything (pass `check_balance=False` to
skip). If the balance does not cover the test, they raise `InsufficientFundsError` with `.required` and `.balance` in
US dollars; the server checks the exact cost again at start and answers HTTP 402 `insufficient_funds`.

## The Assistant over the API

Describe a test in plain language; the Assistant asks for anything missing, drafts the plan and tells you what to
upload. Nothing runs until you start it. See [examples/assistant.py](./examples/assistant.py).

```python
conv = client.agent.start_conversation()
reply = client.agent.send(conv, "Compare my original shoe cabinet page with a benefit-led version on TikTok Shop US. "
                                "25 personas, the price is $37.69 with free shipping.")
print(reply.text)
draft = reply.draft()                  # None until the Assistant has everything it needs; answer it with send()
if draft:
    print(draft.workflow, draft.arms, draft.plan)        # e.g. product_test ['A', 'B'] {...}
    client.agent.upload(conv, draft, {"A": "original.png", "B": "benefit.png"})
    client.agent.start(draft)          # paid like any test (free tests, then balance)
```

For a UI A/B test the draft's images are `{"control": ..., "treatment": ...}`. When the Assistant asks which kind of
test you mean, answer with `client.agent.send(conv, "", workflow="product_test")` (or `"ui_ab_test"`). Follow a
started test with `client.product_tests.wait(id)` or `client.wait_experiment(id)`, or ask the Assistant to explain the
results.

## Errors

All errors are `facetlab.FacetLabError` subclasses with `.code`, `.message` and `.details`:

| Exception | When |
|---|---|
| `InsufficientFundsError` | The balance does not cover the test (`insufficient_funds`, HTTP 402) |
| `LimitError` | `free_tier_limit`, `plan_limit` (tests per period) or `quota_exceeded` |
| `AuthenticationError` | Missing, invalid or revoked API key (HTTP 401) |
| `FacetLabError` | Anything else, e.g. `invalid_image` (also images over 5 MB), `image_too_large` (UI A/B screenshots over about 3 MB together), `payload_too_large`, `tier_limit`, `audience_too_small`, `images_missing` |

AI mockup generation (`generate_mockups()`) still runs in the web app only.

## Support

- Documentation: [qyzkdesign.com/docs](https://qyzkdesign.com/docs)
- Email: qyzkai@gmail.com
- Issues: [GitHub Issues](https://github.com/qyzk/facetlab-sdk-public/issues)

## License

MIT License - see [LICENSE](./LICENSE) for details.
