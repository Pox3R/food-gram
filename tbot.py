from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

from orderinfo import OrderInfo

import requests
import random
from pyzbar.pyzbar import decode
from PIL import Image

# токен  бота
API_TOKEN = '1056772125:AAFQrxSVgSzMO3Ihc9Rb3n4Uqm9pYZAa5NQ'
# создание бота и диспетчера
bot = Bot(token=API_TOKEN)
bot.parse_mode = 'HTML'

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class OrderState(StatesGroup):
    idle = State()
    gather_places = State()
    poll = State()


@dp.message_handler(commands=['start'])
async def if_start(message: types.Message):

    if message.chat.type == 'private':
        message_text = "%s, привет. " \
                       "Команда /help поможет разобраться как что работает" % message.from_user.first_name
        await bot.send_message(message.chat.id, message_text)
        return

    current_state = await storage.get_state(chat=message.chat.id)
    if current_state is not None and current_state != OrderState.idle.state:
        message_text = "%s! Заказ уже делается! Не хулигань. 😠" % message.from_user.first_name
        await bot.send_message(message.chat.id, message_text)
        return

    order_info = OrderInfo.from_message(message)
    await storage.set_data(chat=message.chat.id, data={'order': order_info.to_dict()})
    await storage.set_state(chat=message.chat.id, state=OrderState.gather_places.state)

    message_text = "Привет, будем заказывать\n" \
                   "<b>%s</b> - инициатор заказа, будет иметь основные права и обязанности. " \
                   "Пишите места командой" % message.from_user.first_name
    await bot.send_message(message.chat.id, message_text)

    # информируем главного что он главный
    # message_text = "Привет, %s! Ты решил сделать заказ в чате %s \n 😎 " \
    #                % (message.from_user.first_name, message.chat.title)
    # await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(commands=['addPlace'])
async def if_add_place(message: types.Message):

    current_state = await storage.get_state(chat=message.chat.id, default=OrderState.idle.state)
    if current_state != OrderState.gather_places.state:
        message_text = "Данная команда недоступна на текущей стадии заказа."
        await bot.send_message(message.chat.id, message_text)
        return

    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])

    new_place = message.text.split(' ', maxsplit=1)[1]
    order.add_place(new_place)
    await storage.update_data(chat=message.chat.id, data={'order': order.to_dict()})

    message_text = f"Место \"{new_place}\" было добавлено. Места участвующие в голосовании: {order.places}."
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands=['startPoll'])
async def if_start_poll(message: types.Message):
    current_state = await storage.get_state(chat=message.chat.id, default=OrderState.idle.state)
    if current_state != OrderState.gather_places.state:
        message_text = "Данная команда недоступна на текущей стадии заказа."
        await bot.send_message(message.chat.id, message_text)
        return

    await storage.set_state(chat=message.chat.id, state=OrderState.poll.state)

    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])

    question = "Из какого места заказать еду?"
    sent_message = await bot.send_poll(message.chat.id, question, order.places)

    await storage.update_data(chat=message.chat.id, data={'poll_message_id': sent_message.message_id})


@dp.message_handler(commands=['showPlace'])
async def if_show_place(message: types.Message):
    current_state = await storage.get_state(chat=message.chat.id, default=OrderState.idle.state)
    if current_state != OrderState.poll.state:
        message_text = "Данная команда недоступна на текущей стадии заказа."
        await bot.send_message(message.chat.id, message_text)
        return

    data = await storage.get_data(chat=message.chat.id)
    poll_message_id = data['poll_message_id']
    poll = await bot.stop_poll(message.chat.id, poll_message_id)

    poll.options.sort(key=lambda o: o.voter_count)
    winner_option = poll.options[0]

    message_text = f"Вариант \"{winner_option.text}\" набраил наибольшее количество голосов."
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands='cancel')
async def if_cancel(message: types.Message):
    await storage.reset_state(chat=message.chat.id, with_data=True)

    message_text = "Текущий заказ отменен."
    await bot.send_message(message.chat.id, message_text)

