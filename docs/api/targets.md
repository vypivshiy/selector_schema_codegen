# Target Converters Reference

Target backends and DOM/HTTP abstractions for Python, JavaScript, and Go code generation.

## Python Backend

### Visitor
::: ssc_codegen.targets.python.visitor.PythonVisitor

### DOM Spelling Interface
::: ssc_codegen.targets.python.html_libs.base.DomSpelling

### DOM Spelling Implementations
::: ssc_codegen.targets.python.html_libs.bs4.Bs4DomSpelling

::: ssc_codegen.targets.python.html_libs.lxml.LxmlDomSpelling

::: ssc_codegen.targets.python.html_libs.parsel.ParselDomSpelling

::: ssc_codegen.targets.python.html_libs.slax.SlaxDomSpelling

### HTTP Library Strategies
::: ssc_codegen.targets.python.http_libs.base.HttpLibStrategy

::: ssc_codegen.targets.python.http_libs.httpx.HttpxStrategy

::: ssc_codegen.targets.python.http_libs.aiohttp.AioHttpStrategy

::: ssc_codegen.targets.python.http_libs.requests.RequestsStrategy

## JavaScript Backend

### Visitor
::: ssc_codegen.targets.javascript.visitor.JsVisitor

### HTTP Library Strategies
::: ssc_codegen.targets.javascript.http_libs.base.JsHttpLibStrategy

::: ssc_codegen.targets.javascript.http_libs.fetch.FetchStrategy

::: ssc_codegen.targets.javascript.http_libs.axios.AxiosStrategy

## Go Backend

### Visitor
::: ssc_codegen.targets.golang.visitor.GoVisitor

### HTTP Library Strategies
::: ssc_codegen.targets.golang.http_libs.base.GoHttpLibStrategy

::: ssc_codegen.targets.golang.http_libs.nethttp.NetHttpStrategy
