import json
import os
import telegram.ext
import apiai
import datetime
import requests
import shutil
import random

keys = {}
translation = {}


def parse_text(update):
    ai = apiai.ApiAI(keys['DialogFlow'])
    request = ai.text_request()
    request.lang = 'ru'
    request.session_id = update.message.chat_id
    request.query = update.message.text
    response = json.loads(request.getresponse().read().decode())
    date = response['result']["parameters"]['date']
    city = response['result']['parameters']['geo-city']
    return city, date


def get_coordinates(city_name):
    if city_name == '':
        raise KeyError
    result = list(map(float,
               requests.get('https://geocode-maps.yandex.ru/1.x/',
                            params={'geocode': city_name,
                                    'format': 'json',
                                    'key': keys['YandexMaps']}) \
               .json()['response']['GeoObjectCollection']['featureMember']
               [0]['GeoObject']['Point']['pos'].split()))
    return {'longitude': result[0], 'latitude': result[1]}


def get_weather(coordinates, date):
    response = requests.get('https://api.weather.yandex.ru/v1/forecast',
                           params={'lon': coordinates['longitude'],
                                   'lat': coordinates['latitude']},
                           headers={'X-Yandex-API-Key': keys['YandexWeather']}).json()
    if date == '':
        return response['fact']
    diff = datetime.datetime.strptime(date, '%Y-%m-%d') - \
               datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    return response['forecasts'][diff.days]['parts']['day_short']


def send_picture(city, bot, chat_id):
    url = requests.get('https://api.cognitive.microsoft.com/bing/v7.0/images/search',
                       headers={'Ocp-Apim-Subscription-Key': keys['Bing']},
                       params={'q': city, 'count': 1}).json()['value'][0]['contentUrl']
    file = open('../tmp/url', 'wb')
    shutil.copyfileobj(requests.get(url, stream=True).raw, file)
    file.close()
    file = open('../tmp/url', 'rb')
    bot.sendPhoto(chat_id=chat_id, photo=file)
    file.close()
    os.remove('../tmp/url')


def send_poem(condition, bot, chat_id):
    if condition.find('ясно') >= 0:
        type = 'sun/'
    elif condition.find('облачно') >= 0:
        type = 'cloudy/'
    elif condition.find('дождь') >= 0:
        type = 'rain/'
    elif condition.find('снег') >= 0:
        type = 'snow/'
    elif condition.find('пасмурно') >= 0:
        type = 'overcast/'
    poem_id = str(random.randint(0, 3))
    bot.sendMessage(chat_id=chat_id, text=open('poems/'+type+poem_id+'.txt').read())


def handle_message(bot, update):
    try:
        city, date = parse_text(update)
        coordinates = get_coordinates(city)
        weather = get_weather(coordinates, date)
        if date == '':
            date = 'сейчас'
        else:
            date = 'на ' + date
        bot.sendMessage(chat_id=update.message.chat_id,
                            text='Погода в городе {} {}:\n{}\u00B0C, {}'
                            .format(city, date, weather['temp'], translation[weather['condition']]))
        send_picture(city, bot, update.message.chat_id)
        send_poem(translation[weather['condition']], bot, update.message.chat_id)
    except IndexError:
        bot.sendMessage(chat_id=update.message.chat_id, text=\
            """Я не знаю погоду на это время.\nНабери /help, чтобы узнать параметры запроса""")
    except KeyError:
        bot.sendMessage(chat_id=update.message.chat_id, text=\
            """Я не могу найти этот город.\nНабери /help, чтобы узнать параметры запроса""")
    except Exception:
        bot.sendMessage(chat_id=update.message.chat_id, text='Случилась непредвиденная ошибка')


def handle_help(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id,
                    text=\
    """Привет!\nЯ могу отвечать на твои запросы о погоде, заданные в произвольной форме.
    Вопрос должен содержать название места.
    Если не указан день прогноза, показывается погода в данный момент.""")


def main():
    global keys, translation
    try:
        keys = json.load(open('config/keys.json'))
        translation = json.load(open('config/translation.json'))
    except FileNotFoundError:
        keys = json.load(open('../config/keys.json'))
        translation = json.load(open('../config/translation.json'))

    message_handler = telegram.ext.MessageHandler(telegram.ext.Filters.text, handle_message)
    help_handler = telegram.ext.CommandHandler(command='help', callback=handle_help)

    updater = telegram.ext.Updater(token=keys['TelegramBot'])
    updater.dispatcher.add_handler(help_handler)
    updater.dispatcher.add_handler(message_handler)
    updater.start_webhook(listen="0.0.0.0",
                          port=int(os.environ.get('PORT', '5000')),
                          url_path=keys['TelegramBot'])
    updater.bot.set_webhook("https://murmuring-lowlands-52462.herokuapp.com/" + keys['TelegramBot'])
    updater.idle()


if __name__ == '__main__':
    main()