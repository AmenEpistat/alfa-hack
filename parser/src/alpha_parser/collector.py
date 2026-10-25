"""Add source evidence to a collection without an extra model agent."""


class SourceCollector:
    @staticmethod
    def gap(run, text):
        if text not in run["gaps"]:
            run["gaps"].append(text)

    def add_document(self, run, doc):
        if doc["quality"] == "failed":
            self.gap(run, "A requested document failed extraction")
            return
        if doc["version_id"] not in [x["version_id"] for x in run["documents"]]:
            run["documents"].append({k: doc[k] for k in ("document_id", "version_id", "source_type", "source_name", "url", "title", "quality", "published_at")})
        if not doc["published_at"]:
            self.gap(run, "Some document publication dates are unknown")
        if doc["quality"] != "extracted":
            self.gap(run, "Some extracted evidence needs manual quality review")

    def add_hits(self, run, hits):
        for hit in hits:
            self.add_document(run, hit["document"])
            if hit["chunk"]["chunk_id"] not in run["chunk_ids"]:
                run["chunk_ids"].append(hit["chunk"]["chunk_id"])
