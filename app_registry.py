import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format='%(asctime)s [FoxxGent] %(levelname)s: %(message)s')
logger = logging.getLogger("foxxgent")


@dataclass
class AppConfig:
    id: str
    name: str
    category: str
    icon: str
    auth_type: str  # oauth, api_key, bearer, basic
    auth_fields: List[Dict[str, str]]  # field name, label, type, required
    scopes: List[str] = field(default_factory=list)
    api_base_url: str = ""
    documentation: str = ""
    capabilities: List[str] = field(default_factory=list)


APP_REGISTRY: Dict[str, AppConfig] = {
    # Communication
    "gmail": AppConfig(
        id="gmail", name="Gmail", category="Communication",
        icon="📧", auth_type="oauth",
        auth_fields=[{"name": "credentials_path", "label": "OAuth Credentials File", "type": "file", "required": True}],
        scopes=["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"],
        api_base_url="https://gmail.googleapis.com/gmail/v1",
        documentation="https://developers.google.com/gmail/api",
        capabilities=["read_emails", "send_emails", "search_emails", "manage_labels"]
    ),
    "google_calendar": AppConfig(
        id="google_calendar", name="Google Calendar", category="Communication",
        icon="📅", auth_type="oauth",
        auth_fields=[{"name": "credentials_path", "label": "OAuth Credentials File", "type": "file", "required": True}],
        scopes=["https://www.googleapis.com/auth/calendar.readonly", "https://www.googleapis.com/auth/calendar.events"],
        api_base_url="https://www.googleapis.com/calendar/v3",
        documentation="https://developers.google.com/calendar/api",
        capabilities=["list_events", "create_event", "delete_event", "update_event"]
    ),
    "slack": AppConfig(
        id="slack", name="Slack", category="Communication",
        icon="💬", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "bot_token", "label": "Bot Token (xoxb-...)", "type": "password", "required": False}
        ],
        scopes=["channels:read", "channels:write", "chat:write", "users:read"],
        api_base_url="https://slack.com/api",
        documentation="https://api.slack.com/",
        capabilities=["send_message", "list_channels", "create_channel", "manage_members"]
    ),
    "discord": AppConfig(
        id="discord", name="Discord", category="Communication",
        icon="🎮", auth_type="bearer",
        auth_fields=[
            {"name": "bot_token", "label": "Bot Token", "type": "password", "required": True}
        ],
        api_base_url="https://discord.com/api/v10",
        documentation="https://discord.com/developers/docs",
        capabilities=["send_message", "manage_guild", "list_channels", "manage_roles"]
    ),
    "telegram": AppConfig(
        id="telegram", name="Telegram", category="Communication",
        icon="✈️", auth_type="api_key",
        auth_fields=[
            {"name": "bot_token", "label": "Bot Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.telegram.org/bot",
        documentation="https://core.telegram.org/bots/api",
        capabilities=["send_message", "manage_groups", "webhooks", "inline keyboards"]
    ),
    "whatsapp": AppConfig(
        id="whatsapp", name="WhatsApp", category="Communication",
        icon="💙", auth_type="api_key",
        auth_fields=[
            {"name": "phone_number_id", "label": "Phone Number ID", "type": "text", "required": True},
            {"name": "access_token", "label": "Access Token", "type": "password", "required": True},
            {"name": "business_account_id", "label": "Business Account ID", "type": "text", "required": False}
        ],
        api_base_url="https://graph.facebook.com/v18.0",
        documentation="https://developers.facebook.com/docs/whatsapp",
        capabilities=["send_message", "send_template", "manage_templates"]
    ),
    "microsoft_teams": AppConfig(
        id="microsoft_teams", name="Microsoft Teams", category="Communication",
        icon="👥", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "tenant_id", "label": "Tenant ID", "type": "text", "required": True}
        ],
        scopes=["Team.ReadBasic.All", "Channel.ReadBasic.All", "ChatMessage.Send"],
        api_base_url="https://graph.microsoft.com/v1.0",
        documentation="https://learn.microsoft.com/en-us/microsoftteams/",
        capabilities=["send_message", "list_teams", "manage_channels"]
    ),
    "zoom": AppConfig(
        id="zoom", name="Zoom", category="Communication",
        icon="📹", auth_type="jwt",
        auth_fields=[
            {"name": "account_id", "label": "Account ID", "type": "text", "required": True},
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True}
        ],
        api_base_url="https://api.zoom.us/v2",
        documentation="https://marketplace.zoom.us/docs/api-reference",
        capabilities=["create_meeting", "list_meetings", "manage_users"]
    ),
    
    # Productivity
    "notion": AppConfig(
        id="notion", name="Notion", category="Productivity",
        icon="📝", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "Integration Token", "type": "password", "required": True},
            {"name": "database_id", "label": "Default Database ID", "type": "text", "required": False}
        ],
        api_base_url="https://api.notion.com/v1",
        documentation="https://developers.notion.com/",
        capabilities=["list_databases", "query_database", "create_page", "update_page", "create_database"]
    ),
    "trello": AppConfig(
        id="trello", name="Trello", category="Productivity",
        icon="📋", auth_type="api_key",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "text", "required": True},
            {"name": "token", "label": "Access Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.trello.com/1",
        documentation="https://developer.atlassian.com/cloud/trello/rest/",
        capabilities=["list_boards", "create_card", "manage_lists", "create_board"]
    ),
    "asana": AppConfig(
        id="asana", name="Asana", category="Productivity",
        icon="✅", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Personal Access Token", "type": "password", "required": True}
        ],
        api_base_url="https://app.asana.com/api/1.0",
        documentation="https://developers.asana.com/",
        capabilities=["list_projects", "create_task", "manage_workspaces", "create_project"]
    ),
    "todoist": AppConfig(
        id="todoist", name="Todoist", category="Productivity",
        icon="🎯", auth_type="bearer",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.todoist.com/rest/v2",
        documentation="https://developer.todoist.com/rest/v2",
        capabilities=["list_tasks", "create_task", "complete_task", "manage_projects"]
    ),
    "airtable": AppConfig(
        id="airtable", name="Airtable", category="Productivity",
        icon="🗃️", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True},
            {"name": "base_id", "label": "Base ID", "type": "text", "required": False}
        ],
        api_base_url="https://api.airtable.com/v0",
        documentation="https://airtable.com/api",
        capabilities=["list_records", "create_record", "update_record", "manage_bases"]
    ),
    "clickup": AppConfig(
        id="clickup", name="ClickUp", category="Productivity",
        icon="🖱️", auth_type="bearer",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.clickup.com/api/v2",
        documentation="https://clickup.com/api",
        capabilities=["list_tasks", "create_task", "manage_spaces", "create_folder"]
    ),
    "monday": AppConfig(
        id="monday", name="Monday.com", category="Productivity",
        icon="📊", auth_type="api_key",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.monday.com/v2",
        documentation="https://developer.monday.com/",
        capabilities=["list_boards", "create_item", "manage_groups", "create_board"]
    ),
    "notion_calendar": AppConfig(
        id="notion_calendar", name="Notion Calendar", category="Productivity",
        icon="🗓️", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "Integration Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.notion.com/v1",
        capabilities=["sync_calendar", "create_event", "manage_schedule"]
    ),
    
    # Cloud Storage
    "google_drive": AppConfig(
        id="google_drive", name="Google Drive", category="Cloud Storage",
        icon="💾", auth_type="oauth",
        auth_fields=[{"name": "credentials_path", "label": "OAuth Credentials File", "type": "file", "required": True}],
        scopes=["https://www.googleapis.com/auth/drive"],
        api_base_url="https://www.googleapis.com/drive/v3",
        documentation="https://developers.google.com/drive/api",
        capabilities=["list_files", "upload_file", "download_file", "manage_permissions"]
    ),
    "dropbox": AppConfig(
        id="dropbox", name="Dropbox", category="Cloud Storage",
        icon="📦", auth_type="oauth",
        auth_fields=[
            {"name": "app_key", "label": "App Key", "type": "text", "required": True},
            {"name": "app_secret", "label": "App Secret", "type": "password", "required": True},
            {"name": "access_token", "label": "Access Token", "type": "password", "required": False}
        ],
        api_base_url="https://api.dropboxapi.com/2",
        documentation="https://www.dropbox.com/developers",
        capabilities=["list_files", "upload_file", "create_folder", "share_link"]
    ),
    "onedrive": AppConfig(
        id="onedrive", name="OneDrive", category="Cloud Storage",
        icon="☁️", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True}
        ],
        scopes=["Files.ReadWrite.All"],
        api_base_url="https://graph.microsoft.com/v1.0",
        documentation="https://docs.microsoft.com/en-us/onedrive/",
        capabilities=["list_files", "upload_file", "download_file", "create_folder"]
    ),
    "box": AppConfig(
        id="box", name="Box", category="Cloud Storage",
        icon="📁", auth_type="jwt",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "enterprise_id", "label": "Enterprise ID", "type": "text", "required": True},
            {"name": "private_key", "label": "Private Key", "type": "textarea", "required": True}
        ],
        api_base_url="https://api.box.com/2.0",
        documentation="https://developer.box.com/",
        capabilities=["list_files", "upload_file", "manage_collaborations"]
    ),
    
    # Developer Tools
    "github": AppConfig(
        id="github", name="GitHub", category="Developer Tools",
        icon="🐙", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Personal Access Token", "type": "password", "required": True}
        ],
        scopes=["repo", "read:user"],
        api_base_url="https://api.github.com",
        documentation="https://docs.github.com/en/rest",
        capabilities=["list_repos", "create_issue", "create_pr", "manage_webhooks", "run_actions"]
    ),
    "gitlab": AppConfig(
        id="gitlab", name="GitLab", category="Developer Tools",
        icon="🦊", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Personal Access Token", "type": "password", "required": True},
            {"name": "gitlab_url", "label": "GitLab URL", "type": "text", "required": True}
        ],
        scopes=["api", "read_user"],
        api_base_url="https://gitlab.com/api/v4",
        documentation="https://docs.gitlab.com/ee/api/",
        capabilities=["list_projects", "create_issue", "manage_mr", "trigger_pipeline"]
    ),
    "bitbucket": AppConfig(
        id="bitbucket", name="Bitbucket", category="Developer Tools",
        icon="🪣", auth_type="bearer",
        auth_fields=[
            {"name": "app_password", "label": "App Password", "type": "password", "required": True},
            {"name": "username", "label": "Username", "type": "text", "required": True}
        ],
        scopes=["repo", "pullrequest"],
        api_base_url="https://api.bitbucket.org/2.0",
        documentation="https://developer.atlassian.com/cloud/bitbucket/",
        capabilities=["list_repos", "create_repo", "create_pr"]
    ),
    "jira": AppConfig(
        id="jira", name="Jira", category="Developer Tools",
        icon="📜", auth_type="basic",
        auth_fields=[
            {"name": "domain", "label": "Jira Domain", "type": "text", "required": True},
            {"name": "email", "label": "Email", "type": "text", "required": True},
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.atlassian.com/ex/jira",
        documentation="https://developer.atlassian.com/cloud/jira/",
        capabilities=["list_issues", "create_issue", "manage_projects", "create_sprint"]
    ),
    "linear": AppConfig(
        id="linear", name="Linear", category="Developer Tools",
        icon="📏", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.linear.app/graphql",
        documentation="https://developers.linear.app/",
        capabilities=["list_issues", "create_issue", "manage_teams", "create_project"]
    ),
    
    # Monitoring & DevOps
    "datadog": AppConfig(
        id="datadog", name="Datadog", category="Monitoring",
        icon="🐕", auth_type="api_key",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True},
            {"name": "app_key", "label": "App Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.datadoghq.com/api/v1",
        documentation="https://docs.datadoghq.com/api/",
        capabilities=["query_metrics", "create_alert", "manage_monitors"]
    ),
    "new_relic": AppConfig(
        id="new_relic", name="New Relic", category="Monitoring",
        icon="📈", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "License Key", "type": "password", "required": True},
            {"name": "account_id", "label": "Account ID", "type": "text", "required": True}
        ],
        api_base_url="https://api.newrelic.com/v2",
        documentation="https://docs.newrelic.com/docs/apis/",
        capabilities=["query_metrics", "list_apps", "manage_alerts"]
    ),
    "sentry": AppConfig(
        id="sentry", name="Sentry", category="Monitoring",
        icon="🐦", auth_type="bearer",
        auth_fields=[
            {"name": "auth_token", "label": "Auth Token", "type": "password", "required": True},
            {"name": "organization_slug", "label": "Organization", "type": "text", "required": True}
        ],
        api_base_url="https://sentry.io/api/0",
        documentation="https://docs.sentry.io/api/",
        capabilities=["list_issues", "create_project", "manage_releases"]
    ),
    "pagerduty": AppConfig(
        id="pagerduty", name="PagerDuty", category="Monitoring",
        icon="🔔", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.pagerduty.com",
        documentation="https://developer.pagerduty.com/",
        capabilities=["create_incident", "manage_oncall", "create_service"]
    ),
    "cloudflare": AppConfig(
        id="cloudflare", name="Cloudflare", category="DevOps",
        icon="☁️", auth_type="bearer",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True},
            {"name": "account_id", "label": "Account ID", "type": "text", "required": True}
        ],
        scopes=["zone:read", "zone:edit"],
        api_base_url="https://api.cloudflare.com/client/v4",
        documentation="https://developers.cloudflare.com/",
        capabilities=["list_zones", "manage_dns", "create_record", "purge_cache"]
    ),
    "aws": AppConfig(
        id="aws", name="AWS", category="DevOps",
        icon="🟧", auth_type="aws",
        auth_fields=[
            {"name": "access_key_id", "label": "Access Key ID", "type": "text", "required": True},
            {"name": "secret_access_key", "label": "Secret Access Key", "type": "password", "required": True},
            {"name": "region", "label": "Default Region", "type": "text", "required": True}
        ],
        api_base_url="https://sts.amazonaws.com",
        documentation="https://docs.aws.amazon.com/",
        capabilities=["ec2_manage", "s3_manage", "lambda_invoke", "cloudwatch_query"]
    ),
    "heroku": AppConfig(
        id="heroku", name="Heroku", category="DevOps",
        icon="🟣", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.heroku.com",
        documentation="https://devcenter.heroku.com/articles/platform-api",
        capabilities=["list_apps", "deploy_app", "manage_dynos", "view_logs"]
    ),
    "digitalocean": AppConfig(
        id="digitalocean", name="DigitalOcean", category="DevOps",
        icon="🌊", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Access Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.digitalocean.com/v2",
        documentation="https://docs.digitalocean.com/reference/api/",
        capabilities=["list_droplets", "create_droplet", "manage_volumes"]
    ),
    "vercel": AppConfig(
        id="vercel", name="Vercel", category="DevOps",
        icon="▲", auth_type="bearer",
        auth_fields=[
            {"name": "token", "label": "Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.vercel.com/v6",
        documentation="https://vercel.com/docs/rest-api",
        capabilities=["list_deployments", "create_deployment", "manage_domains"]
    ),
    
    # CRM & Sales
    "salesforce": AppConfig(
        id="salesforce", name="Salesforce", category="CRM",
        icon="☁️", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Consumer Key", "type": "text", "required": True},
            {"name": "client_secret", "label": "Consumer Secret", "type": "password", "required": True},
            {"name": "instance_url", "label": "Instance URL", "type": "text", "required": True}
        ],
        scopes=["api", "refresh_token"],
        api_base_url="https://login.salesforce.com/services/data/v58.0",
        documentation="https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/",
        capabilities=["query_objects", "create_record", "manage_leads"]
    ),
    "hubspot": AppConfig(
        id="hubspot", name="HubSpot", category="CRM",
        icon="🍯", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Private App Token", "type": "password", "required": True}
        ],
        scopes=["crm.objects.contacts.read", "crm.objects.deals.read"],
        api_base_url="https://api.hubspot.com/crm/v3",
        documentation="https://developers.hubspot.com/docs/api/overview",
        capabilities=["list_contacts", "create_contact", "manage_deals", "create_ticket"]
    ),
    "pipedrive": AppConfig(
        id="pipedrive", name="Pipedrive", category="CRM",
        icon="📈", auth_type="bearer",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.pipedrive.com/v1",
        documentation="https://developers.pipedrive.com/docs/api/v1/",
        capabilities=["list_deals", "create_deal", "manage_persons", "list_activities"]
    ),
    "zoho_crm": AppConfig(
        id="zoho_crm", name="Zoho CRM", category="CRM",
        icon="🟢", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "datacenter", "label": "Data Center (com/in/eu/etc)", "type": "text", "required": True}
        ],
        scopes=["ZohoCRM.modules.all", "ZohoCRM.settings.all"],
        api_base_url="https://www.zohoapis.com/crm/v2",
        documentation="https://www.zoho.com/crm/developer/docs/api/",
        capabilities=["list_leads", "create_contact", "manage_deals"]
    ),
    
    # Marketing
    "mailchimp": AppConfig(
        id="mailchimp", name="Mailchimp", category="Marketing",
        icon="🐵", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True},
            {"name": "server_prefix", "label": "Server Prefix (us1, us2...)", "type": "text", "required": True}
        ],
        api_base_url="https://<server>.api.mailchimp.com/3.0",
        documentation="https://mailchimp.com/developer/",
        capabilities=["list_subscribers", "add_subscriber", "create_campaign", "send_campaign"]
    ),
    "sendgrid": AppConfig(
        id="sendgrid", name="SendGrid", category="Marketing",
        icon="📨", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.sendgrid.com/v3",
        documentation="https://docs.sendgrid.com/",
        capabilities=["send_email", "create_template", "manage_lists", "view_stats"]
    ),
    "buffer": AppConfig(
        id="buffer", name="Buffer", category="Marketing",
        icon="🫙", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Access Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.bufferapp.com/1",
        documentation="https://buffer.com/developers",
        capabilities=["list_profiles", "schedule_post", "update_profile"]
    ),
    "hootsuite": AppConfig(
        id="hootsuite", name="Hootsuite", category="Marketing",
        icon="🦉", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True}
        ],
        scopes=["content.write", "content.read", "analytics.read"],
        api_base_url="https://api.hootsuite.com/v1",
        documentation="https://developer.hootsuite.com/",
        capabilities=["schedule_post", "list_social_profiles", "get_analytics"]
    ),
    
    # Finance
    "quickbooks": AppConfig(
        id="quickbooks", name="QuickBooks", category="Finance",
        icon="📕", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "realm_id", "label": "Company ID", "type": "text", "required": True}
        ],
        scopes=["com.intuit.quickbooks.accounting"],
        api_base_url="https://quickbooks.api.intuit.com/v3",
        documentation="https://developer.intuit.com/",
        capabilities=["create_invoice", "list_customers", "manage_vendors"]
    ),
    "xero": AppConfig(
        id="xero", name="Xero", category="Finance",
        icon="🧾", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True}
        ],
        scopes=["openid", "profile", "email", "accounting.read", "accounting.write"],
        api_base_url="https://api.xero.com/api.xro/2.0",
        documentation="https://developer.xero.com/",
        capabilities=["create_invoice", "list_contacts", "get_reports"]
    ),
    "stripe": AppConfig(
        id="stripe", name="Stripe", category="Finance",
        icon="💳", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "Secret Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.stripe.com/v1",
        documentation="https://stripe.com/docs/api",
        capabilities=["create_charge", "list_customers", "create_payment_intent", "list_invoices"]
    ),
    "plaid": AppConfig(
        id="plaid", name="Plaid", category="Finance",
        icon="🏦", auth_type="basic",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "secret", "label": "Secret", "type": "password", "required": True},
            {"name": "environment", "label": "Environment (sandbox/development/production)", "type": "text", "required": True}
        ],
        api_base_url="https://sandbox.plaid.com",
        documentation="https://plaid.com/docs/",
        capabilities=["link_token", "exchange_token", "get_balance", "get_transactions"]
    ),
    
    # Analytics
    "google_analytics": AppConfig(
        id="google_analytics", name="Google Analytics", category="Analytics",
        icon="📊", auth_type="oauth",
        auth_fields=[{"name": "credentials_path", "label": "OAuth Credentials File", "type": "file", "required": True}],
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        api_base_url="https://analyticsdata.googleapis.com/v1beta",
        documentation="https://developers.google.com/analytics/devguides/reporting/data/v1",
        capabilities=["run_report", "get_metadata", "list_accounts"]
    ),
    "mixpanel": AppConfig(
        id="mixpanel", name="Mixpanel", category="Analytics",
        icon="🔬", auth_type="bearer",
        auth_fields=[
            {"name": "service_account_username", "label": "Service Account Username", "type": "text", "required": True},
            {"name": "service_account_secret", "label": "Service Account Secret", "type": "password", "required": True}
        ],
        api_base_url="https://api.mixpanel.com",
        documentation="https://developer.mixpanel.com/",
        capabilities=["track_event", "list_events", "get_insights"]
    ),
    "amplitude": AppConfig(
        id="amplitude", name="Amplitude", category="Analytics",
        icon="📈", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "text", "required": True},
            {"name": "secret_key", "label": "Secret Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.amplitude.com/2",
        documentation="https://developers.amplitude.com/",
        capabilities=["track_event", "get_data", "list_charts"]
    ),
    
    # AI & ML
    "openai": AppConfig(
        id="openai", name="OpenAI", category="AI & ML",
        icon="🤖", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.openai.com/v1",
        documentation="https://platform.openai.com/docs/",
        capabilities=["complete", "embed", "image_create", "chat_completion"]
    ),
    "anthropic": AppConfig(
        id="anthropic", name="Anthropic (Claude)", category="AI & ML",
        icon="🧠", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.anthropic.com/v1",
        documentation="https://docs.anthropic.com/",
        capabilities=["complete", "message"]
    ),
    "huggingface": AppConfig(
        id="huggingface", name="Hugging Face", category="AI & ML",
        icon="🤗", auth_type="bearer",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api-inference.huggingface.co",
        documentation="https://huggingface.co/docs/api",
        capabilities=["inference", "list_models", "deploy_model"]
    ),
    "replicate": AppConfig(
        id="replicate", name="Replicate", category="AI & ML",
        icon="🔄", auth_type="bearer",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.replicate.com/v1",
        documentation="https://replicate.com/docs/reference/http",
        capabilities=["run_model", "list_models", "get_prediction"]
    ),
    
    # Database
    "mongodb": AppConfig(
        id="mongodb", name="MongoDB", category="Database",
        icon="🍃", auth_type="connection_string",
        auth_fields=[
            {"name": "connection_string", "label": "Connection String", "type": "password", "required": True},
            {"name": "database", "label": "Database Name", "type": "text", "required": False}
        ],
        api_base_url="mongodb+srv://",
        documentation="https://www.mongodb.com/docs/atlas/",
        capabilities=["find_documents", "insert_document", "update_document", "aggregate"]
    ),
    "supabase": AppConfig(
        id="supabase", name="Supabase", category="Database",
        icon="🟢", auth_type="bearer",
        auth_fields=[
            {"name": "url", "label": "Project URL", "type": "text", "required": True},
            {"name": "anon_key", "label": "Anon Key", "type": "password", "required": True},
            {"name": "service_key", "label": "Service Role Key", "type": "password", "required": False}
        ],
        api_base_url="https://<project>.supabase.co/rest/v1",
        documentation="https://supabase.com/docs",
        capabilities=["query_table", "insert_row", "update_row", "manage_auth"]
    ),
    "planetscale": AppConfig(
        id="planetscale", name="PlanetScale", category="Database",
        icon="⚡", auth_type="bearer",
        auth_fields=[
            {"name": "database_url", "label": "Database URL", "type": "text", "required": True},
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.planetscale.com/v1",
        documentation="https://planetscale.com/docs/",
        capabilities=["execute_query", "list_branches", "deploy_branch"]
    ),
    
    # Other
    "webflow": AppConfig(
        id="webflow", name="Webflow", category="Websites",
        icon="🌊", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Access Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.webflow.com/v1",
        documentation="https://developers.webflow.com/",
        capabilities=["list_sites", "publish_site", "list_collections"]
    ),
    "shopify": AppConfig(
        id="shopify", name="Shopify", category="E-commerce",
        icon="🛒", auth_type="oauth",
        auth_fields=[
            {"name": "shop_name", "label": "Shop Name", "type": "text", "required": True},
            {"name": "access_token", "label": "Access Token", "type": "password", "required": True}
        ],
        scopes=["read_products", "write_orders", "read_customers"],
        api_base_url="https://<shop>.myshopify.com/admin/api/2024-01",
        documentation="https://shopify.dev/docs/api/admin-rest",
        capabilities=["list_products", "create_order", "manage_customers"]
    ),
    "cal_com": AppConfig(
        id="cal_com", name="Cal.com", category="Scheduling",
        icon="📅", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True},
            {"name": "base_url", "label": "Base URL", "type": "text", "required": True}
        ],
        api_base_url="https://api.cal.com/v1",
        documentation="https://docs.cal.com/",
        capabilities=["list_bookings", "create_booking", "list_event_types"]
    ),
    "calendly": AppConfig(
        id="calendly", name="Calendly", category="Scheduling",
        icon="📆", auth_type="bearer",
        auth_fields=[
            {"name": "api_token", "label": "API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.calendly.com/v2",
        documentation="https://developer.calendly.com/",
        capabilities=["list_events", "list_event_types", "schedule_event"]
    ),
    
    # Mail Apps
    "outlook": AppConfig(
        id="outlook", name="Outlook / Microsoft 365", category="Mail",
        icon="📧", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "tenant_id", "label": "Tenant ID", "type": "text", "required": True}
        ],
        scopes=["Mail.Read", "Mail.Send", "User.Read"],
        api_base_url="https://graph.microsoft.com/v1.0",
        documentation="https://docs.microsoft.com/en-us/graph/api/resources/mail-api",
        capabilities=["list_emails", "send_email", "list_folders", "create_folder"]
    ),
    "yahoo_mail": AppConfig(
        id="yahoo_mail", name="Yahoo Mail", category="Mail",
        icon="📨", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True}
        ],
        scopes=["mail-read", "mail-send"],
        api_base_url="https://api.mail.yahoo.com",
        documentation="https://developer.yahoo.com/mail/",
        capabilities=["list_emails", "send_email", "list_folders"]
    ),
    "proton_mail": AppConfig(
        id="proton_mail", name="Proton Mail", category="Mail",
        icon="🔒", auth_type="bearer",
        auth_fields=[
            {"name": "access_token", "label": "Access Token", "type": "password", "required": True}
        ],
        scopes=["mail.read", "mail.send"],
        api_base_url="https://api.protonmail.com",
        documentation="https://developers.protonmail.com/",
        capabilities=["list_emails", "send_email", "get_contacts"]
    ),
    "zoho_mail": AppConfig(
        id="zoho_mail", name="Zoho Mail", category="Mail",
        icon="📬", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True},
            {"name": "org_id", "label": "Organization ID", "type": "text", "required": True}
        ],
        scopes=["Zt Mgmt.Domains", "Zt Mgmt.Org"],
        api_base_url="https://mail.zoho.com/api",
        documentation="https://www.zoho.com/mail/help/api/",
        capabilities=["list_emails", "send_email", "list_folders", "create_filter"]
    ),
    "fastmail": AppConfig(
        id="fastmail", name="Fastmail", category="Mail",
        icon="⚡", auth_type="basic",
        auth_fields=[
            {"name": "email", "label": "Email", "type": "text", "required": True},
            {"name": "app_password", "label": "App Password", "type": "password", "required": True}
        ],
        scopes=["email"],
        api_base_url="https://api.fastmail.com",
        documentation="https://www.fastmail.com/dev/masked/",
        capabilities=["list_emails", "send_email", "get_folders"]
    ),
    "icloud_mail": AppConfig(
        id="icloud_mail", name="iCloud Mail", category="Mail",
        icon="☁️", auth_type="oauth",
        auth_fields=[
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "client_secret", "label": "Client Secret", "type": "password", "required": True}
        ],
        scopes=["READ", "WRITE"],
        api_base_url="https://api.icloud.com",
        documentation="https://developer.apple.com/cloudkit/",
        capabilities=["list_emails", "send_email"]
    ),
    "gmaily": AppConfig(
        id="gmaily", name="Gmail (Y)", category="Mail",
        icon="📧", auth_type="oauth",
        auth_fields=[{"name": "credentials_path", "label": "OAuth Credentials File", "type": "file", "required": True}],
        scopes=["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"],
        api_base_url="https://gmail.googleapis.com/gmail/v1",
        documentation="https://developers.google.com/gmail/api",
        capabilities=["list_emails", "send_email", "search_emails", "manage_labels", "create_label", "get_threads"]
    ),
    "google_workspace": AppConfig(
        id="google_workspace", name="Google Workspace", category="Mail",
        icon="🏢", auth_type="oauth",
        auth_fields=[{"name": "credentials_path", "label": "OAuth Credentials File", "type": "file", "required": True}],
        scopes=["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/admin.directory.user"],
        api_base_url="https://gmail.googleapis.com/gmail/v1",
        documentation="https://developers.google.com/gmail/api",
        capabilities=["list_emails", "send_email", "manage_users", "manage_groups", "create_group"]
    ),
    "postmark": AppConfig(
        id="postmark", name="Postmark", category="Mail",
        icon="📮", auth_type="bearer",
        auth_fields=[
            {"name": "server_api_token", "label": "Server API Token", "type": "password", "required": True}
        ],
        api_base_url="https://api.postmarkapp.com",
        documentation="https://postmarkapp.com/developer/api",
        capabilities=["send_email", "get_bounces", "get_deliveries"]
    ),
    "mailgun": AppConfig(
        id="mailgun", name="Mailgun", category="Mail",
        icon="🔫", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True},
            {"name": "domain", "label": "Domain", "type": "text", "required": True}
        ],
        api_base_url="https://api.mailgun.net/v3",
        documentation="https://documentation.mailgun.com/",
        capabilities=["send_email", "get_events", "get_stats"]
    ),
    "resend": AppConfig(
        id="resend", name="Resend", category="Mail",
        icon="📤", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.resend.com",
        documentation="https://resend.com/docs",
        capabilities=["send_email", "list_domains", "get_batches"]
    ),
    "brevo": AppConfig(
        id="brevo", name="Brevo (Sendinblue)", category="Mail",
        icon="💙", auth_type="bearer",
        auth_fields=[
            {"name": "api_key", "label": "API Key", "type": "password", "required": True}
        ],
        api_base_url="https://api.brevo.com/v3",
        documentation="https://developers.brevo.com/",
        capabilities=["send_email", "list_contacts", "create_contact", "get_campaigns"]
    ),
}


def get_apps_by_category() -> Dict[str, List[AppConfig]]:
    categories = {}
    for app in APP_REGISTRY.values():
        if app.category not in categories:
            categories[app.category] = []
        categories[app.category].append(app)
    return categories


def get_app_config(app_id: str) -> Optional[AppConfig]:
    return APP_REGISTRY.get(app_id)


def get_all_apps() -> List[AppConfig]:
    return list(APP_REGISTRY.values())


def get_app_categories() -> List[str]:
    return list(set(app.category for app in APP_REGISTRY.values()))