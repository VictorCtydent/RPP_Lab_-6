from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, Filters, Updater
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
import logging
import psycopg2
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

logger = logging.getLogger(__name__)

CURRENCY, RATE = range(2)
currency_dict = {}
AMOUNT = ''


def help(update, context):
    update.message.reply_text(
        'Доступные команды:\n/save_currency - сохранить курс валюты\n/convert - конвертировать валюту')


def start(update, context):
    user = update.effective_user
    if is_admin(user.id):
        commands = ['/start', '/manage_currency', '/get_currencies', '/convert']
    else:
        commands = ['/start', '/get_currencies', '/convert']

    reply_markup = ReplyKeyboardMarkup([[command] for command in commands], one_time_keyboard=True)
    message = "Доступные команды:"
    update.message.reply_text(message, reply_markup=reply_markup)


def save_currency(update, context):
    currency = update.message.text
    context.user_data['currency'] = currency
    update.message.reply_text('Введите курс валюты к рублю:')
    return RATE


def save_rate(update, context):
    rate = update.message.text
    currency = context.user_data['currency']
    currency_dict[currency] = rate
    update.message.reply_text(f'Курс {currency} сохранен: {rate}')
    return ConversationHandler.END


conv_handler_save = ConversationHandler(
    entry_points=[CommandHandler('save_currency', start)],
    states={
        CURRENCY: [MessageHandler(Filters.text & ~Filters.command, save_currency)],
        RATE: [MessageHandler(Filters.text & ~Filters.command, save_rate)],
    },
    fallbacks=[],
)


def get_currency_rate(update, context):
    currency = update.message.text
    connection = psycopg2.connect(host="localhost", database="RPP_6", user="postgres", password="postgres")
    cursor = connection.cursor()
    cursor.execute("SELECT rate FROM currencies WHERE currency_name = %s", (currency,))
    result = cursor.fetchone()
    if result:
        rate = float(result[0])
        context.user_data['currency'] = currency
        context.user_data['rate'] = rate
        update.message.reply_text('Введите сумму:')
        return AMOUNT
    else:
        update.message.reply_text('Данная валюта не найдена')
        return ConversationHandler.END


def convert_currency(update, context):
    amount = float(update.message.text)
    currency = context.user_data['currency']
    rate = context.user_data['rate']
    converted_amount = round(amount * rate, 2)
    update.message.reply_text(f'{amount} {currency} = {converted_amount} RUB')
    return ConversationHandler.END


def cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Конвертация отменена.',
                              reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


