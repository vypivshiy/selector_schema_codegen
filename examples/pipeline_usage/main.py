"""Example repice HOW TO use it in scripts pipelines

USAGE:

    ```bash
    curl "https://example.com" | python main.py
   ```

   tool by projectdiscovery

   ```
   httpx -u "https://example.com" | python main.py
   ``` 
"""

import sys
import pprint
from parser_schema import Main

if __name__ == "__main__":
    for line in sys.stdin:
        line = line.strip()
        pprint.pprint(Main(line).parse())