_HELPER_BUILDINS = r"""
local htmlparser = require("htmlparser")
local json = require("dkjson")


-- optional module for Buildins.re_any, Buildins.re_all, Buildins.re, Buildins.re_all, Buildins.re_sub
-- if not passed flag - codegen should be try convert to pattern matching synatax for simple cases
local ok, rex = pcall(require, "rex_pcre") if not ok then rex = {} end

-- UTILS collection
local Buildins = {}
function Buildins.map(tbl, fn)
    local res = {}
    for i, v in ipairs(tbl) do res[i] = fn(v) end
    return res
end

function Buildins.filter(tbl, fn)
    local res = {}
    for _, v in ipairs(tbl) do if fn(v) then res[#res + 1] = v end end
    return res
end

function Buildins.escape_pattern(s) return s:gsub("([%%%^%$%(%)%.%[%]%*%+%-%?])", "%%%1") end

function Buildins.trim(s, chars)
    chars = chars and "[" .. chars:gsub("([%%%^%$%(%)%.%[%]%*%+%-%?])", "%%%1") .. "]" or "%s"
    return s:gsub("^" .. chars .. "+", ""):gsub(chars .. "+$", "")
end

function Buildins.ltrim(s, chars)
    chars = chars and "[" .. chars:gsub("([%%%^%$%(%)%.%[%]%*%+%-%?])", "%%%1") .. "]" or "%s"
    return s:gsub("^" .. chars .. "+", "")
end

function Buildins.rtrim(s, chars)
    chars = chars and "[" .. chars:gsub("([%%%^%$%(%)%.%[%]%*%+%-%?])", "%%%1") .. "]" or "%s"
    return s:gsub(chars .. "+$", "")
end

function Buildins.split(s, sep)
    local res = {}
    for part in string.gmatch(s, "([^" .. (sep or "%s") .. "]+)") do res[#res + 1] = part end
    return res
end

function Buildins.at0(arr, index) return index < 0 and arr[#arr + index + 1] or arr[index + 1] end

function Buildins.contains(arr, value)
    for _, v in ipairs(arr) do if v == value then return true end end
    return false
end

function Buildins.to_bool(v) return not (v == nil or v == "" or (type(v) == "table" and #v == 0)) end

function Buildins.remove_prefix(s, prefix)
    return s:sub(1, #prefix) == prefix and s:sub(#prefix + 1) or s
end

function Buildins.remove_suffix(s, suffix)
    return s:sub(- #suffix) == suffix and s:sub(1, - #suffix - 1) or s
end

function Buildins.remove_prefix_suffix(s, substr)
    return Buildins.remove_suffix(Buildins.remove_prefix(s, substr), substr)
end

function Buildins.unique(arr)
    local seen, res = {}, {}
    for _, v in ipairs(arr) do
        if not seen[v] then
            seen[v] = true
            res[#res + 1] = v
        end
    end
    return res
end

function Buildins.re_any(arr, pattern)
    for _, s in ipairs(arr) do if rex.match(s, pattern) then return true end end
    return false
end

function Buildins.re_all(arr, pattern)
    for _, s in ipairs(arr) do if not rex.match(s, pattern) then return false end end
    return true
end

function Buildins.map_replace(str, old, new)
    local result = str
    
    for i = 1, #old do
        local old_str = old[i]
        local new_str = new[i]
        local escaped_old = Buildins.escape_pattern(old_str)    
        result = result:gsub(escaped_old, new_str)
    end
    
    return result
end

function Buildins.unescape(v)
    local result = v
    
    local html_entities = {
        ["&amp;"] = "&",
        ["<"] = "<",
        [">"] = ">",
        ["&quot;"] = '"',
        ["&#039;"] = "'",
        ["&#x2F;"] = "/",
        ["&nbsp;"] = " "
    }
    
    for entity, char in pairs(html_entities) do
        result = result:gsub(entity, char)
    end
    
    result = result:gsub("&#x([0-9a-fA-F]+);", function(hex)
        local num = tonumber(hex, 16)
        return num and string.char(num) or "&#x" .. hex .. ";"
    end)
    
    result = result:gsub("\\u(%x%x%x%x)", function(hex)
        local num = tonumber(hex, 16)
        return num and string.char(num) or "\\u" .. hex
    end)
    
    result = result:gsub("\\x(%x%x)", function(hex)
        local num = tonumber(hex, 16)
        return num and string.char(num) or "\\x" .. hex
    end)
    
    local escapes = {
        b = "\b",
        f = "\f",
        n = "\n",
        r = "\r",
        t = "\t"
    }
    
    result = result:gsub("\\([bfnrt])", function(ch)
        return (escapes[ch] or "\\") .. ch
    end)
    
    return result
end
"""

