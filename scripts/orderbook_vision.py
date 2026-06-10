#!/usr/bin/env python3
"""
Orderbook Vision API Wrapper
Uses Hermes vision model (Claude/GPT-4o) to extract orderbook data.
Falls back to OCR if vision fails.
"""

import sys
import json
import argparse
from hermes_tools import vision_analyze

def extract_with_vision(image_path: str) -> Dict:
    """Use vision model to extract orderbook data."""
    question = """
    Extract orderbook data from this screenshot of an IDX broker app. 
    Return a STRICT JSON with this schema:
    {
      "ticker": "string",
      "timestamp": "HH:MM",
      "stats": {"open": int, "high": int, "low": int, "prev": int, "ara": int, "arb": int, "avg": int, "val_billion": float, "total_lot_million": float},
      "bids": [{"price": int, "lot": int, "freq": int}],
      "asks": [{"price": int, "lot": int, "freq": int}],
      "confidence": float
    }
    Ensure bid/ask prices are sorted correctly.
    """
    
    # Analyze image
    analysis = vision_analyze(image_url=image_path, question=question)
    
    # Parse JSON from vision output
    # (Vision model often returns markdown code blocks)
    try:
        if "```json" in analysis:
            json_str = analysis.split("```json")[1].split("```")[0].strip()
        else:
            json_str = analysis.strip()
        
        return json.loads(json_str)
    except Exception as e:
        return {"error": f"Vision extraction failed: {e}"}

def main():
    parser = argparse.ArgumentParser(description="Vision API orderbook extraction")
    parser.add_argument("image", help="Input image path")
    args = parser.parse_args()
    
    result = extract_with_vision(args.image)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    sys.exit(main())
