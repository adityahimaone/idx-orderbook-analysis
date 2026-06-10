#!/usr/bin/env python3
"""
IDX Orderbook Screenshot Preprocessor
Phase 1: Image preprocessing for mobile screenshots

Handles:
- Dark mode detection and inversion
- Contrast enhancement (CLAHE)
- Rotation/skew detection
- Denoise for refresh artifacts
- Auto-crop: header stats vs orderbook table
"""

import sys
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import argparse


class OrderbookPreprocessor:
    """Preprocess orderbook screenshots for optimal OCR accuracy"""
    
    def __init__(self, debug=False):
        self.debug = debug
        
    def is_mobile_screenshot(self, img):
        """Detect mobile screenshot by aspect ratio"""
        h, w = img.shape[:2]
        aspect_ratio = h / w
        # Mobile screens typically 16:9 to 20:9 (1.77 to 2.22)
        return 1.5 < aspect_ratio < 2.5
    
    def is_dark_mode(self, img):
        """Detect dark mode by analyzing average brightness"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        avg_brightness = np.mean(gray)
        # Dark mode: average brightness < 100 (out of 255)
        return avg_brightness < 100
    
    def invert_dark_mode(self, img):
        """Invert dark mode screenshot for better OCR (Tesseract optimized for black text on white)"""
        return cv2.bitwise_not(img)
    
    def enhance_contrast(self, img):
        """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)"""
        # Convert to LAB color space
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        # Merge and convert back
        lab = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return enhanced
    
    def denoise(self, img):
        """Remove noise from screen refresh artifacts"""
        return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    
    def detect_rotation(self, img):
        """Detect and correct rotation/skew"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is None:
            return 0
        
        # Calculate dominant angle
        angles = []
        for rho, theta in lines[:, 0]:
            angle = np.degrees(theta) - 90
            angles.append(angle)
        
        # Filter outliers and get median
        angles = np.array(angles)
        angles = angles[np.abs(angles) < 45]  # Only consider reasonable rotations
        
        if len(angles) == 0:
            return 0
        
        median_angle = np.median(angles)
        return median_angle if abs(median_angle) > 0.5 else 0
    
    def rotate_image(self, img, angle):
        """Rotate image by given angle"""
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
    
    def auto_crop_regions(self, img):
        """
        Separate header stats from orderbook table
        Returns: (header_img, orderbook_img)
        """
        h, w = img.shape[:2]
        
        # Heuristic: header is top 15-20% of image
        # Orderbook table is remaining 80-85%
        header_height = int(h * 0.18)
        
        header = img[0:header_height, :]
        orderbook = img[header_height:, :]
        
        return header, orderbook
    
    def sharpen(self, img):
        """Sharpen image for better OCR"""
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(img, -1, kernel)
        return sharpened
    
    def preprocess(self, image_path, output_path=None):
        """
        Full preprocessing pipeline
        
        Args:
            image_path: Path to input screenshot
            output_path: Optional path to save preprocessed image
            
        Returns:
            dict with preprocessed images and metadata
        """
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
        
        # Step 3: Rotation detection and correction
        rotation_angle = self.detect_rotation(img)
        if abs(rotation_angle) > 0.5:
            img = self.rotate_image(img, rotation_angle)
            steps.append(f"Corrected rotation: {rotation_angle:.2f}°")
        
        # Step 4: Denoise
        img = self.denoise(img)
        steps.append("Applied denoising")
        
        # Step 5: Contrast enhancement
        img = self.enhance_contrast(img)
        steps.append("Enhanced contrast (CLAHE)")
        
        # Step 6: Sharpen
        img = self.sharpen(img)
        steps.append("Applied sharpening")
        
        # Step 7: Auto-crop regions
        header, orderbook = self.auto_crop_regions(img)
        steps.append("Separated header and orderbook regions")
        
        # Save if output path provided
        if output_path:
            cv2.imwrite(str(output_path), img)
            steps.append(f"Saved to: {output_path}")
        
        result = {
            "full_image": img,
            "header": header,
            "orderbook": orderbook,
            "metadata": {
                "original_shape": original_shape,
                "is_mobile": is_mobile,
                "is_dark_mode": is_dark,
                "rotation_corrected": rotation_angle,
                "preprocessing_steps": steps
            }
        }
        
        if self.debug:
            print("\n".join(steps))
        
        return result


def main():
    parser = argparse.ArgumentParser(description="Preprocess orderbook screenshots for OCR")
    parser.add_argument("input", help="Input screenshot path")
    parser.add_argument("-o", "--output", help="Output preprocessed image path")
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("--header-only", action="store_true", help="Save only header region")
    parser.add_argument("--orderbook-only", action="store_true", help="Save only orderbook region")
    
    args = parser.parse_args()
    
    preprocessor = OrderbookPreprocessor(debug=args.debug)
    
    try:
        result = preprocessor.preprocess(args.input, args.output)
        
        # Save specific regions if requested
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
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