_HELPER_REGEX = r"""
local PM = {}

function PM.search(s, pat, ...)
    local patterns = { pat, ... }

    for _, pattern in ipairs(patterns) do
        local match = s:match(pattern)
        if match then
            return match
        end
    end

    return nil
end

function PM.findall(s, pat, ...)
    local patterns = { pat, ... }
    local all_matches = {}

    -- find all results
    for pattern_index, pattern in ipairs(patterns) do
        local start_pos = 1
        while true do
            local startPos, endPos, capture = s:find(pattern, start_pos)
            if not startPos then break end

            local match_text = capture or s:sub(startPos, endPos)
            table.insert(all_matches, {
                text = match_text,
                start = startPos,
                finish = endPos,
                pattern_index = pattern_index
            })

            start_pos = endPos + 1
        end
    end

    -- sort by pos or pattern indexes
    table.sort(all_matches, function(a, b)
        if a.start == b.start then
            return a.pattern_index < b.pattern_index
        else
            return a.start < b.start
        end
    end)

    -- remove overlapping matches
    local results = {}
    local last_end = 0

    for _, match in ipairs(all_matches) do
        if match.start > last_end then
            table.insert(results, match.text)
            last_end = match.finish
        end
    end

    return results
end

function PM.sub(s, repl, pat, ...)
    local patterns = { pat, ... }
    local all_matches = {}

    -- search all matches
    for pattern_index, pattern in ipairs(patterns) do
        local start_pos = 1
        while true do
            local startPos, endPos, capture = s:find(pattern, start_pos)
            if not startPos then break end

            local match_text = capture or s:sub(startPos, endPos)
            table.insert(all_matches, {
                text = match_text,
                start = startPos,
                finish = endPos,
                pattern_index = pattern_index
            })

            start_pos = endPos + 1
        end
    end

    -- sort by pos or pattern indexes
    table.sort(all_matches, function(a, b)
        if a.start == b.start then
            return a.pattern_index < b.pattern_index
        else
            return a.start < b.start
        end
    end)

    -- remove overlapping matches
    local non_overlapping = {}
    local last_end = 0

    for _, match in ipairs(all_matches) do
        if match.start > last_end then
            table.insert(non_overlapping, match)
            last_end = match.finish
        end
    end

    -- replace
    local result = s
    for i = #non_overlapping, 1, -1 do
        local match = non_overlapping[i]
        local before = result:sub(1, match.start - 1)
        local after = result:sub(match.finish + 1)
        result = before .. repl .. after
    end

    return result
end

-- strings - массив строк, хотя бы одна совпадает с коллекцией паттернов
function PM.re_any(strings, pat, ...)
    local patterns = {pat, ...}
    
    for _, str in ipairs(strings) do
        for _, pattern in ipairs(patterns) do
            local match = str:match(pattern)
            if match then
                return true
            end
        end
    end
    
    return false
end

function PM.re_all(strings, pat, ...)
    local patterns = {pat, ...}
    
    for _, str in ipairs(strings) do
        local found_match = false
        
        for _, pattern in ipairs(patterns) do
            local match = str:match(pattern)
            if match then
                found_match = true
                break
            end
        end
        
        if not found_match then
            return false
        end
    end
    
    return true
end
"""

