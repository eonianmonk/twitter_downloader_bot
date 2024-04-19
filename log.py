import logging
import telegram.error
import traceback
import html
import json

from telegram.ext import CallbackContext
from telegram import Update
from io import StringIO
from config import BOT_TOKEN, DEVELOPER_ID, IS_BOT_PRIVATE

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# TODO: use LoggerAdapter instead
def log_handling(update: Update, level: str, message: str) -> None:
    """Log message with chat_id and message_id."""
    _level = getattr(logging, level.upper())
    logger.log(_level, f'[{update.effective_chat.id}:{update.effective_message.message_id}] {message}')


def error_handler(update: object, context: CallbackContext) -> None:
    """Log the error and send a telegram message to notify the developer."""

    if isinstance(context.error, telegram.error.Unauthorized):
        return

    if isinstance(context.error, telegram.error.Conflict):
        # logger.critical(msg="Requests conflict found, exiting...")
        # kill(getpid(), SIGTERM)
        logger.error("Telegram requests conflict")
        return

    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    # if there is no update, don't send an error report (probably a network error, happens sometimes)
    if update is None:
        return

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    # Build the message with some markup and additional information about what happened.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f'#error_report\n'
        f'An exception was raised in runtime\n'
        f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}'
        '</pre>\n\n'
        f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
        f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
        f'<pre>{html.escape(tb_string)}</pre>'
    )

    # Finally, send the message
    logger.info('Sending error report')
    message = (
        f'update = {json.dumps(update_str, indent=2, ensure_ascii=False)}'
        '\n\n'
        f'context.chat_data = {str(context.chat_data)}\n\n'
        f'context.user_data = {str(context.user_data)}\n\n'
        f'{tb_string}'
    )
    string_out = StringIO(message)
    context.bot.send_document(chat_id=DEVELOPER_ID, document=string_out, filename='error_report.txt',
                              caption='#error_report\nAn exception was raised during runtime\n')

    if update:
        error_class_name = ".".join([context.error.__class__.__module__, context.error.__class__.__qualname__])
        update.effective_message.reply_text(f'Error\n{error_class_name}: {str(context.error)}')
