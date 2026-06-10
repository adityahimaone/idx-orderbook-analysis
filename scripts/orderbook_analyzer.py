#!/usr/bin/env python3
"""
IDX Orderbook Analyzer
Phase 3: Enhanced analysis engine

Features:
- Wall detection with lot/freq ratio analysis
- Smart money detection (institutional vs retail patterns)
- Bid/ask imbalance with proven thresholds
- Support/resistance identification
- Momentum scoring
"""

import sys
import json
import argparse
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from statistics import median, mean


@dataclass
class Wall:
    """Orderbook wall (large lot concentration)"""
    price: int
    lot: int
    freq: int
    side: str  # "bid" or "ask"
    strength: float  # 0-100 score
    lot_freq_ratio: float
    is_institutional: bool


@dataclass
class SupportResistance:
    """Support or resistance level"""
    price: int
    total_lot: int
    avg_freq: float
    level_count: int
    strength: float  # 0-100 score
    type: str  # "support" or "resistance"


@dataclass
class ImbalanceAnalysis:
    """Bid/ask imbalance analysis"""
    ratio: float  # ask_total / bid_total
    bias: str  # "BULLISH", "NEUTRAL", "BEARISH", "HEAVILY_BEARISH"
    score: int  # 0-100 (50 = neutral)
    bid_total: int
    ask_total: int
    spread_pct: float


@dataclass
class SmartMoneySignal:
    """Smart money detection result"""
    detected: bool
    side: str  # "bid" or "ask"
    price: int
    lot: int
    freq: int
    pattern: str  # "institutional_single", "institutional_cluster", "retail_fomo"
    confidence: float  # 0-100


