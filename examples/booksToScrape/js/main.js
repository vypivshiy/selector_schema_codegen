/// USAGE EXAMPLE
import CataloguePage from './booksToScrape';

// invoke from console or get response from http request
let parser = new CataloguePage(document);
let result = parser.parse();
console.log(result)
