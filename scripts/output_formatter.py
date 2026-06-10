#!/usr/bin/env python3
"""
IDX Orderbook Output Formatter
Phase 6: Markdown report generation

Generates human-readable markdown reports with:
- Orderbook summary tables
- Bid/ask imbalance visualization
- Wall detection results
- 3-tier recommendations
- Portfolio verdict (if applicable)
- Delta comparison (if applicable)
"""

import sys
import json
import argparse
from typing import Dict, List, Optional
from datetime import datetime


class OutputFormatter:
    """Format analysis results as markdown report"""
    
    def __init__(self, debug=False):
        self.debug = debug
    
    def format_orderbook_summary(self, ocr_data: Dict) -> str:
        """Format orderbook summary table"""
        lines = [
            "## Data Utama",
            "",
            "| Metric | Value |",
            "|--------|-------|"
        ]
        
        metrics = [
            ("Ticker", ocr_data.get("ticker", "N/A")),
            ("Time", ocr_data.get("timestamp", "N/A")),
            ("Prev", f"{ocr_data.get('prev', 0):,}"),
            ("Open", f"{ocr_data.get('open', 0):,}"),
            ("High", f"{ocr_data.get('high', 0):,}"),
            ("Low", f"{ocr_data.get('low', 0):,}"),
            ("ARA", f"{ocr_data.get('ara', 0):,}"),
            ("ARB", f"{ocr_data.get('arb', 0):,}"),
            ("Avg", f"{ocr_data.get('avg', 0):,}"),
            ("Val (M)", f"{ocr_data.get('val', 0):,}"),
            ("Lot", f"{ocr_data.get('lot', 0):,}"),
            ("Confidence", f"{ocr_data.get('confidence', 0):.1f}%")
        ]
        
        for name, value in metrics:
            lines.append(f"| {name} | {value} |")
        
        return "\n".join(lines)
    
    def format_bid_ask_tables(self, ocr_data: Dict) -> str:
        """Format bid/ask tables"""
        lines = [
            "## Struktur Orderbook",
            "",
            "### Bid (Buy)",
            "| Price | Lot | Freq |",
            "|-------|-----|------|"
        ]
        
        bids = ocr_data.get("bids", [])
        for bid in bids[:10]:  # Top 10 bids
            lines.append(f"| {bid.get('price', 0):,} | {bid.get('lot', 0):,} | {bid.get('freq', 0):,} |")
        
        if len(bids) > 10:
            lines.append(f"| ... {len(bids) - 10} more levels | | |")
        
        lines.extend([
            "",
            "### Ask (Sell)",
            "| Price | Lot | Freq |",
            "|-------|-----|------|"
        ])
        
        asks = ocr_data.get("asks", [])
        for ask in asks[:10]:  # Top 10 asks
            lines.append(f"| {ask.get('price', 0):,} | {ask.get('lot', 0):,} | {ask.get('freq', 0):,} |")
        
        if len(asks) > 10:
            lines.append(f"| ... {len(asks) - 10} more levels | | |")
        
        return "\n".join(lines)
    
    def format_analysis(self, analysis: Dict) -> str:
        """Format analysis results"""
        imbalance = analysis.get("imbalance", {})
        walls = analysis.get("walls", {})
        smart_money = analysis.get("smart_money", {})
        sr = analysis.get("support_resistance", {})
        
        lines = [
            "## Analisis Teknikal",
            ""
        ]
        
        # Imbalance
        bias_emoji = {
            "BULLISH": "🟢",
            "NEUTRAL": "🟡",
            "BEARISH": "🟠",
            "HEAVILY_BEARISH": "🔴"
        }.get(imbalance.get("bias", "NEUTRAL"), "⚪")
        
        lines.append(f"- **Rasio**: {imbalance.get('ratio', 0):.2f} → {bias_emoji} **{imbalance.get('bias', 'N/A')}** (score {imbalance.get('score', 0)}/100)")
        
        # Walls
        ask_walls = walls.get("ask", [])
        if ask_walls:
            top_wall = ask_walls[0]
            inst_flag = "🏛️ " if top_wall.get("is_institutional") else ""
            lines.append(f"- **Tembok Ask**: {inst_flag}{top_wall.get('price', 0):,} ({top_wall.get('lot', 0):,} lot, strength {top_wall.get('strength', 0):.0f}/100)")
        
        bid_walls = walls.get("bid", [])
        if bid_walls:
            top_wall = bid_walls[0]
            inst_flag = "🏛️ " if top_wall.get("is_institutional") else ""
            lines.append(f"- **Support Bid**: {inst_flag}{top_wall.get('price', 0):,} ({top_wall.get('lot', 0):,} lot, strength {top_wall.get('strength', 0):.0f}/100)")
        
        # Smart money
        bid_smart = smart_money.get("bid", [])
        ask_smart = smart_money.get("ask", [])
        
        if bid_smart or ask_smart:
            lines.append(f"- **Smart Money**: {len(bid_smart) + len(ask_smart)} signal(s) detected")
            for signal in bid_smart[:2] + ask_smart[:2]:
                side_emoji = "🟢" if signal.get("side") == "bid" else "🔴"
                lines.append(f"  - {side_emoji} {signal.get('pattern', 'N/A')} at {signal.get('price', 0):,} ({signal.get('confidence', 0):.0f}% confidence)")
        
        # Support/Resistance
        supports = sr.get("supports", [])
        resistances = sr.get("resistances", [])
        
        if supports:
            support_prices = ', '.join(f"{s.get('price', 0):,}" for s in supports[:3])
            lines.append(f"- **Support Levels**: {support_prices}")
        if resistances:
            resistance_prices = ', '.join(f"{r.get('price', 0):,}" for r in resistances[:3])
            lines.append(f"- **Resistance Levels**: {resistance_prices}")
        
        # Context
        momentum = analysis.get("momentum_score", 50)
        if momentum > 60:
            context = "Strong momentum, favorable for entry"
        elif momentum < 40:
            context = "Weak momentum, caution advised"
        else:
            context = "Neutral momentum, wait for confirmation"
        
        lines.append(f"- **Konteks**: {context}")
        
        return "\n".join(lines)
    
    def format_recommendations(self, recommendations: Dict) -> str:
        """Format 3-tier recommendations"""
        tiers = recommendations.get("tiers", {})
        market_context = recommendations.get("market_context", {})
        
        lines = [
            "## Rekomendasi",
            ""
        ]
        
        # Market context
        bias = market_context.get("bias", "NEUTRAL")
        bias_emoji = {
            "BULLISH": "🟢",
            "NEUTRAL": "🟡",
            "BEARISH": "🟠",
            "HEAVILY_BEARISH": "🔴"
        }.get(bias, "⚪")
        
        lines.append(f"**Bias Pasar**: {bias_emoji} {bias} (score {market_context.get('imbalance_score', 50)}/100)")
        lines.append(f"**Spread**: {market_context.get('spread_pct', 0):.2f}%")
        lines.append("")
        
        # Tier 1: Aggressive
        agg = tiers.get("aggressive", {})
        if agg:
            lines.append("### 🚀 Aggressive")
            lines.append(f"- **Entry**: {agg.get('entry_min', 0):,} - {agg.get('entry_max', 0):,}")
            lines.append(f"- **TP**: {agg.get('tp1', 0):,}")
            lines.append(f"- **SL**: {agg.get('sl', 0):,}")
            lines.append(f"- **R/R**: {agg.get('rr_ratio', 0):.2f}:1")
            for reason in agg.get("reasoning", [])[:3]:
                lines.append(f"  - {reason}")
            lines.append("")
        
        # Tier 2: Moderat
        mod = tiers.get("moderat", {})
        if mod:
            lines.append("### ⚖️ Moderat")
            lines.append(f"- **Entry**: {mod.get('entry_min', 0):,} - {mod.get('entry_max', 0):,}")
            lines.append(f"- **TP**: {mod.get('tp1', 0):,}")
            lines.append(f"- **SL**: {mod.get('sl', 0):,}")
            lines.append(f"- **R/R**: {mod.get('rr_ratio', 0):.2f}:1")
            for reason in mod.get("reasoning", [])[:3]:
                lines.append(f"  - {reason}")
            lines.append("")
        
        # Tier 3: Low Risk (PRIORITY)
        lr = tiers.get("low_risk", {})
        if lr:
            lines.append("### 🛡️ Low Risk (Priority)")
            lines.append(f"- **Entry**: {lr.get('entry_min', 0):,} - {lr.get('entry_max', 0):,}")
            lines.append(f"- **TP1**: {lr.get('tp1', 0):,}")
            if lr.get("tp2"):
                lines.append(f"- **TP2**: {lr.get('tp2', 0):,}")
            lines.append(f"- **SL**: {lr.get('sl', 0):,}")
            lines.append(f"- **R/R**: {lr.get('rr_ratio', 0):.2f}:1")
            for reason in lr.get("reasoning", []):
                lines.append(f"  - {reason}")
        
        return "\n".join(lines)
    
    def format_portfolio_verdict(self, verdict: Dict) -> str:
        """Format portfolio verdict"""
        lines = [
            "## Portfolio Verdict",
            ""
        ]
        
        action = verdict.get("action", "N/A")
        action_emoji = {
            "SELL": "🔴",
            "HOLD_WITH_SL": "🟡",
            "AVERAGE_DOWN": "🟢",
            "CUT_LOSS": "🔴",
            "SECURE_PROFIT": "🟢"
        }.get(action, "⚪")
        
        lines.append(f"**Action**: {action_emoji} {action}")
        lines.append(f"**Floating P/L**: {verdict.get('floating_pnl', 0):,.0f} ({verdict.get('floating_pnl_pct', 0):+.1f}%)")
        
        if verdict.get("recommended_sl"):
            lines.append(f"**Recommended SL**: {verdict.get('recommended_sl', 0):,}")
        if verdict.get("recommended_tp"):
            lines.append(f"**Recommended TP**: {verdict.get('recommended_tp', 0):,}")
        
        lines.append("")
        lines.append("**Reasoning**:")
        for reason in verdict.get("reasoning", []):
            lines.append(f"- {reason}")
        
        return "\n".join(lines)
    
    def format_tracking(self, tracking: Dict) -> str:
        """Format tracking results"""
        lines = [
            "## Delta Tracking",
            ""
        ]
        
        dist = tracking.get("distribution", {})
        if dist.get("detected"):
            lines.append(f"⚠ **DISTRIBUTION DETECTED** ({dist.get('pattern_type', 'N/A').upper()})")
            lines.append(f"Confidence: {dist.get('confidence', 0):.0f}/100")
            for evidence in dist.get("evidence", []):
                lines.append(f"- {evidence}")
        else:
            lines.append("✓ No distribution pattern detected")
        
        lines.append("")
        
        # Trends
        trends = tracking.get("trends", {})
        lines.append("**Trends**:")
        lines.append(f"- Bid/Ask Ratio: {trends.get('bid_ask_ratio', 'unknown')} ({trends.get('ratio_change', 0):+.2f})")
        lines.append(f"- Momentum: {trends.get('momentum', 'unknown')} ({trends.get('momentum_change', 0):+.0f} pts)")
        lines.append(f"- Volume: {trends.get('total_volume', 'unknown')} ({trends.get('volume_change_pct', 0):+.1f}%)")
        
        # Recent changes
        changes = tracking.get("changes", [])
        if changes:
            latest = changes[-1]
            lines.append("")
            lines.append(f"**Latest changes ({latest.get('from', '')} → {latest.get('to', '')})**:")
            
            for change in latest.get("changes", []):
                if change.get("significance") in ["high", "medium"]:
                    arrow = "↑" if change.get("direction") == "increase" else "↓" if change.get("direction") == "decrease" else "→"
                    lines.append(f"- {arrow} {change.get('metric', 'N/A')}: {change.get('change_pct', 0):+.1f}% ({change.get('significance', 'low')})")
        
        return "\n".join(lines)
    
    def format_full_report(self, data: Dict) -> str:
        """
        Format complete markdown report
        
        Args:
            data: dict with all pipeline results
            
        Returns:
            Complete markdown report
        """
        ocr_data = data.get("ocr_data", {})
        validation = data.get("validation", {})
        analysis = data.get("analysis", {})
        recommendations = data.get("recommendations", {})
        portfolio_verdict = data.get("portfolio_verdict")
        tracking = data.get("tracking")
        
        lines = [
            f"# Analisis Orderbook {ocr_data.get('ticker', 'N/A')} — {ocr_data.get('timestamp', 'N/A')}",
            ""
        ]
        
        # Validation warning
        if validation.get("manual_verification_required"):
            lines.append("> ⚠ **MANUAL VERIFICATION REQUIRED** — Confidence below threshold or validation errors detected")
            lines.append("")
        
        # Orderbook summary
        lines.append(self.format_orderbook_summary(ocr_data))
        lines.append("")
        
        # Bid/ask tables
        lines.append(self.format_bid_ask_tables(ocr_data))
        lines.append("")
        
        # Analysis
        lines.append(self.format_analysis(analysis))
        lines.append("")
        
        # Recommendations
        lines.append(self.format_recommendations(recommendations))
        lines.append("")
        
        # Portfolio verdict (if applicable)
        if portfolio_verdict:
            lines.append(self.format_portfolio_verdict(portfolio_verdict))
            lines.append("")
        
        # Tracking (if applicable)
        if tracking:
            lines.append(self.format_tracking(tracking))
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"*Generated by IDX Orderbook Analysis v1.0 • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(lines)
    
    def format_json(self, data: Dict) -> str:
        """Format as JSON"""
        return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Format orderbook analysis results")
    parser.add_argument("input", help="Input JSON file with pipeline results")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    try:
        with open(args.input) as f:
            data = json.load(f)
        
        formatter = OutputFormatter()
        
        if args.format == "markdown":
            output = formatter.format_full_report(data)
        else:
            output = formatter.format_json(data)
        
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Report saved to: {args.output}")
        else:
            print(output)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
