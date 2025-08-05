"""Example filters usage. Works only with LIST_STRING types

Supported logic operators

| Operator   | Value                           |
|------------|---------------------------------|
|    &       |  AND                            |
|    |       |  OR                             |
|    ~       |  NOT                            |
|   ==       |  equal (substr, len string)     |
|   !=       |  not equal (substr, len string) |
|   >        |  bigger (len string)            |
|   <        |  less (len string)              |
|   >=       |  greather or equal (len string) |
|   <=       |  less or equal (len string)     |
|   re()     | value matched by regex          |
|  starts()  | value starts by substr          |
|  ends()    | value ends by substr            |
| contains() | value contains by substr        |

"""

from ssc_codegen import ItemSchema, D, F

# filters declaration
# TIP:
#  you can define filters as constants
#  optional coverage constants by docstring (IDE support show this information)
#
# understand filter equals expressions
F_IMAGE_PNG = F().ends(".png")
"""
str.endswith(".png")
"""

F_IMAGE_EXT = F().ends(".png", ".jpg")
"""
str.endswith(".png") OR str.endswith(".jpg")
"""

F_CONTACTS = F().starts("tel:", "email:")
"""
str.startswith("tel:") OR str.startswith("email:")
"""
F_TEL_CONTACT = F().starts("tel:")
"""
str.startswith("tel:")
"""

F_FISH_TEXT = F().contains("lorem", "upsum", "dolor")
"""
"lorem" IN str OR "upsum" IN str OR "dolor" IN str
"""

# REGEX check
# \D matches any character that's not a digit (equivalent to [^0-9])
F_NOT_DIGIT = F().re(r"\D")
"""
regex.test(r"\D", str) 
# "1000" -> False
# "test123" -> True
"""

# overrides
F_NE_LOREM = F() != "lorem"
"""
str != "lorem"
"""

F_NE_FISH_TEXT = F() != ("lorem", "upsum", "dolor")
"""
str != "lorem" OR str != "upsum" OR str != "dolor"
"""

F_NE_LEN_STR_10 = F() != 10
"""
len(str) != 10
"""

# overrides
F_EQ_LOREM = F() == "lorem"
"""
str == "lorem"
"""

F_EQ_FISH_TEXT = F() == ("lorem", "upsum", "dolor")
"""
str == "lorem" OR str == "upsum" OR str == "dolor"
"""

F_EQ_LEN_STR_10 = F() == 10
"""
len(str) == 10
"""

# len str checks
F_BIGGER_10 = F() > 10
"""
len(str) > 10
"""
F_LESS_10 = F() < 10
"""
len(str) < 10
"""

F_BIGGER_OR_EQ_10 = F() >= 10
"""
len(str) >= 10
"""

F_LESS_OR_EQ_10 = F() <= 10
"""
len(str) <= 10
"""

# combine filters
# equal len(str) > 10 AND len(str) < 32 AND NOT (str != "lorem" OR str != "upsum" OR str != "dolor")
F_TARGET = (F() > 10) & (F() < 32) & ~F_FISH_TEXT
"""
len(str) > 10 
AND len(str) < 32 
AND NOT (str != "lorem" OR str != "upsum" OR str != "dolor")
"""


class Main(ItemSchema):
    images = (
        D([])
        .css_all("img[src]::attr(src)")
        .filter(F().ends(".png", ".jpg", ".gif") & ~F().ends(".webp"))
        # drop duplicates operator 
        # (order not be saved)
        .unique()
    )
    ajax_scripts = (
        D([]).css_all("script::text")
        .filter(
            # drop too short/long scripts
            # NOTE: required wrap to brackets this shortcuts
            (F() > 10) & (F() < 1024)
            # drop google metrics-like scripts example (naive)
            & ~F().contains("gtag(")  
            # other ajax call patterns
            & F().contains("xhr.open", "axios")  
        )
    )
