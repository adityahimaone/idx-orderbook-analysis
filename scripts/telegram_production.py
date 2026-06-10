#!/usr/bin/env python3
"""
Telegram Orderbook Analysis - Production Ready
Hybrid approach: Fast OCR first, fallback if confidence < 70%

Usage with Hermes Telegram plugin:
1. Save image to /tmp/orderbook.jpg
2. Run: python3.11 telegram_production.py /tmp/orderbook.jpg
3. Send output to Telegram via send_message
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Optional

# Add skill scripts to path
sys.path.insert(0, str(Path(__file__).parent))
from orderbook_pipeline_fast import OrderbookPipelineOptimized


class TelegramOrderbookAnalyzer:
    """Production-ready orderbook analyzer for Telegram"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        
        # Initialize pipelines
        self.fast_pipeline = OrderbookPipelineOptimized(debug=debug, fast_mode=True)
        self.full_pipeline = OrderbookPipelineOptimized(debug=debug, fast_mode=False)
        
        print(f"Telegram Orderbook Analyzer initialized")
        print(f"Mode: Hybrid (fast first, fallback if confidence < 70%)")
    
    def analyze_hybrid(self, image_path: str) -> Dict:
        """
        Hybrid analysis: fast OCR first, fallback if needed
        
        Returns: {
            "result": analysis_result,
            "mode": "fast" | "full" | "hybrid",
            "processing_time": total_time,
            "confidence": confidence_score,
            "recommendation": user_message
        }
        """
        start_time = time.time()
        
        print(f"[1/2] Running fast OCR...")
        fast_start = time.time()
        
        try:
            # Try fast OCR first
            fast_result = self.fast_pipeline.run(
                image_path,
                output_format="markdown"
            )
            
            fast_time = time.time() - fast_start
            fast_confidence = fast_result["metadata"].get("confidence", 0)
            
            print(f"[1/2] Fast OCR completed: {fast_time:.2f}s, confidence: {fast_confidence:.1f}%")
            
            # Check if we need fallback
            if fast_confidence >= 70:
                total_time = time.time() - start_time
                
                return {
                    "result": fast_result,
                    "mode": "fast",
                    "processing_time": total_time,
                    "confidence": fast_confidence,
                    "recommendation": f"✅ Fast analysis (confidence: {fast_confidence:.1f}%)"
                }
            
            # Fallback to full OCR
            print(f"[2/2] Confidence low ({fast_confidence:.1f}%), falling back to full OCR...")
            fallback_start = time.time()
            
            full_result = self.full_pipeline.run(
                image_path,
                output_format="markdown"
            )
            
            fallback_time = time.time() - fallback_start
            full_confidence = full_result["metadata"].get("confidence", 0)
            
            total_time = time.time() - start_time
            
            print(f"[2/2] Full OCR completed: {fallback_time:.2f}s, confidence: {full_confidence:.1f}%")
            print(f"[DONE] Total time: {total_time:.2f}s")
            
            return {
                "result": full_result,
                "mode": "hybrid",
                "processing_time": total_time,
                "confidence": full_confidence,
                "recommendation": f"🔄 Hybrid analysis (fast: {fast_time:.1f}s + full: {fallback_time:.1f}s)"
            }
            
        except Exception as e:
            print(f"Error in hybrid analysis: {e}")
            
            # Try direct full OCR as last resort
            try:
                print("[FALLBACK] Trying direct full OCR...")
                full_result = self.full_pipeline.run(
                    image_path,
                    output_format="markdown"
                )
                
                total_time = time.time() - start_time
                confidence = full_result["metadata"].get("confidence", 0)
                
                return {
                    "result": full_result,
                    "mode": "full_fallback",
                    "processing_time": total_time,
                    "confidence": confidence,
                    "recommendation": f"⚠️ Direct full OCR (error in fast mode)"
                }
                
            except Exception as e2:
                raise RuntimeError(f"Both fast and full OCR failed: {e2}")
    
    def format_for_telegram(self, analysis_result: Dict) -> str:
        """
        Format analysis result for Telegram
        
        Returns: Markdown formatted message
        """
        result = analysis_result["result"]
        mode = analysis_result["mode"]
        processing_time = analysis_result["processing_time"]
        confidence = analysis_result["confidence"]
        
        ocr_data = result["ocr_data"]
        metadata = result["metadata"]
        recommendations = result.get("recommendations", {})
        
        # Extract key info
        ticker = ocr_data.get("ticker", "N/A")
        engine_used = ocr_data.get("engine_used", "N/A")
        
        # Build Telegram message
        message = f"📊 **Orderbook Analysis**\n\n"
        
        # Mode indicator
        if mode == "fast":
            message += f"⚡ **Mode:** Fast OCR ({processing_time:.1f}s)\n"
        elif mode == "hybrid":
            message += f"🔄 **Mode:** Hybrid (fast + fallback, {processing_time:.1f}s)\n"
        else:
            message += f"🛡️ **Mode:** Full OCR ({processing_time:.1f}s)\n"
        
        # Key metrics
        message += f"✅ **Ticker:** {ticker}\n"
        message += f"📈 **Confidence:** {confidence:.1f}%\n"
        message += f"⚙️ **Engine:** {engine_used}\n\n"
        
        # Validation status
        validation = result.get("validation", {})
        if validation.get("manual_verification_required", False):
            message += f"⚠️ **Manual verification recommended**\n"
            message += f"   Confidence below 70% threshold\n\n"
        
        # Speed comparison
        if processing_time < 5:
            message += f"⚡ **Speed:** Excellent (< 5s)\n"
        elif processing_time < 10:
            message += f"⚡ **Speed:** Good (< 10s)\n"
        elif processing_time < 20:
            message += f"⚡ **Speed:** Moderate (< 20s)\n"
        else:
            message += f"⚡ **Speed:** Slow (> 20s)\n"
        
        message += f"⏱️ **Processing:** {processing_time:.1f}s\n\n"
        
        # Quick summary
        if "analysis" in result:
            analysis = result["analysis"]
            bias = analysis.get("bias", "NEUTRAL")
            momentum = analysis.get("momentum_score", 0)
            
            message += f"**Market Bias:** {bias}\n"
            message += f"**Momentum:** {momentum}/100\n\n"
        
        # Entry recommendations (if any valid)
        valid_recommendations = []
        for tier in ["low_risk", "moderat", "aggressive"]:
            if tier in recommendations:
                rec = recommendations[tier]
                if rec.get("valid", False):
                    valid_recommendations.append((tier, rec))
        
        if valid_recommendations:
            message += "**🎯 Valid Entry Recommendations**\n\n"
            
            for tier, rec in valid_recommendations:
                entry = rec.get("entry_range", "N/A")
                rr = rec.get("risk_reward_ratio", "N/A")
                
                emoji = "🟢" if tier == "low_risk" else "🟡" if tier == "moderat" else "🔴"
                tier_name = tier.upper().replace('_', ' ')
                
                message += f"{emoji} **{tier_name}**\n"
                message += f"   Entry: {entry}\n"
                message += f"   R/R: {rr}\n\n"
        else:
            message += "**🎯 No valid entry recommendations**\n"
            message += "   Market conditions not favorable\n\n"
        
        # Full report link (truncated)
        full_report = result["formatted_output"]
        if len(full_report) > 800:
            full_report = full_report[:700] + "\n\n... [report truncated]"
        
        message += "**📋 Report Summary**\n"
        message += "```\n"
        message += full_report[:300]  # First 300 chars
        message += "\n```\n\n"
        
        # Footer
        message += f"*Generated by IDX Orderbook Analysis • {time.strftime('%Y-%m-%d %H:%M')}*"
        
        return message
    
    def analyze_and_format(self, image_path: str) -> str:
        """
        Complete pipeline: analyze + format for Telegram
        
        Returns: Telegram-ready markdown message
        """
        print(f"Starting analysis of: {image_path}")
        
        # Run hybrid analysis
        analysis_result = self.analyze_hybrid(image_path)
        
        # Format for Telegram
        telegram_message = self.format_for_telegram(analysis_result)
        
        print(f"Analysis completed in {analysis_result['processing_time']:.2f}s")
        print(f"Confidence: {analysis_result['confidence']:.1f}%")
        print(f"Mode: {analysis_result['mode']}")
        
        return telegram_message


def main():
    """CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram orderbook analyzer (production)")
    parser.add_argument("image", help="Path to orderbook screenshot")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    
    args = parser.parse_args()
    
    # Check file exists
    if not Path(args.image).exists():
        print(f"Error: Image not found: {args.image}")
        return 1
    
    try:
        # Initialize analyzer
        analyzer = TelegramOrderbookAnalyzer(debug=args.debug)
        
        if args.json:
            # JSON output
            result = analyzer.analyze_hybrid(args.image)
            print(json.dumps(result, indent=2))
        else:
            # Telegram-formatted markdown
            message = analyzer.analyze_and_format(args.image)
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
