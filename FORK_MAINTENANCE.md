# Руководство по поддержке форка (Phone Transfer Payment Feature)

## 📋 Обзор

Этот документ описывает архитектуру изоляции функционала оплаты по номеру телефона для минимизации конфликтов при обновлении upstream проекта.

## 🎯 Принципы изоляции

### 1. Модульная структура
Весь специфичный код вынесен в отдельные модули:
- `bot/handlers/admin/phone_transfer_payments.py` - admin handlers
- `bot/services/phone_transfer_service.py` - бизнес-логика
- `db/models.py` - модель `PhoneTransferPayment` (только добавление таблицы)

### 2. Условная регистрация
Роутеры регистрируются только если `PHONE_TRANSFER_ENABLED=True`:

```python
# bot/handlers/admin/__init__.py
try:
    from config.settings import get_settings
    settings = get_settings()
    if settings.PHONE_TRANSFER_ENABLED:
        from . import phone_transfer_payments
        admin_router_aggregate.include_router(phone_transfer_payments.router)
except Exception:
    pass  # Graceful degradation
```

### 3. Минимальные изменения в core файлах

#### ✅ Безопасные изменения (низкий риск конфликтов):

**`bot/app/factories/build_services.py`**
```python
# Только добавление нового сервиса
from bot.services.phone_transfer_service import PhoneTransferService

phone_transfer_service = PhoneTransferService(settings)

return {
    # ... existing services ...
    "phone_transfer_service": phone_transfer_service,  # Добавлено
}
```

**`bot/keyboards/inline/user_keyboards.py`**
```python
# Добавление кнопки через условие
if settings.PHONE_TRANSFER_ENABLED:
    builder.button(text=_("pay_with_phone_transfer_button"),
                   callback_data=f"pay_phone_transfer:{months}:{price}")
```

**`db/models.py`**
```python
# Только добавление новых таблиц - не изменяет существующие
class PhoneTransferPayment(Base):
    __tablename__ = "phone_transfer_payments"
    # ...
```

**`bot/handlers/admin/payments.py`**
```python
# Добавление provider в dictionary
provider_text = {
    'yookassa': 'YooKassa',
    # ... existing ...
    'phone_transfer': 'Перевод по номеру',  # Добавлено
}

# Добавление статуса в условие
if payment.provider == 'phone_transfer':
    status_emoji = "✅" if payment.status == 'approved' else (...)
else:
    # existing logic
```

**`.env.example`**
```bash
# Добавление новых переменных в конец секции
PHONE_TRANSFER_ENABLED=true
PHONE_TRANSFER_NUMBER=+79001234567
PHONE_TRANSFER_BANK_NAME="Сбербанк"
PHONE_TRANSFER_INSTRUCTIONS="Укажите в комментарии: VPN подписка"
```

## 📝 Процесс обновления upstream

### Шаг 1: Подготовка
```bash
# Сделайте бекап текущих изменений
git stash
git fetch upstream
```

### Шаг 2: Анализ изменений
```bash
# Проверьте, какие файлы изменились
git diff upstream/main..HEAD --stat

# Особое внимание на:
# - bot/handlers/admin/payments.py (формат статусов)
# - bot/keyboards/inline/user_keyboards.py (функция get_payment_method_keyboard)
# - db/models.py (связи между таблицами)
```

### Шаг 3: Слияние
```bash
git merge upstream/main
```

### Шаг 4: Разрешение конфликтов

#### ⚠️ Частые конфликты и их решение:

**1. `bot/handlers/admin/payments.py` - provider_text dictionary**
```python
# ✅ Правильно: объединить оба варианта
provider_text = {
    'yookassa': 'YooKassa',
    # ... upstream providers ...
    'phone_transfer': 'Перевод по номеру',  # Ваше
}
```

**2. `bot/keyboards/inline/user_keyboards.py` - payment buttons**
```python
# ✅ Правильно: сохранить все кнопки
if settings.NEW_UPSTREAM_PROVIDER:  # upstream
    builder.button(...)
if settings.PHONE_TRANSFER_ENABLED:  # ваше
    builder.button(text=_("pay_with_phone_transfer_button"), ...)
```

**3. `db/models.py` - relationships**
```python
# ✅ Правильно: добавить ваш relationship
class PromoCode(Base):
    # ... upstream relationships ...
    phone_transfer_payments_where_used = relationship(
        "PhoneTransferPayment", 
        back_populates="promo_code_used"
    )  # Ваше
```