_HELPER_SELECTORS = r"""
-- HTML parser utils
--[[
CSS3 query extensions. Coauthor Qwen3-Coder LLM model.
--]]

local CssExt = {}

function CssExt.attr(el, key)
    if key == "class" then
        if not el.classes then
            error("Attribute '" .. key .. "' not found", 2)
        end
        return table.concat(el.classes, " ")
    elseif key == "id" then
        if not el.id then
            error("Attribute '" .. key .. "' not found", 2)
        end
        return el.id
    else
        if not el.attributes[key] then
            error("Attribute '" .. key .. "' not found", 2)
        end
        return el.attributes[key]
    end
end

-- save extract multiple keys from element
function CssExt.get_attr_values(el, keys)
    local values = {}
    for _, key in ipairs(keys) do
        if key == "class" then
            if next(el.classes) ~= nil then
                local val = table.concat(el.classes, " ")
                table.insert(values, val)
            end
        elseif key == "id" then
            local val = el.id
            if el.id ~= nil then
                table.insert(values, val)
            end
        else
            local val = el.attributes[key]
            if val ~= nil then
                table.insert(values, val)
            end
        end
    end
    return values
end

function CssExt.flat_get_attr_values(elements, keys)
    local values = {}
    for _, vals in ipairs(Buildins.map(elements, function(el) return CssExt.get_attr_values(el, keys) end)) do
        for _, v in ipairs(vals) do table.insert(values, v) end
    end
    return values
end

function CssExt.has_attr(el, attr)
    if attr == "class" and next(el.classes) ~= nil then return true end
    if attr == "id" and el.id ~= nil then return true end
    if el.attributes[attr] ~= nil then return true end
    return false
end

function CssExt.all_has_attr(nodelist, attr)
    for _, el in ipairs(nodelist) do
        if CssExt.has_attr(el, attr) == false then
            return false
        end
    end
    return true
end

-- CSS3 selector backport. Used in ssc-gen converter

-- combinator `,` (union selector)
function CssExt.combine_comma(root, left_result, right_selector)
    if type(left_result) == "table" and left_result.index and left_result.name then
        left_result = { left_result }
    end
    local right_elements = root:select(right_selector) or {}

    -- Combine results, avoiding duplicates
    local combined = {}
    local seen = {}

    for _, elem in ipairs(left_result) do
        if not seen[elem] then
            table.insert(combined, elem)
            seen[elem] = true
        end
    end

    for _, elem in ipairs(right_elements) do
        if not seen[elem] then
            table.insert(combined, elem)
            seen[elem] = true
        end
    end

    return combined
end

-- Combinator: child (>) - Direct child elements
function CssExt.combine_child(parent_elements, child_selector)
    if type(parent_elements) == "table" and parent_elements.index and parent_elements.name then
        parent_elements = { parent_elements }
    end
    local result = {}
    local result_map = {}

    for _, parent_element in ipairs(parent_elements) do
        for _, child in ipairs(parent_element.nodes) do
            local temp_root = parent_element.root or parent_element
            local matched = temp_root:select(child_selector)
            for _, matched_element in ipairs(matched) do
                if matched_element == child and not result_map[matched_element.index] then
                    table.insert(result, child)
                    result_map[matched_element.index] = true
                end
            end
        end
    end

    table.sort(result, function(a, b) return a.index < b.index end)
    return result
end

-- Combinator: adjacent sibling (+)
function CssExt.combine_plus(first_elements, second_selector)
    if type(first_elements) == "table" and first_elements.index and first_elements.name then
        first_elements = { first_elements }
    end

    local result = {}
    local result_map = {}

    for _, first_element in ipairs(first_elements) do
        local parent = first_element.parent
        if parent then
            for i = 1, #parent.nodes - 1 do
                if parent.nodes[i] == first_element then
                    local next_sibling = parent.nodes[i + 1]
                    local temp_root = parent.root or parent
                    local matched = temp_root:select(second_selector)

                    for _, matched_element in ipairs(matched) do
                        if matched_element == next_sibling and not result_map[matched_element.index] then
                            table.insert(result, next_sibling)
                            result_map[matched_element.index] = true
                        end
                    end
                    break
                end
            end
        end
    end

    table.sort(result, function(a, b) return a.index < b.index end)
    return result
end

-- Combinator: general sibling (~)
function CssExt.combine_tilde(first_elements, second_selector)
    if type(first_elements) == "table" and first_elements.index and first_elements.name then
        first_elements = { first_elements }
    end
    local result = {}
    local result_map = {}

    for _, first_element in ipairs(first_elements) do
        local parent = first_element.parent
        if parent then
            local first_index = nil
            for i, sibling in ipairs(parent.nodes) do
                if sibling == first_element then
                    first_index = i
                    break
                end
            end
            if first_index then
                for i = first_index + 1, #parent.nodes do
                    local subsequent_sibling = parent.nodes[i]
                    local temp_root = parent.root or parent
                    local matched = temp_root:select(second_selector)
                    for _, matched_element in ipairs(matched) do
                        if matched_element == subsequent_sibling and not result_map[matched_element.index] then
                            table.insert(result, subsequent_sibling)
                            result_map[matched_element.index] = true
                        end
                    end
                end
            end
        end
    end

    table.sort(result, function(a, b) return a.index < b.index end)
    return result
end

-- nth-child implementation
function CssExt.nth_child(elements, n)
    if not elements then return {} end
    
    local result = {}
    local result_map = {}
    
    if type(elements) == "table" and elements.index and elements.name then
        elements = { elements }
    end
    
    for _, element in ipairs(elements) do
        local parent = element.parent
        if parent then
            -- search first pos in siblings
            local position = nil
            for i, sibling in ipairs(parent.nodes) do
                if sibling == element then
                    position = i
                    break
                end
            end
            if position then
                local match = false
                if n == 1 and position == 1 then
                    -- first-child
                    match = true
                elseif n == -1 and position == #parent.nodes then
                    -- last-child
                    match = true
                elseif n > 0 and position == n then
                    -- nth-child(n)
                    match = true
                end
                
                if match and not result_map[element.index] then
                    table.insert(result, element)
                    result_map[element.index] = true
                end
            end
        end
    end
    
    table.sort(result, function(a, b) return a.index < b.index end)
    return result
end

-- :first-child
function CssExt.first_child(elements) return CssExt.nth_child(elements, 1) end
-- :last-child
function CssExt.last_child(elements) return CssExt.nth_child(elements, -1) end

-- remove nodes by query. has a side effect
function CssExt.remove(node, selector)
    local elements = node:select(selector)
    return CssExt.remove_elements(node, elements)
end

-- remove nodes by passed elements. has a side effect
function CssExt.remove_elements(node, elements)
    local to_remove = {}
    for _, element in ipairs(elements) do
        to_remove[element] = true
    end
    for element in pairs(to_remove) do
        local parent = element.parent
        if parent then
            for i = #parent.nodes, 1, -1 do
                if parent.nodes[i] == element then
                    table.remove(parent.nodes, i)
                    break
                end
            end
            local current = parent
            while current do
                current.deepernodes:remove(element)
                if current.deeperelements[element.name] then
                    current.deeperelements[element.name]:remove(element)
                    if not next(current.deeperelements[element.name]) then
                        current.deeperelements[element.name] = nil
                    end
                end
                for attr_name in pairs(element.attributes) do
                    if current.deeperattributes[attr_name] then
                        current.deeperattributes[attr_name]:remove(element)
                        if not next(current.deeperattributes[attr_name]) then
                            current.deeperattributes[attr_name] = nil
                        end
                    end
                end
                if element.id and current.deeperids[element.id] then
                    current.deeperids[element.id]:remove(element)
                    if not next(current.deeperids[element.id]) then
                        current.deeperids[element.id] = nil
                    end
                end
                for _, class_name in ipairs(element.classes) do
                    if current.deeperclasses[class_name] then
                        current.deeperclasses[class_name]:remove(element)
                        if not next(current.deeperclasses[class_name]) then
                            current.deeperclasses[class_name] = nil
                        end
                    end
                end
                current = current.parent
            end
        end
    end
    return node
end

-- merge elements, avoid duplicates (comma-separated implementation)
function CssExt.megre_elements(...)
    local args = { ... }
    local combined = {}
    local seen = {}

    for _, elements in ipairs(args) do
        -- Handle case when elements is a single NodeElement instead of array
        if type(elements) == "table" and elements.index and elements.name then
            if not seen[elements] then
                table.insert(combined, elements)
                seen[elements] = true
            end
        else
            for _, elem in ipairs(elements) do
                if not seen[elem] then
                    table.insert(combined, elem)
                    seen[elem] = true
                end
            end
        end
    end
    return combined
end
"""

