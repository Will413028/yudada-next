"""Explicit synthetic administrator for disposable browser-test databases."""

import asyncio
import sys

from app.accounts import Registration
from scripts.create_admin import create

if __name__ == "__main__":
    asyncio.run(
        create(
            Registration(
                account=sys.argv[1],
                password="browser_admin_fixture_password_123",
                display_name="瀏覽器管理者",
            )
        )
    )
