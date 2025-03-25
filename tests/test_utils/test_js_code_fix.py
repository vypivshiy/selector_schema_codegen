from ssc_codegen.str_utils import js_pure_optimize_return
import pytest

JS_RETURN_OPT_CASE_1 = (
    """
_parseFoo(val){
return val;
}
""",
    """
_parseFoo(val){
return val;
}
""",
)

JS_RETURN_OPT_CASE_2 = (
    """
_parseBar(val){
let val1 = val.callSomething();
return val1;
}
""",
    """
_parseBar(val){
return val.callSomething();
}
""",
)

JS_RETURN_OPT_CASE_3 = (
    """
class A {
parse(value){
value1 = value.a()
value2 = value1.b()
return value2;
}
_parseBar(val){
let val1 = val.callSomething();
return val1;
}
_splitMe(val){
let val1 = val.callSomething();
let val2 = val1.callSomething();
return val2;
}
_splitFoo(val){
let val1 = val.callSomething();
let val2 = val1.callSomething();
let val3 = val2.callSomething();
let val4 = val3.callSomething();
return val4;
}
}
""",
    """
class A {
parse(value){
value1 = value.a()
value2 = value1.b()
return value2;
}
_parseBar(val){
return val.callSomething();
}
_splitMe(val){
let val1 = val.callSomething();
return val1.callSomething();
}
_splitFoo(val){
let val1 = val.callSomething();
let val2 = val1.callSomething();
let val3 = val2.callSomething();
return val3.callSomething();
}
}
""",
)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("", ""),
        JS_RETURN_OPT_CASE_1,
        JS_RETURN_OPT_CASE_2,
        JS_RETURN_OPT_CASE_3,
    ],
)
def test_js_return_optimize(code: str, expected: str) -> None:
    out = js_pure_optimize_return(code)
    assert out.strip() == expected.strip()
