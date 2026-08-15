"""Main handlers for /start, /help, /cancel commands and menu navigation."""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.db.models import User
from app.bot.keyboards.inline import get_main_menu_keyboard, get_back_to_menu_keyboard
from app.bot.keyboards.callbacks import NavigationCallback
from app.bot.states import CreateReminderStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User):
    """Handle /start command with a beautiful greeting and main menu."""
    await state.clear()
    name = user.first_name or "друг"
    greeting = (
        f"👋 <b>Привет, {name}!</b>\n\n"
        f"Я твой умный персональный помощник для напоминаний.\n\n"
        f"💡 <b>Как мной пользоваться?</b>\n"
        f"Просто напиши мне любой текст, например:\n"
        f"• <i>«завтра в 15:00 позвонить маме»</i>\n"
        f"• <i>«через 30 минут выключить духовку»</i>\n"
        f"• <i>«каждый день в 20:00 принимать витамины»</i>\n"
        f"• <i>«каждую пятницу в 18:30 проверить отчёт»</i>\n\n"
        f"Воспользуйся кнопками ниже для управления напоминаниями:"
    )
    await message.answer(greeting, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command with detailed usage examples."""
    help_text = (
        "❓ <b>СПРАВКА И ПРИМЕРЫ</b>\n\n"
        "Бот понимает естественную речь на русском языке. Вам не нужно изучать сложные команды!\n\n"
        "<b>Примеры разовых напоминаний:</b>\n"
        "• «через 15 минут»\n"
        "• «завтра в 8:30 купить хлеб»\n"
        "• «послезавтра в 14:00 встреча»\n"
        "• «в понедельник в 19:30 спортзал»\n"
        "• «16 августа в 10:00 забрать заказ»\n\n"
        "<b>Примеры повторяющихся напоминаний:</b>\n"
        "• «каждый день в 09:00 зарядка»\n"
        "• «каждый будний день в 8:30 вставать»\n"
        "• «каждую субботу в 12:00 уборка»\n"
        "• «каждое 1 число месяца в 10:00 оплатить интернет»\n"
        "• «каждые 2 часа пить воду»\n\n"
        "<b>Контекстные действия:</b>\n"
        "• Напишите <i>«перенеси на завтра»</i>, чтобы перенести последнее напоминание.\n\n"
        "<b>Основные команды:</b>\n"
        "/start — Главное меню\n"
        "/list — Мои активные напоминания\n"
        "/today — Напоминания на сегодня\n"
        "/repeat — Повторяющиеся задачи\n"
        "/settings — Настройки часового пояса и тихих часов\n"
        "/cancel — Отменить текущий ввод"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_back_to_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current FSM input."""
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=get_main_menu_keyboard())


@router.callback_query(NavigationCallback.filter(F.target == "main_menu"))
async def nav_main_menu(call: CallbackQuery, state: FSMContext, user: User):
    """Return to main menu via callback instantly acknowledging callback query."""
    await call.answer()
    await state.clear()
    name = user.first_name or "друг"
    text = f"🏠 <b>Главное меню</b>\n\nЧем могу помочь, {name}?"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())


@router.callback_query(NavigationCallback.filter(F.target == "help"))
async def nav_help(call: CallbackQuery):
    """Show help screen via callback instantly acknowledging callback query."""
    await call.answer()
    help_text = (
        "❓ <b>СПРАВКА</b>\n\n"
        "Просто отправьте текст бота, например:\n"
        "• <i>«завтра в 10:00 позвонить врачу»</i>\n"
        "• <i>«по будням в 08:00 подъем»</i>\n\n"
        "Используйте кнопки меню для управления."
    )
    await call.message.edit_text(help_text, parse_mode="HTML", reply_markup=get_back_to_menu_keyboard())


@router.callback_query(NavigationCallback.filter(F.target == "create"))
async def nav_create(call: CallbackQuery, state: FSMContext):
    """Prompt user to write a reminder text instantly acknowledging callback query."""
    await call.answer()
    await state.set_state(CreateReminderStates.waiting_for_text)
    msg = (
        "✍️ <b>Напишите напоминание</b>\n\n"
        "Например:\n"
        "<i>«Завтра в 15:00 позвонить маме»</i> или <i>«Через 20 минут проверить духовку»</i>"
    )
    await call.message.edit_text(msg, parse_mode="HTML", reply_markup=get_back_to_menu_keyboard())
