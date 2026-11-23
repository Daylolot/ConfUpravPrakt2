# Независимое сравнение с Maven

Проверка 23 ноября 2026 года: Apache Maven 3.9.11, Java 21,
`maven-dependency-plugin:3.8.1`. Сценарий: `examples/compare-maven.sh`.
Журналы `.log` — сохранённый вывод настоящего Maven.

| Команда | Библиотека | Ожидаемая зависимость |
| --- | --- | --- |
| `sh examples/compare-maven.sh junit tree` | junit:junit:4.13.2 | org.hamcrest:hamcrest-core:1.3 |
| `sh examples/compare-maven.sh text tree` | org.apache.commons:commons-text:1.12.0 | org.apache.commons:commons-lang3:3.14.0 |
| `sh examples/compare-maven.sh slf4j tree` | org.slf4j:slf4j-simple:2.0.13 | org.slf4j:slf4j-api:2.0.13 |
| `sh examples/compare-maven.sh junit resolve` | junit:junit:4.13.2 | Список разрешённых артефактов и сетевые запросы |

Сравниваются координаты и рёбра. Служебный корень Maven
`edu.demo:maven-reference:1.0`, тип `jar` и подпись `compile` отсутствуют
в выводе анализатора и не означают расхождения графов.

В среде проверки Java не мог обратиться к Maven Central напрямую.
Поэтому Maven получал неизменённые файлы официального HTTPS-репозитория
через локальный HTTP-посредник с кешем. Адреса 127.0.0.1 в журналах
относятся к этому транспорту. Граф и список артефактов вычислял сам Maven.
При повторении на обычном компьютере посредник не требуется.

Порядок DFS — зависимость раньше потребителя: Hamcrest, затем JUnit.
Дерево Maven показывает потребителя выше зависимости. Порядок запросов
JAR и список `dependency:resolve` не обязаны совпадать с топологическим
порядком: загрузчик использует кеш и параллельные запросы.
