#!/usr/bin/env python3
"""
Telegram Orderbook Formatter - Caveman + RTK Optimized
Compact, comprehensive output dengan table format

Usage:
  python3.11 telegram_formatter_compact.py analysis_result.json
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List


class CompactTelegramFormatter:
    """Format orderbook analysis untuk Telegram dengan Caveman template"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.template_path = Path(__file__).parent.parent / "templates/telegram_compact.txt"
        
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")
    
    def extract_walls(self, analysis: Dict) -> List[Dict]:
        """Extract bid/ask walls dari analysis"""
        walls = []
        
        # Bid walls
        if "bid_walls" in analysis:
            for wall in analysis["bid_walls"][:3]:  # Top 3 only
                walls.append({
                    "side": "BID",
                    "price": wall.get("price", "N/A"),
                    "lot": f"{wall.get('lot', 0):,}",
                    "strength": wall.get("strength", 0),
                    "institutional": wall.get("institutional", False)
                })
        
        # Ask walls
        if "ask_walls" in analysis:
            for wall in analysis["ask_walls"][:3]:  # Top 3 only
                walls.append({
                    "side": "ASK",
                    "price": wall.get("price", "N/A"),
                    "lot": f"{wall.get('lot', 0):,}",
                    "strength": wall.get("strength", 0),
                    "institutional": wall.get("institutional", False)
                })
        
        return walls
    
    def extract_recommendations(self, recommendations: Dict) -> List[Dict]:
        """Extract entry recommendations"""
        recs = []
        
        tier_map = {
            "aggressive": ("🔴", "AGGRESSIVE"),
            "moderat": ("🟡", "MODERAT"),
            "low_risk": ("🟢", "LOW RISK")
        }
        
        for tier_key, (emoji, tier_name) in tier_map.items():
            if tier_key in recommendations:
                rec = recommendations[tier_key]
                if rec.get("valid", False):
                    recs.append({
                        "emoji": emoji,
                        "tier": tier_name,
                        "entry": rec.get("entry_range", "N/A"),
                        "tp": rec.get("target_price", "N/A"),
                        "sl": rec.get("stop_loss", "N/A"),
                        "rr": f"{rec.get('risk_reward_ratio', 0):.2f}:1"
                    })
        
        return recs
    
    def prepare_data(self, result: Dict) -> Dict:
        """Prepare data untuk Caveman template"""
        ocr_data = result.get("ocr_data", {})
        metadata = result.get("metadata", {})
        analysis = result.get("analysis", {})
        recommendations = result.get("recommendations", {})
        
        # Calculate percentages
        bid_total = sum(b.get("lot", 0) for b in ocr_data.get("bids", []))
        ask_total = sum(a.get("lot", 0) for a in ocr_data.get("asks", []))
        total = bid_total + ask_total
        
        bid_pct = int((bid_total / total * 100) if total > 0 else 0)
        ask_pct = int((ask_total / total * 100) if total > 0 else 0)
        
        # Count frequencies
        bid_freq = sum(b.get("freq", 0) for b in ocr_data.get("bids", []))
        ask_freq = sum(a.get("freq", 0) for a in ocr_data.get("asks", []))
        
        # Imbalance ratio
        imbalance = ask_total / bid_total if bid_total > 0 else 0
        
        # Mode indicator
        mode_map = {
            "fast": "⚡ FAST",
            "hybrid": "🔄 HYBRID",
            "full_fallback": "🛡️ FULL"
        }
        mode = mode_map.get(metadata.get("mode", "unknown"), "UNKNOWN")
        
        # Warnings
        warnings = []
        if metadata.get("manual_verification_required", False):
            warnings.append("Low confidence")
        if imbalance > 2:
            warnings.append("Strong seller pressure")
        elif imbalance < 0.5:
            warnings.append("Strong buyer pressure")
        
        data = {
            "ticker": ocr_data.get("ticker", "N/A"),
            "timestamp": ocr_data.get("timestamp", "N/A"),
            "processing_time": f"{metadata.get('processing_times', {}).get('total', 0):.1f}",
            "confidence": f"{metadata.get('confidence', 0):.0f}",
            "mode": mode,
            "bias": analysis.get("bias", "NEUTRAL"),
            "momentum": int(analysis.get("momentum_score", 0)),
            "imbalance_ratio": f"{imbalance:.2f}",
            "bid_total": f"{bid_total:,}",
            "ask_total": f"{ask_total:,}",
            "bid_freq": f"{bid_freq:,}",
            "ask_freq": f"{ask_freq:,}",
            "bid_pct": bid_pct,
            "ask_pct": ask_pct,
            "walls": self.extract_walls(analysis),
            "recommendations": self.extract_recommendations(recommendations),
            "warnings": warnings,
            "footer": f"Generated {metadata.get('processing_times', {}).get('total', 0):.1f}s"
        }
        
        return data
    
    def format_with_caveman(self, data: Dict) -> str:
        """Format menggunakan Caveman template"""
        try:
            # Save data to temp JSON
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({"d": data}, f)
                data_file = f.name
            
            # Run caveman
            result = subprocess.run(
                ["caveman", str(self.template_path), data_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Cleanup
            Path(data_file).unlink()
            
            if result.returncode != 0:
                if self.debug:
                    print(f"Caveman error: {result.stderr}")
                return self.format_fallback(data)
            
            return result.stdout.strip()
            
        except Exception as e:
            if self.debug:
                print(f"Caveman formatting failed: {e}")
            return self.format_fallback(data)
    
    def format_fallback(self, data: Dict) -> str:
        """Fallback format tanpa Caveman"""
        msg = f"📊 **{data['ticker']}** — {data['timestamp']}\n\n"
        msg += f"⚡ {data['processing_time']}s | 📈 {data['confidence']}% | {data['mode']}\n\n"
        
        msg += f"**Market**\n"
        msg += f"Bias: {data['bias']} | Momentum: {data['momentum']}/100 | Imbalance: {data['imbalance_ratio']}x\n\n"
        
        msg += f"**Orderbook**\n"
        msg += f"| Side | Total | Freq | Ratio |\n"
        msg += f"|------|-------|------|-------|\n"
        msg += f"| BID  | {data['bid_total']} | {data['bid_freq']} | {data['bid_pct']}% |\n"
        msg += f"| ASK  | {data['ask_total']} | {data['ask_freq']} | {data['ask_pct']}% |\n\n"
        
        if data['walls']:
            msg += f"**Walls**\n"
            for wall in data['walls']:
                inst = " [INST]" if wall['institutional'] else ""
                msg += f"{wall['side']} {wall['price']}: {wall['lot']} lot ({wall['strength']}/100){inst}\n"
            msg += "\n"
        
        if data['recommendations']:
            msg += f"**🎯 Entry**\n"
            for rec in data['recommendations']:
                msg += f"{rec['emoji']} **{rec['tier']}** | Entry: {rec['entry']} | TP: {rec['tp']} | SL: {rec['sl']} | R/R: {rec['rr']}\n"
            msg += "\n"
        
        if data['warnings']:
            msg += f"⚠️ {', '.join(data['warnings'])}\n\n"
        
        msg += f"*{data['footer']}*"
        
        return msg
    
    def format(self, result: Dict) -> str:
        """Format analysis result untuk Telegram"""
        # Prepare data
        data = self.prepare_data(result)
        
        # Try Caveman first, fallback to manual format
        try:
            return self.format_with_caveman(data)
        except:
            return self.format_fallback(data)


def main():
    """CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compact Telegram formatter dengan Caveman")
    parser.add_argument("result_json", help="Path to analysis result JSON")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--caveman-only", action="store_true", help="Use Caveman only (fail if not available)")
    
    args = parser.parse_args()
    
    # Load result
    if not Path(args.result_json).exists():
        print(f"Error: File not found: {args.result_json}")
        return 1
    
    with open(args.result_json) as f:
        result = json.load(f)
    
    try:
        formatter = CompactTelegramFormatter(debug=args.debug)
        
        if args.caveman_only:
            # Force Caveman only
            data = formatter.prepare_data(result)
            message = formatter.format_with_caveman(data)
        else:
            # Try Caveman, fallback to manual
            message = formatter.format(result)
        
        print(message)
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
