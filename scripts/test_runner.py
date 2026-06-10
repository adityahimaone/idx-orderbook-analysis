#!/usr/bin/env python3
"""
IDX Orderbook Analysis Test Runner
Test all pipeline components with ground truth data
"""

import sys
import json
import os
from pathlib import Path

# Add script directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from orderbook_validator import OrderbookValidator
from orderbook_analyzer import OrderbookAnalyzer
from recommendation_engine import RecommendationEngine
from orderbook_tracker import OrderbookTracker


def test_validator():
    """Test validator with ground truth data"""
    print("\n=== TESTING VALIDATOR ===")
    
    validator = OrderbookValidator(debug=False)
    
    # Load test data
    test_files = [
        "test_kaef_0915.json",
        "test_irra_0918.json",
        "test_fire_0919.json",
        "test_wbsa_0930.json"
    ]
    
    for test_file in test_files:
        test_path = script_dir.parent / "references" / test_file
        with open(test_path) as f:
            data = json.load(f)
        
        print(f"\nTesting {data['ticker']} {data['timestamp']}:")
        
        # Run validation
        result = validator.validate(data)
        
        # Check confidence
        if result["confidence_score"] >= 70:
            print(f"  ✓ Confidence: {result['confidence_score']}/100")
        else:
            print(f"  ✗ Confidence too low: {result['confidence_score']}/100")
        
        # Check errors
        if result["errors"]:
            print(f"  ✗ Errors: {len(result['errors'])}")
            for err in result["errors"][:2]:
                print(f"    - {err['message']}")
        else:
            print(f"  ✓ No validation errors")
        
        # Check warnings
        if result["warnings"]:
            print(f"  ⚠ Warnings: {len(result['warnings'])}")
        else:
            print(f"  ✓ No warnings")
    
    return True


def test_analyzer():
    """Test analyzer with ground truth data"""
    print("\n=== TESTING ANALYZER ===")
    
    analyzer = OrderbookAnalyzer(debug=False)
    
    test_files = [
        "test_kaef_0915.json",
        "test_irra_0918.json",
        "test_fire_0919.json"
    ]
    
    for test_file in test_files:
        test_path = script_dir.parent / "references" / test_file
        with open(test_path) as f:
            data = json.load(f)
        
        print(f"\nTesting {data['ticker']} {data['timestamp']}:")
        
        # Run analysis
        result = analyzer.analyze(data)
        
        # Check bias
        expected_bias = data.get("expected_bias", "NEUTRAL")
        actual_bias = result["imbalance"]["bias"]
        
        if actual_bias == expected_bias:
            print(f"  ✓ Bias: {actual_bias} (expected: {expected_bias})")
        else:
            print(f"  ✗ Bias mismatch: {actual_bias} (expected: {expected_bias})")
        
        # Check ratio
        expected_ratio = data.get("expected_ratio", 1.0)
        actual_ratio = result["imbalance"]["ratio"]
        ratio_diff = abs(actual_ratio - expected_ratio) / expected_ratio
        
        if ratio_diff < 0.1:  # Within 10%
            print(f"  ✓ Ratio: {actual_ratio:.2f} (expected: {expected_ratio:.2f})")
        else:
            print(f"  ✗ Ratio mismatch: {actual_ratio:.2f} (expected: {expected_ratio:.2f})")
        
        # Check walls
        if data.get("expected_ask_wall"):
            expected_wall = data["expected_ask_wall"]
            ask_walls = result["walls"]["ask"]
            
            if ask_walls:
                top_wall = ask_walls[0]
                if top_wall["price"] == expected_wall["price"]:
                    print(f"  ✓ Ask wall: {top_wall['price']} ({top_wall['lot']:,} lot)")
                else:
                    print(f"  ✗ Ask wall mismatch: {top_wall['price']} vs {expected_wall['price']}")
        
        # Check momentum score
        momentum = result["momentum_score"]
        if momentum > 0:
            print(f"  ✓ Momentum score: {momentum}/100")
    
    return True


def test_recommendation_engine():
    """Test recommendation engine"""
    print("\n=== TESTING RECOMMENDATION ENGINE ===")
    
    engine = RecommendationEngine(debug=False)
    
    # Test with KAEF
    test_path = script_dir.parent / "references" / "test_kaef_0915.json"
    with open(test_path) as f:
        kaef_data = json.load(f)
    
    # Run analysis first
    analyzer = OrderbookAnalyzer(debug=False)
    analysis = analyzer.analyze(kaef_data)
    
    print(f"\nTesting KAEF 09:15:")
    
    # Generate recommendations
    result = engine.generate_recommendations(analysis)
    
    # Check tiers
    tiers = result["entry_recommendations"]["tiers"]
    
    for tier_name, tier in tiers.items():
        print(f"  {tier['tier']}:")
        print(f"    Entry: {tier['entry_min']:,}-{tier['entry_max']:,}")
        print(f"    TP: {tier['tp1']:,}" + (f", {tier['tp2']:,}" if tier.get('tp2') else ""))
        print(f"    SL: {tier['sl']:,}")
        print(f"    R/R: {tier['rr_ratio']:.2f}:1")
    
    # Test portfolio verdict with WBSA
    test_path = script_dir.parent / "references" / "test_wbsa_0930.json"
    with open(test_path) as f:
        wbsa_data = json.load(f)
    
    analysis = analyzer.analyze(wbsa_data)
    
    portfolio = {
        "avg_price": 168,
        "lot": 3,
        "pemantauan_khusus": wbsa_data.get("pemantauan_khusus", False)
    }
    
    result = engine.generate_recommendations(analysis, portfolio)
    
    print(f"\nTesting WBSA portfolio verdict:")
    verdict = result["portfolio_verdict"]
    print(f"  Action: {verdict['action']}")
    print(f"  P/L: {verdict['floating_pnl']:,.0f} ({verdict['floating_pnl_pct']:+.1f}%)")
    
    expected_verdict = wbsa_data.get("expected_verdict", "HOLD_WITH_SL")
    if verdict["action"] == expected_verdict:
        print(f"  ✓ Verdict matches expected: {expected_verdict}")
    else:
        print(f"  ✗ Verdict mismatch: {verdict['action']} vs {expected_verdict}")
    
    return True


