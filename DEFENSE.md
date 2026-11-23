# Защита второй работы — вариант № 9

Все команды выполняются в обычном Терминале Mac из папки проекта.
Команды `git switch` предполагают чистую рабочую копию. После клонирования
используются удалённые ветки `origin/stage-N`. При переходе
на ранний этап этот файл временно исчезнет: держи инструкцию открытой.

## 1. Конфигурация

```bash
git switch --detach origin/stage-1
sh examples/stage1.sh
```

Покажи пять строк: `package`, `repo`, `test`, `version`, `ascii`.
Дальше сценарий проверяет пять неправильных запусков и ожидает код 2.
В `src/main.py` покажи `parse_options()` и `run()`.
Скажи: «Настройки считываются из командной строки. Первый прототип
проверяет значения и печатает их как ключ=значение».

## 2. Прямые зависимости

```bash
git switch --detach origin/stage-2
repo=https://repo.maven.apache.org/maven2
python3 src/main.py --package junit:junit --version 4.13.2 --repo "$repo"
```

В выводе найди Hamcrest 1.3. В `src/maven.py` покажи `read_pom`,
`MavenRepository.direct` и подстановку свойств.
Скажи: «Координаты превращаю в путь к POM конкретной версии. Скачиваю
XML и читаю секцию зависимостей. Maven для этого не запускается.
На этом этапе выводятся прямые зависимости вместе со scope».

## 3. DFS и циклы

```bash
git switch --detach origin/stage-3
python3 src/main.py --package A --version 1.0 --test --repo examples/diamond.txt
python3 src/main.py --package A --version 1.0 --test --repo examples/cycle.txt
python3 src/main.py --package A --version 1.0 --test --repo examples/leaf.txt
```

На первом графе D достижим по двум ветвям; на втором появляется
`cycle: A -> B -> C -> A`; на третьем выводится только A.
Покажи `build_graph` и вложенный `visit` в `src/graph.py`.
Скажи: «DFS рекурсивно посещает соседей. Если узел уже на текущем пути,
сохраняю ребро цикла, но прекращаю углубление по этой ветви».

## 4. Порядок загрузки и Maven

```bash
git switch --detach origin/stage-4
repo=https://repo.maven.apache.org/maven2
python3 src/main.py --package A --version 1.0 --test --repo examples/diamond.txt
python3 src/main.py --package A --version 1.0 --test --repo examples/leaf.txt
python3 src/main.py --package A --version 1.0 --test --repo examples/cycle.txt
python3 src/main.py --package junit:junit --version 4.13.2 --repo "$repo"
sh examples/compare-maven.sh junit resolve
sh examples/compare-maven.sh junit tree
```

Ожидается D, B, C, A; отдельно одиночный A и диагностика невозможности
порядка при цикле. Для JUnit порядок: Hamcrest, затем JUnit.
В `src/graph.py` покажи `finished.append(node)` после обхода детей.
Скажи: «Это порядок готовности зависимостей. Maven выводит дерево сверху
вниз, поэтому JUnit расположен над Hamcrest. В проверочном запуске Maven
3.9.11 запросил JAR JUnit раньше JAR Hamcrest. Это порядок сетевых
запросов, а не порядок готовности: Maven загружает также метаданные
и плагины, может качать параллельно и использовать кеш».

На Mac для сравнения отдельно нужны команды `mvn -version` и
`java -version` с успешным результатом.

## 5. Mermaid, ASCII и три пакета

```bash
git switch --detach origin/stage-5
repo=https://repo.maven.apache.org/maven2
python3 src/main.py --package junit:junit --version 4.13.2 --repo "$repo"
python3 src/main.py --package org.apache.commons:commons-text --version 1.12.0 --repo "$repo"
python3 src/main.py --package org.slf4j:slf4j-simple --version 2.0.13 --repo "$repo"
python3 src/main.py --package A --version 1.0 --test --repo examples/diamond.txt --ascii
sh examples/compare-maven.sh junit tree
sh examples/compare-maven.sh text tree
sh examples/compare-maven.sh slf4j tree
python3 -m unittest discover -s tests -v
git switch main
```

Для ASCII на реальном пакете добавь `--ascii` в ту же команду запуска.
Открой `src/render.py`: `mermaid` даёт узлам уникальные идентификаторы
и печатает рёбра; `ascii_tree` показывает ветви с отступами.
Сравнивай координаты и связи, не служебные подписи: Maven добавляет свой
проект-обёртку `edu.demo:maven-reference`, тип `jar` и scope.
Ожидаемые основные рёбра: JUnit → Hamcrest, Commons Text → Commons Lang,
SLF4J Simple → SLF4J API.
