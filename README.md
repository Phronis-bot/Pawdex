# Pawdex

Мобильная игра-коллекция про уличных кошек и собак. Полное задание и фазы описаны в [pawdex-task.md](pawdex-task.md).

```
/api                FastAPI + Alembic (Python 3.12, работает в Docker)
/db                 образ Postgres: PostGIS + pgvector
/app                Flutter-приложение
docker-compose.yml  api + db одной командой
```

## 1. Что нужно установить (один раз)

| Инструмент | Зачем | Где взять |
|---|---|---|
| Git | репозиторий | https://git-scm.com |
| Docker Desktop (с WSL2) | API и база | https://www.docker.com/products/docker-desktop |
| Flutter SDK | приложение | https://docs.flutter.dev/get-started/install/windows |
| Android Studio | Android SDK (и эмулятор, если нет телефона) | https://developer.android.com/studio |

Python ставить локально не нужно: API работает в контейнере.

В Windows нужно включить **режим разработчика**, иначе Flutter не соберёт приложение с плагинами (ему нужны символические ссылки): **Параметры → Система → Для разработчиков → Режим разработчика**.

Проверка:

```bash
docker --version
flutter doctor
```

## 2. Запустить API и базу

Из корня репозитория:

```bash
docker compose up --build
```

При первом запуске Docker соберёт образы, это займёт несколько минут. API сам применит миграции (`alembic upgrade head`) и включит расширения PostGIS и pgvector.

Проверка: откройте http://localhost:8000/health, ответ должен быть таким:

```json
{"status": "ok", "db": "ok", "postgis": "3.4 ...", "pgvector": "0.x.x"}
```

Swagger с документацией API: http://localhost:8000/docs

Вид животного (кошка / собака / нет животного) определяет модель CLIP (`openai/clip-vit-base-patch32`). При первом определении она скачает веса (~600 МБ) в Docker-том `apidata`, поэтому первая загрузка фото займёт на минуту-две дольше обычного. Фото хранятся в том же томе, в `/data/photos`.

Конкретное животное узнаёт модель DINOv2 (`facebook/dinov2-base`, ещё ~350 МБ при первом запуске). Новое фото сравнивается только с животными того же вида в радиусе 300 м. Радиус и пороги сходства лежат в `api/app/config.py`. Как выбраны модель и пороги, показывает скрипт сравнения на фото знаменитых животных:

```bash
docker compose exec api python -m eval.reid_eval
```

## 3. Тесты API

При запущенном `docker compose up`, в соседнем терминале:

```bash
docker compose exec api pytest
```

Тесты используют отдельную базу `pawdex_test`, которая пересоздаётся при каждом запуске, так что ваши данные в `pawdex` они не трогают. Тесты классификатора прогоняют настоящую модель на картинках из `api/tests/fixtures`.

## 4. Запустить приложение

```bash
cd app
flutter pub get
```

В браузере камеры нет, но можно выбрать фото с диска, а координаты браузер спросит сам:

```bash
flutter run -d chrome
```

Внизу три вкладки: **Snap** (сфотографировать или выбрать фото), **Map** (карта) и **My sightings** (мои встречи).

Карта использует тайлы OpenStreetMap (`tile.openstreetmap.org`). Для разработки этого достаточно, но их правила запрещают большую нагрузку, поэтому перед публичным релизом нужно подключить платного поставщика тайлов (MapTiler, Stadia и т. п.): это одна строка `urlTemplate` в `app/lib/map_screen.dart`. Животные на карте показаны только шестиугольниками H3 шириной ~350 м, без точек.

- **Эмулятор Android**: адрес `10.0.2.2:8000` подставляется автоматически.
- **Android-телефон по USB** (включена отладка по USB, `flutter devices` его видит). Пробросьте порт, чтобы `localhost:8000` на телефоне вёл на компьютер. Это нужно делать заново после каждого переподключения кабеля:
  ```bash
  & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
  ```
  ```bash
  flutter run --dart-define=API_BASE_URL=http://localhost:8000
  ```
- **iPhone**: сборка возможна только на Mac.

Тесты приложения:

```bash
flutter test
```

## Полезное

```bash
docker compose down        # остановить
docker compose down -v     # остановить и стереть базу
docker compose logs -f api # логи API
```
