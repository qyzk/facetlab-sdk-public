import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from facetlab import FacetLabClient
from facetlab._http import check
from facetlab.agent import AgentClient
from facetlab.exceptions import AuthenticationError, FacetLabError, InsufficientFundsError, LimitError


def resp(status, body):
    r = MagicMock()
    r.status_code, r.ok = status, 200 <= status < 300
    r.json.return_value = body
    return r


def test_check_maps_server_errors_to_typed_exceptions():
    assert check(resp(200, {"a": 1})) == {"a": 1}
    with pytest.raises(InsufficientFundsError) as e:
        check(resp(402, {"error": {"code": "insufficient_funds", "message": "Insufficient funds",
                                   "details": {"required": 49.75, "balance": 25}}}))
    assert (e.value.required, e.value.balance) == (49.75, 25)
    with pytest.raises(LimitError) as e:
        check(resp(403, {"error": "Free tier limit reached", "code": "free_tier_limit"}))
    assert e.value.code == "free_tier_limit"
    with pytest.raises(AuthenticationError):
        check(resp(401, {"error": "Invalid or missing API key", "code": "unauthorized"}))
    with pytest.raises(FacetLabError) as e:
        check(resp(500, {"error": {"code": "internal_error", "message": "Unexpected error"}}))
    assert e.value.code == "internal_error"


def account(balance, remaining=0, rate=1.99):
    return {"plan": "pay_as_you_go", "free_tests": {"used": 2, "limit": 2, "remaining": remaining}, "balance": balance,
            "next_test_rate": rate}


def test_check_funds_before_uploading():
    client = FacetLabClient(api_key="fl_test")
    client.session = MagicMock()
    client.session.get.return_value = resp(200, account(25))
    with pytest.raises(InsufficientFundsError) as e:
        client.check_funds(25)            # 25 x $1.99 = $49.75 > $25
    assert e.value.required == 49.75
    client.session.get.return_value = resp(200, account(50))
    assert client.check_funds(25)["balance"] == 50
    client.session.get.return_value = resp(200, account(0, remaining=1))
    client.check_funds(25)                # a free test covers it


def sse(*events):
    return [f"data: {json.dumps(e)}" for e in events]


def test_agent_send_collects_the_streamed_reply_and_its_draft():
    s = MagicMock()
    stream = resp(200, None)
    stream.iter_lines.return_value = ["", *sse(
        {"type": "workflow", "workflow": "product_test", "confidence": 0.9},
        {"type": "text", "delta": "I drafted "}, {"type": "text", "delta": "a plan."},
        {"type": "card", "card": {"kind": "upload_request", "workflow": "product_test", "draft_id": "pt_1",
                                  "arms": [{"id": "A", "label": "Original"}, {"id": "B", "label": "New"}]}},
        {"type": "card", "card": {"kind": "plan", "draft_id": "pt_1", "name": "Shoe cabinet"}},
        {"type": "done", "usage": {"input_tokens": 1, "output_tokens": 1}})]
    s.post.return_value = stream
    agent = AgentClient(s, "https://qyzkdesign.com")
    reply = agent.send("conv#abc", "Compare my pages")
    assert s.post.call_args[0][0] == "https://qyzkdesign.com/api/agent/conversations/conv%23abc/messages"
    assert reply.text == "I drafted a plan." and reply.workflow == "product_test"
    draft = reply.draft()
    assert (draft.workflow, draft.draft_id, draft.arms, draft.plan["name"]) == ("product_test", "pt_1", ["A", "B"], "Shoe cabinet")


def test_agent_uploads_then_starts_each_kind_of_draft(tmp_path):
    from facetlab.agent import Draft
    s, put = MagicMock(), MagicMock(return_value=resp(200, None))
    a, b = tmp_path / "a.png", tmp_path / "b.jpg"
    a.write_bytes(b"png"); b.write_bytes(b"jpg")
    s.post.side_effect = [resp(200, {"upload_urls": {"A": {"url": "https://s3/a", "content_type": "image/png"},
                                                     "B": {"url": "https://s3/b", "content_type": "image/jpeg"}}}),
                          resp(200, {"id": "pt_1", "status": "queued"}),
                          resp(200, {"job_id": "exp-1", "status": "queued"})]
    agent = AgentClient(s, "https://qyzkdesign.com", put=put)
    draft = Draft("product_test", "pt_1", ["A", "B"])
    agent.upload("conv#abc", draft, {"A": str(a), "B": str(b)})
    assert s.post.call_args_list[0][1]["json"] == {"draft_id": "pt_1", "workflow": "product_test",
                                                   "content_types": {"A": "image/png", "B": "image/jpeg"}}
    assert put.call_count == 2
    assert agent.start(draft)["status"] == "queued"
    assert s.post.call_args_list[1][0][0] == "https://qyzkdesign.com/api/v1/product-tests/pt_1/start"
    agent.start(Draft("ui_ab_test", "exp-1", ["control", "treatment"]))
    assert s.post.call_args_list[2][0][0] == "https://qyzkdesign.com/api/sdk/experiments/exp-1/start"
    with pytest.raises(FacetLabError):
        agent.upload("conv#abc", draft, {"A": str(a)})
