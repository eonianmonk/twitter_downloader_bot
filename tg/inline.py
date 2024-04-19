import traceback
from io import StringIO
from typing import List
from telegram import *
from telegram.ext import Updater, CallbackContext, InlineQueryHandler,Filters,BaseFilter

from log import log_handling,logger,error_handler
from twitter import extract_tweet_ids, reply_media,scrape_media,inline_videos

def inline_reply_media(update: Update, context:CallbackContext, tweet_media: list) -> List[InlineQueryResultArticle]:
    #photos = [media for media in tweet_media if media["type"] == "image"]
    #gifs = [media for media in tweet_media if media["type"] == "gif"]
    videos = [media for media in tweet_media if media["type"] == "video"]

    if not videos:
        return []

    return inline_videos(update, context, videos)


def error_result(msg: str) -> List[InlineQueryResultArticle]:
    return []

def inline_dl_twitter_video(update: Update, context: CallbackContext) -> None:
    if tweet_ids := extract_tweet_ids(update):
        log_handling(update, 'info', f'Found Tweet IDs {tweet_ids} in message')
    else:
        log_handling(update, 'info', 'No supported tweet link found')
        update.inline_query.answer(error_result('No supported tweet link found'))
        return []
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
                found = inline_reply_media(update, context, media)
                if found:
                    found_media = True
                    update.inline_query.answer(found)
                    return found
                else:
                    log_handling(update, 'info', f'Found unsupported media: {media[0]["type"]}')
            else:
                log_handling(update, 'info', f'Tweet {tweet_id} has no media')
                update.inline_query.answer(f'Tweet {tweet_id} has no media')
        except Exception:
            log_handling(update, 'error', f'Error occurred when scraping tweet {tweet_id}: {traceback.format_exc()}')
            update.inline_query.answer(error_result(f'Error handling tweet {tweet_id}'))
            return []
            
    return []

def inline_handlers() -> List[InlineQueryHandler]:
    return [InlineQueryHandler(callback=inline_dl_twitter_video)] #,pattern=r"(?:twitter|x)\.com/.{1,15}/(?:web|status(?:es)?)/([0-9]{1,20})")]