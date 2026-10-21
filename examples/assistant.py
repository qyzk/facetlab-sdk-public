"""
Use the FacetLab Assistant from code: describe the test, upload what it asks for, start it, wait for the result.
Get an API key at https://qyzkdesign.com/dashboard/api-keys
"""

from facetlab import FacetLabClient, InsufficientFundsError

client = FacetLabClient(api_key="fl_your_api_key_here")
print("Account:", client.account())

conv = client.agent.start_conversation()
reply = client.agent.send(conv, "Pre-test my sign-up page: control vs a version with a bigger free-trial banner, "
                                "US visitors, 10 personas. The goal is more free-trial starts.")
print(reply.text)

draft = reply.draft()
while draft is None:
    answer = input("Your answer to the Assistant (empty to stop): ").strip()
    if not answer:
        raise SystemExit
    reply = client.agent.send(conv, answer)
    print(reply.text)
    draft = reply.draft()

images = {"control": "screenshots/control.png", "treatment": "screenshots/treatment.png"} \
    if draft.workflow == "ui_ab_test" else {arm: f"screenshots/{arm}.png" for arm in draft.arms}
client.agent.upload(conv, draft, images)
try:
    started = client.agent.start(draft)
except InsufficientFundsError as e:
    raise SystemExit(f"Top up first: the test needs ${e.required} and your balance is ${e.balance}.")
print("Started:", started)

if draft.workflow == "ui_ab_test":
    print(client.wait_experiment(draft.draft_id))
else:
    print(client.product_tests.wait(draft.draft_id)["results"]["narrative"]["en"]["headline"])
