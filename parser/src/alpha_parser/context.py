"""Company context comes exclusively from preprocessing JSON."""
from .schemas import CompanyInput


class Context:
    def __init__(self, store):
        self.store = store

    def get(self, uid, group_id=None, role=None):
        profile = self.store.state["company_profiles"].get(uid)
        if profile is None:
            raise ValueError("Pass a company profile from preprocessing JSON first")
        spec = CompanyInput.model_validate(profile)
        if group_id and group_id != spec.group_id:
            raise ValueError("group_id does not match preprocessing profile")
        public = spec.public_context()
        return {"company_id": uid, "group_id": spec.group_id, "role": role,
                "selected_company": {"industry": spec.industry, "region": spec.region,
                                     "okved_code": spec.okved_code, "city": spec.city},
                "industries": public["industries"], "regions": public["regions"],
                "company_input": profile}

    @staticmethod
    def public(context):
        primary = context.get("selected_company", {})
        return {"company_industry": primary.get("industry"), "company_region": primary.get("region"),
                "industries": context.get("industries", []), "regions": context.get("regions", [])}
