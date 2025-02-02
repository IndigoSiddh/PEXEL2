import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext

import config

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

SELECT_ORIENTATION = 1
ENTER_NEW_QUERY = 2

def get_images_from_pexels(query, orientation, num_images=1, exclude_ids=[]):
    headers = {'Authorization': config.PEXELS_API_KEY}
    params = {'query': query, 'per_page': num_images + len(exclude_ids), 'orientation': orientation}
    response = requests.get('https://api.pexels.com/v1/search', headers=headers, params=params)
    data = response.json()
    image_urls = []
    for photo in data.get('photos', []):
        if photo['id'] not in exclude_ids:
            image_urls.append(photo['src']['large'])
            exclude_ids.append(photo['id'])
            if len(image_urls) == num_images:
                break
    return image_urls

def get_videos_from_pexels(query, orientation, num_videos=1, exclude_ids=[]):
    headers = {'Authorization': config.PEXELS_API_KEY}
    params = {'query': query, 'per_page': num_videos + len(exclude_ids), 'orientation': orientation}
    response = requests.get('https://api.pexels.com/videos/search', headers=headers, params=params)
    data = response.json()
    video_urls = []
    for video in data.get('videos', []):
        if video['id'] not in exclude_ids:
            video_urls.append(video['video_files'][0]['link'])
            exclude_ids.append(video['id'])
            if len(video_urls) == num_videos:
                break
    return video_urls

def start(update: Update, context: CallbackContext) -> int:
    logger.info("Start command received")
    update.message.reply_text("Введите запрос для поиска контента:", reply_markup=ReplyKeyboardRemove())
    return ENTER_NEW_QUERY

def process_user_selection(update: Update, context: CallbackContext) -> int:
    logger.info("User selection received: %s", update.message.text)
    user_selection = update.message.text
    user_text = context.user_data.get('user_text')
    images = []
    videos = []

    if user_selection == '|F|':
        images = get_images_from_pexels(user_text, 'portrait', exclude_ids=context.user_data.get('sent_images', []))
    elif user_selection == '__F__':
        images = get_images_from_pexels(user_text, 'landscape', exclude_ids=context.user_data.get('sent_images', []))
    elif user_selection == '|V|':
        videos = get_videos_from_pexels(user_text, 'portrait', exclude_ids=context.user_data.get('sent_videos', []))
    elif user_selection == '__V__':
        videos = get_videos_from_pexels(user_text, 'landscape', exclude_ids=context.user_data.get('sent_videos', []))

    if images or videos:
        update.message.reply_text("Результаты:")

        for image in images:
            context.bot.send_photo(chat_id=update.message.chat_id, photo=image)
            if 'sent_images' not in context.user_data:
                context.user_data['sent_images'] = []
            context.user_data['sent_images'].append(image)

        for video in videos:
            try:
                context.bot.send_video(chat_id=update.message.chat_id, video=video)
                if 'sent_videos' not in context.user_data:
                    context.user_data['sent_videos'] = []
                context.user_data['sent_videos'].append(video)
            except Exception as e:
                logger.error("Failed to send video: %s", e)
                update.message.reply_text("Не удалось отправить видео. Попробуйте снова.")

        reply_keyboard = [['|F|', '__F__'], ['|V|', '__V__'], ['/new']]
        update.message.reply_text("Выберите ориентацию контента или введите /new для нового запроса:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return SELECT_ORIENTATION
    else:
        update.message.reply_text("Результаты не найдены. Введите новый запрос или используйте /new для начала нового поиска.")
        return ENTER_NEW_QUERY

def enter_new_query(update: Update, context: CallbackContext) -> int:
    logger.info("New query requested")
    update.message.reply_text("Введите новый запрос:")
    return ENTER_NEW_QUERY

def save_new_query(update: Update, context: CallbackContext) -> int:
    logger.info("New query saved: %s", update.message.text)
    context.user_data['user_text'] = update.message.text
    context.user_data['sent_images'] = []
    context.user_data['sent_videos'] = []
    reply_keyboard = [['|F|', '__F__'], ['|V|', '__V__']]
    update.message.reply_text("Запрос сохранен. Выберите ориентацию контента:", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return SELECT_ORIENTATION

def main():
    telegram_token = config.TELEGRAM_BOT_TOKEN
    updater = Updater(token=telegram_token, use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_ORIENTATION: [MessageHandler(Filters.regex(r'^(\|F\||__F__|\|V\||__V__)$'), process_user_selection)],
            ENTER_NEW_QUERY: [MessageHandler(Filters.text & ~Filters.command, save_new_query)],
        },
        fallbacks=[CommandHandler('new', enter_new_query)],
    )

    dispatcher.add_handler(conv_handler)

    logger.info("Bot started")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()