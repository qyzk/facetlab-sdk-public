"""
Basic A/B Test Experiment Example

This example shows how to run a simple A/B test simulation
with the FacetLab SDK.
"""

from facetlab import FacetLabClient

# Initialize client with your API key
# Get your API key at: https://qyzkdesign.com/dashboard/api-keys
client = FacetLabClient(api_key="fl_your_api_key_here")

# Run A/B test simulation
result = client.run_experiment(
    control_image="screenshots/control.png",      # Path to control image
    treatment_image="screenshots/treatment.png",  # Path to treatment image
    context="E-commerce checkout page redesign - testing new CTA button",
    locale="usa",        # "usa", "europe", or "asia"
    persona_count=100,   # 50-5000 based on your tier
    scenario="ui_change" # ui_change, price, promo, content, ranking, cart
)

# Print results
print(f"🏆 Winner: {result.winner}")
print(f"📊 Confidence: {result.confidence:.1%}")
print(f"📈 Lift: {result.lift}")
print()

# Demographic segmentation
print("📊 Segmentation Insights:")
for segment, data in result.segmentation.items():
    print(f"  - {segment}: {data}")
print()

# Recommendations
print("💡 Recommendations:")
for i, rec in enumerate(result.recommendations, 1):
    print(f"  {i}. {rec}")