def manage_currency(update, context):
    chat_id = update.effective_chat.id
    # Проверка наличия пользователя в таблице admins
    if is_admin(chat_id):
        # Отображение кнопок "Добавить валюту", "Удалить валюту" и "Изменить курс валюты"
        keyboard = [
            [InlineKeyboardButton("Добавить валюту", callback_data='add_currency')],
            [InlineKeyboardButton("Удалить валюту", callback_data='delete_currency')],
            [InlineKeyboardButton("Изменить курс валюты", callback_data='change_currency_rate')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Выберите действие:', reply_markup=reply_markup)
    else:
        update.message.reply_text('Нет доступа к команде')


def change_currency_rate_callback(update, context):
    query = update.callback_query
    query.answer()
    query.message.reply_text('Введите название валюты:')
    return 'change_currency_rate'


def change_currency_rate(update, context):
    currency = update.message.text
    # Проверка наличия валюты в таблице currencies
    if is_currency_exist(currency):
        context.user_data['currency'] = currency
        update.message.reply_text('Введите курс к рублю:')
        return 'change_rate'
    else:
        update.message.reply_text(f'Валюта {currency} не найдена')
        return ConversationHandler.END


def change_rate(update, context):
    rate = update.message.text
    currency = context.user_data['currency']
    update_currency_rate_in_db(currency, rate)
    update.message.reply_text(f'Курс валюты {currency} успешно изменён')
    return ConversationHandler.END


def update_currency_rate_in_db(currency, rate):
    connection = psycopg2.connect(host="localhost", database="RPP_6", user="postgres", password="postgres")
    cursor = connection.cursor()
    cursor.execute("UPDATE currencies SET rate = %s WHERE currency_name = %s", (rate, currency))
    connection.commit()


def is_admin(chat_id):
    # Проверка наличия chat_id в таблице admins
    connection = psycopg2.connect(host="localhost", database="RPP_6", user="postgres", password="postgres")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM admins WHERE chat_id = %s", (str(chat_id),))
    return cursor.fetchone() is not None


def delete_currency(update, context):
    currency = update.message.text
    # Проверка наличия валюты в таблице currencies
    if is_currency_exist(currency):
        delete_currency_from_db(currency)
        update.message.reply_text(f'Валюта {currency} удалена')
    else:
        update.message.reply_text(f'Валюта {currency} не найдена')
    return ConversationHandler.END


def delete_currency_from_db(currency):
    connection = psycopg2.connect(host="localhost", database="RPP_6", user="postgres", password="postgres")
    cursor = connection.cursor()
    cursor.execute("DELETE FROM currencies WHERE currency_name = %s", (currency,))
    connection.commit()


def delete_currency_callback(update, context):
    query = update.callback_query
    query.answer()
    query.message.reply_text('Введите название валюты:')
    return 'delete_currency'


def add_currency_callback(update, context):
    query = update.callback_query
    query.answer()
    query.message.reply_text('Введите название валюты:')
    return CURRENCY


def add_currency(update, context):
    currency = update.message.text
    # Проверка наличия валюты в таблице currencies
    if is_currency_exist(currency):
        update.message.reply_text('Данная валюта уже существует')
        return ConversationHandler.END
    context.user_data['currency'] = currency
    update.message.reply_text('Введите курс к рублю:')
    return RATE


def add_rate(update, context):
    rate = update.message.text
    currency = context.user_data['currency']
    save_currency_rate(currency, rate)
    update.message.reply_text(f'Валюта {currency} успешно добавлена')
    return ConversationHandler.END


def is_currency_exist(currency):
    connection = psycopg2.connect(host="localhost", database="RPP_6", user="postgres", password="postgres")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM currencies WHERE currency_name = %s", (currency,))
    return cursor.fetchone() is not None


def save_currency_rate(currency, rate):
    connection = psycopg2.connect(host="localhost", database="RPP_6", user="postgres", password="postgres")
    cursor = connection.cursor()
    cursor.execute("INSERT INTO currencies (currency_name, rate) VALUES (%s, %s)", (currency, rate))
    connection.commit()


def convert(update, context):
    update.message.reply_text('Введите название валюты:')
    return CURRENCY


conv_handler_convert = ConversationHandler(
    entry_points=[CommandHandler('convert', convert)],
    states={
        CURRENCY: [MessageHandler(Filters.text & ~Filters.command, get_currency_rate)],
        AMOUNT: [MessageHandler(Filters.text & ~Filters.command, convert_currency)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)


def get_currencies(update, context):
    connection = psycopg2.connect(database="RPP_6", user="postgres", password="postgres", host="localhost", port="5432")
    cursor = connection.cursor()

    cursor.execute("SELECT currency_name, rate FROM currencies")
    currencies = cursor.fetchall()

    if currencies:
        message = "Список доступных валют:\n"
        for currency in currencies:
            currency_name, rate = currency
            message += f"{currency_name}: {rate}\n"
    else:
        message = "Нет сохраненных валют"

    update.message.reply_text(message)

    cursor.close()
    connection.close()


conv_handler_manage = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_currency_callback, pattern='^add_currency$'),
        CallbackQueryHandler(delete_currency_callback, pattern='^delete_currency$'),
        CallbackQueryHandler(change_currency_rate_callback, pattern='^change_currency_rate$')
    ],
    states={
        CURRENCY: [MessageHandler(Filters.text & ~Filters.command, add_currency)],
        RATE: [MessageHandler(Filters.text & ~Filters.command, add_rate)],
        'delete_currency': [MessageHandler(Filters.text & ~Filters.command, delete_currency)],
        'change_currency_rate': [MessageHandler(Filters.text & ~Filters.command, change_currency_rate)],
        'change_rate': [MessageHandler(Filters.text & ~Filters.command, change_rate)]

    },
    fallbacks=[]
)


def main():
    token = '5992714308:AAEcAZEz-rohv6ij5eMJVW_Gy-l9aLVLOeg'
    updater1 = Updater(token, use_context=True)
    dp1 = updater.dispatcher

    # добавление ConversationHandler для сохранения курсов валюты и конвертации валюты
    dp1.add_handler(conv_handler_save)
    dp1.add_handler(conv_handler_convert)

    # запуск бота
    updater1.start_polling()
    updater1.idle()


if __name__ == '__main__':
    updater = Updater('5992714308:AAEcAZEz-rohv6ij5eMJVW_Gy-l9aLVLOeg', use_context=True)
    dp = updater.dispatcher

    # добавляем обработчики команд
    dp.add_handler(CommandHandler('manage_currency', manage_currency))
    dp.add_handler(CommandHandler('get_currencies', get_currencies))

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('help', help))

    dp.add_handler(conv_handler_save)
    dp.add_handler(conv_handler_convert)
    dp.add_handler(conv_handler_manage)

    # запуск бота
    updater.start_polling()
    updater.idle()
