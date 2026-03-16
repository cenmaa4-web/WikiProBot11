from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx


@dataclass
class WikiClient:
    lang: str
    timeout: float = 12.0

    @property
    def api_url(self) -> str:
        return f"https://{self.lang}.wikipedia.org/w/api.php"

    @property
    def rest_url(self) -> str:
        return f"https://{self.lang}.wikipedia.org/api/rest_v1"

    async def _api(self, client: httpx.AsyncClient, **params) -> dict:
        base = {"format": "json", "formatversion": "2", "utf8": "1"}
        base.update(params)
        r = await client.get(self.api_url, params=base)
        r.raise_for_status()
        return r.json()

    async def search(self, query: str, limit: int = 6) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await self._api(
                client,
                action="query",
                list="search",
                srsearch=query,
                srlimit=str(limit),
            )
        return (data.get("query") or {}).get("search") or []

    async def quick_info(self, pageid: int) -> dict | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await self._api(
                client,
                action="query",
                prop="info|pageprops",
                inprop="url",
                pageids=str(pageid),
            )
        pages = (data.get("query") or {}).get("pages") or []
        if not pages:
            return None
        p = pages[0]
        return {
            "pageid": p.get("pageid"),
            "title": p.get("title") or "",
            "fullurl": p.get("fullurl") or f"https://{self.lang}.wikipedia.org/?curid={pageid}",
            "length": p.get("length") or 0,
            "lastrevid": p.get("lastrevid") or 0,
        }

    async def summary(self, title: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.rest_url}/page/summary/{quote(title)}"
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

    async def extract_plain(self, pageid: int, chars: int = 2500) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await self._api(
                client,
                action="query",
                prop="extracts",
                pageids=str(pageid),
                explaintext="1",
                exchars=str(chars),
            )
        pages = (data.get("query") or {}).get("pages") or []
        if not pages:
            return ""
        return pages[0].get("extract") or ""

    async def random_summary(self) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.rest_url}/page/random/summary")
            r.raise_for_status()
            return r.json()
