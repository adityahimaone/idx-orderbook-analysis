#!/usr/bin/env python3
"""
IDX Orderbook Tracker
Phase 5: Delta tracking between snapshots

Track changes between orderbook snapshots:
- Price movement (bid/ask drift)
- Wall appearance/disappearance
- Bid/ask ratio trend
- Volume accumulation rate
- Distribution pattern detection
"""

import sys
import json
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class DeltaChange:
    """Change between two snapshots"""
    metric: str
    prev_value: float
    curr_value: float
    change: float
    change_pct: float
    direction: str  # "increase", "decrease", "stable"
    significance: str  # "low", "medium", "high"


@dataclass
class DistributionPattern:
    """Distribution pattern detection"""
    detected: bool
    confidence: float  # 0-100
    pattern_type: str  # "aggressive", "gradual", "none"
    evidence: List[str]
    time_window_minutes: int


class OrderbookTracker:
    """Track orderbook changes over time"""
    
    # Thresholds for significance
    SIGNIFICANCE_THRESHOLDS = {
        "price_change": 0.02,  # 2%
        "lot_change": 0.3,     # 30%
        "ratio_change": 0.2,   # 20%
        "wall_change": 0.5,    # 50%
    }
    
    # Distribution detection thresholds
    DISTRIBUTION_THRESHOLDS = {
        "ask_growth_rate": 0.5,    # Ask total up > 50% in < 30 min
        "bid_erosion_rate": 0.3,   # Bid total down > 30%
        "wall_thickening": 0.3,    # Wall lot up > 30%
        "avg_price_drift": 0.01,   # Avg price up > 1%
    }
    
    def __init__(self, debug=False):
        self.debug = debug
    
    def compare_snapshots(self, prev: Dict, curr: Dict) -> List[DeltaChange]:
        """
        Compare two orderbook snapshots
        
        Args:
            prev: Previous snapshot data
            curr: Current snapshot data
            
        Returns:
            List of changes with significance
        """
        changes = []
        
        # Compare key metrics
        metrics = [
            ("bid_total", "Bid Total Lot"),
            ("ask_total", "Ask Total Lot"),
            ("imbalance_ratio", "Bid/Ask Ratio"),
            ("avg_price", "Average Price"),
            ("spread_pct", "Spread %"),
            ("momentum_score", "Momentum Score"),
        ]
        
        for metric_key, metric_name in metrics:
            prev_val = prev.get(metric_key, 0)
            curr_val = curr.get(metric_key, 0)
            
            if prev_val == 0:
                continue
            
            change = curr_val - prev_val
            change_pct = (change / prev_val) * 100
            
            direction = "increase" if change > 0 else "decrease" if change < 0 else "stable"
            
            # Determine significance
            threshold = self.SIGNIFICANCE_THRESHOLDS.get(
                metric_key,
                self.SIGNIFICANCE_THRESHOLDS.get("price_change", 0.02)
            )
            
            abs_change_pct = abs(change_pct) / 100  # Convert to decimal
            if abs_change_pct > threshold * 2:
                significance = "high"
            elif abs_change_pct > threshold:
                significance = "medium"
            else:
                significance = "low"
            
            changes.append(DeltaChange(
                metric=metric_name,
                prev_value=prev_val,
                curr_value=curr_val,
                change=change,
                change_pct=change_pct,
                direction=direction,
                significance=significance
            ))
        
        # Compare wall changes
        prev_walls = prev.get("walls", {})
        curr_walls = curr.get("walls", {})
        
        for side in ["bid", "ask"]:
            prev_side_walls = prev_walls.get(side, [])
            curr_side_walls = curr_walls.get(side, [])
            
            if prev_side_walls and curr_side_walls:
                prev_top_wall = prev_side_walls[0]
                curr_top_wall = curr_side_walls[0]
                
                if prev_top_wall.get("price") == curr_top_wall.get("price"):
                    # Same wall, check lot change
                    prev_lot = prev_top_wall.get("lot", 0)
                    curr_lot = curr_top_wall.get("lot", 0)
                    
                    if prev_lot > 0:
                        change_pct = ((curr_lot - prev_lot) / prev_lot) * 100
                        significance = "high" if abs(change_pct) > 30 else "medium" if abs(change_pct) > 15 else "low"
                        
                        changes.append(DeltaChange(
                            metric=f"{side.upper()} Wall Lot",
                            prev_value=prev_lot,
                            curr_value=curr_lot,
                            change=curr_lot - prev_lot,
                            change_pct=change_pct,
                            direction="increase" if change_pct > 0 else "decrease",
                            significance=significance
                        ))
        
        return changes
    
    def detect_distribution(self, snapshots: List[Dict]) -> DistributionPattern:
        """
        Detect distribution pattern from multiple snapshots
        
        Distribution patterns observed in KAEF & IRRA:
        - Ask total increases significantly (+65% IRRA in 23 min)
        - Bid total decreases or stays flat
        - Average price drifts slightly upward
        - Ask walls get thicker
        
        Args:
            snapshots: List of snapshots in chronological order
            
        Returns:
            DistributionPattern with detection result
        """
        if len(snapshots) < 2:
            return DistributionPattern(
                detected=False,
                confidence=0,
                pattern_type="none",
                evidence=["Insufficient data"],
                time_window_minutes=0
            )
        
        # Get first and last snapshot
        first = snapshots[0]
        last = snapshots[-1]
        
        # Calculate time difference
        first_time = first.get("timestamp", "")
        last_time = last.get("timestamp", "")
        
        try:
            if ":" in first_time and ":" in last_time:
                # Parse HH:MM times
                f_h, f_m = map(int, first_time.split(":"))
                l_h, l_m = map(int, last_time.split(":"))
                time_diff_minutes = (l_h * 60 + l_m) - (f_h * 60 + f_m)
            else:
                time_diff_minutes = 30  # Default assumption
        except:
            time_diff_minutes = 30
        
        # Calculate changes
        first_ask_total = first.get("ask_total", 0)
        last_ask_total = last.get("ask_total", 0)
        ask_growth = (last_ask_total - first_ask_total) / first_ask_total if first_ask_total > 0 else 0
        
        first_bid_total = first.get("bid_total", 0)
        last_bid_total = last.get("bid_total", 0)
        bid_erosion = (first_bid_total - last_bid_total) / first_bid_total if first_bid_total > 0 else 0
        
        first_avg = first.get("avg_price", 0)
        last_avg = last.get("avg_price", 0)
        avg_drift = (last_avg - first_avg) / first_avg if first_avg > 0 else 0
        
        # Check thresholds
        evidence = []
        confidence = 0
        
        # Ask growth check
        if ask_growth > self.DISTRIBUTION_THRESHOLDS["ask_growth_rate"]:
            evidence.append(f"Ask total increased {ask_growth:.1%} in {time_diff_minutes}min")
            confidence += 30
        
        # Bid erosion check
        if bid_erosion > self.DISTRIBUTION_THRESHOLDS["bid_erosion_rate"]:
            evidence.append(f"Bid total decreased {bid_erosion:.1%} in {time_diff_minutes}min")
            confidence += 25
        
        # Average price drift check
        if avg_drift > self.DISTRIBUTION_THRESHOLDS["avg_price_drift"]:
            evidence.append(f"Average price drifted up {avg_drift:.1%} (transactions at higher prices)")
            confidence += 20
        
        # Wall thickening check
        first_walls = first.get("walls", {}).get("ask", [])
        last_walls = last.get("walls", {}).get("ask", [])
        
        if first_walls and last_walls:
            first_wall_lot = first_walls[0].get("lot", 0)
            last_wall_lot = last_walls[0].get("lot", 0)
            
            if first_wall_lot > 0:
                wall_growth = (last_wall_lot - first_wall_lot) / first_wall_lot
                if wall_growth > self.DISTRIBUTION_THRESHOLDS["wall_thickening"]:
                    evidence.append(f"Ask wall thickened {wall_growth:.1%}")
                    confidence += 25
        
        # Determine pattern type
        if confidence >= 60:
            pattern_type = "aggressive" if confidence >= 80 else "gradual"
            detected = True
        else:
            pattern_type = "none"
            detected = False
            evidence.append("No clear distribution pattern detected")
        
        return DistributionPattern(
            detected=detected,
            confidence=confidence,
            pattern_type=pattern_type,
            evidence=evidence,
            time_window_minutes=time_diff_minutes
        )
    
    def track(self, snapshots: List[Dict]) -> Dict:
        """
        Track changes across multiple snapshots
        
        Args:
            snapshots: List of snapshots in chronological order
            
        Returns:
            dict with tracking results
        """
        if len(snapshots) < 2:
            return {
                "error": "Need at least 2 snapshots for tracking",
                "changes": [],
                "distribution": None
            }
        
        # Compare consecutive snapshots
        all_changes = []
        for i in range(1, len(snapshots)):
            changes = self.compare_snapshots(snapshots[i-1], snapshots[i])
            all_changes.append({
                "from": snapshots[i-1].get("timestamp"),
                "to": snapshots[i].get("timestamp"),
                "changes": [asdict(c) for c in changes]
            })
        
        # Detect distribution pattern
        distribution = self.detect_distribution(snapshots)
        
        # Calculate trends
        trends = self._calculate_trends(snapshots)
        
        result = {
            "ticker": snapshots[0].get("ticker"),
            "snapshot_count": len(snapshots),
            "time_range": {
                "first": snapshots[0].get("timestamp"),
                "last": snapshots[-1].get("timestamp")
            },
            "changes": all_changes,
            "distribution": asdict(distribution),
            "trends": trends
        }
        
        if self.debug:
            self._print_tracking(result)
        
        return result
    
    def _calculate_trends(self, snapshots: List[Dict]) -> Dict:
        """Calculate overall trends"""
        if len(snapshots) < 2:
            return {}
        
        first = snapshots[0]
        last = snapshots[-1]
        
        # Bid/ask ratio trend
        first_ratio = first.get("imbalance_ratio", 0)
        last_ratio = last.get("imbalance_ratio", 0)
        ratio_trend = "increasing" if last_ratio > first_ratio else "decreasing" if last_ratio < first_ratio else "stable"
        
        # Momentum trend
        first_momentum = first.get("momentum_score", 50)
        last_momentum = last.get("momentum_score", 50)
        momentum_trend = "improving" if last_momentum > first_momentum else "deteriorating" if last_momentum < first_momentum else "stable"
        
        # Volume trend
        first_volume = first.get("bid_total", 0) + first.get("ask_total", 0)
        last_volume = last.get("bid_total", 0) + last.get("ask_total", 0)
        volume_trend = "increasing" if last_volume > first_volume else "decreasing" if last_volume < first_volume else "stable"
        
        return {
            "bid_ask_ratio": ratio_trend,
            "momentum": momentum_trend,
            "total_volume": volume_trend,
            "ratio_change": last_ratio - first_ratio,
            "momentum_change": last_momentum - first_momentum,
            "volume_change_pct": ((last_volume - first_volume) / first_volume * 100) if first_volume > 0 else 0
        }
    
    def _print_tracking(self, result: Dict):
        """Print tracking report"""
        print("\n=== ORDERBOOK TRACKING ===")
        print(f"Ticker: {result['ticker']}")
        print(f"Snapshots: {result['snapshot_count']}")
        print(f"Time range: {result['time_range']['first']} → {result['time_range']['last']}")
        
        # Distribution detection
        dist = result["distribution"]
        if dist["detected"]:
            print(f"\n⚠ DISTRIBUTION DETECTED ({dist['pattern_type'].upper()})")
            print(f"Confidence: {dist['confidence']:.0f}/100")
            for evidence in dist["evidence"]:
                print(f"  • {evidence}")
        else:
            print(f"\n✓ No distribution pattern detected")
        
        # Trends
        trends = result["trends"]
        print(f"\nTrends:")
        print(f"  Bid/Ask Ratio: {trends.get('bid_ask_ratio', 'unknown')} ({trends.get('ratio_change', 0):+.2f})")
        print(f"  Momentum: {trends.get('momentum', 'unknown')} ({trends.get('momentum_change', 0):+.0f} pts)")
        print(f"  Volume: {trends.get('total_volume', 'unknown')} ({trends.get('volume_change_pct', 0):+.1f}%)")
        
        # Recent changes
        if result["changes"]:
            latest = result["changes"][-1]
            print(f"\nLatest changes ({latest['from']} → {latest['to']}):")
            
            for change in latest["changes"]:
                if change["significance"] in ["high", "medium"]:
                    arrow = "↑" if change["direction"] == "increase" else "↓" if change["direction"] == "decrease" else "→"
                    print(f"  {arrow} {change['metric']}: {change['change_pct']:+.1f}% ({change['significance']})")


def main():
    parser = argparse.ArgumentParser(description="Track orderbook changes over time")
    parser.add_argument("snapshots", nargs="+", help="JSON files with snapshot data (chronological order)")
    parser.add_argument("--debug", action="store_true", help="Print detailed tracking")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    try:
        snapshots = []
        for snapshot_file in args.snapshots:
            with open(snapshot_file) as f:
                snapshots.append(json.load(f))
        
        tracker = OrderbookTracker(debug=args.debug)
        result = tracker.track(snapshots)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if not args.debug:
                tracker._print_tracking(result)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
