# Граф зависимостей Maven — вариант № 9

Инструмент читает Maven POM по HTTP(S) средствами стандартной библиотеки
Python 3.9+. Установка Python-пакетов не требуется. Maven и JDK нужны только
для независимого сравнения.

```bash
python3 src/main.py --package A --version 1.0 --test \
  --repo examples/diamond.txt --ascii
python3 -m unittest discover -s tests -v
```

Без `--ascii` программа печатает Mermaid (`flowchart TD`). В Markdown
вставьте этот текст в блок с языком `mermaid`. Ориентация рёбер:
пакет → его зависимость. Метки ASCII: `[shared]` — уже показанный узел,
`[cycle]` — ссылка на узел текущей ветки. Диагностика циклов идёт в stderr.

В тестовом репозитории строка `A: B C` объявляет пакет A с зависимостями B
и C. Строка `A:` задаёт пакет без зависимостей. Версия тестовых пакетов —
`1.0`. Имена — одиночные заглавные латинские буквы.

Команды по этапам, результаты и подсказки для защиты: [DEFENSE.md](DEFENSE.md).
Версии этапов можно открыть командами `git switch --detach stage-1` …
`git switch --detach stage-5`. Вернуться: `git switch main`.

Три примера из Maven Central:

```bash
repo=https://repo.maven.apache.org/maven2
python3 src/main.py --package junit:junit --version 4.13.2 --repo "$repo"
python3 src/main.py --package org.apache.commons:commons-text --version 1.12.0 --repo "$repo"
python3 src/main.py --package org.slf4j:slf4j-simple --version 2.0.13 --repo "$repo"
sh examples/compare-maven.sh junit tree
sh examples/compare-maven.sh text tree
sh examples/compare-maven.sh slf4j tree
```

Анализатор ориентирован на JAR с фиксированными версиями, доступными в
одном репозитории. Поддерживает базовые свойства, наследование POM и
управляемые версии из обычного `dependencyManagement`. Граф показывает
зависимости compile/runtime самого корня и не распространяет optional
через промежуточный пакет. Maven используется в режиме потребителя:
optional-зависимости выбранной библиотеки в такой проверке исключаются.
Также полноценный Maven учитывает профили, импорт BOM, исключения,
конфликты версий и другие правила, которые анализатор не реализует.
На сложных проектах возможны отличия или ошибка при неразрешённой версии.
