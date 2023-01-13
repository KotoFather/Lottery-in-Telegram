import os
import random

import requests
from telegram.utils.request import Request
import string

from django.core.management.base import BaseCommand
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot
from telegram.ext import CallbackContext, Updater, MessageHandler, Filters, CallbackQueryHandler


from bot.models import *
from tl_shop import settings
import datetime



def log_errors(f):
    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = f'Произошла ошибка: {e}'
            print(error_message)
            raise e

    return inner


# PaymentLinkGenerate
def payment_link_generate(u1, u2):
    paysite = "https://lk.rukassa.pro/api/v1/create"
    datajs = {
        "shop_id": 174,
        "token": "470008a4755424a2792381c470277b91",
        "order_id": u1,
        "amount": u2
    }
    response = requests.post(f"{paysite}", datajs)
    #print(response.json())
    #urltopay = response.json()
    return response.json()



#print(payment_link_generate(123, 340))

'''
def payment_history_last(pk):
    s = requests.Session()
    h = s.get('https://lk.rukassa.pro/api/v1/getPayInfo').json()
    order = Order.objects.get(pk=pk)
    res = "NO"
    if order.step == 2:
        for transition in h["data"]:
            if order.pay == transition["amount"] and id == transition["comment"] and transition["STATUS"] == "WAIT":
                res = "OK"
                order.step = 3
                order.save()
    return res
'''

# Проверка платежа qiwi
def payment_history_last(pk):
    s = requests.Session()
    s.headers['authorization'] = 'Bearer ' + settings.Token
    #parameters = {'rows': 50}
    order = Order.objects.get(pk=pk)
    transition = s.get('https://lk.rukassa.pro/api/v1/getPayInfo?id=' + order.payid).json()
    res = "NO"
    #About PAID
    if order.step == 2:
            print(transition)
            if order.payid == transition["id"] and order.pay == transition["amount"] and transition["status"] == "PAID":
                res = "OK"
                order.step = 3
                order.save()
    print(res)
    return res


# Генератор названия файлов
def generate_name():
    length = 10
    letters = string.ascii_letters + string.digits
    rand_string = ''.join(random.choice(letters) for i in range(length))
    return rand_string


# Получить сообщение или создать
def get_mess(pk, text):
    message, _ = MessageText.objects.get_or_create(pk=pk, defaults={"message": text})
    return message.message


# Получить кнопку меню или создать
def get_menu(pk, text):
    menu, _ = MenuText.objects.get_or_create(pk=pk, defaults={"button": text})
    return menu.button


# Получить пользователя или создать
def get_person(chat_id, name=""):
    p, _ = Profile.objects.get_or_create(
        external_id=chat_id,
        defaults={
            'name': name,
            'level': 1
        }
    )
    return p


