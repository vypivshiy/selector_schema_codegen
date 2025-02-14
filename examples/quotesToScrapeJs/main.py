# html page example from http://quotes.toscrape.com/js/
import pathlib
import pprint

from parser_schema import Main

if __name__ == "__main__":
    body = pathlib.Path("index.html").read_text(encoding="utf-8")
    result = Main(body).parse()
    pprint.pprint(result, compact=True, sort_dicts=False)
# /home/georgiy/PycharmProjects/selector_schema_codegen/.venv/bin/python /home/georgiy/PycharmProjects/selector_schema_codegen/examples/quotesToScrapeJs/main.py
# {'data': [{'tags': ['change', 'deep-thoughts', 'thinking', 'world'],
#            'author': {'name': 'Albert Einstein',
#                       'goodreads_link': '/author/show/9810.Albert_Einstein',
#                       'slug': 'Albert-Einstein'},
#            'text': '“The world as we have created it is a process of our '
#                    'thinking. It cannot be changed without changing our '
#                    'thinking.”'},
#           {'tags': ['abilities', 'choices'],
#            'author': {'name': 'J.K. Rowling',
#                       'goodreads_link': '/author/show/1077326.J_K_Rowling',
#                       'slug': 'J-K-Rowling'},
#            'text': '“It is our choices, Harry, that show what we truly are, '
#                    'far more than our abilities.”'},
#           {'tags': ['inspirational', 'life', 'live', 'miracle', 'miracles'],
#            'author': {'name': 'Albert Einstein',
#                       'goodreads_link': '/author/show/9810.Albert_Einstein',
#                       'slug': 'Albert-Einstein'},
#            'text': '“There are only two ways to live your life. One is as '
#                    'though nothing is a miracle. The other is as though '
#                    'everything is a miracle.”'},
#           {'tags': ['aliteracy', 'books', 'classic', 'humor'],
#            'author': {'name': 'Jane Austen',
#                       'goodreads_link': '/author/show/1265.Jane_Austen',
#                       'slug': 'Jane-Austen'},
#            'text': '“The person, be it gentleman or lady, who has not pleasure '
#                    'in a good novel, must be intolerably stupid.”'},
#           {'tags': ['be-yourself', 'inspirational'],
#            'author': {'name': 'Marilyn Monroe',
#                       'goodreads_link': '/author/show/82952.Marilyn_Monroe',
#                       'slug': 'Marilyn-Monroe'},
#            'text': "“Imperfection is beauty, madness is genius and it's better "
#                    'to be absolutely ridiculous than absolutely boring.”'},
#           {'tags': ['adulthood', 'success', 'value'],
#            'author': {'name': 'Albert Einstein',
#                       'goodreads_link': '/author/show/9810.Albert_Einstein',
#                       'slug': 'Albert-Einstein'},
#            'text': '“Try not to become a man of success. Rather become a man '
#                    'of value.”'},
#           {'tags': ['life', 'love'],
#            'author': {'name': 'André Gide',
#                       'goodreads_link': '/author/show/7617.Andr_Gide',
#                       'slug': 'Andre-Gide'},
#            'text': '“It is better to be hated for what you are than to be '
#                    'loved for what you are not.”'},
#           {'tags': ['edison', 'failure', 'inspirational', 'paraphrased'],
#            'author': {'name': 'Thomas A. Edison',
#                       'goodreads_link': '/author/show/3091287.Thomas_A_Edison',
#                       'slug': 'Thomas-A-Edison'},
#            'text': "“I have not failed. I've just found 10,000 ways that won't "
#                    'work.”'},
#           {'tags': ['misattributed-eleanor-roosevelt'],
#            'author': {'name': 'Eleanor Roosevelt',
#                       'goodreads_link': '/author/show/44566.Eleanor_Roosevelt',
#                       'slug': 'Eleanor-Roosevelt'},
#            'text': '“A woman is like a tea bag; you never know how strong it '
#                    "is until it's in hot water.”"},
#           {'tags': ['humor', 'obvious', 'simile'],
#            'author': {'name': 'Steve Martin',
#                       'goodreads_link': '/author/show/7103.Steve_Martin',
#                       'slug': 'Steve-Martin'},
#            'text': '“A day without sunshine is like, you know, night.”'}]}
