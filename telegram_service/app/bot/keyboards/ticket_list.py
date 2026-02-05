from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def ticket_list_filters(*, show_search: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Все", callback_data="adm:list:filter=all:page=0"),
            InlineKeyboardButton(text="Активные", callback_data="adm:list:filter=active:page=0"),
            InlineKeyboardButton(text="Повторы", callback_data="adm:list:filter=repeat:page=0"),
        ]
    ]
    if show_search:
        rows.append([InlineKeyboardButton(text="🔎 Поиск", callback_data="adm:search:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ticket_list_items(ticket_ids: list[int]) -> list[list[InlineKeyboardButton]]:
    return [
        [InlineKeyboardButton(text=f"Открыть #{ticket_id}", callback_data=f"ticket:{ticket_id}")]
        for ticket_id in ticket_ids
    ]


def ticket_list_keyboard(
    *,
    ticket_ids: list[int],
    page: int,
    total_pages: int,
    filter_key: str,
    search_mode: bool,
) -> InlineKeyboardMarkup:
    rows = ticket_list_items(ticket_ids)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=_list_callback(filter_key, page - 1, search_mode)))
    nav.append(InlineKeyboardButton(text="🔄", callback_data=_list_callback(filter_key, page, search_mode)))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=_list_callback(filter_key, page + 1, search_mode)))
    if nav:
        rows.append(nav)
    if search_mode:
        rows.append([InlineKeyboardButton(text="🗂 К списку", callback_data="adm:search:back")])
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:list:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def worker_closed_keyboard(
    *,
    ticket_buttons: list[tuple[int, str]],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Открыть #{ticket_label}", callback_data=f"closed_open:{ticket_id}")]
        for ticket_id, ticket_label in ticket_buttons
    ]
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"wrk:closed:page={page - 1}"))
    nav.append(InlineKeyboardButton(text="🔄", callback_data=f"wrk:closed:page={page}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"wrk:closed:page={page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="wrk:closed:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _list_callback(filter_key: str, page: int, search_mode: bool) -> str:
    if search_mode:
        return f"adm:search:page={page}"
    return f"adm:list:filter={filter_key}:page={page}"


def ticket_actions(ticket_id: int, can_cancel: bool) -> InlineKeyboardMarkup:
    buttons = []
    if can_cancel:
        buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data=f"ticket_cancel:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else InlineKeyboardMarkup(inline_keyboard=[])