# Создание меню кнопок
def build_menu(buttons, n_cols,
               header_buttons=None,
               footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu.json

# Собирает необходимую информацию
def zparse_data(p, data):
    order = p.order.filter(step__in=[1])[0]
    product = order.product
    kol_enter = order.data_kol + 1
    order.data_kol = kol_enter
    order.data_have = order.data_have + data + "\n"
    order.save()

    message_text = reply_markup = ""
    if len(product.data.split(";")) == kol_enter or len(product.data) == 0:
        # Все необходимые данные введены
        order.step = 2
        order.code = ''.join(random.choice("0123456789") for i in range(9))
        urltopay = order.urltopay = str(payment_link_generate(order.code, product.price1)["url"])
        idtocheck = order.payid = str(payment_link_generate(order.code, product.price1)["id"])
        order.save()
        message_text = get_mess(8, f"👉 Для оплаты покупки перейдите по ссылке"
                                   f""
                                   f"{urltopay}"
                                   f""
                                   f"👉 После подтверждения покупки, вы увидите ваш билет во вкладке ⭐️Мои билеты"
                                ).format(code=order.code, pay=order.pay, urltopay=order.urltopay)

        keyboard = [[InlineKeyboardButton(get_menu(8, "Проверить платеж"), callback_data='check-' + str(idtocheck))]]
        reply_markup = InlineKeyboardMarkup(keyboard)
#    else:
        # Если это телефон или ФИО, то записываем в заказ
#        if kol_enter == 1:
#            order.fio = data
#            order.save()
#        elif kol_enter == 2:
#            order.phone = data
#            order.save()
#        message_text = get_mess(5, "Пожалуйства отправьте/введите {data}").format(
#            data=product.data.split("\n")[kol_enter])
    return (message_text, reply_markup)

# timedelta
def timedelta_to_dhms(duration):
    # преобразование в дни, часы, минуты и секунды
    days, seconds = duration.days, duration.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = (seconds % 60)
    return days, hours, minutes, seconds

# Обработчик сообщений
@log_errors
def do_echo(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text

    p = get_person(chat_id, update.message.from_user.username)
    message_text = get_mess(7, "Мы вас не поняли")
    reply_markup = ""

    import datetime

    if text == "/start" or text == "Отменить покупку":
        if text == "Отменить покупку" and p.order.filter(step__in=[1]).count() > 0:
            # Отменяем заказ
            order = p.order.filter(step__in=[1])[0]
            order.step = 6
            order.save()
            update.message.reply_text(text=get_mess(6, "Покупка отменена"))
        # Старт
        message_text = get_mess(1, "👋 Я - Лотерейный бот CALottery"
                                   "Прежде, чем начать играть, просим вас ознакомиться с условиями игры в разделе FAQ")
        reply_markup = ReplyKeyboardMarkup([
            [get_menu(1, "📋 Лотерея")],
            [get_menu(2, "📝 Отзывы"), get_menu(3, "⭐️ Мои билеты")],
            [get_menu(4, "🎈️ FAQ")]
        ])
    elif MenuText.objects.filter(button=text).count() != 0:
        button = MenuText.objects.filter(button=text)[0]
        if button.pk == 1:

            message_text = get_mess(2, "📌 Лото MegaMillions это американская лотерея, первая игра которой прошла в 1996 году, а среди участников были 6 штатов."
                                       ""
                                       "В наше время в лото Мегамиллионы принимают участие жители 45 штатов и 47 юрисдикций."
                                       ""
                                       "Тиражи лотереи проходят дважды в неделю, во вторник и пятницу вечером."
                                       ""
                                       "👉 Для принятия участия в лотерейной игре Мега Миллионы требуется выбрать 5 основных шаров и мега шар (Mega Ball), который выполняет роль бонус шара."
)
            keyboard = [[InlineKeyboardButton(cat.text, callback_data='cat-' + str(cat.pk))] for cat in
                        Category.objects.filter(nesting_level=1)]
            reply_markup = InlineKeyboardMarkup(keyboard)
        elif button.pk == 2:
            message_text = get_mess(11, "В разработке")
        elif button.pk == 3:

            if p.order.filter(step__in=[5]).count() != 0:
            # Загружаем введенные данные
                message_text = get_mess(15, "Ваши лотерейные билеты:")

                for ee in p.order.filter(step__in=[5]):
                    #
                    context.bot.sendMessage(chat_id=chat_id, text=datetime.datetime.strftime(ee.date_create, "%Y-%m-%d %H:%M:%S") + ": \n" + ee.comment)

                    context.bot.sendMessage(chat_id=chat_id, text="📷 Фотографии ваших билетов:")
                    for pp in FileOrder.objects.filter(order=ee):
                        print(pp.file_order.url)
                        orderphoto = pp.file_order
                        context.bot.send_photo(chat_id, orderphoto)
                    datebuyweek = datetime.datetime.weekday(ee.date_create)
                    # дата сейчас
                    datebnow = datetime.datetime.now()
                    # Дата покупки билета
                    dateb = datetime.datetime.replace(ee.date_create, tzinfo=None)

                    # Генерируем Вторник
                    tuesday = dateb + datetime.timedelta((2 - dateb.weekday()) % 7)
                    # Генерируем Пятницу
                    friday = dateb + datetime.timedelta((4 - dateb.weekday()) % 7)

                    # Генерируем дату следующей пятницы
                    fr = (datetime.datetime.strptime(str(friday.date()), "%Y-%m-%d") + datetime.timedelta(hours=19, minutes=45))
                    # Генерируем дату следующего вторника
                    tu = (datetime.datetime.strptime(str(tuesday.date()), "%Y-%m-%d") + datetime.timedelta(hours=19, minutes=45))

                    print(fr)
                    print("ITOGO:")
                    diff2 = fr - datebnow
                    diff3 = tu - datebnow
                    print(diff2.days)

                    hours1 = int(diff2.seconds // (60 * 60))
                    mins1 = int((diff2.seconds // 60) % 60)
                    hours2 = int(diff3.seconds // (60 * 60))
                    mins2 = int((diff3.seconds // 60) % 60)

                    if datebuyweek in [2, 3, 4]:
                        context.bot.sendMessage(chat_id=chat_id, text=f"🕤 Следующий розыгрыш через {diff2.days} суток {hours1} часов {mins1} минут")
                    else:
                        context.bot.sendMessage(chat_id=chat_id, text=f"🕤 Следующий розыгрыш через {diff3.days} суток {hours2} часов {mins2} минут")
                    #print(datetime.datetime.weekday(ee.date_create))
                    #print(datetime.datetime.today().weekday())
                    #print(datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S"))

#    file_ord = FileOrder()
#    file_ord.file_order.name = "documents/" + name

            if p.order.filter(step__in=[3]).count() != 0:
                context.bot.sendMessage(chat_id=chat_id, text="🛒 Ваши покупки в обработке:")

                for ee in p.order.filter(step__in=[3]):
                    context.bot.sendMessage(chat_id=chat_id, text=datetime.datetime.strftime(ee.date_create, "%Y-%m-%d %H:%M:%S") + ": \n" + ee.comment)

            if p.order.filter(step__in=[5]).count() == 0 and p.order.filter(step__in=[3]).count() == 0 and p.order.filter(step__in=[4]).count() != 0:
                context.bot.sendMessage(chat_id=chat_id, text="❌ Вы еще не покупали билеты")

            if p.order.filter(step__in=[4]).count() != 0:
                context.bot.sendMessage(chat_id=chat_id, text="💸 Билеты, ожидающие выплаты:")
                for ee in p.order.filter(step__in=[4]):
                    context.bot.sendMessage(chat_id=chat_id, text=datetime.datetime.strftime(ee.date_create, "%Y-%m-%d %H:%M:%S") + ": \n" + ee.comment)

        # Отправка фото и описания
            #context.bot.send_photo(chat_id=chat_id, photo=open(product.img.path, 'rb'))
            #context.bot.sendMessage(chat_id=chat_id, text=bilet.text)

        elif button.pk == 4:
            message_text = get_mess(13, "❓ Как начать участвовать в лотерее ?"
                                        "❗️ Приобрести билет и дождаться подтверждения покупки в разделе - Мои билеты."
                                        ""
                                        "❓ Сколько времени занимает покупка ?"
                                        "❗️ Оплата проходит моментально, все остальное автоматически, фактически вы получаете фотографию оригинального билета в течении трех часов."
                                        ""
                                        "❓ Я счастливчик, как я могу получить выигрыш ?"
                                        "❗️ Мы автоматически свяжемся с вами через Телеграм и предложим вам варианты получения выигрыша."
                                        ""
                                        "❓ Какие комиссии ?"
                                        "❗️ Мы оставляем за собой 20% от суммы выигрыша после оплаты всех налогов и сборов."
                                        ""
                                        "❓ У меня есть другие вопросы."
                                        "❗️ Пишите в поддержку @CaLottery_Support_bot")

    elif p.order.filter(step__in=[1]).count() != 0:
        # Загружаем введенные данные
        message_text, reply_markup = zparse_data(p, text)

    if type(reply_markup) == str:

        update.message.reply_text(
            text=message_text
        )
    else:
        update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )


# Обработчик файлов
@log_errors
def message_files(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    # Качаем файл
    if update.message.document is None:
        file_id = update.message.photo[-1].file_id
        file_ras = "jpg"
    else:
        file_id = update.message.document.file_id
        file_ras = update.message.document.file_name.split('.')[-1]
    new_file = context.bot.get_file(file_id)
    path = os.path.join(settings.MEDIA_ROOT, 'documents') + "/"
    name = str(generate_name()) + "." + file_ras
    new_file.download(path + name)

    # Привязываем файл к модели
    file_ord = FileOrder()
    file_ord.file_order.name = "documents/" + name
    file_ord.save()

    p = get_person(chat_id, update.message.from_user.username)
    #message_text = get_mess(7, "Мы вас не поняли")
    #reply_markup = ""
    if p.order.filter(step__in=[1]).count() != 0:
        # Загружаем введенные данные
        file_ord.order = p.order.filter(step__in=[1])[0]
        file_ord.save()
        message_text, reply_markup = zparse_data(p, settings.DOMAIN + file_ord.file_order.url)

    if type(reply_markup) == str:
        update.message.reply_text(
            text=message_text
        )
    else:
        update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )


# Обработчик Inline кнопок
@log_errors
def button(update: Update, context: CallbackContext):
    chat_id = context._chat_id_and_data[0]
    query = update.callback_query
    # Получить пользователя
    p = get_person(chat_id)

    variant = query.data.split("-")
    message_text = reply_markup = ""
    # Отменяем покупку, если пользователь нажал на inline кнопку
    if p.order.filter(step__in=[1]).count() != 0:
        order = p.order.filter(step__in=[1])[0]
        order.step = 6
        order.save()
        update.message.reply_text(text=get_mess(6, "Покупка отменена"))
    if variant[0] == "cat":
        # Обрабатываем нажатие на категорию
        cat = Category.objects.get(pk=int(variant[1]))
        if (cat.nested_category.count() > 0):
            message_text = get_mess(2, "Выберите из списка")
            keyboard = [[InlineKeyboardButton(cat.text, callback_data='cat-' + str(cat.pk))] for cat in
                        cat.nested_category.all()]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            message_text = get_mess(3, "Выберите товар из списка")
            keyboard = [[InlineKeyboardButton(product.name, callback_data='product-' + str(product.pk))] for product in
                        cat.products.all()]
            reply_markup = InlineKeyboardMarkup(keyboard)
    elif variant[0] == "product":
        # Обрабатываем нажатие на товар
        product = Product.objects.get(pk=int(variant[1]))
        # Отправка фото и описания
        context.bot.send_photo(chat_id=chat_id, photo=open(product.img.path, 'rb'))
        context.bot.sendMessage(chat_id=chat_id, text=product.text)
        # Задаем вопросы
        if product.ask != "":
            message_text = product.ask.split(";")[0]
            keyboard = [
                [InlineKeyboardButton("Да", callback_data='yes-' + str(product.pk) + "-" + "0"),
                 InlineKeyboardButton("Нет", callback_data='no-' + str(product.pk) + "0")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            # Вызываем цену
            price_list = [product.price1, product.price2, product.price3, product.price4, product.price5]
            message_text = get_mess(4, "К оплате: {price} руб.").format(price=price_list[p.level - 1])
            keyboard = [[InlineKeyboardButton(get_menu(6, "Купить"), callback_data='buy-' + str(product.pk))]]
            reply_markup = InlineKeyboardMarkup(keyboard)
    elif variant[0] == "buy":
        # Обрабатываем нажатие на кнопку купить
        product = Product.objects.get(pk=int(variant[1]))
        price_list = [product.price1, product.price2, product.price3, product.price4, product.price5]
        order = Order(step=1, product=product, user=p, pay=price_list[p.level - 1])
        order.save()

        # Отправляем доп. информацию
        description = product.description.split(";")
        if description != "":
            for message in description:
                if message != "":
                    context.bot.sendMessage(chat_id=chat_id, text=message)
        if product.data != "":
            context.bot.sendMessage(chat_id=chat_id, text="Отправляя данные, Вы соглашаетесь с правилами участия в лотерее.")
            message_text = get_mess(5, "{data}").format(data=product.data)
            reply_markup = ReplyKeyboardMarkup([
                [get_menu(7, "Отменить покупку")]
                ])
        else:
            #context.bot.sendMessage(chat_id=chat_id, text=message_text, reply_markup=reply_markup)

            message_text = get_mess(20,
                                    "Нажимая кнопку Оплатить, Вы соглашаетесь с правилами участия в лотерее.").format(
                data=product.data)

            reply_markup = ReplyKeyboardMarkup([
                ['Оплатить'],
                [get_menu(7, "Отменить покупку")]
                ])


        # Снова время
        datebnow = datetime.datetime.now()
        # Дата покупки билета
        tuesday = datetime.datetime.today() + datetime.timedelta((1 - datebnow.weekday()) % 7)
        # Генерируем Пятницу
        friday = datetime.datetime.today() + datetime.timedelta((4 - datebnow.weekday()) % 7)
        datebuyweek = datetime.datetime.now().weekday()
        # Генерируем дату следующей пятницы
        fr = datetime.datetime.strptime(str(friday.date()), "%Y-%m-%d") + datetime.timedelta(hours=19, minutes=45)
        # Генерируем дату следующего вторника
        tu = datetime.datetime.strptime(str(tuesday.date()), "%Y-%m-%d") + datetime.timedelta(hours=19, minutes=45)

        diff2 = fr - datebnow
        diff3 = tu - datebnow

        hours1 = int(diff2.seconds // (60 * 60))
        mins1 = int((diff2.seconds // 60) % 60)
        hours2 = int(diff3.seconds // (60 * 60))
        mins2 = int((diff3.seconds // 60) % 60)

        if datebuyweek in [2, 3, 4]:
            context.bot.sendMessage(chat_id=chat_id,
                                    text=f"🕤 Следующий розыгрыш через {diff2.days} суток {hours1} часов {mins1} минут")
        else:
            context.bot.sendMessage(chat_id=chat_id,
                                    text=f"🕤 Следующий розыгрыш через {diff3.days} суток {hours2} часов {mins2} минут")

        # Просим ввести необходимые данные

    elif variant[0] == "check":
        # Проверка платежа
        res = payment_history_last(variant[1])
        reply_markup = ReplyKeyboardMarkup([
            [get_menu(1, "📋 Тарифы")],
            [get_menu(2, "📝 Отзывы"), get_menu(3, "⭐️ Мои билеты")],
            [get_menu(4, "⚙️ Поддержка")]
        ])
        if res == "OK":
            message_text = get_mess(9, "Оплата прошла успешно")
            context.bot.sendMessage(chat_id="-797296858", text="Новый заказ")
        else:
            message_text = get_mess(10, "Оплата пока не пришла")
    elif variant[0] == "yes":
        product = Product.objects.get(pk=int(variant[1]))
        if int(variant[2]) + 1 == len(product.ask.split(";")):
            # Вызываем цену
            price_list = [product.price1, product.price2, product.price3, product.price4, product.price5]
            message_text = get_mess(4, "К оплате: {price} руб.").format(price=price_list[p.level - 1])
            keyboard = [[InlineKeyboardButton(get_menu(6, "Купить"), callback_data='buy-' + str(product.pk))]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            message_text = product.ask.split(";")[int(variant[2]) + 1]
            keyboard = [
                [InlineKeyboardButton("Да", callback_data='yes-' + str(product.pk) + "-" + str(int(variant[2]) + 1)),
                 InlineKeyboardButton("Нет", callback_data='no-' + str(product.pk) + "0")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
    elif variant[0] == "no":
        message_text = get_mess(14, "К сожалению вы не сможете заказать этот товар")
    # query.answer()
    if type(reply_markup) == str:
        if message_text != "":
            context.bot.sendMessage(chat_id=chat_id, text=message_text)
        #query.edit_message_text(
        #    text=message_text
        #)
    else:
        context.bot.sendMessage(chat_id=chat_id, text=message_text, reply_markup=reply_markup)
        #query.edit_message_text(
        #    text=message_text,
        #    reply_markup=reply_markup
        #)


class Command(BaseCommand):
    help = 'Телеграм-бот'

    def handle(self, *args, **options):
        # подключение
        request = Request(
            connect_timeout=0.5,
            read_timeout=1.0,
        )
        bot = Bot(
            request=request,
            token=settings.TOKEN,
        )
        print(bot.get_me())

        # обработчики
        updater = Updater(
            bot=bot,
            use_context=True,
        )

        message_handler = MessageHandler(Filters.text, do_echo)
        media_handler = MessageHandler(Filters.document, message_files)
        photo_handler = MessageHandler(Filters.photo, message_files)
        updater.dispatcher.add_handler(message_handler)
        updater.dispatcher.add_handler(media_handler)
        updater.dispatcher.add_handler(photo_handler)

        updater.dispatcher.add_handler(CallbackQueryHandler(button))
        # запустить бесконечную обработку входящих сообщений
        updater.start_polling()
        updater.idle()
