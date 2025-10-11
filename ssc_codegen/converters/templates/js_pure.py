# used functions instead consts arrow functions for allow rewrite it wout errors
HELPER_FUNCTIONS = r"""
function sscUnescape(v) {
  return v
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&#x2F;/g, '/')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#x([0-9a-fA-F]+);/g, function(_, hex) {
      return String.fromCharCode(parseInt(hex, 16));
    })
    .replace(/\\u([0-9a-fA-F]{4})/g, function(_, hex) {
      return String.fromCharCode(parseInt(hex, 16));
    })
    .replace(/\\x([0-9a-fA-F]{2})/g, function(_, hex) {
      return String.fromCharCode(parseInt(hex, 16));
    })
    .replace(/\\([bfnrt])/g, function(_, ch) {
      return { b: '\b', f: '\f', n: '\n', r: '\r', t: '\t' }[ch];
    });
}

function sscRmPrefix(v, p) {
  return v.startsWith(p) ? v.slice(p.length) : v;
}

function sscRmSuffix(v, s) {
  return v.endsWith(s) ? v.slice(0, -s.length) : v;
}

function sscRmPrefixSuffix(v, p, s) {
  return sscRmSuffix(sscRmPrefix(v, p), s);
}
 
"""
