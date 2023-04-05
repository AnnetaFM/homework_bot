import logging
import os
import requests
import telegram
import time
import sys


from dotenv import load_dotenv
from json import JSONDecodeError
from http import HTTPStatus


from exceptions import EmptyStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)

logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Проверяем наличие всех необходимых токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for name, token in tokens.items():
        if not token:
            message = ('Не задан токен: '
                       f'{name}. Выполнение программы прекращено.')
            logger.critical(message)
            sys.exit()


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        logging.info('Начало отправки сообщения в Telegram: {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено в Telegram: {message}')
    except Exception as sending_error:
        logging.error(f'Ошибка отправки сообщения в Telegram: {sending_error}')


def get_api_answer(timestamp):
    """Получение статуса домашней работы с API сервиса Практикум.Домашка."""
    params = {'from_date': timestamp}
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    try:
        response = requests.get(ENDPOINT, headers=headers, params=params)
        if response.status_code != HTTPStatus.OK:
            message = ('Сбой в работе программы: '
                       f'Эндпоинт {ENDPOINT} недоступен. '
                       f'Код ответа API: {response.status_code}')
            logger.error(message)
            raise response.raise_for_status()
        logger.info(
            f'Запрос получен. Статус ответа: {response.status_code}'
        )
        clear_response = response.json()
        if 'error' in clear_response:
            message = clear_response.get('error')
            logger.error(
                f'Ошибка формата ответа сервера {message}'
            )
            raise SystemError('Ошибка формата ответа сервера')
        return clear_response
    except JSONDecodeError:
        logger.error('Ошибка декодирования JSON')
    except requests.RequestException as e:
        logger.error(f'Ошибка запроса API: {e}')


def check_response(response):
    """Проверка ответа от API сервиса Практикум.Домашка."""
    if not isinstance(response, dict):
        raise TypeError("В ответе от API ожидался словарь")
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе от API отсутствует ожидаемый ключ "homeworks"')
    if not isinstance(response["homeworks"], list):
        raise TypeError('В ответе от API ожидался список домашних работ')
    if not isinstance(response.get('current_date'), int):
        raise TypeError('Ответ не содержит число current_date')
    if not response.get('current_date'):
        raise KeyError('Отсутствует значение ключа current date')
    if not response.get('homeworks'):
        raise KeyError('Не допустимое значение* ключа homeworks')
    return True


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not homework_name:
        raise KeyError('Отсутствует домашняя работа')
    if not homework_status:
        raise EmptyStatus('Статус домашней работы отсутствует')
    if not verdict:
        raise TypeError('Неожиданный статус домашней работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    previous_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if response['homeworks']:
                new_message = parse_status(response['homeworks'][0])
            if new_message != last_message:
                last_message = new_message
                send_message(bot, last_message)
            else:
                logging.debug("Новых фообщений нет")
        except Exception as e:
            message = f'Бот упал с ошибкой: {e}'
            if message != previous_message:
                previous_message = message
                send_message(bot, message)
                logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )
    main()
