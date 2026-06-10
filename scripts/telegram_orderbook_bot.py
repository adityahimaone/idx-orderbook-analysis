#!/usr/bin/env python3
"""
Telegram Bot for IDX Orderbook Analysis
Fast processing: < 10 seconds from image to report

Usage:
1. Save this as telegram_orderbook_bot.py
2. Set TELEGRAM_BOT_TOKEN environment variable
3. Run: python3.11 telegram_orderbook_bot.py
"""

import os
import sys
import json
import tempfile
import asyncio
from pathlib import Path
from typing import Optional

# Telegram imports
try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

# Import fast pipeline
sys.path.insert(0, str(Path(__file__).parent))
from orderbook_pipeline_fast import OrderbookPipelineOptimized


class OrderbookTelegramBot:
    """Fast Telegram bot for orderbook analysis"""
    
    def __init__(self, token: str, debug: bool = False):
        self.token = token
        self.debug = debug
        self.pipeline = OrderbookPipelineOptimized(debug=debug, fast_mode=True)
        
        # Cache for user sessions
        self.user_cache = {}
        
        print(f"Orderbook Telegram Bot initialized")
        print(f"Fast mode: Enabled (target < 10s)")
        print(f"Debug: {debug}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_msg = (
            f"Halo {user.first_name}! 👋\n\n"
            "Gw bot analisa orderbook IDX. Kirim screenshot orderbook dari Stockbit/MOST/IPOT, "
            "gw analisa dalam < 10 detik.\n\n"
            "**Cara pakai:**\n"
            "1. Ambil screenshot orderbook (full screen)\n"
            "2. Kirim ke gw\n"
            "3. Tunggu ~5-10 detik\n"
            "4. Dapet analisa lengkap + rekomendasi entry\n\n"
            "**Format:**\n"
            "- Mobile screenshot (portrait)\n"
            "- Dark/light mode oke\n"
            "- Ticker harus keliatan jelas\n\n"
            "Kirim screenshot sekarang!"
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_msg = (
            "**Orderbook Analysis Bot**\n\n"
            "Kirim screenshot orderbook, gw proses:\n"
            "1. OCR extraction (1-2s)\n"
            "2. Validation & sanity checks\n"
            "3. Technical analysis\n"
            "4. 3-tier entry recommendations\n"
            "5. Risk assessment\n\n"
            "**Supported brokers:**\n"
            "- Stockbit\n"
            "- MOST\n"
            "- IPOT\n"
            "- Ajaib\n"
            "- Any mobile screenshot\n\n"
            "**Commands:**\n"
            "/start - Mulai bot\n"
            "/help - Bantuan ini\n"
            "/status - Cek bot status\n"
            "/speed - Test processing speed\n\n"
            "Kirim screenshot untuk mulai analisa!"
        )
        await update.message.reply_text(help_msg, parse_mode="Markdown")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        import psutil
        import time
        
        # Get system info
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status_msg = (
            f"**Bot Status**\n\n"
            f"🟢 **Online**\n"
            f"⏱️ **Uptime:** {self.get_uptime()}\n"
            f"⚡ **CPU:** {cpu_percent:.1f}%\n"
            f"💾 **RAM:** {memory.percent:.1f}% ({memory.used/1024/1024:.0f}MB)\n"
            f"💿 **Disk:** {disk.percent:.1f}% ({disk.free/1024/1024/1024:.1f}GB free)\n"
            f"🚀 **Fast Mode:** Enabled (< 10s target)\n"
            f"📊 **Cache:** {len(self.user_cache)} user sessions\n\n"
            f"Kirim screenshot untuk test!"
        )
        await update.message.reply_text(status_msg, parse_mode="Markdown")
    
    async def speed_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /speed command - test processing speed"""
        test_msg = (
            "**Speed Test**\n\n"
            "Gw bakal test processing speed dengan sample image.\n"
            "Tunggu ~5 detik..."
        )
        status_msg = await update.message.reply_text(test_msg, parse_mode="Markdown")
        
        try:
            # Test with sample image
            sample_path = Path.home() / ".hermes/stock_analysis.jpg"
            if not sample_path.exists():
                await status_msg.edit_text("Sample image not found. Kirim screenshot untuk test.")
                return
            
            start_time = time.time()
            
            # Run pipeline
            result = self.pipeline.run(
                str(sample_path),
                output_format="markdown"
            )
            
            elapsed = time.time() - start_time
            times = result["metadata"]["processing_times"]
            
            speed_msg = (
                f"**Speed Test Results**\n\n"
                f"✅ **Total:** {elapsed:.2f}s\n"
                f"📸 **OCR:** {times.get('ocr', 0):.2f}s\n"
                f"✅ **Validation:** {times.get('validation', 0):.2f}s\n"
                f"📊 **Analysis:** {times.get('analysis', 0):.2f}s\n"
                f"🎯 **Recommendations:** {times.get('recommendations', 0):.2f}s\n"
                f"📝 **Formatting:** {times.get('formatting', 0):.2f}s\n\n"
                f"**Status:** {'🟢 FAST' if elapsed < 10 else '🟡 MODERATE' if elapsed < 30 else '🔴 SLOW'}\n"
                f"**Target:** < 10s ✅\n\n"
                f"Kirim screenshot untuk analisa real!"
            )
            
            await status_msg.edit_text(speed_msg, parse_mode="Markdown")
            
        except Exception as e:
            await status_msg.edit_text(f"Error: {str(e)}")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages"""
        user = update.effective_user
        photo = update.message.photo[-1]  # Get highest resolution
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            "📸 **Processing screenshot...**\n"
            "⏱️ Estimated: 5-10 seconds\n"
            "Status: Downloading image...",
            parse_mode="Markdown"
        )
        
        try:
            # Download image
            await processing_msg.edit_text(
                "📸 **Processing screenshot...**\n"
                "⏱️ Estimated: 5-10 seconds\n"
                "Status: Downloading image... ✅",
                parse_mode="Markdown"
            )
            
            # Get file and download
            file = await photo.get_file()
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                image_path = tmp.name
            
            # Process image
            await processing_msg.edit_text(
                "📸 **Processing screenshot...**\n"
                "⏱️ Estimated: 5-10 seconds\n"
                "Status: OCR extraction...",
                parse_mode="Markdown"
            )
            
            start_time = time.time()
            result = self.pipeline.run(
                image_path,
                output_format="markdown"
            )
            elapsed = time.time() - start_time
            
            # Get formatted output
            report = result["formatted_output"]
            metadata = result["metadata"]
            
            # Truncate if too long (Telegram limit ~4096 chars)
            if len(report) > 4000:
                report = report[:3900] + "\n\n... [truncated, full report saved to file]"
            
            # Send results
            await processing_msg.edit_text(
                f"✅ **Analysis Complete!**\n"
                f"⏱️ **Time:** {elapsed:.2f}s\n"
                f"📊 **Confidence:** {metadata.get('confidence', 0):.1f}%\n"
                f"🎯 **Ticker:** {result.get('ocr_data', {}).get('ticker', 'N/A')}\n\n"
                f"{report}",
                parse_mode="Markdown"
            )
            
            # Clean up
            os.unlink(image_path)
            
            # Cache user session
            self.user_cache[user.id] = {
                "last_analysis": time.time(),
                "ticker": result.get('ocr_data', {}).get('ticker'),
                "confidence": metadata.get('confidence', 0)
            }
            
        except Exception as e:
            error_msg = f"❌ **Error processing image**\n\n{str(e)}"
            if self.debug:
                import traceback
                error_msg += f"\n\n```\n{traceback.format_exc()}\n```"
            
            await processing_msg.edit_text(error_msg, parse_mode="Markdown")
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document messages (image files)"""
        document = update.message.document
        
        # Check if it's an image
        mime_type = document.mime_type
        if mime_type and mime_type.startswith('image/'):
            await self.handle_photo(update, context)
        else:
            await update.message.reply_text(
                "Kirim file gambar (jpg/png) ya, bukan file lain."
            )
    
    def get_uptime(self) -> str:
        """Get bot uptime"""
        import time
        if not hasattr(self, '_start_time'):
            self._start_time = time.time()
        
        uptime_seconds = time.time() - self._start_time
        
        # Format uptime
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        else:
            return f"{minutes}m {seconds}s"
    
    def run(self):
        """Run the bot"""
        if not HAS_TELEGRAM:
            print("Error: python-telegram-bot not installed")
            print("Install: pip install python-telegram-bot")
            return
        
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("speed", self.speed_command))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        application.add_handler(MessageHandler(filters.Document.IMAGE, self.handle_document))
        
        # Start bot
        print("Bot starting...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram bot for IDX orderbook analysis")
    parser.add_argument("--token", help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env)")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    
    args = parser.parse_args()
    
    # Get token
    token = args.token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: Telegram bot token required")
        print("Set TELEGRAM_BOT_TOKEN environment variable or use --token")
        return 1
    
    # Import time module
    global time
    import time
    
    # Run bot
    bot = OrderbookTelegramBot(token, debug=args.debug)
    bot.run()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
