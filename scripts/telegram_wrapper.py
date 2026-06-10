#!/usr/bin/env python3
"""
Simple Telegram Integration for Orderbook Analysis
Use with Hermes Agent Telegram plugin or manual sending

Usage:
1. Save image to /tmp/orderbook.jpg
2. Run: python3.11 telegram_wrapper.py /tmp/orderbook.jpg
3. Get markdown output ready for Telegram
"""

import sys
import json
import time
from pathlib import Path

# Import fast pipeline
sys.path.insert(0, str(Path(__file__).parent))
from orderbook_pipeline_fast import OrderbookPipelineOptimized


def analyze_for_telegram(image_path: str, fast_mode: bool = True) -> str:
    """
    Analyze orderbook and format for Telegram
    
    Returns: Markdown formatted message ready for Telegram
    """
    start_time = time.time()
    
    # Initialize pipeline
    pipeline = OrderbookPipelineOptimized(debug=False, fast_mode=fast_mode)
    
    try:
        # Run analysis
        result = pipeline.run(
            image_path,
            output_format="markdown"
        )
        
        elapsed = time.time() - start_time
        metadata = result["metadata"]
        ocr_data = result["ocr_data"]
        
        # Extract key info
        ticker = ocr_data.get("ticker", "N/A")
        confidence = metadata.get("confidence", 0)
        processing_time = metadata["processing_times"]["total"]
        
        # Get recommendations
        recommendations = result.get("recommendations", {})
        
        # Format Telegram message
        message = f"📊 **Orderbook Analysis**\n\n"
        message += f"✅ **Ticker:** {ticker}\n"
        message += f"⏱️ **Time:** {processing_time:.2f}s\n"
        message += f"📈 **Confidence:** {confidence:.1f}%\n\n"
        
        # Add summary
        if "analysis" in result:
            analysis = result["analysis"]
            bias = analysis.get("bias", "NEUTRAL")
            momentum = analysis.get("momentum_score", 0)
            
            message += f"**Market Bias:** {bias}\n"
            message += f"**Momentum:** {momentum}/100\n\n"
        
        # Add recommendations
        if recommendations:
            message += "**🎯 Entry Recommendations**\n\n"
            
            for tier in ["low_risk", "moderat", "aggressive"]:
                if tier in recommendations:
                    rec = recommendations[tier]
                    if rec.get("valid", False):
                        entry = rec.get("entry_range", "N/A")
                        rr = rec.get("risk_reward_ratio", "N/A")
                        
                        emoji = "🟢" if tier == "low_risk" else "🟡" if tier == "moderat" else "🔴"
                        message += f"{emoji} **{tier.upper().replace('_', ' ')}**\n"
                        message += f"   Entry: {entry}\n"
                        message += f"   R/R: {rr}\n\n"
        
        # Add validation status
        validation = result.get("validation", {})
        if validation.get("manual_verification_required", False):
            message += "⚠️ **Manual verification recommended**\n"
            message += "   Confidence below threshold\n\n"
        
        # Add full report (truncated)
        full_report = result["formatted_output"]
        if len(full_report) > 1000:
            full_report = full_report[:900] + "\n\n... [truncated]"
        
        message += "**📋 Full Report**\n"
        message += "```\n"
        message += full_report
        message += "\n```"
        
        return message
        
    except Exception as e:
        error_msg = f"❌ **Error analyzing orderbook**\n\n{str(e)}"
        return error_msg


def main():
    """CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram wrapper for orderbook analysis")
    parser.add_argument("image", help="Path to orderbook screenshot")
    parser.add_argument("--fast", action="store_true", default=True, help="Fast mode (default)")
    parser.add_argument("--full", action="store_true", help="Full analysis (slower)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    
    args = parser.parse_args()
    
    # Check file exists
    if not Path(args.image).exists():
        print(f"Error: Image not found: {args.image}")
        return 1
    
    # Run analysis
    if args.json:
        # JSON output
        pipeline = OrderbookPipelineOptimized(debug=False, fast_mode=args.fast)
        result = pipeline.run(args.image, output_format="json")
        print(json.dumps(result, indent=2))
    else:
        # Telegram-formatted markdown
        message = analyze_for_telegram(args.image, fast_mode=args.fast)
        print(message)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
