"""
Run: .venv/bin/python smoke_test.py
Confirms auth works and prints first site from GET /Sites.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from app.alsoenergy import client


async def main():
    print("Authenticating...")
    await client.authenticate()
    print(f"Token status: {client.token_status}")

    print("\nFetching /Sites...")
    sites = await client.get_sites()

    count = len(sites) if isinstance(sites, list) else "?"
    print(f"Got {count} site(s)")

    if isinstance(sites, list) and sites:
        print("\nFirst site:")
        print(json.dumps(sites[0], indent=2))
    else:
        print("Response:", json.dumps(sites, indent=2)[:2000])

    await client.close()


asyncio.run(main())
