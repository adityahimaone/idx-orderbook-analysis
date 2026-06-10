#!/usr/bin/env python3
"""
IDX Orderbook Data Validator
Phase 2: Confidence scoring and sanity checks

Validates OCR output against known patterns and rules:
- Price sanity (detect absurd values like 1134118)
- Ticker validation (TACO, 7AS7 misreads)
- Lot spike detection
- ARA/ARB consistency checks
- Confidence threshold enforcement
"""

import sys
import json
import argparse
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict


@dataclass
class ValidationResult:
    """Result of validation check"""
    passed: bool
    rule: str
    message: str
    severity: str  # "error", "warning", "info"
    value: Any = None


class OrderbookValidator:
    """Validate OCR-extracted orderbook data"""
    
    # Configuration
    CONFIDENCE_THRESHOLD = 70  # Below this: flag for manual verification
    
    # Sanity rules
    SANITY_RULES = {
        "price_range": {
            "description": "Price should be within 50%-200% of previous close",
            "check": lambda prev, price: 0.5 * prev <= price <= 2.0 * prev if prev > 0 else True
        },
        "ara_check": {
            "description": "ARA (ask) should be ~125% of previous (±5%)",
            "check": lambda prev, ara: abs(ara - prev * 1.25) < prev * 0.05 if prev > 0 else True
        },
        "arb_check": {
            "description": "ARB (bid) should be ~85% of previous (±5%)",
            "check": lambda prev, arb: abs(arb - prev * 0.85) < prev * 0.05 if prev > 0 else True
        },
        "lot_spike": {
            "description": "No single lot should exceed 10x the 3rd largest lot",
            "check": lambda lots: max(lots) < 10 * sorted(lots, reverse=True)[2] if len(lots) >= 3 else True
        },
        "ticker_valid": {
            "description": "Ticker should be 2-6 uppercase letters",
            "check": lambda t: t.isalpha() and 2 <= len(t) <= 6 and t.isupper()
        },
        "bid_ask_order": {
            "description": "Bid prices should be < Ask prices",
            "check": lambda bids, asks: all(b < a for b in bids for a in asks) if bids and asks else True
        },
        "ara_arb_order": {
            "description": "ARB (bid) should be < ARA (ask)",
            "check": lambda arb, ara: arb < ara
        },
        "open_high_low": {
            "description": "Open should be between High and Low",
            "check": lambda open_p, high, low: low <= open_p <= high
        },
        "high_low_order": {
            "description": "High should be >= Low",
            "check": lambda high, low: high >= low
        },
        "avg_in_range": {
            "description": "Average price should be between Low and High",
            "check": lambda avg, high, low: low <= avg <= high
        }
    }
    
    # Artifact patterns (common OCR misreads)
    ARTIFACT_PATTERNS = {
        "TACO": "TACO",  # Common misread
        "7AS7": "TASS",  # 7 misread as T
        "1AS1": "IASI",  # 1 misread as I
        "0AS0": "OASO",  # 0 misread as O
    }
    
    def __init__(self, debug=False):
        self.debug = debug
        self.validation_log = []
    
    def validate_confidence(self, confidence: float) -> ValidationResult:
        """Check if OCR confidence is acceptable"""
        if confidence < self.CONFIDENCE_THRESHOLD:
            return ValidationResult(
                passed=False,
                rule="confidence_threshold",
                message=f"Confidence {confidence:.1f}% below threshold {self.CONFIDENCE_THRESHOLD}%",
                severity="warning",
                value=confidence
            )
        return ValidationResult(
            passed=True,
            rule="confidence_threshold",
            message=f"Confidence {confidence:.1f}% acceptable",
            severity="info",
            value=confidence
        )
    
    def validate_ticker(self, ticker: str) -> ValidationResult:
        """Validate ticker symbol"""
        # Check if empty or None
        if not ticker or ticker is None:
            return ValidationResult(
                passed=False,
                rule="ticker_missing",
                message="Ticker symbol missing",
                severity="error",
                value=ticker
            )
        
        # Check format (with None safety)
        try:
            if not self.SANITY_RULES["ticker_valid"]["check"](ticker):
                return ValidationResult(
                    passed=False,
                    rule="ticker_format",
                    message=f"Ticker '{ticker}' invalid (must be 2-6 uppercase letters)",
                    severity="error",
                    value=ticker
                )
        except (AttributeError, TypeError):
            return ValidationResult(
                passed=False,
                rule="ticker_format",
                message=f"Ticker '{ticker}' invalid format",
                severity="error",
                value=ticker
            )
        
        return ValidationResult(
            passed=True,
            rule="ticker_valid",
            message=f"Ticker '{ticker}' valid",
            severity="info",
            value=ticker
        )
    
    def validate_prices(self, data: Dict) -> List[ValidationResult]:
        """Validate price fields"""
        results = []
        prev = data.get("prev", 0)
        
        # Check individual prices
        price_fields = {
            "open": data.get("open"),
            "high": data.get("high"),
            "low": data.get("low"),
            "ara": data.get("ara"),
            "arb": data.get("arb"),
            "avg": data.get("avg")
        }
        
        # Detect absurd values (e.g., 1134118 when should be ~1134)
        for field, price in price_fields.items():
            if price is None:
                continue
            
            # Check for obvious OCR errors (price > 100x previous)
            if prev > 0 and price > prev * 100:
                results.append(ValidationResult(
                    passed=False,
                    rule="price_absurd",
                    message=f"{field.upper()} = {price} is absurdly high (prev={prev}), likely OCR error",
                    severity="error",
                    value=price
                ))
                continue
            
            # Check price range
            if prev > 0 and not self.SANITY_RULES["price_range"]["check"](prev, price):
                results.append(ValidationResult(
                    passed=False,
                    rule="price_range",
                    message=f"{field.upper()} = {price} outside reasonable range (50%-200% of prev={prev})",
                    severity="warning",
                    value=price
                ))
        
        # Check ARA/ARB consistency
        ara = data.get("ara")
        arb = data.get("arb")
        if ara and arb:
            if not self.SANITY_RULES["ara_arb_order"]["check"](arb, ara):
                results.append(ValidationResult(
                    passed=False,
                    rule="ara_arb_order",
                    message=f"ARB ({arb}) should be < ARA ({ara})",
                    severity="error",
                    value=(arb, ara)
                ))
        
        # Check open/high/low relationship
        open_p = data.get("open")
        high = data.get("high")
        low = data.get("low")
        if open_p and high and low:
            if not self.SANITY_RULES["open_high_low"]["check"](open_p, high, low):
                results.append(ValidationResult(
                    passed=False,
                    rule="open_high_low",
                    message=f"Open ({open_p}) should be between Low ({low}) and High ({high})",
                    severity="warning",
                    value=(open_p, high, low)
                ))
            
            if not self.SANITY_RULES["high_low_order"]["check"](high, low):
                results.append(ValidationResult(
                    passed=False,
                    rule="high_low_order",
                    message=f"High ({high}) should be >= Low ({low})",
                    severity="error",
                    value=(high, low)
                ))
        
        # Check average in range
        avg = data.get("avg")
        if avg and high and low:
            if not self.SANITY_RULES["avg_in_range"]["check"](avg, high, low):
                results.append(ValidationResult(
                    passed=False,
                    rule="avg_in_range",
                    message=f"Average ({avg}) should be between Low ({low}) and High ({high})",
                    severity="warning",
                    value=(avg, high, low)
                ))
        
        return results
    
    def validate_lots(self, bids: List[Dict], asks: List[Dict]) -> List[ValidationResult]:
        """Validate lot quantities"""
        results = []
        
        # Extract lot values
        bid_lots = [b.get("lot", 0) for b in bids if b.get("lot")]
        ask_lots = [a.get("lot", 0) for a in asks if a.get("lot")]
        all_lots = bid_lots + ask_lots
        
        if len(all_lots) < 3:
            return results
        
        # Check for lot spikes
        sorted_lots = sorted(all_lots, reverse=True)
        max_lot = sorted_lots[0]
        third_largest = sorted_lots[2]
        
        if max_lot > 10 * third_largest:
            results.append(ValidationResult(
                passed=False,
                rule="lot_spike",
                message=f"Max lot ({max_lot}) exceeds 10x the 3rd largest ({third_largest}), possible OCR error",
                severity="warning",
                value=(max_lot, third_largest)
            ))
        
        return results
    
    def validate_orderbook_structure(self, bids: List[Dict], asks: List[Dict]) -> List[ValidationResult]:
        """Validate bid/ask structure"""
        results = []
        
        if not bids:
            results.append(ValidationResult(
                passed=False,
                rule="empty_bids",
                message="No bid levels found",
                severity="error"
            ))
        
        if not asks:
            results.append(ValidationResult(
                passed=False,
                rule="empty_asks",
                message="No ask levels found",
                severity="error"
            ))
        
        # Check bid/ask ordering
        bid_prices = [b.get("price") for b in bids if b.get("price")]
        ask_prices = [a.get("price") for a in asks if a.get("price")]
        
        if bid_prices and ask_prices:
            max_bid = max(bid_prices)
            min_ask = min(ask_prices)
            
            if max_bid >= min_ask:
                results.append(ValidationResult(
                    passed=False,
                    rule="bid_ask_overlap",
                    message=f"Max bid ({max_bid}) >= min ask ({min_ask}), orderbook invalid",
                    severity="error",
                    value=(max_bid, min_ask)
                ))
        
        return results
    
    def validate(self, ocr_data: Dict) -> Dict:
        """
        Full validation pipeline
        
        Args:
            ocr_data: OCR-extracted orderbook data
            
        Returns:
            dict with validation results and overall status
        """
        results = {
            "overall_passed": True,
            "confidence_score": 100,
            "errors": [],
            "warnings": [],
            "info": [],
            "manual_verification_required": False
        }
        
        # Validate confidence
        conf_result = self.validate_confidence(ocr_data.get("confidence", 0))
        self._add_result(results, conf_result)
        
        # Validate ticker
        ticker_result = self.validate_ticker(ocr_data.get("ticker", ""))
        self._add_result(results, ticker_result)
        
        # Validate prices
        price_results = self.validate_prices(ocr_data)
        for result in price_results:
            self._add_result(results, result)
        
        # Validate lots
        bids = ocr_data.get("bids", [])
        asks = ocr_data.get("asks", [])
        lot_results = self.validate_lots(bids, asks)
        for result in lot_results:
            self._add_result(results, result)
        
        # Validate structure
        structure_results = self.validate_orderbook_structure(bids, asks)
        for result in structure_results:
            self._add_result(results, result)
        
        # Determine overall status
        if results["errors"]:
            results["overall_passed"] = False
            results["manual_verification_required"] = True
        
        if results["warnings"]:
            results["confidence_score"] -= len(results["warnings"]) * 5
        
        if ocr_data.get("confidence", 100) < self.CONFIDENCE_THRESHOLD:
            results["manual_verification_required"] = True
        
        results["confidence_score"] = max(0, min(100, results["confidence_score"]))
        
        if self.debug:
            self._print_report(results)
        
        return results
    
    def _add_result(self, results: Dict, validation_result: ValidationResult):
        """Add validation result to results dict"""
        result_dict = asdict(validation_result)
        
        if validation_result.severity == "error":
            results["errors"].append(result_dict)
            results["overall_passed"] = False
        elif validation_result.severity == "warning":
            results["warnings"].append(result_dict)
        else:
            results["info"].append(result_dict)
    
    def _print_report(self, results: Dict):
        """Print validation report"""
        print("\n=== VALIDATION REPORT ===")
        print(f"Overall: {'PASS' if results['overall_passed'] else 'FAIL'}")
        print(f"Confidence Score: {results['confidence_score']}/100")
        print(f"Manual Verification Required: {results['manual_verification_required']}")
        
        if results["errors"]:
            print(f"\nErrors ({len(results['errors'])}):")
            for err in results["errors"]:
                print(f"  ✗ {err['rule']}: {err['message']}")
        
        if results["warnings"]:
            print(f"\nWarnings ({len(results['warnings'])}):")
            for warn in results["warnings"]:
                print(f"  ⚠ {warn['rule']}: {warn['message']}")


def main():
    parser = argparse.ArgumentParser(description="Validate OCR-extracted orderbook data")
    parser.add_argument("input", help="Input JSON file with OCR data")
    parser.add_argument("--debug", action="store_true", help="Print detailed report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    try:
        with open(args.input) as f:
            ocr_data = json.load(f)
        
        validator = OrderbookValidator(debug=args.debug)
        results = validator.validate(ocr_data)
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            if not args.debug:
                validator._print_report(results)
        
        return 0 if results["overall_passed"] else 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
