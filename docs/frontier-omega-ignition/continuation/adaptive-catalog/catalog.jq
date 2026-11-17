# Run on one complete catalog batch. The outer catch ensures atomic refusal.
def publication:
  ["catalog_language", "edition_language", "folder_language", "title"] as $required
  | if type != "object" then error("missing_field")
    elif ($required - keys | length) > 0 then error("missing_field")
    elif (keys - $required | length) > 0 then error("extra_field")
    elif (.title | type) != "string" or (.edition_language | type) != "string" then error("invalid_value")
    else {publication: .title, reading_language: .edition_language}
    end;

try (
  if (@json | utf8bytelength) > 2097152 then error("budget")
  elif type != "object" or keys != ["rows"] or (.rows | type) != "array" or (.rows | length) > 2048 then error("invalid_input")
  else {rows: [.rows[] | publication]}
       | if (@json | utf8bytelength) > 2097152 then error("budget") else {output: .} end
  end
) catch {error: .}
