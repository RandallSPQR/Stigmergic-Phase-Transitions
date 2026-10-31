"""OpenRouter chat-completions client with an append-only on-disk cache.

Every request body (plus an explicit replicate index for repeated sampling) is
hashed; the compact response is appended to results/llm/cache/<model>.jsonl (git-ignored). Its gzip
snapshot <model>.jsonl.gz (made by llm/snapshot_cache.py) lives in the private HF dataset named in
results/llm/cache_manifest.json, not in git; on first use it is downloaded (needs HF_TOKEN) and restored.
Reruns with the same body are free. The API key is read from OPENROUTER_API_KEY
if set (otherwise the session proxy injects auth); it is never printed or stored.
"""
import hashlib, json, os, random, threading, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "results", "llm", "cache")
URL = "https://openrouter.ai/api/v1/chat/completions"

_locks = {}
_index = {}          # model -> {hash: record}
_glock = threading.Lock()
_spend = {"usd": 0.0, "calls": 0}
# CLIENT_SLIM=1: keep only key/rep/t/resp in memory (the on-disk cache keeps the request bodies). For long runs whose
# callers only read rec["resp"] (llm/stage3_replicate.py); cuts the in-memory index by more than half.
SLIM = os.environ.get("CLIENT_SLIM") == "1"


class BudgetExceeded(RuntimeError):
    pass


class CacheMiss(RuntimeError):
    pass


# SPT_OFFLINE=1 (set by `make replicate`): never call the API; a request missing from the cache raises CacheMiss.
OFFLINE = os.environ.get("SPT_OFFLINE") == "1"


def _slug(model):
    return model.replace("/", "__").replace(":", "_")


def _path(model):
    return os.path.join(CACHE_DIR, _slug(model) + ".jsonl")


def _load(model):
    with _glock:
        if model in _index:
            return _index[model], _locks[model]
        idx, p = {}, _path(model)
        if not os.path.exists(p) and not os.path.exists(p + ".gz"):   # fresh clone: snapshot lives on HF, not in git
            import fetch_cache
            name = os.path.basename(p) + ".gz"
            if any(f["file"] == name for f in fetch_cache.manifest()["files"]):
                try:
                    bad = fetch_cache.fetch(CACHE_DIR, only={name}, verbose=False)
                except Exception as e:
                    bad = repr(e)
                if bad:   # never fall through to live (paid, non-reproducible) calls for a model we already cached
                    raise RuntimeError(f"cache snapshot {name} could not be fetched/verified ({bad}); "
                                       "set HF_TOKEN and run python llm/fetch_cache.py")
        if not os.path.exists(p) and os.path.exists(p + ".gz"):   # restore the raw cache from its snapshot
            import gzip, shutil
            with gzip.open(p + ".gz", "rb") as fi, open(p, "wb") as fo:
                shutil.copyfileobj(fi, fo)
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        r = json.loads(line)
                        if SLIM:
                            r.pop("body", None)
                        idx[r["key"]] = r
        _index[model], _locks[model] = idx, threading.Lock()
        return idx, _locks[model]


def request_key(body, rep=0):
    canon = json.dumps({"body": body, "rep": rep}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def _headers():
    h = {"Content-Type": "application/json", "X-Title": "social-phase-transitions"}
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        h["Authorization"] = "Bearer " + k
    return h


def _compact(resp):
    """Keep only what analysis needs: text, first-token top logprobs, provider, usage."""
    ch = (resp.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    lp = ch.get("logprobs") or {}
    content_lp = lp.get("content") or []
    first = None
    if content_lp:
        t0 = content_lp[0]
        first = {"token": t0.get("token"), "logprob": t0.get("logprob"),
                 "top": [[t.get("token"), t.get("logprob")] for t in (t0.get("top_logprobs") or [])]}
    # the OpenRouter generation id is account-linked and deliberately NOT stored (owner decision 2026-10-09)
    return {"provider": resp.get("provider"), "model": resp.get("model"),
            "content": msg.get("content"), "reasoning": msg.get("reasoning"),
            "finish": ch.get("finish_reason"), "first": first, "n_lp_tokens": len(content_lp),
            "usage": resp.get("usage")}


def cached(body, rep=0):
    idx, _ = _load(body["model"])
    return idx.get(request_key(body, rep))


def chat(body, rep=0, budget_usd=None, retries=6, timeout=60):
    """Return the compact cached record for (body, rep), calling the API on a miss."""
    model = body["model"]
    idx, lock = _load(model)
    key = request_key(body, rep)
    if key in idx:
        return idx[key]
    if OFFLINE:   # replication (tier 1): a cache miss is an error, never a live call
        raise CacheMiss(f"{model} rep={rep}: request not in cache (SPT_OFFLINE=1)")
    if budget_usd is not None and _spend["usd"] >= budget_usd:
        raise BudgetExceeded(f"session spend ${_spend['usd']:.4f} >= cap ${budget_usd}")
    payload = dict(body)
    payload["usage"] = {"include": True}
    err = None
    a = n429 = 0
    while a < retries:
        try:
            r = requests.post(URL, headers=_headers(), json=payload, timeout=timeout)
            if r.status_code == 200:
                resp = r.json()
                if "error" in resp:
                    err = f"api error: {str(resp['error'])[:300]}"
                elif not resp.get("choices"):
                    err = "empty choices"
                else:
                    rec = {"key": key, "rep": rep, "body": body, "t": time.time(), "resp": _compact(resp)}
                    cost = ((resp.get("usage") or {}).get("cost")) or 0.0
                    with lock:
                        os.makedirs(CACHE_DIR, exist_ok=True)
                        with open(_path(model), "a") as f:
                            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                        idx[key] = {k: v for k, v in rec.items() if k != "body"} if SLIM else rec
                    with _glock:
                        _spend["usd"] += float(cost); _spend["calls"] += 1
                    return rec
            else:
                err = f"http {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 402, 403, 404):
                    break                       # not retryable
                if r.status_code == 429 and n429 < 60:   # shared upstream pool: short jittered retry
                    n429 += 1
                    time.sleep(0.5 + 2.5 * random.random())
                    continue
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {str(e)[:200]}"
        time.sleep(min(2 ** a, 30))
        a += 1
    raise RuntimeError(f"{model} rep={rep}: {err}")


def spend():
    return dict(_spend)
