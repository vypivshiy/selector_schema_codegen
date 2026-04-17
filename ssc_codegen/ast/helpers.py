# Regex utilities moved to ssc_codegen.regex_utils
# Import from there if needed:
#   from ssc_codegen.regex_utils import extract_regex_flags, unverbosify_regex

import re

RE_CAPTURED_GROUPS = re.compile(r"(?<!\\()\\((?!\\?:)[^)]+\\)")
