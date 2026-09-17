"""Bound the browser to declared public pages and read-only requests."""
from urllib.parse import urlsplit


def allow_request(method, url, top_navigation, config):
    if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        return False
    if not top_navigation:
        return True
    p, base = urlsplit(url), urlsplit(config["base_url"])
    return (method.upper() in {"GET", "HEAD"}
            and p.scheme == base.scheme and p.netloc == base.netloc
            and p.path in {page["path"] for page in config["pages"]}
            and not p.query)
