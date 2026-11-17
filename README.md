# Граф зависимостей Maven — вариант № 9

Этап 3: транзитивный граф с рекурсивным DFS. Нужен Python 3.9+.

```bash
for graph in diamond cycle leaf; do
  python3 src/main.py --package A --version 1.0 --test \
    --repo "examples/$graph.txt"
done
```