# # обработчик команды /eat & /bill
# @dp.message_handler(content_types=['text'])
# async def if_message(message: types.Message):
#     global order_chats
#     global order_enable
#     global photo_enable
#
#     # командой eat разрешаем ввод заказа текстом
#     if message.text == '/eat':
#         # проверка что пользователь регистрировался в чате - жал makeorder
#         for i in order_chats:
#             if message.from_user.id in order_chats[i]:
#                 order_enable = 1
#                 await bot.send_message(message.from_user.id, 'Пиши пункты заказа через перенос')
#                 return
#         # если не нашли пользователя в массиве
#         await bot.send_message(message.from_user.id, "Вас нет в списках! Жмите makeorder в чате заказа")
#         return
#
#     # командой bill разрешаем отправку фото
#     elif message.text == '/bill':
#         photo_enable = 1
#         await bot.send_message(message.from_user.id, 'Отправь фото чека\nФото должно быть четким')
#
#         # если просто текст поступил с разрешенным txt_enable
#     else:
#         if order_enable:
#             order_enable = 0
#             tmp = 0
#             for i in order_chats:
#                 if message.from_user.id in order_chats[i]:
#                     tmp = i
#                     break
#             for i in range(len(message.text.split())):
#                 order_chats[tmp][message.from_user.id][i] = message.text.split()[i]
#             to_out = []
#             for i in order_chats[tmp][message.from_user.id]:
#                 to_out.append('<b>' + str(i) + '</b> - ' + str(order_chats[tmp][message.from_user.id][i]))
#             await bot.send_message(message.from_user.id, "\n".join(to_out))
#         else:
#             await bot.send_message(message.from_user.id, "/help  ⬅  жми")


def bill_existing(fn, fd, fpd, date, sum):
    site = 'https://proverkacheka.nalog.ru:9999/v1/ofds/*/inns/*/fss/' \
           + fn + '/operations/1/tickets/' + fd
    payload = {'fiscalSign': fpd, 'date': date, 'sum': sum}
    response = requests.get(site, params=payload)
    if response.status_code == 204:
        return 1  # чек есть в бд
    if response.status_code == 406:
        return 0  # чека нет или дата/сумма некорректная
    if response.status_code == 400:
        return -1  # неправильный запрос
    return -2  # просто ошибка


def bill_detal_inf(fn, fd, fpd):
    site = 'https://proverkacheka.nalog.ru:9999/v1/inns/*/kkts/*/fss/' \
           + fn + '/tickets/' + fd
    payload = {'fiscalSign': fpd, 'sendToEmail': 'no'}
    headers = {'device-id': '', 'device-os': '', 'Authorization': 'Basic Kzc5MTE5OTEyOTcxOjQ1ODQzMw=='}
    response = requests.get(site, params=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    # else:
    #    return -1
    return -1


@dp.message_handler(content_types=['photo'])
async def handle_docs_photo(message):
    global photo_enable
    if photo_enable:
        try:
            file_id = message.photo[len(message.photo) - 1].file_id
            site = 'https://api.telegram.org/bot' \
                   + API_TOKEN + '/getFile?file_id=' \
                   + file_id
            gf = requests.get(site)
            site2 = 'https://api.telegram.org/file/bot' \
                    + API_TOKEN + '/' + gf.json()['result']['file_path']
            df = requests.get(site2)
            with open(file_id + '.jpg', 'wb') as new_file:
                new_file.write(df.content)
            # os.startfile(r'ph1.jpg')
            qr_txt = decode(Image.open(file_id + '.jpg'))
            bill_par = {}
            bill_arr = str(qr_txt[0].data).replace("b'", '').split('&')
            for a in bill_arr:
                tmp = a.split('=')
                bill_par[tmp[0]] = tmp[1]
            # print(bill_par)

            a = bill_existing(bill_par['fn'], bill_par['i'], bill_par['fp'], bill_par['t'],
                              bill_par['s'].replace(".", ""))
            if a:
                await bot.send_message(message.chat.id, 'Чек корректен')
            else:
                await bot.send_message(message.chat.id, str(a))
            ret = bill_detal_inf(bill_par['fn'], bill_par['i'], bill_par['fp'])
            to_out = []
            for i in ret['document']['receipt']['items']:
                to_out.append(i['name'] + '\n<i>Стоймсть:</i> <b>' + str(i['price'] / 100) + '</b>\n')
            await bot.send_message(message.chat.id, ''.join(to_out), parse_mode="HTML")
        except Exception as e:
            await bot.send_message(message.chat.id, e)
    else:
        await bot.send_message(message.chat.id, 'К чему ты это?', reply_to_message_id=message)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
