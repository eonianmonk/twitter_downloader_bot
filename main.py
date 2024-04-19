import traceback
from io import StringIO
from os import makedirs

import telegram.error
from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, PicklePersistence

from config import BOT_TOKEN, DEVELOPER_ID, IS_BOT_PRIVATE
from log import log_handling,logger,error_handler
from twitter import extract_tweet_ids, reply_media,scrape_media


def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    log_handling(update, 'info', f'Received /start command from userId {update.effective_user.id}')
    user = update.effective_user
    update.effective_message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!' +
        '\nSend tweet link here and I will download media in the best available quality for you'
    )


def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.effective_message.reply_text('Send tweet link here and I will download media in the best available quality for you')


def stats_command(update: Update, context: CallbackContext) -> None:
    """Send stats when the command /stats is issued."""
    if not 'stats' in context.bot_data:
        context.bot_data['stats'] = {'messages_handled': 0, 'media_downloaded': 0}
        logger.info('Initialized stats')
    logger.info(f'Sent stats: {context.bot_data["stats"]}')
    update.effective_message.reply_markdown_v2(f'*Bot stats:*\nMessages handled: *{context.bot_data["stats"].get("messages_handled")}*'
                                     f'\nMedia downloaded: *{context.bot_data["stats"].get("media_downloaded")}*')


def reset_stats_command(update: Update, context: CallbackContext) -> None:
    """Reset stats when the command /resetstats is issued."""
    stats = {'messages_handled': 0, 'media_downloaded': 0}
    context.bot_data['stats'] = stats
    logger.info("Bot stats have been reset")
    update.effective_message.reply_text("Bot stats have been reset")


def deny_access(update: Update, context: CallbackContext) -> None:
    """Deny unauthorized access"""
    log_handling(update, 'info',
                 f'Access denied to {update.effective_user.full_name} (@{update.effective_user.username}),'
                 f' userId {update.effective_user.id}')
    update.effective_message.reply_text(f'Access denied. Your id ({update.effective_user.id}) is not whitelisted')


def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle the user message. Reply with found supported media."""
    log_handling(update, 'info', 'Received message: ' + update.effective_message.text.replace("\n", ""))
    if not 'stats' in context.bot_data:
        context.bot_data['stats'] = {'messages_handled': 0, 'media_downloaded': 0}
        logger.info('Initialized stats')
    context.bot_data['stats']['messages_handled'] += 1

    if tweet_ids := extract_tweet_ids(update):
        log_handling(update, 'info', f'Found Tweet IDs {tweet_ids} in message')
    else:
        log_handling(update, 'info', 'No supported tweet link found')
        update.effective_message.reply_text('No supported tweet link found', quote=True)
        return
    found_media = False
    found_tweets = False
    for tweet_id in tweet_ids:
        # Scrape a single tweet by ID
        log_handling(update, 'info', f'Scraping tweet ID {tweet_id}')
        try:
            media = scrape_media(tweet_id)
            found_tweets = True
            if media:
                log_handling(update, 'info', f'tweet media: {media}')
                if reply_media(update, context, media):
                    found_media = True
                else:
                    log_handling(update, 'info', f'Found unsupported media: {media[0]["type"]}')
            else:
                log_handling(update, 'info', f'Tweet {tweet_id} has no media')
                update.effective_message.reply_text(f'Tweet {tweet_id} has no media', quote=True)
        except Exception:
            log_handling(update, 'error', f'Error occurred when scraping tweet {tweet_id}: {traceback.format_exc()}')
            update.effective_message.reply_text(f'Error handling tweet {tweet_id}', quote=True)
            

    if found_tweets and not found_media:
        log_handling(update, 'info', 'No supported media found')
        update.effective_message.reply_text('No supported media found', quote=True)


def main() -> None:
    """Start the bot."""
    makedirs('data', exist_ok=True)  # Create data
    persistence = PicklePersistence(filename='data/persistence')

    # Create the Updater and pass it your bot's token.
    updater = Updater(BOT_TOKEN, persistence=persistence)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Get the bot to set commands menu
    bot = dispatcher.bot

    dispatcher.add_handler(CommandHandler("stats", stats_command, Filters.chat(DEVELOPER_ID)))
    dispatcher.add_handler(CommandHandler("resetstats", reset_stats_command, Filters.chat(DEVELOPER_ID)))

    if IS_BOT_PRIVATE:
        # Deny access to everyone but developer
        dispatcher.add_handler(MessageHandler(~Filters.chat(DEVELOPER_ID), deny_access))

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", start, Filters.chat(DEVELOPER_ID)))
        dispatcher.add_handler(CommandHandler("help", help_command, Filters.chat(DEVELOPER_ID)))

        # on non command i.e message - handle the message
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command & Filters.chat(DEVELOPER_ID),
                                              handle_message, run_async=True))

        # Set commands menu
        commands = [BotCommand("start", "Start the bot"), BotCommand("help", "Help message"),
                    BotCommand("stats", "Get bot statistics"), BotCommand("resetstats", "Reset bot statistics")]
        try:
            bot.set_my_commands(commands, scope=BotCommandScopeChat(DEVELOPER_ID))
        except telegram.error.BadRequest as exc:
            logger.warning(f"Couldn't set my commands for developer chat: {exc.message}")

    else:
        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))

        # on non command i.e message - handle the message
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message, run_async=True))

        # Set commands menu
        # Public commands are useless for now
        # public_commands = [BotCommand("start", "Start the bot"), BotCommand("help", "Help message")]
        public_commands = []
        dev_commands = public_commands + [BotCommand("stats", "Get bot statistics"),
                                          BotCommand("resetstats", "Reset bot statistics")]
        bot.set_my_commands(public_commands)
        try:
            bot.set_my_commands(dev_commands, scope=BotCommandScopeChat(DEVELOPER_ID))
        except telegram.error.BadRequest as exc:
            logger.warning(f"Couldn't set my commands for developer chat: {exc.message}")

    dispatcher.add_error_handler(error_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
