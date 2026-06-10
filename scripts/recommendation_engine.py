#!/usr/bin/env python3
"""
IDX Orderbook Recommendation Engine
Phase 4: 3-tier entry recommendations and portfolio verdict

3-Tier System:
1. AGGRESSIVE: Entry near current price, tight SL, 1:1-1.2:1 R/R
2. MODERAT: Entry at pullback, wider SL, 1.5:1-1.8:1 R/R
3. LOW RISK: Entry at strong support, widest SL, 2:1-2.5:1 R/R (priority tier)

Sell/Keep/Hold logic for existing positions based on:
- Floating P/L
- Support/resistance proximity
- Imbalance bias
- Pemantauan Khusus status
"""

import sys
import json
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class Verdict(Enum):
    """Position verdict"""
    SELL = "SELL"
    HOLD_WITH_SL = "HOLD_WITH_SL"
    AVERAGE_DOWN = "AVERAGE_DOWN"
    CUT_LOSS = "CUT_LOSS"
    SECURE_PROFIT = "SECURE_PROFIT"


@dataclass
class EntryTier:
    """Entry recommendation tier"""
    tier: str  # "AGGRESSIVE", "MODERAT", "LOW_RISK"
    entry_min: int
    entry_max: int
    tp1: int
    tp2: Optional[int]
    sl: int
    rr_ratio: float
    reasoning: List[str]
    risk_level: str


@dataclass
class PortfolioVerdict:
    """Verdict for existing position"""
    verdict: str  # SELL, HOLD_WITH_SL, AVERAGE_DOWN, CUT_LOSS, SECURE_PROFIT
    floating_pnl: float
    floating_pnl_pct: float
    action: str
    reasoning: List[str]
    recommended_sl: Optional[int]
    recommended_tp: Optional[int]


