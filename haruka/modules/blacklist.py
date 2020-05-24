import html
import re
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, ParseMode
from telegram.error import BadRequest
from telegram.ext import CommandHandler, MessageHandler, Filters, run_async

import haruka.modules.sql.blacklist_sql as sql
from haruka import dispatcher, LOGGER
from haruka.modules.disable import DisableAbleCommandHandler
from haruka.modules.helper_funcs.chat_status import user_admin, user_not_admin
from haruka.modules.helper_funcs.extraction import extract_text
from haruka.modules.helper_funcs.misc import split_message

from haruka.modules.connection import connected

from haruka.modules.translations.strings import tld

BLACKLIST_GROUP = 11


@run_async
def blacklist(bot: Bot, update: Update, args: List[str]):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    
    conn = connected(bot, update, chat, user.id, need_admin=False)
    if not conn == False:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            exit(1)
        else:
            chat_id = update.effective_chat.id
            chat_name = chat.title
    
    filter_list = tld(chat.id, "<b>Current blacklisted words in {}:</b>\n").format(chat_name)

    all_blacklisted = sql.get_chat_blacklist(chat_id)

    if len(args) > 0 and args[0].lower() == 'copy':
        for trigger in all_blacklisted:
            filter_list += "<code>{}</code>\n".format(html.escape(trigger))
    else:
        for trigger in all_blacklisted:
            filter_list += " • <code>{}</code>\n".format(html.escape(trigger))

    split_text = split_message(filter_list)
    for text in split_text:
        if filter_list == tld(chat.id, "<b>Current blacklisted words in {}:</b>\n").format(chat_name): #We need to translate
            msg.reply_text(tld(chat.id, "There are no blacklisted messages in <b>{}</b>!").format(chat_name), parse_mode=ParseMode.HTML)
            return
        msg.reply_text(text, parse_mode=ParseMode.HTML)


