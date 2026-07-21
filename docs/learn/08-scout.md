# 08. Scout — разведка HTML

**Версия DSL:** 2.1
**Последнее обновление:** 2026-07-21 (discover v2: item_selector, sample list, table_candidates, page_summary, top_level_keys)

`ssc-gen scout` — вспомогательный инструмент для разведки HTML перед
написанием `.kdl` схемы. Регулярные выражения по тексту/атрибутам,
пересечение с CSS-селектором, навигация (parent/child/sibling), режим
обзора `--discover`.

CSS сам по себе не может выразить «найди все теги, в тексте которых есть
цена формата `$X.YZ`» — `scout` может. Возвращает готовый CSS-path для
каждого матча, который можно вставить в `.kdl`.

## Первый вызов — обзор страницы

Перед написанием схемы прогоните `--discover` — это single-call замена
слепому перебору селекторов:

```bash
ssc-gen scout -i page.html --discover -f json
```

Возвращает:
- `sample_normalized: true` — глобальный маркер: все `sample` значения
  whitespace-collapsed (`get_text(strip=True)`), не verbatim HTML.
  Не пишите regex, ожидающий сырые `\n` / multi-space runs.
- `tag_stats` — частота тегов.
- `class_stats` — частота классов.
- `id_stats` — частота id.
- `data_attrs` — встречающиеся `data-*` атрибуты.
- `repeat_containers` — повторяющиеся контейнеры (кандидаты в `(list)struct`)
  с pre-computed `common_descendants` — подсказки для полей. Каждый контейнер
  дополнительно содержит:
  - `item_selector` — короткий стабильный CSS (якорь на редком `#id` /
    классе, ≤3 хопа). При `selector_stability: "fragile"` — путь ненадёжен.
  - `single_link_item`, `has_th_row`, `single_label_child` — булевы флаги
    формы элементов (навигация / тело таблицы / "метка: значение").
  - В каждом `common_descendants[i]`: `sample` (список ≤3 значений из
    головы) и опционально `sample_tail` (≤3 значения из хвоста после
    дедупликации против `sample`).
- `table_candidates` — `<table>` элементы с pre-extracted ключами строк
  (из `<th>`, или первая `<td>` каждой строки при отсутствии `<th>`).
- `page_summary` — сводка: `has_table`, `has_embedded_json`,
  `container_count_estimate`.
- `json_signals` — встроенный JSON (в `<script>`, `data-*` атрибутах,
  `var X = {...}`) для `jsonify`-сценариев. Каждый signal включает
  `top_level_keys` (до 10 ключей) если body парсится как JSON-объект
  или массив объектов.

## Фильтры (комбинируются через И)

| Флаг | Форма | Описание |
|---|---|---|
| `--text REGEX` | regex | совпадение в тексте потомков |
| `--attr NAME` | presence | атрибут присутствует |
| `--attr NAME=VAL` | exact | точное значение |
| `--attr NAME=~REGEX` | regex | regex на значение атрибута |
| `--tag NAME` | exact | фильтр по имени тега |
| `--css SEL` | css | исходное множество кандидатов (intersect) |

Модификаторы:
- `-I` / `--ignore-case` — case-insensitive regex.
- `-F` / `--fixed` — трактовать pattern как literal (escape regex).
- `-v` / `--invert` — инвертировать матч (вернуть теги НЕ подходящие).

## Навигация

После фильтрации можно сдвинуться по дереву (применяются по порядку,
dedup по `id(tag)`):

- `--up N` — подняться на N уровней вверх.
- `--down N` — спуститься на N first-child уровней.
- `--next N` — N следующих соседей.
- `--prev N` — N предыдущих соседей.

## Output

Поля через `--fields` (comma-separated, default `path,tag,text`):

- `path` — copy-pasteable CSS-селектор.
- `tag`, `text`, `html`, `attrs`, `classes`, `index`, `line`.
- `attr.NAME` — конкретный атрибут.

Пагинация и truncation:
- `--limit N` (default 50)
- `--offset N`
- `--snippet LEN` (default 200) — обрезать `text`/`html` до N символов.
- `-c` / `--count` — только количество матчей.

## Примеры

```bash
# FIRST CALL — обзор страницы
ssc-gen scout -i page.html --discover -f json

# regex на текст — найти цены
ssc-gen scout -i page.html --text '\$\d+\.\d{2}' --fields path -f json

# regex на значение атрибута — найти продукты по href
ssc-gen scout -i page.html --attr 'href=~^/product/\d+' -f json

# CSS intersect + подняться к родительскому контейнеру
ssc-gen scout -i page.html --css ".price" --up 2 --fields path -f json

# one-off извлечение (без .kdl схемы)
ssc-gen scout -i page.html --css ".product-card" --fields attr.data-id,text -f json

# HTML через stdin
curl -s https://example.com | ssc-gen scout --attr 'class=~\bbtn\b' -f json

# только количество (exit 0 на match, 1 на no-match, 2 на error)
ssc-gen scout -i page.html --tag img --attr alt -v -c
```

## Exit codes

- `0` — есть матчи.
- `1` — нет матчей.
- `2` — ошибка (невалидный фильтр, пустой input, etc).
