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
| Android Studio | эмулятор Android (не обязательно для фазы 0) | https://developer.android.com/studio |

Python ставить локально не нужно: API работает в контейнере.

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

## 3. Тесты API

При запущенном `docker compose up`, в соседнем терминале:

```bash
docker compose exec api pytest
```

## 4. Запустить приложение

Один раз сгенерируйте папки платформ (android/ios/web/windows). Существующие `lib/`, `test/` и `pubspec.yaml` при этом не перезаписываются:

```bash
cd app
flutter create . --project-name pawdex --org app.pawdex
flutter pub get
```

Для фазы 0 проще всего запускать в браузере или как Windows-приложение:

```bash
flutter run -d chrome
```

На экране будет «Hello Pawdex» и JSON-ответ от `/health`.

- **Эмулятор Android**: адрес `10.0.2.2:8000` подставляется автоматически. Android по умолчанию блокирует обычный `http://`, поэтому в `app/android/app/src/debug/AndroidManifest.xml` внутрь `<manifest>` нужно добавить `<application android:usesCleartextTraffic="true"/>`.
- **Настоящий телефон** (в той же Wi-Fi-сети): передайте IP компьютера:
  ```bash
  flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
  ```

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
