using System.Collections.Generic;

// Every interface string has an explicit Russian and English version.
static class UiText {
    static readonly Dictionary<string,string[]> values = new Dictionary<string,string[]> {
        {"title",new[]{"Google One · шаг за шагом","Google One · step by step"}},
        {"intro",new[]{"Запустите MuMu: Root и ADB → Enable local connection.\nВойдите в Google, откройте Google One и проверьте подключение.","Start MuMu: Root and ADB → Enable local connection.\nSign in to Google, open Google One, then check the connection."}},
        {"check",new[]{"Проверить подключение","Check connection"}},
        {"install",new[]{"Установить Google One","Install Google One"}},
        {"offers",new[]{"Посмотреть предложения","List offers"}},
        {"login",new[]{"Открыть вход Google","Open Google sign-in"}},
        {"account",new[]{"В Play Маркете выбран нужный аккаунт","The correct account is selected in Play Store"}},
        {"step1",new[]{"1 · 12 месяцев","1 · 12 months"}},
        {"step2",new[]{"2 · ещё 6 месяцев","2 · add 6 months"}},
        {"step3",new[]{"3 · ещё 6 месяцев","3 · add 6 months"}},
        {"extra",new[]{"Дополнительные 6 месяцев","Extra 6 months"}},
        {"note",new[]{"После каждого шага проверяйте дату следующего платежа.\nИсходный скрипт может подтвердить распознанную нулевую цену — следите за окном MuMu.","Check the next payment date after each step.\nThe original script may confirm a detected zero price — watch the checkout in MuMu."}},
        {"initial",new[]{"Начните с проверки подключения","Start with a connection check"}},
        {"subscriptions",new[]{"Открыть подписки","Open subscriptions"}},
        {"source",new[]{"Исходники","Source code"}},
        {"log",new[]{"Журнал","Logs"}},
        {"guide",new[]{"Инструкция","Instructions"}},
        {"stop",new[]{"Остановить скрипт","Stop script"}},
        {"dark",new[]{"Тёмная тема","Dark theme"}},
        {"light",new[]{"Светлая тема","Light theme"}},
        {"close",new[]{"Остановить скрипт и закрыть приложение? Уже оформленная подписка не отменится.","Stop the script and close the app? An existing subscription will not be cancelled."}},
        {"selectAccount",new[]{"Проверьте аккаунт в Play Маркете и отметьте галочку.","Check the selected account in Play Store and tick the checkbox."}},
        {"confirmFirst",new[]{"Открыть предложение на 12 месяцев? Проверьте сумму и срок в MuMu.","Open the 12-month offer? Check the price and period in MuMu."}},
        {"confirmStack",new[]{"Предыдущий шаг оформлен, подписка активна и дата следующего платежа проверена?","Is the previous step complete, the subscription active, and the next payment date checked?"}},
        {"unpack",new[]{"Распакуйте весь ZIP в одну папку вместе с runtime.","Extract the entire ZIP to one folder, including runtime."}},
        {"running",new[]{"Выполняется: ","Running: "}},
        {"failure",new[]{"Ошибка — подробности в журнале","Error — see the log"}},
        {"ready",new[]{"Подключение готово. Выберите нужный шаг.","Connection ready. Choose a step."}},
        {"listed",new[]{"Предложения получены. Подписка не оформлялась.","Offers listed. No subscription was purchased."}},
        {"opened",new[]{"Страница открыта в MuMu.","Page opened in MuMu."}},
        {"loginOpened",new[]{"Дождитесь загрузки входа Google в MuMu и продолжите вручную.","Wait for Google sign-in to load in MuMu, then continue manually."}},
        {"result",new[]{"Результат скрипта: ","Script result: "}},
        {"review",new[]{"Проверьте результат и дату следующего платежа в MuMu.","Check the result and next payment date in MuMu."}},
        {"startError",new[]{"Не удалось запустить: ","Unable to start: "}},
        {"stopped",new[]{"Скрипт остановлен. Android и подписки не отменены.","Script stopped. Android and subscriptions are unchanged."}}
    };
    public static string Get(string key,bool english){return values[key][english?1:0];}
}
