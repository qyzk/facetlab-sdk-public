"""
The FacetLab Assistant over the API: describe a test in plain language, the Assistant sets it up as a draft, you upload
the screenshots and start it. Tests are paid like any other (free tests first, then your prepaid balance).

    conv = client.agent.start_conversation()
    reply = client.agent.send(conv, "Compare my original and benefit-led shoe cabinet pages on TikTok Shop US")
    print(reply.text)
    draft = reply.draft()            # the plan the Assistant drafted, once it has everything it needs
    if draft:
        client.agent.upload(conv, draft, {"A": "original.png", "B": "benefit.png"})
        started = client.agent.start(draft)
"""

import json
import mimetypes
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from ._http import check
from .exceptions import FacetLabError

TIMEOUT = 30
TURN_TIMEOUT = 180   # one Assistant turn can call several tools
UPLOAD_TIMEOUT = 120
WORKFLOWS = ("product_test", "ui_ab_test")


@dataclass
class Draft:
    """A test the Assistant prepared: upload its images, then start it."""
    workflow: str          # "product_test" or "ui_ab_test"
    draft_id: str          # product test id ("pt_...") or UI A/B experiment id ("exp-...")
    arms: List[str]        # image keys to upload: arm ids ("A", "B", ...) or "control" and "treatment"
    plan: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentReply:
    """One Assistant turn: its text, the cards it produced (plans, results, ...) and the workflow it chose."""
    text: str
    cards: List[Dict[str, Any]]
    workflow: Optional[str] = None
    error: Optional[Dict[str, Any]] = None

    def draft(self) -> Optional[Draft]:
        """The draft from an upload request card in this reply, with its plan card when present."""
        upload = next((c for c in self.cards if c.get("kind") == "upload_request"), None)
        if not upload:
            return None
        plan = next((c for c in self.cards if c.get("kind") in ("plan", "ui_plan")
                     and c.get("draft_id") == upload["draft_id"]), {})
        return Draft(workflow=upload["workflow"], draft_id=upload["draft_id"],
                     arms=[a["id"] for a in upload.get("arms", [])], plan=plan)


class AgentClient:
    def __init__(self, session: requests.Session, site: str, put=None):
        self._s, self._site = session, site.rstrip("/")
        self._put = put or requests.put   # presigned S3 PUTs must not carry the API key

    def _conv(self, conversation_id: str) -> str:
        return f"{self._site}/api/agent/conversations/{quote(conversation_id, safe='')}"

    def start_conversation(self) -> str:
        """A new conversation; returns its id."""
        return check(self._s.post(f"{self._site}/api/agent/conversations", timeout=TIMEOUT))["id"]

    def list_conversations(self) -> List[Dict[str, Any]]:
        return check(self._s.get(f"{self._site}/api/agent/conversations", timeout=TIMEOUT)).get("conversations", [])

    def send(self, conversation_id: str, text: str, workflow: Optional[str] = None) -> AgentReply:
        """Sends a message and waits for the whole reply (the server streams it; this collects it).

        `workflow` ("product_test" or "ui_ab_test") answers the Assistant when it asks which kind of test you mean.
        """
        if workflow is not None and workflow not in WORKFLOWS:
            raise ValueError(f"workflow must be one of {WORKFLOWS}")
        body: Dict[str, Any] = {"text": text}
        if workflow:
            body["workflow"] = workflow
        r = self._s.post(f"{self._conv(conversation_id)}/messages", json=body, stream=True, timeout=TURN_TIMEOUT,
                         headers={"Accept": "text/event-stream"})
        if not r.ok:
            check(r)
        texts, cards, chosen, error = [], [], workflow, None
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue   # heartbeats and blank separators
            event = json.loads(raw[5:].strip())
            kind = event.get("type")
            if kind == "text":
                texts.append(event.get("delta", ""))
            elif kind == "card":
                cards.append(event["card"])
            elif kind == "workflow":
                chosen = event.get("workflow")
            elif kind == "error":
                error = event
            elif kind == "done":
                break
        reply = AgentReply(text="".join(texts), cards=cards, workflow=chosen, error=error)
        if error and not reply.text:
            raise FacetLabError(error.get("message") or "The assistant failed", code=error.get("code") or "agent_error",
                                details=error)
        return reply

    def upload(self, conversation_id: str, draft: Draft, images: Dict[str, str]) -> None:
        """Uploads one image per arm of the draft ({"A": "a.png", "B": "b.png"} or {"control": ..., "treatment": ...})."""
        missing = [a for a in draft.arms if a not in images]
        if missing:
            raise FacetLabError(f"Images missing for: {', '.join(missing)}", code="invalid_image")
        types = {}
        for key in draft.arms:
            ctype = mimetypes.guess_type(images[key])[0] or "image/png"
            types[key] = "image/jpeg" if ctype == "image/jpg" else ctype
        urls = check(self._s.post(f"{self._conv(conversation_id)}/uploads", timeout=TIMEOUT,
                                  json={"draft_id": draft.draft_id, "workflow": draft.workflow, "content_types": types}))
        for key, target in urls["upload_urls"].items():
            with open(images[key], "rb") as f:
                put = self._put(target["url"], data=f.read(), headers={"Content-Type": target["content_type"]},
                                timeout=UPLOAD_TIMEOUT)
            if not put.ok:
                raise FacetLabError(f"Upload failed for {key}", code="upload_failed",
                                    details={"status": getattr(put, "status_code", None)})

    def start(self, draft: Draft) -> Dict[str, Any]:
        """Starts an uploaded draft. Paid like any test: InsufficientFundsError (402) when the balance is too low."""
        if draft.workflow == "product_test":
            return check(self._s.post(f"{self._site}/api/v1/product-tests/{draft.draft_id}/start", timeout=TIMEOUT))
        return check(self._s.post(f"{self._site}/api/sdk/experiments/{draft.draft_id}/start", timeout=TIMEOUT))
