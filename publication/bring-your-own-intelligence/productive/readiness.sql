SELECT p.version, o.case_id,
  CASE
    WHEN p.archive_sha256 IS NULL OR p.source_url IS NULL THEN 'HOLD_MISSING_PUBLISHER_BINDING'
    WHEN o.archive_sha256 IS NULL THEN 'HOLD_MISSING_PACKAGE'
    WHEN o.archive_sha256 != p.archive_sha256 THEN 'HOLD_ARCHIVE_MISMATCH'
    WHEN o.inventory_verified IS NOT 1 THEN 'HOLD_INVENTORY'
    WHEN o.package_version IS NOT p.version OR o.source_url IS NOT p.source_url OR o.source_verified IS NOT 1 THEN 'HOLD_SOURCE'
    ELSE 'VERIFIED_ARCHIVE'
  END AS decision,
  o.archive_sha256, o.source_url, o.inventory_count
FROM publisher AS p CROSS JOIN observed AS o
