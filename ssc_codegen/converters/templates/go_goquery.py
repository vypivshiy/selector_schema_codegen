IMPORTS = """package $PACKAGE$

import (
    "fmt"
    "regexp"
    "strings"
    "slices"
    "strconv"
    "json"
    "github.com/tidwall/gjson"
    "github.com/PuerkitoBio/goquery"
)

"""
"""Default imports $PACKAGE$ varibale should be replaced to `main` or package folder"""


# poor golang syntax we are forced to make a collection of auxiliary functions
HELPER_FUNCTIONS = r"""
var (
    sscHexEntityRe  = regexp.MustCompile(`&#x([0-9a-fA-F]+);`)
    sscUnicodeEscRe = regexp.MustCompile(`\\u([0-9a-fA-F]{4})`)
    sscByteEscRe    = regexp.MustCompile(`\\x([0-9a-fA-F]{2})`)
    sscCharEscRe    = regexp.MustCompile(`\\([bfnrt])`)
    sscCharEscMap   = map[byte]string{'b': "\b", 'f': "\f", 'n': "\n", 'r': "\r", 't': "\t"}
    sscHtmlUnescMap = map[string]string{"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"", "&#039;": "'", "&#x2F;": "/", "&nbsp;": " "}
)

func mapStr(vs []string, f func(string) string) []string {
    r := make([]string, len(vs))
    for i, s := range vs {
        r[i] = f(s)
    }
    return r
}

func sscSliceStrFmt(v []string, t string) []string {
    return mapStr(v, func(s string) string { return fmt.Sprintf(t, s) })
}
func sscSliceStrTrim(v []string, c string) []string {
    return mapStr(v, func(s string) string { return strings.Trim(s, c) })
}
func sscSliceStrLTrim(v []string, c string) []string {
    return mapStr(v, func(s string) string { return strings.TrimLeft(s, c) })
}
func sscSliceStrRTrim(v []string, c string) []string {
    return mapStr(v, func(s string) string { return strings.TrimRight(s, c) })
}
func sscSliceStrRmPrefix(v []string, p string) []string {
    return mapStr(v, func(s string) string { return strings.TrimPrefix(s, p) })
}
func sscSliceStrRmSuffix(v []string, s string) []string {
    return mapStr(v, func(str string) string { return strings.TrimSuffix(str, s) })
}
func sscSliceStrReplace(v []string, o, n string) []string {
    return mapStr(v, func(s string) string { return strings.ReplaceAll(s, o, n) })
}

func sscSliceStrRmPrefixSuffix(v []string, p, s string) []string {
    return mapStr(v, func(str string) string { return strings.TrimSuffix(strings.TrimPrefix(str, p), s) })
}

func sscSliceStrReSub(v []string, re *regexp.Regexp, repl string) []string {
    return mapStr(v, func(s string) string { return re.ReplaceAllString(s, repl) })
}

func sscRegexMatch(v string, re *regexp.Regexp, g int) (string, error) {
    m := re.FindStringSubmatch(v)
    if m == nil {
        return "", fmt.Errorf("not found match %v", re)
    }
    return m[g], nil
}

func sscRegexFindAll(v string, re *regexp.Regexp) ([]string, error) {
    m := re.FindAllString(v, -1)
    if m == nil {
        return nil, fmt.Errorf("not found match %v", re)
    }
    return m, nil
}

func sscSliceStrToSliceInt(v []string) ([]int, error) {
    r := make([]int, 0, len(v))
    for _, s := range v {
        if i, err := strconv.Atoi(s); err != nil {
            return nil, err
        } else {
            r = append(r, i)
        }
    }
    return r, nil
}

func sscSliceStrToSliceFloat(v []string) ([]float64, error) {
    r := make([]float64, 0, len(v))
    for _, s := range v {
        if f, err := strconv.ParseFloat(s, 64); err != nil {
            return nil, err
        } else {
            r = append(r, f)
        }
    }
    return r, nil
}

func sscStrToInt(v string) (int, error)       { return strconv.Atoi(v) }
func sscStrToFloat(v string) (float64, error) { return strconv.ParseFloat(v, 64) }

func sscGetAttr(a *goquery.Selection, key string) (string, error) {
    if attr, ok := a.Attr(key); ok {
        return attr, nil
    }
    return "", fmt.Errorf("attr `%s` not exists", key)
}

func sscEachGetAttrs(a *goquery.Selection, key string) ([]string, error) {
    var r []string
    var err error
    a.Each(func(_ int, s *goquery.Selection) {
        if attr, ok := s.Attr(key); ok {
            r = append(r, attr)
        } else if err == nil {
            err = fmt.Errorf("attr `%s` not exists", key)
        }
    })
    return r, err
}

func sscGetManyAttrs(a *goquery.Selection, keys []string) []string {
    keys = []string{"a", "b", "c"}
    var r []string
    for _, k := range keys {
        if attr, ok := a.Attr(k); ok {
            r = append(r, attr)
        }
    }
    return r
}

func sscEachGetManyAttrs(a *goquery.Selection, keys []string) []string {
    var r []string
    a.Each(func(_ int, s *goquery.Selection) {
        for _, k := range keys {
            if attr, ok := s.Attr(k); ok {
                r = append(r, attr)
            }
        }
    })
    return r
}

func sscEachGetText(a *goquery.Selection) []string {
    var r []string
    a.Each(func(_ int, s *goquery.Selection) {
        r = append(r, s.Text())
    })
    return r
}

func sscUnescape(s string) string {
    s = strings.NewReplacer(
        "&amp;", "&", "&lt;", "<", "&gt;", ">", "&quot;", "\"",
        "&#039;", "'", "&#x2F;", "/", "&nbsp;", " ",
    ).Replace(s)

    s = sscHexEntityRe.ReplaceAllStringFunc(s, func(m string) string {
        if i, err := strconv.ParseInt(sscHexEntityRe.FindStringSubmatch(m)[1], 16, 64); err == nil {
            return string(rune(i))
        }
        return m
    })

    s = sscUnicodeEscRe.ReplaceAllStringFunc(s, func(m string) string {
        if i, err := strconv.ParseUint(sscUnicodeEscRe.FindStringSubmatch(m)[1], 16, 16); err == nil {
            return string(rune(i))
        }
        return m
    })

    s = sscByteEscRe.ReplaceAllStringFunc(s, func(m string) string {
        if i, err := strconv.ParseUint(sscByteEscRe.FindStringSubmatch(m)[1], 16, 8); err == nil {
            return string(byte(i))
        }
        return m
    })

    return sscCharEscRe.ReplaceAllStringFunc(s, func(m string) string {
        if repl, ok := sscCharEscMap[m[1]]; ok {
            return repl
        }
        return m
    })
}

func sscHtmlRawAll(a *goquery.Selection) ([]string, error) {
    var r []string
    var e error
    a.Each(func(_ int, s *goquery.Selection) {
        v, err := s.Html()
        if err != nil {
            e = err
            return
        }
        r = append(r, v)
    })
    if e != nil {
        return nil, e
    }
    return r, nil
}

func sscSliceUnescape(s []string) []string { return mapStr(s, sscUnescape) }

func sscAssertEqual[T comparable](v1, v2 T, msg string) error {
    if v1 != v2 {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertNotEqual[T comparable](v1, v2 T, msg string) error {
    if v1 == v2 {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertContains[S ~[]E, E comparable](v1 S, v2 E, msg string) error {
    if !(slices.Contains(v1, v2, msg)) {
        return fmt.Errorf("%s", msg)
    }
    return nil
}

func sscAssertNotContains[S ~[]E, E comparable](v1 S, v2 E, msg string) error {
    err := sscAssertContains(v1, v2, msg)
    if err == nil {
        return fmt.Errorf("%s", msg)
    }
    return nil
}

func sscAssertRegex(v string, re *regexp.Regexp, msg string) error {
    if !re.MatchString(v) {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscNotAssertRegex(v string, re *regexp.Regexp, msg string) error {
    err := sscAssertRegex(v, re, msg)
    if err == nil {
        return fmt.Errorf(msg)
    } 
    return nil
}

func sscAssertSliceAnyRegex(v []string, re *regexp.Regexp, msg string) error {
    for _, s := range v {
        if re.MatchString(s) {
            return nil
        }
    }
    return fmt.Errorf(msg)
}

func sscAssertSliceAllRegex(v []string, re *regexp.Regexp, msg string) error {
    for _, s := range v {
        if !re.MatchString(s) {
            return fmt.Errorf(msg)
        }
    }
    return nil
}

func sscAssertCss(v *goquery.Selection, query, msg string) error {
    found := false
    v.Find(query).EachWithBreak(func(_ int, _ *goquery.Selection) bool {
        found = true
        return false
    })
    if !found {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertNotCss(v *goquery.Selection, query, msg string) error {
    err := sscAssertCss(v, query, msg)
    if err == nil {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertHasAttr(v *goquery.Selection, key, msg string) error {
    if _, ok := v.Attr(key); !ok {
        return fmt.Errorf(msg)
    }
    return nil
}

func sscAssertNotHasAttr(v *goquery.Selection, key, msg string) error {
    err := sscAssertHasAttr(v, key, msg)
    if err == nil {
        return return fmt.Errorf(msg) 
    }
    return nil
}


func sscSliceStrUnique(v []string) []string {
    seen := make(map[string]bool, len(v))
    var r []string
    for _, s := range v {
        if !seen[s] {
            seen[s] = true
            r = append(r, s)
        }
    }
    return r
}

func sscStringReplaceWithMap(v string, p []string) string {
    return strings.NewReplacer(p...).Replace(v)
}

func sscSliceStringReplaceWithMap(v []string, p []string) []string {
    return mapStr(v, func(s string) string { return sscStringReplaceWithMap(s, p) })
}

func sscSliceStringFilter(v []string, f func(string) bool) []string {
    var r []string
    for _, s := range v {

        if f(s) {
            r = append(r, s)
        }
    }
    return r
}

func sscAnyStr(t []string, f func(string) bool) bool {
    for _, i := range t {
        if f(i) {
            return true
        }
    }
    return false
}

func sscAnyContainsSubstring(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return strings.Contains(t, s) })
}

func sscAnyStarts(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return strings.HasPrefix(t, s) })
}

func sscAnyEnds(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return strings.HasSuffix(t, s) })
}

func sscAnyEqual(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return t == s })
}

func sscAnyNotEqual(t string, s []string) bool {
    return sscAnyStr(s, func(s string) bool { return t != s })
}

func sscMapAttrs(a *goquery.Selection) []string {
    var r []string
    a.Each(func(_ int, s *goquery.Selection) {
        // parent node extract only
        for _, attr := range s.Nodes[0].Attr {
            r = append(r, attr.Val)
        }
    })
    return r
}

func sscDocFhasAnyAttribute(sel *goquery.Selection, attrs []string) bool {
	for _, attr := range attrs {
		if sel.AttrOr(attr, "") != "" {
			return true
		}
	}
	return false
}

func sscDocFAttrEq(sel *goquery.Selection, key string, value string) bool {
	v, _ := sel.Attr(key)
	return v == value
}

func sscDocFAnyAttrEq(sel *goquery.Selection, key string, values []string) bool {
	for _, v := range values {
		if sscDocFAttrEq(sel, key, v) {
			return true
		}
	}
	return false
}

func sscDocFAttrContains(sel *goquery.Selection, key string, value string) bool {
	v, _ := sel.Attr(key)
	return strings.Contains(v, value)
}

func sscDocFAnyAttrContains(sel *goquery.Selection, key string, values []string) bool {
	for _, v := range values {
		if sscDocFAttrContains(sel, key, v) {
			return true
		}
	}
	return false
}

func sscDocFAttrStarts(sel *goquery.Selection, key string, value string) bool {
	v, _ := sel.Attr(key)
	return strings.HasPrefix(v, value)
}

func sscDocFAttrAnyStarts(sel *goquery.Selection, key string, values []string) bool {
	for _, v := range values {
		if sscDocFAttrStarts(sel, key, v) {
			return true
		}
	}
	return false
}

func sscDocFAttrEnds(sel *goquery.Selection, key string, value string) bool {
	v, _ := sel.Attr(key)
	return strings.HasSuffix(v, value)
}

func sscDocFAttrAnyEnds(sel *goquery.Selection, key string, values []string) bool {
	for _, v := range values {
		if sscDocFAttrEnds(sel, key, v) {
			return true
		}
	}
	return false
}

func sscDocFAttrIsRegex(sel *goquery.Selection, key string, pattern string) bool {
	v, _ := sel.Attr(key)
	return regexp.MustCompile(pattern).MatchString(v)
}

func sscDocFAnyTextContains(sel *goquery.Selection, values []string) bool {
    t := sel.Text()
	for _, v := range values {
		if strings.Contains(t, v) {
			return true
		}
	}
	return false
}

func sscDocFAnyRawContains(sel *goquery.Selection, values []string) bool {
    t := sel.Html()
	for _, v := range values {
		if strings.Contains(t, v) {
			return true
		}
	}
	return false
}
"""
