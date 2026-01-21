"""
ERPX AI - Telegram Bot
======================
Bot for document upload and approval via Telegram.

Features:
- Upload documents (photo/file)
- View job status
- Approve/Reject proposals
- View recent jobs
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Telegram imports
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

sys.path.insert(0, "/root/erp-ai")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("erpx.telegram")


# ===========================================================================
# Configuration
# ===========================================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8345444347:AAHKbjVbAdKLALcaotWRdWHtCgpdeMigKYg")
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
UPLOAD_DIR = Path("/root/erp-ai/data/uploads/telegram")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed users (can be expanded to database lookup)
ALLOWED_USERS: set = set()
ADMIN_USERS: set = set()


# ===========================================================================
# State Management
# ===========================================================================


class BotState:
    """Simple state management for bot"""

    def __init__(self):
        self.pending_jobs: dict[str, dict[str, Any]] = {}
        self.user_sessions: dict[int, dict[str, Any]] = {}

    def set_user_session(self, user_id: int, key: str, value: Any):
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        self.user_sessions[user_id][key] = value

    def get_user_session(self, user_id: int, key: str) -> Any:
        return self.user_sessions.get(user_id, {}).get(key)


bot_state = BotState()


# ===========================================================================
# API Client
# ===========================================================================

import httpx


async def upload_to_api(file_path: str, filename: str, tenant_id: str = "default") -> dict[str, Any]:
    """Upload file to API service"""
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            headers = {"X-Tenant-Id": tenant_id}
            response = await client.post(f"{API_BASE_URL}/v1/upload", files=files, headers=headers, timeout=60.0)
            return response.json()


async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get job status from API"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/v1/jobs/{job_id}", timeout=30.0)
        return response.json()


async def approve_job(job_id: str, approved: bool, notes: str = "", approver_id: str = "") -> dict[str, Any]:
    """Approve or reject job"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/v1/approve/{job_id}",
            json={"approved": approved, "notes": notes, "approver_id": approver_id},
            timeout=30.0,
        )
        return response.json()


# ===========================================================================
# Bot Handlers
# ===========================================================================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user

    welcome_message = f"""
🤖 *Chào mừng {user.first_name} đến với ERPX AI Bot!*

Bot này giúp bạn xử lý hóa đơn và chứng từ kế toán tự động.

*Các lệnh có sẵn:*
📤 /upload - Hướng dẫn upload hóa đơn
📋 /status <job\\_id> - Xem trạng thái xử lý
📊 /jobs - Xem danh sách công việc gần đây
✅ /approve <job\\_id> - Duyệt bút toán
❌ /reject <job\\_id> - Từ chối bút toán
❓ /help - Xem hướng dẫn

*Cách sử dụng:*
1\\. Gửi ảnh hoặc file PDF hóa đơn
2\\. Bot sẽ xử lý và đề xuất bút toán
3\\. Xem và duyệt bút toán
"""
    await update.message.reply_text(welcome_message, parse_mode="MarkdownV2")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📚 *Hướng dẫn sử dụng ERPX AI Bot*

*Upload hóa đơn:*
• Gửi ảnh chụp hoặc file PDF/Excel trực tiếp
• Bot sẽ tự động nhận diện và xử lý

*Xem kết quả:*
• Dùng /status <job\\_id> để xem chi tiết
• Kết quả bao gồm: loại chứng từ, nhà cung cấp, số tiền, bút toán đề xuất

*Duyệt bút toán:*
• /approve <job\\_id> \\- Duyệt và ghi sổ
• /reject <job\\_id> \\- Từ chối

