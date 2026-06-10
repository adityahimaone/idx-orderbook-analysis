#!/usr/bin/env python3
"""
IDX Orderbook Analysis Pipeline
Complete orchestrator: Screenshot → OCR → Analysis → Recommendations → Report

Usage:
    python3.11 orderbook_pipeline.py screenshot.png
    python3.11 orderbook_pipeline.py screenshot.png --portfolio portfolio.json
    python3.11 orderbook_pipeline.py screenshot.png --prev-snapshot prev.json
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, Optional

# Import all pipeline components
from orderbook_preprocessor import OrderbookPreprocessor
from orderbook_validator import OrderbookValidator
from orderbook_analyzer import OrderbookAnalyzer
from recommendation_engine import RecommendationEngine
from orderbook_tracker import OrderbookTracker
from output_formatter import OutputFormatter


class OrderbookPipeline:
    """Complete orderbook analysis pipeline"""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.preprocessor = OrderbookPreprocessor(debug=debug)
        self.validator = OrderbookValidator(debug=debug)
        self.analyzer = OrderbookAnalyzer(debug=debug)
        self.recommendation_engine = RecommendationEngine(debug=debug)
        self.tracker = OrderbookTracker(debug=debug)
        self.formatter = OutputFormatter(debug=debug)
    
    def run(self, 
            image_path: str,
            portfolio: Optional[Dict] = None,
            prev_snapshot: Optional[Dict] = None,
            output_format: str = "markdown",
            save_intermediate: bool = False) -> Dict:
        """
        Run complete pipeline
        
        Args:
            image_path: Path to orderbook screenshot
            portfolio: Optional portfolio data {avg_price, lot, pemantauan_khusus}
            prev_snapshot: Optional previous snapshot for delta tracking
            output_format: "markdown" or "json"
            save_intermediate: Save intermediate results to files
            
        Returns:
            dict with all pipeline results
        """
        if self.debug:
            print(f"=== ORDERBOOK ANALYSIS PIPELINE ===")
            print(f"Input: {image_path}")
        
        # Phase 1: Preprocessing
        if self.debug:
            print("\n[1/6] Preprocessing image...")
        
        preprocessed = self.preprocessor.preprocess(image_path)
        
        if save_intermediate:
            import cv2
            output_dir = Path(image_path).parent / "pipeline_output"
            output_dir.mkdir(exist_ok=True)
            cv2.imwrite(str(output_dir / "01_preprocessed.png"), preprocessed["full_image"])
        
        # Phase 2: OCR Extraction
        if self.debug:
            print("[2/6] Running OCR extraction...")
        
        # Use existing orderbook_ocr.py from stock-orderbook-analysis
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            import cv2
            cv2.imwrite(tmp.name, preprocessed["full_image"])
            tmp_path = tmp.name
        
        try:
            # Find orderbook_ocr.py from stock-orderbook-analysis skill
            ocr_script = Path.home() / ".hermes/skills/finance/stock-orderbook-analysis/scripts/orderbook_ocr.py"
            if not ocr_script.exists():
                raise FileNotFoundError(f"OCR script not found: {ocr_script}")
            
            python_path = Path.home() / ".hermes/hermes-agent/venv/bin/python3.11"
            
            result = subprocess.run(
                [str(python_path), str(ocr_script), tmp_path, "--json", "--engine", "tesseract"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"OCR failed: {result.stderr}")
            
            ocr_data = json.loads(result.stdout)
            
        finally:
            os.unlink(tmp_path)
        
        if save_intermediate:
            with open(output_dir / "02_ocr_data.json", "w") as f:
                json.dump(ocr_data, f, indent=2)
        
        # Phase 3: Validation
        if self.debug:
            print("[3/6] Validating OCR data...")
        
        validation = self.validator.validate(ocr_data)
        
        if save_intermediate:
            with open(output_dir / "03_validation.json", "w") as f:
                json.dump(validation, f, indent=2)
        
        # Phase 4: Analysis
        if self.debug:
            print("[4/6] Analyzing orderbook structure...")
        
        # Prepare data for analyzer
        analyzer_input = {
            **ocr_data,
            "bid_total": sum(b.get("lot", 0) for b in ocr_data.get("bids", [])),
            "ask_total": sum(a.get("lot", 0) for a in ocr_data.get("asks", [])),
        }
        
        analysis = self.analyzer.analyze(analyzer_input)
        
        if save_intermediate:
            with open(output_dir / "04_analysis.json", "w") as f:
                json.dump(analysis, f, indent=2)
        
        # Phase 5: Recommendations
        if self.debug:
            print("[5/6] Generating recommendations...")
        
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
        
        if save_intermediate:
            with open(output_dir / "05_recommendations.json", "w") as f:
                json.dump(recommendations, f, indent=2)
        
        # Phase 6: Tracking (if prev_snapshot provided)
        tracking = None
        if prev_snapshot:
            if self.debug:
                print("[6/6] Tracking changes from previous snapshot...")
            
            current_snapshot = {
                **analyzer_input,
                **analysis,
                "timestamp": ocr_data.get("timestamp"),
                "ticker": ocr_data.get("ticker"),
            }
            
            tracking = self.tracker.track([prev_snapshot, current_snapshot])
            
            if save_intermediate:
                with open(output_dir / "06_tracking.json", "w") as f:
                    json.dump(tracking, f, indent=2)
        
        # Compile final result
        result = {
            "ocr_data": ocr_data,
            "validation": validation,
            "analysis": analysis,
            "recommendations": recommendations.get("entry_recommendations", {}),
            "portfolio_verdict": recommendations.get("portfolio_verdict"),
            "tracking": tracking,
            "metadata": {
                "image_path": image_path,
                "preprocessing_steps": preprocessed["metadata"]["preprocessing_steps"],
                "confidence": ocr_data.get("confidence", 0),
                "manual_verification_required": validation.get("manual_verification_required", False)
            }
        }
        
        # Format output
        if self.debug:
            print("\n[DONE] Formatting output...")
        
        if output_format == "markdown":
            formatted_output = self.formatter.format_full_report(result)
        else:
            formatted_output = self.formatter.format_json(result)
        
        result["formatted_output"] = formatted_output
        
        return result


def main():
    parser = argparse.ArgumentParser(
        description="Complete IDX orderbook analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  python3.11 orderbook_pipeline.py screenshot.png
  
  # With portfolio position
  python3.11 orderbook_pipeline.py screenshot.png --portfolio portfolio.json
  
  # With delta tracking
  python3.11 orderbook_pipeline.py screenshot.png --prev-snapshot prev.json
  
  # Save all intermediate results
  python3.11 orderbook_pipeline.py screenshot.png --save-intermediate
  
  # JSON output
  python3.11 orderbook_pipeline.py screenshot.png --format json
        """
    )
    
    parser.add_argument("image", help="Path to orderbook screenshot")
    parser.add_argument("--portfolio", help="Portfolio JSON file {avg_price, lot, pemantauan_khusus}")
    parser.add_argument("--prev-snapshot", help="Previous snapshot JSON for delta tracking")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    parser.add_argument("--output", help="Output file (default: stdout)")
    parser.add_argument("--save-intermediate", action="store_true", help="Save intermediate results")
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
        
        # Run pipeline
        pipeline = OrderbookPipeline(debug=args.debug)
        result = pipeline.run(
            args.image,
            portfolio=portfolio,
            prev_snapshot=prev_snapshot,
            output_format=args.format,
            save_intermediate=args.save_intermediate
        )
        
        # Output
        formatted_output = result["formatted_output"]
        
        if args.output:
            with open(args.output, "w") as f:
                f.write(formatted_output)
            print(f"Report saved to: {args.output}")
            
            # Also save full result as JSON
            json_output = Path(args.output).with_suffix(".json")
            with open(json_output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Full result saved to: {json_output}")
        else:
            print(formatted_output)
        
        # Exit code based on validation
        if result["metadata"]["manual_verification_required"]:
            return 2  # Warning: manual verification needed
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
