# Граф зависимостей Maven — вариант № 9

Этап 4: порядок загрузки зависимостей. В списке каждая зависимость идёт
раньше пакета, которому она нужна. При цикле такой порядок невозможен.
Нужен Python 3.9+.

```bash
for graph in diamond cycle leaf; do
  python3 src/main.py --package A --version 1.0 --test \
    --repo "examples/$graph.txt"
done
```

Для сравнения вручную запустите:

```bash
python3 src/main.py --package junit:junit --version 4.13.2 \
  --repo https://repo.maven.apache.org/maven2
sh examples/compare-maven.sh junit
```

Для JUnit порядок DFS: сначала Hamcrest, затем JUnit. Maven показывает
JUnit первым, а Hamcrest под ним: это порядок отображения дерева,
а не порядок готовности пакетов. Сетевые загрузки можно наблюдать,
убрав `-ntp` и добавив Maven опцию `-Dmaven.repo.local=/путь/к/новой/папке`.
Maven также скачивает POM родителей и плагины; эти файлы не являются
рёбрами графа библиотек. Кеш и параллелизм влияют на сетевой порядок.
