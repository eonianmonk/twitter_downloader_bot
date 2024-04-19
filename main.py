
from os import makedirs

import telegram.error
from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, PicklePersistence

from config import BOT_TOKEN, DEVELOPER_ID, IS_BOT_PRIVATE
from log import log_handling,logger,error_handler
import tg.bot as bot
import tg.inline as tg_inline

def main() -> None:
    """Start the bot."""
    makedirs('data', exist_ok=True)  # Create data
    persistence = PicklePersistence(filename='data/persistence')

    # Create the Updater and pass it your bot's token.
    updater = Updater(BOT_TOKEN, persistence=persistence)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Get the bot to set commands menu
    tgbot = dispatcher.bot

    dispatcher.add_handler(CommandHandler("stats", bot.stats_command, Filters.chat(DEVELOPER_ID)))
    dispatcher.add_handler(CommandHandler("resetstats", bot.reset_stats_command, Filters.chat(DEVELOPER_ID)))

    # inline 
    for h in tg_inline.inline_handlers():
        dispatcher.add_handler(h)

    if IS_BOT_PRIVATE:
        # Deny access to everyone but developer
        dispatcher.add_handler(MessageHandler(~Filters.chat(DEVELOPER_ID), bot.deny_access))

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", bot.start, Filters.chat(DEVELOPER_ID)))
        dispatcher.add_handler(CommandHandler("help", bot.help_command, Filters.chat(DEVELOPER_ID)))

        # on non command i.e message - handle the message
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command & Filters.chat(DEVELOPER_ID),
                                              bot.handle_message, run_async=True))

        # Set commands menu
        commands = [BotCommand("start", "Start the bot"), BotCommand("help", "Help message"),
                    BotCommand("stats", "Get bot statistics"), BotCommand("resetstats", "Reset bot statistics")]
        try:
            tgbot.set_my_commands(commands, scope=BotCommandScopeChat(DEVELOPER_ID))
        except telegram.error.BadRequest as exc:
            logger.warning(f"Couldn't set my commands for developer chat: {exc.message}")

    else:
        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", bot.start))
        dispatcher.add_handler(CommandHandler("help", bot.help_command))

        # on non command i.e message - handle the message
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, bot.handle_message, run_async=True))

        # Set commands menu
        # Public commands are useless for now
        # public_commands = [BotCommand("start", "Start the bot"), BotCommand("help", "Help message")]
        public_commands = []
        dev_commands = public_commands + [BotCommand("stats", "Get bot statistics"),
                                          BotCommand("resetstats", "Reset bot statistics")]
        bot.set_my_commands(public_commands)
        try:
            tgbot.set_my_commands(dev_commands, scope=BotCommandScopeChat(DEVELOPER_ID))
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
