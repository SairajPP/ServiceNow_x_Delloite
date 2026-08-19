import asyncio
import os
import httpx
from app.config import settings

async def main():
    async with httpx.AsyncClient(auth=(settings.servicenow_user, settings.servicenow_password)) as client:
        resp = await client.get(
            f"{settings.sn_table_url}/x_snc_ecosentine_0_complaint",
            params={"sysparm_limit": 1, "sysparm_query": "ORDERBYDESCsys_created_on"}
        )
        data = resp.json().get("result", [])
        if data:
            c = data[0]
            print(f"[{c.get('number')}] Severity: {c.get('ai_severity')}")
            print(f"Confidence: {c.get('ai_confidence')}")
            print(f"Rationale: {c.get('ai_rationale')}")

if __name__ == "__main__":
    asyncio.run(main())
