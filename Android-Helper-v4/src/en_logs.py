"""English presentation of worker messages. Technical codes remain unchanged."""
import re

MESSAGES = {
    'Базовая проверка окружения завершена': 'Environment check complete',
    'Используется текущий аккаунт Play; проверьте его вручную (--force)': 'Using the current Play account; check it manually (--force)',
    'Android подключён': 'Android connected', 'Эмулятор подключён': 'Emulator connected',
    'Получен root через ADB': 'Root access obtained through ADB',
    'Frida уже работает в Android': 'Frida is already running in Android',
    'Frida запущена в Android': 'Frida started in Android',
    'Не удалось запустить Frida в Android': 'Unable to start Frida in Android',
    'Загрузка Frida для Android…': 'Downloading Frida for Android…',
    'Модуль оплаты готов': 'Billing module ready', 'Модуль оплаты скопирован': 'Billing module copied',
    'Копирование модуля оплаты в Android…': 'Copying the billing module to Android…',
    'Play Маркет работает': 'Play Store is running', 'Запуск Play Маркета…': 'Starting Play Store…',
    'Play Маркет запущен': 'Play Store started',
    'Play Маркет не запустился. Откройте его вручную или перезапустите MuMu.': 'Play Store did not start. Open it manually or restart MuMu.',
    'Получение предложений Google Play…': 'Querying Google Play offers…',
    'Проверка суммы в окне оплаты…': 'Checking the checkout price…',
    'Окно оплаты открыто': 'Checkout opened',
    'Скрипт подтвердил подписку с распознанной нулевой ценой': 'The script confirmed a subscription with a detected zero price',
    'Скрипт подтвердил бесплатный период': 'The script confirmed the free trial',
    'Окно оплаты не обнаружено; проверьте текущую подписку и экран MuMu.': 'Checkout not found; check the current subscription and the MuMu screen.',
    'Сумма сейчас': 'Current price', 'не равна нулю; подтверждение не нажато': 'is not zero; confirmation was not clicked',
    'Аккаунт не соответствует условиям бесплатного периода': 'The account is not eligible for the free trial',
    'Подтверждение не нажато': 'Confirmation was not clicked',
    'Текущий аккаунт': 'Current account', 'Шаг': 'Step', 'Итог': 'Summary', 'Результат': 'Result',
    'Отчёт сохранён в': 'Report saved to', 'аккаунт(ов); начало операции': 'account(s); starting operation', 'Всего': 'Total',
    'Чтение токена действующей подписки…': 'Reading the active subscription token…',
    'Токен действующей подписки получен': 'Active subscription token received',
    'Будет использован режим обновления подписки': 'Subscription upgrade mode will be used',
    'Токен не прочитан; попытка запроса действующей подписки через Google Play.': 'Token unavailable; querying the active subscription through Google Play.',
    'Прокси внутри Android отключён': 'Android proxy disabled', 'предыдущее значение': 'previous value',
    'для подключения к Google Play': 'to connect to Google Play',
    'Временно остановлено приложение Android': 'Android application temporarily stopped',
    'оно может перехватывать соединение Play Маркета': 'it may intercept Play Store connections',
    'Загрузка': 'Downloading', 'неизвестно': 'unknown', 'аккаунт': 'account',
    'Не удалось подтвердить': 'Unable to confirm', 'Завершено': 'Complete',
    'сообщение компонента': 'component message',
    'Подключение к Android…': 'Connecting to Android…',
    'Дождитесь загрузки входа Google в MuMu и продолжите вручную.': 'Wait for Google sign-in to load in MuMu, then continue manually.',
    'Проверка UTF-8 завершена': 'UTF-8 check complete',
    'Операция не завершилась. Причина указана в журнале. Следующий шаг пока не запускайте.': 'The operation did not complete. See the log before starting another step.',
    'ADB не выделил порт для Frida.': 'ADB did not allocate a Frida port.',
    'ADB, root и Frida проверены, но Play Маркет не запустился. Откройте его вручную в MuMu или перезапустите MuMu, затем повторите проверку.': 'ADB, root and Frida checked, but Play Store did not start. Open it manually or restart MuMu, then check again.',
    'Установите Google One в MuMu. Для этого нажмите «Установить Google One», затем повторите проверку.': 'Install Google One in MuMu using the Install Google One button, then check again.',
    'В MuMu включите Root и перезапустите эмулятор. Затем повторите проверку.': 'Enable Root in MuMu, restart the emulator, then check again.',
    'MuMu не подключён. Запустите его и включите ADB → Enable local connection.': 'MuMu is not connected. Start it and enable ADB → Enable local connection.',
    'ADB отсутствует. Распакуйте весь пакет вместе с папкой runtime.': 'ADB is missing. Extract the entire package, including runtime.',
    'Frida не запустилась внутри Android. Проверьте root; подробности есть в журнале.': 'Frida did not start in Android. Check root and see the log for details.',
    'Не удалось запустить': 'Unable to start',
    'Приложение не установлено в MuMu: ': 'Application is not installed in MuMu: ',
    'Не найдена стартовая Activity приложения: ': 'Launcher activity was not found: ',
    'Android не смог открыть приложение: ': 'Android could not open the application: ',
    'Приложение не запустилось вовремя. Откройте его вручную в MuMu: ': 'The application did not start in time. Open it manually in MuMu: ',
}

def translate(text):
    # Preserve paths and filenames even if they contain Cyrillic characters.
    pattern = r'([A-Za-z]:[\\/][^\r\n]*|\b\S*\.py\b|\b\S*\.apk\b)'
    parts = re.split(pattern, text)
    for i in range(0, len(parts), 2):
        for original, translated in sorted(MESSAGES.items(), key=lambda item: -len(item[0])):
            parts[i] = parts[i].replace(original, translated)
        parts[i] = re.sub(r'[А-Яа-яЁё]+(?:[ \t]+[А-Яа-яЁё]+)*', 'component message', parts[i])
    return ''.join(parts)
