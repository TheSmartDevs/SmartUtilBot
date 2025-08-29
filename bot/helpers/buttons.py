from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LoginUrl, CallbackGame
from ..helpers import LOGGER

class SmartButtons:
    def __init__(self):
        self._button = []
        self._header_button = []
        self._footer_button = []

    def button(self, text, callback_data=None, url=None, web_app=None, login_url=None, user_id=None, switch_inline_query=None, switch_inline_query_current_chat=None, callback_game=None, copy_text=None, position=None):
        kwargs = {}
        if callback_data is not None:
            kwargs["callback_data"] = callback_data
        elif url is not None:
            kwargs["url"] = url
        elif web_app is not None:
            kwargs["web_app"] = web_app
        elif login_url is not None:
            kwargs["login_url"] = login_url
        elif user_id is not None:
            kwargs["user_id"] = user_id
        elif switch_inline_query is not None:
            kwargs["switch_inline_query"] = switch_inline_query
        elif switch_inline_query_current_chat is not None:
            kwargs["switch_inline_query_current_chat"] = switch_inline_query_current_chat
        elif callback_game is not None:
            kwargs["callback_game"] = callback_game
        elif copy_text is not None:
            kwargs["copy_text"] = copy_text
        else:
            LOGGER.error("At least one optional parameter must be provided for InlineKeyboardButton")
            return
        button = InlineKeyboardButton(text=text, **kwargs)
        if not position:
            self._button.append(button)
        elif position == "header":
            self._header_button.append(button)
        elif position == "footer":
            self._footer_button.append(button)

    def build_menu(self, b_cols=1, h_cols=8, f_cols=8):
        menu = [self._button[i:i + b_cols] for i in range(0, len(self._button), b_cols)]
        if self._header_button:
            h_cnt = len(self._header_button)
            if h_cnt > h_cols:
                header_buttons = [self._header_button[i:i + h_cols] for i in range(0, len(self._header_button), h_cols)]
                menu = header_buttons + menu
            else:
                menu.insert(0, self._header_button)
        if self._footer_button:
            if len(self._footer_button) > f_cols:
                [menu.append(self._footer_button[i:i + f_cols]) for i in range(0, len(self._footer_button), f_cols)]
            else:
                menu.append(self._footer_button)
        return InlineKeyboardMarkup(menu)

    def reset(self):
        self._button = []
        self._header_button = []
        self._footer_button = []