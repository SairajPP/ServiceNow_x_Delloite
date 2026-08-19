import asyncio
import os
import httpx
from app.config import settings

async def main():
    async with httpx.AsyncClient(auth=(settings.servicenow_user, settings.servicenow_password)) as client:
        resp = await client.get(
            f"{settings.sn_table_url}/x_snc_ecosentine_0_complaint",
            params={"sysparm_limit": 5, "sysparm_query": "ORDERBYDESCsys_created_on"}
        )
        data = resp.json().get("result", [])
        for c in data:
            print(f"[{c.get('number')}] Severity: {c.get('ai_severity')} Confidence: {c.get('ai_confidence')}")

if __name__ == "__main__":
    asyncio.run(main())