_HELPER_FILTER = r"""
-- filters std
local F = {}
F._u = function(s) local t = {} for _, c in utf8.codes(s) do t[#t+1] = c end return t end
F.in_ = function(s, sub) return s:find(sub, 1, true) ~= nil end
F.sw = function(s, prefix) return s:sub(1, #prefix) == prefix end
F.ew = function(s, suffix) return suffix == "" or s:sub(-#suffix) == suffix end
F.re = function(s, pat, flags) return rex.find(s, pat, flags) ~= nil end
-- pattern matching syntax
F.pm = function(s, pat, ...) for _, pattern in ipairs({pat, ...}) do if s:match(pattern) then return true end end return false end
F.eq = function(s, other)
    local a, b = F._u(s), F._u(other)
    if #a ~= #b then return false end
    for i = 1, #a do if a[i] ~= b[i] then return false end end
    return true
end
F.ne = function(s, other) return not F.eq(s, other) end
F.len_eq = function(s, n) return utf8.len(s) == n end
F.len_ne = function(s, n) return utf8.len(s) ~= n end
F.len_gt = function(s, n) return utf8.len(s) > n end
F.len_ge = function(s, n) return utf8.len(s) >= n end
F.len_lt = function(s, n) return utf8.len(s) < n end
F.len_le = function(s, n) return utf8.len(s) <= n end
F.any_in = function(s, arr)
    for _, p in ipairs(arr) do if s:find(p, 1, true) then return true end end
    return false
end
F.any_sw = function(s, arr)
    for _, p in ipairs(arr) do if s:sub(1, #p) == p then return true end end
    return false
end
F.any_ew = function(s, arr)
    for _, p in ipairs(arr) do if p == "" or s:sub(-#p) == p then return true end end
    return false
end
F.any_eq = function(s, arr)
    for _, p in ipairs(arr) do if F.eq(s, p) then return true end end
    return false
end
F.all_ne = function(s, arr)
    for _, p in ipairs(arr) do if F.eq(s, p) then return false end end
    return true
end
"""


HELPER_FUNCTIONS = (
    _HELPER_BUILDINS + _HELPER_REGEX + _HELPER_FILTER + _HELPER_SELECTORS + '-- Main code'
)


def lua_struct_init(parent_name: str) -> str:
    """generate constructor for parent class"""
    return f"""function {parent_name}:new(document)
    if type(document) == "string" then
        self._document = htmlparser.parse(document);
    else
        self._document = document;
    end
    return self
end
"""
