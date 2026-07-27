# NumCalc 1.0.0 release checklist

## Автоматическая проверка

- [x] Linux CI: компиляция активных Python-модулей.
- [x] Linux CI: полный `unittest discover`.
- [x] Linux CI: `node --check` собранного renderer.
- [x] Windows CI: полный `unittest discover`.
- [x] Windows CI: PyInstaller создаёт `dist\NumCalc.exe`.
- [x] Windows CI: создан и опубликован SHA-256.
- [x] Свойства EXE содержат `NumCalc 1.0.0-rc.1`.

Последняя автоматическая проверка должна оставаться зелёной после каждого изменения release-candidate ветки.

## Ручная приёмка

- [ ] Полностью пройден `WINDOWS_ACCEPTANCE.md`.
- [ ] Проверена Windows 10 либо зафиксировано «не применимо».
- [ ] Проверена Windows 11.
- [ ] Проверены NumLock-hook, tray, single-instance и автозагрузка.
- [ ] Проверены DPI 100%, 125%, 150% и 200%.
- [ ] Проверены обычное и portable-хранилища.
- [ ] Проверены `Ctrl+C`, `Alt+←/→`, `* → ⋅` и ввод `3100*.,1`.
- [ ] В диагностике нет чувствительных пользовательских данных сверх выражений/ошибок, добавленных самим пользователем.

## Выпуск

- [ ] Все блокирующие дефекты закрыты.
- [ ] `APP_VERSION` изменена с `1.0.0-rc.1` на `1.0.0`.
- [ ] Перегенерирован `version_info.txt`.
- [x] Обновлены `README.md` и `CHANGELOG.md` для release candidate.
- [x] Release-candidate EXE собран из проверенного коммита.
- [x] SHA-256 опубликован рядом с release-candidate EXE.
- [ ] Создан GitHub Release `v1.0.0`.
