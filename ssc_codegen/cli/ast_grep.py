from importlib import resources


RULES_PATH = resources.files("ssc_codegen.ast_grep_rules")

PY_RULES = str(RULES_PATH.joinpath("py_rules.yml"))
JS_RULES = str(RULES_PATH.joinpath("js_rules.yml"))