class RecommendationEngine:
    """Generate trading recommendations from orderbook analysis"""
    
    def __init__(self, debug=False):
        self.debug = debug
    
    def generate_tiers(self, analysis: Dict, portfolio: Optional[Dict] = None) -> Dict:
        """
        Generate 3-tier entry recommendations
        
        Args:
            analysis: Output from OrderbookAnalyzer
            portfolio: Optional portfolio data {avg_price, lot, pemantauan_khusus}
            
        Returns:
            dict with 3 entry tiers
        """
        imbalance = analysis.get("imbalance", {})
        walls = analysis.get("walls", {})
        smart_money = analysis.get("smart_money", {})
        sr = analysis.get("support_resistance", {})
        
        # Extract key prices
        bid_walls = walls.get("bid", [])
        ask_walls = walls.get("ask", [])
        supports = sr.get("supports", [])
        resistances = sr.get("resistances", [])
        
        # Current market prices
        arb = analysis.get("arb", 0)  # Bid
        ara = analysis.get("ara", 0)  # Ask
        avg = analysis.get("avg", 0)  # Average
        
        # Support/resistance levels
        strongest_support = supports[0]["price"] if supports else arb
        strongest_resistance = resistances[0]["price"] if resistances else ara
        
        # Secondary levels
        second_support = supports[1]["price"] if len(supports) > 1 else strongest_support * 0.98
        second_resistance = resistances[1]["price"] if len(resistances) > 1 else strongest_resistance * 1.02
        
        tiers = {}
        
        # TIER 1: AGGRESSIVE
        # Entry: near current bid (±1-2 tick)
        # SL: support terdekat
        # TP: resistance terdekat
        # Use case: momentum play, quick scalp
        agg_entry_min = int(arb * 0.99)  # 1% below bid
        agg_entry_max = int(arb)
        agg_sl = int(strongest_support * 0.98)
        agg_tp = int(strongest_resistance * 1.01)
        agg_rr = (agg_tp - agg_entry_max) / (agg_entry_max - agg_sl) if agg_entry_max > agg_sl else 0
        
        agg_reasoning = [
            f"Entry near current bid ({agg_entry_min}-{agg_entry_max})",
            f"SL at support {agg_sl}",
            f"TP at resistance {agg_tp}",
            f"R/R ratio: {agg_rr:.2f}:1",
            "Use case: momentum scalp, quick entry/exit"
        ]
        
        if imbalance.get("bias") == "BULLISH":
            agg_reasoning.append("✓ Bullish bias supports aggressive entry")
        elif imbalance.get("bias") == "HEAVILY_BEARISH":
            agg_reasoning.append("⚠ Heavily bearish - aggressive entry risky")
        
        tiers["aggressive"] = EntryTier(
            tier="AGGRESSIVE",
            entry_min=agg_entry_min,
            entry_max=agg_entry_max,
            tp1=agg_tp,
            tp2=None,
            sl=agg_sl,
            rr_ratio=agg_rr,
            reasoning=agg_reasoning,
            risk_level="HIGH"
        )
        
        # TIER 2: MODERAT
        # Entry: pullback ke support pertama
        # SL: bawah support pertama
        # TP: mid resistance
        # Use case: swing entry, balanced risk/reward
        mod_entry_min = int(strongest_support * 1.01)
        mod_entry_max = int(strongest_support * 1.03)
        mod_sl = int(strongest_support * 0.97)
        mod_tp = int((strongest_support + strongest_resistance) / 2)
        mod_rr = (mod_tp - mod_entry_max) / (mod_entry_max - mod_sl) if mod_entry_max > mod_sl else 0
        
        mod_reasoning = [
            f"Entry at pullback to support ({mod_entry_min}-{mod_entry_max})",
            f"SL below support {mod_sl}",
            f"TP at mid-level {mod_tp}",
            f"R/R ratio: {mod_rr:.2f}:1",
            "Use case: swing trade, balanced entry"
        ]
        
        if imbalance.get("bias") in ["BULLISH", "NEUTRAL"]:
            mod_reasoning.append("✓ Suitable for moderat entry")
        
        tiers["moderat"] = EntryTier(
            tier="MODERAT",
            entry_min=mod_entry_min,
            entry_max=mod_entry_max,
            tp1=mod_tp,
            tp2=None,
            sl=mod_sl,
            rr_ratio=mod_rr,
            reasoning=mod_reasoning,
            risk_level="MEDIUM"
        )
        
        # TIER 3: LOW RISK (PRIORITY)
        # Entry: zona support terkuat (wall bid)
        # SL: bawah wall bid
        # TP1: support pertama dari atas
        # TP2: resistance pertama
        # Use case: value entry, best R/R
        # Extra analysis: lot validation, freq check
        
        # Find strongest bid wall
        strongest_bid_wall = bid_walls[0] if bid_walls else None
        wall_price = strongest_bid_wall["price"] if strongest_bid_wall else strongest_support
        
        lr_entry_min = int(wall_price * 0.99)
        lr_entry_max = int(wall_price * 1.01)
        lr_sl = int(wall_price * 0.96)
        lr_tp1 = int(second_support * 1.02)
        lr_tp2 = int(strongest_resistance * 1.01)
        lr_rr = (lr_tp2 - lr_entry_max) / (lr_entry_max - lr_sl) if lr_entry_max > lr_sl else 0
        
        lr_reasoning = [
            f"Entry at strongest support wall ({lr_entry_min}-{lr_entry_max})",
            f"SL below wall {lr_sl}",
            f"TP1 at secondary support {lr_tp1}",
            f"TP2 at resistance {lr_tp2}",
            f"R/R ratio: {lr_rr:.2f}:1",
            "Use case: value entry, best risk/reward"
        ]
        
        # Extra validation for low risk tier
        if strongest_bid_wall:
            lr_reasoning.append(f"✓ Wall strength: {strongest_bid_wall.get('strength', 0):.0f}/100")
            if strongest_bid_wall.get("is_institutional"):
                lr_reasoning.append("✓ Institutional support detected")
            lr_reasoning.append(f"✓ Wall lot: {strongest_bid_wall.get('lot', 0):,} ({strongest_bid_wall.get('freq', 0)} freq)")
        
        # Check for smart money on bid side
        bid_smart_money = smart_money.get("bid", [])
        if bid_smart_money:
            lr_reasoning.append(f"✓ Smart money signal: {bid_smart_money[0].get('pattern')}")
        
        tiers["low_risk"] = EntryTier(
            tier="LOW_RISK",
            entry_min=lr_entry_min,
            entry_max=lr_entry_max,
            tp1=lr_tp1,
            tp2=lr_tp2,
            sl=lr_sl,
            rr_ratio=lr_rr,
            reasoning=lr_reasoning,
            risk_level="LOW"
        )
        
        return {
            "tiers": {
                "aggressive": asdict(tiers["aggressive"]),
                "moderat": asdict(tiers["moderat"]),
                "low_risk": asdict(tiers["low_risk"])
            },
            "market_context": {
                "bias": imbalance.get("bias"),
                "imbalance_score": imbalance.get("score"),
                "strongest_support": strongest_support,
                "strongest_resistance": strongest_resistance,
                "spread_pct": imbalance.get("spread_pct")
            }
        }
    
    def sell_or_keep_verdict(self, analysis: Dict, portfolio: Dict) -> PortfolioVerdict:
        """
        Generate sell/keep/hold verdict for existing position
        
        Args:
            analysis: Output from OrderbookAnalyzer
            portfolio: {avg_price, lot, pemantauan_khusus (optional)}
            
        Returns:
            PortfolioVerdict with action and reasoning
        """
        avg_price = portfolio.get("avg_price", 0)
        lot = portfolio.get("lot", 0)
        pemantauan_khusus = portfolio.get("pemantauan_khusus", False)
        
        if not avg_price or not lot:
            raise ValueError("Portfolio must have avg_price and lot")
        
        # Current market prices
        arb = analysis.get("arb", 0)  # Current bid
        ara = analysis.get("ara", 0)  # Current ask
        iep = analysis.get("iep", 0)  # Initial Equity Price (if available)
        
        # Calculate floating P/L
        current_price = arb  # Use bid for conservative estimate
        floating_pnl = (current_price - avg_price) * lot
        floating_pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
        
        # Get support/resistance
        sr = analysis.get("support_resistance", {})
        supports = sr.get("supports", [])
        strongest_support = supports[0]["price"] if supports else arb * 0.95
        
        imbalance = analysis.get("imbalance", {})
        bias = imbalance.get("bias", "NEUTRAL")
        
        reasoning = []
        verdict = Verdict.HOLD_WITH_SL
        recommended_sl = None
        recommended_tp = None
        
        # Case 1: IEP at ARB (imminent distribution)
        if iep and iep == arb:
            verdict = Verdict.SELL
            reasoning.append("⚠ IEP = ARB: Imminent distribution signal")
            reasoning.append("Action: SELL immediately to avoid trap")
            return PortfolioVerdict(
                verdict=verdict.value,
                floating_pnl=floating_pnl,
                floating_pnl_pct=floating_pnl_pct,
                action="SELL_IMMEDIATELY",
                reasoning=reasoning,
                recommended_sl=None,
                recommended_tp=None
            )
        
        # Case 2: Pemantauan Khusus (special monitoring)
        if pemantauan_khusus:
            reasoning.append("⚠ Pemantauan Khusus: Extra caution required")
            
            # If profit is large, secure it
            if floating_pnl_pct > 100:
                verdict = Verdict.SECURE_PROFIT
                reasoning.append(f"✓ Profit {floating_pnl_pct:.1f}% is very large")
                reasoning.append("Action: Secure profit, reduce position or set tight TP")
                recommended_tp = int(current_price * 1.02)  # 2% above current
            else:
                verdict = Verdict.HOLD_WITH_SL
                reasoning.append("Action: HOLD with tight SL, monitor closely")
                recommended_sl = int(strongest_support * 0.98)
        
        # Case 3: Large profit (>100%)
        elif floating_pnl_pct > 100:
            verdict = Verdict.SECURE_PROFIT
            reasoning.append(f"✓ Massive profit: {floating_pnl_pct:.1f}%")
            reasoning.append("Action: Secure profit, consider taking partial")
            recommended_tp = int(current_price * 1.02)
        
        # Case 4: Profit (>20%)
        elif floating_pnl_pct > 20:
            verdict = Verdict.HOLD_WITH_SL
            reasoning.append(f"✓ Good profit: {floating_pnl_pct:.1f}%")
            reasoning.append("Action: HOLD with SL at support")
            recommended_sl = int(strongest_support * 0.98)
            recommended_tp = int(current_price * 1.05)
        
        # Case 5: Small profit (0-20%)
        elif floating_pnl_pct > 0:
            verdict = Verdict.HOLD_WITH_SL
            reasoning.append(f"✓ Small profit: {floating_pnl_pct:.1f}%")
            
            if bias == "BULLISH":
                reasoning.append("✓ Bullish bias: potential for more upside")
                reasoning.append("Action: HOLD with SL at support")
                recommended_sl = int(strongest_support * 0.98)
            elif bias == "HEAVILY_BEARISH":
                reasoning.append("⚠ Heavily bearish: risk of reversal")
                reasoning.append("Action: Consider taking profit")
                verdict = Verdict.SECURE_PROFIT
            else:
                reasoning.append("Action: HOLD with SL at support")
                recommended_sl = int(strongest_support * 0.98)
        
        # Case 6: Break even (±1%)
        elif floating_pnl_pct > -1:
            verdict = Verdict.HOLD_WITH_SL
            reasoning.append("≈ Near break even")
            reasoning.append("Action: HOLD with SL, wait for direction clarity")
            recommended_sl = int(avg_price * 0.98)
        
        # Case 7: Small loss (-1% to -10%)
        elif floating_pnl_pct > -10:
            verdict = Verdict.HOLD_WITH_SL
            reasoning.append(f"⚠ Small loss: {floating_pnl_pct:.1f}%")
            
            if bias == "BULLISH":
                reasoning.append("✓ Bullish bias: potential recovery")
                reasoning.append("Action: HOLD with SL, consider averaging down")
                verdict = Verdict.AVERAGE_DOWN
                recommended_sl = int(strongest_support * 0.98)
            else:
                reasoning.append("Action: HOLD with tight SL")
                recommended_sl = int(avg_price * 0.98)
        
        # Case 8: Significant loss (< -10%)
        else:
            verdict = Verdict.CUT_LOSS
            reasoning.append(f"✗ Significant loss: {floating_pnl_pct:.1f}%")
            reasoning.append("Action: CUT LOSS to prevent further damage")
        
        return PortfolioVerdict(
            verdict=verdict.value,
            floating_pnl=floating_pnl,
            floating_pnl_pct=floating_pnl_pct,
            action=verdict.value,
            reasoning=reasoning,
            recommended_sl=recommended_sl,
            recommended_tp=recommended_tp
        )
    
    def generate_recommendations(self, analysis: Dict, portfolio: Optional[Dict] = None) -> Dict:
        """
        Generate complete recommendations (entry tiers + portfolio verdict)
        
        Args:
            analysis: Output from OrderbookAnalyzer
            portfolio: Optional portfolio data
            
        Returns:
            dict with all recommendations
        """
        tiers = self.generate_tiers(analysis, portfolio)
        
        verdict = None
        if portfolio:
            verdict = self.sell_or_keep_verdict(analysis, portfolio)
        
        result = {
            "ticker": analysis.get("ticker"),
            "timestamp": analysis.get("timestamp"),
            "entry_recommendations": tiers,
            "portfolio_verdict": asdict(verdict) if verdict else None
        }
        
        if self.debug:
            self._print_recommendations(result)
        
        return result
    
    def _print_recommendations(self, result: Dict):
        """Print recommendations report"""
        print("\n=== RECOMMENDATIONS ===")
        print(f"Ticker: {result['ticker']}")
        print(f"Time: {result['timestamp']}")
        
        tiers = result["entry_recommendations"]["tiers"]
        
        for tier_name in ["aggressive", "moderat", "low_risk"]:
            tier = tiers[tier_name]
            print(f"\n{tier['tier']}:")
            print(f"  Entry: {tier['entry_min']}-{tier['entry_max']}")
            print(f"  TP: {tier['tp1']}" + (f", {tier['tp2']}" if tier['tp2'] else ""))
            print(f"  SL: {tier['sl']}")
            print(f"  R/R: {tier['rr_ratio']:.2f}:1")
            for reason in tier['reasoning']:
                print(f"  • {reason}")
        
        if result["portfolio_verdict"]:
            verdict = result["portfolio_verdict"]
            print(f"\n=== PORTFOLIO VERDICT ===")
            print(f"Action: {verdict['action']}")
            print(f"Floating P/L: {verdict['floating_pnl']:,.0f} ({verdict['floating_pnl_pct']:.1f}%)")
            for reason in verdict['reasoning']:
                print(f"  • {reason}")


def main():
    parser = argparse.ArgumentParser(description="Generate trading recommendations")
    parser.add_argument("input", help="Input JSON file with analysis data")
    parser.add_argument("--portfolio", help="Portfolio JSON file {avg_price, lot, pemantauan_khusus}")
    parser.add_argument("--debug", action="store_true", help="Print detailed recommendations")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    try:
        with open(args.input) as f:
            analysis = json.load(f)
        
        portfolio = None
        if args.portfolio:
            with open(args.portfolio) as f:
                portfolio = json.load(f)
        
        engine = RecommendationEngine(debug=args.debug)
        result = engine.generate_recommendations(analysis, portfolio)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if not args.debug:
                engine._print_recommendations(result)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
