"""Fixed, keyless OpenAlex Works adapter. Never writes canonical state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
import re
import time
from urllib.parse import urlencode

import httpx

from ..contracts import SearchResultInspectionV1, canonical_json_bytes

ORIGIN = "https://api.openalex.org"
MAX_RESULTS_PER_LANE = 10
MAX_BODY_BYTES = 1024 * 1024
FIELDS = "id,doi,display_name,publication_date,authorships,abstract_inverted_index"
MAX_ABSTRACT_WORDS = 16384


class OpenAlexError(ValueError):
    """An explicitly classified provider failure, never an automatic retry."""

    def __init__(self, reason: str, *, bytes_received: int = 0):
        super().__init__(reason)
        self.bytes_received = bytes_received


@dataclass(frozen=True)
class Work:
    openalex_id: str
    doi: str | None
    title: str
    authors: tuple[str, ...]
    publication_date: str | None
    inspection: SearchResultInspectionV1
    raw: bytes
    abstract: bytes | None
    abstract_error: bool = False


def request_url(query: str, limit: int) -> str:
    if type(query) is not str or not query.strip() or type(limit) is not int or not 1 <= limit <= MAX_RESULTS_PER_LANE:
        raise OpenAlexError("invalid bounded OpenAlex request")
    url = ORIGIN + "/works?" + urlencode((("search", query), ("per_page", limit), ("select", FIELDS)))
    if len(url.encode("ascii")) > 4000:
        raise OpenAlexError("frozen query exceeds pilot request URL bound")
    return url


def fetch(
    query: str, limit: int, *, byte_limit: int, elapsed_limit: int, transport: httpx.BaseTransport | None = None
) -> bytes:
    """One GET, no redirects/retries/cookies/proxy or certificate env inheritance.

    The transport injection is for trusted offline tests, never an operator option.
    A fresh client is used for each request, so received cookies are never replayed.
    """
    url = request_url(query, limit)
    bound = min(MAX_BODY_BYTES, byte_limit)
    if bound < 1 or elapsed_limit < 1:
        raise OpenAlexError("invalid transport budget")
    timeout = httpx.Timeout(
        connect=min(5, elapsed_limit),
        read=min(10, elapsed_limit),
        write=min(5, elapsed_limit),
        pool=min(5, elapsed_limit),
    )
    deadline = time.monotonic() + elapsed_limit
    received = 0
    body = bytearray()
    try:
        with httpx.Client(
            transport=transport,
            trust_env=False,
            verify=True,
            follow_redirects=False,
            timeout=timeout,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        ) as client:
            client.headers.clear()
            with client.stream(
                "GET", url, headers={"Accept": "application/json", "Accept-Encoding": "identity"}
            ) as response:
                if response.status_code != 200:
                    raise OpenAlexError(f"OpenAlex HTTP {response.status_code}")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise OpenAlexError("compressed OpenAlex response is unsupported")
                if response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                    raise OpenAlexError("OpenAlex response is not JSON")
                # No chunk_size: account for each delivered fragment before HTTPX can coalesce it.
                for chunk in response.iter_raw():
                    received += len(chunk)
                    if time.monotonic() > deadline:
                        raise OpenAlexError("OpenAlex elapsed budget exceeded", bytes_received=received)
                    if received > bound:
                        raise OpenAlexError("OpenAlex response exceeds byte bound", bytes_received=received)
                    body.extend(chunk)
    except (httpx.HTTPError, httpx.StreamError) as exc:
        # Do not persist URLs, response text, environment values, or exception details.
        raise OpenAlexError("OpenAlex transport failed; no retry", bytes_received=received) from exc
    return bytes(body)


def _text(value: object, label: str, maximum: int = 2048) -> str:
    if type(value) is not str or not value.strip():
        raise OpenAlexError(f"invalid OpenAlex {label}")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise OpenAlexError(f"invalid Unicode in OpenAlex {label}") from exc
    if size > maximum:
        raise OpenAlexError(f"oversized OpenAlex {label}")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise OpenAlexError(f"invalid control character in OpenAlex {label}")
    return value


def reconstruct_abstract(index: object) -> bytes | None:
    if index is None:
        return None
    if type(index) is not dict or not index or len(index) > MAX_ABSTRACT_WORDS:
        raise OpenAlexError("malformed abstract index")
    words: dict[int, str] = {}
    for word, positions in index.items():
        _text(word, "abstract token", 512)
        if type(positions) is not list or not positions or len(positions) > MAX_ABSTRACT_WORDS:
            raise OpenAlexError("malformed abstract positions")
        for position in positions:
            if type(position) is not int or not 0 <= position < MAX_ABSTRACT_WORDS or position in words:
                raise OpenAlexError("duplicate or invalid abstract position")
            words[position] = word
    if set(words) != set(range(len(words))):
        raise OpenAlexError("abstract positions contain gaps")
    text = " ".join(words[i] for i in range(len(words))).encode("utf-8")
    if len(text) > 131072:
        raise OpenAlexError("abstract exceeds text bound")
    return text


def _reject_constant(value: str) -> None:
    raise OpenAlexError("non-finite JSON")


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise OpenAlexError("non-finite JSON")
    return value


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise OpenAlexError("duplicate JSON key")
        result[key] = value
    return result


def normalize(body: bytes, limit: int) -> tuple[Work, ...]:
    if len(body) > MAX_BODY_BYTES or not 1 <= limit <= MAX_RESULTS_PER_LANE:
        raise OpenAlexError("OpenAlex normalization bound exceeded")
    try:
        root = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise OpenAlexError("malformed OpenAlex JSON") from exc
    if type(root) is not dict or type(root.get("results")) is not list or len(root["results"]) > limit:
        raise OpenAlexError("invalid or oversized OpenAlex results")
    works = []
    seen: set[str] = set()
    for rank, item in enumerate(root["results"], 1):
        if type(item) is not dict:
            raise OpenAlexError("malformed OpenAlex result")
        identifier = _text(item.get("id"), "work ID", 80)
        if not re.fullmatch(r"https://openalex\.org/W[1-9][0-9]{0,19}", identifier):
            raise OpenAlexError("invalid OpenAlex work ID")
        doi = item.get("doi")
        if doi is not None:
            doi = _text(doi, "DOI", 512).lower()
            if not re.fullmatch(r"https://doi\.org/10\.[0-9]{4,9}/[^\s?#]+", doi):
                raise OpenAlexError("invalid OpenAlex DOI")
            doi = doi.removeprefix("https://doi.org/")
        locator = f"https://doi.org/{doi}" if doi else identifier
        if identifier in seen or locator in seen:
            # Dropping/renumbering duplicates would change the returned ranking.
            raise OpenAlexError("duplicate OpenAlex result")
        seen.update((identifier, locator))
        title = _text(item.get("display_name"), "title")
        authorships = item.get("authorships")
        if type(authorships) is not list or len(authorships) > 100:
            raise OpenAlexError("invalid OpenAlex authorships")
        authors = []
        for authorship in authorships:
            if type(authorship) is not dict or type(authorship.get("author")) is not dict:
                raise OpenAlexError("invalid OpenAlex author")
            authors.append(_text(authorship["author"].get("display_name"), "author name", 512))
        published = item.get("publication_date")
        if published is not None:
            published = _text(published, "publication date", 10)
            try:
                if date.fromisoformat(published).isoformat() != published:
                    raise ValueError("noncanonical date")
            except ValueError as exc:
                raise OpenAlexError("invalid OpenAlex publication date") from exc
        bad_abstract = False
        try:
            abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
        except OpenAlexError:
            abstract, bad_abstract = None, True
        work_hash = hashlib.sha256(f"work|{locator}".encode()).hexdigest()
        identity = hashlib.sha256(
            canonical_json_bytes({"canonical_locator": locator, "work_identity_sha256": work_hash}, trailing_lf=False)
        ).hexdigest()
        inspection = SearchResultInspectionV1(
            canonical_locator=locator,
            locator_sha256=hashlib.sha256(locator.encode()).hexdigest(),
            work_identity_sha256=work_hash,
            result_identity_sha256=identity,
            provider_rank=1,
            result_rank=rank,
        )
        # Retain only requested, validated metadata and the supplied index, never extra remote fields.
        raw = canonical_json_bytes(
            dict(
                id=identifier,
                doi=f"https://doi.org/{doi}" if doi else None,
                display_name=title,
                publication_date=published,
                authorships=[{"author": {"display_name": name}} for name in authors],
                abstract_inverted_index=item.get("abstract_inverted_index") if not bad_abstract else None,
            )
        )
        works.append(Work(identifier, doi, title, tuple(authors), published, inspection, raw, abstract, bad_abstract))
    return tuple(works)
