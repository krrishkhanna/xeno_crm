from __future__ import annotations

from dataclasses import dataclass

from app.agent.schemas import (
    CampaignListItem,
    CreateCampaignInput,
    DraftMessageInput,
    GetCampaignAnalyticsInput,
    ListCampaignsInput,
    QueryCustomersInput,
    SendCampaignInput,
)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_model: type

    def openai_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


QUERY_CUSTOMERS = ToolSpec(
    name="query_customers",
    description="Query CRM customers using a segment definition and return audience size with a small preview.",
    input_model=QueryCustomersInput,
)
CREATE_CAMPAIGN = ToolSpec(
    name="create_campaign",
    description="Create a campaign record for a drafted marketing message and segment definition.",
    input_model=CreateCampaignInput,
)
DRAFT_MESSAGE = ToolSpec(
    name="draft_message",
    description="Draft a campaign message and a campaign name based on the marketing objective and segment summary.",
    input_model=DraftMessageInput,
)
SEND_CAMPAIGN = ToolSpec(
    name="send_campaign",
    description="Dispatch a campaign to the channel service and queue communications.",
    input_model=SendCampaignInput,
)
GET_CAMPAIGN_ANALYTICS = ToolSpec(
    name="get_campaign_analytics",
    description="Fetch campaign delivery analytics from the CRM backend.",
    input_model=GetCampaignAnalyticsInput,
)
LIST_CAMPAIGNS = ToolSpec(
    name="list_campaigns",
    description="List recent campaigns with their current status.",
    input_model=ListCampaignsInput,
)

TOOL_SPECS = [
    QUERY_CUSTOMERS,
    CREATE_CAMPAIGN,
    DRAFT_MESSAGE,
    SEND_CAMPAIGN,
    GET_CAMPAIGN_ANALYTICS,
    LIST_CAMPAIGNS,
]


def get_tool_spec(name: str) -> ToolSpec:
    for spec in TOOL_SPECS:
        if spec.name == name:
            return spec
    raise KeyError(name)


def openai_tool_definitions() -> list[dict]:
    return [spec.openai_definition() for spec in TOOL_SPECS]