@run_async
@user_admin
def add_blacklist(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    words = msg.text.split(None, 1)

    conn = connected(bot, update, chat, user.id)
    if not conn == False:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            exit(1)
        else:
            chat_name = chat.title

    if len(words) > 1:
        text = words[1]
        to_blacklist = list(set(trigger.strip() for trigger in text.split("\n") if trigger.strip()))
        for trigger in to_blacklist:
            sql.add_to_blacklist(chat_id, trigger.lower())

        if len(to_blacklist) == 1:
            msg.reply_text(tld(chat.id, "Added <code>{}</code> to the blacklist in <b>{}</b>!").format(html.escape(to_blacklist[0]), chat_name),
                           parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(tld(chat.id, 
             "Added <code>{}</code> to the blacklist in <b>{}</b>!").format(len(to_blacklist)), chat_name, parse_mode=ParseMode.HTML)

    else:
        msg.reply_text(tld(chat.id, "Tell me what words you would like to add to the blacklist."))


@run_async
@user_admin
def unblacklist(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    words = msg.text.split(None, 1)

    conn = connected(bot, update, chat, user.id)
    if not conn == False:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            exit(1)
        else:
            chat_name = chat.title

    if len(words) > 1:
        text = words[1]
        to_unblacklist = list(set(trigger.strip() for trigger in text.split("\n") if trigger.strip()))
        successful = 0
        for trigger in to_unblacklist:
            success = sql.rm_from_blacklist(chat_id, trigger.lower())
            if success:
                successful += 1

        if len(to_unblacklist) == 1:
            if successful:
                msg.reply_text(tld(chat.id, "Removed <code>{}</code> from the blacklist in <b>{}</b>!").format(html.escape(to_unblacklist[0]), chat_name),
                               parse_mode=ParseMode.HTML)
            else:
                msg.reply_text(tld(chat.id, "This isn't a blacklisted trigger...!"))

        elif successful == len(to_unblacklist):
            msg.reply_text(tld(chat.id, 
                "Removed <code>{}</code> triggers from the blacklist in <b>{}</b>!").format(
                    successful, chat_name), parse_mode=ParseMode.HTML)

        elif not successful:
            msg.reply_text(tld(chat.id, 
                "None of these triggers were exist, so they weren't removed.").format(
                    successful, len(to_unblacklist) - successful), parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(tld(chat.id, 
                "Removed <code>{}</code> triggers from the blacklist in <b>{}</b>! {} did not exist, "
                "so were not removed.").format(successful, chat_name, len(to_unblacklist) - successful),
                parse_mode=ParseMode.HTML)
    else:
        msg.reply_text(tld(chat.id, "Tell me what words you would like to remove from the blacklist."))


@run_async
@user_not_admin
def del_blacklist(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    to_match = extract_text(message)
    if not to_match:
        return

    chat_filters = sql.get_chat_blacklist(chat.id)
    for trigger in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(trigger) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            try:
                message.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    LOGGER.exception("Error while deleting blacklist message.")
            break


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(bot, update, chat, chatP, user):
    blacklisted = sql.num_blacklist_chat_filters(chat.id)
    return "There are {} blacklisted words.".format(blacklisted)


def __stats__():
    return "{} blacklist triggers, across {} chats.".format(sql.num_blacklist_filters(),
                                                            sql.num_blacklist_filter_chats())
import html

from telegram import Bot, ParseMode, Update
from telegram.error import BadRequest
from telegram.ext import CommandHandler, Filters, MessageHandler, run_async

import tldextract
from haruka import LOGGER, dispatcher
from haruka.modules.disable import DisableAbleCommandHandler
from haruka.modules.helper_funcs.chat_status import user_admin, user_not_admin
from haruka.modules.sql import urlblacklist_sql as sql


@run_async
@user_admin
def add_blacklist_url(bot: Bot, update: Update):
    chat = update.effective_chat
    message = update.effective_message
    urls = message.text.split(None, 1)
    if len(urls) > 1:
        urls = urls[1]
        to_blacklist = list(set(uri.strip()
                                for uri in urls.split("\n") if uri.strip()))
        blacklisted = []

        for uri in to_blacklist:
            extract_url = tldextract.extract(uri)
            if extract_url.domain and extract_url.suffix:
                blacklisted.append(extract_url.domain + "." + extract_url.suffix)
                sql.blacklist_url(chat.id, extract_url.domain + "." + extract_url.suffix)

        if len(to_blacklist) == 1:
            extract_url = tldextract.extract(to_blacklist[0])
            if extract_url.domain and extract_url.suffix:
                message.reply_text(
                    "Added <code>{}</code> domain to the blacklist!".format(
                        html.escape(
                            extract_url.domain + "." + extract_url.suffix)),
                    parse_mode=ParseMode.HTML)
            else:
                message.reply_text(
                    "You are trying to blacklist an invalid url")
        else:
            message.reply_text(
                "Added <code>{}</code> domains to the blacklist.".format(
                    len(blacklisted)), parse_mode=ParseMode.HTML)
    else:
        message.reply_text(
            "Tell me which urls you would like to add to the blacklist.")


@run_async
@user_admin
def rm_blacklist_url(bot: Bot, update: Update):
    chat = update.effective_chat
    message = update.effective_message
    urls = message.text.split(None, 1)

    if len(urls) > 1:
        urls = urls[1]
        to_unblacklist = list(set(uri.strip()
                                  for uri in urls.split("\n") if uri.strip()))
        unblacklisted = 0
        for uri in to_unblacklist:
            extract_url = tldextract.extract(uri)
            success = sql.rm_url_from_blacklist(chat.id, extract_url.domain + "." + extract_url.suffix)
            if success:
                unblacklisted += 1

        if len(to_unblacklist) == 1:
            if unblacklisted:
                message.reply_text(
                    "Removed <code>{}</code> from the blacklist!".format(
                        html.escape(
                            to_unblacklist[0])),
                    parse_mode=ParseMode.HTML)
            else:
                message.reply_text("This isn't a blacklisted domain...!")
        elif unblacklisted == len(to_unblacklist):
            message.reply_text(
                "Removed <code>{}</code> domains from the blacklist.".format(
                    unblacklisted), parse_mode=ParseMode.HTML)
        elif not unblacklisted:
            message.reply_text(
                "None of these domains exist, so they weren't removed.",
                parse_mode=ParseMode.HTML)
        else:
            message.reply_text(
                "Removed <code>{}</code> domains from the blacklist. {} did not exist, "
                "so were not removed.".format(
                    unblacklisted,
                    len(to_unblacklist) - unblacklisted),
                parse_mode=ParseMode.HTML)
    else:
        message.reply_text(
            "Tell me which domains you would like to remove from the blacklist.")


@run_async
@user_not_admin
def del_blacklist_url(bot: Bot, update: Update):
    chat = update.effective_chat
    message = update.effective_message
    parsed_entities = message.parse_entities(types=["url"])
    extracted_domains = []
    for obj, url in parsed_entities.items():
        extract_url = tldextract.extract(url)
        extracted_domains.append(extract_url.domain + "." + extract_url.suffix)
    for url in sql.get_blacklisted_urls(chat.id):
        if url in extracted_domains:
            try:
                message.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    LOGGER.exception("Error while deleting blacklist message.")
            break


@run_async
def get_blacklisted_urls(bot: Bot, update: Update):
    chat = update.effective_chat
    message = update.effective_message

    base_string = "Current <b>blacklisted</b> domains:\n"
    blacklisted = sql.get_blacklisted_urls(chat.id)

    if not blacklisted:
        message.reply_text("There are no blacklisted domains here!")
        return
    for domain in blacklisted:
        base_string += "- <code>{}</code>\n".format(domain)

    message.reply_text(base_string, parse_mode=ParseMode.HTML)


URL_BLACKLIST_HANDLER = DisableAbleCommandHandler(
    "blacklist",
    add_blacklist_url,
    filters=Filters.group,
    pass_args=True,
    admin_ok=True)
ADD_URL_BLACKLIST_HANDLER = CommandHandler(
    "addurl", add_blacklist_url, filters=Filters.group)

RM_BLACKLIST_URL_HANDLER = CommandHandler(
    "delurl", rm_blacklist_url, filters=Filters.group)

GET_BLACKLISTED_URLS = CommandHandler(
    "geturl",
    get_blacklisted_urls,
    filters=Filters.group)

URL_DELETE_HANDLER = MessageHandler(
    Filters.entity("url"),
    del_blacklist_url,
    edited_updates=True)


dispatcher.add_handler(URL_BLACKLIST_HANDLER)
dispatcher.add_handler(ADD_URL_BLACKLIST_HANDLER)
dispatcher.add_handler(RM_BLACKLIST_URL_HANDLER)
dispatcher.add_handler(GET_BLACKLISTED_URLS)
dispatcher.add_handler(URL_DELETE_HANDLER)


__mod_name__ = "Blacklists"

__help__ = """
You can set blacklist filters to take automatic action on people when they say certain things. This is done using:
 - /addblacklist <blacklist trigger> <blacklist reason>: blacklists the trigger. You can set sentences by putting quotes around the reason.
 - /unblacklist <blacklist trigger>: stop blacklisting a certain blacklist trigger.
 - /rmblacklist <blacklist trigger>: same as /unblacklist
 - /blacklist: list all active blacklist filters

/addblacklist "the admins suck" Respect your admins!
This would delete any message containing 'the admins suck'.
If you've enabled an alternative blacklist mode, it will warn, ban, kick, or mute a user with a message specifying the reason.

Top tip:
Blacklists allow you to use some modifiers to match "unknown" characters. For example, you can use the ? character to match a single occurence of any non-whitespace character.
You could also use the * modifier, which matches any number of any character. If you want to blacklist urls, this will allow you to match the full thing. It matches every character except spaces. This is cool if you want to stop, for example, url shorteners.
For example, the following will ban any bit.ly link:
/addblacklist "bit.ly/*" We dont like shorteners!
If you wanted to only match bit.ly/ links followed by three characters, you could use:
/addblacklist "bit.ly/???" We dont like shorteners!
This would match bit.ly/abc, but not bit.ly/abcd.


Domain blacklisting is used to stop certain domains from being mentioned in a group, Any time an url on that domain is mentioned, /
the message will immediately be deleted.

*NOTE:* domain blacklisting do not affect group admins.

- /geturl: View the current blacklisted urls

*Admin only:*

- /addurl <urls>: Add a domain to the blacklist. The bot will automatically parse the url.
- /delurl <urls>: Remove urls from the blacklist

"""

BLACKLIST_HANDLER = DisableAbleCommandHandler("blacklist", blacklist, pass_args=True, admin_ok=True)
ADD_BLACKLIST_HANDLER = CommandHandler("addblacklist", add_blacklist)
UNBLACKLIST_HANDLER = CommandHandler(["unblacklist", "rmblacklist"], unblacklist)
BLACKLIST_DEL_HANDLER = MessageHandler(
    (Filters.text | Filters.command | Filters.sticker | Filters.photo) & Filters.group, del_blacklist, edited_updates=True)

dispatcher.add_handler(BLACKLIST_HANDLER)
dispatcher.add_handler(ADD_BLACKLIST_HANDLER)
dispatcher.add_handler(UNBLACKLIST_HANDLER)
dispatcher.add_handler(BLACKLIST_DEL_HANDLER, group=BLACKLIST_GROUP)
