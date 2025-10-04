# Brief

## Http requests vs browser render

| Aspect                              | Browser Render                                     | HTTP Request (curl, requests, etc.)              |
|-------------------------------------|---------------------------------------------------|--------------------------------------------------|
| **JavaScript Execution**            | Yes — JS is fully executed                        | No — JS is not executed                          |
| **Dynamically Loaded Content**      | Loaded (AJAX, fetch, WebSocket, etc.)             | Not loaded — must be requested manually          |
| **DOM Structure**                   | Fully rendered and updated DOM                    | Only raw HTML from the server                    |
| **Framework Support (React, Vue)**  | Works correctly                                   | Often returns an empty HTML shell                |
| **CSS and Visual Styles**           | Applied and may affect structure                  | Not applied                                      |
| **Headers, Cookies, and Sessions**  | Handled automatically by the browser              | Must be configured manually                      |
| **Bot Protection (e.g., Cloudflare)** | Often bypassed successfully                       | Often blocked or challenged                      |
| **User-Agent and Headers**          | Set automatically by the browser                  | Must be manually specified                       |
| **Performance / Speed**             | Slower (due to rendering and resource usage)      | Faster and lightweight                           |
| **Tools**                           | Puppeteer, Playwright, Selenium                   | curl, requests, httpx, aiohttp                   |
| **Asynchronous Events & Timing**    | Fully supported                                   | Not supported                                    |
| **Realism (User Behavior Emulation)** | Fully mimics real user behavior                   | Often identified as a non-human client           |

## Rest-api, graphql

Ssc-gen DSL not support works with json outputs from rest-api or graphql. For documentation APIs use tools like [mitmproxy2swagger](https://github.com/alufers/mitmproxy2swagger)

## CSS selectors

>[!tip]
> This project recommended use CSS(3) selectors if possible: it can be guaranteed convert to XPATH query syntax

- use [this cheat sheet](https://www.w3schools.com/cssref/css_selectors.php) about CSS syntax and try it in browser developer console
- use [selector gadget (chome based browser)](https://chromewebstore.google.com/detail/selectorgadget/mhjhnkcfbdhnjickkkdbjoemdmbfginb) or [scrape mate (firefox)](https://addons.mozilla.org/en-US/firefox/addon/scrapemate/) extensions for simplify create CSS selectors
- if the target site does not use SSR (Server-Side-Render backend) and the parser implies the use of http responses - download the html page using an http request and experiment in the local development stage.

### ssc-gen Limitations

- Most HTML parsers libraries implement CSS3 standard only. Check the library implementation before writing "complex" selectors
- for example, javascript, bs4 support CSS4 standard, but goquery, parsel do not
- some libraries maybe not full implementation of CSS3 standard: eg pseudo-classes (`:nth-child(), :is(), :not()`), CSS Attribute Selectors `(=, ~=, |=, ^=, $=, *=)`

### Regex

- use [regex101](https://regex101.com/) tool for write and test regexps
 avoid too complex patterns and [Catastrophic backtracking](https://regex101.com/r/iXSKTs/1/debugger): they can greatly reduce the performance of the code
- great reference for writing regular expressions - [yt-dlp/CONTRIBUTING.md#regular-expressions](https://github.com/yt-dlp/yt-dlp/blob/master/CONTRIBUTING.md#regular-expressions)

#### ssc-gen Limitations

- not support lookahed, lookbehind groups `(?=), (?!), (?<=), (?<!)`
- DSL expressions `.re(), .re_all()` capture **only first group: nested arrays are not supported**. For this you can use non-capturing groups

example, to handle multiple patterns instead of:

```
(?x)
(spam[a-z]+)
|(egg\d+)
|(foo[A-Z]+)
|(bar[abcdefh0-9]+)
```

write:

```
(
    (?x)
    (?:spam[a-z]+)
    |(?:egg\d+)
    |(?:foo[A-Z]+)
    |(?:bar[abcdefh0-9]+)
)
```
