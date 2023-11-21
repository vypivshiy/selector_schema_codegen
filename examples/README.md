## Install

```shell
pip install ssc_codegen
```

## Usage

```shell
ssc_gen books_schema.yaml python
ssc_gen books_schema.yaml dart
...
```

## Projects examples:

### Python
```python
import httpx
from schema import Book, BookCatalogue


if __name__ == '__main__':
    resp = httpx.get("http://books.toscrape.com/index.html")
    sc = BookCatalogue(resp.text)
    sc.parse()
    data = sc.view()
    print(*data, sep="\n")
    print("---")
    resp2 = httpx.get("http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html")
    sc2 = Book(resp2.text)
    sc2.parse()
    print(*sc2.view(), sep="\n")
```

### Dart

```dart
import 'package:books/books.dart' as books;
import 'package:http/http.dart' as http;
import 'schema.dart';

void main(List<String> arguments) async {
  final response = await http.get(Uri.parse('http://books.toscrape.com/'));
  var sc = BookCatalogue(response.body);
  sc.parse();
  for (var i in sc.view()){
    print(i);
  }

  final resp2 = await http.get(Uri.parse("http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"));
  var sc2 = Book(resp2.body);
  sc2.parse();
  print(sc2.view());
}
```