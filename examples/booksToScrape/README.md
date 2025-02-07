# ssc-gen Example

This directory provide auto generated parsers and usage example:

Generate code command examples:

## python

```shell
ssc-gen py schemas/booksToScrape.py -i parsel -o python
```

## js

```shell
ssc-gen js schemas/booksToScrape.py -o js
```

## dart

```shell
ssc-gen dart schemas/booksToScrape.py -o dart
```

## go

```shell
ssc-gen go schemas/booksToScrape.py -o go
```

At the default, package name get from output folder. You can override it:

```shell
ssc-gen go schemas/booksToScrape.py -o go --package main
```

## manual python API usage

see `manual_make.py` example
