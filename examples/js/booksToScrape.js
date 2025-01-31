// autogenerated by ssc-gen DO NOT_EDIT
/**
* Dummy parser config for http://books.toscrape.com/
*/
/**
* fetch add patches and urls from <a> tag
* 
* [
*     "String",
*     "..."
* ]
*/
class Urls{
constructor(doc){this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : doc;}
_splitDoc(value){
let value1 = value.querySelectorAll('a');
return value1;
}
_parseItem(value){
let value1 = value.getAttribute('href');
return value1;
}
parse(){
let items = Array.from(this._splitDoc(this._doc)).map((e) => this._parseItem(e));return items;}
}
/**
* 
* 
* {
*     "<K>": "String",
*     "<KN>": "..."
* }
*/
class UrlsMap{
constructor(doc){this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : doc;}
_splitDoc(value){
let value1 = value.querySelectorAll('a');
return value1;
}
_parseKey(value){
let value1 = value.getAttribute('href');
return value1;
}
_parseValue(value){
let value1 = value.querySelector("html").innerHTML;
let value2 = (function (str, chars){return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');})(value1, ' ');
return value2;
}
parse(){
let item = {};Array.from(this._splitDoc(this._doc)).forEach((e) =>{let k = this._parseKey(e);item[k] = this._parseValue(e);});return item;}
}
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
class Books{
constructor(doc){this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : doc;}
_splitDoc(value){
let value1 = value.querySelectorAll('.col-lg-3');
return value1;
}
_parseName(value){
let value1 = value.querySelector('.thumbnail');
let value2 = value1.getAttribute('alt');
return value2;
}
_parseImageUrl(value){
let value1 = value.querySelector('.thumbnail');
let value2 = value1.getAttribute('src');
let value3 = `https://${value2}`;
return value3;
}
_parseUrl(value){
let value1 = value.querySelector('.image_container > a');
let value2 = value1.getAttribute('href');
return value2;
}
_parseRating(value){
let value1 = value.querySelector('.star-rating');
let value2 = value1.getAttribute('class');
let value3 = (function (str, chars){return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');})(value2, 'star-rating ');
return value3;
}
_parsePrice(value){
try {
let value2 = value1.querySelector('.price_color');
let value3 = value2.textContent;
let value4 = value3.match(/(\d+)/g)[0];
return value6;
} catch(Error) {return 0;}
}
parse(){
let items = [];Array.from(this._splitDoc(this._doc)).forEach((e) =>{items.push({name: this._parseName(e),image_url: this._parseImageUrl(e),url: this._parseUrl(e),rating: this._parseRating(e),price: this._parsePrice(e)});});return items;}
}
/**
* books.toscrape.com catalogue page entrypoint parser
* 
*     USAGE:
* 
*         1. GET <catalog page> (https://books.toscrape.com/, https://books.toscrape.com/catalogue/page-2.html, ...)
*         2. add another prepare instruction how to correct cook page (if needed?)
* 
*     ISSUES:
* 
*         1. nope! Their love being scraped!
*     
* 
* {
*     "title": "String",
*     "urls": [
*         "String",
*         "..."
*     ],
*     "urls_map": {
*         "<K>": "String",
*         "<KN>": "..."
*     },
*     "books": [
*         {
*             "name": "String",
*             "image_url": "String",
*             "url": "String",
*             "rating": "String",
*             "price": "Any"
*         },
*         "..."
*     ]
* }
*/
class CataloguePage{
constructor(doc){this._doc = typeof document === 'string' ? new DOMParser().parseFromString(doc, 'text/html') : doc;}
_preValidate(value){
let value1 = value.querySelector('title');
let value2 = value1.textContent;
if (value2.match(/Books to Scrape/) === null) throw new Error('');
return null;
}
_parseTitle(value){
try {
if (!value1.querySelector('title')) throw new Error('');let value2 = value1;
let value3 = value2.querySelector('title');
let value4 = value3.textContent;
let value5 = value4.replace(/^\s+/g, '');
let value6 = value5.replace(/\s+$/g, '');
return value7;
} catch(Error) {return 'test';}
}
_parseUrls(value){
let value1 = (new Urls(value)).parse();
return value1;
}
_parseUrlsMap(value){
let value1 = (new UrlsMap(value)).parse();
return value1;
}
_parseBooks(value){
let value1 = (new Books(value)).parse();
return value1;
}
parse(){
this._preValidate(this._doc);let item = {title: this._parseTitle(this._doc),urls: this._parseUrls(this._doc),urls_map: this._parseUrlsMap(this._doc),books: this._parseBooks(this._doc)};return item;}
}