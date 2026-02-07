# AGENTS.md

Ты — автономный инженер. Работаешь только через ветки и Pull Request.
main защищён. Нельзя ломать сборку/тесты.

## Platform policy
- Target framework: net8.0 ONLY
- Using preview .NET versions is forbidden
- CI must use the same SDK version as projects

## Обязательные правила
- НЕ пушь напрямую в main. Только PR.
- Перед тем как считать задачу готовой: прогнать тесты. Если красное — чинить до зелени.
- Делай маленькие коммиты, понятные сообщения.
- Не добавляй зависимости без причины.
- Симуляция (Core) должна быть в чистом .NET без Unity API.
- Любая случайность — через интерфейс IRandom с seed (детерминизм для тестов).

## Definition of Done
- Все тесты зелёные.
- PR содержит:
  - что сделано
  - как проверить (команды)
  - что осталось/известные ограничения

## Команды
- dotnet test ./core/CoreSim.Tests/CoreSim.Tests.csproj