*Lưu ý:*
• Ảnh nên rõ ràng, không mờ
• Hỗ trợ: PDF, PNG, JPG, XLSX
• Kích thước tối đa: 50MB
"""
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /upload command"""
    await update.message.reply_text(
        "📤 *Để upload hóa đơn:*\n\n"
        "1\\. Gửi ảnh chụp hóa đơn \\(photo\\)\n"
        "2\\. Hoặc gửi file PDF/Excel \\(document\\)\n\n"
        "Bot sẽ tự động xử lý và đề xuất bút toán\\.",
        parse_mode="MarkdownV2",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status <job_id> command"""
    if not context.args:
        await update.message.reply_text("❌ Vui lòng cung cấp job_id: /status <job_id>")
        return

    job_id = context.args[0]

    try:
        job = await get_job_status(job_id)

        status_emoji = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "failed": "❌",
            "approved": "✅",
            "rejected": "❌",
            "needs_review": "⚠️",
        }.get(job.get("status"), "❓")

        message = f"""
{status_emoji} *Job: {job_id[:8]}\\.\\.\\.*

*Trạng thái:* {job.get("status", "unknown")}
*Tạo lúc:* {job.get("created_at", "N/A")[:19]}
"""

        # Add result if available
        if job.get("result"):
            result = job["result"]
            message += f"""
*Loại chứng từ:* {result.get("doc_type", "N/A")}
*Nhà cung cấp:* {result.get("vendor", "N/A")}
*Số HĐ:* {result.get("invoice_no", "N/A")}
*Tổng tiền:* {result.get("total_amount", 0):,.0f} VND
*Thuế VAT:* {result.get("vat_amount", 0):,.0f} VND
*Độ tin cậy:* {result.get("confidence", 0):.0%}
"""

            # Add entries
            entries = result.get("entries", [])
            if entries:
                message += "\n*Bút toán đề xuất:*\n"
                for e in entries[:5]:  # Limit to 5 entries
                    debit = f"{e.get('debit', 0):,.0f}" if e.get("debit") else "-"
                    credit = f"{e.get('credit', 0):,.0f}" if e.get("credit") else "-"
                    message += f"• {e.get('account_code', '')}: Nợ {debit} / Có {credit}\n"

        # Add error if failed
        if job.get("error"):
            message += f"\n❌ *Lỗi:* {job.get('error')[:100]}"

        # Add action buttons if completed
        keyboard = None
        if job.get("status") == "completed":
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_{job_id}"),
                        InlineKeyboardButton("❌ Từ chối", callback_data=f"reject_{job_id}"),
                    ]
                ]
            )

        # Escape special characters for MarkdownV2
        message = message.replace(".", "\\.").replace("-", "\\-").replace("(", "\\(").replace(")", "\\)")

        await update.message.reply_text(message, parse_mode="MarkdownV2", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        await update.message.reply_text(f"❌ Lỗi kiểm tra trạng thái: {str(e)[:100]}")


async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /jobs command - list recent jobs"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/v1/jobs?limit=10", timeout=30.0)
            data = response.json()

        jobs = data.get("jobs", [])

        if not jobs:
            await update.message.reply_text("📋 Chưa có công việc nào.")
            return

        message = "📋 *Công việc gần đây:*\n\n"

        for job in jobs[-10:]:
            status_emoji = {
                "pending": "⏳",
                "processing": "🔄",
                "completed": "✅",
                "failed": "❌",
                "approved": "✅",
            }.get(job.get("status"), "❓")
            job_id = job.get("job_id", "")[:8]
            status = job.get("status", "unknown")
            message += f"{status_emoji} `{job_id}` \\- {status}\n"

        await update.message.reply_text(message, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Jobs list failed: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /approve <job_id> command"""
    if not context.args:
        await update.message.reply_text("❌ Vui lòng cung cấp job_id: /approve <job_id>")
        return

    job_id = context.args[0]
    user = update.effective_user

    try:
        result = await approve_job(job_id, approved=True, approver_id=str(user.id))
        await update.message.reply_text(f"✅ Đã duyệt job {job_id[:8]}...")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi duyệt: {str(e)[:100]}")


async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reject <job_id> command"""
    if not context.args:
        await update.message.reply_text("❌ Vui lòng cung cấp job_id: /reject <job_id>")
        return

    job_id = context.args[0]
    user = update.effective_user
    notes = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    try:
        result = await approve_job(job_id, approved=False, notes=notes, approver_id=str(user.id))
        await update.message.reply_text(f"❌ Đã từ chối job {job_id[:8]}...")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi từ chối: {str(e)[:100]}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads"""
    user = update.effective_user

    await update.message.reply_text("📥 Đang nhận ảnh...")

    try:
        # Get largest photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        # Download
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photo_{user.id}_{timestamp}.jpg"
        file_path = UPLOAD_DIR / filename

        await file.download_to_drive(str(file_path))

        await update.message.reply_text("🔄 Đang xử lý...")

        # Upload to API
        result = await upload_to_api(str(file_path), filename, tenant_id="telegram")

        job_id = result.get("job_id", "")
        bot_state.pending_jobs[job_id] = {"user_id": user.id, "filename": filename}

        await update.message.reply_text(
            f"✅ Đã nhận hóa đơn!\n\n📋 *Job ID:* `{job_id}`\n⏳ Đang xử lý...\n\nDùng /status {job_id} để xem kết quả",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Photo handling failed: {e}")
        await update.message.reply_text(f"❌ Lỗi xử lý ảnh: {str(e)[:100]}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads (PDF, Excel)"""
    user = update.effective_user
    document = update.message.document

    # Check file type
    mime_type = document.mime_type or ""
    allowed = ["pdf", "spreadsheet", "excel", "csv"]
    if not any(t in mime_type for t in allowed):
        await update.message.reply_text(f"❌ Loại file không hỗ trợ: {mime_type}\nChỉ hỗ trợ: PDF, Excel")
        return

    await update.message.reply_text("📥 Đang nhận file...")

    try:
        file = await context.bot.get_file(document.file_id)

        # Download
        filename = document.file_name or f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_path = UPLOAD_DIR / f"{user.id}_{filename}"

        await file.download_to_drive(str(file_path))

        await update.message.reply_text("🔄 Đang xử lý...")

        # Upload to API
        result = await upload_to_api(str(file_path), filename, tenant_id="telegram")

        job_id = result.get("job_id", "")
        bot_state.pending_jobs[job_id] = {"user_id": user.id, "filename": filename}

        await update.message.reply_text(
            f"✅ Đã nhận file!\n\n"
            f"📋 *Job ID:* `{job_id}`\n"
            f"📄 *File:* {filename}\n"
            f"⏳ Đang xử lý...\n\n"
            f"Dùng /status {job_id} để xem kết quả",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Document handling failed: {e}")
        await update.message.reply_text(f"❌ Lỗi xử lý file: {str(e)[:100]}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = query.from_user

    if data.startswith("approve_"):
        job_id = data.replace("approve_", "")
        try:
            await approve_job(job_id, approved=True, approver_id=str(user.id))
            await query.edit_message_text(f"✅ Đã duyệt job {job_id[:8]}...")
        except Exception as e:
            await query.edit_message_text(f"❌ Lỗi: {str(e)[:100]}")

    elif data.startswith("reject_"):
        job_id = data.replace("reject_", "")
        try:
            await approve_job(job_id, approved=False, approver_id=str(user.id))
            await query.edit_message_text(f"❌ Đã từ chối job {job_id[:8]}...")
        except Exception as e:
            await query.edit_message_text(f"❌ Lỗi: {str(e)[:100]}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error: {context.error}")


# ===========================================================================
# Main
# ===========================================================================


def create_bot_application() -> Optional["Application"]:
    """Create bot application"""
    if not TELEGRAM_AVAILABLE:
        logger.error("Telegram library not available")
        return None

    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return None

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("upload", upload_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("jobs", jobs_command))
    application.add_handler(CommandHandler("approve", approve_command))
    application.add_handler(CommandHandler("reject", reject_command))

    # Photo and document handlers
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Callback handler for inline buttons
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Error handler
    application.add_error_handler(error_handler)

    return application


def run_bot():
    """Run the bot"""
    application = create_bot_application()
    if application:
        logger.info("Starting Telegram bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
