from typing import Literal, TypeAlias

RESERVED_METHODS = {
    '__PRE_VALIDATE__', '__SPLIT_DOC__', '__KEY__', '__VALUE__', '__ITEM__', '__START_PARSE__'
}

M_START_PARSE: TypeAlias = Literal['__START_PARSE__']
M_PRE_VALIDATE: TypeAlias = Literal['__PRE_VALIDATE__']
M_SPLIT_DOC: TypeAlias = Literal['__SPLIT_DOC__']
M_ITEM: TypeAlias = Literal['__ITEM__']
M_KEY: TypeAlias = Literal['__KEY__']
M_VALUE: TypeAlias = Literal['__VALUE__']