class OrderbookAnalyzer:
    """Analyze orderbook structure and patterns"""
    
    # Thresholds from live sessions (KAEF, IRRA, FIRE, WBSA)
    IMBALANCE_THRESHOLDS = {
        "BULLISH": 0.8,           # ratio < 0.8
        "NEUTRAL": 1.2,           # 0.8 <= ratio <= 1.2
        "BEARISH": 2.0,           # 1.2 < ratio <= 2.0
        "HEAVILY_BEARISH": 2.0    # ratio > 2.0 (e.g., KAEF 09:15: 3.41)
    }
    
    WALL_THRESHOLD_MULTIPLIER = 2.5  # lot > 2.5x median = wall
    INSTITUTIONAL_LOT_THRESHOLD = 10000  # lot >= 10k likely institutional
    INSTITUTIONAL_FREQ_RATIO = 100  # lot/freq > 100 = single large player
    
    def __init__(self, debug=False):
        self.debug = debug
    
    def detect_walls(self, levels: List[Dict], side: str, threshold_multiplier: float = None) -> List[Wall]:
        """
        Detect walls (large lot concentrations)
        
        Wall = level with lot > threshold_multiplier * median of all levels
        
        Examples from live sessions:
        - FIRE 160 bid: 28,029 lot (2.5x median → confirmed wall)
        - IRRA 635 ask: 11,936 lot (ARA wall)
        - KAEF 790 ask: 33,750 lot (ARA wall)
        """
        if not levels:
            return []
        
        threshold_multiplier = threshold_multiplier or self.WALL_THRESHOLD_MULTIPLIER
        
        lots = [lvl.get("lot", 0) for lvl in levels if lvl.get("lot")]
        if not lots:
            return []
        
        median_lot = median(lots)
        threshold = median_lot * threshold_multiplier
        
        walls = []
        for lvl in levels:
            lot = lvl.get("lot", 0)
            freq = lvl.get("freq", 1)
            price = lvl.get("price", 0)
            
            if lot >= threshold:
                lot_freq_ratio = lot / freq if freq > 0 else 0
                is_institutional = lot >= self.INSTITUTIONAL_LOT_THRESHOLD and lot_freq_ratio > self.INSTITUTIONAL_FREQ_RATIO
                
                # Calculate strength score (0-100)
                # Based on: lot size relative to median, freq pattern
                lot_strength = min(100, (lot / median_lot) * 20)
                freq_strength = min(100, lot_freq_ratio / 10) if is_institutional else 50
                strength = (lot_strength + freq_strength) / 2
                
                walls.append(Wall(
                    price=price,
                    lot=lot,
                    freq=freq,
                    side=side,
                    strength=strength,
                    lot_freq_ratio=lot_freq_ratio,
                    is_institutional=is_institutional
                ))
        
        # Sort by strength
        walls.sort(key=lambda w: w.strength, reverse=True)
        return walls
    
    def calculate_imbalance(self, bid_total: int, ask_total: int, arb: int, ara: int) -> ImbalanceAnalysis:
        """
        Calculate bid/ask imbalance
        
        Returns bias based on thresholds from live observations:
        - < 0.8  → BULLISH
        - 0.8-1.2 → NEUTRAL
        - 1.2-2.0 → BEARISH
        - > 2.0  → HEAVILY_BEARISH (e.g., KAEF 09:15: ratio 3.41)
        """
        ratio = ask_total / bid_total if bid_total > 0 else float('inf')
        
        # Determine bias
        if ratio < self.IMBALANCE_THRESHOLDS["BULLISH"]:
            bias = "BULLISH"
            score = int(50 + (0.8 - ratio) * 50)  # 50-90
        elif ratio <= self.IMBALANCE_THRESHOLDS["NEUTRAL"]:
            bias = "NEUTRAL"
            score = 50  # Neutral
        elif ratio <= self.IMBALANCE_THRESHOLDS["BEARISH"]:
            bias = "BEARISH"
            score = int(50 - (ratio - 1.2) * 25)  # 30-50
        else:
            bias = "HEAVILY_BEARISH"
            score = max(0, int(30 - (ratio - 2.0) * 10))  # 0-30
        
        # Calculate spread percentage
        spread_pct = ((ara - arb) / arb * 100) if arb > 0 else 0
        
        return ImbalanceAnalysis(
            ratio=ratio,
            bias=bias,
            score=score,
            bid_total=bid_total,
            ask_total=ask_total,
            spread_pct=spread_pct
        )
    
    def detect_smart_money(self, levels: List[Dict], side: str) -> List[SmartMoneySignal]:
        """
        Detect smart money patterns
        
        Patterns:
        1. Institutional single: Large lot, low freq → one big player
           Example: FIRE 160: 28K lot, freq 206 → ratio 136
        
        2. Institutional cluster: Multiple large lots at similar prices
        
        3. Retail FOMO: Large lot, high freq → many small players
           Example: lot 20K, freq 5000 → ratio 4
        """
        if not levels:
            return []
        
        signals = []
        lots = [lvl.get("lot", 0) for lvl in levels if lvl.get("lot")]
        
        if not lots:
            return []
        
        median_lot = median(lots)
        
        for lvl in levels:
            lot = lvl.get("lot", 0)
            freq = lvl.get("freq", 1)
            price = lvl.get("price", 0)
            
            if lot < median_lot * 2:  # Only analyze significant levels
                continue
            
            lot_freq_ratio = lot / freq if freq > 0 else 0
            
            # Pattern 1: Institutional single player
            if lot >= self.INSTITUTIONAL_LOT_THRESHOLD and lot_freq_ratio > self.INSTITUTIONAL_FREQ_RATIO:
                confidence = min(100, (lot_freq_ratio / self.INSTITUTIONAL_FREQ_RATIO) * 50 + 50)
                signals.append(SmartMoneySignal(
                    detected=True,
                    side=side,
                    price=price,
                    lot=lot,
                    freq=freq,
                    pattern="institutional_single",
                    confidence=confidence
                ))
            
            # Pattern 2: Retail FOMO (high freq relative to lot)
            elif lot_freq_ratio < 10:
                confidence = min(100, (10 - lot_freq_ratio) * 10 + 50)
                signals.append(SmartMoneySignal(
                    detected=True,
                    side=side,
                    price=price,
                    lot=lot,
                    freq=freq,
                    pattern="retail_fomo",
                    confidence=confidence
                ))
        
        # Pattern 3: Institutional cluster (multiple large lots within 5% price range)
        if len(levels) >= 3:
            sorted_levels = sorted(levels, key=lambda x: x.get("price", 0))
            for i in range(len(sorted_levels) - 2):
                lvl1, lvl2, lvl3 = sorted_levels[i:i+3]
                p1, p2, p3 = lvl1.get("price", 0), lvl2.get("price", 0), lvl3.get("price", 0)
                
                if p1 > 0 and (p3 - p1) / p1 <= 0.05:  # Within 5%
                    total_lot = sum(lvl.get("lot", 0) for lvl in [lvl1, lvl2, lvl3])
                    if total_lot >= self.INSTITUTIONAL_LOT_THRESHOLD * 2:
                        signals.append(SmartMoneySignal(
                            detected=True,
                            side=side,
                            price=p2,  # Middle price
                            lot=total_lot,
                            freq=sum(lvl.get("freq", 0) for lvl in [lvl1, lvl2, lvl3]),
                            pattern="institutional_cluster",
                            confidence=80
                        ))
                        break
        
        return signals
    
    def generate_support_resistance(self, bids: List[Dict], asks: List[Dict]) -> Tuple[List[SupportResistance], List[SupportResistance]]:
        """
        Identify support and resistance levels
        
        Support = bid levels with largest lots (top 3)
        Resistance = ask levels with largest lots (top 3)
        Weighted score based on lot + freq
        """
        supports = []
        resistances = []
        
        # Support from bids
        if bids:
            sorted_bids = sorted(bids, key=lambda x: x.get("lot", 0), reverse=True)[:3]
            for i, bid in enumerate(sorted_bids):
                lot = bid.get("lot", 0)
                freq = bid.get("freq", 1)
                price = bid.get("price", 0)
                
                # Strength: weighted by lot size and position (1st > 2nd > 3rd)
                position_weight = (3 - i) / 3  # 1.0, 0.67, 0.33
                lot_weight = lot / sorted_bids[0].get("lot", 1)
                strength = (position_weight * 0.6 + lot_weight * 0.4) * 100
                
                supports.append(SupportResistance(
                    price=price,
                    total_lot=lot,
                    avg_freq=freq,
                    level_count=1,
                    strength=strength,
                    type="support"
                ))
        
        # Resistance from asks
        if asks:
            sorted_asks = sorted(asks, key=lambda x: x.get("lot", 0), reverse=True)[:3]
            for i, ask in enumerate(sorted_asks):
                lot = ask.get("lot", 0)
                freq = ask.get("freq", 1)
                price = ask.get("price", 0)
                
                position_weight = (3 - i) / 3
                lot_weight = lot / sorted_asks[0].get("lot", 1)
                strength = (position_weight * 0.6 + lot_weight * 0.4) * 100
                
                resistances.append(SupportResistance(
                    price=price,
                    total_lot=lot,
                    avg_freq=freq,
                    level_count=1,
                    strength=strength,
                    type="resistance"
                ))
        
        return supports, resistances
    
    def calculate_momentum_score(self, data: Dict, imbalance: ImbalanceAnalysis) -> int:
        """
        Calculate momentum score (0-100)
        
        Based on:
        - Bid/ask imbalance
        - Price position relative to high/low
        - Average price trend
        """
        score = 50  # Start neutral
        
        # Imbalance contribution (±30 points)
        score += (50 - imbalance.score) * 0.6
        
        # Price position (±20 points)
        high = data.get("high", 0)
        low = data.get("low", 0)
        avg = data.get("avg", 0)
        
        if high > low:
            price_position = (avg - low) / (high - low)  # 0-1
            score += (price_position - 0.5) * 40  # -20 to +20
        
        return max(0, min(100, int(score)))
    
    def analyze(self, orderbook_data: Dict) -> Dict:
        """
        Full orderbook analysis
        
        Args:
            orderbook_data: Validated OCR data
            
        Returns:
            dict with analysis results
        """
        bids = orderbook_data.get("bids", [])
        asks = orderbook_data.get("asks", [])
        
        # Calculate totals
        bid_total = sum(b.get("lot", 0) for b in bids)
        ask_total = sum(a.get("lot", 0) for a in asks)
        
        arb = orderbook_data.get("arb", 0)
        ara = orderbook_data.get("ara", 0)
        
        # Imbalance analysis
        imbalance = self.calculate_imbalance(bid_total, ask_total, arb, ara)
        
        # Wall detection
        bid_walls = self.detect_walls(bids, "bid")
        ask_walls = self.detect_walls(asks, "ask")
        
        # Smart money detection
        bid_smart_money = self.detect_smart_money(bids, "bid")
        ask_smart_money = self.detect_smart_money(asks, "ask")
        
        # Support/resistance
        supports, resistances = self.generate_support_resistance(bids, asks)
        
        # Momentum score
        momentum_score = self.calculate_momentum_score(orderbook_data, imbalance)
        
        result = {
            "ticker": orderbook_data.get("ticker"),
            "timestamp": orderbook_data.get("timestamp"),
            "imbalance": asdict(imbalance),
            "momentum_score": momentum_score,
            "walls": {
                "bid": [asdict(w) for w in bid_walls],
                "ask": [asdict(w) for w in ask_walls]
            },
            "smart_money": {
                "bid": [asdict(s) for s in bid_smart_money],
                "ask": [asdict(s) for s in ask_smart_money]
            },
            "support_resistance": {
                "supports": [asdict(s) for s in supports],
                "resistances": [asdict(r) for r in resistances]
            },
            "summary": self._generate_summary(imbalance, bid_walls, ask_walls, bid_smart_money, ask_smart_money, momentum_score)
        }
        
        if self.debug:
            self._print_analysis(result)
        
        return result
    
    def _generate_summary(self, imbalance, bid_walls, ask_walls, bid_smart_money, ask_smart_money, momentum_score) -> str:
        """Generate human-readable summary"""
        lines = []
        
        # Bias
        lines.append(f"Bias: {imbalance.bias} (ratio {imbalance.ratio:.2f})")
        
        # Walls
        if ask_walls:
            top_ask_wall = ask_walls[0]
            lines.append(f"Tembok Ask: {top_ask_wall.price} ({top_ask_wall.lot:,} lot)")
        
        if bid_walls:
            top_bid_wall = bid_walls[0]
            lines.append(f"Support Bid: {top_bid_wall.price} ({top_bid_wall.lot:,} lot)")
        
        # Smart money
        institutional_signals = [s for s in bid_smart_money + ask_smart_money if s.pattern == "institutional_single"]
        if institutional_signals:
            lines.append(f"Smart Money: {len(institutional_signals)} institutional signal(s) detected")
        
        # Momentum
        if momentum_score > 60:
            lines.append(f"Momentum: STRONG ({momentum_score}/100)")
        elif momentum_score < 40:
            lines.append(f"Momentum: WEAK ({momentum_score}/100)")
        else:
            lines.append(f"Momentum: NEUTRAL ({momentum_score}/100)")
        
        return " | ".join(lines)
    
    def _print_analysis(self, result: Dict):
        """Print analysis report"""
        print("\n=== ORDERBOOK ANALYSIS ===")
        print(f"Ticker: {result['ticker']}")
        print(f"Time: {result['timestamp']}")
        print(f"\n{result['summary']}")
        
        imb = result["imbalance"]
        print(f"\nImbalance: {imb['bias']} (score {imb['score']}/100)")
        print(f"  Bid Total: {imb['bid_total']:,} lot")
        print(f"  Ask Total: {imb['ask_total']:,} lot")
        print(f"  Ratio: {imb['ratio']:.2f}")
        print(f"  Spread: {imb['spread_pct']:.2f}%")
        
        if result["walls"]["ask"]:
            print(f"\nAsk Walls ({len(result['walls']['ask'])}):")
            for w in result["walls"]["ask"][:3]:
                inst = " [INSTITUTIONAL]" if w["is_institutional"] else ""
                print(f"  {w['price']}: {w['lot']:,} lot (strength {w['strength']:.0f}/100){inst}")
        
        if result["walls"]["bid"]:
            print(f"\nBid Walls ({len(result['walls']['bid'])}):")
            for w in result["walls"]["bid"][:3]:
                inst = " [INSTITUTIONAL]" if w["is_institutional"] else ""
                print(f"  {w['price']}: {w['lot']:,} lot (strength {w['strength']:.0f}/100){inst}")


def main():
    parser = argparse.ArgumentParser(description="Analyze orderbook structure and patterns")
    parser.add_argument("input", help="Input JSON file with validated orderbook data")
    parser.add_argument("--debug", action="store_true", help="Print detailed analysis")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    try:
        with open(args.input) as f:
            orderbook_data = json.load(f)
        
        analyzer = OrderbookAnalyzer(debug=args.debug)
        result = analyzer.analyze(orderbook_data)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if not args.debug:
                analyzer._print_analysis(result)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
