"""
Example organize config

usage example:

- `ssc-gen js ssc_imports_struct/main.py -o .`

Limitation:

- to ensure that all classes are extracted during generation - import the file or import the classes explicitly
- schemas from module namespace name overwrite certain schemas (namespace file name will be ignored)

EG error generate (not found `header.Link` schema)


```py
from ssc_codegen import ItemSchema, N

# cli cannot found nested class `Link` vvv
from ssc_imports_struct.header import Head 
from ssc_imports_struct.body import Contacts
```

class Page(ItemSchema):
    head = N().sub_parser(Head)
    contacts = N().sub_parser(Contacts)

"""
from ssc_codegen import ItemSchema, N
from ssc_imports_struct import header
from ssc_imports_struct import body



class Page(ItemSchema):
    head = N().sub_parser(header.Head)
    contacts = N().sub_parser(body.Contacts)