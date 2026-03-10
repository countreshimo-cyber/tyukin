import os
import json
import logging
from datetime import datetime
import base64
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configuration
TELEGRAM_BOT_TOKEN = "8750405247:AAFkSAa4uss66oEhkvNjGLnun7bJfNAiA-Y"
GITHUB_TOKEN = "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"
GITHUB_REPO = "countreshimo-cyber/tyukin"
GITHUB_FILE_PATH = "blog-posts.json"

# Authorized users
AUTHORIZED_USERS = [157563909, 409950568]  # Антон и Тюкин

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Category mapping
CATEGORY_NAMES = {
    'preparation': 'Подготовка',
    'rehabilitation': 'Реабилитация',
    'myths': 'Мифы и факты',
    'techniques': 'Техники операций'
}

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized"""
    return user_id in AUTHORIZED_USERS

def format_text_to_html(text: str) -> str:
    """Convert plain text to HTML with automatic paragraph formatting"""
    paragraphs = text.strip().split('\n\n')
    html_parts = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Check if it's a list item
        if para.startswith('- '):
            # Start a list
            items = [item.strip('- ').strip() for item in para.split('\n') if item.strip().startswith('- ')]
            html_parts.append('<ul>')
            for item in items:
                html_parts.append(f'<li>{item}</li>')
            html_parts.append('</ul>')
        else:
            # Regular paragraph
            html_parts.append(f'<p>{para}</p>')
    
    return ''.join(html_parts)

async def get_github_file():
    """Get current blog posts from GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data['content']).decode('utf-8')
            return json.loads(content), data['sha']
        elif response.status_code == 404:
            # File doesn't exist, create empty structure
            return {"posts": []}, None
        else:
            logger.error(f"GitHub API error: {response.status_code}")
            return None, None
    except Exception as e:
        logger.error(f"Error getting file from GitHub: {e}")
        return None, None

async def update_github_file(content: dict, sha: str = None):
    """Update blog posts file on GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    content_base64 = base64.b64encode(content_json.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": "Add new blog post",
        "content": content_base64
    }
    
    if sha:
        data["sha"] = sha
    
    try:
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            return True
        else:
            logger.error(f"GitHub update error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error updating GitHub file: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("⛔️ У вас нет доступа к этому боту.")
        return
    
    welcome_text = """
👋 Привет! Я бот для управления блогом на сайте tyukinplastic.ru

📝 Как добавить статью:

Отправьте сообщение в формате:

/add_post
Категория: preparation
Заголовок: Название статьи
Превью: Краткое описание (1-2 предложения)
Текст:
Полный текст статьи.

Можно несколько абзацев.

📌 Доступные категории:
• preparation - Подготовка
• rehabilitation - Реабилитация
• myths - Мифы и факты
• techniques - Техники операций

Дата публикации устанавливается автоматически.
"""
    await update.message.reply_text(welcome_text)

async def add_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add_post command"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("⛔️ У вас нет доступа к этому боту.")
        return
    
    await update.message.reply_text(
        "📝 Отправьте данные для статьи в следующем формате:\n\n"
        "Категория: preparation\n"
        "Заголовок: Название статьи\n"
        "Превью: Краткое описание\n"
        "Текст:\n"
        "Полный текст статьи...\n\n"
        "Категории: preparation, rehabilitation, myths, techniques"
    )
    
    # Set state to wait for post data
    context.user_data['waiting_for_post'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("⛔️ У вас нет доступа к этому боту.")
        return
    
    if not context.user_data.get('waiting_for_post'):
        await update.message.reply_text(
            "Используйте команду /add_post для добавления статьи.\n"
            "Или /start для справки."
        )
        return
    
    text = update.message.text
    
    try:
        # Parse the message
        lines = text.strip().split('\n')
        data = {}
        text_start_index = -1
        
        for i, line in enumerate(lines):
            if line.startswith('Категория:'):
                data['category'] = line.split(':', 1)[1].strip()
            elif line.startswith('Заголовок:'):
                data['title'] = line.split(':', 1)[1].strip()
            elif line.startswith('Превью:'):
                data['preview'] = line.split(':', 1)[1].strip()
            elif line.startswith('Текст:'):
                text_start_index = i + 1
                break
        
        if text_start_index > 0:
            data['text'] = '\n'.join(lines[text_start_index:]).strip()
        
        # Validate data
        if not all(k in data for k in ['category', 'title', 'preview', 'text']):
            await update.message.reply_text(
                "❌ Неправильный формат! Проверьте, что указали все поля:\n"
                "- Категория\n"
                "- Заголовок\n"
                "- Превью\n"
                "- Текст"
            )
            return
        
        if data['category'] not in CATEGORY_NAMES:
            await update.message.reply_text(
                f"❌ Неправильная категория! Доступные: {', '.join(CATEGORY_NAMES.keys())}"
            )
            return
        
        if len(data['text']) > 10000:
            await update.message.reply_text("❌ Текст слишком длинный (максимум 10000 символов)")
            return
        
        # Show processing message
        processing_msg = await update.message.reply_text("⏳ Добавляю статью...")
        
        # Get current posts
        posts_data, sha = await get_github_file()
        
        if posts_data is None:
            await processing_msg.edit_text("❌ Ошибка при получении данных с GitHub")
            return
        
        # Generate new post ID
        existing_ids = [post['id'] for post in posts_data.get('posts', [])]
        new_id = max(existing_ids) + 1 if existing_ids else 1
        
        # Format text to HTML
        content_html = format_text_to_html(data['text'])
        
        # Create new post
        new_post = {
            "id": new_id,
            "category": data['category'],
            "title": data['title'],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "preview": data['preview'],
            "content": content_html
        }
        
        # Add to beginning of posts list
        posts_data.setdefault('posts', []).insert(0, new_post)
        
        # Update GitHub
        success = await update_github_file(posts_data, sha)
        
        if success:
            await processing_msg.edit_text(
                f"✅ Статья добавлена!\n\n"
                f"📌 {data['title']}\n"
                f"📂 {CATEGORY_NAMES[data['category']]}\n"
                f"📅 {new_post['date']}\n\n"
                f"Статья появится на сайте в течение 1-2 минут."
            )
        else:
            await processing_msg.edit_text("❌ Ошибка при обновлении GitHub")
        
        # Reset state
        context.user_data['waiting_for_post'] = False
        
    except Exception as e:
        logger.error(f"Error processing post: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        context.user_data['waiting_for_post'] = False

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_post", add_post_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start polling
    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
