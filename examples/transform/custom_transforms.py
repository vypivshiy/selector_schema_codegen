"""experimental transform API for insert custom code

Useful for specific tasks, experiments or extend DSL API


in next versions, signature maybe changed


"""

from ssc_codegen.transform import BaseTransform, target, VariableType


class UpperCaseTransform(BaseTransform):
    # 1. define allowed types (for type-check tests)
    accept_type = VariableType.STRING
    return_type = VariableType.STRING

    # define methods for current module target
    @target("py_base")
    def emit_py_upper(self, prv: str, nxt: str) -> list[str]:
        return [f"{nxt} = {prv}.upper()"]
    
    # NOTE: if add extraother python impl ("py_bs4", "py_lxml"...) - duplicate code

    @target("js_pure")
    def emit_js_upper(self, prv: str, nxt: str) -> list[str]:
        return [f"{nxt} = {prv}.toUpperCase();"]


# currently, not allow accept multiple types, required create a new class
class ListUpperCaseTransform(BaseTransform):
    accept_type = VariableType.LIST_STRING
    return_type = VariableType.LIST_STRING

    @target("py_base")
    def emit_upper(self, prv: str, nxt: str) -> list[str]:
        return [f"{nxt} = [i.upper() for i in {prv}]"]


# example of how to add additional dependencies
# for more specific data transformation logic
# provide A REAL VALID CODE howto define extra import
class Base64Transform(BaseTransform):
    accept_type = VariableType.STRING
    return_type = VariableType.STRING

    # provide import module (currently implemended only in python)
    # import should be looks as a real valid import code
    @target("py_base", dependencies=["import base64"])
    def emit_py_upper(self, prv: str, nxt: str) -> list[str]:
        return [
            f"{nxt} =  base64.b64encode({prv}.encode('utf-8')).decode('utf-8')"
        ]
