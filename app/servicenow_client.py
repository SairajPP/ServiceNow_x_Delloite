"""
Thin async wrapper around the ServiceNow Table & Attachment APIs.
Implements integration-contract.md endpoints 2.2, 2.3, 2.7, 2.8, 2.9.

Auth: HTTP Basic against the `ecosentinel.api` web-service-only account
for PDI/demo use. Swap `_auth` for an OAuth2 client credentials flow
before going past a hackathon/demo environment (see
architecture-improvement-plan.md, P1 item).
"""
import base64
from typing import Any, Optional

import httpx

from app.config import settings
from app.logging_utils import get_logger

logger = get_logger(__name__)


class ServiceNowError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ServiceNowClient:
    def __init__(self) -> None:
        self._auth = (settings.servicenow_user, settings.servicenow_password)
        self._timeout = settings.request_timeout_seconds

    async def get_complaint(self, sys_id: str) -> dict[str, Any]:
        """Section 2.2 — GET /api/now/table/x_snc_ecosentine_0_complaint/{sys_id}"""
        url = f"{settings.sn_table_url}/x_snc_ecosentine_0_complaint/{sys_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, auth=self._auth, headers=_json_headers())
        if resp.status_code != 200:
            raise ServiceNowError(f"GET complaint failed: {resp.text}", resp.status_code)
        return resp.json()["result"]

    async def get_attachment_binary(self, complaint_sys_id: str) -> Optional[tuple[bytes, str]]:
        """
        Section 2.3 — look up attachment metadata for the complaint, then
        download the binary. Returns (bytes, content_type) or None if no
        photo was attached (handled per the "Malformed / Missing Photo"
        failure mode in integration-contract.md Section 6).
        """
        meta_url = (
            f"{settings.sn_attachment_url}"
            f"?sysparm_query=table_sys_id={complaint_sys_id}^table_name=x_snc_ecosentine_0_complaint^ORtable_name=ZZ_YYx_snc_ecosentine_0_complaint"
        )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            meta_resp = await client.get(meta_url, auth=self._auth, headers=_json_headers())
            if meta_resp.status_code != 200:
                raise ServiceNowError(f"GET attachment metadata failed: {meta_resp.text}", meta_resp.status_code)

            results = meta_resp.json().get("result", [])
            if not results:
                logger.warning("No attachment found for complaint %s", complaint_sys_id)
                return None

            attachment_sys_id = results[0]["sys_id"]
            content_type = results[0].get("content_type", "image/jpeg")

            file_url = f"{settings.sn_attachment_url}/{attachment_sys_id}/file"
            file_resp = await client.get(file_url, auth=self._auth)
            if file_resp.status_code != 200:
                raise ServiceNowError(f"GET attachment file failed: {file_resp.text}", file_resp.status_code)

            return file_resp.content, content_type

    async def patch_complaint(self, sys_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Section 2.7 — PATCH /api/now/table/x_snc_ecosentine_0_complaint/{sys_id}"""
        url = f"{settings.sn_table_url}/x_snc_ecosentine_0_complaint/{sys_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.patch(url, auth=self._auth, headers=_json_headers(), json=fields)
        if resp.status_code != 200:
            raise ServiceNowError(f"PATCH complaint failed: {resp.text}", resp.status_code)
        return resp.json()["result"]

    async def patch_inspection(self, sys_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """PATCH /api/now/table/x_snc_ecosentine_0_inspection/{sys_id}"""
        url = f"{settings.sn_table_url}/x_snc_ecosentine_0_inspection/{sys_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.patch(url, auth=self._auth, headers=_json_headers(), json=fields)
        if resp.status_code != 200:
            raise ServiceNowError(f"PATCH inspection failed: {resp.text}", resp.status_code)
        return resp.json()["result"]

    async def patch_legal_case(self, sys_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """PATCH /api/now/table/x_snc_ecosentine_0_legal_case/{sys_id}"""
        url = f"{settings.sn_table_url}/x_snc_ecosentine_0_legal_case/{sys_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.patch(url, auth=self._auth, headers=_json_headers(), json=fields)
        if resp.status_code != 200:
            raise ServiceNowError(f"PATCH legal_case failed: {resp.text}", resp.status_code)
        return resp.json()["result"]

    async def post_snapshot(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Section 2.8 — POST /api/now/table/x_snc_ecosentine_0_environment_snapshot"""
        url = f"{settings.sn_table_url}/x_snc_ecosentine_0_environment_snapshot"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, auth=self._auth, headers=_json_headers(), json=fields)
        if resp.status_code != 201:
            raise ServiceNowError(f"POST snapshot failed: {resp.text}", resp.status_code)
        return resp.json()["result"]

    async def post_agent_log(self, fields: dict[str, Any]) -> dict[str, Any]:
        """
        Section 2.9 — POST /api/now/table/x_snc_ecosentine_0_agent_decision_log.
        Deliberately a separate call (not bundled into the complaint PATCH)
        so the table can stay append-only under standard Table ACLs — see
        the "Architectural Note: Logging Strategy" in integration-contract.md.
        """
        url = f"{settings.sn_table_url}/x_snc_ecosentine_0_agent_decision_log"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, auth=self._auth, headers=_json_headers(), json=fields)
        if resp.status_code != 201:
            # Logging must never take down the pipeline — log and move on.
            logger.error("POST agent_log failed (%s): %s", resp.status_code, resp.text)
            return {}
        return resp.json()["result"]

    async def post_agent_decision(self, fields: dict[str, Any]) -> dict[str, Any]:
        """POST /api/now/table/x_snc_ecosentine_0_agent_decision_log"""
        url = f"{settings.sn_table_url}/x_snc_ecosentine_0_agent_decision_log"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, auth=self._auth, headers=_json_headers(), json=fields)
        if resp.status_code != 201:
            logger.error("POST agent decision failed (%s): %s", resp.status_code, resp.text)
            return {}
        return resp.json().get("result", {})


def _json_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "Accept": "application/json"}


def image_to_data_url(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"


sn_client = ServiceNowClient()
