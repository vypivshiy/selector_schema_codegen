from types import NoneType
from typing import Optional, List, Dict, get_args, Union, Any, NamedTuple, Type

from ssc_codegen2.document import DocumentOpNested
from ssc_codegen2.document.base import BaseDocument
from ssc_codegen2.expression import Expression
from ssc_codegen2.schema.utils import get_json_signature, get_annotations
from ssc_codegen2.tokens import TokenType
from ssc_codegen2.type_state import TypeVariableState

# TODO: typing
_T_SCHEMA_SIGNATURE = Union[str, Dict[str, str], List[Any]]


class Field:
    # MAGIC METHODS
    __AUTO_TYPE_RET__ = {
        "__PRE_VALIDATE__": TypeVariableState.NONE,
        "__SPLIT_DOC__": TypeVariableState.LIST_DOCUMENT
    }

    def _insert_return_expr(self):
        self._instructions.append(
            Expression(len(self._instructions) - 1,
                       self.RET_TYPE,
                       TokenType.ST_NO_RET)
        )

    def _insert_no_return_expr(self):
        self._instructions.append(
            Expression(len(self._instructions) - 1,
                       self.RET_TYPE,
                       TokenType.ST_RET)
        )

    def _update_num_instructions(self):
        tmp_instr = self._instructions.copy()
        new_instr: List[Expression] = []
        for i, expr in enumerate(tmp_instr):
            new_instr.append(
                Expression(
                    num=i,
                    VARIABLE_TYPE=expr.VARIABLE_TYPE,
                    TOKEN_TYPE=expr.TOKEN_TYPE,
                    arguments=expr.arguments,

                )
            )
        self._instructions = new_instr.copy()

    def __init__(self, name: str, doc: "BaseDocument"):
        self.name = name
        self.document = doc
        self._instructions = doc.instructions.copy()
        self.RET_TYPE = self.__AUTO_TYPE_RET__.get(self.name) or doc.last_var_type
        self._method = self._method_expr()

        # default value wrapper
        if self._instructions[0].TOKEN_TYPE == TokenType.OP_DEFAULT:
            self._default: Optional[Expression] = self._instructions.pop(0)
            self._update_num_instructions()  # helps correct variables naming
        else:
            self._default = None

        # add return expr
        if self.RET_TYPE == TypeVariableState.NONE:
            self._insert_return_expr()
        else:
            self._insert_no_return_expr()

    @property
    def method(self):
        return self._method

    @property
    def default(self):
        return self._default

    def _method_expr(self):
        return Expression(
            -1,
            TypeVariableState.NONE,
            TOKEN_TYPE=TokenType.ST_METHOD,
            arguments=(self.name,)
        )

    @property
    def count(self) -> int:
        return len(self._instructions)

    @property
    def expressions(self) -> List[Expression]:
        return self._instructions

    @property
    def ret_type(self) -> TypeVariableState:
        return self.document.last_var_type


class AstStruct(NamedTuple):
    cls_schema: Type["BaseSchema"]

    @property
    def name(self):
        return self.cls_schema.__name__

    @property
    def fields(self):
        return [Field(k, v) for k, v in self.cls_schema.__expr_fields__().items()]

    def docstring(self):
        return self.cls_schema.__expr_doc__()


