# GTA Arb MCP Server

Cross-venue arbitrage scanner as an MCP tool. Scans Hyperliquid perpetuals vs Coinbase spot across 7 assets.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Run (stdio transport)
python server.py
```

## MCP Tools

### `scan_arb`

Scan for arb opportunities.

**Parameters:**
| Field | Type | Description |
|-------|------|-------------|
| `assets` | `string[]` | Optional. Filter to specific assets |
| `min_spread_bps` | `number` | Optional. Min spread to report |

**Example response:**
```
AVAX — CONTANGO +12.3 bps
  Perp: $6.67 | Spot: $6.67
  Trade: Short perp + Long spot
```

## Integration

**Hermes:**
```json
{
  "mcpServers": {
    "gta-arb": {
      "command": "python",
      "args": ["/path/to/gta-arb-mcp/server.py"]
    }
  }
}
```

**Claude Desktop / Cursor / Any MCP client:**
Same config — point to the `server.py` path.

## Tracked Assets

BTC, ETH, SOL, AVAX, LINK, ONDO, PAXG

## Architecture

```
Agent (any MCP client)
  ↓ calls scan_arb
GTA MCP Server
  ↓
Hyperliquid API (perp prices)
  + Coinbase API (spot prices)
  ↓
Returns structured arb data
```

Built by GenTech Labs — agent-powered arbitrage.
