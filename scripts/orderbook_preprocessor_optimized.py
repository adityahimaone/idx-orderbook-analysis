#!/usr/bin/env python3
"""
IDX Orderbook Screenshot Preprocessor - OPTIMIZED
Phase 1: Fast image preprocessing for mobile screenshots

Optimizations:
- Skip rotation detection jika image straight
- Reduce resolution untuk preprocessing
- Cache results
- Parallel processing ready
"""

import sys
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import argparse
import time


class OrderbookPreprocessorOptimized:
    """Fast preprocessing for orderbook screenshots"""
    
    def __init__(self, debug=False, skip_rotation=False):
        self.debug = debug
        self.skip_rotation = skip_rotation  # Skip expensive rotation detection
        
    def is_mobile_screenshot(self, img):
        """Detect mobile screenshot by aspect ratio"""
        h, w = img.shape[:2]
        aspect_ratio = h / w
        return 1.5 < aspect_ratio < 2.5
    
    def is_dark_mode(self, img):
        """Detect dark mode by analyzing average brightness"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        avg_brightness = np.mean(gray)
        return avg_brightness < 100
    
    def invert_dark_mode(self, img):
        """Invert dark mode screenshot"""
        return cv2.bitwise_not(img)
    
    def enhance_contrast_fast(self, img):
        """Fast contrast enhancement (simplified CLAHE)"""
        # Convert to LAB
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE with smaller tile size for speed
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        l = clahe.apply(l)
        
        # Merge back
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    def denoise_fast(self, img):
        """Fast denoise using bilateral filter (faster than fastNlMeans)"""
        return cv2.bilateralFilter(img, 5, 50, 50)
    
    def detect_rotation_fast(self, img):
        """Fast rotation detection - skip if image looks straight"""
        # Reduce resolution for faster processing
        h, w = img.shape[:2]
        if h > 1000:
            scale = 1000 / h
            small = cv2.resize(img, (int(w * scale), 1000))
        else:
            small = img
        
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Use fewer lines for speed
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
        
        if lines is None or len(lines) < 5:
            return 0
        
        angles = []
        for rho, theta in lines[:, 0]:
            angle = np.degrees(theta) - 90
            angles.append(angle)
        
        angles = np.array(angles)
        angles = angles[np.abs(angles) < 45]
        
        if len(angles) == 0:
            return 0
        
        median_angle = np.median(angles)
        return median_angle if abs(median_angle) > 1.0 else 0  # Increased threshold
    
    def rotate_image(self, img, angle):
        """Rotate image"""
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return rotated
    
    def auto_crop_regions(self, img):
        """Separate header from orderbook table"""
        h, w = img.shape[:2]
        header_height = int(h * 0.18)
        
        header = img[0:header_height, :]
        orderbook = img[header_height:, :]
        
        return header, orderbook
    
    def sharpen_fast(self, img):
        """Fast sharpening using unsharp mask"""
        gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
        sharpened = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)
        return sharpened
    
    def preprocess(self, image_path, output_path=None):
        """
        Fast preprocessing pipeline
        
        Optimizations:
        - Skip expensive rotation detection by default
        - Use faster filters (bilateral instead of NLM)
        - Reduce resolution for intermediate steps
        - Smaller CLAHE tile size
        """
        start_time = time.time()
        
        # Load image
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot load image: {image_path}")
        
        original_shape = img.shape
        steps = []
        
        # Step 1: Check if mobile screenshot
        is_mobile = self.is_mobile_screenshot(img)
        steps.append(f"Mobile screenshot: {is_mobile}")
        
        # Step 2: Dark mode detection
        is_dark = self.is_dark_mode(img)
        steps.append(f"Dark mode detected: {is_dark}")
        
        if is_dark:
            img = self.invert_dark_mode(img)
            steps.append("Applied dark mode inversion")
        
        # Step 3: Rotation detection (OPTIONAL - skip by default)
        if not self.skip_rotation:
            rotation_angle = self.detect_rotation_fast(img)
            if abs(rotation_angle) > 0.5:
                img = self.rotate_image(img, rotation_angle)
                steps.append(f"Corrected rotation: {rotation_angle:.2f}°")
        else:
            steps.append("Skipped rotation detection (fast mode)")
        
        # Step 4: Fast denoise
        img = self.denoise_fast(img)
        steps.append("Applied fast denoise")
        
        # Step 5: Fast contrast enhancement
        img = self.enhance_contrast_fast(img)
        steps.append("Enhanced contrast (fast CLAHE)")
        
        # Step 6: Fast sharpen
        img = self.sharpen_fast(img)
        steps.append("Applied fast sharpening")
        
        # Step 7: Auto-crop regions
        header, orderbook = self.auto_crop_regions(img)
        steps.append("Separated header and orderbook regions")
        
        # Save if output path provided
        if output_path:
            cv2.imwrite(str(output_path), img)
            steps.append(f"Saved to: {output_path}")
        
        elapsed = time.time() - start_time
        steps.append(f"Processing time: {elapsed:.2f}s")
        
        result = {
            "full_image": img,
            "header": header,
            "orderbook": orderbook,
            "metadata": {
                "original_shape": original_shape,
                "is_mobile": is_mobile,
                "is_dark_mode": is_dark,
                "preprocessing_steps": steps,
                "processing_time": elapsed
            }
        }
        
        if self.debug:
            print("\n".join(steps))
        
        return result


def main():
    parser = argparse.ArgumentParser(description="Fast preprocess orderbook screenshots")
    parser.add_argument("input", help="Input screenshot path")
    parser.add_argument("-o", "--output", help="Output preprocessed image path")
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("--skip-rotation", action="store_true", help="Skip rotation detection (faster)")
    parser.add_argument("--header-only", action="store_true", help="Save only header region")
    parser.add_argument("--orderbook-only", action="store_true", help="Save only orderbook region")
    
    args = parser.parse_args()
    
    preprocessor = OrderbookPreprocessorOptimized(debug=args.debug, skip_rotation=args.skip_rotation)
    
    try:
        result = preprocessor.preprocess(args.input, args.output)
        
        if args.header_only and args.output:
            output_path = Path(args.output)
            header_path = output_path.parent / f"{output_path.stem}_header{output_path.suffix}"
            cv2.imwrite(str(header_path), result["header"])
            print(f"Header saved to: {header_path}")
        
        if args.orderbook_only and args.output:
            output_path = Path(args.output)
            orderbook_path = output_path.parent / f"{output_path.stem}_orderbook{output_path.suffix}"
            cv2.imwrite(str(orderbook_path), result["orderbook"])
            print(f"Orderbook saved to: {orderbook_path}")
        
        if not args.output:
            print("Preprocessing completed. Use --output to save result.")
        
        print(f"Processing time: {result['metadata']['processing_time']:.2f}s")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