class BaseSchema:
    # auto generate items string signature
    __SCHEMA_TYPE__: str = "BASE"
    __SIGNATURE__: Union[
        Dict, List
    ] = NotImplemented  # optional signature implement
    __REPR_TYPE_NAMES_ALIASES__ = {
        str: "String",
        Optional[str]: "null | String",
        list: "Array[String]",
        List: "Array[String]",
        list[str]: "Array[String]",
        List[str]: "Array[String]",
        Optional[list]: "null | Array[String]",
        Optional[list[str]]: "null | Array[String]",
        Optional[List]: "null | Array[String]",
        Optional[List[str]]: "null | Array[String]",
        NoneType: "null",
        None: "null",
    }
    __ARG_TYPE_STATE_ALIAS__ = {
        TypeVariableState.LIST_STRING: "Array[String]",
        TypeVariableState.STRING: "String",
        TypeVariableState.NONE: "null",
        TypeVariableState.NESTED: "Struct"
    }

    __NON_TYPED_FIELDS__ = (
        "__PRE_VALIDATE__",  # always returns None
        "__SPLIT_DOC__",  # returns array of elements or iterator of elements (LIST_DOCUMENT)
        "__doc__",  # docstring hook
    )
    __MAGIC_METHODS_NAMES__ = (
        "__PRE_VALIDATE__",
        "__SPLIT__DOC__",
        # dict list item
        "__KEY__",  # dict
        "__VALUE__",  # dict
        "__ITEM__",  # flat list
        # "__doc__",
    )
    __PRE_VALIDATE__: Optional["BaseDocument"] = None  # TODO

    @classmethod
    def check(cls) -> None:
        pass

    @staticmethod
    def _is_implemented(value) -> bool:
        return value != NotImplemented or value != None

    @classmethod
    def get_fields(cls) -> Dict[str, "BaseDocument"]:
        fields = {}

        # copy dicts to avoid runtime err:
        # RuntimeError: dictionary changed size during iteration
        cls_attrs = vars(cls).copy()

        for k, v in cls_attrs.items():
            v: "BaseDocument"
            k: str

            if k in cls.__MAGIC_METHODS_NAMES__ and cls._is_implemented(v):
                fields[k] = v
            # # nested schemas
            # elif cls.__annotations__.get(k) and issubclass(
            #     cls.__annotations__.get(k), BaseSchema
            # ):
            #     fields[k] = cls.__annotations__.get(k).get_fields()
            elif k.startswith("_"):
                continue
            else:
                fields[k] = v
        return fields

    @staticmethod
    def _is_list_schema(type_):
        type_args = get_args(type_)
        return len(type_args) == 1 and issubclass(type_args[0], BaseSchema)

    @classmethod
    def get_fields_signature(cls) -> Dict[str, _T_SCHEMA_SIGNATURE]:
        signature = {}
        # copy dicts to avoid runtime err:
        # RuntimeError: dictionary changed size during iteration
        cls_annotations = get_annotations(cls).copy()

        for k, v in cls.get_fields().items():
            if type_ := cls_annotations.get(k):
                # schema
                if issubclass(type_, BaseSchema):
                    type_.check()
                    if type_.__SIGNATURE__ != NotImplemented:
                        signature[k] = type_.__SIGNATURE__
                    else:
                        signature[k] = type_.get_fields_signature()
                elif (type_args := get_args(type_)) and issubclass(type_args[0], BaseSchema):
                    t: BaseSchema = type_args[0]
                    t.check()
                    if t.__SIGNATURE__ != NotImplemented:
                        signature[k] = t.__SIGNATURE__
                    else:
                        signature[k] = t.get_fields_signature()
                # other
                else:
                    signature[k] = cls.__REPR_TYPE_NAMES_ALIASES__.get(type_)

            elif k not in cls.__NON_TYPED_FIELDS__:
                type_ = cls.__ARG_TYPE_STATE_ALIAS__.get(v.last_var_type, "???")  # TODO
                signature[k] = type_

            elif isinstance(v, DocumentOpNested):
                signature[k] = v.instructions[-1].arguments[1].get_fields_signature()
        return signature

    def __repr__(self):
        return f"{self.__class__.__name__}[{self.__SCHEMA_TYPE__}]: {self.get_fields_signature()}"

    # TODO refactoring

    @classmethod
    def get_ast_struct(cls) -> AstStruct:
        return AstStruct(cls)

    @classmethod
    def __expr_fields__(cls) -> Dict[str, "BaseDocument"]:
        dct_copy = vars(cls).copy()  # copy avoid runtime err
        fields: dict[str, "BaseDocument"] = {
            k: v for k, v in dct_copy.items() if isinstance(v, BaseDocument)
        }
        return fields

    @classmethod
    def __expr_doc__(cls, indent: int = 2, sep: str = '\n\n') -> Expression:
        """get docstring token"""
        docstr = cls.__doc__ or ''
        signature = get_json_signature(cls, indent=indent)
        full_doc = f"{docstr}{sep}{signature}"
        return Expression(num=-2,
                          TOKEN_TYPE=TokenType.ST_DOCSTRING,
                          VARIABLE_TYPE=TypeVariableState.NONE,
                          arguments=(full_doc,))

    @classmethod
    def __expr_init__(cls):
        return Expression(-1, TOKEN_TYPE=TokenType.ST_INIT, VARIABLE_TYPE=TypeVariableState.DOCUMENT)


if __name__ == '__main__':
    print(BaseSchema.__expr_doc__())
