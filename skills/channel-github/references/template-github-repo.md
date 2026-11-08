---
type: repo
title: "{{url|split:\"?\"|first|split:\"/\"|slice:3,4|join}}--{{url|split:\"?\"|first|split:\"/\"|slice:4,5|join}}"
resource: "https://github.com/{{url|split:\"?\"|first|split:\"/\"|slice:3,5|join:\"/\"}}"
description: "{{meta:property:og:description}}"
author: "{{url|split:\"?\"|first|split:\"/\"|slice:3,4|join}}"
source_host: github.com
status: draft
tags: [github, gh-clipped]
gh_stars: "{{selector:#repo-stars-counter-star?title}}"
gh_topics: "{{selector:a.topic-tag|join:\", \"}}"
gh_seen: "{{date|date:'YYYY-MM-DD'}}"
gh_first_seen: "{{date|date:'YYYY-MM-DD'}}"
---

> [!summary]
> {{meta:property:og:description}}

- How it got here: clipped {{date|date:'YYYY-MM-DD'}}

## Notes

{{highlights}}

## README

{{content}}
