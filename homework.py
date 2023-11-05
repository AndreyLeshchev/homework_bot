import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import CustomTelegramError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logger = logging.getLogger(name=__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler = logging.StreamHandler()
logger.addHandler(handler)
handler.setFormatter(formatter)

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    logger.debug('Начало проверки переменных окружения.')
    for value in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if not value:
            return False
    logger.debug('Проверка переменных окружений прошла успешно.')
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logger.debug('Попытка отправить сообщение.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено успешно.')
    except telegram.error.TelegramError:
        raise CustomTelegramError(
            'Cбой в Telegram при отправке сообщения.'
        )


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    try:
        logger.debug('Попытка отправки запроса к API.')
        response = requests.get(
            ENDPOINT, headers=HEADERS,
            params={'from_date': timestamp},
        )
        if response.status_code != requests.codes.ok:
            raise requests.HTTPError(f'Статус ответа {response.status_code}')
        valid_response = response.json()
    except requests.HTTPError as error:
        raise requests.HTTPError(error)
    except ValueError:
        raise ValueError('Невалидные данные JSON.')
    except requests.RequestException:
        raise ConnectionError(f'Эндпоинт {ENDPOINT} недоступен.')
    logger.debug('Запрос успешно отправлен.')
    return valid_response


def check_response(response):
    """Проверка ответа API на соответствие."""
    logger.debug('Проверка ответа API на соответствие.')
    if type(response) is not dict:
        raise TypeError('Cтруктура данных API не соответствует ожиданиям.')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа "homeworks".')
    if 'current_date' not in response:
        raise KeyError('Отсутствие ожидаемых ключей в ответе API.')
    if type(response['homeworks']) is not list:
        raise TypeError('Данные "homeworks" приходят не в виде списка.')
    logger.debug('Проверка ответа API на соответствие прошла успешно.')
    return response


def parse_status(homework):
    """Получение названия и статуса домашней работы."""
    logger.debug('Попытка получить статус домашней работы.')
    if 'homework_name' not in homework:
        raise KeyError('В ответе API нет ключа "homework_name".')
    if homework['status'] not in ('reviewing', 'approved', 'rejected'):
        raise ValueError('В ответе API нет статуса домашней работы.')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework['status']]
    logger.debug('Статус домашней работы получен.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.debug('Бот начал работу.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    status = ''
    last_message = ''
    if not check_tokens():
        logger.critical(
            'Отсутствует обязательная переменная окружения. '
        )
        sys.exit('Программа принудительно остановлена.')
    while True:
        try:
            response = check_response(get_api_answer(timestamp))
            if response['homeworks']:
                if response['homeworks'][0]['status'] != status:
                    status = response['homeworks'][0]['status']
                    for homework in response.get('homeworks'):
                        send_message(bot, parse_status(homework))
                else:
                    message = 'Статус домашней работы не изменился.'
                    logger.debug(message)
                    send_message(bot, message)
            else:
                message = (
                    'Список домашних работ за период '
                    f'{timestamp} времени пуст.'
                )
                logger.debug(message)
                send_message(bot, message)
        except CustomTelegramError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_message:
                last_message = message
                send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
