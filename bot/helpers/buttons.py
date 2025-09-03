from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
from bot.helpers.logger import LOGGER

class SmartButtons:
    def __init__(self):
        self._button = []
        self._header_button = []
        self._footer_button = []

    def button(self, text, callback_data=None, url=None, pay=None, web_app=None, login_url=None, 
               switch_inline_query=None, switch_inline_query_current_chat=None, 
               switch_inline_query_chosen_chat=None, copy_text=None, callback_game=None, position=None):
        kwargs = {}
        if callback_data is not None:
            kwargs["callback_data"] = callback_data
        if url is not None:
            kwargs["url"] = url
        if pay is not None:
            kwargs["pay"] = pay
        if web_app is not None:
            kwargs["web_app"] = web_app
        if login_url is not None:
            kwargs["login_url"] = login_url
        if switch_inline_query is not None:
            kwargs["switch_inline_query"] = switch_inline_query
        if switch_inline_query_current_chat is not None:
            kwargs["switch_inline_query_current_chat"] = switch_inline_query_current_chat
        if switch_inline_query_chosen_chat is not None:
            kwargs["switch_inline_query_chosen_chat"] = switch_inline_query_chosen_chat
        if copy_text is not None:
            if isinstance(copy_text, str):
                kwargs["copy_text"] = CopyTextButton(text=copy_text)
            else:
                kwargs["copy_text"] = copy_text
        if callback_game is not None:
            kwargs["callback_game"] = callback_game

        try:
            button = InlineKeyboardButton(text=text, **kwargs)
        except Exception as e:
            LOGGER.error(f"Failed to create InlineKeyboardButton: {e}")
            raise

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
        return InlineKeyboardMarkup(inline_keyboard=menu)

    def reset(self):
        self._button = []
        self._header_button = []
        self._footer_button = []
