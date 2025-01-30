// autogenerated by ssc-gen DO NOT_EDIT
// Dummy parser config for http://books.toscrape.com/

package main

import (
	"fmt"
	"github.com/PuerkitoBio/goquery"
	"regexp"
	"strconv"
	"strings"
)

type TUrls = []string
type TUrlsMap = map[string]string
type TBooks struct {
	Name     string `json:"name"`
	ImageUrl string `json:"image_url"`
	Url      string `json:"url"`
	Rating   string `json:"rating"`
	Price    int    `json:"price"`
}
type TBooksITEMS = []TBooks
type TCataloguePage struct {
	Title   string      `json:"title"`
	Urls    TUrls       `json:"urls"`
	UrlsMap TUrlsMap    `json:"urls_map"`
	Books   TBooksITEMS `json:"books"`
}

// Urls fetch add patches and urls from <a> tag
//
// [
//     "String",
//     "..."
// ]
type Urls struct{ Document *goquery.Document }

func (p *Urls) splitDoc(value *goquery.Selection) *goquery.Selection {
	value1 := value.Find("a")
	return value1
}
func (p *Urls) parseItem(value *goquery.Selection) string {
	value1, isExists := value.Attr("href")
	if !isExists {
		panic(fmt.Errorf("attr `%s` not exists in `%s`", "href", value))
	}
	return value1
}
func (p *Urls) Parse() (*TUrls, error) {
	items := make(TUrls, 0)
	for _, i := range p.splitDoc(p.Document.Selection).EachIter() {
		rawItem := p.parseItem(i)
		items = append(items, rawItem)
	}
	return &items, nil
}

// UrlsMap
//
// {
//     "<K>": "String",
//     "<KN>": "..."
// }
type UrlsMap struct{ Document *goquery.Document }

func (p *UrlsMap) splitDoc(value *goquery.Selection) *goquery.Selection {
	value1 := value.Find("a")
	return value1
}
func (p *UrlsMap) parseKey(value *goquery.Selection) string {
	value1 := value.Text()
	value2 := strings.Trim(" ", value1)
	return value2
}
func (p *UrlsMap) parseValue(value *goquery.Selection) string {
	value1, isExists := value.Attr("href")
	if !isExists {
		panic(fmt.Errorf("attr `%s` not exists in `%s`", "href", value))
	}
	return value1
}
func (p *UrlsMap) Parse() (*TUrlsMap, error) {
	items := make(TUrlsMap)
	for _, i := range p.splitDoc(p.Document.Selection).EachIter() {
		keyRaw := p.parseKey(i)
		valueRaw := p.parseValue(i)
		items[keyRaw] = valueRaw
	}
	return &items, nil
}

// Books
//
// [
//     {
//         "name": "String",
//         "image_url": "String",
//         "url": "String",
//         "rating": "String",
//         "price": "Int"
//     },
//     "..."
// ]
type Books struct{ Document *goquery.Document }

func (p *Books) splitDoc(value *goquery.Selection) *goquery.Selection {
	value1 := value.Find(".col-lg-3")
	return value1
}
func (p *Books) parseName(value *goquery.Selection) string {
	value1 := value.Find(".thumbnail").First()
	value2, isExists := value1.Attr("alt")
	if !isExists {
		panic(fmt.Errorf("attr `%s` not exists in `%s`", "alt", value1))
	}
	return value2
}
func (p *Books) parseImageUrl(value *goquery.Selection) string {
	value1 := value.Find(".thumbnail").First()
	value2, isExists := value1.Attr("src")
	if !isExists {
		panic(fmt.Errorf("attr `%s` not exists in `%s`", "src", value1))
	}
	value3 := fmt.Sprintf("https://%s", value2)
	return value3
}
func (p *Books) parseUrl(value *goquery.Selection) string {
	value1 := value.Find(".image_container > a").First()
	value2, isExists := value1.Attr("href")
	if !isExists {
		panic(fmt.Errorf("attr `%s` not exists in `%s`", "href", value1))
	}
	return value2
}
func (p *Books) parseRating(value *goquery.Selection) string {
	value1 := value.Find(".star-rating").First()
	value2, isExists := value1.Attr("class")
	if !isExists {
		panic(fmt.Errorf("attr `%s` not exists in `%s`", "class", value1))
	}
	value3 := strings.TrimLeft(value2, "star-rating ")
	return value3
}
func (p *Books) parsePrice(value *goquery.Selection) (result int, err error) {
	defer func() {
		if r := recover(); r != nil {
			result = 0
		}
	}()
	value1 := value
	value2 := value1.Find(".price_color").First()
	value3 := value2.Text()
	value4 := regexp.MustCompile(`(\d+)`).FindStringSubmatch(value3)[0]
	value5, err := strconv.Atoi(value4)
	if err != nil {
		panic(err)
	}
	result = value5
	return result, nil
}
func (p *Books) Parse() (*TBooksITEMS, error) {
	items := make(TBooksITEMS, 0)
	for _, i := range p.splitDoc(p.Document.Selection).EachIter() {
		NameRaw := p.parseName(i)
		ImageUrlRaw := p.parseImageUrl(i)
		UrlRaw := p.parseUrl(i)
		RatingRaw := p.parseRating(i)
		PriceRaw, _ := p.parsePrice(i)
		item := TBooks{NameRaw, ImageUrlRaw, UrlRaw, RatingRaw, PriceRaw}
		items = append(items, item)
	}
	return &items, nil
}

