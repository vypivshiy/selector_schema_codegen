import 'package:http/http.dart' as http;
import 'ex.dart';

void main() async {
  String url = "https://books.toscrape.com/";

  try {
    http.Response response = await http.get(Uri.parse(url));
    if (response.statusCode == 200) {
      String responseBody = response.body;
      var data = CataloguePage(responseBody).parse();
      print(data);
    } else {
      print("Failed to load data. Status code: ${response.statusCode}");
    }
  } catch (e) {
    print("An error occurred: $e");
  }
}