import asyncio
import logging
import base64

from aiogram.types import FSInputFile
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from openai import AsyncOpenAI

from config import (
    BOT_TOKEN,
    OPENAI_API_KEY,
    MODEL_NAME,
    IMAGE_MODEL,
    MAX_HISTORY_MESSAGES,
    CONTEXT_MESSAGES_LIMIT,
    GENERATED_DIR,
    load_prompts,
)
from memory import ChatMemory


logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

prompts_data = load_prompts()
PROMPTS = prompts_data["prompts"]
DEFAULT_MODE = prompts_data["default_prompt"]

memory = ChatMemory(
    max_history=MAX_HISTORY_MESSAGES,
    default_mode=DEFAULT_MODE,
)


def build_modes_keyboard() -> InlineKeyboardMarkup:
    buttons = []

    for mode_key, mode_data in PROMPTS.items():
        buttons.append(
            [
                InlineKeyboardButton(
                    text=mode_data["name"],
                    callback_data=f"mode:{mode_key}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_openai_messages(chat_id: int, user_text: str) -> list[dict]:
    current_mode = memory.get_mode(chat_id)
    system_prompt = PROMPTS[current_mode]["system_prompt"]

    history = memory.get_history(chat_id, limit=CONTEXT_MESSAGES_LIMIT)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    return messages


async def get_ai_response(messages: list[dict]) -> str:
    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
    )

    content = response.choices[0].message.content

    if not content:
        return "Не удалось получить ответ от модели."

    return content.strip()

async def generate_image_file(prompt: str) -> Path:
    response = await client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size="1024x1024",
    )

    image_base64 = response.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    file_path = GENERATED_DIR / filename

    with open(file_path, "wb") as file:
        file.write(image_bytes)

    return file_path

@dp.message(Command("start"))
async def cmd_start(message: Message):
    current_mode = memory.get_mode(message.chat.id)
    mode_name = PROMPTS[current_mode]["name"]

    text = (
        "Привет! Я Telegram-бот с памятью диалога и режимами.\n\n"
        f"Текущий режим: {mode_name}\n\n"
        "Команды:\n"
        "/mode — выбрать режим\n"
        "/reset — очистить память диалога"
    )
    await message.answer(text)

@dp.message(Command("mode"))
async def cmd_mode(message: Message):
    current_mode = memory.get_mode(message.chat.id)
    current_mode_name = PROMPTS[current_mode]["name"]

    lines = ["Выберите режим работы:\n"]

    for mode_key, mode_data in PROMPTS.items():
        prefix = "•"
        if mode_key == current_mode:
            prefix = "✅"

        lines.append(
            f"{prefix} {mode_data['name']}\n{mode_data['description']}\n"
        )

    text = "\n".join(lines)
    text += f"\nТекущий режим: {current_mode_name}"

    await message.answer(text, reply_markup=build_modes_keyboard())    


@dp.callback_query(F.data.startswith("mode:"))
async def process_mode_change(callback: CallbackQuery):
    if callback.message is None:
        await callback.answer("Ошибка: сообщение недоступно.", show_alert=True)
        return

    chat_id = callback.message.chat.id
    mode_key = callback.data.split(":", 1)[1]

    if mode_key not in PROMPTS:
        await callback.answer("Неизвестный режим.", show_alert=True)
        return

    memory.set_mode(chat_id, mode_key)

    current_mode_name = PROMPTS[mode_key]["name"]

    lines = ["Выберите режим работы:\n"]

    for key, mode_data in PROMPTS.items():
        prefix = "•"
        if key == mode_key:
            prefix = "✅"

        lines.append(
            f"{prefix} {mode_data['name']}\n{mode_data['description']}\n"
        )

    text = "\n".join(lines)
    text += f"\nТекущий режим: {current_mode_name}"

    await callback.message.edit_text(
        text,
        reply_markup=build_modes_keyboard()        
    )

    await callback.answer("Режим обновлён.")


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    memory.reset_history(message.chat.id)
    await message.answer("Память диалога очищена.")


@dp.message(Command("image"))
async def cmd_image(message: Message):
    user_text = message.text or ""
    prompt = user_text.replace("/image", "", 1).strip()

    if not prompt:
        await message.answer(
            "Напиши промпт после команды.\n\n"
            "Пример:\n"
            "/image futuristic AI assistant inside Telegram, holographic chat window, neural connections, dark premium background, glowing interface, cyber style, realistic digital art, blue and purple neon lighting, high detail, elegant composition, modern developer aesthetic, no text"
        )
        return

    await message.answer("Генерирую изображение...")

    try:
        image_path = await generate_image_file(prompt)

        logging.info("Изображение сохранено: %s", image_path)

        if not image_path.exists():
            await message.answer("Файл изображения не был создан.")
            return

        photo = FSInputFile(str(image_path))

        await message.answer_photo(
            photo=photo,
            caption=f"Изображение по промпту:\n{prompt}"
        )

    except Exception as error:
        logging.exception("Ошибка при генерации изображения")
        await message.answer(
            "Не удалось сгенерировать изображение.\n\n"
            f"Ошибка: {error}"
        )  


@dp.message(F.text)
async def handle_message(message: Message):
    chat_id = message.chat.id
    user_text = message.text.strip()

    if not user_text:
        await message.answer("Пожалуйста, отправь текстовое сообщение.")
        return

    try:
        messages = build_openai_messages(chat_id, user_text)
        answer = await get_ai_response(messages)

        memory.add_message(chat_id, "user", user_text)
        memory.add_message(chat_id, "assistant", answer)

        await message.answer(answer)

    except Exception as error:
        logging.exception("Ошибка при обработке сообщения")
        await message.answer(f"Произошла ошибка: {error}")


async def main():
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())