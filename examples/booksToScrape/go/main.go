// usage generated module example
package main

import (
	"encoding/json"
	"github.com/PuerkitoBio/goquery"
	"log"
	"net/http"
)

func main() {
	_, doc := readDocument()
	cp := CataloguePage{Document: doc}
	data, err := cp.Parse()
	if err != nil {
		log.Fatalf("Error parsing HTML: %v", err)
	}
	out, _ := json.MarshalIndent(data, "", "  ")
	print(string(out))
}

func readDocument() (error, *goquery.Document) {
	url := "https://books.toscrape.com/"

	// Send HTTP GET request
	resp, err := http.Get(url)
	if err != nil {
		log.Fatalf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Fatalf("Received non-OK HTTP status: %s", resp.Status)
	}
	doc, err := goquery.NewDocumentFromReader(resp.Body)

	if err != nil {
		log.Fatalf("Error parsing HTML: %v", err)
	}
	return err, doc
}
