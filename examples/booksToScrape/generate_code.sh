ssc-gen go schemas/booksToScrape.py -o go --package main
# OPTIONAL chose parser backend lib
ssc-gen py schemas/booksToScrape.py -i parsel -o python
ssc-gen js schemas/booksToScrape.py -o js
ssc-gen dart schemas/booksToScrape.py -o dart