**4. `.env.example` - конфигурация**
```bash
# ✅ Правильно: добавить ваши переменные в соответствующие секции
# Payment Method Toggles
YOOKASSA_ENABLED=True
NEW_PROVIDER_ENABLED=True  # upstream
PHONE_TRANSFER_ENABLED=true  # ваше

# Phone Transfer Configuration (в конце файла)
PHONE_TRANSFER_NUMBER=+79001234567
# ...
```

### Шаг 5: Тестирование
```bash
# Проверьте, что функционал работает
python -m pytest tests/

# Запустите бота
python bot/main_bot.py
```

## 🔧 Структура модулей Phone Transfer

```
bot/
├── handlers/
│   ├── admin/
│   │   ├── phone_transfer_payments.py  # 🔒 Изолированный модуль
│   │   ├── payments.py                 # ⚠️ Минимальные изменения
│   │   └── __init__.py                 # ✅ Условная регистрация
│   └── user/
│       └── phone_transfer_handler.py   # 🔒 Изолированный модуль
├── services/
│   └── phone_transfer_service.py       # 🔒 Изолированный модуль
├── keyboards/
│   └── inline/
│       ├── admin_keyboards.py          # 🔒 Функции для phone_transfer
│       └── user_keyboards.py           # ⚠️ Одна кнопка if ENABLED
└── dal/
    └── phone_transfer_dal.py           # 🔒 Изолированный модуль

db/
└── models.py                            # ⚠️ Только PhoneTransferPayment

config/
└── settings.py                          # ✅ PHONE_TRANSFER_* переменные
```

## 📊 Риски конфликтов (по файлам)

| Файл | Риск | Причина | Решение |
|------|------|---------|---------|
| `phone_transfer_*.py` | 🟢 Нет | Ваши файлы | - |
| `db/models.py` | 🟡 Низкий | Добавление таблицы | Всегда принимайте обе стороны |
| `build_services.py` | 🟡 Низкий | Добавление в dict | Объединяйте словари |
| `user_keyboards.py` | 🟠 Средний | Изменение кнопок | Сохраняйте все if conditions |
| `payments.py` | 🟠 Средний | Dictionary + статусы | Объединяйте dictionaries |
| `.env.example` | 🟠 Средний | Новые переменные | Добавляйте секцию в конец |
| `__init__.py` | 🔴 Высокий | Регистрация роутеров | Используйте условную регистрацию |

## 🚀 Автоматизация

### Git hooks для предупреждения

Создайте `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Проверка, что изолированные модули не изменены
ISOLATED_FILES=(
    "bot/handlers/admin/phone_transfer_payments.py"
    "bot/services/phone_transfer_service.py"
)

for file in "${ISOLATED_FILES[@]}"; do
    if git diff --cached --name-only | grep -q "$file"; then
        echo "✅ Изменения в изолированном модуле: $file"
    fi
done

# Предупреждение об изменениях в core файлах
CORE_FILES=(
    "bot/handlers/admin/payments.py"
    "bot/keyboards/inline/user_keyboards.py"
    "db/models.py"
)

for file in "${CORE_FILES[@]}"; do
    if git diff --cached --name-only | grep -q "$file"; then
        echo "⚠️  ВНИМАНИЕ: Изменения в core файле: $file"
        echo "   Убедитесь, что изменения минимальны!"
    fi
done
```

## 📚 Дополнительная документация

- **Архитектура платежей**: См. основной проект
- **Workflow phone transfer**: См. `bot/services/phone_transfer_service.py`
- **Миграции БД**: См. `db/migrator.py`

## 💡 Советы

1. **Регулярно синхронизируйте с upstream** (раз в неделю)
2. **Делайте атомарные коммиты** для phone_transfer функционала
3. **Тегируйте коммиты**: `[FORK]` для ваших изменений
4. **Ведите changelog** ваших модификаций
5. **Используйте feature branches** для экспериментов

## 🆘 Помощь

Если возникли сложные конфликты:
1. Создайте backup branch: `git branch backup-$(date +%Y%m%d)`
2. Посмотрите историю: `git log --graph --oneline --all`
3. Используйте: `git mergetool`
4. В крайнем случае: `git merge --abort` и cherry-pick изменения

---

**Последнее обновление**: 2025-10-30

