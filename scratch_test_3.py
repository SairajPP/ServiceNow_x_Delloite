import asyncio
import os
import httpx
from app.config import settings

async def main():
    async with httpx.AsyncClient(auth=(settings.servicenow_user, settings.servicenow_password)) as client:
        resp = await client.get(
            f"{settings.sn_table_url}/x_snc_ecosentine_0_legal_case",
            params={"sysparm_limit": 1, "sysparm_query": "ORDERBYDESCsys_created_on"}
        )
        data = resp.json().get("result", [])
        if data:
            print(list(data[0].keys()))

if __name__ == "__main__":
    asyncio.run(main())
