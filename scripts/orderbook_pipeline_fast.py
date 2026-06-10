#!/usr/bin/env python3
"""
IDX Orderbook Analysis Pipeline - OPTIMIZED
Fast orchestrator: Screenshot → OCR → Analysis → Recommendations → Report

Optimizations:
- Fast preprocessing (skip rotation detection)
- Parallel processing where possible
- Cache intermediate results
- Reduced image resolution for preprocessing
"""

import sys
import os
import json
import argparse
import time
from pathlib import Path
from typing import Dict, Optional

# Import optimized components
from orderbook_preprocessor_optimized import OrderbookPreprocessorOptimized
from orderbook_validator import OrderbookValidator
from orderbook_analyzer import OrderbookAnalyzer
from recommendation_engine import RecommendationEngine
from orderbook_tracker import OrderbookTracker
from output_formatter import OutputFormatter


class OrderbookPipelineOptimized:
    """Fast orderbook analysis pipeline"""
    
    def __init__(self, debug=False, fast_mode=True):
        self.debug = debug
        self.fast_mode = fast_mode
        
        # Initialize components
        self.preprocessor = OrderbookPreprocessorOptimized(debug=debug, skip_rotation=fast_mode)
        self.validator = OrderbookValidator(debug=debug)
        self.analyzer = OrderbookAnalyzer(debug=debug)
        self.recommendation_engine = RecommendationEngine(debug=debug)
        self.tracker = OrderbookTracker(debug=debug)
        self.formatter = OutputFormatter(debug=debug)
        
        # Cache for repeated analysis
        self.cache = {}
    
    def run_ocr_fast(self, image_path: str) -> Dict:
        """
        Fast OCR extraction using optimized fast OCR
        
        Optimizations:
        - Use fast OCR (1-2s instead of 18s)
        - Skip preprocessing
        - Cache results
        - Fallback to original OCR if needed
        """
        import subprocess
        
        # Check cache
        cache_key = f"ocr_{Path(image_path).stat().st_mtime}"
        if cache_key in self.cache:
            if self.debug:
                print("[CACHE] Using cached OCR result")
            return self.cache[cache_key]
        
        if self.debug:
            print("[1/6] Fast OCR extraction (1-2s)...")
        
        try:
            # Use fast OCR script
            ocr_script = Path(__file__).parent / "orderbook_ocr_fast.py"
            python_path = Path.home() / ".hermes/hermes-agent/venv/bin/python3.11"
            
            # Run fast OCR
            result = subprocess.run(
                [str(python_path), str(ocr_script), image_path, "--json"],
                capture_output=True,
                text=True,
                timeout=10  # Very fast timeout
            )
            
            if result.returncode != 0:
                if self.debug:
                    print(f"Fast OCR failed, falling back to original: {result.stderr}")
                # Fallback to original OCR
                return self.run_ocr_fallback(image_path)
            
            ocr_data = json.loads(result.stdout)
            
            # Cache result
            self.cache[cache_key] = ocr_data
            
            return ocr_data
            
        except Exception as e:
            if self.debug:
                print(f"Fast OCR error: {e}, falling back")
            return self.run_ocr_fallback(image_path)
    
    def run_ocr_fallback(self, image_path: str) -> Dict:
        """Fallback to original OCR if fast OCR fails"""
        import subprocess
        import tempfile
        
        if self.debug:
            print("[FALLBACK] Using original OCR...")
        
        # Fast preprocessing
        preprocessed = self.preprocessor.preprocess(image_path)
        
        # Save preprocessed image to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            import cv2
            cv2.imwrite(tmp.name, preprocessed["full_image"])
            tmp_path = tmp.name
        
        try:
            # Find original orderbook_ocr.py
            ocr_script = Path.home() / ".hermes/skills/finance/stock-orderbook-analysis/scripts/orderbook_ocr.py"
            python_path = Path.home() / ".hermes/hermes-agent/venv/bin/python3.11"
            
            # Run OCR with timeout
            result = subprocess.run(
                [str(python_path), str(ocr_script), tmp_path, "--json", "--engine", "tesseract"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"OCR failed: {result.stderr}")
            
            ocr_data = json.loads(result.stdout)
            
            return ocr_data
            
        finally:
            os.unlink(tmp_path)
    
    def run(self, 
            image_path: str,
            portfolio: Optional[Dict] = None,
            prev_snapshot: Optional[Dict] = None,
            output_format: str = "markdown",
            save_intermediate: bool = False) -> Dict:
        """
        Fast pipeline execution
        
        Target: < 60 seconds total
        """
        total_start = time.time()
        
        if self.debug:
            print(f"=== FAST ORDERBOOK ANALYSIS ===")
            print(f"Input: {image_path}")
            print(f"Fast mode: {self.fast_mode}")
        
        # Phase 1: OCR Extraction
        ocr_start = time.time()
        ocr_data = self.run_ocr_fast(image_path)
        ocr_time = time.time() - ocr_start
        
        if self.debug:
            print(f"[1/6] OCR: {ocr_time:.2f}s")
        
        # Phase 2: Validation
        val_start = time.time()
        validation = self.validator.validate(ocr_data)
        val_time = time.time() - val_start
        
        if self.debug:
            print(f"[2/6] Validation: {val_time:.2f}s")
        
        # Phase 3: Analysis
        ana_start = time.time()
        
        # Prepare data for analyzer
        analyzer_input = {
            **ocr_data,
            "bid_total": sum(b.get("lot", 0) for b in ocr_data.get("bids", [])),
            "ask_total": sum(a.get("lot", 0) for a in ocr_data.get("asks", [])),
        }
        
        analysis = self.analyzer.analyze(analyzer_input)
        ana_time = time.time() - ana_start
        
        if self.debug:
            print(f"[3/6] Analysis: {ana_time:.2f}s")
        
        # Phase 4: Recommendations
        rec_start = time.time()
        
        # Prepare data for recommendation engine
        recommendation_input = {
            **analysis,
            "arb": ocr_data.get("arb", 0),
            "ara": ocr_data.get("ara", 0),
            "avg": ocr_data.get("avg", 0),
            "iep": ocr_data.get("iep", 0),
        }
        
        recommendations = self.recommendation_engine.generate_recommendations(
            recommendation_input,
            portfolio
        )
        rec_time = time.time() - rec_start
        
        if self.debug:
            print(f"[4/6] Recommendations: {rec_time:.2f}s")
        
        # Phase 5: Tracking (optional)
        tracking = None
        if prev_snapshot:
            track_start = time.time()
            
            current_snapshot = {
                **analyzer_input,
                **analysis,
                "timestamp": ocr_data.get("timestamp"),
                "ticker": ocr_data.get("ticker"),
            }
            
            tracking = self.tracker.track([prev_snapshot, current_snapshot])
            track_time = time.time() - track_start
            
            if self.debug:
                print(f"[5/6] Tracking: {track_time:.2f}s")
        
        # Phase 6: Formatting
        fmt_start = time.time()
        
        # Compile result
        result = {
            "ocr_data": ocr_data,
            "validation": validation,
            "analysis": analysis,
            "recommendations": recommendations.get("entry_recommendations", {}),
            "portfolio_verdict": recommendations.get("portfolio_verdict"),
            "tracking": tracking,
            "metadata": {
                "image_path": image_path,
                "confidence": ocr_data.get("confidence", 0),
                "manual_verification_required": validation.get("manual_verification_required", False),
                "processing_times": {
                    "ocr": ocr_time,
                    "validation": val_time,
                    "analysis": ana_time,
                    "recommendations": rec_time,
                    "total": time.time() - total_start
                }
            }
        }
        
        # Format output
        if output_format == "markdown":
            formatted_output = self.formatter.format_full_report(result)
        else:
            formatted_output = json.dumps(result, indent=2)
        
        result["formatted_output"] = formatted_output
        fmt_time = time.time() - fmt_start
        
        if self.debug:
            total_time = time.time() - total_start
            print(f"[6/6] Formatting: {fmt_time:.2f}s")
            print(f"[DONE] Total: {total_time:.2f}s")
            print(f"Ticker: {ocr_data.get('ticker', 'N/A')}")
            print(f"Confidence: {ocr_data.get('confidence', 0):.1f}%")
        
        return result


def main():
    parser = argparse.ArgumentParser(
        description="Fast IDX orderbook analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fast analysis (skip rotation detection)
  python3.11 orderbook_pipeline_fast.py screenshot.png --fast
  
  # Normal analysis
  python3.11 orderbook_pipeline_fast.py screenshot.png
  
  # With portfolio
  python3.11 orderbook_pipeline_fast.py screenshot.png --portfolio portfolio.json
  
  # JSON output
  python3.11 orderbook_pipeline_fast.py screenshot.png --format json --output result.json
        """
    )
    
    parser.add_argument("image", help="Path to orderbook screenshot")
    parser.add_argument("--portfolio", help="Portfolio JSON file {avg_price, lot, pemantauan_khusus}")
    parser.add_argument("--prev-snapshot", help="Previous snapshot JSON for delta tracking")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Output file (default: stdout)")
    parser.add_argument("--fast", action="store_true", help="Fast mode (skip rotation detection)")
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    
    args = parser.parse_args()
    
    try:
        # Load portfolio if provided
        portfolio = None
        if args.portfolio:
            with open(args.portfolio) as f:
                portfolio = json.load(f)
        
        # Load previous snapshot if provided
        prev_snapshot = None
        if args.prev_snapshot:
            with open(args.prev_snapshot) as f:
                prev_snapshot = json.load(f)
        
        # Run fast pipeline
        pipeline = OrderbookPipelineOptimized(debug=args.debug, fast_mode=args.fast)
        result = pipeline.run(
            args.image,
            portfolio=portfolio,
            prev_snapshot=prev_snapshot,
            output_format=args.format
        )
        
        # Output
        formatted_output = result["formatted_output"]
        
        if args.output:
            with open(args.output, "w") as f:
                f.write(formatted_output)
            
            # Also save timing info
            timing_file = Path(args.output).with_suffix(".timing.json")
            with open(timing_file, "w") as f:
                json.dump(result["metadata"]["processing_times"], f, indent=2)
            
            print(f"Report saved to: {args.output}")
            print(f"Timing info: {timing_file}")
            
            # Print summary
            times = result["metadata"]["processing_times"]
            print(f"\nProcessing times:")
            for phase, t in times.items():
                if phase != "total":
                    print(f"  {phase}: {t:.2f}s")
            print(f"  TOTAL: {times['total']:.2f}s")
            
        else:
            print(formatted_output)
        
        # Exit code based on validation
        if result["metadata"]["manual_verification_required"]:
            return 2
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