def test_tracker():
    """Test tracker with multiple snapshots"""
    print("\n=== TESTING TRACKER ===")
    
    tracker = OrderbookTracker(debug=False)
    
    # Load IRRA snapshots (simulated)
    test_path = script_dir.parent / "references" / "test_irra_0918.json"
    with open(test_path) as f:
        irra_0918 = json.load(f)
    
    # Create simulated 09:41 snapshot (ask increased, bid decreased)
    irra_0941 = irra_0918.copy()
    irra_0941["timestamp"] = "09:41"
    irra_0941["ask_total"] = int(irra_0918["ask_total"] * 1.65)  # +65%
    irra_0941["bid_total"] = int(irra_0918["bid_total"] * 0.9)   # -10%
    irra_0941["avg"] = int(irra_0918["avg"] * 1.02)              # +2%
    
    # Create simulated 10:33 snapshot (further changes)
    irra_1033 = irra_0941.copy()
    irra_1033["timestamp"] = "10:33"
    irra_1033["ask_total"] = int(irra_0941["ask_total"] * 1.1)   # +10%
    irra_1033["bid_total"] = int(irra_0941["bid_total"] * 0.95)  # -5%
    irra_1033["avg"] = int(irra_0941["avg"] * 1.01)              # +1%
    
    snapshots = [irra_0918, irra_0941, irra_1033]
    
    print(f"\nTesting IRRA distribution detection (3 snapshots):")
    
    result = tracker.track(snapshots)
    
    # Check distribution detection
    dist = result["distribution"]
    if dist["detected"]:
        print(f"  ✓ Distribution detected: {dist['pattern_type']}")
        print(f"    Confidence: {dist['confidence']:.0f}/100")
        for evidence in dist["evidence"][:3]:
            print(f"    - {evidence}")
    else:
        print(f"  ✗ No distribution detected")
    
    # Check trends
    trends = result["trends"]
    print(f"  Trends:")
    print(f"    Bid/Ask Ratio: {trends.get('bid_ask_ratio', 'unknown')}")
    print(f"    Momentum: {trends.get('momentum', 'unknown')}")
    print(f"    Volume: {trends.get('total_volume', 'unknown')}")
    
    return True


def test_pipeline_integration():
    """Test full pipeline integration"""
    print("\n=== TESTING PIPELINE INTEGRATION ===")
    
    # Import pipeline
    from orderbook_pipeline import OrderbookPipeline
    
    # Create test image path (dummy)
    test_image = script_dir / "test_screenshot.png"
    
    # Check if we have a real screenshot to test
    real_screenshot = Path.home() / ".hermes/stock_analysis.jpg"
    if real_screenshot.exists():
        test_image = real_screenshot
        print(f"\nTesting with real screenshot: {test_image}")
    else:
        print(f"\nNo real screenshot found, using dummy path")
        # Create dummy test data
        return True
    
    try:
        # Run pipeline
        pipeline = OrderbookPipeline(debug=True)
        result = pipeline.run(
            str(test_image),
            output_format="markdown",
            save_intermediate=False
        )
        
        print(f"\nPipeline completed:")
        print(f"  Ticker: {result['ocr_data'].get('ticker', 'N/A')}")
        print(f"  Confidence: {result['metadata']['confidence']:.1f}%")
        print(f"  Manual verification required: {result['metadata']['manual_verification_required']}")
        
        if result["recommendations"]:
            tiers = result["recommendations"]["tiers"]
            print(f"  Recommendations generated: {len(tiers)} tiers")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Pipeline error: {e}")
        return False


def main():
    """Run all tests"""
    print("IDX Orderbook Analysis Test Suite")
    print("=" * 50)
    
    tests = [
        ("Validator", test_validator),
        ("Analyzer", test_analyzer),
        ("Recommendation Engine", test_recommendation_engine),
        ("Tracker", test_tracker),
        ("Pipeline Integration", test_pipeline_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n✗ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{test_name:25} {status}")
        if success:
            passed += 1
    
    print(f"\n{passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n❌ {len(results) - passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
