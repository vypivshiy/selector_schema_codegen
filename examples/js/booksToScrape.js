// Token: DOCSTRING
/**
 * Dummy parser config for http://books.toscrape.com/
 */

// Token: DOCSTRING
/**
 * fetch add patches and urls from <a> tag
 *
 * [
 *     "String",
 *     "..."
 * ]
 */
// Token: STRUCT
class Urls {
// Token: STRUCT_INIT
    constructor(doc) {
        this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : doc;
    }

// Token: STRUCT_PART_DOCUMENT
    _splitDoc(value) {
// Token: EXPR_CSS_ALL
        let value1 = value.querySelectorAll('a');
// Token: EXPR_RETURN ret_type: LIST_DOCUMENT
        return value1;
    }

// Token: STRUCT_FIELD
    _parseItem(value) {
// Token: EXPR_ATTR
        let value1 = value.getAttribute('href');
// Token: EXPR_RETURN ret_type: STRING
        return value1;
    }

// Token: STRUCT_PARSE_START struct_type: FLAT_LIST
// Call instructions count: 2
    parse() {
        let items = Array.from(this._splitDoc(this._doc)).map((e) => this._parseItem(e));
        return items;
    }
}

// Token: DOCSTRING
/**
 *
 *
 * [
 *     {
 *         "name": "String",
 *         "image_url": "String",
 *         "url": "String",
 *         "rating": "String",
 *         "price": "Int"
 *     },
 *     "..."
 * ]
 */
// Token: STRUCT
class Books {
// Token: STRUCT_INIT
    constructor(doc) {
        this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : doc;
    }

// Token: STRUCT_PART_DOCUMENT
    _splitDoc(value) {
// Token: EXPR_CSS_ALL
        let value1 = value.querySelectorAll('.col-lg-3');
// Token: EXPR_RETURN ret_type: LIST_DOCUMENT
        return value1;
    }

// Token: STRUCT_FIELD
    _parseName(value) {
// Token: EXPR_CSS
        let value1 = value.querySelector('.thumbnail');
// Token: EXPR_ATTR
        let value2 = value1.getAttribute('alt');
// Token: EXPR_RETURN ret_type: STRING
        return value2;
    }

// Token: STRUCT_FIELD
    _parseImageUrl(value) {
// Token: EXPR_CSS
        let value1 = value.querySelector('.thumbnail');
// Token: EXPR_ATTR
        let value2 = value1.getAttribute('src');
// Token: EXPR_STRING_FORMAT
        let value3 = `https://${value2}`;
// Token: EXPR_RETURN ret_type: STRING
        return value3;
    }

// Token: STRUCT_FIELD
    _parseUrl(value) {
// Token: EXPR_CSS
        let value1 = value.querySelector('.image_container > a');
// Token: EXPR_ATTR
        let value2 = value1.getAttribute('href');
// Token: EXPR_RETURN ret_type: STRING
        return value2;
    }

// Token: STRUCT_FIELD
    _parseRating(value) {
// Token: EXPR_CSS
        let value1 = value.querySelector('.star-rating');
// Token: EXPR_ATTR
        let value2 = value1.getAttribute('class');
// Token: EXPR_STRING_LTRIM
        let value3 = (function (str, chars) {
            return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');
        })(value2, 'star-rating ');
// Token: EXPR_RETURN ret_type: STRING
        return value3;
    }

// Token: STRUCT_FIELD
    _parsePrice(value) {
// Token: EXPR_DEFAULT_START
        try {
// Token: EXPR_CSS
            let value2 = value1.querySelector('.price_color');
// Token: EXPR_TEXT
            let value3 = value2.textContent;
// Token: EXPR_REGEX
            let value4 = value3.match(/(\d+)/g)[0];
// Token: EXPR_RETURN ret_type: INT
            return value6;
// Token: EXPR_DEFAULT_END
        } catch (Error) {
            return 0;
        }
    }

// Token: STRUCT_PARSE_START struct_type: LIST
// Call instructions count: 6
    parse() {
        let items = [];
        Array.from(this._splitDoc(this._doc)).forEach((e) => {
            items.push({
                name: this._parseName(e),
                image_url: this._parseImageUrl(e),
                url: this._parseUrl(e),
                rating: this._parseRating(e),
                price: this._parsePrice(e)
            });
        });
        return items;
    }
}

// Token: DOCSTRING
/**
 *
 *
 * {
 *     "title": "String",
 *     "urls": [
 *         "String",
 *         "..."
 *     ],
 *     "books": [
 *         {
 *             "name": "String",
 *             "image_url": "String",
 *             "url": "String",
 *             "rating": "String",
 *             "price": "ANY"
 *         },
 *         "..."
 *     ]
 * }
 */
// Token: STRUCT
class CataloguePage {
// Token: STRUCT_INIT
    constructor(doc) {
        this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : doc;
    }

// Token: STRUCT_PRE_VALIDATE
    _preValidate(value) {
// Token: EXPR_CSS
        let value1 = value.querySelector('title');
// Token: EXPR_TEXT
        let value2 = value1.textContent;
// Token: IS_REGEX_MATCH
        if (value2.match(/Books to Scrape/) === null) throw new Error('');
// Token: EXPR_NO_RETURN
        return null;
    }

// Token: STRUCT_FIELD
    _parseTitle(value) {
// Token: EXPR_DEFAULT_START
        try {
// Token: IS_CSS
            if (!value1.querySelector('title')) throw new Error('');
            let value2 = value1;
// Token: EXPR_CSS
            let value3 = value2.querySelector('title');
// Token: EXPR_TEXT
            let value4 = value3.textContent;
// Token: EXPR_REGEX_SUB
            let value5 = value4.replace(/^\s+/g, '');
// Token: EXPR_REGEX_SUB
            let value6 = value5.replace(/\s+$/g, '');
// Token: EXPR_RETURN ret_type: STRING
            return value7;
// Token: EXPR_DEFAULT_END
        } catch (Error) {
            return 'test';
        }
    }

// Token: STRUCT_FIELD
    _parseUrls(value) {
// Token: EXPR_NESTED
        let value1 = (new Urls(value)).parse();
// Token: EXPR_RETURN ret_type: NESTED
        return value1;
    }

// Token: STRUCT_FIELD
    _parseBooks(value) {
// Token: EXPR_NESTED
        let value1 = (new Books(value)).parse();
// Token: EXPR_RETURN ret_type: NESTED
        return value1;
    }

// Token: STRUCT_PARSE_START struct_type: ITEM
// Call instructions count: 4
    parse() {
        this._preValidate(this._doc);
        let item = {
            title: this._parseTitle(this._doc),
            urls: this._parseUrls(this._doc),
            books: this._parseBooks(this._doc)
        };
        return item;
    }
}

let parser = new CataloguePage(document);
let result = parser.parse();
console.log(result)
