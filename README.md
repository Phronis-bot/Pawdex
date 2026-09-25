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

Какие модели скачиваются при первом использовании (всё в том же томе):

| Модель | Зачем | Размер |
|---|---|---|
| CLIP ViT-B/32 | кошка / собака / никого, окрас | ~600 МБ |
| DINOv2 base | узнать конкретное животное | ~350 МБ |
| CLIP ViT-L/14 | порода (только когда модель уверена) | ~1,7 ГБ |
| Mask R-CNN (torchvision) | найти животное на фото: вырезать его для узнавания и размыть фон | ~170 МБ |

Серверу нужно ~4–5 ГБ оперативной памяти. Новое фото сравнивается только с животными того же вида в радиусе 300 м, и только по вырезанному животному (фон не мешает). В сохранённом фото фон размыт, чтобы по вывескам нельзя было найти место. Радиус, пороги и настройки размытия лежат в `api/app/config.py`. Как выбраны модели и пороги, показывают скрипты сравнения:

```bash
docker compose exec api python -m eval.reid_eval
```
```bash
docker compose exec api python -m eval.breed_eval
```

Если данные остались от старых версий, одноразовые скрипты доводят их до актуального состояния: `python -m app.backfill_coats` (окрас, редкость, порода) и `python -m app.reprocess_photos` (размытие фона и пересчёт отпечатков).

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
