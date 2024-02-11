from abc import abstractmethod
from enum import IntEnum

from typing import Optional, Sequence

from ssc_codegen.document import Document
from ssc_codegen.validate import assert_


class StructType(IntEnum):
    BASE = 0
    LIST = 1
    DICT = 2
    ITEM = 3


class BaseStructStrategy:
    TYPE: StructType = StructType.BASE

    def __init__(self):
        self.assert_ = assert_

    def __pre_validate_document__(self, doc: Document) -> Optional[Document]:
        """optional pre validation method before parse"""
        pass

    def __split_document_entrypoint__(self, doc: Document) -> Document:
        """split document entry point. should be returns LIST_DOCUMENT type state"""
        pass


class ListStruct(BaseStructStrategy):
    """Generate structure like: [{K1: V1, ..., KN, VN}, ...]

    should be provided split document logic (should be return LIST_DOCUMENT type)
    """
    TYPE = StructType.LIST

    @abstractmethod
    def __split_document_entrypoint__(self, doc: Document) -> Document:
        pass


class DictStruct(BaseStructStrategy):
    """Generate structure like: {K1: V2, ..., KN, VN}

       should be provided:

        1. split document logic (should be return LIST_DOCUMENT type)

        2. get key logic

        3. get value logic

    """
    TYPE = StructType.DICT

    # struct for generate

    @abstractmethod
    def __split_document_entrypoint__(self, doc: Document) -> Sequence[Document]:
        pass

    @abstractmethod
    def key(self, doc: Document) -> Document:
        pass

    @abstractmethod
    def value(self, doc: Document) -> Document:
        pass


class ItemStruct(BaseStructStrategy):
    """generate dict structure with first founded element

    {K1: V2, K2: V2, ..., KN: VN}"""
    TYPE = StructType.ITEM
    #
    pass
