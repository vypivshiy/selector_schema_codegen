# Selector Schema codegen

Experimental PoC implementation of a code generator based on KDL2.0 syntax DSL.

## install

```
uv tool install git+https://github.com/vypivshiy/selector_schema_codegen@features-kdl
```

## usage

### generate modules

```
ssc-gen generate examples/ -t js-pure -o .
```

### lint syntax

```
ssc-gen check examples/
```

### test schema by html output

from file:
```
python main.py run .\examples\booksToScrape.kdl:MainCatalogue -t py-bs4 -i index.html
```

from stdin:
```
curl https://books.toscrape.com/ | python main.py run .\examples\booksToScrape.kdl:MainCatalogue -t py-bs4
```

### test selectors:

from file
```
python main.py health .\examples\booksToScrape.kdl:MainCatalogue -i index.html
```

from stdin
```
curl https://books.toscrape.com/catalogue/page-2.html | python main.py health .\examples\booksToScrape.kdl:MainCatalogue
```


## syntax

see [docs](docs) and [examples](examples) how to use syntax

## LLM generate dsl config (experimental, not ready)

### prompt

use [SYSTEM_PROMPT](SYSTEM_PROMPT.md) for use in API pipelines or chats. before generate, call `ssc-gen check [FILES...] -f json` liner and send errors output if exists

### skill
use [kdl-schema-dsl](.agents/skills/kdl-schema-dsl) for generate config