// CataloguePage
//
// {
//     "title": "String",
//     "urls": [
//         "String",
//         "..."
//     ],
//     "urls_map": {
//         "<K>": "String",
//         "<KN>": "..."
//     },
//     "books": [
//         {
//             "name": "String",
//             "image_url": "String",
//             "url": "String",
//             "rating": "String",
//             "price": "Any"
//         },
//         "..."
//     ]
// }
type CataloguePage struct{ Document *goquery.Document }

func (p *CataloguePage) preValidate(value *goquery.Selection) error {
	value1 := value.Find("title").First()
	value2 := value1.Text()
	_, errValue2 := regexp.Match(`Books to Scrape`, []byte(value2))
	if errValue2 != nil {
		panic(fmt.Errorf(""))
	}
	return nil
}
func (p *CataloguePage) parseTitle(value *goquery.Selection) (result string, err error) {
	defer func() {
		if r := recover(); r != nil {
			result = "test"
		}
	}()
	value1 := value
	if value1.Find("title").Length() == 0 {
		panic(fmt.Errorf(""))
	}
	value2 := value1
	value3 := value2.Find("title").First()
	value4 := value3.Text()
	value5 := string(regexp.MustCompile(`^\s+`).ReplaceAll([]byte(value4), []byte("")))
	value6 := string(regexp.MustCompile(`\s+$`).ReplaceAll([]byte(value5), []byte("")))
	result = value6
	return result, nil
}
func (p *CataloguePage) parseUrls(value *goquery.Selection) (TUrls, error) {
	doc0 := goquery.NewDocumentFromNode(value.Nodes[0])
	st0 := Urls{doc0}
	value1, err := st0.Parse()
	if err != nil {
		panic(err)
	}
	return *value1, nil
}
func (p *CataloguePage) parseUrlsMap(value *goquery.Selection) (TUrlsMap, error) {
	doc0 := goquery.NewDocumentFromNode(value.Nodes[0])
	st0 := UrlsMap{doc0}
	value1, err := st0.Parse()
	if err != nil {
		panic(err)
	}
	return *value1, nil
}
func (p *CataloguePage) parseBooks(value *goquery.Selection) (TBooksITEMS, error) {
	doc0 := goquery.NewDocumentFromNode(value.Nodes[0])
	st0 := Books{doc0}
	value1, err := st0.Parse()
	if err != nil {
		panic(err)
	}
	return *value1, nil
}
func (p *CataloguePage) Parse() (*TCataloguePage, error) {
	err := p.preValidate(p.Document.Selection)
	if err != nil {
		panic(err)
	}
	TitleRaw, err := p.parseTitle(p.Document.Selection)
	if err != nil {
		return nil, err
	}
	UrlsRaw, err := p.parseUrls(p.Document.Selection)
	if err != nil {
		return nil, err
	}
	UrlsMapRaw, err := p.parseUrlsMap(p.Document.Selection)
	if err != nil {
		return nil, err
	}
	BooksRaw, err := p.parseBooks(p.Document.Selection)
	if err != nil {
		return nil, err
	}
	item := TCataloguePage{TitleRaw, UrlsRaw, UrlsMapRaw, BooksRaw}
	return &item, nil
}
