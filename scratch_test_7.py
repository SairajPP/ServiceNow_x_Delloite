import asyncio
import os
import httpx
from app.config import settings

async def main():
    async with httpx.AsyncClient(auth=(settings.servicenow_user, settings.servicenow_password)) as client:
        resp = await client.get(
            f"{settings.sn_table_url}/x_snc_ecosentine_0_legal_case",
            params={"sysparm_limit": 1, "sysparm_query": "number=LEG0001016"}
        )
        data = resp.json().get("result", [])
        if data:
            c = data[0]
            print(f"[{c.get('number')}] source_complaint: {c.get('source_complaint')}")
            print(f"Case Narrative: {c.get('case_narrative')}")

if __name__ == "__main__":
    asyncio.run(main())
