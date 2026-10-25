"""Count evidence once across revisions, fragments, topics and identical-content copies."""
TOPICS = ("news", "pdf", "competitors")


def document_groups(items):
    parents = {}

    def find(key):
        parents.setdefault(key, key)
        if parents[key] != key:
            parents[key] = find(parents[key])
        return parents[key]
    for item in items:
        document = ("document", item["document_id"])
        find(document)
        if item.get("duplicate_group"):
            content = ("content", item["duplicate_group"])
            parents[find(document)] = find(content)
    return {item["document_id"]: find(("document", item["document_id"])) for item in items}


def coverage_for(topics, min_sources=10, min_sources_per_topic=5):
    groups = document_groups([item for topic in TOPICS for item in topics.get(topic, [])])
    by_topic = {topic: {groups[item["document_id"]] for item in topics.get(topic, [])} for topic in TOPICS}
    all_sources = set().union(*by_topic.values())
    shortfalls = {topic: min_sources_per_topic - len(keys) for topic, keys in by_topic.items()
                  if len(keys) < min_sources_per_topic}
    missing = [topic for topic in TOPICS if not by_topic[topic]]
    return {
        "min_sources": min_sources, "min_sources_per_topic": min_sources_per_topic,
        "total_sources": len(all_sources),
        "by_topic": {topic: len(keys) for topic, keys in by_topic.items()},
        "missing_topics": missing, "minimum_met": len(all_sources) >= min_sources,
        "all_topics_present": not missing, "topic_minimums_met": not shortfalls, "topic_shortfalls": shortfalls,
        "requirements_met": len(all_sources) >= min_sources and not missing and not shortfalls,
        "counting_unit": "unique documents; revisions, repeated fragments, topic overlap and identical-content copies count once",
    }


def coverage_gaps(coverage):
    gaps = []
    if not coverage["minimum_met"]:
        gaps.append(f"Minimum source requirement not met: {coverage['total_sources']}/{coverage['min_sources']} unique documents")
    if coverage["missing_topics"]:
        gaps.append("Required source topics are missing: " + ", ".join(coverage["missing_topics"]))
    for topic in coverage.get("topic_shortfalls", {}):
        gaps.append(f"Minimum source requirement for {topic} not met: "
                    f"{coverage['by_topic'][topic]}/{coverage['min_sources_per_topic']} unique documents")
    return gaps


def count_run_sources(store, run, *, source_type=None, version_ids=None):
    documents = []
    for reference in run.get("documents", []):
        if source_type and reference["source_type"] != source_type:
            continue
        if version_ids is not None and reference["version_id"] not in version_ids:
            continue
        document = store.version(reference["version_id"])
        if document:
            documents.append(document)
    return len(set(document_groups(documents).values()))


def select_diverse_hits(hits, limit):
    """Prefer one relevant fragment per unique document before additional fragments."""
    groups = document_groups([hit["document"] for hit in hits])
    first, rest, seen = [], [], set()
    for hit in hits:
        group = groups[hit["document"]["document_id"]]
        if group in seen:
            rest.append(hit)
        else:
            first.append(hit)
            seen.add(group)
    return (first + rest)[:limit]
