# brief

## css selectors

>[!note] 
> in this section CSS is implied in the context of web-scraping and element extraction, not customizing styles
> 
> If you don't know css selectors, I recommend paying a little attention before installing the plugin 
> at the end of the section.

CSS-selectors (CSS3) is used in most web parsers libraries.  

For demonstration will use Chromium browser and `https://books.toscrape.com/` page 

### Prepare

1. open developer tools (ctrl + shift + I)
2. goto `Elements` (`Inspector` in firefox)
3. all examples need insert to search HTML text field:

![](assets/t_devtools.png)


### select by tag name

```css
small
```

![](assets/t_select_tag.png)

### select by class or id name

select all div tags with class="page_inner"

```css
div.page_inner
```

![](assets/t_select_class.png)

>[!tip]
> tag name is optional in CSS selectors
> you can select all tags with `.page_inner` class name
```css
.page_inner
```

select by tag id
```css
#default
```

![](assets/t_select_id.png)

>[!tip]
> tag name is optional in CSS selectors
> you can select all tags with `#default` id
```css
body#default
```

### combined selectors

Get all `<a>` tag  inside a `.sidebar` class tag

```css
.sidebar a
```

![](assets/t_select_combined.png)

```mermaid
graph TD;
    A[.sidebar] --> B1[a];
    A --> B2[a];
    A --> B3[a];
    A --> B4[...];
```

### find by attribute

find `<a>` tags with `href` attribute
```css
a[href]
```

![](assets/t_select_attr.png)

### child tags search

Find `<a>` tags where

- `<li>` tag parent
- `<ul>` tag parent for `<li>`

```css
ul > li > a
```

![](assets/t_child_find.png)

```mermaid
graph TD;
    UL[ul] --> LI[li];
    LI --> A[a];
```

### parent tags search

find all <ul> tags where <a> tag is child

```css
a +ul
```

![](assets/t_parent_find.png)

```mermaid
flowchart TD
    A[A] -->UL[ul]
```

### pseudo classes


| selector               | description                                                      |
|------------------------|------------------------------------------------------------------|
| `ul > li:first-child`  | get first child element for `<ul>` tag                           |
| `ul > li:last-child`   | get last child element for `<ul>` tag                            |
| `ul > li:nth-child(5)` | get child element for `<ul>` tag by index. Index starts at `(1)` |


### useful plugin

For chromium-based browsers, use 
[selector-gadget](https://chromewebstore.google.com/detail/selectorgadget/mhjhnkcfbdhnjickkkdbjoemdmbfginb)
extension. it will make it easier to find the optimal css selectors


## regular expressions

>[!tip]
> There are plenty of regexp tutorials on the internet, find them yourself!

- [quickref.me](https://quickref.me/regex.html) - Another regex cheat sheet
- [regex101](https://regex101.com/) - interactive tester and debugger regexps

