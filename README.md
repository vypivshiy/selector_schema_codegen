# Selector Schema codegen

Experimental PoC implementation of a code generator based on KDL2.0 syntax DSL.

## install

```
uv tool install # todo: git+ URL
```

## run

generate code
```
ssc-gen generate examples/ -t js-pure -o .
```

lint syntax
```
ssc-gen check examples/
```

## syntax

see [docs](docs) and [examples](examples) how to use syntax

## LLM generate dsl config (experimental, not ready)

use [kdl-schema-dsl](.agents/skills/kdl-schema-dsl) for generate config