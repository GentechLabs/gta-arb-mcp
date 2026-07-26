"""
GTA Arb MCP Server
Exposes cross-venue arbitrage scanner as an MCP tool.

Usage:
  python server.py  # Runs on stdio transport (default for MCP)
  
Test:
  echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"scan_arb","arguments":{"assets":"BTC,ETH"}}}' | python server.py
"""
import json, sys, os, urllib.request, time, re
from typing import Any

# ── CONFIG ──────────────────────────────────────────────────────────────────
HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"
COINBASE_SPOT = "https://api.coinbase.com/v2/prices"
ASSET_MAP = {
    "BTC":  {"hl": "BTC", "cb": "BTC-USD"},
    "ETH":  {"hl": "ETH", "cb": "ETH-USD"},
    "SOL":  {"hl": "SOL", "cb": "SOL-USD"},
    "AVAX": {"hl": "AVAX", "cb": "AVAX-USD"},
    "LINK": {"hl": "LINK", "cb": "LINK-USD"},
    "ONDO": {"hl": "ONDO", "cb": "ONDO-USD"},
    "PAXG": {"hl": "PAXG", "cb": "PAXG-USD"},
}

# ── HELPERS ─────────────────────────────────────────────────────────────────
def hl_post(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(HYPERLIQUID_INFO, data=data,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def cb_price(product_id: str) -> float | None:
    try:
        url = f"{COINBASE_SPOT}/{product_id}/spot"
        req = urllib.request.Request(url, headers={"User-Agent": "GTA/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            return float(d.get("data", {}).get("amount", 0))
    except: return None

def calc_bps(perp: float, spot: float) -> float:
    if spot == 0: return 0
    return round((perp - spot) / spot * 10000, 1)

def scan_arb(assets: list[str] | None = None) -> list[dict]:
    """Scan for arb opportunities across specified assets (default: all 7)."""
    if assets is None:
        assets = list(ASSET_MAP.keys())
    
    # Get Hyperliquid perp prices
    mids = hl_post({"type": "allMids"})
    results = []
    
    for symbol in assets:
        cfg = ASSET_MAP.get(symbol)
        if not cfg: continue
        
        hl_mid = float(mids.get(cfg["hl"], 0))
        if hl_mid == 0: continue
        
        cb_mid = cb_price(cfg["cb"])
        if cb_mid is None: continue
        
        bps = calc_bps(hl_mid, cb_mid)
        
        results.append({
            "asset": symbol,
            "perp_price": hl_mid,
            "spot_price": cb_mid,
            "spread_bps": bps,
            "direction": "CONTANGO" if bps > 0 else "BACKWARDATION",
            "trade": f"{'Short perp + Long spot' if bps > 0 else 'Long perp + Short spot'}"
        })
    
    return sorted(results, key=lambda x: abs(x["spread_bps"]), reverse=True)

# ── MCP PROTOCOL ────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "scan_arb",
        "description": "Scan for cross-venue arbitrage opportunities between Hyperliquid perp and Coinbase spot. Returns spread in basis points for each asset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assets": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(ASSET_MAP.keys())},
                    "description": "Assets to scan (default: all 7 tracked assets)"
                },
                "min_spread_bps": {
                    "type": "number",
                    "description": "Minimum spread in basis points to filter results (default: 0)"
                }
            }
        }
    }
]

def handle_request(msg: dict) -> dict | None:
    req_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})
    
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    
    elif method == "tools/call":
        tool = params.get("name")
        args = params.get("arguments", {})
        
        if tool == "scan_arb":
            results = scan_arb(args.get("assets"))
            min_bps = args.get("min_spread_bps", 0)
            if min_bps:
                results = [r for r in results if abs(r["spread_bps"]) >= min_bps]
            
            if not results:
                text = "No arb opportunities above minimum spread."
            else:
                lines = ["## GTA Arb Scan Results\n"]
                for r in results:
                    lines.append(f"**{r['asset']}** — {r['direction']} **{r['spread_bps']:+.1f} bps**")
                    lines.append(f"  Perp: ${r['perp_price']:.2f} | Spot: ${r['spot_price']:.2f}")
                    lines.append(f"  Trade: {r['trade']}")
                    lines.append("")
                text = "\n".join(lines)
            
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": text}]
            }}
        
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool '{tool}' not found"}}
    
    elif method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}
    
    return None

# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    if sys.stdin.isatty():
        # Interactive test mode
        print("GTA Arb MCP Server — stdio transport")
        print("Tools: scan_arb")
        results = scan_arb()
        for r in results:
            print(f"  {r['asset']}: {r['spread_bps']:+.1f} bps ({r['direction']})")
        return
    
    # MCP stdio transport
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            msg = json.loads(line)
            resp = handle_request(msg)
            if resp:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32000, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
