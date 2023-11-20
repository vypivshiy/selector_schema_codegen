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
