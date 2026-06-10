#!/usr/bin/env python3
"""
Fast OCR for IDX Orderbook Screenshots
Optimized for speed: < 10 seconds target

Optimizations:
- Reduce image resolution (max 1200px width)
- Skip unnecessary preprocessing
- Focus OCR on orderbook region only
- Parallel header + orderbook OCR
"""

import sys
import cv2
import numpy as np
import json
import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


class FastOrderbookOCR:
    """Ultra-fast OCR for orderbook screenshots"""
    
    def __init__(self, debug=False, max_width=1200):
        self.debug = debug
        self.max_width = max_width
        
        if not HAS_TESSERACT:
            raise ImportError("pytesseract not installed")
    
    def resize_for_speed(self, img):
        """Reduce resolution for faster OCR"""
        h, w = img.shape[:2]
        
        if w > self.max_width:
            scale = self.max_width / w
            new_w = self.max_width
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            if self.debug:
                print(f"Resized: {w}x{h} → {new_w}x{new_h} (scale {scale:.2f})")
        
        return img
    
    def quick_preprocess(self, img):
        """Minimal preprocessing for speed"""
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Check if dark mode
        avg_brightness = np.mean(gray)
        if avg_brightness < 100:
            gray = cv2.bitwise_not(gray)
        
        # Simple threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def split_regions(self, img):
        """Split header and orderbook regions"""
        h, w = img.shape[:2]
        
        # Header: top 18%
        header_h = int(h * 0.18)
        header = img[0:header_h, :]
        
        # Orderbook: remaining
        orderbook = img[header_h:, :]
        
        return header, orderbook
    
    def extract_header_stats(self, full_img) -> Dict:
        """Fast header extraction with improved parsing from full image"""
        import re
        
        # Preprocess full image
        gray = cv2.cvtColor(full_img, cv2.COLOR_BGR2GRAY) if len(full_img.shape) == 3 else full_img
        
        # Check if dark mode
        avg_brightness = np.mean(gray)
        if avg_brightness < 100:
            gray = cv2.bitwise_not(gray)
        
        # Simple threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # OCR with PSM 3 for better structure detection
        text = pytesseract.image_to_string(
            binary,
            config='--psm 3 --oem 3'
        )
        
        if self.debug:
            print(f"Full OCR text:\n{text[:300]}")
        
        # Parse key stats
        stats = {
            "ticker": None,
            "timestamp": None,
            "prev": 0,
            "open": 0,
            "high": 0,
            "low": 0,
            "ara": 0,
            "arb": 0,
            "avg": 0,
            "val": 0,
            "lot": 0
        }
        
        lines = text.strip().split('\n')
        
        # Improved ticker detection from full text
        # Look for pattern: "< TICKER" or "TICKER" near beginning
        ticker_pattern = r'<[^>]*?([A-Z]{4,5})|([A-Z]{4,5})\s+[A-Z]'
        match = re.search(ticker_pattern, text.upper())
        if match:
            candidate = match.group(1) or match.group(2)
            # Validate: not common OCR artifacts
            if candidate and candidate not in ['PREV', 'OPEN', 'HIGH', 'LOWW', 'AVGG', 'VALL', 'KEYSTATS', 'ORDERBOOK']:
                stats["ticker"] = candidate
                if self.debug:
                    print(f"Ticker detected: {candidate}")
        
        # Improved timestamp detection (HH:MM format)
        time_pattern = r'\b(\d{1,2}):(\d{2})\b'
        for line in lines:
            match = re.search(time_pattern, line)
            if match:
                hour, minute = match.groups()
                # Validate: reasonable time range (00:00 - 23:59)
                if 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59:
                    stats["timestamp"] = f"{hour.zfill(2)}:{minute}"
                    if self.debug:
                        print(f"Timestamp detected: {stats['timestamp']}")
                    break
        
        # Improved number extraction with context
        for line in lines:
            line_upper = line.upper()
            
            # Extract all numbers from line (including with commas and suffixes like M, B, K)
            numbers = re.findall(r'[\d,]+(?:\.\d+)?[MBK]?', line)
            if not numbers:
                continue
            
            # Clean numbers (remove commas, handle suffixes)
            clean_numbers = []
            for num in numbers:
                clean = num.replace(',', '')
                
                # Handle suffixes
                multiplier = 1
                if clean.endswith('M'):
                    multiplier = 1_000_000
                    clean = clean[:-1]
                elif clean.endswith('B'):
                    multiplier = 1_000_000_000
                    clean = clean[:-1]
                elif clean.endswith('K'):
                    multiplier = 1_000
                    clean = clean[:-1]
                
                try:
                    val = float(clean) * multiplier
                    clean_numbers.append(int(val))
                except:
                    pass
            
            if not clean_numbers:
                continue
            
            # Try to parse based on keywords
            if 'PREV' in line_upper and not stats["prev"]:
                try:
                    stats["prev"] = clean_numbers[0]
                    if self.debug:
                        print(f"Prev: {stats['prev']}")
                except:
                    pass
            
            elif 'OPEN' in line_upper and not stats["open"]:
                try:
                    stats["open"] = clean_numbers[0]
                    if self.debug:
                        print(f"Open: {stats['open']}")
                except:
                    pass
            
            elif 'HIGH' in line_upper and not stats["high"]:
                try:
                    stats["high"] = clean_numbers[0]
                    if self.debug:
                        print(f"High: {stats['high']}")
                except:
                    pass
            
            elif 'LOW' in line_upper and not stats["low"]:
                try:
                    stats["low"] = clean_numbers[0]
                    if self.debug:
                        print(f"Low: {stats['low']}")
                except:
                    pass
            
            elif 'ARA' in line_upper and not stats["ara"]:
                try:
                    stats["ara"] = clean_numbers[0]
                    if self.debug:
                        print(f"ARA: {stats['ara']}")
                except:
                    pass
            
            elif 'ARB' in line_upper and not stats["arb"]:
                try:
                    stats["arb"] = clean_numbers[0]
                    if self.debug:
                        print(f"ARB: {stats['arb']}")
                except:
                    pass
            
            elif 'AVG' in line_upper and not stats["avg"]:
                try:
                    stats["avg"] = clean_numbers[0]
                    if self.debug:
                        print(f"Avg: {stats['avg']}")
                except:
                    pass
            
            elif 'VAL' in line_upper and not stats["val"]:
                try:
                    stats["val"] = clean_numbers[0]
                    if self.debug:
                        print(f"Val: {stats['val']}")
                except:
                    pass
            
            elif 'LOT' in line_upper and not stats["lot"]:
                try:
                    stats["lot"] = clean_numbers[0]
                    if self.debug:
                        print(f"Lot: {stats['lot']}")
                except:
                    pass
        
        return stats
    
    def extract_orderbook_table(self, orderbook_img) -> Tuple[List[Dict], List[Dict]]:
        """Fast orderbook table extraction"""
        # Quick preprocess
        processed = self.quick_preprocess(orderbook_img)
        
        # Split left (bid) and right (ask)
        h, w = processed.shape[:2]
        mid = w // 2
        
        bid_img = processed[:, :mid]
        ask_img = processed[:, mid:]
        
        # OCR both sides with table mode
        bid_text = pytesseract.image_to_string(
            bid_img,
            config='--psm 6 --oem 3'
        )
        
        ask_text = pytesseract.image_to_string(
            ask_img,
            config='--psm 6 --oem 3'
        )
        
        # Parse tables
        bids = self.parse_orderbook_side(bid_text)
        asks = self.parse_orderbook_side(ask_text)
        
        return bids, asks
    
    def parse_orderbook_side(self, text: str) -> List[Dict]:
        """Parse orderbook side text into structured data"""
        entries = []
        lines = text.strip().split('\n')
        
        for line in lines:
            # Extract numbers from line
            nums = []
            current_num = ""
            
            for char in line:
                if char.isdigit():
                    current_num += char
                elif current_num:
                    nums.append(int(current_num))
                    current_num = ""
            
            if current_num:
                nums.append(int(current_num))
            
            # Expect: price, lot, freq
            if len(nums) >= 2:
                entry = {
                    "price": nums[0],
                    "lot": nums[1],
                    "freq": nums[2] if len(nums) >= 3 else 0
                }
                entries.append(entry)
        
        return entries
    
    def extract(self, image_path: str) -> Dict:
        """Fast extraction pipeline"""
        start_time = time.time()
        
        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot load image: {image_path}")
        
        # Resize for speed
        img = self.resize_for_speed(img)
        
        # Split regions
        header, orderbook = self.split_regions(img)
        
        # Extract header (fast) - pass full image for better parsing
        if self.debug:
            print("Extracting header...")
        header_start = time.time()
        stats = self.extract_header_stats(img)  # Pass full image, not just header
        header_time = time.time() - header_start
        
        # Extract orderbook (slower)
        if self.debug:
            print("Extracting orderbook...")
        orderbook_start = time.time()
        bids, asks = self.extract_orderbook_table(orderbook)
        orderbook_time = time.time() - orderbook_start
        
        # Calculate confidence (simple heuristic)
        confidence = 0
        if stats["ticker"]:
            confidence += 30
        if stats["timestamp"]:
            confidence += 20
        if len(bids) >= 5:
            confidence += 25
        if len(asks) >= 5:
            confidence += 25
        
        result = {
            **stats,
            "bids": bids,
            "asks": asks,
            "confidence": confidence,
            "engine_used": "tesseract_fast",
            "processing_time": time.time() - start_time,
            "timing": {
                "header": header_time,
                "orderbook": orderbook_time
            }
        }
        
        if self.debug:
            print(f"Total OCR time: {result['processing_time']:.2f}s")
            print(f"  Header: {header_time:.2f}s")
            print(f"  Orderbook: {orderbook_time:.2f}s")
            print(f"Confidence: {confidence}%")
        
        return result


def main():
    parser = argparse.ArgumentParser(description="Fast OCR for orderbook screenshots")
    parser.add_argument("image", help="Input screenshot path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--max-width", type=int, default=1200, help="Max image width for OCR")
    
    args = parser.parse_args()
    
    try:
        ocr = FastOrderbookOCR(debug=args.debug, max_width=args.max_width)
        result = ocr.extract(args.image)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Ticker: {result['ticker']}")
            print(f"Time: {result['timestamp']}")
            print(f"Bids: {len(result['bids'])} entries")
            print(f"Asks: {len(result['asks'])} entries")
            print(f"Confidence: {result['confidence']}%")
            print(f"Processing time: {result['processing_time']:.2f}s")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
