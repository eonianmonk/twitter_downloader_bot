import requests
from typing import List, Optional
from telegram import Update, InputMediaDocument, constants, InlineQueryResultArticle,InputMessageContent,InlineQueryResultVideo
from log import log_handling
from telegram.ext import CallbackContext
try:
    import re2 as re
except ImportError:
    import re
import telegram.error
from tempfile import TemporaryFile
from urllib.parse import urlsplit

def extract_tweet_ids(update: Update) -> Optional[list[str]]:
    """Extract tweet IDs from message."""
    if update.effective_message is not None:
        text = update.effective_message.text
    elif update.inline_query.query is not None:
        text = update.inline_query.query
        
    # For t.co links
    unshortened_links = ''
    for link in re.findall(r"t\.co\/[a-zA-Z0-9]+", text):
        try:
            unshortened_link = requests.get('https://' + link).url
            unshortened_links += '\n' + unshortened_link
            log_handling(update, 'info', f'Unshortened t.co link [https://{link} -> {unshortened_link}]')
        except:
            log_handling(update, 'info', f'Could not unshorten link [https://{link}]')

    # Parse IDs from received text
    tweet_ids = re.findall(r"(?:twitter|x)\.com/.{1,15}/(?:web|status(?:es)?)/([0-9]{1,20})", text + unshortened_links)
    tweet_ids = list(dict.fromkeys(tweet_ids))
    return tweet_ids or None


def scrape_media(tweet_id: int) -> list[dict]:
    r = requests.get(f'https://api.vxtwitter.com/Twitter/status/{tweet_id}')
    r.raise_for_status()
    return r.json()['media_extended']


def reply_media(update: Update, context: CallbackContext, tweet_media: list) -> bool:
    """Reply to message with supported media."""
    photos = [media for media in tweet_media if media["type"] == "image"]
    gifs = [media for media in tweet_media if media["type"] == "gif"]
    videos = [media for media in tweet_media if media["type"] == "video"]
    if photos:
        reply_photos(update, context, photos)
    if gifs:
        reply_gifs(update, context, gifs)
    elif videos:
        reply_videos(update, context, videos)
    return bool(photos or gifs or videos)


def reply_photos(update: Update, context: CallbackContext, twitter_photos: list[dict]) -> None:
    """Reply with photo group."""
    photo_group = []
    for photo in twitter_photos:
        photo_url = photo['url']
        log_handling(update, 'info', f'Photo[{len(photo_group)}] url: {photo_url}')
        parsed_url = urlsplit(photo_url)

        # Try changing requested quality to 'orig'
        try:
            new_url = parsed_url._replace(query='format=jpg&name=orig').geturl()
            log_handling(update, 'info', 'New photo url: ' + new_url)
            requests.head(new_url).raise_for_status()
            photo_group.append(InputMediaDocument(media=new_url))
        except requests.HTTPError:
            log_handling(update, 'info', 'orig quality not available, using original url')
            photo_group.append(InputMediaDocument(media=photo_url))
    update.effective_message.reply_media_group(photo_group, quote=True)
    log_handling(update, 'info', f'Sent photo group (len {len(photo_group)})')
    context.bot_data['stats']['media_downloaded'] += len(photo_group)


def reply_gifs(update: Update, context: CallbackContext, twitter_gifs: list[dict]):
    """Reply with GIF animations."""
    for gif in twitter_gifs:
        gif_url = gif['url']
        log_handling(update, 'info', f'Gif url: {gif_url}')
        update.effective_message.reply_animation(animation=gif_url, quote=True)
        log_handling(update, 'info', 'Sent gif')
        context.bot_data['stats']['media_downloaded'] += 1


def inline_videos(update:Update,context: CallbackContext, twitter_videos: list[dict]) -> List[InlineQueryResultArticle]:
    articles = []
    for video in twitter_videos:
        video_url = video['url'] # 'https://video.twimg.com/ext_tw_video/1781026478945177600/pu/vid/avc1/1280x720/HFcgiEB20ArXRrcU.mp4?tag=12'
        id = video_url.split('/')[-1].split('.')[0]
        try:
            request = requests.get(video_url, stream=True)
            request.raise_for_status()
            if (video_size := int(request.headers['Content-Length'])) <= constants.MAX_FILESIZE_DOWNLOAD:
                # Try sending by url
                articles.append(InlineQueryResultVideo(
                    id=id,
                    video_url=video_url,
                    thumb_url=video['thumbnail_url'],
                    mime_type='video/mp4',
                    #input_message_content=InputMediaDocument(media=video_url)
                    caption=video_url,
                    title=video_url,
                    description=video_url
                    ))
            else:
                log_handling(update, 'info', 'Video is too large, sending direct link')
                
        except (requests.HTTPError, KeyError, telegram.error.BadRequest, requests.exceptions.ConnectionError) as exc:
            log_handling(update, 'info', f'{exc.__class__.__qualname__} IQ: {exc}')
            log_handling(update, 'info', 'Error occurred when trying to send video, sending direct link')
            
        context.bot_data['stats']['media_downloaded'] += 1
    return articles
            

    return


def reply_videos(update: Update, context: CallbackContext, twitter_videos: list[dict]):
    """Reply with videos."""
    for video in twitter_videos:
        video_url = video['url']
        try:
            request = requests.get(video_url, stream=True)
            request.raise_for_status()
            if (video_size := int(request.headers['Content-Length'])) <= constants.MAX_FILESIZE_DOWNLOAD:
                # Try sending by url
                update.effective_message.reply_video(video=video_url, quote=True)
                log_handling(update, 'info', 'Sent video (download)')
            elif video_size <= constants.MAX_FILESIZE_UPLOAD:
                log_handling(update, 'info', f'Video size ({video_size}) is bigger than '
                                            f'MAX_FILESIZE_UPLOAD, using upload method')
                message = update.effective_message.reply_text(
                    'Video is too large for direct download\nUsing upload method '
                    '(this might take a bit longer)',
                    quote=True)
                with TemporaryFile() as tf:
                    log_handling(update, 'info', f'Downloading video (Content-length: '
                                                f'{request.headers["Content-length"]})')
                    for chunk in request.iter_content(chunk_size=128):
                        tf.write(chunk)
                    log_handling(update, 'info', 'Video downloaded, uploading to Telegram')
                    tf.seek(0)
                    update.effective_message.reply_video(video=tf, quote=True, supports_streaming=True)
                    log_handling(update, 'info', 'Sent video (upload)')
                message.delete()
            else:
                log_handling(update, 'info', 'Video is too large, sending direct link')
                update.effective_message.reply_text(f'Video is too large for Telegram upload. Direct video link:\n'
                                        f'{video_url}', quote=True)
        except (requests.HTTPError, KeyError, telegram.error.BadRequest, requests.exceptions.ConnectionError) as exc:
            log_handling(update, 'info', f'{exc.__class__.__qualname__}: {exc}')
            log_handling(update, 'info', 'Error occurred when trying to send video, sending direct link')
            update.effective_message.reply_text(f'Error occurred when trying to send video. Direct link:\n'
                                    f'{video_url}', quote=True)
        context.bot_data['stats']['media_downloaded'] += 1
